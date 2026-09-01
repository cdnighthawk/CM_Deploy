"""Private B2 snapshots for RFP vendor files (no public bucket, no SMTP attach)."""
from __future__ import annotations

import hashlib
import io
import re
import uuid
import zipfile
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from flask import Response, current_app, redirect, send_file
from sqlalchemy import select

from ..extensions import db
from ..models import AuditLog, Document, Drawing, Rfp, RfpDrawing
from .object_storage import (
    UploadCategory,
    b2_enabled,
    copy_b2_object,
    local_raw_path,
    object_key,
    prefixed_key,
    presigned_get_url,
    put_raw_bytes,
    read_raw_bytes,
    read_stored_bytes,
    stored_exists,
)
from .project_file_keys import document_object_candidates, drawing_object_candidates, safe_filename

_CAD_EXT = frozenset({".dwg", ".rvt", ".dxf", ".ifc"})
_UNSAFE = re.compile(r"[^A-Za-z0-9._-]+")


def download_ttl() -> int:
    try:
        return int(current_app.config.get("B2_DOWNLOAD_TTL_SEC") or 600)
    except (TypeError, ValueError, RuntimeError):
        return 600


def _is_cad(obj: Drawing | Document | None) -> bool:
    if obj is None:
        return False
    name = (getattr(obj, "original_filename", None) or getattr(obj, "title", None) or "").lower()
    mime = (getattr(obj, "mime_type", None) or "").lower()
    return any(name.endswith(ext) for ext in _CAD_EXT) or "dwg" in mime or "revit" in mime


def _source_bytes(drawing: Drawing | None, document: Document | None) -> tuple[bytes | None, str, str | None]:
    if drawing is not None:
        for name in drawing_object_candidates(drawing):
            data = read_stored_bytes(UploadCategory.DRAWINGS, name)
            if data:
                fname = drawing.original_filename or f"{drawing.sheet_number or drawing.id}.pdf"
                return data, fname, object_key(UploadCategory.DRAWINGS, name) if b2_enabled() else None
    if document is not None:
        for name in document_object_candidates(document):
            data = read_stored_bytes(UploadCategory.DOCUMENTS, name)
            if data:
                fname = document.original_filename or f"{document.id}.pdf"
                return data, fname, object_key(UploadCategory.DOCUMENTS, name) if b2_enabled() else None
    return None, "", None


def _source_b2_key(drawing: Drawing | None, document: Document | None) -> str | None:
    if not b2_enabled():
        return None
    if drawing is not None:
        for name in drawing_object_candidates(drawing):
            if stored_exists(UploadCategory.DRAWINGS, name):
                return object_key(UploadCategory.DRAWINGS, name)
    if document is not None:
        for name in document_object_candidates(document):
            if stored_exists(UploadCategory.DOCUMENTS, name):
                return object_key(UploadCategory.DOCUMENTS, name)
    return None


def snap_rel_key(
    rfp_id: uuid.UUID,
    send_batch: str,
    *,
    source_id: uuid.UUID,
    rev: str,
    filename: str,
) -> str:
    safe = safe_filename(filename, default="drawing.pdf")
    rev_part = _UNSAFE.sub("-", (rev or "0").strip())[:40] or "0"
    return f"rfp/{rfp_id}/snap/{send_batch}/{source_id}/{rev_part}/{safe}"


def zip_rel_key(rfp_id: uuid.UUID, send_batch: str) -> str:
    return f"rfp/{rfp_id}/snap/{send_batch}/_bundle/drawings.zip"


def snapshot_on_send(rfp: Rfp) -> str:
    """Copy selected sheets into a new send_batch. Does not overwrite prior snap keys."""
    send_batch = uuid.uuid4().hex
    rows = list(
        db.session.scalars(select(RfpDrawing).where(RfpDrawing.rfp_id == rfp.id).order_by(RfpDrawing.sort_order)).all()
    )
    if b2_enabled():
        bucket = str(current_app.config.get("B2_BUCKET_NAME") or "") or None
    else:
        current_app.logger.warning(
            "RFP B2 credentials missing — snapshotting to local DOCUMENT_ROOT/instance. "
            "Production must use a private B2 bucket."
        )
        bucket = "local"
    for row in rows:
        drawing = db.session.get(Drawing, row.drawing_id) if row.drawing_id else None
        document = db.session.get(Document, row.document_id) if row.document_id else None
        if _is_cad(drawing or document):
            continue
        data, fname, _src_full = _source_bytes(drawing, document)
        if not data:
            continue
        source_id = drawing.id if drawing is not None else (document.id if document is not None else row.id)
        rev = (drawing.revision if drawing is not None else None) or "0"
        rel = snap_rel_key(rfp.id, send_batch, source_id=source_id, rev=rev, filename=fname)
        copied = False
        src_key = _source_b2_key(drawing, document)
        if src_key:
            copied = copy_b2_object(src_key, prefixed_key(rel))
        if not copied:
            put_raw_bytes(rel, data, content_type="application/pdf")
        digest = hashlib.sha256(data).hexdigest()
        row.b2_bucket = bucket
        row.b2_key = rel
        row.sha256 = digest
        row.byte_size = len(data)
        row.content_type = "application/pdf"
        row.original_filename = (fname or "drawing.pdf")[:500]
        row.send_batch = send_batch
        row.frozen_pdf_path = rel
        row.frozen_checksum = digest
        row.frozen_bytes = len(data)
    rfp.last_send_batch = send_batch
    rfp.files_zip_status = None
    rfp.files_zip_key = None
    rfp.files_zip_bytes = None
    db.session.flush()
    return send_batch


