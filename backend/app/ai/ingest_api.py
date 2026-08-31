"""PDF ingest AI routes: package-classify, spec-sections, sheet-identity via Grok.

Desktop USISPdfApp POSTs here. The xAI key never leaves this host.
"""
from __future__ import annotations

import json
import re
import uuid
from typing import Any

from flask import jsonify, request

from . import config
from .grok_client import GrokClientError, chat_completion

_ALLOWED_TYPES = frozenset(
    {"Drawing", "Specification", "BidForm", "Geotech", "AddendumNarrative", "Other"}
)
_JSON_OBJECT = {"type": "json_object"}
_SHEET_CHUNK = 4
_SPEC_IMAGE_CHUNK = 8
_MAX_B64 = 2_500_000

_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


def register_ingest_ai_routes(bp) -> None:
    @bp.post("/ai/package-classify")
    def package_classify():
        denied = _require_ai()
        if denied is not None:
            return denied
        item = _unwrap_item(request.get_json(silent=True))
        if item is None:
            return jsonify({"error": "expected JSON object with item"}), 400
        try:
            result = _classify_package(item)
        except GrokClientError as exc:
            return jsonify({"error": exc.message}), 502
        return jsonify({"item": result})

    @bp.post("/ai/spec-sections")
    def spec_sections():
        denied = _require_ai()
        if denied is not None:
            return denied
        item = _unwrap_item(request.get_json(silent=True))
        if item is None:
            return jsonify({"error": "expected JSON object with item"}), 400
        try:
            result = _split_spec(item)
        except GrokClientError as exc:
            return jsonify({"error": exc.message}), 502
        return jsonify({"item": result})

    @bp.post("/ai/sheet-identity")
    def sheet_identity():
        denied = _require_ai()
        if denied is not None:
            return denied
        body = request.get_json(silent=True)
        items = _unwrap_items(body)
        if items is None:
            return jsonify({"error": "expected JSON object with items"}), 400
        try:
            result = _identify_sheets(items)
        except GrokClientError as exc:
            return jsonify({"error": exc.message}), 502
        return jsonify({"items": result})


def _require_ai():
    if not config.is_configured():
        return (
            jsonify(
                {
                    "error": "AI is not configured (USIS_AI_ENABLED and USIS_XAI_API_KEY required)"
                }
            ),
            503,
        )
    return None


def _g(d: dict[str, Any], *keys: str, default: Any = None) -> Any:
    for k in keys:
        if k in d and d[k] is not None:
            return d[k]
    return default


def _unwrap_item(body: Any) -> dict[str, Any] | None:
    if not isinstance(body, dict):
        return None
    item = body.get("item")
    if isinstance(item, dict):
        return item
    if any(k in body for k in ("files", "jobId", "job_id", "sourceId", "source_id", "pages")):
        return body
    return None


def _unwrap_items(body: Any) -> list[dict[str, Any]] | None:
    if not isinstance(body, dict):
        return None
    raw = body.get("items")
    if isinstance(raw, list):
        return [x for x in raw if isinstance(x, dict)]
    item = body.get("item")
    if isinstance(item, dict):
        return [item]
    return None


def _as_uuid_str(value: Any) -> str:
    if value is None:
        return str(uuid.uuid4())
    text = str(value).strip()
    try:
        return str(uuid.UUID(text))
    except (ValueError, AttributeError, TypeError):
        return text or str(uuid.uuid4())


def _parse_json_content(content: str | None) -> Any:
    if not content or not str(content).strip():
        return None
    s = _FENCE.sub("", str(content).strip()).strip()
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        start_obj, start_arr = s.find("{"), s.find("[")
        starts = [i for i in (start_obj, start_arr) if i >= 0]
        if not starts:
            return None
        start = min(starts)
        try:
            return json.loads(s[start:])
        except json.JSONDecodeError:
            return None


def _chat_json(system: str, user: Any) -> Any:
    result = chat_completion(
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        response_format=_JSON_OBJECT,
    )
    return _parse_json_content(result.content)


