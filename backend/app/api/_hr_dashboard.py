"""HR dashboard API (Plan 19). Live aggregates from hr_* tables when present."""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Any

from flask import Blueprint, request
from sqlalchemy import func, or_, select

from ..extensions import db
from ..models import (
    Document,
    HrEmployeeDocument,
    HrEmployeePayScale,
    HrHireApplication,
    HrOnboardingItem,
    HrPolicyAcknowledgment,
    HrTrainingAssignment,
    Project,
    SafetyTrainingRecord,
    User,
    WageRate,
)
from ..services.hire_application_review import HIRE_STATUS_SUBMITTED, HIRE_STATUS_UNDER_REVIEW
from . import _hr_dispatch_service as hr_dispatch_svc
from ._perms import CurrentUser, current_user
from .v1 import _iso, _jsonify

# Human-readable labels for known seeded keys (fallback: format the key).
_POLICY_TITLES: dict[str, str] = {
    "handbook-2025-01": "Employee handbook (2025-01)",
    "hire-federal-i9-attestation-v1": "Federal Form I-9 — eligibility attestation (wizard)",
    "hire-federal-w4-attestation-v1": "Federal Form W-4 — withholding attestation (wizard)",
}
_COURSE_TITLES: dict[str, str] = {
    "company-orientation-video": "Company orientation (video)",
    "harassment-prevention-101": "Harassment prevention 101",
}
_SAFETY_TRAINING_LABELS: dict[str, str] = {
    "osha_10": "OSHA 10-hour",
    "osha_30": "OSHA 30-hour",
    "forklift": "Forklift operator",
    "first_aid": "First aid / CPR",
    "fall_protection": "Fall protection",
    "other": "Other / site-specific",
}


def _policy_title(version: str) -> str:
    return _POLICY_TITLES.get(version, version.replace("-", " ").title())


def _course_title(course_key: str) -> str:
    return _COURSE_TITLES.get(course_key, course_key.replace("-", " ").title())


def _safety_training_label(training_type: str) -> str:
    return _SAFETY_TRAINING_LABELS.get(training_type, training_type.replace("_", " ").title())


def _can_view_hr_employee_detail(cu: CurrentUser, target_user_id: uuid.UUID) -> bool:
    """Plan 19: hr_admin / admin / executive see others; any user may see self."""
    if cu.is_dev_admin:
        return True
    if cu.has_role("admin", "hr_admin", "executive"):
        return True
    if cu.id is not None and cu.id == target_user_id:
        return True
    return False


_ALLOWED_PAY_BASIS = frozenset({"hourly", "salary", "prevailing_reference", "other"})


def _can_edit_hr_employee_records(cu: CurrentUser) -> bool:
    """Mutations to pay scales and HR employee document links (not self-service by default)."""
    return cu.is_dev_admin or cu.has_role("admin", "hr_admin", "executive")


def _decimal_json(d: Decimal | None) -> str | None:
    if d is None:
        return None
    return format(d, "f")


def _wage_rate_summary(wr: WageRate | None) -> dict[str, Any] | None:
    if wr is None:
        return None
    return {
        "id": str(wr.id),
        "state": wr.state,
        "year": wr.year,
        "trade": wr.trade,
        "label": f"{wr.state} {wr.year} {wr.trade}",
    }


def _parse_json_uuid(data: dict[str, Any], key: str) -> uuid.UUID | None:
    raw = data.get(key)
    if raw is None or raw == "":
        return None
    try:
        return uuid.UUID(str(raw).strip())
    except (ValueError, TypeError):
        return None


def _parse_json_date(data: dict[str, Any], key: str) -> date | None:
    raw = data.get(key)
    if raw is None or raw == "":
        return None
    if isinstance(raw, date):
        return raw
    s = str(raw).strip()
    if "T" in s:
        s = s.split("T", 1)[0]
    parts = s.split("-")
    if len(parts) != 3:
        return None
    try:
        return date(int(parts[0]), int(parts[1]), int(parts[2]))
    except (ValueError, TypeError):
        return None


