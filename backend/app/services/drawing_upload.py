"""Split multi-page drawing PDFs into one stored sheet per page."""
from __future__ import annotations

import hashlib
import io
import uuid
from typing import Any

from pypdf import PdfReader, PdfWriter
from sqlalchemy import select, update
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from ..extensions import db
from ..models import Document, Drawing
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
    preferred_document_object_name,
    preferred_drawing_object_name,
    document_storage_relpath,
    safe_filename,
)

B2_UPLOAD_URL_UNAVAILABLE = "B2_UPLOAD_URL_UNAVAILABLE"
B2_MINT_UNAVAILABLE_MESSAGE = (
    "The website could not mint a Backblaze upload URL. The drawing row is on usiscm, but the PDF was not stored."
)
B2_MINT_UNAVAILABLE_DOCUMENT_MESSAGE = (
    "The website could not mint a Backblaze upload URL. The document row is on usiscm, but the file was not stored."
)
FILE_PENDING_CODE = "FILE_PENDING"
FILE_PENDING_MESSAGE = "file not on cloud yet"


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


def _as_b2_native_hint(raw: dict | None) -> dict | None:
    """Normalize a mint dict to the locked native-B2 contract, or None.

    Never returns ``s3_presigned_put``, ``presignedPut``, or an ``X-Amz-`` URL.
    Old keys (``url``, ``authorization``, ``mode``) stay set so desktop 0.1.162
    can read them, but ``protocol`` / ``kind`` are always ``b2-native``.
    """
    if not isinstance(raw, dict):
        return None
    from .object_storage import is_native_b2_upload_url

    url = str(raw.get("uploadUrl") or raw.get("url") or raw.get("upload_url") or "").strip()
    mode = str(raw.get("protocol") or raw.get("kind") or raw.get("mode") or "").strip().lower().replace("_", "-")
    if mode in {"s3-presigned-put", "s3", "presigned", "s3-presigned"}:
        return None
    if not is_native_b2_upload_url(url):
        return None
    if mode and mode not in {"b2-native", "b2native"}:
        return None
    token = str(
        raw.get("authorizationToken") or raw.get("authorization") or raw.get("token") or ""
    ).strip()
    if not token:
        return None
    file_name = str(raw.get("fileName") or raw.get("file_name") or "").strip()
    bucket_id = str(raw.get("bucketId") or raw.get("bucket_id") or "").strip()
    expires_at = str(raw.get("expiresAt") or raw.get("expires_at") or "").strip()
    return {
        "protocol": "b2-native",
        "kind": "b2-native",
        "mode": "b2_native",
        "uploadUrl": url,
        "url": url,
        "authorizationToken": token,
        "authorization": token,
        "fileName": file_name,
        "file_name": file_name,
        "bucketId": bucket_id or None,
        "expiresAt": expires_at or None,
        "sha1_header": raw.get("sha1_header") or "X-Bz-Content-Sha1",
    }


def mint_unavailable_body(*, kind: str = "drawing", detail: str | None = None) -> dict[str, Any]:
    message = B2_MINT_UNAVAILABLE_DOCUMENT_MESSAGE if kind == "document" else B2_MINT_UNAVAILABLE_MESSAGE
    error: dict[str, Any] = {"code": B2_UPLOAD_URL_UNAVAILABLE, "message": message}
    if detail:
        error["detail"] = detail
    return {"error": error}


def drawing_file_pending(d) -> bool:
    tags = d.tags if isinstance(getattr(d, "tags", None), dict) else {}
    return bool(tags.get("file_pending"))


def document_file_pending(d) -> bool:
    return drawing_file_pending(d)


def file_pending_error_body() -> dict[str, Any]:
    return {"error": {"code": FILE_PENDING_CODE, "message": FILE_PENDING_MESSAGE}}


