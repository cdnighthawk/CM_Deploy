"""Job offer letter generation, acceptance, and auto-hire for standard applicants."""
from __future__ import annotations

import io
import json
import os
import uuid
from datetime import date, datetime
from typing import Any

from flask import current_app, render_template

from sqlalchemy import select

from ..extensions import db
from ..models import Document, HrEmployeeDocument, HrHireApplication, Role, User
from ..permissions.applicant import APPLICANT_ROLE_CODE
from ..services.hire_application_review import (
    HIRE_STATUS_HIRED,
    HIRE_STATUS_OFFER_ACCEPTED,
    HIRE_STATUS_OFFER_EXTENDED,
    HireReviewError,
    can_hr_hire_after_offer_accepted,
    utc_now,
)
from ..services.hire_path import HIRE_PATH_STANDARD, is_standard_path
from ..services.hr_hired_employee import provision_hired_employee_hr_records
from ..services.object_storage import UploadCategory, save_upload, send_stored_file
from ..api import _admin_users_service as admin_users_svc


def _company_name() -> str:
    raw = (current_app.config.get("DOCUMENT_PRINT_COMPANY_NAME") or os.environ.get("DOCUMENT_PRINT_COMPANY_NAME") or "").strip()
    return raw or "DOCOM, INC."


def _employee_name(user: User, hire_row: HrHireApplication | None = None) -> str:
    parts = [user.first_name, user.last_name]
    name = " ".join(p for p in parts if p).strip()
    if name:
        return name
    payload = None
    if hire_row and hire_row.application_json:
        try:
            payload = json.loads(hire_row.application_json)
        except json.JSONDecodeError:
            payload = None
    if isinstance(payload, dict):
        fn = str(payload.get("first_name") or "").strip()
        ln = str(payload.get("last_name") or "").strip()
        combo = " ".join(p for p in (fn, ln) if p).strip()
        if combo:
            return combo
    return user.email or "Applicant"


def _fmt_date(d: date | None) -> str:
    if d is None:
        return "—"
    return d.strftime("%B %d, %Y")


def _fmt_dt(dt: datetime | None) -> str:
    if dt is None:
        return "—"
    return dt.strftime("%B %d, %Y at %I:%M %p %Z").strip()


def render_job_offer_html(
    *,
    user: User,
    hire_row: HrHireApplication,
    accepted: bool = False,
) -> str:
    return render_template(
        "documents/hire_job_offer.html",
        company_name=_company_name(),
        employee_name=_employee_name(user, hire_row),
        employee_email=user.email,
        offer_date=_fmt_date(hire_row.offer_sent_at.date() if hire_row.offer_sent_at else utc_now().date()),
        position=hire_row.offer_position or "—",
        pay_description=hire_row.offer_pay_description or "—",
        start_date=_fmt_date(hire_row.offer_start_date),
        accepted_at=_fmt_dt(hire_row.offer_accepted_at) if accepted and hire_row.offer_accepted_at else None,
    )


def offer_storage_name(document_id: uuid.UUID) -> str:
    return f"{document_id}.html"


def _upsert_employee_offer_document(*, user_id: uuid.UUID, document_id: uuid.UUID) -> None:
    title = "Job offer letter"
    row = db.session.scalar(
        select(HrEmployeeDocument).where(
            HrEmployeeDocument.user_id == user_id,
            HrEmployeeDocument.category == "offer_letter",
        )
    )
    if row is None:
        db.session.add(
            HrEmployeeDocument(
                user_id=user_id,
                category="offer_letter",
                title=title,
                document_id=document_id,
            )
        )
    else:
        row.document_id = document_id
        row.title = title


def persist_job_offer_document(
    *,
    hire_row: HrHireApplication,
    user: User,
    html: str,
    uploaded_by_user_id: uuid.UUID | None,
) -> Document:
    doc = db.session.get(Document, hire_row.offer_document_id) if hire_row.offer_document_id else None
    if doc is None:
        doc = Document(
            document_type="other",
            title="Job offer letter",
            uploaded_by_user_id=uploaded_by_user_id,
            mime_type="text/html",
            original_filename="job-offer.html",
        )
        db.session.add(doc)
        db.session.flush()

    payload = html.encode("utf-8")
    size = save_upload(UploadCategory.HR_HIRE_OFFER, offer_storage_name(doc.id), io.BytesIO(payload))
    doc.title = "Job offer letter"
    doc.mime_type = "text/html"
    doc.original_filename = "job-offer.html"
    doc.file_size_bytes = size
    hire_row.offer_document_id = doc.id
    return doc


def load_offer_html(hire_row: HrHireApplication) -> str | None:
    if hire_row.offer_document_id is None:
        return None
    doc = db.session.get(Document, hire_row.offer_document_id)
    if doc is None:
        return None
    resp = send_stored_file(
        UploadCategory.HR_HIRE_OFFER,
        offer_storage_name(doc.id),
        mimetype=doc.mime_type or "text/html",
        download_name=doc.original_filename or "job-offer.html",
    )
    if resp is None:
        return None
    return resp.get_data(as_text=True)


