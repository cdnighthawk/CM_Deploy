"""Union card / dispatch photo upload/download for the hire wizard."""

from __future__ import annotations

import uuid
from pathlib import Path

from flask import Blueprint, request
from sqlalchemy import func, select
from werkzeug.utils import secure_filename

from ..extensions import db
from ..models import AuditLog, HrHireApplication, HrHireUnionDocumentFile
from ..services.hr_union_documents import (
    UNION_DOC_EXT,
    UNION_DOC_KINDS,
    UNION_DOC_MAX_BYTES,
    UNION_DOC_MAX_PER_KIND,
    serialize_union_document,
)
from ..services.hr_hire_upload import resolve_hire_doc_upload
from ..services.hire_application_review import applicant_wizard_mutable
from ..services.hire_path import applicant_may_upload_union
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


def _hire_row_for_user(uid: uuid.UUID) -> HrHireApplication | None:
    return db.session.scalar(select(HrHireApplication).where(HrHireApplication.user_id == uid))


def _hire_wizard_locked(hire_row: HrHireApplication | None) -> bool:
    return not applicant_wizard_mutable(hire_row)


def _union_upload_requires_w4(hire_row: HrHireApplication | None) -> bool:
    return hire_row is None or hire_row.w4_signed_at is None


def list_union_documents_for_hire(hire_row: HrHireApplication | None) -> list[dict]:
    if hire_row is None:
        return []
    rows = db.session.scalars(
        select(HrHireUnionDocumentFile)
        .where(HrHireUnionDocumentFile.hire_application_id == hire_row.id)
        .order_by(
            HrHireUnionDocumentFile.document_kind,
            HrHireUnionDocumentFile.sort_order,
            HrHireUnionDocumentFile.created_at,
        )
    ).all()
    return [serialize_union_document(r) for r in rows]


def union_kind_has_photo(hire_row: HrHireApplication | None, kind: str) -> bool:
    if hire_row is None:
        return False
    count = db.session.scalar(
        select(func.count())
        .select_from(HrHireUnionDocumentFile)
        .where(
            HrHireUnionDocumentFile.hire_application_id == hire_row.id,
            HrHireUnionDocumentFile.document_kind == kind,
        )
    )
    return count is not None and int(count) > 0


def _next_sort_order(hire_id: uuid.UUID, kind: str) -> int:
    existing = db.session.scalars(
        select(HrHireUnionDocumentFile.sort_order)
        .where(
            HrHireUnionDocumentFile.hire_application_id == hire_id,
            HrHireUnionDocumentFile.document_kind == kind,
        )
        .order_by(HrHireUnionDocumentFile.sort_order.desc())
    ).all()
    if not existing:
        return 0
    return int(existing[0]) + 1


