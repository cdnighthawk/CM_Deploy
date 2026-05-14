"""HR dashboard summary (Plan 19) backed by hr_* tables."""
from __future__ import annotations

import uuid
from unittest.mock import patch

from app.api._perms import CurrentUser


def test_hr_dashboard_summary(client):
    r = client.get("/api/v1/hr/dashboard-summary")
    assert r.status_code == 200
    data = r.get_json()
    assert data.get("entity") == "hr_dashboard_summary"
    assert data.get("stub") is False
    assert "counts" in data
    c = data["counts"]
    assert "pending_acknowledgments" in c
    assert "onboarding_in_progress" in c
    assert "expiring_safety_certs_30d" in c
    assert "pending_approvals_hr" in c
    assert isinstance(c["pending_acknowledgments"], int)
    assert isinstance(c["onboarding_in_progress"], int)
    assert "sample_employees" in data
    assert isinstance(data["sample_employees"], list)
    assert "hint" in data


def test_hr_employee_summary_demo_user(client):
    r = client.get("/api/v1/hr/employees/a1700000-0000-4000-8000-000000000001")
    assert r.status_code == 200
    data = r.get_json()
    assert data.get("entity") == "hr_employee_summary"
    u = data.get("user", {})
    assert u.get("email") == "hr.demo.employee@usis.local"
    assert "phone" in u
    assert "last_login_at" in u
    assert isinstance(data.get("onboarding_items"), list)
    assert isinstance(data.get("policy_acknowledgments"), list)
    assert isinstance(data.get("training_assignments"), list)
    assert isinstance(data.get("pending_hr_approvals"), list)
    assert isinstance(data.get("document_links"), list)
    assert isinstance(data.get("regulatory_certifications"), list)
    assert any(c.get("training_type") == "forklift" for c in data["regulatory_certifications"])
    assert isinstance(data.get("pay_scales"), list)
    assert isinstance(data.get("hr_employee_documents"), list)
    assert any(p.get("label") == "Field journeyman (standard)" for p in data["pay_scales"])
    assert data.get("capabilities", {}).get("can_edit_hr_employee_records") is True
    assert data.get("links", {}).get("safety_module")


def test_hr_employee_summary_not_found(client):
    r = client.get("/api/v1/hr/employees/00000000-0000-4000-8000-000000000099")
    assert r.status_code == 404
    data = r.get_json()
    assert data.get("error") == "user not found"


def test_hr_employee_forbidden_without_privilege(client):
    cu = CurrentUser(user=None, role_codes=frozenset(["read_only"]), granular=frozenset(), is_dev_admin=False)
    with patch("app.api._hr_dashboard.current_user", return_value=cu):
        r = client.get("/api/v1/hr/employees/a1700000-0000-4000-8000-000000000001")
    assert r.status_code == 403
    data = r.get_json()
    assert data.get("error") == "forbidden"


def test_hr_employee_self_service_without_hr_role(client, flask_app):
    uid = uuid.UUID("a1700000-0000-4000-8000-000000000001")
    with flask_app.app_context():
        from app.extensions import db
        from app.models import User

        u = db.session.get(User, uid)
    assert u is not None
    cu = CurrentUser(user=u, role_codes=frozenset(), granular=frozenset(), is_dev_admin=False)
    with patch("app.api._hr_dashboard.current_user", return_value=cu):
        r = client.get(f"/api/v1/hr/employees/{uid}")
    assert r.status_code == 200


def test_hr_post_pay_scale_forbidden_for_read_only(client):
    cu = CurrentUser(user=None, role_codes=frozenset(["read_only"]), granular=frozenset(), is_dev_admin=False)
    jamie = "a1700000-0000-4000-8000-000000000001"
    with patch("app.api._hr_dashboard.current_user", return_value=cu):
        r = client.post(
            f"/api/v1/hr/employees/{jamie}/pay-scales",
            json={"label": "Test scale", "pay_basis": "hourly", "hourly_rate": "1"},
        )
    assert r.status_code == 403


def test_hr_post_pay_scale_ok_for_hr_admin(client):
    cu = CurrentUser(user=None, role_codes=frozenset(["hr_admin"]), granular=frozenset(), is_dev_admin=False)
    jamie = "a1700000-0000-4000-8000-000000000001"
    with patch("app.api._hr_dashboard.current_user", return_value=cu):
        r = client.post(
            f"/api/v1/hr/employees/{jamie}/pay-scales",
            json={
                "label": "API test pay row",
                "pay_basis": "hourly",
                "hourly_rate": "12.5000",
                "sort_order": 99,
            },
        )
    assert r.status_code == 201
    data = r.get_json()
    assert data.get("entity") == "hr_employee_pay_scale"
    item = data.get("item") or {}
    assert item.get("label") == "API test pay row"
    scale_id = item.get("id")
    assert scale_id
    with patch("app.api._hr_dashboard.current_user", return_value=cu):
        r2 = client.delete(f"/api/v1/hr/employees/{jamie}/pay-scales/{scale_id}")
    assert r2.status_code == 200
    del_data = r2.get_json()
    assert del_data.get("deleted") is True
