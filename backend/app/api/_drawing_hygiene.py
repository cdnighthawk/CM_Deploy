"""CPU-first drawing hygiene: label check, then sheet type. AI only later for exceptions."""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from ..extensions import db
from ..models import Drawing, Estimate
from . import _bid_locations as bid_locations
from ._rfi_service import ApiError

LABEL_OK = "ok"
LABEL_NEEDS_AI = "needs_ai"
LABEL_UNKNOWN = "unknown"

SHEET_FUNCTIONS = (
    "floor_plan",
    "rcp",
    "roof_plan",
    "site_plan",
    "exterior_elevation",
    "interior_elevation",
    "section",
    "detail",
    "finish_schedule",
    "door_schedule",
    "hardware_schedule",
    "cover_index",
    "demo_plan",
    "unknown",
)

# Letter + optional separator + digits, optional decimal/suffix. A-100, A2.01, I-201, ID-101.
_SHEET_NUM_RE = re.compile(
    r"^[A-Z]{1,3}[-\s.]?\d{1,4}(?:[.-]\d{1,2})?[A-Z]?$",
    re.IGNORECASE,
)
_PAGE_RE = re.compile(r"^(page|sheet|pg|p)\s*\d+", re.IGNORECASE)
_IMG_RE = re.compile(r"^(img|image|dsc|scan)[_-]?\d+", re.IGNORECASE)
_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)
_FROM_FILENAME_RE = re.compile(
    r"\b([A-Z]{1,3}[-\s.]?\d{1,4}(?:[.-]\d{1,2})?[A-Z]?)\b",
    re.IGNORECASE,
)

_TYPE_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("rcp", ("reflected ceiling", " rcp ", "rcp-", "rcp_")),
    ("roof_plan", ("roof plan", "roofing plan")),
    ("site_plan", ("site plan", "civil site")),
    ("demo_plan", ("demolition", " demo plan", "demo plan")),
    ("interior_elevation", ("interior elevation", "int. elevation", "int elevation")),
    ("exterior_elevation", ("exterior elevation", "building elevation")),
    ("finish_schedule", ("finish schedule", "room finish", "finish legend")),
    ("door_schedule", ("door schedule",)),
    ("hardware_schedule", ("hardware schedule", "hardware set")),
    ("cover_index", ("title sheet", "cover sheet", "drawing index", "sheet index", "g-000", "g000")),
    ("section", ("building section", "wall section", " sections ", " section ")),
    ("detail", (" typical detail", " details ", " detail ")),
    ("floor_plan", ("floor plan", "level plan", "first floor", "second floor", "third floor", "enlarged plan")),
    ("exterior_elevation", ("elevation",)),
)

_ELEVATION_INTERIOR_HINTS = ("interior", "int.", "corridor", "toilet", "restroom", "lobby")


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


def _norm(raw: str | None) -> str:
    return " ".join(str(raw or "").strip().lower().split())


def extract_sheet_number_from_filename(filename: str | None) -> str | None:
    name = str(filename or "").rsplit(".", 1)[0]
    name = name.replace("_", " ").replace("—", " ")
    hits = _FROM_FILENAME_RE.findall(name)
    if not hits:
        return None
    return str(hits[0]).upper().replace(" ", "")


def classify_label(sheet_number: str | None, filename: str | None = None) -> dict[str, Any]:
    raw = (sheet_number or "").strip()
    from_file = extract_sheet_number_from_filename(filename)
    if raw and _SHEET_NUM_RE.match(raw) and not _PAGE_RE.match(raw):
        conflict = bool(from_file) and _digits(raw) != _digits(from_file)
        if conflict:
            return {
                "label_status": LABEL_NEEDS_AI,
                "label_reason": "filename sheet number disagrees with stored drawing #",
                "filename_guess": from_file,
            }
        return {"label_status": LABEL_OK, "label_reason": "matches drawing-number pattern", "filename_guess": from_file}
    if raw and (_PAGE_RE.match(raw) or _IMG_RE.match(raw) or _UUID_RE.match(raw)):
        return {
            "label_status": LABEL_NEEDS_AI,
            "label_reason": "stored drawing # looks like a page, image, or id — not A-100 style",
            "filename_guess": from_file,
        }
    if from_file and _SHEET_NUM_RE.match(from_file):
        return {
            "label_status": LABEL_NEEDS_AI,
            "label_reason": "stored drawing # is missing or nonstandard; filename looks like a sheet id",
            "filename_guess": from_file,
        }
    if not raw:
        return {"label_status": LABEL_UNKNOWN, "label_reason": "no drawing # and no filename pattern", "filename_guess": None}
    return {
        "label_status": LABEL_NEEDS_AI,
        "label_reason": "drawing # does not match A-100 / A2.01 style",
        "filename_guess": from_file,
    }


