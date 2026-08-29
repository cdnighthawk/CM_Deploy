"""Split multi-page drawing PDFs into one stored sheet per page."""
from __future__ import annotations

import io
import re
import uuid
from pathlib import Path
from typing import Any

from pypdf import PdfReader, PdfWriter
from sqlalchemy import select
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from ..extensions import db
from ..models import Drawing, Project
from ..services.object_storage import UploadCategory, delete_stored, save_upload, stored_exists

_SLUG_BAD = re.compile(r'[<>:"/\\|?*]+')
_SLUG_SPACE = re.compile(r"[\s,]+")


def _slug_part(raw: str, fallback: str) -> str:
    s = _SLUG_BAD.sub("-", (raw or "").strip())
    s = _SLUG_SPACE.sub("-", s)
    s = re.sub(r"-{2,}", "-", s).strip("-")
    return (s[:80] or fallback)


def _safe_filename(raw: str) -> str:
    name = Path(raw or "").name.strip() or "drawing.pdf"
    name = _SLUG_BAD.sub("-", name)
    if not name.lower().endswith(".pdf"):
        name += ".pdf"
    return name[:200]


def _project_label(project_id: uuid.UUID | None) -> str:
    if project_id is None:
        return "unassigned"
    number = db.session.scalar(select(Project.number).where(Project.id == project_id))
    label = (number or "").strip()
    return _slug_part(label, str(project_id))


def drawing_storage_relpath(d: Drawing, *, project_label: str | None = None) -> str:
    """Human-readable B2/NAS key under the drawings/ prefix."""
    fname = _safe_filename(d.original_filename or "") or f"{d.id}.pdf"
    proj = project_label or _project_label(d.project_id)
    disc = _slug_part(d.discipline or "", "Drawings")
    dset = _slug_part(d.drawing_set or "", "Set")
    return f"{proj}/{disc}/{dset}/{fname}"


def drawing_object_candidates(d: Drawing) -> list[str]:
    names: list[str] = []
    tags = d.tags if isinstance(d.tags, dict) else {}
    stored = str(tags.get("storage_object") or "").strip()
    if stored:
        names.append(stored)
    human = drawing_storage_relpath(d)
    if human not in names:
        names.append(human)
    legacy = f"{d.id}.pdf"
    if legacy not in names:
        names.append(legacy)
    return names


def resolve_drawing_object_name(d: Drawing) -> str | None:
    for name in drawing_object_candidates(d):
        if stored_exists(UploadCategory.DRAWINGS, name):
            return name
    return None


def delete_drawing_objects(d: Drawing) -> None:
    for name in drawing_object_candidates(d):
        delete_stored(UploadCategory.DRAWINGS, name)


class DrawingUploadError(Exception):
    def __init__(self, message: str, status: int = 400):
        self.message = message
        self.status = status


def _page_pdf_bytes(reader: PdfReader, page_index: int) -> bytes:
    writer = PdfWriter()
    writer.add_page(reader.pages[page_index])
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def _base_name(raw_filename: str) -> str:
    name = secure_filename(raw_filename) or "upload.pdf"
    if name.lower().endswith(".pdf"):
        name = name[:-4]
    return name[:200] or "drawing"


def _existing_series_id(project_id: uuid.UUID | None, sheet_number: str | None) -> uuid.UUID | None:
    """Reuse the series for later revisions of the same sheet on a project."""
    sn = (sheet_number or "").strip()
    if project_id is None or not sn:
        return None
    row = db.session.scalar(
        select(Drawing)
        .where(Drawing.project_id == project_id, Drawing.sheet_number == sn)
        .order_by(Drawing.created_at.asc(), Drawing.id.asc())
    )
    return row.drawing_series_id if row is not None else None


