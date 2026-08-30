"""Parse drawing filenames and folder paths into sheet labels.

Expected one-PDF-per-sheet name:

    {SheetToken}_{Title}_{optional Rev/Set}.pdf

    A1-001_BCK-1.pdf
    G0.1.01_SHEET-INDEX-VOLUME-1.pdf
    A10.02.1_FINISH-PLAN-L2_Rev-04_Bulletin-15.pdf

Folder ingest (authoritative for discipline / set):

    {job}/{Discipline}/{Set}/{filename}.pdf
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

# A-100, A2.01, A1-001, G0.1.01, G0.1.03-A, A10.02.1, P3-G0.1.01
_SHEET_NUM_RE = re.compile(
    r"^(?:[A-Z]{1,3}\d{0,2}-)?[A-Z]{1,3}[-\s.]?\d{1,4}(?:[.\-]\d{1,4}){0,3}(?:-[A-Z0-9]{1,3})?[A-Z]?$",
    re.IGNORECASE,
)
_LEADING_SHEET = re.compile(r"^[A-Z]{1,3}[-\s.]?\d", re.IGNORECASE)
_REV = re.compile(r"(?:^|[_-])rev(?:ision)?[-_]?([A-Z0-9.]+)", re.IGNORECASE)
_PAGE_RE = re.compile(r"^(?:page|sheet|pg)[\s._-]*\d+$", re.IGNORECASE)

_DISC_FROM_PREFIX: tuple[tuple[tuple[str, ...], str], ...] = (
    (("ID", "AD", "I", "A"), "Architectural"),
    (("S",), "Structural"),
    (("MP", "MD", "M"), "Mechanical"),
    (("EL", "EP", "E"), "Electrical"),
    (("PL", "P"), "Plumbing"),
    (("CG", "CS", "C"), "Civil"),
    (("LA", "LS", "L"), "Landscape"),
    (("FA", "FP", "F"), "Fire Protection"),
    (("G",), "General"),
    (("T",), "Telecom"),
)

_FOLDER_DISC_ALIASES = {
    "arch": "Architectural",
    "architectural": "Architectural",
    "architecture": "Architectural",
    "05-architectural": "Architectural",
    "struct": "Structural",
    "structural": "Structural",
    "mech": "Mechanical",
    "mechanical": "Mechanical",
    "elec": "Electrical",
    "electrical": "Electrical",
    "plumb": "Plumbing",
    "plumbing": "Plumbing",
    "civil": "Civil",
    "landscape": "Landscape",
    "fire": "Fire Protection",
    "fire-protection": "Fire Protection",
    "general": "General",
    "01-general": "General",
    "telecom": "Telecom",
    "interiors": "Interiors",
}


def is_sheet_number(raw: str | None) -> bool:
    token = (raw or "").strip()
    if not token or _PAGE_RE.match(token):
        return False
    return bool(_SHEET_NUM_RE.match(token))


def normalize_sheet_number(raw: str | None) -> str | None:
    token = (raw or "").strip()
    if not token:
        return None
    return token.upper().replace(" ", "")[:50]


def _title_from_rest(rest: str) -> str | None:
    parts = [p for p in re.split(r"[_]+", rest) if p]
    keep: list[str] = []
    for part in parts:
        if _REV.match(part) or re.match(r"^rev[-_]?", part, re.I):
            continue
        keep.append(part.replace("-", " ").strip())
    title = " ".join(keep).strip()
    return title[:500] or None


def parse_filename(filename: str | None) -> dict[str, str | None]:
    """Read sheet #, title, and revision from a drawing filename."""
    name = Path(filename or "").name
    stem = name.rsplit(".", 1)[0] if name else ""
    if not stem:
        return {"sheet_number": None, "sheet_title": None, "revision": None}

    token, sep, rest = stem.partition("_")
    if not sep:
        bits = stem.split(None, 1)
        token = bits[0] if bits else ""
        rest = bits[1] if len(bits) > 1 else ""
    token = token.strip()
    sheet = None
    title = None
    if token and _LEADING_SHEET.match(token):
        sheet = normalize_sheet_number(token)
        if rest:
            title = _title_from_rest(rest)
    if sheet is None:
        compact = stem.replace("_", " ").replace("—", " ")
        hit = re.search(
            r"\b((?:[A-Z]{1,3}\d{0,2}-)?[A-Z]{1,3}[-\s.]?\d{1,4}(?:[.\-]\d{1,4}){0,3}(?:-[A-Z0-9]{1,3})?[A-Z]?)\b",
            compact,
            re.I,
        )
        if hit:
            sheet = normalize_sheet_number(hit.group(1))
            leftover = compact.replace(hit.group(1), " ", 1).strip(" -_")
            title = leftover[:500] or None

    rev = None
    m = _REV.search(stem)
    if m:
        rev = m.group(1)[:50]
    return {"sheet_number": sheet, "sheet_title": title, "revision": rev}


