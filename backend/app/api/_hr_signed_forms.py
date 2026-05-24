"""Serve signed I-9 / W-4 HTML documents and signature images."""
from __future__ import annotations

import base64
import uuid

from flask import Blueprint, Response
from sqlalchemy import select

from ..extensions import db
from ..models import Document, HrHireApplication
from ..services.hr_hire_signed_forms import signed_form_storage_name
from ..services.object_storage import UploadCategory, send_stored_file
from ._hr_applications import _forbidden, _require_hr_reviewer
from ._perms import current_user
from .v1 import _jsonify

_SIGNED_FORM_KINDS = frozenset({"i9", "w4"})


def _can_view_signed_forms(user_id: uuid.UUID) -> bool:
    cu = current_user()
    if cu.user is None:
        return False
    if cu.user.id == user_id:
        return True
    return _require_hr_reviewer(cu)


def _hire_row_for_user(user_id: uuid.UUID) -> HrHireApplication | None:
    return db.session.scalar(select(HrHireApplication).where(HrHireApplication.user_id == user_id))


def _signature_png_response(data_url: str | None) -> Response:
    if not data_url:
        return Response("not found", status=404)
    raw = data_url.strip()
    if raw.startswith("data:"):
        parts = raw.split(",", 1)
        if len(parts) != 2:
            return Response("invalid signature", status=400)
        raw = parts[1]
    try:
        payload = base64.b64decode(raw)
    except Exception:
        return Response("invalid signature", status=400)
    return Response(payload, mimetype="image/png")


def register_hr_signed_form_routes(bp: Blueprint) -> None:
    @bp.get("/hr/applications/<uuid:user_id>/signed-forms/<kind>")
    def hr_application_signed_form(user_id: uuid.UUID, kind: str):
        if not _can_view_signed_forms(user_id):
            return _forbidden("hr_signed_form")

        kind_norm = (kind or "").strip().lower()
        if kind_norm not in _SIGNED_FORM_KINDS:
            return _jsonify({"entity": "hr_signed_form", "error": "invalid form kind"}), 400

        hire_row = _hire_row_for_user(user_id)
        if hire_row is None:
            return _jsonify({"entity": "hr_signed_form", "error": "not found"}), 404

        doc_id = hire_row.i9_signed_document_id if kind_norm == "i9" else hire_row.w4_signed_document_id
        if doc_id is None:
            return _jsonify({"entity": "hr_signed_form", "error": "signed document not available"}), 404

        doc = db.session.get(Document, doc_id)
        if doc is None:
            return _jsonify({"entity": "hr_signed_form", "error": "not found"}), 404

        category = UploadCategory.HR_I9 if kind_norm == "i9" else UploadCategory.HR_W4
        resp = send_stored_file(
            category,
            signed_form_storage_name(doc.id, mime_type=doc.mime_type),
            mimetype=doc.mime_type or "application/octet-stream",
            download_name=doc.original_filename or f"{kind_norm}-signed.pdf",
        )
        if resp is None:
            return _jsonify({"entity": "hr_signed_form", "error": "file not found"}), 404
        return resp

    @bp.get("/hr/applications/<uuid:user_id>/signed-forms/<kind>/signature")
    def hr_application_signed_form_signature(user_id: uuid.UUID, kind: str):
        if not _can_view_signed_forms(user_id):
            return _forbidden("hr_signed_form")

        kind_norm = (kind or "").strip().lower()
        if kind_norm not in _SIGNED_FORM_KINDS:
            return _jsonify({"entity": "hr_signed_form", "error": "invalid form kind"}), 400

        hire_row = _hire_row_for_user(user_id)
        if hire_row is None:
            return _jsonify({"entity": "hr_signed_form", "error": "not found"}), 404

        sig = hire_row.i9_signature_png if kind_norm == "i9" else hire_row.w4_signature_png
        if not sig:
            return _jsonify({"entity": "hr_signed_form", "error": "signature not available"}), 404
        return _signature_png_response(sig)

    @bp.get("/hr/me/signed-forms/<kind>")
    def hr_me_signed_form(kind: str):
        cu = current_user()
        if cu.user is None:
            return _jsonify({"entity": "hr_signed_form", "error": "authentication required"}), 401
        return hr_application_signed_form(cu.user.id, kind)

    @bp.get("/hr/me/signed-forms/<kind>/signature")
    def hr_me_signed_form_signature(kind: str):
        cu = current_user()
        if cu.user is None:
            return _jsonify({"entity": "hr_signed_form", "error": "authentication required"}), 401
        return hr_application_signed_form_signature(cu.user.id, kind)