def parse_ack_payload(payload: dict[str, Any] | None) -> dict[str, Any]:
    """Accept locked ``{ item: { b2FileId, ... } }`` and the older flat keys."""
    raw = payload if isinstance(payload, dict) else {}
    item = raw.get("item") if isinstance(raw.get("item"), dict) else raw

    def text(*keys: str) -> str | None:
        for key in keys:
            value = item.get(key)
            if value is None and item is not raw:
                value = raw.get(key)
            if value is None:
                continue
            text_value = str(value).strip()
            if text_value:
                return text_value
        return None

    byte_size = None
    for key in ("contentLength", "content_length", "byte_size", "byteSize"):
        raw_size = item.get(key)
        if raw_size is None and item is not raw:
            raw_size = raw.get(key)
        if raw_size is None:
            continue
        try:
            byte_size = int(raw_size)
        except (TypeError, ValueError) as exc:
            raise DrawingUploadError("byte_size must be an integer", 400) from exc
        break
    return {
        "b2_file_id": text("b2FileId", "b2_file_id", "fileId"),
        "b2_file_name": text("b2FileName", "b2_file_name", "fileName"),
        "content_sha1": text("contentSha1", "content_sha1"),
        "content_hash": text("sha256", "content_hash", "contentHash"),
        "content_type": text("contentType", "content_type"),
        "byte_size": byte_size,
    }


def native_upload_hint_for_drawing(d: Drawing) -> dict | None:
    """Mint a native ``b2_upload_file`` session for this drawing, or None.

    Desktop ingest (USISPdfApp) writes the PDF itself. Never return an S3
    presigned PUT: those are signed locally with boto3 and never talk to B2.
    """
    from .object_storage import native_upload_session

    name = preferred_drawing_object_name(d)
    native = native_upload_session(UploadCategory.DRAWINGS, name)
    return _as_b2_native_hint(native)


def native_upload_hint_for_document(d: Document) -> dict | None:
    """Mint a native ``b2_upload_file`` session for a non-drawing document."""
    from .object_storage import native_upload_session

    name = preferred_document_object_name(d)
    native = native_upload_session(UploadCategory.DOCUMENTS, name)
    return _as_b2_native_hint(native)


def _apply_ack_tags(
    row,
    *,
    obj_name: str,
    byte_size: int,
    content_hash: str | None,
    b2_file_id: str | None,
    b2_file_name: str | None,
    content_sha1: str | None,
    content_type: str | None,
    default_mime: str,
) -> None:
    tags = dict(row.tags) if isinstance(row.tags, dict) else {}
    existing_id = str(tags.get("b2_file_id") or "").strip()
    if existing_id and b2_file_id and existing_id == b2_file_id and not tags.get("file_pending"):
        if byte_size and not row.file_size_bytes:
            row.file_size_bytes = int(byte_size)
        return
    tags["storage_object"] = obj_name
    tags.pop("file_pending", None)
    tags.pop("storage_error", None)
    digest = (content_hash or "").strip().lower()
    if digest:
        tags["content_hash"] = digest
    if b2_file_id:
        tags["b2_file_id"] = b2_file_id
    if b2_file_name:
        tags["b2_file_name"] = b2_file_name
    if content_sha1:
        tags["content_sha1"] = content_sha1
    row.tags = tags
    row.file_size_bytes = int(byte_size)
    if content_type:
        row.mime_type = content_type[:120]
    elif not row.mime_type:
        row.mime_type = default_mime