def discipline_from_sheet_number(sheet_number: str | None) -> str | None:
    raw = (sheet_number or "").strip().upper()
    if not raw:
        return None
    if raw.startswith("P") and "-" in raw:
        raw = raw.split("-", 1)[1]
    letters = re.match(r"^([A-Z]{1,3})", raw)
    if not letters:
        return None
    prefix = letters.group(1)
    for keys, name in _DISC_FROM_PREFIX:
        if prefix in keys:
            return name
    return None


def normalize_discipline(raw: str | None) -> str | None:
    s = (raw or "").strip()
    if not s:
        return None
    alias = _FOLDER_DISC_ALIASES.get(s.lower())
    if alias:
        return alias
    return s[:50]


def parse_folder_path(path: str | None) -> dict[str, str | None]:
    """Parse ``{job}/{discipline}/{set}/{file}`` or ``{discipline}/{set}/{file}``."""
    parts = [p for p in str(path or "").replace("\\", "/").split("/") if p and p not in (".", "..")]
    if parts and parts[0].lower() == "drawings":
        parts = parts[1:]
    if len(parts) < 1:
        return {"job": None, "discipline": None, "drawing_set": None, "filename": None}
    filename = parts[-1] if "." in parts[-1] else None
    segs = parts[:-1] if filename else parts
    job = None
    discipline = None
    drawing_set = None
    if segs and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,31}", segs[0] or ""):
        if re.fullmatch(r"\d{4,8}", segs[0]) or re.fullmatch(r"[A-Z]{0,3}\d{4,8}", segs[0], re.I):
            job = segs[0]
            segs = segs[1:]
    if segs:
        discipline = normalize_discipline(segs[0])
    if len(segs) >= 2:
        drawing_set = segs[1][:120]
    return {
        "job": job,
        "discipline": discipline,
        "drawing_set": drawing_set,
        "filename": filename,
    }


def label_drawing(
    *,
    filename: str | None,
    folder_path: str | None = None,
    sheet_number: str | None = None,
    sheet_title: str | None = None,
    discipline: str | None = None,
    drawing_set: str | None = None,
    revision: str | None = None,
    allow_filename_sheet: bool = True,
) -> dict[str, str | None]:
    """Fill missing labels from filename and optional folder path. Explicit values win."""
    parsed = parse_filename(filename)
    folder = parse_folder_path(folder_path) if folder_path else {
        "job": None,
        "discipline": None,
        "drawing_set": None,
        "filename": None,
    }
    sn = (sheet_number or "").strip() or None
    if allow_filename_sheet and not sn:
        sn = parsed["sheet_number"]
    title = (sheet_title or "").strip() or None
    if not title:
        title = parsed["sheet_title"]
    disc = normalize_discipline(discipline) or folder["discipline"]
    if not disc and sn:
        disc = discipline_from_sheet_number(sn)
    dset = (drawing_set or "").strip() or None
    if not dset:
        dset = folder["drawing_set"]
    rev = (revision or "").strip() or None
    if (not rev or rev == "0") and parsed["revision"]:
        rev = parsed["revision"]
    if not rev:
        rev = "0"
    return {
        "sheet_number": normalize_sheet_number(sn) if sn and not _PAGE_RE.match(sn) else sn,
        "sheet_title": (title[:500] if title else None),
        "discipline": (disc[:50] if disc else None),
        "drawing_set": (dset[:120] if dset else None),
        "revision": (rev[:50] if rev else "0"),
    }


def label_public(fields: dict[str, Any]) -> dict[str, Any]:
    return {
        "sheet_number": fields.get("sheet_number"),
        "sheet_title": fields.get("sheet_title"),
        "discipline": fields.get("discipline"),
        "drawing_set": fields.get("drawing_set"),
        "revision": fields.get("revision"),
    }