def _parse_json_decimal(data: dict[str, Any], key: str) -> Decimal | None:
    raw = data.get(key)
    if raw is None or raw == "":
        return None
    try:
        return Decimal(str(raw))
    except Exception:
        return None


def _serialize_pay_scale(row: HrEmployeePayScale) -> dict[str, Any]:
    wr: WageRate | None = None
    if row.wage_rate_id is not None:
        wr = db.session.get(WageRate, row.wage_rate_id)
    return {
        "id": str(row.id),
        "sort_order": row.sort_order,
        "label": row.label,
        "pay_basis": row.pay_basis,
        "hourly_rate": _decimal_json(row.hourly_rate),
        "annual_salary": _decimal_json(row.annual_salary),
        "currency": row.currency,
        "effective_from": _iso(row.effective_from),
        "effective_to": _iso(row.effective_to),
        "wage_rate_id": str(row.wage_rate_id) if row.wage_rate_id else None,
        "wage_rate": _wage_rate_summary(wr),
        "document_id": str(row.document_id) if row.document_id else None,
        "notes": row.notes,
    }


def _serialize_hr_employee_document(row: HrEmployeeDocument) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "sort_order": row.sort_order,
        "category": row.category,
        "title": row.title,
        "document_id": str(row.document_id) if row.document_id else None,
    }


