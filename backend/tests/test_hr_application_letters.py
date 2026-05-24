"""Tests for hire application approval/rejection letter emails."""
from __future__ import annotations

import json
import uuid
from unittest.mock import patch

import pytest

from app.extensions import db
from app.models import HrHireApplication, User
from app.permissions.applicant import assign_applicant_role
from app.services.hire_path import HIRE_PATH_UNION_DISPATCH
from app.services.hr_application_letters import (
    approval_letter_plain_text,
    rejection_letter_plain_text,
    render_approval_letter_html,
    render_rejection_letter_html,
)


@pytest.fixture
def hire_applicant(flask_app):
    with flask_app.app_context():
        email = f"letters.test.{uuid.uuid4().hex[:8]}@usis.local"
        u = User(email=email, first_name="Letter", last_name="Tester", is_active=True)
        db.session.add(u)
        db.session.flush()
        assign_applicant_role(u)
        hire = HrHireApplication(
            user_id=u.id,
            application_json=json.dumps({"position_applying_for": "Electrician", "city": "Denver"}),
            hire_status="submitted",
            hire_path=HIRE_PATH_UNION_DISPATCH,
        )
        db.session.add(hire)
        db.session.commit()
        uid = u.id
        hire_id = hire.id
        yield {"user": u, "hire": hire, "email": email}
        row = db.session.get(HrHireApplication, hire_id)
        if row is not None:
            db.session.delete(row)
        u2 = db.session.get(User, uid)
        if u2 is not None:
            db.session.delete(u2)
        db.session.commit()


def test_rejection_letter_includes_notes(flask_app, hire_applicant):
    with flask_app.app_context():
        user = db.session.get(User, hire_applicant["user"].id)
        hire = db.session.get(HrHireApplication, hire_applicant["hire"].id)
        hire.review_notes = "We selected another candidate for this opening."
        hire.reviewed_at = hire_applicant["hire"].updated_at

        plain = rejection_letter_plain_text(user=user, hire_row=hire)
        html = render_rejection_letter_html(user=user, hire_row=hire)

        assert "Electrician" in plain
        assert "another candidate" in plain
        assert "another candidate" in html
        assert hire_applicant["email"] in html


def test_approval_letter_includes_login_link(flask_app, hire_applicant):
    with flask_app.app_context():
        user = db.session.get(User, hire_applicant["user"].id)
        hire = db.session.get(HrHireApplication, hire_applicant["hire"].id)
        hire.hire_status = "hired"
        hire.reviewed_at = hire_applicant["hire"].updated_at

        login_url = "https://www.usiscm.com/page-login.html"
        plain = approval_letter_plain_text(user=user, hire_row=hire, login_url=login_url)
        html = render_approval_letter_html(user=user, hire_row=hire, login_url=login_url)

        assert "approved" in plain.lower()
        assert "Electrician" in plain
        assert login_url in plain
        assert login_url in html


def test_hr_application_reject_sends_letter(client, hire_applicant):
    from app.api._perms import CurrentUser

    cu = CurrentUser(user=None, role_codes=frozenset(["hr_admin"]), granular=frozenset(), is_dev_admin=False)
    uid = str(hire_applicant["user"].id)
    with patch("app.api._hr_applications.current_user", return_value=cu), patch(
        "app.api._hr_applications.send_application_rejection_letter_email"
    ) as send_mail:
        send_mail.return_value = {"sent": True, "dry_run": False, "error": None}
        r = client.patch(
            f"/api/v1/hr/applications/{uid}/status",
            json={"status": "rejected", "review_notes": "Position filled."},
        )
    assert r.status_code == 200
    send_mail.assert_called_once()


def test_hr_application_hire_sends_approval_letter(client, hire_applicant, flask_app):
    from app.api._perms import CurrentUser
    from sqlalchemy import select
    from app.models import Role

    uid = hire_applicant["user"].id
    with flask_app.app_context():
        staff_role = db.session.scalar(select(Role).where(Role.code == "project_manager"))
        assert staff_role is not None
        role_id = str(staff_role.id)

    cu = CurrentUser(user=None, role_codes=frozenset(["hr_admin"]), granular=frozenset(), is_dev_admin=False)
    with patch("app.api._hr_applications.current_user", return_value=cu), patch(
        "app.api._hr_applications.send_application_approval_letter_email"
    ) as send_mail:
        send_mail.return_value = {"sent": True, "dry_run": False, "error": None}
        r = client.patch(
            f"/api/v1/hr/applications/{uid}/status",
            json={"status": "hired", "role_ids": [role_id], "review_notes": "Welcome aboard"},
        )
    assert r.status_code == 200
    send_mail.assert_called_once()
