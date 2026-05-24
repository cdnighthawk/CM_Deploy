"""Staff HR review queue for hire wizard applications."""
from __future__ import annotations

import uuid
from typing import Any

from flask import Blueprint, request
from sqlalchemy import func, or_, select
from sqlalchemy.orm import selectinload

from ..extensions import db
from ..models import (
    AuditLog,
    HrHireApplication,
    HrHireI9DocumentFile,
    HrHireUnionDocumentFile,
    HrHireW4DocumentFile,
    Role,
    User,
    UserRole,
)
from ..permissions.applicant import APPLICANT_ROLE_CODE, is_applicant_only_user
from ..services.hire_application_review import (
    HIRE_STATUS_HIRED,
    HIRE_STATUS_REJECTED,
    HIRE_STATUS_UNDER_REVIEW,
    TERMINAL_HIRE_STATUSES,
    HireReviewError,
    allowed_hr_status_transition,
    application_position,
    can_hr_manual_hire,
    can_hr_hire_after_offer_accepted,
    can_hr_send_offer,
    show_hire_after_offer_panel,
    parse_application_payload,
    purge_hire_application_files,
    serialize_hire_status,
    serialize_offer_block,
    utc_now,
)
from ..services.hr_hired_employee import provision_hired_employee_hr_records
from ..services.hr_job_offer import (
    complete_standard_path_hire,
    extend_job_offer,
    parse_pending_role_ids,
    render_job_offer_html,
)
from ._notifications import (
    send_application_approval_letter_email,
    send_application_rejection_letter_email,
    send_job_offer_email,
)
from ..services.hr_i9_crypto import decrypt_section1
from ..services.hr_w4_crypto import decrypt_w4
from ..services.hr_hire_signed_forms import signed_form_staff_url
from ..services.object_storage import UploadCategory, send_stored_file
from . import _admin_users_service as admin_users_svc
from ._hr_dashboard import _can_review_hire_applications
from ._hr_hire_wizard import (
    _build_hire_tasks,
    _i9_status_block,
    _w4_status_block,
)
from ._hr_i9_documents import list_i9_documents_for_hire
from ._hr_union_documents import list_union_documents_for_hire
from ._hr_w4_documents import list_w4_documents_for_hire
from ._perms import CurrentUser, can_manage_directory_users, current_user
from .v1 import _iso, _jsonify

_DOC_KINDS = frozenset({"union_card", "union_dispatch", "i9", "w4"})


def _require_hr_reviewer(cu: CurrentUser) -> bool:
    return _can_review_hire_applications(cu)


def _can_delete_applicant(cu: CurrentUser) -> bool:
    return _require_hr_reviewer(cu) or can_manage_directory_users(cu)


def _forbidden(entity: str, message: str = "Insufficient permission."):
    return _jsonify({"entity": entity, "error": "forbidden", "message": message}), 403


def _client_ip_for_audit() -> str | None:
    xff = request.headers.get("X-Forwarded-For")
    if xff:
        first = xff.split(",")[0].strip()
        if first:
            return first[:64]
    if request.remote_addr:
        return str(request.remote_addr)[:64]
    return None


def _user_display(u: User) -> str:
    return " ".join(p for p in (u.first_name, u.last_name) if p).strip() or (u.email or "")


def _staff_doc_url(user_id: uuid.UUID, kind: str, file_id: uuid.UUID) -> str:
    return f"/api/v1/hr/applications/{user_id}/documents/{kind}/{file_id}/file"


def _with_staff_doc_urls(user_id: uuid.UUID, docs: list[dict], kind: str) -> list[dict]:
    out: list[dict] = []
    for d in docs:
        item = dict(d)
        fid = item.get("id")
        if fid:
            item["staff_file_url"] = _staff_doc_url(user_id, kind, uuid.UUID(str(fid)))
        out.append(item)
    return out


