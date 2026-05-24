"""I-9 supporting document photo upload/download for the hire wizard."""

from __future__ import annotations

import uuid
from pathlib import Path

from flask import Blueprint, request
from sqlalchemy import func, select
from werkzeug.utils import secure_filename

from ..extensions import db
from ..models import AuditLog, HrHireApplication, HrHireI9DocumentFile
from ..services.hr_i9_documents import (
    I9_DOC_EXT,
    I9_DOC_MAX_BYTES,
    I9_DOC_MAX_PER_SLOT,
    I9_DOC_SLOTS,
    serialize_i9_document,
)
from ..services.hr_hire_upload import resolve_hire_doc_upload
from ..services.hire_application_review import applicant_wizard_mutable
from ..services.hire_path import applicant_may_complete_i9_w4
from ..services.object_storage import UploadCategory, delete_stored, save_upload, send_stored_file
from ._perms import current_user
from .v1 import _jsonify


def _client_ip_for_audit() -> str | None:
    xff = request.headers.get("X-Forwarded-For")
    if xff:
        first = xff.split(",")[0].strip()
        if first:
            return first[:64]
    if request.remote_addr:
        return str(request.remote_addr)[:64]
    return None


def _parse_uuid_param(raw: str) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(raw))
    except (ValueError, AttributeError):
        return None


def _hire_row_for_user(uid: uuid.UUID) -> HrHireApplication | None:
    return db.session.scalar(select(HrHireApplication).where(HrHireApplication.user_id == uid))


def _i9_locked(hire_row: HrHireApplication | None) -> bool:
    return _i9_upload_block(hire_row) is not None


def _i9_upload_block(hire_row: HrHireApplication | None) -> tuple[str, int] | None:
    if hire_row is None:
        return "hire application not found", 404
    if hire_row.i9_signed_at is not None:
        return "I-9 is signed and locked", 409
    if not applicant_wizard_mutable(hire_row):
        return "I-9 cannot be edited in the current hire status", 409
    if not applicant_may_complete_i9_w4(hire_row):
        return "Accept your job offer before uploading I-9 document photos", 403
    return None


def list_i9_documents_for_hire(hire_row: HrHireApplication | None) -> list[dict]:
    if hire_row is None:
        return []
    rows = db.session.scalars(
        select(HrHireI9DocumentFile)
        .where(HrHireI9DocumentFile.hire_application_id == hire_row.id)
        .order_by(HrHireI9DocumentFile.slot, HrHireI9DocumentFile.sort_order, HrHireI9DocumentFile.created_at)
    ).all()
    return [serialize_i9_document(r) for r in rows]


def _next_sort_order(hire_id: uuid.UUID, slot: str) -> int:
    existing = db.session.scalars(
        select(HrHireI9DocumentFile.sort_order)
        .where(
            HrHireI9DocumentFile.hire_application_id == hire_id,
            HrHireI9DocumentFile.slot == slot,
        )
        .order_by(HrHireI9DocumentFile.sort_order.desc())
    ).all()
    if not existing:
        return 0
    return int(existing[0]) + 1


