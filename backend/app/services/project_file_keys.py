"""B2/NAS object names for project files.

New uploads use a human-readable key under the category prefix:

    {project_number}/{kind}/{optional-set}/{filename}

Older rows used ``{uuid}.pdf`` or ``{uuid}_{filename}``. Serving must try both.
Listing must never probe storage — that HEADs B2 once per sheet.
"""
from __future__ import annotations

import re
import uuid
from pathlib import Path

from sqlalchemy import select
from werkzeug.utils import secure_filename

from ..extensions import db
from ..models import Project

_SLUG_BAD = re.compile(r'[<>:"/\\|?*]+')
_SLUG_SPACE = re.compile(r"[\s,]+")


def slug_part(raw: str, fallback: str) -> str:
    s = _SLUG_BAD.sub("-", (raw or "").strip())
    s = _SLUG_SPACE.sub("-", s)
    s = re.sub(r"-{2,}", "-", s).strip("-")
    return (s[:80] or fallback)


def safe_filename(raw: str, *, default: str = "file.bin") -> str:
    name = Path(raw or "").name.strip() or default
    name = _SLUG_BAD.sub("-", name)
    return name[:200] or default


def project_label(project_id: uuid.UUID | None) -> str:
    if project_id is None:
        return "unassigned"
    fallback = slug_part("", str(project_id))
    try:
        from flask import has_app_context

        if not has_app_context():
            return fallback
        number = db.session.scalar(select(Project.number).where(Project.id == project_id))
    except Exception:
        return fallback
    label = (number or "").strip()
    return slug_part(label, str(project_id))


def _unique(names: list[str]) -> list[str]:
    out: list[str] = []
    for name in names:
        n = (name or "").strip()
        if n and n not in out:
            out.append(n)
    return out


def drawing_storage_relpath(d, *, label: str | None = None) -> str:
    fname = safe_filename(getattr(d, "original_filename", None) or "", default=f"{d.id}.pdf")
    if not fname.lower().endswith(".pdf"):
        fname += ".pdf"
    proj = label or project_label(getattr(d, "project_id", None))
    disc = slug_part(getattr(d, "discipline", None) or "", "Drawings")
    dset = slug_part(getattr(d, "drawing_set", None) or "", "Set")
    return f"{proj}/{disc}/{dset}/{fname}"


def drawing_object_candidates(d) -> list[str]:
    tags = d.tags if isinstance(getattr(d, "tags", None), dict) else {}
    return _unique(
        [
            str(tags.get("storage_object") or ""),
            drawing_storage_relpath(d),
            f"{d.id}.pdf",
            str(d.id),
        ]
    )


def preferred_drawing_object_name(d) -> str:
    """First candidate without probing disk or B2."""
    names = drawing_object_candidates(d)
    return names[0] if names else f"{d.id}.pdf"


def document_storage_relpath(doc, *, label: str | None = None) -> str:
    kind = slug_part(getattr(doc, "document_type", None) or "other", "other")
    raw = getattr(doc, "original_filename", None) or getattr(doc, "title", None) or f"{doc.id}"
    fname = safe_filename(raw, default=f"{doc.id}")
    proj = label or project_label(getattr(doc, "project_id", None))
    return f"{proj}/{kind}/{fname}"


def document_object_candidates(doc) -> list[str]:
    tags = doc.tags if isinstance(getattr(doc, "tags", None), dict) else {}
    stored = str(tags.get("storage_object") or "")
    raw = getattr(doc, "original_filename", None) or getattr(doc, "title", None) or "upload"
    ascii_name = secure_filename(Path(str(raw)).name) or "upload"
    return _unique(
        [
            stored,
            document_storage_relpath(doc),
            f"{doc.id}_{ascii_name}"[:200],
            f"{doc.id}.pdf",
            str(doc.id),
        ]
    )


def preferred_document_object_name(doc) -> str:
    names = document_object_candidates(doc)
    return names[0] if names else str(doc.id)


def spec_storage_relpath(row, *, original_filename: str | None = None, label: str | None = None) -> str:
    proj = label or project_label(getattr(row, "project_id", None))
    code = slug_part(getattr(row, "code", None) or "", "spec")
    raw = original_filename or f"{code}.pdf"
    fname = safe_filename(raw, default=f"{row.id}.pdf")
    if not fname.lower().endswith(".pdf"):
        fname += ".pdf"
    return f"{proj}/specifications/{code}_{fname}"


def spec_object_candidates(row) -> list[str]:
    return _unique(
        [
            spec_storage_relpath(row),
            f"{row.id}.pdf",
            str(row.id),
        ]
    )
