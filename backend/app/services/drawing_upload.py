"""Split multi-page drawing PDFs into one stored sheet per page."""
from __future__ import annotations

import hashlib
import io
import uuid
from typing import Any

from pypdf import PdfReader, PdfWriter
from sqlalchemy import select
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from ..extensions import db
from ..models import Drawing
from ..services.object_storage import (
    StorageError,
    UploadCategory,
    delete_stored,
    save_upload,
    stored_exists,
    stored_size,
)
from ..services.drawing_label import label_drawing
from ..services.project_file_keys import (
    drawing_object_candidates,
    drawing_storage_relpath,
    preferred_drawing_object_name,
    safe_filename,
)


def resolve_drawing_object_name(d: Drawing) -> str | None:
    """Probe storage for an old UUID key or a new human-readable key.

    Use only when serving a file. Do not call this while listing drawings —
    each probe can HEAD B2.
    """
    for name in drawing_object_candidates(d):
        if stored_exists(UploadCategory.DRAWINGS, name):
            return name
    return None


def delete_drawing_objects(d: Drawing) -> None:
    for name in drawing_object_candidates(d):
        delete_stored(UploadCategory.DRAWINGS, name)


def native_upload_hint_for_drawing(d: Drawing) -> dict | None:
    """Mint a client-side B2 write URL for this drawing, or None.

    Prefer a native ``b2_get_upload_url`` session. If Render cannot reach that
    API, sign an S3 PUT so the office PC still writes the bytes (Render does
    not proxy the PDF).
    """
    from .object_storage import native_upload_session, presigned_put_url

    name = preferred_drawing_object_name(d)
    native = native_upload_session(UploadCategory.DRAWINGS, name)
    if native:
        return native
    url = presigned_put_url(
        UploadCategory.DRAWINGS,
        name,
        content_type="application/pdf",
    )
    if not url:
        return None
    return {
        "mode": "s3_presigned_put",
        "url": url,
        "file_name": name,
    }


def ack_drawing_file(
    d: Drawing,
    *,
    byte_size: int | None = None,
    content_hash: str | None = None,
) -> int:
    """Mark a drawing as stored after the client wrote the object (native B2).

    Prefer HEAD of B2 when that works. If the S3 gateway is still dropping,
    trust the client's byte size so ingest can clear ``file_pending``.
    """
    obj_name = preferred_drawing_object_name(d)
    sz = stored_size(UploadCategory.DRAWINGS, obj_name)
    if not sz:
        if byte_size and int(byte_size) > 0:
            sz = int(byte_size)
        else:
            raise DrawingUploadError("file not found in storage", 404)
    tags = dict(d.tags) if isinstance(d.tags, dict) else {}
    tags["storage_object"] = obj_name
    tags.pop("file_pending", None)
    tags.pop("storage_error", None)
    digest = (content_hash or "").strip().lower()
    if digest:
        tags["content_hash"] = digest
    d.tags = tags
    d.file_url = f"/api/v1/drawings/{d.id}/file"
    d.file_size_bytes = int(sz)
    d.mime_type = "application/pdf"
    return int(sz)


def replace_drawing_file(d: Drawing, pdf_bytes: bytes) -> int:
    """Overwrite the stored PDF for an existing drawing row. Returns byte size."""
    if not pdf_bytes:
        raise DrawingUploadError("empty upload", 400)
    tags = dict(d.tags) if isinstance(d.tags, dict) else {}
    obj_name = preferred_drawing_object_name(d)
    try:
        sz = save_upload(UploadCategory.DRAWINGS, obj_name, io.BytesIO(pdf_bytes))
    except StorageError as exc:
        raise DrawingUploadError(exc.message, exc.status) from exc
    except OSError as exc:
        raise DrawingUploadError(f"could not save file: {exc}", 500) from exc
    if sz == 0:
        raise DrawingUploadError("empty upload", 400)
    tags["storage_object"] = obj_name
    tags.pop("file_pending", None)
    tags.pop("storage_error", None)
    tags["content_hash"] = hashlib.sha256(pdf_bytes).hexdigest()
    d.tags = tags
    d.file_url = f"/api/v1/drawings/{d.id}/file"
    d.file_size_bytes = int(sz)
    d.mime_type = "application/pdf"
    return sz