def register_hr_i9_document_routes(bp: Blueprint) -> None:
    @bp.post("/hr/me/i9-section1/documents")
    def hr_me_i9_document_upload():
        cu = current_user()
        if cu.user is None:
            return _jsonify({"entity": "hr_i9_document", "error": "authentication required"}), 401

        uid = cu.user.id
        hire_row = _hire_row_for_user(uid)
        if hire_row is None:
            hire_row = HrHireApplication(user_id=uid)
            db.session.add(hire_row)
            db.session.flush()

        blocked = _i9_upload_block(hire_row)
        if blocked is not None:
            msg, status = blocked
            return _jsonify({"entity": "hr_i9_document", "error": msg}), status

        slot = (request.form.get("slot") or "").strip().lower()
        if slot not in I9_DOC_SLOTS:
            return _jsonify(
                {
                    "entity": "hr_i9_document",
                    "error": f"slot must be one of: {', '.join(sorted(I9_DOC_SLOTS))}",
                }
            ), 400

        count = db.session.scalar(
            select(func.count())
            .select_from(HrHireI9DocumentFile)
            .where(
                HrHireI9DocumentFile.hire_application_id == hire_row.id,
                HrHireI9DocumentFile.slot == slot,
            )
        )
        if count is not None and int(count) >= I9_DOC_MAX_PER_SLOT:
            return _jsonify(
                {
                    "entity": "hr_i9_document",
                    "error": f"maximum {I9_DOC_MAX_PER_SLOT} photos per document slot",
                }
            ), 400

        f = request.files.get("file")
        if f is None or not getattr(f, "filename", None):
            return _jsonify({"entity": "hr_i9_document", "error": "missing file field (multipart form-data)"}), 400

        raw_name = secure_filename(f.filename) or "photo.jpg"
        resolved = resolve_hire_doc_upload(f.filename, f.mimetype)
        if resolved is None:
            ext = Path(raw_name).suffix.lower() or "(unknown)"
            return _jsonify(
                {
                    "entity": "hr_i9_document",
                    "error": f"unsupported file type {ext}; allowed: {', '.join(sorted(I9_DOC_EXT))}",
                }
            ), 400
        raw_name, ext = resolved

        cl = request.content_length
        if cl is not None and cl > I9_DOC_MAX_BYTES:
            return _jsonify({"entity": "hr_i9_document", "error": "file too large (max 10MB)"}), 400

        sort_raw = request.form.get("sort_order")
        if sort_raw is not None and str(sort_raw).strip() != "":
            try:
                sort_order = int(sort_raw)
            except ValueError:
                return _jsonify({"entity": "hr_i9_document", "error": "invalid sort_order"}), 400
            if sort_order < 0 or sort_order > 9:
                return _jsonify({"entity": "hr_i9_document", "error": "sort_order out of range"}), 400
        else:
            sort_order = _next_sort_order(hire_row.id, slot)

        row = HrHireI9DocumentFile(
            hire_application_id=hire_row.id,
            slot=slot,
            sort_order=sort_order,
            original_filename=raw_name[:500],
            mime_type=(f.mimetype or "").strip()[:120] or None,
            file_ext=ext,
        )
        db.session.add(row)
        db.session.flush()

        obj_name = f"{row.id}{ext}"
        try:
            sz = save_upload(UploadCategory.HR_I9, obj_name, f)
        except OSError as exc:
            db.session.rollback()
            return _jsonify({"entity": "hr_i9_document", "error": f"could not save file: {exc}"}), 500
        except Exception as exc:
            db.session.rollback()
            return _jsonify({"entity": "hr_i9_document", "error": f"could not save file: {exc}"}), 500

        if sz == 0:
            delete_stored(UploadCategory.HR_I9, obj_name)
            db.session.rollback()
            return _jsonify({"entity": "hr_i9_document", "error": "empty upload"}), 400
        if sz > I9_DOC_MAX_BYTES:
            delete_stored(UploadCategory.HR_I9, obj_name)
            db.session.rollback()
            return _jsonify({"entity": "hr_i9_document", "error": "file too large (max 10MB)"}), 400

        row.file_size_bytes = int(sz) if sz is not None else None
        db.session.add(
            AuditLog(
                user_id=uid,
                entity_type="hr_hire_i9_document",
                entity_id=row.id,
                action="uploaded",
                ip_address=_client_ip_for_audit(),
                message=f"I-9 document photo uploaded ({slot})",
            )
        )
        db.session.commit()
        return _jsonify({"entity": "hr_i9_document", "ok": True, "item": serialize_i9_document(row)}), 201

    @bp.get("/hr/me/i9-section1/documents/<uuid:file_id>/file")
    def hr_me_i9_document_file(file_id: uuid.UUID):
        cu = current_user()
        if cu.user is None:
            return _jsonify({"entity": "hr_i9_document", "error": "authentication required"}), 401

        row = db.session.get(HrHireI9DocumentFile, file_id)
        if row is None:
            return _jsonify({"entity": "hr_i9_document", "error": "not found"}), 404

        hire_row = db.session.get(HrHireApplication, row.hire_application_id)
        if hire_row is None or hire_row.user_id != cu.user.id:
            return _jsonify({"entity": "hr_i9_document", "error": "not found"}), 404

        obj_name = f"{row.id}{row.file_ext}"
        dl = (row.original_filename or "document-photo").replace('"', "")[:200]
        mt = row.mime_type or "image/jpeg"
        resp = send_stored_file(
            UploadCategory.HR_I9,
            obj_name,
            mimetype=mt,
            download_name=dl,
        )
        if resp is None:
            return _jsonify({"entity": "hr_i9_document", "error": "file not found on server"}), 404
        return resp

    @bp.delete("/hr/me/i9-section1/documents/<uuid:file_id>")
    def hr_me_i9_document_delete(file_id: uuid.UUID):
        cu = current_user()
        if cu.user is None:
            return _jsonify({"entity": "hr_i9_document", "error": "authentication required"}), 401

        row = db.session.get(HrHireI9DocumentFile, file_id)
        if row is None:
            return _jsonify({"entity": "hr_i9_document", "error": "not found"}), 404

        hire_row = db.session.get(HrHireApplication, row.hire_application_id)
        if hire_row is None or hire_row.user_id != cu.user.id:
            return _jsonify({"entity": "hr_i9_document", "error": "not found"}), 404

        if _i9_locked(hire_row):
            return _jsonify({"entity": "hr_i9_document", "error": "I-9 is signed and locked"}), 409

        obj_name = f"{row.id}{row.file_ext}"
        db.session.delete(row)
        db.session.add(
            AuditLog(
                user_id=cu.user.id,
                entity_type="hr_hire_i9_document",
                entity_id=file_id,
                action="deleted",
                ip_address=_client_ip_for_audit(),
                message=f"I-9 document photo removed ({row.slot})",
            )
        )
        db.session.commit()
        delete_stored(UploadCategory.HR_I9, obj_name)
        return _jsonify({"entity": "hr_i9_document", "ok": True, "deleted": True, "id": str(file_id)})