def _image_part(b64: Any) -> dict[str, Any] | None:
    if not b64:
        return None
    s = str(b64).strip()
    if not s or len(s) > _MAX_B64:
        return None
    if s.startswith("data:"):
        url = s
    else:
        url = f"data:image/jpeg;base64,{s}"
    return {"type": "image_url", "image_url": {"url": url}}


def _user_multimodal(text: str, images: list[dict[str, Any]]) -> Any:
    if not images:
        return text
    return [{"type": "text", "text": text}, *images]


# --- package-classify -------------------------------------------------------

_CLASSIFY_SYSTEM = """You classify construction bid-package files from folder and file names only.
Return JSON: {"files":[{"sourceId":"<uuid>","type":"Drawing","revision":"Addendum 1","title":"optional","confidence":0.0,"needsReview":false}]}
Allowed type values exactly: Drawing, Specification, BidForm, Geotech, AddendumNarrative, Other.
A file name that looks like a sheet number (A-101, A10.01.1, S-201, I-401, G001) is Drawing even if a parent folder says Specifications.
Use the folder name for revision when it is an addendum/ASI/bulletin; otherwise keep sessionDefaultRevision.
confidence is 0..1. needsReview true when you are guessing.
Only include files you are changing or confirming. JSON only."""


def _classify_package(item: dict[str, Any]) -> dict[str, Any]:
    files = _g(item, "files", default=[]) or []
    if not isinstance(files, list) or not files:
        return {"files": []}
    folders = _g(item, "folders", default=[]) or []
    payload = {
        "sessionDefaultRevision": _g(item, "sessionDefaultRevision", "session_default_revision") or "Bid Set",
        "folders": [
            {
                "relativePath": _g(f, "relativePath", "relative_path") or "",
                "name": _g(f, "name") or "",
            }
            for f in folders
            if isinstance(f, dict)
        ],
        "files": [
            {
                "sourceId": _as_uuid_str(_g(f, "sourceId", "source_id")),
                "relativePath": _g(f, "relativePath", "relative_path") or "",
                "fileName": _g(f, "fileName", "file_name") or "",
                "localType": _g(f, "localType", "local_type") or "",
                "localRevision": _g(f, "localRevision", "local_revision"),
            }
            for f in files
            if isinstance(f, dict)
        ],
    }
    parsed = _chat_json(_CLASSIFY_SYSTEM, json.dumps(payload, ensure_ascii=False))
    out: list[dict[str, Any]] = []
    raw_files = []
    if isinstance(parsed, dict):
        raw_files = parsed.get("files") or []
    elif isinstance(parsed, list):
        raw_files = parsed
    known = {p["sourceId"] for p in payload["files"]}
    for row in raw_files:
        if not isinstance(row, dict):
            continue
        sid = _as_uuid_str(_g(row, "sourceId", "source_id"))
        if sid not in known:
            continue
        typ = str(_g(row, "type", default="") or "").strip()
        if typ not in _ALLOWED_TYPES:
            continue
        conf = _confidence(row)
        out.append(
            {
                "sourceId": sid,
                "type": typ,
                "revision": (str(_g(row, "revision") or "").strip() or None),
                "title": (str(_g(row, "title") or "").strip() or None),
                "confidence": conf,
                "needsReview": bool(_g(row, "needsReview", "needs_review", default=conf < 0.80)),
            }
        )
    return {"files": out}


# --- spec-sections ----------------------------------------------------------

_SPEC_SYSTEM = """You split a construction specification book into CSI MasterFormat sections.
Return JSON: {"sections":[{"sectionNumber":"26 05 00","sectionTitle":"COMMON WORK RESULTS FOR ELECTRICAL","startPage":41,"endPage":48,"confidence":0.88}]}
sectionNumber must look like ## ## ## or ######. Pages are 1-based PDF indexes.
Cover ranges without gaps. Ignore running headers like 26 05 00-3 as new sections.
If you cannot find at least two real sections, return {"sections":[]}. JSON only."""


