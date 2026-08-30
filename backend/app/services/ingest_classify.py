"""Guess drawing vs document (and document type) from a relative path."""
from __future__ import annotations

import re
from pathlib import Path

from .drawing_label import _FOLDER_DISC_ALIASES, parse_filename
from .ingest import _DOCUMENT_TYPES

_SKIP_NAMES = frozenset(
    {
        ".ds_store",
        "thumbs.db",
        "desktop.ini",
        ".gitkeep",
        ".gitignore",
    }
)
_SKIP_DIR_NAMES = frozenset({".git", "__pycache__", "__macosx", ".svn", "node_modules"})
_PHOTO_EXT = frozenset({".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic", ".tif", ".tiff", ".bmp"})
_DRAWING_FOLDER_TOKENS = frozenset(
    {
        "drawings",
        "drawing",
        "sheets",
        "sheet",
        "plans",
        "plan",
        *{k.lower() for k in _FOLDER_DISC_ALIASES},
        *{v.lower() for v in _FOLDER_DISC_ALIASES.values()},
    }
)
_DOC_TYPE_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\brfi\b", re.I), "rfi"),
    (re.compile(r"submittal", re.I), "submittal"),
    (re.compile(r"\bspec(?:ification)?s?\b", re.I), "specification"),
    (re.compile(r"addend", re.I), "specification"),
    (re.compile(r"contract", re.I), "contract"),
    (re.compile(r"change[_\s-]?order|\bco[-_\s]", re.I), "change_order"),
    (re.compile(r"invoice", re.I), "invoice"),
    (re.compile(r"\bpermit", re.I), "permit"),
    (re.compile(r"safety|iipp|js[ah]|toolbox", re.I), "safety_doc"),
    (re.compile(r"\breport\b", re.I), "report"),
    (re.compile(r"ai[_\s-]?review", re.I), "ai_review_export"),
)


def normalize_rel(path: str | None) -> str:
    return str(path or "").replace("\\", "/").strip("/")


def should_skip_path(relative_path: str | None) -> bool:
    rel = normalize_rel(relative_path)
    if not rel:
        return True
    parts = [p for p in rel.split("/") if p]
    if not parts:
        return True
    if any(p.lower() in _SKIP_DIR_NAMES or p.startswith(".") for p in parts[:-1]):
        return True
    name = parts[-1]
    if name.startswith(".") or name.lower() in _SKIP_NAMES:
        return True
    return False


def guess_document_type(relative_path: str | None) -> str:
    rel = normalize_rel(relative_path)
    name = Path(rel).name
    ext = Path(name).suffix.lower()
    if ext in _PHOTO_EXT:
        return "photo"
    hay = rel.replace("/", " ")
    for pattern, dtype in _DOC_TYPE_PATTERNS:
        if pattern.search(hay):
            return dtype if dtype in _DOCUMENT_TYPES else "other"
    return "other"


def folder_looks_like_drawings(relative_path: str | None) -> bool:
    rel = normalize_rel(relative_path)
    parts = [p for p in rel.split("/") if p]
    folders = parts[:-1] if parts and "." in parts[-1] else parts
    for seg in folders:
        token = seg.lower().strip()
        if token in _DRAWING_FOLDER_TOKENS:
            return True
        if token.split("-", 1)[-1] in _DRAWING_FOLDER_TOKENS:
            return True
    return False


def classify_ingest_file(relative_path: str | None, *, kind: str = "auto") -> dict[str, str]:
    """Return ``{"kind": "drawing"|"document", "document_type": ...}``."""
    rel = normalize_rel(relative_path)
    name = Path(rel).name
    ext = Path(name).suffix.lower()
    override = (kind or "auto").strip().lower()
    if override == "drawing":
        return {"kind": "drawing", "document_type": "drawing"}
    if override == "document":
        return {"kind": "document", "document_type": guess_document_type(rel)}

    if ext == ".pdf":
        parsed = parse_filename(name)
        if parsed.get("sheet_number") or folder_looks_like_drawings(rel):
            return {"kind": "drawing", "document_type": "drawing"}
    return {"kind": "document", "document_type": guess_document_type(rel)}