def ack_drawing_file(
    d: Drawing,
    *,
    byte_size: int | None = None,
    content_hash: str | None = None,
    b2_file_id: str | None = None,
    b2_file_name: str | None = None,
    content_sha1: str | None = None,
    content_type: str | None = None,
) -> int:
    """Mark a drawing as stored after the client wrote the object (native B2).

    Prefer HEAD of B2 when that works. If the S3 gateway is still dropping,
    trust the client's byte size so ingest can clear ``file_pending``.
    Idempotent on the same ``b2FileId``.
    """
    obj_name = (b2_file_name or "").strip() or preferred_drawing_object_name(d)
    tags = dict(d.tags) if isinstance(d.tags, dict) else {}
    stored_name = str(tags.get("storage_object") or "").strip()
    if stored_name:
        obj_name = stored_name
    sz = stored_size(UploadCategory.DRAWINGS, preferred_drawing_object_name(d))
    if not sz:
        sz = stored_size(UploadCategory.DRAWINGS, obj_name)
    if not sz:
        if byte_size and int(byte_size) > 0:
            sz = int(byte_size)
        else:
            raise DrawingUploadError("file not found in storage", 404)
    _apply_ack_tags(
        d,
        obj_name=preferred_drawing_object_name(d),
        byte_size=int(sz),
        content_hash=content_hash,
        b2_file_id=b2_file_id,
        b2_file_name=b2_file_name,
        content_sha1=content_sha1,
        content_type=content_type,
        default_mime="application/pdf",
    )
    d.file_url = f"/api/v1/drawings/{d.id}/file"
    d.mime_type = (content_type or d.mime_type or "application/pdf")[:120]
    return int(sz)


def ack_document_file(
    d: Document,
    *,
    byte_size: int | None = None,
    content_hash: str | None = None,
    b2_file_id: str | None = None,
    b2_file_name: str | None = None,
    content_sha1: str | None = None,
    content_type: str | None = None,
) -> int:
    """Mark a document as stored after the client wrote the object (native B2)."""
    obj_name = preferred_document_object_name(d)
    sz = stored_size(UploadCategory.DOCUMENTS, obj_name)
    if not sz:
        if byte_size and int(byte_size) > 0:
            sz = int(byte_size)
        else:
            raise DrawingUploadError("file not found in storage", 404)
    _apply_ack_tags(
        d,
        obj_name=obj_name,
        byte_size=int(sz),
        content_hash=content_hash,
        b2_file_id=b2_file_id,
        b2_file_name=b2_file_name,
        content_sha1=content_sha1,
        content_type=content_type,
        default_mime="application/octet-stream",
    )
    d.file_url = f"/api/v1/documents/{d.id}/file"
    return int(sz)


def load_catalog_document(doc_id: uuid.UUID) -> Document | None:
    """Load a drawing or document without blowing up on unmapped document_type identities."""
    drawing = db.session.get(Drawing, doc_id)
    if drawing is not None:
        return drawing
    try:
        return db.session.get(Document, doc_id)
    except AssertionError:
        return _document_from_core(doc_id)


def _document_from_core(doc_id: uuid.UUID) -> Document | None:
    rec = db.session.execute(select(Document.__table__).where(Document.__table__.c.id == doc_id)).mappings().first()
    if rec is None:
        return None
    obj = Document()
    for key, value in rec.items():
        if key == "document_type":
            continue
        try:
            setattr(obj, key, value)
        except Exception:
            pass
    object.__setattr__(obj, "document_type", rec.get("document_type") or "other")
    return obj


def persist_document_ack(doc_id: uuid.UUID, row: Document) -> None:
    """Write ack fields for a document that may not be a safe ORM identity."""
    try:
        attached = db.session.get(Document, doc_id)
    except AssertionError:
        attached = None
    if attached is not None and attached is row:
        return
    db.session.execute(
        update(Document.__table__)
        .where(Document.__table__.c.id == doc_id)
        .values(
            tags=row.tags,
            file_url=row.file_url,
            file_size_bytes=row.file_size_bytes,
            mime_type=row.mime_type,
        )
    )


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


