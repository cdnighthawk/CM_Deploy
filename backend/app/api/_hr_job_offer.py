"""Applicant hire path selection and job offer acceptance."""
from __future__ import annotations

import uuid

from flask import Blueprint, Response, request
from sqlalchemy import select

from ..extensions import db
from ..models import AuditLog, HrHireApplication, User
from ..services.hire_application_review import (
    HIRE_STATUS_OFFER_ACCEPTED,
    HIRE_STATUS_OFFER_EXTENDED,
    HIRE_STATUS_HIRED,
    HireReviewError,
    serialize_offer_block,
)
from ..services.hire_path import HIRE_PATHS, normalize_hire_path
from ..services.hr_job_offer import accept_job_offer, load_offer_html, render_job_offer_html
from ._hr_hire_wizard import _get_or_create_hire_row, _wizard_mutable_guard
from ._perms import current_user
from .v1 import _jsonify


def register_hr_job_offer_routes(bp: Blueprint) -> None:
    @bp.post("/hr/me/hire-wizard/path")
    def hr_me_hire_wizard_path():
        cu = current_user()
        if cu.user is None:
            return _jsonify({"entity": "hr_hire_path", "error": "authentication required"}), 401

        body = request.get_json(silent=True) or {}
        if not isinstance(body, dict):
            return _jsonify({"entity": "hr_hire_path", "error": "JSON body required"}), 400

        path = normalize_hire_path(str(body.get("hire_path") or ""))
        if path is None:
            return _jsonify(
                {
                    "entity": "hr_hire_path",
                    "error": f"hire_path must be one of: {', '.join(sorted(HIRE_PATHS))}",
                }
            ), 400

        uid = cu.user.id
        hire_row = _get_or_create_hire_row(uid)
        blocked = _wizard_mutable_guard(hire_row)
        if blocked is not None:
            return blocked

        if hire_row.hire_path:
            return _jsonify({"entity": "hr_hire_path", "error": "hire path already selected"}), 409

        hire_row.hire_path = path
        db.session.commit()
        return _jsonify({"entity": "hr_hire_path", "ok": True, "hire_path": path})

    @bp.get("/hr/me/job-offer/preview")
    def hr_me_job_offer_preview():
        cu = current_user()
        if cu.user is None:
            return _jsonify({"entity": "hr_job_offer_preview", "error": "authentication required"}), 401

        uid = cu.user.id
        hire_row = db.session.scalar(select(HrHireApplication).where(HrHireApplication.user_id == uid))
        if hire_row is None or hire_row.offer_document_id is None:
            return _jsonify({"entity": "hr_job_offer_preview", "error": "no job offer to preview"}), 404

        if hire_row.hire_status not in (HIRE_STATUS_OFFER_EXTENDED, HIRE_STATUS_OFFER_ACCEPTED, HIRE_STATUS_HIRED):
            return _jsonify({"entity": "hr_job_offer_preview", "error": "job offer not available"}), 404

        u = cu.user
        assert u is not None
        html = load_offer_html(hire_row)
        if html is None:
            html = render_job_offer_html(
                user=u,
                hire_row=hire_row,
                accepted=hire_row.offer_accepted_at is not None,
            )
        return Response(html, mimetype="text/html")

    @bp.post("/hr/me/job-offer/accept")
    def hr_me_job_offer_accept():
        cu = current_user()
        if cu.user is None:
            return _jsonify({"entity": "hr_job_offer_accept", "error": "authentication required"}), 401

        uid = cu.user.id
        hire_row = db.session.scalar(select(HrHireApplication).where(HrHireApplication.user_id == uid))
        if hire_row is None:
            return _jsonify({"entity": "hr_job_offer_accept", "error": "hire application not found"}), 404

        u = cu.user
        assert u is not None
        try:
            accept_job_offer(hire_row=hire_row, user=u)
        except HireReviewError as exc:
            return _jsonify({"entity": "hr_job_offer_accept", "error": exc.message}), exc.status

        db.session.add(
            AuditLog(
                user_id=uid,
                entity_type="hr_hire_offer",
                entity_id=hire_row.id,
                action="offer_accepted",
                message="Applicant accepted job offer",
            )
        )
        db.session.commit()
        return _jsonify(
            {
                "entity": "hr_job_offer_accept",
                "ok": True,
                "hire_status": hire_row.hire_status,
                "offer": serialize_offer_block(hire_row),
            }
        )
