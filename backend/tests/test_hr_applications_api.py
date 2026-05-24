"""HR staff review queue for hire applications."""
from __future__ import annotations

import json
import uuid
from unittest.mock import patch

import pytest
from sqlalchemy import select

from app.api._perms import CurrentUser
from app.extensions import db
from app.models import HrHireApplication, Role, User, UserRole
from app.permissions.applicant import APPLICANT_ROLE_CODE, assign_applicant_role


def _hr_admin_cu() -> CurrentUser:
    return CurrentUser(user=None, role_codes=frozenset(["hr_admin"]), granular=frozenset(), is_dev_admin=False)


def _hr_manager_cu() -> CurrentUser:
    return CurrentUser(user=None, role_codes=frozenset(["hr_manager"]), granular=frozenset(), is_dev_admin=False)


def _read_only_cu() -> CurrentUser:
    return CurrentUser(user=None, role_codes=frozenset(["read_only"]), granular=frozenset(), is_dev_admin=False)


def _user_admin_cu() -> CurrentUser:
    return CurrentUser(
        user=None,
        role_codes=frozenset(),
        granular=frozenset(),
        module_access={"user_admin": "admin"},
        is_dev_admin=False,
    )


@pytest.fixture
def applicant_user(flask_app):
    with flask_app.app_context():
        email = f"applicant.test.{uuid.uuid4().hex[:8]}@usis.local"
        u = User(email=email, first_name="Apply", last_name="Tester", is_active=True)
        db.session.add(u)
        db.session.flush()
        assign_applicant_role(u)
        hire = HrHireApplication(
            user_id=u.id,
            application_json=json.dumps({"position_applying_for": "Laborer", "city": "Denver"}),
            hire_status="submitted",
        )
        db.session.add(hire)
        db.session.commit()
        uid = u.id
        yield {"user_id": str(uid), "email": email}
        u2 = db.session.get(User, uid)
        if u2 is not None:
            db.session.delete(u2)
            db.session.commit()


def test_hr_applications_list_forbidden(client):
    with patch("app.api._hr_applications.current_user", return_value=_read_only_cu()):
        r = client.get("/api/v1/hr/applications")
    assert r.status_code == 403


def test_hr_applications_list_ok(client, applicant_user):
    with patch("app.api._hr_applications.current_user", return_value=_hr_admin_cu()):
        r = client.get("/api/v1/hr/applications?hire_status=submitted")
    assert r.status_code == 200
    data = r.get_json()
    assert data.get("entity") == "hr_applications_list"
    ids = [row["user_id"] for row in data.get("items") or []]
    assert applicant_user["user_id"] in ids
    assert data.get("capabilities", {}).get("can_delete_applicants") is True
    applicant_row = next(row for row in data["items"] if row["user_id"] == applicant_user["user_id"])
    assert applicant_row.get("can_delete") is True


def test_hr_applications_list_ok_for_hr_manager(client, applicant_user):
    with patch("app.api._hr_applications.current_user", return_value=_hr_manager_cu()):
        r = client.get("/api/v1/hr/applications?hire_status=submitted")
    assert r.status_code == 200
    ids = [row["user_id"] for row in r.get_json().get("items") or []]
    assert applicant_user["user_id"] in ids


def test_hr_application_detail_can_send_offer_without_hire_path(client, applicant_user):
    uid = applicant_user["user_id"]
    with patch("app.api._hr_applications.current_user", return_value=_hr_admin_cu()):
        r = client.get(f"/api/v1/hr/applications/{uid}")
    assert r.status_code == 200
    assert r.get_json()["capabilities"]["can_send_offer"] is True


def test_hr_applications_list_excludes_hired_by_default(client, flask_app):
    with flask_app.app_context():
        email = f"hired.archived.{uuid.uuid4().hex[:8]}@usis.local"
        u = User(email=email, first_name="Hired", last_name="Person", is_active=True)
        db.session.add(u)
        db.session.flush()
        assign_applicant_role(u)
        hire = HrHireApplication(
            user_id=u.id,
            application_json=json.dumps({"position_applying_for": "Laborer"}),
            hire_status="hired",
        )
        db.session.add(hire)
        db.session.commit()
        uid = str(u.id)
        try:
            with patch("app.api._hr_applications.current_user", return_value=_hr_admin_cu()):
                active = client.get("/api/v1/hr/applications")
                hired_only = client.get("/api/v1/hr/applications?hire_status=hired")
            assert active.status_code == 200
            active_ids = [row["user_id"] for row in active.get_json().get("items") or []]
            assert uid not in active_ids
            assert hired_only.status_code == 200
            hired_ids = [row["user_id"] for row in hired_only.get_json().get("items") or []]
            assert uid in hired_ids
            hired_row = next(row for row in hired_only.get_json()["items"] if row["user_id"] == uid)
            assert hired_row.get("employee_profile_url")
        finally:
            u2 = db.session.get(User, uuid.UUID(uid))
            if u2 is not None:
                db.session.delete(u2)
                db.session.commit()