def snap_key_for_row(row: RfpDrawing) -> str | None:
    return (row.b2_key or row.frozen_pdf_path or "").strip() or None


def authorized_download_response(
    row: RfpDrawing,
    *,
    filename: str | None = None,
    as_attachment: bool = True,
) -> Response | tuple[str, int]:
    rel = snap_key_for_row(row)
    name = filename or row.original_filename or "drawing.pdf"
    ctype = row.content_type or "application/pdf"
    if rel and b2_enabled():
        url = presigned_get_url(rel, ttl=download_ttl(), filename=name, content_type=ctype)
        if url:
            return redirect(url, code=302)
        current_app.logger.warning("RFP B2 presign failed for key=%s; falling back is disabled in production", rel)
        return "File is temporarily unavailable.", 503
    if rel:
        current_app.logger.warning(
            "RFP download using local send_file (B2 unset). Production path is a 302 to a private B2 URL."
        )
        data = read_raw_bytes(rel)
        if data:
            return Response(
                data,
                mimetype=ctype,
                headers={
                    "Content-Length": str(len(data)),
                    "Content-Disposition": f'{"attachment" if as_attachment else "inline"}; filename="{name.replace(chr(34), "")}"',
                },
            )
        path = local_raw_path(rel)
        if path.is_file():
            return send_file(path, mimetype=ctype, as_attachment=as_attachment, download_name=name)
    return "File not found", 404


def build_zip_for_rfp(rfp: Rfp) -> dict[str, Any]:
    """Write drawings.zip into B2 (or local fallback). Do not call from a long HTTP path in prod."""
    send_batch = (rfp.last_send_batch or "").strip()
    rows = list(
        db.session.scalars(
            select(RfpDrawing).where(RfpDrawing.rfp_id == rfp.id, RfpDrawing.include_on_portal.is_(True)).order_by(
                RfpDrawing.sort_order
            )
        ).all()
    )
    if not send_batch:
        send_batch = next((r.send_batch for r in rows if r.send_batch), "") or uuid.uuid4().hex
    rel = zip_rel_key(rfp.id, send_batch)
    buf = io.BytesIO()
    used_names: set[str] = set()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for row in rows:
            key = snap_key_for_row(row)
            if not key:
                continue
            data = read_raw_bytes(key)
            if not data:
                continue
            fname = safe_filename(row.original_filename or f"{row.id}.pdf", default=f"{row.id}.pdf")
            if fname in used_names:
                fname = f"{row.id}_{fname}"
            used_names.add(fname)
            zf.writestr(fname, data)
    payload = buf.getvalue()
    if not payload or not used_names:
        rfp.files_zip_status = "error"
        db.session.flush()
        return {"status": "error", "error": "no files to zip"}
    put_raw_bytes(rel, payload, content_type="application/zip")
    rfp.files_zip_status = "ready"
    rfp.files_zip_key = rel
    rfp.files_zip_bytes = len(payload)
    db.session.flush()
    return {"status": "ready", "key": rel, "bytes": len(payload)}


def enqueue_zip(rfp: Rfp) -> dict[str, Any]:
    if (rfp.files_zip_status or "") == "ready" and rfp.files_zip_key:
        return {"status": "ready", "key": rfp.files_zip_key, "bytes": rfp.files_zip_bytes}
    rfp.files_zip_status = "queued"
    db.session.commit()
    celery = None
    try:
        from ..celery_app import celery as celery_app

        celery = celery_app
    except Exception:
        celery = None
    if celery is not None:
        try:
            celery.send_task("rfp.build_files_zip", kwargs={"rfp_id": str(rfp.id)})
            return {"status": "queued"}
        except Exception:
            current_app.logger.exception("RFP zip Celery dispatch failed; building inline")
    result = build_zip_for_rfp(rfp)
    db.session.commit()
    return result


def zip_download_response(rfp: Rfp) -> Response | tuple[str, int]:
    status = (rfp.files_zip_status or "").strip()
    if status == "queued":
        return "Zip is still being prepared. Retry in a moment.", 202
    if status != "ready" or not rfp.files_zip_key:
        return "Zip is not ready. POST /files/zip first.", 404
    name = "drawings.zip"
    if b2_enabled():
        url = presigned_get_url(rfp.files_zip_key, ttl=download_ttl(), filename=name, content_type="application/zip")
        if url:
            return redirect(url, code=302)
        return "File is temporarily unavailable.", 503
    current_app.logger.warning("RFP zip download using local send_file (B2 unset).")
    data = read_raw_bytes(rfp.files_zip_key)
    if not data:
        return "Zip not found", 404
    return Response(
        data,
        mimetype="application/zip",
        headers={
            "Content-Length": str(len(data)),
            "Content-Disposition": f'attachment; filename="{name}"',
        },
    )


def log_download(
    *,
    rfp: Rfp,
    row: RfpDrawing | None,
    company_id: UUID | None,
    bytes_count: int | None,
    ip: str | None,
) -> None:
    db.session.add(
        AuditLog(
            user_id=None,
            entity_type="rfp",
            entity_id=rfp.id,
            action="drawing_download",
            ip_address=(ip or None)[:45] if ip else None,
            changes={
                "rfp_id": str(rfp.id),
                "company_id": str(company_id) if company_id else None,
                "drawing_id": str(row.drawing_id) if row is not None and row.drawing_id else None,
                "rfp_drawing_id": str(row.id) if row is not None else None,
                "bytes": bytes_count,
                "ip": ip,
                "at": datetime.now(timezone.utc).isoformat(),
            },
        )
    )
    db.session.commit()
