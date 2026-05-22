"""Hire path selection, job offer flow, and I-9/W-4 gating."""
from __future__ import annotations

import json
import uuid
from datetime import date, datetime, timezone
from unittest.mock import patch

import pytest
from sqlalchemy import select

from app.api._perms import CurrentUser
from app.extensions import db
from app.models import HrHireApplication, Role, User
from app.permissions.applicant import assign_applicant_role


def _applicant_cu(user: User) -> CurrentUser:
    return CurrentUser(
        user=user,
        role_codes=frozenset(["applicant"]),
        granular=frozenset(),
        is_dev_admin=False,
    )


def _hr_admin_cu() -> CurrentUser:
    return CurrentUser(user=None, role_codes=frozenset(["hr_admin"]), granular=frozenset(), is_dev_admin=False)


@pytest.fixture
def standard_applicant(flask_app):
    with flask_app.app_context():
        email = f"std.applicant.{uuid.uuid4().hex[:8]}@usis.local"
        u = User(email=email, first_name="Std", last_name="Apply", is_active=True)
        db.session.add(u)
        db.session.flush()
        assign_applicant_role(u)
        hire = HrHireApplication(
            user_id=u.id,
            hire_path="standard",
            application_json=json.dumps({"position_applying_for": "Carpenter"}),
            submitted_at=datetime.now(timezone.utc),
            hire_status="submitted",
        )
        db.session.add(hire)
        db.session.commit()
        uid = u.id
        yield {"user_id": str(uid), "user": u, "email": email}
        u2 = db.session.get(User, uid)
        if u2 is not None:
            db.session.delete(u2)
            db.session.commit()


def test_hire_path_selection(client, flask_app):
    with flask_app.app_context():
        email = f"path.pick.{uuid.uuid4().hex[:8]}@usis.local"
        u = User(email=email, first_name="Path", last_name="Pick", is_active=True)
        db.session.add(u)
        db.session.flush()
        assign_applicant_role(u)
        db.session.commit()
        uid = u.id
    with patch("app.api._hr_job_offer.current_user", return_value=_applicant_cu(db.session.get(User, uid))):
        r = client.post("/api/v1/hr/me/hire-wizard/path", json={"hire_path": "standard"})
    assert r.status_code == 200
    assert r.get_json().get("hire_path") == "standard"
    with flask_app.app_context():
        hire = db.session.scalar(select(HrHireApplication).where(HrHireApplication.user_id == uid))
        assert hire is not None
        assert hire.hire_path == "standard"
        db.session.delete(db.session.get(User, uid))
        db.session.commit()


def test_standard_i9_blocked_until_offer_accepted(client, standard_applicant, flask_app):
    uid = standard_applicant["user_id"]
    with flask_app.app_context():
        user = db.session.get(User, uuid.UUID(uid))
        cu = _applicant_cu(user)
    with patch("app.api._hr_hire_wizard.current_user", return_value=cu):
        r = client.post("/api/v1/hr/me/i9-section1", json={"section1": {"last_name": "Apply"}})
    assert r.status_code == 403
    assert "not available" in (r.get_json().get("error") or "").lower()


def test_send_offer_and_accept_unlocks_i9(client, standard_applicant, flask_app):
    uid = uuid.UUID(standard_applicant["user_id"])
    with flask_app.app_context():
        user = db.session.get(User, uid)

    with flask_app.app_context():
        staff_role = db.session.scalar(select(Role).where(Role.code == "project_manager"))
        assert staff_role is not None
        role_id = str(staff_role.id)

    with patch("app.api._hr_applications.send_job_offer_email", return_value={"ok": True}), patch(
        "app.api._hr_applications.current_user", return_value=_hr_admin_cu()
    ):
        r = client.post(
            f"/api/v1/hr/applications/{uid}/offer",
            json={
                "position": "Carpenter",
                "pay_description": "$32/hr",
                "start_date": date.today().isoformat(),
                "role_ids": [role_id],
            },
        )
    assert r.status_code == 200
    assert r.get_json()["review"]["hire_status"] == "offer_extended"

    with patch("app.api._hr_job_offer.current_user", return_value=_applicant_cu(user)):
        r2 = client.post("/api/v1/hr/me/job-offer/accept")
    assert r2.status_code == 200
    assert r2.get_json()["hire_status"] == "offer_accepted"

    with patch("app.api._hr_hire_wizard.current_user", return_value=_applicant_cu(user)):
        r3 = client.get("/api/v1/hr/me/hire-wizard")
    assert r3.status_code == 200
    w = r3.get_json()
    assert w.get("hire_path") == "standard"
    assert w.get("offer", {}).get("accepted_at")


def test_standard_manual_hire_blocked(client, standard_applicant, flask_app):
    uid = standard_applicant["user_id"]
    with flask_app.app_context():
        staff_role = db.session.scalar(select(Role).where(Role.code == "project_manager"))
        role_id = str(staff_role.id)
    with patch("app.api._hr_applications.current_user", return_value=_hr_admin_cu()):
        r = client.patch(
            f"/api/v1/hr/applications/{uid}/status",
            json={"status": "hired", "role_ids": [role_id]},
        )
    assert r.status_code == 400
    assert "automatically" in (r.get_json().get("error") or "").lower()
