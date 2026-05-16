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


def _sample_i9_section1():
    return {
        "last_name": "Rivera",
        "first_name": "Jamie",
        "middle_initial": "",
        "other_last_names": "",
        "address": "100 Test St",
        "apt": "",
        "city": "Denver",
        "state": "CO",
        "zip": "80202",
        "date_of_birth": "1990-06-01",
        "ssn": "123-45-6789",
        "email": "jamie.rivera@example.com",
        "telephone": "555-0100",
        "citizenship_status": "citizen",
        "document_choice": "list_a",
        "uscis_a_number": "",
        "admission_i94": "",
        "foreign_passport": "",
        "work_authorization_expiration": "",
        "list_a": {
            "document_type": "us_passport",
            "title": "U.S. Passport",
            "issuing_authority": "U.S. Department of State",
            "number": "P1234567",
            "expiration": "2030-06-01",
        },
        "list_b": None,
        "list_c": None,
    }


# 1x1 PNG
_TINY_PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)
_TINY_PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00"
    b"\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


def test_hr_i9_document_upload_and_owner_only(client):
    """Upload I-9 doc photo; only hire wizard owner may download."""
    import io

    demo = "a1700000-0000-4000-8000-000000000001"
    other = "b1700000-0000-4000-8000-000000000001"
    hdr = {"X-Usis-User-Id": demo}
    data = {
        "file": (io.BytesIO(_TINY_PNG_BYTES), "passport-front.png"),
        "slot": "list_a",
    }
    r = client.post(
        "/api/v1/hr/me/i9-section1/documents",
        data=data,
        content_type="multipart/form-data",
        headers=hdr,
    )
    assert r.status_code == 201
    body = r.get_json()
    assert body.get("ok") is True
    fid = (body.get("item") or {}).get("id")
    assert fid

    r2 = client.get(f"/api/v1/hr/me/i9-section1/documents/{fid}/file", headers=hdr)
    assert r2.status_code == 200
    assert r2.data[:8] == b"\x89PNG\r\n\x1a\n"

    r3 = client.get(f"/api/v1/hr/me/i9-section1/documents/{fid}/file", headers={"X-Usis-User-Id": other})
    assert r3.status_code == 404

    w = client.get("/api/v1/hr/me/hire-wizard", headers=hdr).get_json()
    docs = (w.get("i9") or {}).get("documents") or []
    assert any(d.get("id") == fid for d in docs)

    r4 = client.delete(f"/api/v1/hr/me/i9-section1/documents/{fid}", headers=hdr)
    assert r4.status_code == 200
    assert r4.get_json().get("deleted") is True


def test_hr_union_document_upload_and_owner_only(client):
    """Upload union doc photo; only hire wizard owner may download."""
    import io

    demo = "a1700000-0000-4000-8000-000000000001"
    other = "b1700000-0000-4000-8000-000000000001"
    hdr = {"X-Usis-User-Id": demo}
    data = {
        "file": (io.BytesIO(_TINY_PNG_BYTES), "union-card-front.png"),
        "kind": "union_card",
    }
    r = client.post(
        "/api/v1/hr/me/hire-wizard/union-documents",
        data=data,
        content_type="multipart/form-data",
        headers=hdr,
    )
    assert r.status_code == 201
    body = r.get_json()
    assert body.get("ok") is True
    fid = (body.get("item") or {}).get("id")
    assert fid
    assert (body.get("item") or {}).get("document_kind") == "union_card"

    r2 = client.get(f"/api/v1/hr/me/hire-wizard/union-documents/{fid}/file", headers=hdr)
    assert r2.status_code == 200
    assert r2.data[:8] == b"\x89PNG\r\n\x1a\n"

    r3 = client.get(f"/api/v1/hr/me/hire-wizard/union-documents/{fid}/file", headers={"X-Usis-User-Id": other})
    assert r3.status_code == 404

    w = client.get("/api/v1/hr/me/hire-wizard", headers=hdr).get_json()
    union_docs = (w.get("union") or {}).get("documents") or []
    assert any(d.get("id") == fid for d in union_docs)
    union_tasks = {t["key"]: t for t in (w.get("tasks") or [])}
    assert union_tasks["union_card"]["status"] == "complete"

    r4 = client.delete(f"/api/v1/hr/me/hire-wizard/union-documents/{fid}", headers=hdr)
    assert r4.status_code == 200
    assert r4.get_json().get("deleted") is True


def test_hr_hire_wizard_unauthenticated(client, no_dev_admin):
    r = client.get("/api/v1/hr/me/hire-wizard")
    assert r.status_code == 401
    assert r.get_json().get("error") == "authentication required"