def _digits(raw: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(raw or "").upper())


def classify_sheet_function(sheet_title: str | None, sheet_number: str | None = None) -> dict[str, Any]:
    blob = " " + _norm(sheet_title) + " " + _norm(sheet_number) + " "
    if not blob.strip():
        return {
            "sheet_function": "unknown",
            "function_status": LABEL_UNKNOWN,
            "function_reason": "no title to classify",
        }
    if "elevation" in blob and any(h in blob for h in _ELEVATION_INTERIOR_HINTS):
        return {
            "sheet_function": "interior_elevation",
            "function_status": LABEL_OK,
            "function_reason": "title looks like an interior elevation",
        }
    for fn, needles in _TYPE_RULES:
        for n in needles:
            if n in blob:
                return {
                    "sheet_function": fn,
                    "function_status": LABEL_OK,
                    "function_reason": f"title matched {n.strip()}",
                }
    vague = _norm(sheet_title) in ("plan", "architectural", "drawing", "sheet")
    if vague or not _norm(sheet_title):
        return {
            "sheet_function": "unknown",
            "function_status": LABEL_NEEDS_AI,
            "function_reason": "title is missing or too vague for CPU",
        }
    return {
        "sheet_function": "unknown",
        "function_status": LABEL_NEEDS_AI,
        "function_reason": "title did not match a known sheet type",
    }


def classify_drawing_fields(
    *,
    sheet_number: str | None,
    sheet_title: str | None,
    filename: str | None = None,
) -> dict[str, Any]:
    label = classify_label(sheet_number, filename)
    func = classify_sheet_function(sheet_title, sheet_number)
    needs_ai = label["label_status"] == LABEL_NEEDS_AI or func["function_status"] == LABEL_NEEDS_AI
    return {
        **label,
        **func,
        "needs_ai": needs_ai,
        "classified_by": "cpu",
    }


def apply_hygiene(drawing: Drawing) -> dict[str, Any]:
    result = classify_drawing_fields(
        sheet_number=drawing.sheet_number,
        sheet_title=drawing.sheet_title or drawing.title,
        filename=drawing.original_filename,
    )
    drawing.label_status = result["label_status"]
    drawing.sheet_function = result["sheet_function"]
    drawing.hygiene = {
        **result,
        "classified_at": _utcnow().isoformat(),
    }
    return result


def hygiene_public(drawing: Drawing) -> dict[str, Any]:
    h = drawing.hygiene if isinstance(drawing.hygiene, dict) else {}
    return {
        "labelStatus": drawing.label_status or h.get("label_status"),
        "sheetFunction": drawing.sheet_function or h.get("sheet_function"),
        "functionStatus": h.get("function_status"),
        "labelReason": h.get("label_reason"),
        "functionReason": h.get("function_reason"),
        "filenameGuess": h.get("filename_guess"),
        "needsAi": bool(h.get("needs_ai")),
        "classifiedBy": h.get("classified_by") or "cpu",
    }


def run_project_hygiene(project_id: uuid.UUID) -> dict[str, Any]:
    rows = list(
        db.session.scalars(select(Drawing).where(Drawing.project_id == project_id)).all()
    )
    items = []
    counts = {"ok": 0, "needs_ai": 0, "unknown": 0, "typed": 0, "type_needs_ai": 0}
    for d in rows:
        result = apply_hygiene(d)
        if result["label_status"] == LABEL_OK:
            counts["ok"] += 1
        elif result["label_status"] == LABEL_NEEDS_AI:
            counts["needs_ai"] += 1
        else:
            counts["unknown"] += 1
        if result["sheet_function"] != "unknown":
            counts["typed"] += 1
        if result["function_status"] == LABEL_NEEDS_AI:
            counts["type_needs_ai"] += 1
        items.append(
            {
                "id": str(d.id),
                "seriesId": str(d.drawing_series_id),
                "sheetNumber": d.sheet_number,
                "sheetTitle": d.sheet_title or d.title,
                **hygiene_public(d),
            }
        )
    db.session.flush()
    return {
        "entity": "drawing_hygiene",
        "projectId": str(project_id),
        "total": len(rows),
        "counts": counts,
        "items": items,
    }


def run_estimate_hygiene(estimate_id: uuid.UUID) -> dict[str, Any]:
    est = db.session.get(Estimate, estimate_id)
    if est is None:
        raise ApiError("estimate not found", 404)
    if est.project_id is None:
        raise ApiError("estimate has no project — attach a project before drawing hygiene", 409)
    payload = run_project_hygiene(est.project_id)
    payload["bidLocation"] = bid_locations.apply_estimate_bid_locations(est)
    return payload