def create_pending_drawing(
    *,
    project_id: uuid.UUID | None,
    sheet_number: str | None,
    sheet_title: str | None,
    revision: str | None,
    source_file_name: str | None,
    discipline: str | None = None,
    drawing_set: str | None = None,
    client_id: uuid.UUID | None = None,
    content_hash: str | None = None,
) -> Drawing:
    """Insert a catalog row and wait for the client to write the PDF to B2."""
    raw_name = (source_file_name or "").strip() or "drawing.pdf"
    labels = label_drawing(
        filename=raw_name,
        sheet_number=sheet_number,
        sheet_title=sheet_title,
        discipline=discipline,
        drawing_set=drawing_set,
        revision=revision,
    )
    title = (labels["sheet_title"] or sheet_title or _base_name(raw_name))[:500]
    sn = (labels["sheet_number"] or sheet_number or "").strip() or None
    orig = safe_filename(raw_name, default="drawing.pdf")
    if not orig.lower().endswith(".pdf"):
        orig += ".pdf"

    existing = None
    if client_id is not None:
        existing = db.session.get(Drawing, client_id)
    if existing is None:
        existing = _pending_drawing_row(
            project_id,
            sn,
            labels["drawing_set"] or drawing_set,
            labels["revision"] or (revision or "0"),
        )
    if existing is not None:
        d = existing
        d.project_id = project_id
        d.title = title
        d.sheet_number = sn[:50] if sn else d.sheet_number
        d.sheet_title = title
        if labels["discipline"]:
            d.discipline = labels["discipline"][:50]
        if labels["drawing_set"]:
            d.drawing_set = labels["drawing_set"][:120]
        d.revision = (labels["revision"] or revision or d.revision or "0")[:50]
        d.original_filename = orig[:500]
    else:
        series_id = _existing_series_id(project_id, sn)
        d = Drawing(
            id=client_id,
            project_id=project_id,
            title=title,
            sheet_number=(sn[:50] if sn else None),
            sheet_title=title,
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
    _mark_file_pending(d, obj_name, "waiting for client B2 upload")
    digest = (content_hash or "").strip().lower()
    if digest:
        tags = dict(d.tags) if isinstance(d.tags, dict) else {}
        tags["content_hash"] = digest
        d.tags = tags
    from ..api._drawing_hygiene import apply_hygiene

    apply_hygiene(d)
    return d


def create_pending_document(
    *,
    project_id: uuid.UUID | None,
    filename: str | None,
    document_type: str | None = None,
    title: str | None = None,
    mime_type: str | None = None,
    content_hash: str | None = None,
    client_id: uuid.UUID | None = None,
) -> Document:
    """Insert a catalog document row and wait for the client to write bytes to B2."""
    raw_name = (filename or "").strip() or "document"
    orig = safe_filename(raw_name, default="document")
    raw_type = (document_type or "other").strip().lower() or "other"
    allowed = {
        "rfi",
        "submittal",
        "specification",
        "contract",
        "change_order",
        "invoice",
        "photo",
        "report",
        "ai_review_export",
        "safety_doc",
        "permit",
        "other",
    }
    dtype = raw_type if raw_type in allowed else "other"
    existing = db.session.get(Document, client_id) if client_id is not None else None
    if existing is not None and not isinstance(existing, Drawing):
        d = existing
        d.project_id = project_id
        d.title = (title or d.title or orig)[:500]
        d.original_filename = orig[:500]
        if mime_type:
            d.mime_type = mime_type[:120]
    else:
        d = Document(
            id=client_id,
            project_id=project_id,
            document_type=dtype,
            title=(title or orig)[:500],
            original_filename=orig[:500],
            mime_type=(mime_type or "application/octet-stream")[:120],
            file_size_bytes=0,
        )
        db.session.add(d)
        db.session.flush()
    obj_name = document_storage_relpath(d)
    _mark_file_pending(d, obj_name, "waiting for client B2 upload")
    digest = (content_hash or "").strip().lower()
    if digest:
        tags = dict(d.tags) if isinstance(d.tags, dict) else {}
        tags["content_hash"] = digest
        d.tags = tags
    d.file_url = f"/api/v1/documents/{d.id}/file"
    return d


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