def parse_pending_role_ids(raw: str | None) -> list[uuid.UUID]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    out: list[uuid.UUID] = []
    for item in data:
        try:
            out.append(uuid.UUID(str(item)))
        except (ValueError, AttributeError):
            continue
    return out


def encode_pending_role_ids(role_ids: list[uuid.UUID]) -> str:
    return json.dumps([str(r) for r in role_ids])


def validate_staff_role_ids(role_ids: list[uuid.UUID]) -> list[Role]:
    if not role_ids:
        raise HireReviewError("role_ids must include at least one staff role when sending an offer", 400)
    roles = db.session.scalars(select(Role).where(Role.id.in_(role_ids))).all()
    if len(roles) != len(set(role_ids)):
        raise HireReviewError("one or more role_ids are invalid", 400)
    if any(r.code == APPLICANT_ROLE_CODE for r in roles):
        raise HireReviewError("hired users cannot keep the applicant role", 400)
    return roles


def apply_staff_roles(user: User, role_ids: list[uuid.UUID]) -> None:
    roles = validate_staff_role_ids(role_ids)
    admin_users_svc._set_roles(user, [r.id for r in roles])


def extend_job_offer(
    *,
    hire_row: HrHireApplication,
    user: User,
    hr_user_id: uuid.UUID,
    position: str,
    pay_description: str,
    start_date: date,
    role_ids: list[uuid.UUID],
    review_notes: str | None = None,
) -> Document:
    if hire_row.hire_path == "union_dispatch":
        raise HireReviewError("job offers apply only to standard hire path applicants", 400)
    if not hire_row.hire_path:
        hire_row.hire_path = HIRE_PATH_STANDARD
    if (hire_row.hire_status or "") not in ("submitted", "under_review"):
        raise HireReviewError("application must be submitted or under review before sending an offer", 409)

    hire_row.offer_position = position.strip()[:500]
    hire_row.offer_pay_description = pay_description.strip()
    hire_row.offer_start_date = start_date
    hire_row.offer_pending_role_ids = encode_pending_role_ids(role_ids)
    hire_row.offer_sent_at = utc_now()
    hire_row.offer_accepted_at = None
    hire_row.hire_status = HIRE_STATUS_OFFER_EXTENDED
    if review_notes:
        hire_row.review_notes = review_notes.strip()
    hire_row.reviewed_by_user_id = hr_user_id
    hire_row.reviewed_at = utc_now()

    html = render_job_offer_html(user=user, hire_row=hire_row, accepted=False)
    return persist_job_offer_document(
        hire_row=hire_row,
        user=user,
        html=html,
        uploaded_by_user_id=hr_user_id,
    )


def accept_job_offer(*, hire_row: HrHireApplication, user: User) -> None:
    if hire_row.hire_path != HIRE_PATH_STANDARD:
        raise HireReviewError("no job offer to accept for this application path", 400)
    if hire_row.hire_status != HIRE_STATUS_OFFER_EXTENDED:
        raise HireReviewError("no pending job offer to accept", 409)
    if hire_row.offer_document_id is None:
        raise HireReviewError("offer letter is not available", 500)

    now = utc_now()
    hire_row.offer_accepted_at = now
    hire_row.hire_status = HIRE_STATUS_OFFER_ACCEPTED

    html = render_job_offer_html(user=user, hire_row=hire_row, accepted=True)
    persist_job_offer_document(
        hire_row=hire_row,
        user=user,
        html=html,
        uploaded_by_user_id=user.id,
    )


def try_auto_hire_after_onboarding(*, hire_row: HrHireApplication, user: User) -> bool:
    """Promote standard-path applicants to hired after offer accept + I-9 + W-4."""
    if not can_hr_hire_after_offer_accepted(hire_row):
        return False

    role_ids = parse_pending_role_ids(hire_row.offer_pending_role_ids)
    complete_standard_path_hire(hire_row=hire_row, user=user, role_ids=role_ids)
    return True


def complete_standard_path_hire(
    *,
    hire_row: HrHireApplication,
    user: User,
    role_ids: list[uuid.UUID],
    reviewed_by_user_id: uuid.UUID | None = None,
    review_notes: str | None = None,
) -> None:
    """Finalize hire for standard-path applicants (auto or HR-triggered)."""
    apply_staff_roles(user, role_ids)
    now = utc_now()
    hire_row.hire_status = HIRE_STATUS_HIRED
    hire_row.reviewed_at = now
    if reviewed_by_user_id is not None:
        hire_row.reviewed_by_user_id = reviewed_by_user_id
    if review_notes:
        hire_row.review_notes = review_notes.strip()
    provision_hired_employee_hr_records(user.id)
    if hire_row.offer_document_id is not None:
        _upsert_employee_offer_document(user_id=user.id, document_id=hire_row.offer_document_id)
