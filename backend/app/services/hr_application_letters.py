"""Formal hire application approval and rejection letter content."""
from __future__ import annotations

import json
import os
from datetime import date, datetime

from flask import current_app, render_template

from ..models import HrHireApplication, User
from .hire_application_review import application_position, utc_now


def _company_name() -> str:
    raw = (
        current_app.config.get("DOCUMENT_PRINT_COMPANY_NAME")
        or os.environ.get("DOCUMENT_PRINT_COMPANY_NAME")
        or ""
    ).strip()
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


def _letter_date(when: datetime | None = None) -> str:
    return _fmt_date((when or utc_now()).date())


def render_rejection_letter_html(*, user: User, hire_row: HrHireApplication) -> str:
    return render_template(
        "documents/hire_application_rejection.html",
        company_name=_company_name(),
        employee_name=_employee_name(user, hire_row),
        employee_email=user.email,
        letter_date=_letter_date(hire_row.reviewed_at),
        position=application_position(hire_row) or "the position you applied for",
        message=(hire_row.review_notes or "").strip(),
    )


def render_approval_letter_html(*, user: User, hire_row: HrHireApplication, login_url: str) -> str:
    position = (hire_row.offer_position or application_position(hire_row) or "").strip() or None
    start_date = _fmt_date(hire_row.offer_start_date) if hire_row.offer_start_date else None
    return render_template(
        "documents/hire_application_approval.html",
        company_name=_company_name(),
        employee_name=_employee_name(user, hire_row),
        employee_email=user.email,
        letter_date=_letter_date(hire_row.reviewed_at),
        position=position,
        start_date=start_date,
        login_url=login_url,
    )


def rejection_letter_plain_text(*, user: User, hire_row: HrHireApplication) -> str:
    display = _employee_name(user, hire_row)
    position = application_position(hire_row) or "the position you applied for"
    company = _company_name()
    lines = [
        f"Dear {display},",
        "",
        f"Thank you for your interest in employment with {company} and for applying for {position}.",
        "",
        "After careful review, we have decided not to move forward with your application at this time.",
        "",
    ]
    message = (hire_row.review_notes or "").strip()
    if message:
        lines.extend([message, ""])
    lines.extend(
        [
            "We appreciate the time you invested in your application and wish you success in your job search.",
            "",
            f"Sincerely,",
            f"{company} Human Resources",
        ]
    )
    return "\n".join(lines)


def approval_letter_plain_text(*, user: User, hire_row: HrHireApplication, login_url: str) -> str:
    display = _employee_name(user, hire_row)
    company = _company_name()
    position = (hire_row.offer_position or application_position(hire_row) or "").strip()
    lines = [
        f"Dear {display},",
        "",
        f"We are pleased to inform you that your application has been approved and you are now part of the {company} team",
    ]
    if position:
        lines[-1] += f" as {position}."
    else:
        lines[-1] += "."
    if hire_row.offer_start_date:
        lines.extend(["", f"Anticipated start date: {_fmt_date(hire_row.offer_start_date)}"])
    lines.extend(
        [
            "",
            "Please sign in to the USIS portal using the link below. If you previously applied as an applicant, "
            "your account has been updated with staff access.",
            "",
            login_url,
            "",
            "Your HR team will follow up with any remaining onboarding steps.",
            "",
            "Sincerely,",
            f"{company} Human Resources",
        ]
    )
    return "\n".join(lines)


def rejection_letter_subject() -> str:
    return f"Update on your application — {_company_name()}"


def approval_letter_subject() -> str:
    return f"Welcome to {_company_name()} — your application is approved"