def test_hr_application_detail_ok(client, applicant_user):
    uid = applicant_user["user_id"]
    with patch("app.api._hr_applications.current_user", return_value=_hr_admin_cu()):
        r = client.get(f"/api/v1/hr/applications/{uid}")
    assert r.status_code == 200
    data = r.get_json()
    assert data.get("entity") == "hr_application_detail"
    assert data["application"]["payload"]["position_applying_for"] == "Laborer"
    assert data["review"]["hire_status"] == "submitted"


def test_hr_application_status_under_review(client, applicant_user):
    uid = applicant_user["user_id"]
    with patch("app.api._hr_applications.current_user", return_value=_hr_admin_cu()):
        r = client.patch(
            f"/api/v1/hr/applications/{uid}/status",
            json={"status": "under_review"},
        )
    assert r.status_code == 200
    assert r.get_json()["review"]["hire_status"] == "under_review"


def test_hr_application_reject_requires_notes(client, applicant_user):
    uid = applicant_user["user_id"]
    with patch("app.api._hr_applications.current_user", return_value=_hr_admin_cu()):
        r = client.patch(
            f"/api/v1/hr/applications/{uid}/status",
            json={"status": "rejected"},
        )
    assert r.status_code == 400
    assert "review_notes" in (r.get_json().get("error") or "")


def test_hr_application_hire_requires_role_ids(client, applicant_user):
    uid = applicant_user["user_id"]
    with patch("app.api._hr_applications.current_user", return_value=_hr_admin_cu()):
        r = client.patch(
            f"/api/v1/hr/applications/{uid}/status",
            json={"status": "hired"},
        )
    assert r.status_code == 400
    assert "role_ids" in (r.get_json().get("error") or "")


def test_hr_application_hire_ok(client, applicant_user, flask_app):
    uid = uuid.UUID(applicant_user["user_id"])
    with flask_app.app_context():
        staff_role = db.session.scalar(select(Role).where(Role.code == "project_manager"))
        assert staff_role is not None
        role_id = str(staff_role.id)
    with patch("app.api._hr_applications.current_user", return_value=_hr_admin_cu()):
        r = client.patch(
            f"/api/v1/hr/applications/{uid}/status",
            json={"status": "hired", "role_ids": [role_id], "review_notes": "Welcome aboard"},
        )
    assert r.status_code == 200
    assert r.get_json()["review"]["hire_status"] == "hired"
    with flask_app.app_context():
        u = db.session.get(User, uid)
        codes = {ur.role.code for ur in u.roles if ur.role}
        assert "applicant" not in codes
        assert "project_manager" in codes


def test_hr_application_delete_applicant_only(client, flask_app):
    with flask_app.app_context():
        email = f"applicant.delete.{uuid.uuid4().hex[:8]}@usis.local"
        u = User(email=email, first_name="Delete", last_name="Me", is_active=True)
        db.session.add(u)
        db.session.flush()
        assign_applicant_role(u)
        db.session.add(
            HrHireApplication(
                user_id=u.id,
                application_json=json.dumps({"position_applying_for": "Temp"}),
                hire_status="rejected",
            )
        )
        db.session.commit()
        uid = str(u.id)
    with patch("app.api._hr_applications.current_user", return_value=_user_admin_cu()):
        r = client.delete(
            f"/api/v1/hr/applications/{uid}",
            json={"confirm": True, "reason": "Test cleanup"},
        )
    assert r.status_code == 200
    assert r.get_json().get("deleted") is True


def test_hr_application_delete_rejects_staff_user(client, staff_user_for_hr_tests):
    staff_id = staff_user_for_hr_tests["user_id"]
    with patch("app.api._hr_applications.current_user", return_value=_hr_admin_cu()):
        r = client.delete(
            f"/api/v1/hr/applications/{staff_id}",
            json={"confirm": True, "reason": "Should fail"},
        )
    assert r.status_code == 403


def test_applicant_wizard_blocked_when_rejected(client, applicant_user):
    uid = applicant_user["user_id"]
    hdr = {"X-Usis-User-Id": uid}
    with patch("app.api._hr_applications.current_user", return_value=_hr_admin_cu()):
        client.patch(
            f"/api/v1/hr/applications/{uid}/status",
            json={"status": "rejected", "review_notes": "Not a fit at this time"},
        )
    r = client.post(
        "/api/v1/hr/me/hire-application",
        headers=hdr,
        json={"application": {"position_applying_for": "Updated"}},
    )
    assert r.status_code == 409
    assert "application closed" in (r.get_json().get("error") or "")


def test_hr_dashboard_summary_includes_application_counts(client, applicant_user):
    r = client.get("/api/v1/hr/dashboard-summary")
    assert r.status_code == 200
    counts = r.get_json().get("counts") or {}
    assert "applications_submitted" in counts
    assert "applications_under_review" in counts
    assert counts["applications_submitted"] >= 1