def _serialize_list_item(hire_row: HrHireApplication, cu: CurrentUser) -> dict[str, Any]:
    u = hire_row.user
    review = serialize_hire_status(hire_row)
    status = review.get("hire_status") or "in_progress"
    uid = str(hire_row.user_id)
    item: dict[str, Any] = {
        "user_id": uid,
        "name": _user_display(u) if u else "",
        "email": u.email if u else None,
        "position": application_position(hire_row),
        "hire_path": hire_row.hire_path,
        "submitted_for_review_at": review.get("submitted_for_review_at"),
        "hire_status": status,
        "progress_percent": review.get("progress_percent"),
        "can_delete": _can_delete_applicant(cu) and is_applicant_only_user(u),
    }
    if status == HIRE_STATUS_HIRED:
        item["employee_profile_url"] = f"/usis-hr-employee.html?id={uid}"
    return item


def _load_hire_detail(user_id: uuid.UUID) -> HrHireApplication | None:
    return db.session.scalar(
        select(HrHireApplication)
        .where(HrHireApplication.user_id == user_id)
        .options(
            selectinload(HrHireApplication.user).selectinload(User.roles).selectinload(UserRole.role),
            selectinload(HrHireApplication.i9_document_files),
            selectinload(HrHireApplication.w4_document_files),
            selectinload(HrHireApplication.union_document_files),
        )
    )


def _staff_hire_roles() -> list[dict[str, Any]]:
    rows = db.session.scalars(select(Role).order_by(Role.code.asc())).all()
    return [
        {"id": str(r.id), "code": r.code, "name": r.name}
        for r in rows
        if r.code and r.code != APPLICANT_ROLE_CODE
    ]


def _validate_staff_role_ids(role_ids: list[uuid.UUID]) -> list[Role]:
    if not role_ids:
        raise HireReviewError("role_ids must include at least one staff role when hiring", 400)
    roles = db.session.scalars(select(Role).where(Role.id.in_(role_ids))).all()
    if len(roles) != len(set(role_ids)):
        raise HireReviewError("one or more role_ids are invalid", 400)
    if any(r.code == APPLICANT_ROLE_CODE for r in roles):
        raise HireReviewError("hired users cannot keep the applicant role", 400)
    if len(roles) != len(role_ids):
        raise HireReviewError("one or more role_ids are invalid", 400)
    return roles


def _apply_status_patch(
    cu: CurrentUser,
    hire_row: HrHireApplication,
    *,
    new_status: str,
    review_notes: str | None,
    role_ids: list[uuid.UUID] | None,
) -> None:
    current = hire_row.hire_status or "in_progress"
    if not allowed_hr_status_transition(current, new_status):
        raise HireReviewError(f"cannot transition from {current!r} to {new_status!r}", 409)

    notes = (review_notes or "").strip() or None
    if new_status == HIRE_STATUS_REJECTED and not notes:
        raise HireReviewError("review_notes is required when rejecting an application", 400)

    if new_status == HIRE_STATUS_HIRED:
        u = hire_row.user
        if u is None:
            raise HireReviewError("user not found for hire application", 404)
        if can_hr_manual_hire(hire_row):
            ids = role_ids or []
            roles = _validate_staff_role_ids(ids)
            admin_users_svc._set_roles(u, [r.id for r in roles])
            provision_hired_employee_hr_records(u.id)
        elif can_hr_hire_after_offer_accepted(hire_row):
            ids = role_ids or parse_pending_role_ids(hire_row.offer_pending_role_ids)
            if not ids:
                raise HireReviewError(
                    "role_ids must include at least one staff role when hiring (or resend the job offer with roles)",
                    400,
                )
            complete_standard_path_hire(
                hire_row=hire_row,
                user=u,
                role_ids=ids,
                reviewed_by_user_id=cu.user.id if cu.user else None,
                review_notes=notes,
            )
        else:
            raise HireReviewError(
                "hire requires a signed job offer acceptance and completed Form I-9 and W-4, "
                "or use union dispatch manual hire before an offer",
                400,
            )

    hire_row.hire_status = new_status
    if new_status in (HIRE_STATUS_HIRED, HIRE_STATUS_REJECTED):
        hire_row.review_notes = notes
        hire_row.reviewed_by_user_id = cu.user.id if cu.user else None
        hire_row.reviewed_at = utc_now()
    elif new_status == HIRE_STATUS_UNDER_REVIEW and notes:
        hire_row.review_notes = notes