def _create_drawing_row(
    *,
    project_id: uuid.UUID | None,
    pdf_bytes: bytes,
    raw_name: str,
    page_index: int | None,
    page_count: int,
    sheet_number: str | None,
    sheet_title: str | None,
    discipline: str | None,
    drawing_set: str | None,
    revision: str,
) -> Drawing:
    base = _base_name(raw_name)
    if page_count > 1 and page_index is not None:
        title = sheet_title or f"{base} — page {page_index + 1}"
        sn = sheet_number or f"Page {page_index + 1}"
        orig = f"{base}_p{page_index + 1}.pdf"
    else:
        title = sheet_title or base
        sn = sheet_number
        orig = _safe_filename(raw_name)

    series_id = _existing_series_id(project_id, sn)
    d = Drawing(
        project_id=project_id,
        title=title[:500],
        sheet_number=(sn[:50] if sn else None),
        sheet_title=title[:500],
        discipline=(discipline[:50] if discipline else None),
        drawing_set=(drawing_set[:120] if drawing_set else None),
        revision=revision[:50],
        mime_type="application/pdf",
        original_filename=orig[:500],
        drawing_series_id=series_id,
    )
    db.session.add(d)
    db.session.flush()

    obj_name = drawing_storage_relpath(d)
    try:
        sz = save_upload(UploadCategory.DRAWINGS, obj_name, io.BytesIO(pdf_bytes))
    except OSError as exc:
        raise DrawingUploadError(f"could not save file: {exc}", 500) from exc

    if sz == 0:
        delete_stored(UploadCategory.DRAWINGS, obj_name)
        raise DrawingUploadError("empty upload", 400)

    tags = dict(d.tags) if isinstance(d.tags, dict) else {}
    tags["storage_object"] = obj_name
    d.tags = tags
    d.file_url = f"/api/v1/drawings/{d.id}/file"
    d.file_size_bytes = int(sz)
    return d


def upload_project_drawing_pdf(
    *,
    project_id: uuid.UUID,
    file_storage: FileStorage,
    sheet_number: str | None,
    sheet_title: str | None,
    discipline: str | None,
    drawing_set: str | None,
    revision: str,
    split_pages: bool,
    max_bytes: int,
    drawing_public_fn,
) -> dict[str, Any]:
    """Persist one or more single-page drawing PDFs from an upload."""
    raw_name = secure_filename(file_storage.filename) or "upload.pdf"
    if not raw_name.lower().endswith(".pdf"):
        raise DrawingUploadError("only PDF uploads are supported", 400)

    payload = file_storage.read()
    if not payload:
        raise DrawingUploadError("empty upload", 400)
    if len(payload) > max_bytes:
        raise DrawingUploadError("file too large (max 50MB)", 400)

    page_count = 1
    reader = None
    if split_pages:
        try:
            reader = PdfReader(io.BytesIO(payload))
            page_count = len(reader.pages)
        except Exception as exc:
            raise DrawingUploadError(f"invalid or unreadable PDF: {exc}", 400) from exc
        if page_count < 1:
            raise DrawingUploadError("PDF has no pages", 400)

    do_split = bool(split_pages and reader is not None and page_count > 1)
    created: list[Drawing] = []

    if do_split:
        for i in range(page_count):
            page_bytes = _page_pdf_bytes(reader, i)
            if len(page_bytes) > max_bytes:
                raise DrawingUploadError("a split page exceeds max file size (max 50MB)", 400)
            created.append(
                _create_drawing_row(
                    project_id=project_id,
                    pdf_bytes=page_bytes,
                    raw_name=raw_name,
                    page_index=i,
                    page_count=page_count,
                    sheet_number=sheet_number,
                    sheet_title=sheet_title,
                    discipline=discipline,
                    drawing_set=drawing_set,
                    revision=revision,
                )
            )
        return {
            "entity": "drawing_upload",
            "split": True,
            "count": len(created),
            "items": [drawing_public_fn(d) for d in created],
        }

    created.append(
        _create_drawing_row(
            project_id=project_id,
            pdf_bytes=payload,
            raw_name=raw_name,
            page_index=None,
            page_count=1,
            sheet_number=sheet_number,
            sheet_title=sheet_title,
            discipline=discipline,
            drawing_set=drawing_set,
            revision=revision,
        )
    )
    d = created[0]
    return {"entity": "drawing", "item": drawing_public_fn(d), "split": False, "count": 1}