def register_hr_union_document_routes(bp: Blueprint) -> None:
    @bp.post("/hr/me/hire-wizard/union-documents")
    def hr_me_union_document_upload():
        cu = current_user()
        if cu.user is None:
            return _jsonify({"entity": "hr_union_document", "error": "authentication required"}), 401

        uid = cu.user.id
        hire_row = _hire_row_for_user(uid)
        if hire_row is None:
            hire_row = HrHireApplication(user_id=uid)
            db.session.add(hire_row)
            db.session.flush()

        if _hire_wizard_locked(hire_row):
            return _jsonify({"entity": "hr_union_document", "error": "Hire wizard is complete and locked"}), 409

        if not applicant_may_upload_union(hire_row):
            return _jsonify(
                {
                    "entity": "hr_union_document",
                    "error": "Union document uploads are only available for union dispatch applicants",
                }
            ), 403

        if _union_upload_requires_w4(hire_row):
            return _jsonify(
                {
                    "entity": "hr_union_document",
                    "error": "Complete and sign Form W-4 before uploading union documents",
                }
            ), 409

        kind = (request.form.get("kind") or request.form.get("document_kind") or "").strip().lower()
        if kind not in UNION_DOC_KINDS:
            return _jsonify(
                {
                    "entity": "hr_union_document",
                    "error": f"kind must be one of: {', '.join(sorted(UNION_DOC_KINDS))}",
                }
            ), 400

        count = db.session.scalar(
            select(func.count())
            .select_from(HrHireUnionDocumentFile)
            .where(
                HrHireUnionDocumentFile.hire_application_id == hire_row.id,
                HrHireUnionDocumentFile.document_kind == kind,
            )
        )
        if count is not None and int(count) >= UNION_DOC_MAX_PER_KIND:
            return _jsonify(
                {
                    "entity": "hr_union_document",
                    "error": f"maximum {UNION_DOC_MAX_PER_KIND} photos per document type",
                }
            ), 400

        f = request.files.get("file")
        if f is None or not getattr(f, "filename", None):
            return _jsonify({"entity": "hr_union_document", "error": "missing file field (multipart form-data)"}), 400

        raw_name = secure_filename(f.filename) or "photo.jpg"
        resolved = resolve_hire_doc_upload(f.filename, f.mimetype)
        if resolved is None:
            ext = Path(raw_name).suffix.lower() or "(unknown)"
            return _jsonify(
                {
                    "entity": "hr_union_document",
                    "error": f"unsupported file type {ext}; allowed: {', '.join(sorted(UNION_DOC_EXT))}",
                }
            ), 400
        raw_name, ext = resolved

        cl = request.content_length
        if cl is not None and cl > UNION_DOC_MAX_BYTES:
            return _jsonify({"entity": "hr_union_document", "error": "file too large (max 10MB)"}), 400

        sort_raw = request.form.get("sort_order")
        if sort_raw is not None and str(sort_raw).strip() != "":
            try:
                sort_order = int(sort_raw)
            except ValueError:
                return _jsonify({"entity": "hr_union_document", "error": "invalid sort_order"}), 400
            if sort_order < 0 or sort_order > 9:
                return _jsonify({"entity": "hr_union_document", "error": "sort_order out of range"}), 400
        else:
            sort_order = _next_sort_order(hire_row.id, kind)

        row = HrHireUnionDocumentFile(
            hire_application_id=hire_row.id,
            document_kind=kind,
            sort_order=sort_order,
            original_filename=raw_name[:500],
            mime_type=(f.mimetype or "").strip()[:120] or None,
            file_ext=ext,
        )
        db.session.add(row)
        db.session.flush()

        obj_name = f"{row.id}{ext}"
        try:
            sz = save_upload(UploadCategory.HR_UNION, obj_name, f)
        except OSError as exc:
            db.session.rollback()
            return _jsonify({"entity": "hr_union_document", "error": f"could not save file: {exc}"}), 500
        except Exception as exc:
            db.session.rollback()
            return _jsonify({"entity": "hr_union_document", "error": f"could not save file: {exc}"}), 500

        if sz == 0:
            delete_stored(UploadCategory.HR_UNION, obj_name)
            db.session.rollback()
            return _jsonify({"entity": "hr_union_document", "error": "empty upload"}), 400
        if sz > UNION_DOC_MAX_BYTES:
            delete_stored(UploadCategory.HR_UNION, obj_name)
            db.session.rollback()
            return _jsonify({"entity": "hr_union_document", "error": "file too large (max 10MB)"}), 400

        row.file_size_bytes = int(sz) if sz is not None else None
        db.session.add(
            AuditLog(
                user_id=uid,
                entity_type="hr_hire_union_document",
                entity_id=row.id,
                action="uploaded",
                ip_address=_client_ip_for_audit(),
                message=f"Union document photo uploaded ({kind})",
            )
        )
        db.session.commit()
        return _jsonify({"entity": "hr_union_document", "ok": True, "item": serialize_union_document(row)}), 201

    @bp.get("/hr/me/hire-wizard/union-documents/<uuid:file_id>/file")
    def hr_me_union_document_file(file_id: uuid.UUID):
        cu = current_user()
        if cu.user is None:
            return _jsonify({"entity": "hr_union_document", "error": "authentication required"}), 401

        row = db.session.get(HrHireUnionDocumentFile, file_id)
        if row is None:
            return _jsonify({"entity": "hr_union_document", "error": "not found"}), 404

        hire_row = db.session.get(HrHireApplication, row.hire_application_id)
        if hire_row is None or hire_row.user_id != cu.user.id:
            return _jsonify({"entity": "hr_union_document", "error": "not found"}), 404

        obj_name = f"{row.id}{row.file_ext}"
        dl = (row.original_filename or "document-photo").replace('"', "")[:200]
        mt = row.mime_type or "image/jpeg"
        resp = send_stored_file(
            UploadCategory.HR_UNION,
            obj_name,
            mimetype=mt,
            download_name=dl,
        )
        if resp is None:
            return _jsonify({"entity": "hr_union_document", "error": "file not found on server"}), 404
        return resp

    @bp.delete("/hr/me/hire-wizard/union-documents/<uuid:file_id>")
    def hr_me_union_document_delete(file_id: uuid.UUID):
        cu = current_user()
        if cu.user is None:
            return _jsonify({"entity": "hr_union_document", "error": "authentication required"}), 401

        row = db.session.get(HrHireUnionDocumentFile, file_id)
        if row is None:
            return _jsonify({"entity": "hr_union_document", "error": "not found"}), 404

        hire_row = db.session.get(HrHireApplication, row.hire_application_id)
        if hire_row is None or hire_row.user_id != cu.user.id:
            return _jsonify({"entity": "hr_union_document", "error": "not found"}), 404

        if _hire_wizard_locked(hire_row):
            return _jsonify({"entity": "hr_union_document", "error": "Hire wizard is complete and locked"}), 409

        obj_name = f"{row.id}{row.file_ext}"
        kind = row.document_kind
        db.session.delete(row)
        db.session.add(
            AuditLog(
                user_id=cu.user.id,
                entity_type="hr_hire_union_document",
                entity_id=file_id,
                action="deleted",
                ip_address=_client_ip_for_audit(),
                message=f"Union document photo removed ({kind})",
            )
        )
        db.session.commit()
        delete_stored(UploadCategory.HR_UNION, obj_name)
        return _jsonify({"entity": "hr_union_document", "ok": True, "deleted": True, "id": str(file_id)})