class DrawingUploadError(Exception):
    def __init__(self, message: str, status: int = 400, drawing: Drawing | None = None):
        self.message = message
        self.status = status
        self.drawing = drawing


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


def _pending_drawing_row(
    project_id: uuid.UUID | None,
    sheet_number: str | None,
    drawing_set: str | None,
    revision: str,
) -> Drawing | None:
    """Reuse a row whose B2 write failed so a retry does not create a duplicate."""
    sn = (sheet_number or "").strip()
    if project_id is None or not sn:
        return None
    q = (
        select(Drawing)
        .where(Drawing.project_id == project_id, Drawing.sheet_number == sn)
        .order_by(Drawing.created_at.desc(), Drawing.id.desc())
    )
    dset = (drawing_set or "").strip()
    rev = (revision or "").strip()
    for row in db.session.scalars(q):
        tags = row.tags if isinstance(row.tags, dict) else {}
        if not tags.get("file_pending"):
            continue
        if dset and (row.drawing_set or "").strip() != dset:
            continue
        if rev and (row.revision or "").strip() != rev:
            continue
        return row
    return None


def _mark_file_pending(d: Drawing, obj_name: str, message: str) -> None:
    tags = dict(d.tags) if isinstance(d.tags, dict) else {}
    tags["storage_object"] = obj_name
    tags["file_pending"] = True
    tags["storage_error"] = (message or "")[:400]
    d.tags = tags
    d.file_url = f"/api/v1/drawings/{d.id}/file"
    d.file_size_bytes = 0
    d.mime_type = "application/pdf"


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
    labels = label_drawing(
        filename=raw_name,
        sheet_number=sheet_number,
        sheet_title=sheet_title,
        discipline=discipline,
        drawing_set=drawing_set,
        revision=revision,
        allow_filename_sheet=not (page_count > 1 and page_index is not None and not sheet_number),
    )
    if page_count > 1 and page_index is not None:
        title = labels["sheet_title"] or sheet_title or f"{base} — page {page_index + 1}"
        sn = sheet_number or f"Page {page_index + 1}"
        orig = f"{base}_p{page_index + 1}.pdf"
    else:
        title = labels["sheet_title"] or sheet_title or base
        sn = labels["sheet_number"]
        orig = safe_filename(raw_name, default="drawing.pdf")
        if not orig.lower().endswith(".pdf"):
            orig += ".pdf"

    pending = _pending_drawing_row(project_id, sn, labels["drawing_set"] or drawing_set, labels["revision"] or revision)
    if pending is not None:
        d = pending
    else:
        series_id = _existing_series_id(project_id, sn)
        d = Drawing(
            project_id=project_id,
            title=title[:500],
            sheet_number=(sn[:50] if sn else None),
            sheet_title=title[:500],
            discipline=(labels["discipline"][:50] if labels["discipline"] else None),
            drawing_set=(labels["drawing_set"][:120] if labels["drawing_set"] else None),
            revision=(labels["revision"] or revision or "0")[:50],
            mime_type="application/pdf",
            original_filename=orig[:500],
            drawing_series_id=series_id,
        )
        db.session.add(d)
        db.session.flush()

    obj_name = drawing_storage_relpath(d)
    try:
        sz = save_upload(UploadCategory.DRAWINGS, obj_name, io.BytesIO(pdf_bytes))
    except StorageError as exc:
        _mark_file_pending(d, obj_name, exc.message)
        from ..api._drawing_hygiene import apply_hygiene

        apply_hygiene(d)
        raise DrawingUploadError(exc.message, exc.status, drawing=d) from exc
    except OSError as exc:
        _mark_file_pending(d, obj_name, f"could not save file: {exc}")
        raise DrawingUploadError(f"could not save file: {exc}", 500, drawing=d) from exc

    if sz == 0:
        delete_stored(UploadCategory.DRAWINGS, obj_name)
        raise DrawingUploadError("empty upload", 400, drawing=d)

    tags = dict(d.tags) if isinstance(d.tags, dict) else {}
    tags["storage_object"] = obj_name
    tags.pop("file_pending", None)
    tags.pop("storage_error", None)
    tags["content_hash"] = hashlib.sha256(pdf_bytes).hexdigest()
    d.tags = tags
    d.file_url = f"/api/v1/drawings/{d.id}/file"
    d.file_size_bytes = int(sz)
    from ..api._drawing_hygiene import apply_hygiene

    apply_hygiene(d)
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
