"""Split multi-page drawing PDFs into one stored sheet per page."""
from __future__ import annotations

import io
import uuid
from typing import Any

from pypdf import PdfReader, PdfWriter
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from ..extensions import db
from ..models import Drawing
from ..services.object_storage import UploadCategory, delete_stored, save_upload


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


def _create_drawing_row(
    *,
    project_id: uuid.UUID,
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
        orig = secure_filename(raw_name) or "upload.pdf"

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
    )
    db.session.add(d)
    db.session.flush()

    obj_name = f"{d.id}.pdf"
    try:
        sz = save_upload(UploadCategory.DRAWINGS, obj_name, io.BytesIO(pdf_bytes))
    except OSError as exc:
        raise DrawingUploadError(f"could not save file: {exc}", 500) from exc

    if sz == 0:
        delete_stored(UploadCategory.DRAWINGS, obj_name)
        raise DrawingUploadError("empty upload", 400)

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

    try:
        reader = PdfReader(io.BytesIO(payload))
        page_count = len(reader.pages)
    except Exception as exc:
        raise DrawingUploadError(f"invalid or unreadable PDF: {exc}", 400) from exc

    if page_count < 1:
        raise DrawingUploadError("PDF has no pages", 400)

    do_split = split_pages and page_count > 1
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