def register_hr_routes(bp: Blueprint) -> None:
    @bp.get("/hr/dashboard-summary")
    def hr_dashboard_summary():
        pending_acknowledgments = int(
            db.session.scalar(
                select(func.count()).select_from(HrPolicyAcknowledgment).where(HrPolicyAcknowledgment.signed_at.is_(None))
            )
            or 0
        )
        onboarding_in_progress = int(
            db.session.scalar(
                select(func.count(func.distinct(HrOnboardingItem.user_id)))
                .select_from(HrOnboardingItem)
                .where(HrOnboardingItem.completed_at.is_(None))
            )
            or 0
        )
        expiring_safety_certs_30d = 0
        pending_approvals_hr = 0
        applications_submitted = int(
            db.session.scalar(
                select(func.count())
                .select_from(HrHireApplication)
                .where(HrHireApplication.hire_status == HIRE_STATUS_SUBMITTED)
            )
            or 0
        )
        applications_under_review = int(
            db.session.scalar(
                select(func.count())
                .select_from(HrHireApplication)
                .where(HrHireApplication.hire_status == HIRE_STATUS_UNDER_REVIEW)
            )
            or 0
        )

        sample: list[dict[str, Any]] = []
        u_rows = db.session.scalars(
            select(User)
            .where(
                or_(
                    User.id.in_(select(HrOnboardingItem.user_id)),
                    User.id.in_(select(HrPolicyAcknowledgment.user_id)),
                    User.id.in_(select(HrTrainingAssignment.user_id)),
                )
            )
            .distinct()
            .order_by(User.last_name.asc().nullslast(), User.first_name.asc().nullslast())
            .limit(15)
        ).all()
        for u in u_rows:
            uid = u.id
            open_onb = int(
                db.session.scalar(
                    select(func.count())
                    .select_from(HrOnboardingItem)
                    .where(HrOnboardingItem.user_id == uid, HrOnboardingItem.completed_at.is_(None))
                )
                or 0
            )
            pend_pol = int(
                db.session.scalar(
                    select(func.count())
                    .select_from(HrPolicyAcknowledgment)
                    .where(HrPolicyAcknowledgment.user_id == uid, HrPolicyAcknowledgment.signed_at.is_(None))
                )
                or 0
            )
            open_train = int(
                db.session.scalar(
                    select(func.count())
                    .select_from(HrTrainingAssignment)
                    .where(HrTrainingAssignment.user_id == uid, HrTrainingAssignment.completed_at.is_(None))
                )
                or 0
            )
            name = " ".join(p for p in (u.first_name, u.last_name) if p).strip() or (u.email or "")
            sample.append(
                {
                    "user_id": str(uid),
                    "name": name,
                    "email": u.email,
                    "open_onboarding_steps": open_onb,
                    "pending_policies": pend_pol,
                    "open_hr_training": open_train,
                }
            )

        hint: str | None = None
        if (
            not sample
            and pending_acknowledgments == 0
            and onboarding_in_progress == 0
        ):
            hint = (
                "No HR activity in the database yet. From the backend folder run: "
                "flask db upgrade  then  python seed_hr_employees.py"
            )

        return _jsonify(
            {
                "entity": "hr_dashboard_summary",
                "stub": False,
                "message": "Live counts from hr_* tables (safety cert snapshot still placeholder until Safety read model).",
                "counts": {
                    "pending_acknowledgments": pending_acknowledgments,
                    "onboarding_in_progress": onboarding_in_progress,
                    "expiring_safety_certs_30d": expiring_safety_certs_30d,
                    "pending_approvals_hr": pending_approvals_hr,
                    "applications_submitted": applications_submitted,
                    "applications_under_review": applications_under_review,
                },
                "sample_employees": sample,
                "hint": hint,
                "links": {
                    "safety_module": "/usis-safety.html",
                    "documents_hub": "/usis-documents-hub.html",
                },
            }
        )

    @bp.get("/hr/employees/<uuid:user_id>")
    def hr_employee_summary(user_id: uuid.UUID):
        u = db.session.get(User, user_id)
        if u is None:
            return _jsonify({"entity": "hr_employee_summary", "error": "user not found"}), 404

        cu = current_user()
        if not _can_view_hr_employee_detail(cu, user_id):
            return _jsonify(
                {
                    "entity": "hr_employee_summary",
                    "error": "forbidden",
                    "message": "Insufficient permission to view this employee.",
                }
            ), 403

        name = " ".join(p for p in (u.first_name, u.last_name) if p).strip() or (u.email or "")

        onb_rows = db.session.scalars(
            select(HrOnboardingItem)
            .where(HrOnboardingItem.user_id == user_id)
            .order_by(HrOnboardingItem.sort_order.asc(), HrOnboardingItem.title.asc())
        ).all()
        onboarding_items = [
            {
                "id": str(row.id),
                "title": row.title,
                "sort_order": row.sort_order,
                "completed_at": _iso(row.completed_at),
                "document_id": str(row.document_id) if row.document_id else None,
            }
            for row in onb_rows
        ]

        pol_rows = db.session.scalars(
            select(HrPolicyAcknowledgment)
            .where(HrPolicyAcknowledgment.user_id == user_id)
            .order_by(HrPolicyAcknowledgment.policy_version.asc())
        ).all()
        policy_acknowledgments: list[dict[str, Any]] = []
        pending_hr_approvals: list[dict[str, Any]] = []
        for row in pol_rows:
            pt = _policy_title(row.policy_version)
            signed = row.signed_at is not None
            pending_signature = not signed and row.approval_request_id is None
            pending_approval = not signed and row.approval_request_id is not None
            if pending_approval:
                pending_hr_approvals.append(
                    {
                        "policy_acknowledgment_id": str(row.id),
                        "policy_version": row.policy_version,
                        "policy_title": pt,
                        "approval_request_id": str(row.approval_request_id),
                    }
                )
            policy_acknowledgments.append(
                {
                    "id": str(row.id),
                    "policy_version": row.policy_version,
                    "policy_title": pt,
                    "signed_at": _iso(row.signed_at),
                    "document_id": None,
                    "pending_signature": pending_signature,
                    "pending_approval": pending_approval,
                    "approval_request_id": str(row.approval_request_id) if row.approval_request_id else None,
                }
            )

        tr_rows = db.session.scalars(
            select(HrTrainingAssignment)
            .where(HrTrainingAssignment.user_id == user_id)
            .order_by(HrTrainingAssignment.course_key.asc())
        ).all()
        training_assignments = [
            {
                "id": str(row.id),
                "course_key": row.course_key,
                "course_title": _course_title(row.course_key),
                "due_at": _iso(row.due_at),
                "completed_at": _iso(row.completed_at),
                "document_id": str(row.document_id) if row.document_id else None,
            }
            for row in tr_rows
        ]

        cert_rows = db.session.scalars(
            select(SafetyTrainingRecord)
            .where(SafetyTrainingRecord.user_id == user_id)
            .order_by(SafetyTrainingRecord.expires_at.asc().nullslast(), SafetyTrainingRecord.training_type.asc())
        ).all()
        regulatory_certifications = [
            {
                "id": str(row.id),
                "training_type": row.training_type,
                "training_label": _safety_training_label(row.training_type),
                "credential_number": row.credential_number,
                "issuing_body": row.issuing_body,
                "completed_at": _iso(row.completed_at),
                "expires_at": _iso(row.expires_at),
                "document_id": str(row.document_id) if row.document_id else None,
                "project_id": str(row.project_id) if row.project_id else None,
                "notes": row.notes,
            }
            for row in cert_rows
        ]

        pay_rows = db.session.scalars(
            select(HrEmployeePayScale)
            .where(HrEmployeePayScale.user_id == user_id)
            .order_by(HrEmployeePayScale.sort_order.asc(), HrEmployeePayScale.label.asc())
        ).all()
        pay_scales = [_serialize_pay_scale(row) for row in pay_rows]

        hr_doc_rows = db.session.scalars(
            select(HrEmployeeDocument)
            .where(HrEmployeeDocument.user_id == user_id)
            .order_by(HrEmployeeDocument.sort_order.asc(), HrEmployeeDocument.title.asc())
        ).all()
        hr_employee_documents = [_serialize_hr_employee_document(row) for row in hr_doc_rows]

        try:
            dispatch_body = hr_dispatch_svc.list_employee_dispatches(user_id, cu)
            employee_dispatches = dispatch_body.get("items") or []
        except hr_dispatch_svc.ApiError:
            employee_dispatches = []

        document_links: list[dict[str, str]] = []
        seen_doc: set[uuid.UUID] = set()

        def add_doc(did: uuid.UUID | None, label: str, context: str) -> None:
            if did is None or did in seen_doc:
                return
            seen_doc.add(did)
            document_links.append(
                {
                    "document_id": str(did),
                    "label": label,
                    "context": context,
                }
            )

        for row in onb_rows:
            add_doc(row.document_id, row.title, "onboarding")
        for row in tr_rows:
            add_doc(row.document_id, _course_title(row.course_key), "training")
        for row in cert_rows:
            add_doc(
                row.document_id,
                _safety_training_label(row.training_type),
                "regulatory_certification",
            )
        for row in pay_rows:
            add_doc(row.document_id, row.label, "pay_scale")
        for row in hr_doc_rows:
            add_doc(row.document_id, row.title, "hr_employee_document")

        return _jsonify(
            {
                "entity": "hr_employee_summary",
                "user": {
                    "id": str(u.id),
                    "email": u.email,
                    "first_name": u.first_name,
                    "last_name": u.last_name,
                    "name": name,
                    "phone": u.phone,
                    "is_active": u.is_active,
                    "last_login_at": _iso(u.last_login_at),
                },
                "onboarding_items": onboarding_items,
                "policy_acknowledgments": policy_acknowledgments,
                "training_assignments": training_assignments,
                "regulatory_certifications": regulatory_certifications,
                "pay_scales": pay_scales,
                "hr_employee_documents": hr_employee_documents,
                "employee_dispatches": employee_dispatches,
                "capabilities": {
                    "can_edit_hr_employee_records": _can_edit_hr_employee_records(cu),
                },
                "pending_hr_approvals": pending_hr_approvals,
                "document_links": document_links,
                "links": {
                    "safety_module": "/usis-safety.html",
                    "documents_hub": "/usis-documents-hub.html",
                },
            }
        )

    def _hr_mutation_guard(user_id: uuid.UUID) -> tuple[User | None, tuple | None]:
        """Return (user, error) where error is (response, status_code)."""
        u = db.session.get(User, user_id)
        if u is None:
            return None, (_jsonify({"entity": "hr_employee_mutation", "error": "user not found"}), 404)
        cu = current_user()
        if not _can_view_hr_employee_detail(cu, user_id):
            return None, (
                _jsonify(
                    {
                        "entity": "hr_employee_mutation",
                        "error": "forbidden",
                        "message": "Cannot view this employee.",
                    }
                ),
                403,
            )
        if not _can_edit_hr_employee_records(cu):
            return None, (
                _jsonify(
                    {
                        "entity": "hr_employee_mutation",
                        "error": "forbidden",
                        "message": "Insufficient permission to edit HR records.",
                    }
                ),
                403,
            )
        return u, None

    def _fk_document_ok(doc_id: uuid.UUID | None) -> tuple | None:
        if doc_id is None:
            return None
        if db.session.get(Document, doc_id) is None:
            return (_jsonify({"entity": "hr_employee_mutation", "error": "document not found"}), 400)
        return None

    def _fk_wage_rate_ok(wr_id: uuid.UUID | None) -> tuple | None:
        if wr_id is None:
            return None
        if db.session.get(WageRate, wr_id) is None:
            return (_jsonify({"entity": "hr_employee_mutation", "error": "wage_rate not found"}), 400)
        return None

    @bp.post("/hr/employees/<uuid:user_id>/pay-scales")
    def hr_post_pay_scale(user_id: uuid.UUID):
        u, err = _hr_mutation_guard(user_id)
        if err:
            return err[0], err[1]
        assert u is not None
        body = request.get_json(silent=True) or {}
        label = str(body.get("label") or "").strip()
        if not label:
            return _jsonify({"entity": "hr_employee_mutation", "error": "label required"}), 400
        pay_basis = str(body.get("pay_basis") or "hourly").strip().lower()
        if pay_basis not in _ALLOWED_PAY_BASIS:
            return _jsonify({"entity": "hr_employee_mutation", "error": "invalid pay_basis"}), 400
        sort_order = body.get("sort_order")
        try:
            so = int(sort_order) if sort_order is not None else 0
        except (TypeError, ValueError):
            so = 0
        doc_id = _parse_json_uuid(body, "document_id")
        wr_id = _parse_json_uuid(body, "wage_rate_id")
        e = _fk_document_ok(doc_id)
        if e:
            return e[0], e[1]
        e = _fk_wage_rate_ok(wr_id)
        if e:
            return e[0], e[1]
        notes_raw = body.get("notes")
        notes_val: str | None
        if notes_raw is None:
            notes_val = None
        else:
            notes_val = str(notes_raw).strip() or None
        row = HrEmployeePayScale(
            user_id=user_id,
            sort_order=so,
            label=label,
            pay_basis=pay_basis,
            hourly_rate=_parse_json_decimal(body, "hourly_rate"),
            annual_salary=_parse_json_decimal(body, "annual_salary"),
            currency=str(body.get("currency") or "USD").strip()[:8] or "USD",
            effective_from=_parse_json_date(body, "effective_from"),
            effective_to=_parse_json_date(body, "effective_to"),
            wage_rate_id=wr_id,
            document_id=doc_id,
            notes=notes_val,
        )
        db.session.add(row)
        db.session.commit()
        return _jsonify({"entity": "hr_employee_pay_scale", "item": _serialize_pay_scale(row)}), 201

    @bp.patch("/hr/employees/<uuid:user_id>/pay-scales/<uuid:scale_id>")
    def hr_patch_pay_scale(user_id: uuid.UUID, scale_id: uuid.UUID):
        u, err = _hr_mutation_guard(user_id)
        if err:
            return err[0], err[1]
        assert u is not None
        row = db.session.get(HrEmployeePayScale, scale_id)
        if row is None or row.user_id != user_id:
            return _jsonify({"entity": "hr_employee_mutation", "error": "not found"}), 404
        body = request.get_json(silent=True) or {}
        if "label" in body:
            lab = str(body.get("label") or "").strip()
            if not lab:
                return _jsonify({"entity": "hr_employee_mutation", "error": "label cannot be empty"}), 400
            row.label = lab
        if "pay_basis" in body:
            pb = str(body.get("pay_basis") or "").strip().lower()
            if pb not in _ALLOWED_PAY_BASIS:
                return _jsonify({"entity": "hr_employee_mutation", "error": "invalid pay_basis"}), 400
            row.pay_basis = pb
        if "sort_order" in body:
            try:
                row.sort_order = int(body["sort_order"])
            except (TypeError, ValueError):
                return _jsonify({"entity": "hr_employee_mutation", "error": "invalid sort_order"}), 400
        if "hourly_rate" in body:
            row.hourly_rate = _parse_json_decimal(body, "hourly_rate")
        if "annual_salary" in body:
            row.annual_salary = _parse_json_decimal(body, "annual_salary")
        if "currency" in body and body.get("currency") is not None:
            row.currency = str(body.get("currency")).strip()[:8] or "USD"
        if "effective_from" in body:
            row.effective_from = _parse_json_date(body, "effective_from")
        if "effective_to" in body:
            row.effective_to = _parse_json_date(body, "effective_to")
        if "wage_rate_id" in body:
            raw_wr = body.get("wage_rate_id")
            if raw_wr in (None, ""):
                row.wage_rate_id = None
            else:
                wr_id = _parse_json_uuid(body, "wage_rate_id")
                e = _fk_wage_rate_ok(wr_id)
                if e:
                    return e[0], e[1]
                row.wage_rate_id = wr_id
        if "document_id" in body:
            raw_doc = body.get("document_id")
            if raw_doc in (None, ""):
                row.document_id = None
            else:
                doc_id = _parse_json_uuid(body, "document_id")
                e = _fk_document_ok(doc_id)
                if e:
                    return e[0], e[1]
                row.document_id = doc_id
        if "notes" in body:
            n = body.get("notes")
            row.notes = str(n).strip() if n is not None and str(n).strip() else None
        db.session.commit()
        return _jsonify({"entity": "hr_employee_pay_scale", "item": _serialize_pay_scale(row)})

    @bp.delete("/hr/employees/<uuid:user_id>/pay-scales/<uuid:scale_id>")
    def hr_delete_pay_scale(user_id: uuid.UUID, scale_id: uuid.UUID):
        u, err = _hr_mutation_guard(user_id)
        if err:
            return err[0], err[1]
        assert u is not None
        row = db.session.get(HrEmployeePayScale, scale_id)
        if row is None or row.user_id != user_id:
            return _jsonify({"entity": "hr_employee_mutation", "error": "not found"}), 404
        db.session.delete(row)
        db.session.commit()
        return _jsonify({"entity": "hr_employee_pay_scale", "deleted": True})

    @bp.post("/hr/employees/<uuid:user_id>/employee-documents")
    def hr_post_employee_document(user_id: uuid.UUID):
        u, err = _hr_mutation_guard(user_id)
        if err:
            return err[0], err[1]
        assert u is not None
        body = request.get_json(silent=True) or {}
        title = str(body.get("title") or "").strip()
        if not title:
            return _jsonify({"entity": "hr_employee_mutation", "error": "title required"}), 400
        category = str(body.get("category") or "other").strip()[:64] or "other"
        sort_order = body.get("sort_order")
        try:
            so = int(sort_order) if sort_order is not None else 0
        except (TypeError, ValueError):
            so = 0
        doc_id = _parse_json_uuid(body, "document_id")
        e = _fk_document_ok(doc_id)
        if e:
            return e[0], e[1]
        row = HrEmployeeDocument(
            user_id=user_id,
            category=category,
            title=title,
            sort_order=so,
            document_id=doc_id,
        )
        db.session.add(row)
        db.session.commit()
        return _jsonify({"entity": "hr_employee_document", "item": _serialize_hr_employee_document(row)}), 201

    @bp.patch("/hr/employees/<uuid:user_id>/employee-documents/<uuid:doc_row_id>")
    def hr_patch_employee_document(user_id: uuid.UUID, doc_row_id: uuid.UUID):
        u, err = _hr_mutation_guard(user_id)
        if err:
            return err[0], err[1]
        assert u is not None
        row = db.session.get(HrEmployeeDocument, doc_row_id)
        if row is None or row.user_id != user_id:
            return _jsonify({"entity": "hr_employee_mutation", "error": "not found"}), 404
        body = request.get_json(silent=True) or {}
        if "title" in body:
            t = str(body.get("title") or "").strip()
            if not t:
                return _jsonify({"entity": "hr_employee_mutation", "error": "title cannot be empty"}), 400
            row.title = t
        if "category" in body and body.get("category") is not None:
            row.category = str(body.get("category")).strip()[:64] or "other"
        if "sort_order" in body:
            try:
                row.sort_order = int(body["sort_order"])
            except (TypeError, ValueError):
                return _jsonify({"entity": "hr_employee_mutation", "error": "invalid sort_order"}), 400
        if "document_id" in body:
            raw_doc = body.get("document_id")
            if raw_doc in (None, ""):
                row.document_id = None
            else:
                doc_id = _parse_json_uuid(body, "document_id")
                e = _fk_document_ok(doc_id)
                if e:
                    return e[0], e[1]
                row.document_id = doc_id
        db.session.commit()
        return _jsonify({"entity": "hr_employee_document", "item": _serialize_hr_employee_document(row)})

    @bp.delete("/hr/employees/<uuid:user_id>/employee-documents/<uuid:doc_row_id>")
    def hr_delete_employee_document(user_id: uuid.UUID, doc_row_id: uuid.UUID):
        u, err = _hr_mutation_guard(user_id)
        if err:
            return err[0], err[1]
        assert u is not None
        row = db.session.get(HrEmployeeDocument, doc_row_id)
        if row is None or row.user_id != user_id:
            return _jsonify({"entity": "hr_employee_mutation", "error": "not found"}), 404
        db.session.delete(row)
        db.session.commit()
        return _jsonify({"entity": "hr_employee_document", "deleted": True})

    @bp.get("/hr/employees/<uuid:user_id>/dispatches")
    def hr_list_employee_dispatches(user_id: uuid.UUID):
        try:
            return _jsonify(hr_dispatch_svc.list_employee_dispatches(user_id, current_user()))
        except hr_dispatch_svc.ApiError as exc:
            return _jsonify({"entity": "hr_employee_dispatches", "error": exc.message}), exc.status

    @bp.post("/hr/employees/<uuid:user_id>/dispatches")
    def hr_create_employee_dispatch(user_id: uuid.UUID):
        u = db.session.get(User, user_id)
        if u is None:
            return _jsonify({"entity": "hr_employee_dispatch", "error": "user not found"}), 404
        body = request.get_json(silent=True) or {}
        try:
            return _jsonify(hr_dispatch_svc.create_employee_dispatch(user_id, body, current_user())), 201
        except hr_dispatch_svc.ApiError as exc:
            return _jsonify({"entity": "hr_employee_dispatch", "error": exc.message}), exc.status

    @bp.get("/hr/projects-picker")
    def hr_projects_picker():
        """Lightweight project list for dispatch / assignment forms."""
        from ..permissions.project_scope import project_access_clause

        cu = current_user()
        if not _can_edit_hr_employee_records(cu) and not cu.is_dev_admin:
            if not cu.has_role(
                "admin",
                "superuser",
                "standard",
                "project_manager",
                "superintendent",
            ):
                return _jsonify({"entity": "hr_projects_picker", "error": "forbidden"}), 403
        rows = db.session.scalars(
            select(Project)
            .where(project_access_clause(cu))
            .order_by(Project.name.asc())
            .limit(500)
        ).all()
        return _jsonify(
            {
                "entity": "hr_projects_picker",
                "items": [{"id": str(p.id), "name": p.name, "number": p.number} for p in rows],
            }
        )