def register_hr_application_routes(bp: Blueprint) -> None:
    @bp.get("/hr/applications")
    def hr_applications_list():
        cu = current_user()
        if not _require_hr_reviewer(cu):
            return _forbidden("hr_applications_list")

        status_raw = (request.args.get("hire_status") or "").strip().lower()
        show_all_statuses = status_raw == "all"
        status_filter = status_raw if status_raw and status_raw != "all" else None
        q = (request.args.get("q") or request.args.get("search") or "").strip().lower()
        try:
            limit = max(1, min(int(request.args.get("limit", 50)), 200))
        except (TypeError, ValueError):
            limit = 50
        try:
            offset = max(0, int(request.args.get("offset", 0)))
        except (TypeError, ValueError):
            offset = 0

        stmt = (
            select(HrHireApplication)
            .join(User, HrHireApplication.user_id == User.id)
            .options(
                selectinload(HrHireApplication.user).selectinload(User.roles).selectinload(UserRole.role)
            )
        )
        count_stmt = select(func.count()).select_from(HrHireApplication).join(
            User, HrHireApplication.user_id == User.id
        )

        if not show_all_statuses:
            if status_filter:
                stmt = stmt.where(HrHireApplication.hire_status == status_filter)
                count_stmt = count_stmt.where(HrHireApplication.hire_status == status_filter)
            else:
                stmt = stmt.where(HrHireApplication.hire_status.notin_(TERMINAL_HIRE_STATUSES))
                count_stmt = count_stmt.where(HrHireApplication.hire_status.notin_(TERMINAL_HIRE_STATUSES))

        if q:
            filt = or_(
                func.lower(User.email).contains(q),
                func.lower(func.coalesce(User.first_name, "")).contains(q),
                func.lower(func.coalesce(User.last_name, "")).contains(q),
                func.lower(func.coalesce(HrHireApplication.application_json, "")).contains(q),
            )
            stmt = stmt.where(filt)
            count_stmt = count_stmt.where(filt)

        total = int(db.session.scalar(count_stmt) or 0)
        rows = db.session.scalars(
            stmt.order_by(
                HrHireApplication.submitted_for_review_at.desc().nullslast(),
                HrHireApplication.updated_at.desc(),
            )
            .offset(offset)
            .limit(limit)
        ).all()

        return _jsonify(
            {
                "entity": "hr_applications_list",
                "items": [_serialize_list_item(r, cu) for r in rows],
                "total": total,
                "limit": limit,
                "offset": offset,
                "capabilities": {
                    "can_delete_applicants": _can_delete_applicant(cu),
                },
            }
        )

    @bp.get("/hr/applications/<uuid:user_id>")
    def hr_application_detail(user_id: uuid.UUID):
        cu = current_user()
        if not _require_hr_reviewer(cu):
            return _forbidden("hr_application_detail")

        hire_row = _load_hire_detail(user_id)
        if hire_row is None:
            return _jsonify({"entity": "hr_application_detail", "error": "not found"}), 404

        u = hire_row.user
        app_payload = parse_application_payload(hire_row)
        hire_status = hire_row.hire_status or "in_progress"
        if hire_status == HIRE_STATUS_HIRED and u is not None and not is_applicant_only_user(u):
            uid_str = str(user_id)
            return _jsonify(
                {
                    "entity": "hr_application_detail",
                    "redirect": "hr_employee_profile",
                    "employee_profile_url": f"/usis-hr-employee.html?id={uid_str}",
                    "user": {
                        "id": uid_str,
                        "email": u.email,
                        "first_name": u.first_name,
                        "last_name": u.last_name,
                    },
                    "review": serialize_hire_status(hire_row),
                    "message": "This person has been hired. Open their HR employee profile.",
                }
            )

        i9_st = _i9_status_block(hire_row)
        w4_st = _w4_status_block(hire_row)
        steps_block = {
            "application": {
                "completed": hire_row.submitted_at is not None,
            },
            "i9": {"signed_at": _iso(hire_row.i9_signed_at)},
            "w4": {"signed_at": _iso(hire_row.w4_signed_at)},
        }
        checklist = _build_hire_tasks(
            hire_row=hire_row,
            steps=steps_block,
            i9_status=i9_st["status"],
            w4_status=w4_st["status"],
        )

        i9_draft = None
        if hire_row.i9_section1_json_encrypted:
            try:
                i9_draft = decrypt_section1(hire_row.i9_section1_json_encrypted)
            except Exception:
                i9_draft = None

        w4_draft = None
        if hire_row.w4_json_encrypted:
            try:
                w4_draft = decrypt_w4(hire_row.w4_json_encrypted)
            except Exception:
                w4_draft = None

        union_docs = list_union_documents_for_hire(hire_row)
        union_by_kind: dict[str, list[dict]] = {"union_card": [], "union_dispatch": []}
        for doc in union_docs:
            kind = doc.get("document_kind")
            if kind in union_by_kind:
                union_by_kind[kind].append(doc)

        return _jsonify(
            {
                "entity": "hr_application_detail",
                "user": {
                    "id": str(u.id) if u else str(user_id),
                    "email": u.email if u else None,
                    "first_name": u.first_name if u else None,
                    "last_name": u.last_name if u else None,
                    "phone": u.phone if u else None,
                    "is_active": u.is_active if u else None,
                    "roles": [
                        {"id": str(ur.role.id), "code": ur.role.code, "name": ur.role.name}
                        for ur in (u.roles or ())
                        if ur.role is not None
                    ]
                    if u
                    else [],
                },
                "application": {
                    "submitted_at": _iso(hire_row.submitted_at),
                    "payload": app_payload,
                },
                "hire_path": hire_row.hire_path,
                "offer": serialize_offer_block(hire_row),
                "review": serialize_hire_status(hire_row),
                "checklist": checklist,
                "i9": {
                    **i9_st,
                    "draft": i9_draft,
                    "documents": _with_staff_doc_urls(user_id, list_i9_documents_for_hire(hire_row), "i9"),
                    "signature_present": bool(hire_row.i9_signature_png),
                    "signature_url": signed_form_staff_url(user_id, "i9") + "/signature"
                    if hire_row.i9_signature_png
                    else None,
                    "signed_at": _iso(hire_row.i9_signed_at),
                    "signed_document_url": signed_form_staff_url(user_id, "i9")
                    if hire_row.i9_signed_document_id
                    else None,
                    "employee_document_id": str(hire_row.i9_signed_document_id)
                    if hire_row.i9_signed_document_id
                    else None,
                },
                "w4": {
                    **w4_st,
                    "draft": w4_draft,
                    "documents": _with_staff_doc_urls(user_id, list_w4_documents_for_hire(hire_row), "w4"),
                    "signature_present": bool(hire_row.w4_signature_png),
                    "signature_url": signed_form_staff_url(user_id, "w4") + "/signature"
                    if hire_row.w4_signature_png
                    else None,
                    "signed_at": _iso(hire_row.w4_signed_at),
                    "signed_document_url": signed_form_staff_url(user_id, "w4")
                    if hire_row.w4_signed_document_id
                    else None,
                    "employee_document_id": str(hire_row.w4_signed_document_id)
                    if hire_row.w4_signed_document_id
                    else None,
                },
                "union_documents": {
                    "union_card": _with_staff_doc_urls(user_id, union_by_kind["union_card"], "union_card"),
                    "union_dispatch": _with_staff_doc_urls(user_id, union_by_kind["union_dispatch"], "union_dispatch"),
                },
                "staff_roles": _staff_hire_roles(),
                "capabilities": {
                    "can_review": _require_hr_reviewer(cu),
                    "can_delete_applicant": _can_delete_applicant(cu) and is_applicant_only_user(u),
                    "can_send_offer": can_hr_send_offer(hire_row),
                    "can_manual_hire": can_hr_manual_hire(hire_row),
                    "show_hire_after_offer_panel": show_hire_after_offer_panel(hire_row),
                    "can_hire_after_offer": can_hr_hire_after_offer_accepted(hire_row),
                    "employee_profile_url": f"/usis-hr-employee.html?id={user_id}"
                    if (hire_row.hire_status or "") == HIRE_STATUS_HIRED and u and not is_applicant_only_user(u)
                    else None,
                },
                "hire_readiness": {
                    "offer_accepted": hire_row.offer_accepted_at is not None,
                    "i9_signed": hire_row.i9_signed_at is not None,
                    "w4_signed": hire_row.w4_signed_at is not None,
                },
            }
        )

    @bp.get("/hr/applications/<uuid:user_id>/documents/<kind>/<uuid:file_id>/file")
    def hr_application_document_file(user_id: uuid.UUID, kind: str, file_id: uuid.UUID):
        cu = current_user()
        if not _require_hr_reviewer(cu):
            return _forbidden("hr_application_document")

        kind_norm = (kind or "").strip().lower()
        if kind_norm not in _DOC_KINDS:
            return _jsonify({"entity": "hr_application_document", "error": "invalid document kind"}), 400

        hire_row = db.session.scalar(select(HrHireApplication).where(HrHireApplication.user_id == user_id))
        if hire_row is None:
            return _jsonify({"entity": "hr_application_document", "error": "not found"}), 404

        row: HrHireI9DocumentFile | HrHireW4DocumentFile | HrHireUnionDocumentFile | None
        category: UploadCategory
        if kind_norm == "i9":
            row = db.session.get(HrHireI9DocumentFile, file_id)
            category = UploadCategory.HR_I9
        elif kind_norm == "w4":
            row = db.session.get(HrHireW4DocumentFile, file_id)
            category = UploadCategory.HR_W4
        else:
            row = db.session.get(HrHireUnionDocumentFile, file_id)
            category = UploadCategory.HR_UNION

        if row is None or row.hire_application_id != hire_row.id:
            return _jsonify({"entity": "hr_application_document", "error": "not found"}), 404
        if kind_norm in ("union_card", "union_dispatch") and getattr(row, "document_kind", None) != kind_norm:
            return _jsonify({"entity": "hr_application_document", "error": "not found"}), 404

        obj_name = f"{row.id}{row.file_ext}"
        dl = (row.original_filename or "document-photo").replace('"', "")[:200]
        mt = row.mime_type or "image/jpeg"
        resp = send_stored_file(category, obj_name, mimetype=mt, download_name=dl)
        if resp is None:
            return _jsonify({"entity": "hr_application_document", "error": "file not found on server"}), 404
        return resp

    @bp.post("/hr/applications/<uuid:user_id>/offer")
    def hr_application_send_offer(user_id: uuid.UUID):
        cu = current_user()
        if not _require_hr_reviewer(cu):
            return _forbidden("hr_application_offer")

        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return _jsonify({"entity": "hr_application_offer", "error": "JSON body required"}), 400

        position = str(data.get("position") or "").strip()
        pay_description = str(data.get("pay_description") or data.get("pay") or "").strip()
        start_raw = str(data.get("start_date") or "").strip()
        if not position or not pay_description or not start_raw:
            return _jsonify(
                {
                    "entity": "hr_application_offer",
                    "error": "position, pay_description, and start_date are required",
                }
            ), 400

        try:
            from datetime import date as date_cls

            start_date = date_cls.fromisoformat(start_raw)
        except ValueError:
            return _jsonify({"entity": "hr_application_offer", "error": "start_date must be YYYY-MM-DD"}), 400

        hire_row = _load_hire_detail(user_id)
        if hire_row is None:
            return _jsonify({"entity": "hr_application_offer", "error": "not found"}), 404

        u = hire_row.user
        if u is None:
            return _jsonify({"entity": "hr_application_offer", "error": "user not found"}), 404

        try:
            role_ids = admin_users_svc._parse_role_ids(data.get("role_ids"))
        except admin_users_svc.ApiError as exc:
            return _jsonify({"entity": "hr_application_offer", "error": exc.message}), exc.status

        assert cu.user is not None
        try:
            extend_job_offer(
                hire_row=hire_row,
                user=u,
                hr_user_id=cu.user.id,
                position=position,
                pay_description=pay_description,
                start_date=start_date,
                role_ids=role_ids,
                review_notes=data.get("review_notes"),
            )
        except HireReviewError as exc:
            return _jsonify({"entity": "hr_application_offer", "error": exc.message}), exc.status

        offer_html = render_job_offer_html(user=u, hire_row=hire_row, accepted=False)
        send_job_offer_email(
            to=u.email or "",
            applicant_name=_user_display(u),
            html_body=offer_html,
        )

        db.session.add(
            AuditLog(
                user_id=cu.user.id,
                entity_type="hr_hire_application",
                entity_id=hire_row.id,
                action="offer_extended",
                ip_address=_client_ip_for_audit(),
                message=f"Job offer sent to user {user_id}",
            )
        )
        db.session.commit()
        db.session.refresh(hire_row)

        return _jsonify(
            {
                "entity": "hr_application_offer",
                "ok": True,
                "review": serialize_hire_status(hire_row),
                "offer": serialize_offer_block(hire_row),
            }
        )

    @bp.patch("/hr/applications/<uuid:user_id>/status")
    def hr_application_status_patch(user_id: uuid.UUID):
        cu = current_user()
        if not _require_hr_reviewer(cu):
            return _forbidden("hr_application_status")

        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return _jsonify({"entity": "hr_application_status", "error": "JSON body required"}), 400

        new_status = str(data.get("status") or "").strip().lower()
        if not new_status:
            return _jsonify({"entity": "hr_application_status", "error": "status is required"}), 400

        hire_row = _load_hire_detail(user_id)
        if hire_row is None:
            return _jsonify({"entity": "hr_application_status", "error": "not found"}), 404

        role_ids: list[uuid.UUID] | None = None
        if data.get("role_ids") is not None:
            try:
                role_ids = admin_users_svc._parse_role_ids(data.get("role_ids"))
            except admin_users_svc.ApiError as exc:
                return _jsonify({"entity": "hr_application_status", "error": exc.message}), exc.status

        try:
            _apply_status_patch(
                cu,
                hire_row,
                new_status=new_status,
                review_notes=data.get("review_notes"),
                role_ids=role_ids,
            )
        except HireReviewError as exc:
            return _jsonify({"entity": "hr_application_status", "error": exc.message}), exc.status

        db.session.add(
            AuditLog(
                user_id=cu.user.id if cu.user else None,
                entity_type="hr_hire_application",
                entity_id=hire_row.id,
                action=f"status_{new_status}",
                ip_address=_client_ip_for_audit(),
                message=f"HR application status set to {new_status} for user {user_id}",
            )
        )
        db.session.commit()
        db.session.refresh(hire_row)

        u = hire_row.user
        if u is not None:
            if new_status == HIRE_STATUS_REJECTED:
                send_application_rejection_letter_email(user=u, hire_row=hire_row)
            elif new_status == HIRE_STATUS_HIRED:
                send_application_approval_letter_email(user=u, hire_row=hire_row)

        return _jsonify(
            {
                "entity": "hr_application_status",
                "ok": True,
                "review": serialize_hire_status(hire_row),
            }
        )

    @bp.delete("/hr/applications/<uuid:user_id>")
    def hr_application_delete(user_id: uuid.UUID):
        cu = current_user()
        if not _can_delete_applicant(cu):
            return _forbidden("hr_application_delete")

        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return _jsonify({"entity": "hr_application_delete", "error": "JSON body required"}), 400
        if data.get("confirm") is not True:
            return _jsonify({"entity": "hr_application_delete", "error": "confirm must be true"}), 400
        reason = str(data.get("reason") or "").strip()
        if not reason:
            return _jsonify({"entity": "hr_application_delete", "error": "reason is required"}), 400

        u = db.session.scalar(
            select(User)
            .where(User.id == user_id)
            .options(selectinload(User.roles).selectinload(UserRole.role))
        )
        if u is None:
            return _jsonify({"entity": "hr_application_delete", "error": "not found"}), 404
        if not is_applicant_only_user(u):
            return _jsonify(
                {
                    "entity": "hr_application_delete",
                    "error": "forbidden",
                    "message": "Only applicant-only accounts may be deleted through this endpoint.",
                }
            ), 403

        hire_row = _load_hire_detail(user_id)
        if hire_row is not None:
            purge_hire_application_files(hire_row)

        email = u.email
        db.session.add(
            AuditLog(
                user_id=cu.user.id if cu.user else None,
                entity_type="hr_hire_application",
                entity_id=hire_row.id if hire_row else user_id,
                action="deleted_applicant",
                ip_address=_client_ip_for_audit(),
                message=f"Deleted applicant {email}: {reason[:500]}",
            )
        )
        db.session.delete(u)
        db.session.commit()

        return _jsonify(
            {
                "entity": "hr_application_delete",
                "ok": True,
                "deleted": True,
                "user_id": str(user_id),
            }
        )