def _split_spec(item: dict[str, Any]) -> dict[str, Any]:
    pages = _g(item, "pages", default=[]) or []
    if not isinstance(pages, list):
        pages = []
    meta = {
        "fileName": _g(item, "fileName", "file_name") or "",
        "pageCount": int(_g(item, "pageCount", "page_count", default=0) or 0),
    }
    collected: list[dict[str, Any]] = []
    if not pages:
        parsed = _chat_json(
            _SPEC_SYSTEM,
            json.dumps({**meta, "pages": []}, ensure_ascii=False),
        )
        collected.extend(_spec_rows(parsed, meta["pageCount"]))
    else:
        for start in range(0, len(pages), _SPEC_IMAGE_CHUNK):
            chunk = [p for p in pages[start : start + _SPEC_IMAGE_CHUNK] if isinstance(p, dict)]
            images: list[dict[str, Any]] = []
            slim_pages: list[dict[str, Any]] = []
            for p in chunk:
                page_no = int(_g(p, "page", default=0) or 0)
                excerpt = str(_g(p, "textExcerpt", "text_excerpt") or "")[:800]
                slim_pages.append({"page": page_no, "textExcerpt": excerpt})
                img = _image_part(_g(p, "headerJpegBase64", "header_jpeg_base64"))
                if img:
                    images.append(img)
            text = json.dumps({**meta, "pages": slim_pages}, ensure_ascii=False)
            parsed = _chat_json(_SPEC_SYSTEM, _user_multimodal(text, images))
            collected.extend(_spec_rows(parsed, meta["pageCount"]))
    return {"sections": _merge_spec_sections(collected, meta["pageCount"])}


def _spec_rows(parsed: Any, page_count: int) -> list[dict[str, Any]]:
    raw = []
    if isinstance(parsed, dict):
        raw = parsed.get("sections") or []
    elif isinstance(parsed, list):
        raw = parsed
    out: list[dict[str, Any]] = []
    for row in raw:
        if not isinstance(row, dict):
            continue
        number = str(_g(row, "sectionNumber", "section_number") or "").strip()
        if not _looks_like_csi(number):
            continue
        start = _int(_g(row, "startPage", "start_page"), 1)
        end = _int(_g(row, "endPage", "end_page"), start)
        if page_count > 0:
            start = max(1, min(start, page_count))
            end = max(start, min(end, page_count))
        elif end < start:
            end = start
        out.append(
            {
                "sectionNumber": _normalize_csi(number),
                "sectionTitle": str(_g(row, "sectionTitle", "section_title") or "").strip(),
                "startPage": start,
                "endPage": end,
                "confidence": _confidence(row),
            }
        )
    return out


def _merge_spec_sections(rows: list[dict[str, Any]], page_count: int) -> list[dict[str, Any]]:
    if not rows:
        return []
    rows = sorted(rows, key=lambda r: (r["startPage"], r["sectionNumber"]))
    merged: list[dict[str, Any]] = []
    for row in rows:
        if merged and merged[-1]["sectionNumber"] == row["sectionNumber"]:
            merged[-1]["endPage"] = max(merged[-1]["endPage"], row["endPage"])
            merged[-1]["confidence"] = max(merged[-1]["confidence"], row["confidence"])
            if not merged[-1]["sectionTitle"] and row["sectionTitle"]:
                merged[-1]["sectionTitle"] = row["sectionTitle"]
            continue
        merged.append(dict(row))
    for i, row in enumerate(merged):
        if i + 1 < len(merged):
            row["endPage"] = max(row["startPage"], merged[i + 1]["startPage"] - 1)
        elif page_count > 0:
            row["endPage"] = max(row["endPage"], page_count)
    return [r for r in merged if r["endPage"] >= r["startPage"]]


def _looks_like_csi(text: str) -> bool:
    s = re.sub(r"(?i)^section\s+", "", (text or "").strip())
    if re.fullmatch(r"\d{2}\s+\d{2}\s+\d{2}", s):
        return True
    if re.fullmatch(r"\d{6}", s):
        return True
    return False


