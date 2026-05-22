"""Shared hire-wizard document upload helpers (I-9, W-4, union)."""

from __future__ import annotations

from pathlib import Path

from werkzeug.utils import secure_filename

HR_HIRE_DOC_EXT = frozenset({".jpg", ".jpeg", ".png", ".webp", ".gif", ".heic", ".heif", ".pdf"})

_MIME_TO_EXT: dict[str, str] = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
    "image/heic": ".heic",
    "image/heif": ".heif",
    "application/pdf": ".pdf",
}


def resolve_hire_doc_upload(filename: str | None, mimetype: str | None) -> tuple[str, str] | None:
    """Return ``(safe_filename, extension)`` or ``None`` if the file type is not allowed."""
    raw_name = secure_filename(filename or "") or "upload"
    ext = Path(raw_name).suffix.lower()
    if ext in HR_HIRE_DOC_EXT:
        return raw_name, ext

    mt = (mimetype or "").split(";")[0].strip().lower()
    inferred = _MIME_TO_EXT.get(mt)
    if inferred and inferred in HR_HIRE_DOC_EXT:
        stem = Path(raw_name).stem or "upload"
        return f"{stem}{inferred}", inferred

    if not ext and mt.startswith("image/"):
        stem = Path(raw_name).stem or "upload"
        return f"{stem}.jpg", ".jpg"

    return None