def test_hr_hire_wizard_tasks_shape(client):
    demo = "a1700000-0000-4000-8000-000000000001"
    hdr = {"X-Usis-User-Id": demo}
    w = client.get("/api/v1/hr/me/hire-wizard", headers=hdr).get_json()
    assert w.get("entity") == "hr_hire_wizard"
    tasks = w.get("tasks") or []
    keys = [t["key"] for t in tasks]
    assert keys == ["account", "application", "union_card", "union_dispatch", "i9", "w4"]
    assert tasks[0]["status"] == "complete"
    prog = w.get("progress") or {}
    assert prog.get("total") == 6
    assert "percent" in prog


def test_hr_hire_wizard_get_and_submit(client):
    demo = "a1700000-0000-4000-8000-000000000001"
    hdr = {"X-Usis-User-Id": demo}
    r = client.get("/api/v1/hr/me/hire-wizard", headers=hdr)
    assert r.status_code == 200
    w = r.get_json()
    assert w.get("entity") == "hr_hire_wizard"
    assert w.get("steps", {}).get("application", {}).get("onboarding_item_id")
    i9_id = w["steps"]["i9"]["policy_acknowledgment_id"]
    assert i9_id
    assert w.get("i9", {}).get("prefill", {}).get("last_name")
    r2 = client.post(
        "/api/v1/hr/me/hire-application",
        headers=hdr,
        json={"application": {"position_applying_for": "Estimator", "city": "Denver"}},
    )
    assert r2.status_code == 200
    r3 = client.get("/api/v1/hr/me/hire-wizard", headers=hdr)
    assert r3.get_json()["steps"]["application"]["completed"] is True
    r4 = client.post(
        f"/api/v1/hr/me/policy-acknowledgments/{i9_id}/sign",
        headers=hdr,
        json={"certify": True, "typed_full_name": "Jamie Rivera"},
    )
    assert r4.status_code == 400
    assert "i9-section1/sign" in (r4.get_json().get("error") or "")

    r5 = client.post(
        "/api/v1/hr/me/i9-section1",
        headers=hdr,
        json={"section1": _sample_i9_section1(), "mark_complete": True},
    )
    assert r5.status_code == 200
    assert r5.get_json().get("ok") is True
    r6 = client.get("/api/v1/hr/me/hire-wizard", headers=hdr)
    w6 = r6.get_json()
    assert w6["i9"]["status"] in ("completed", "draft")
    assert w6["i9"]["draft"] is not None
    assert w6["i9"]["draft"].get("ssn") == "123-45-6789"

    r7 = client.post(
        "/api/v1/hr/me/i9-section1/sign",
        headers=hdr,
        json={
            "certify": True,
            "typed_full_name": "Jamie Rivera",
            "signature_png_base64": _TINY_PNG_B64,
        },
    )
    assert r7.status_code == 200
    assert r7.get_json().get("ok") is True

    r8 = client.post(
        "/api/v1/hr/me/i9-section1",
        headers=hdr,
        json={"section1": _sample_i9_section1(), "mark_complete": False},
    )
    assert r8.status_code == 409

    r9 = client.get("/api/v1/hr/me/hire-wizard", headers=hdr)
    assert r9.get_json()["i9"]["status"] == "signed"
    assert r9.get_json()["steps"]["i9"]["signed_at"]

    w4_id = r9.get_json()["steps"]["w4"]["policy_acknowledgment_id"]
    r10 = client.post(
        f"/api/v1/hr/me/policy-acknowledgments/{w4_id}/sign",
        headers=hdr,
        json={"certify": True, "typed_full_name": "Jamie Rivera"},
    )
    assert r10.status_code == 400
    assert "w4/sign" in (r10.get_json().get("error") or "")

    sample_w4 = {
        "first_name": "Jamie",
        "last_name": "Rivera",
        "middle_initial": "",
        "address": "100 Test St",
        "city": "Denver",
        "state": "CO",
        "zip": "80202",
        "ssn": "123-45-6789",
        "filing_status": "single",
        "multiple_jobs": False,
        "higher_withholding": False,
        "dependents_amount": "500",
        "other_income": "",
        "deductions": "",
        "extra_withholding": "",
        "exempt_claim": False,
    }
    r11 = client.post(
        "/api/v1/hr/me/w4",
        headers=hdr,
        json={"w4": sample_w4, "mark_complete": True},
    )
    assert r11.status_code == 200
    r12 = client.get("/api/v1/hr/me/hire-wizard", headers=hdr)
    w12 = r12.get_json()
    assert w12["w4"]["draft"] is not None
    assert w12["w4"]["draft"].get("ssn") == "123-45-6789"

    r13 = client.post(
        "/api/v1/hr/me/w4/sign",
        headers=hdr,
        json={
            "certify": True,
            "typed_full_name": "Jamie Rivera",
            "signature_png_base64": _TINY_PNG_B64,
        },
    )
    assert r13.status_code == 200
    r14 = client.get("/api/v1/hr/me/hire-wizard", headers=hdr)
    assert r14.get_json()["w4"]["status"] == "signed"
    assert r14.get_json()["steps"]["w4"]["signed_at"]