def _normalize_csi(text: str) -> str:
    s = re.sub(r"(?i)^section\s+", "", (text or "").strip())
    m = re.fullmatch(r"(\d{2})\s+(\d{2})\s+(\d{2})", s)
    if m:
        return f"{m.group(1)} {m.group(2)} {m.group(3)}"
    m = re.fullmatch(r"(\d{2})(\d{2})(\d{2})", s)
    if m:
        return f"{m.group(1)} {m.group(2)} {m.group(3)}"
    return s


# --- sheet-identity ---------------------------------------------------------

_IDENTIFY_SYSTEM = """You read US construction drawing title blocks (usually bottom-right).
Return JSON: {"items":[{"rowId":"<uuid>","sheetNumber":"A-101","sheetTitle":"FIRST FLOOR PLAN","revisionLabel":"Rev 1","confidence":0.92,"needsReview":false}]}
sheetNumber must look like A-101, A10.01.1, I-401, S-201, G001 — never "Page 12", "Untitled", or the PDF file name.
sheetTitle is the drawing name from the title block, not the file stem.
revisionLabel is the issue/rev in the block (Rev 1, Addendum 2) or null.
If a field is unreadable, use null and lower confidence / needsReview true.
One output item per input rowId. JSON only."""


def _identify_sheets(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for start in range(0, len(items), _SHEET_CHUNK):
        chunk = items[start : start + _SHEET_CHUNK]
        out.extend(_identify_chunk(chunk))
    return out


def _identify_chunk(chunk: list[dict[str, Any]]) -> list[dict[str, Any]]:
    images: list[dict[str, Any]] = []
    slim: list[dict[str, Any]] = []
    known: set[str] = set()
    for item in chunk:
        rid = _as_uuid_str(_g(item, "rowId", "row_id"))
        known.add(rid)
        slim.append(
            {
                "rowId": rid,
                "sourceFileName": _g(item, "sourceFileName", "source_file_name") or "",
                "sourcePage": _g(item, "sourcePage", "source_page"),
                "pageLabel": _g(item, "pageLabel", "page_label"),
                "bookmarkTitle": _g(item, "bookmarkTitle", "bookmark_title"),
                "proposedSheetNumber": _g(item, "proposedSheetNumber", "proposed_sheet_number"),
                "proposedSheetTitle": _g(item, "proposedSheetTitle", "proposed_sheet_title"),
            }
        )
        tb = _image_part(_g(item, "titleBlockJpegBase64", "title_block_jpeg_base64"))
        full = _image_part(_g(item, "fullPageJpegBase64", "full_page_jpeg_base64"))
        if tb:
            images.append(tb)
        if full:
            images.append(full)
    text = json.dumps({"items": slim}, ensure_ascii=False)
    parsed = _chat_json(_IDENTIFY_SYSTEM, _user_multimodal(text, images))
    raw = []
    if isinstance(parsed, dict):
        raw = parsed.get("items") or []
    elif isinstance(parsed, list):
        raw = parsed
    out: list[dict[str, Any]] = []
    for row in raw:
        if not isinstance(row, dict):
            continue
        rid = _as_uuid_str(_g(row, "rowId", "row_id"))
        if rid not in known:
            continue
        number = str(_g(row, "sheetNumber", "sheet_number") or "").strip() or None
        title = str(_g(row, "sheetTitle", "sheet_title") or "").strip() or None
        rev = str(_g(row, "revisionLabel", "revision_label") or "").strip() or None
        conf = _confidence(row)
        needs = bool(_g(row, "needsReview", "needs_review", default=conf < 0.80 or not number or not title))
        out.append(
            {
                "rowId": rid,
                "sheetNumber": number,
                "sheetTitle": title,
                "revisionLabel": rev,
                "confidence": conf,
                "needsReview": needs,
            }
        )
    return out


def _confidence(row: dict[str, Any]) -> float:
    raw = _g(row, "confidence", default=0.0)
    try:
        val = float(raw)
    except (TypeError, ValueError):
        val = 0.0
    return max(0.0, min(1.0, val))


def _int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
