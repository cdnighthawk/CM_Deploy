"""API tests for project pay applications (G702-style)."""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.extensions import db
from app.models import Project, Role, User, UserRole


@pytest.fixture
def no_dev_admin(monkeypatch):
    monkeypatch.setenv("USIS_API_DEV_ALLOW_ANY", "0")


def test_pay_application_create_patch_lines_delete(client, no_dev_admin):
    with client.application.app_context():
        role = db.session.scalar(select(Role).where(Role.code == "standard"))
        if role is None:
            role = Role(code="standard", name="Standard")
            db.session.add(role)
            db.session.flush()
        u = User(email="pay_u_" + uuid.uuid4().hex[:8] + "@t.com", first_name="Pay", last_name="App")
        db.session.add(u)
        db.session.flush()
        db.session.add(UserRole(user_id=u.id, role_id=role.id))
        p = Project(name="PayProj-" + uuid.uuid4().hex[:8], contract_value="100000.00")
        db.session.add(p)
        db.session.flush()
        pid = str(p.id)
        uid = str(u.id)
        db.session.commit()

    hdr = {"X-Usis-User-Id": uid}

    r0 = client.post(f"/api/v1/projects/{pid}/pay-applications", json={}, headers=hdr)
    assert r0.status_code == 201, r0.get_data(as_text=True)
    body0 = r0.get_json()
    assert body0["item"]["application_number"] == 1
    assert body0["item"]["original_contract_sum"] == "100000.00"
    aid = body0["item"]["id"]

    r1 = client.patch(
        f"/api/v1/projects/{pid}/pay-applications/{aid}",
        json={
            "period_to": "2026-05-31",
            "net_change_by_change_orders": "5000.00",
            "lines": [
                {
                    "sort_order": 0,
                    "phase_code": "001",
                    "description": "Mobilization",
                    "scheduled_value": "10000.00",
                    "net_change_co": "0",
                    "work_from_previous": "0",
                    "work_this_period": "5000.00",
                    "materials_stored": "0",
                    "retention_to_date": "500.00",
                }
            ],
        },
        headers=hdr,
    )
    assert r1.status_code == 200, r1.get_data(as_text=True)
    b1 = r1.get_json()
    assert len(b1["lines"]) == 1
    assert b1["item"]["contract_sum_to_date"] == "105000.00"
    assert b1["item"]["total_completed_and_stored_to_date"] == "5000.00"

    r2 = client.get(f"/api/v1/projects/{pid}/pay-applications", headers=hdr)
    assert r2.status_code == 200
    assert len(r2.get_json()["items"]) == 1

    r3 = client.delete(f"/api/v1/projects/{pid}/pay-applications/{aid}", headers=hdr)
    assert r3.status_code == 204
