"""API tests for project prime contract SOV."""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.extensions import db
from app.models import Project, Role, User, UserRole


@pytest.fixture
def no_dev_admin(monkeypatch):
    monkeypatch.setenv("USIS_API_DEV_ALLOW_ANY", "0")


def test_prime_contract_sov_get_put(client, no_dev_admin):
    with client.application.app_context():
        role = db.session.scalar(select(Role).where(Role.code == "standard"))
        if role is None:
            role = Role(code="standard", name="Standard")
            db.session.add(role)
            db.session.flush()
        u = User(email="sov_u_" + uuid.uuid4().hex[:8] + "@t.com", first_name="Sov", last_name="User")
        db.session.add(u)
        db.session.flush()
        db.session.add(UserRole(user_id=u.id, role_id=role.id))
        p = Project(name="SovProj-" + uuid.uuid4().hex[:8], contract_value="50000.00")
        db.session.add(p)
        db.session.flush()
        pid = str(p.id)
        uid = str(u.id)
        db.session.commit()

    hdr = {"X-Usis-User-Id": uid}

    r0 = client.get(f"/api/v1/projects/{pid}/prime-contract/sov", headers=hdr)
    assert r0.status_code == 200, r0.get_data(as_text=True)
    b0 = r0.get_json()
    assert b0["lines"] == []
    assert b0["total_scheduled_value"] == "0.00"
    assert b0["contract_value"] == "50000.00"
    assert b0["sov_matches_contract_value"] is False

    body = {
        "lines": [
            {"phase_code": "01", "description": "General", "scheduled_value": "20000.00"},
            {"phase_code": "02", "description": "Site", "scheduled_value": "30000.00"},
        ]
    }
    r1 = client.put(f"/api/v1/projects/{pid}/prime-contract/sov", json=body, headers=hdr)
    assert r1.status_code == 200, r1.get_data(as_text=True)
    b1 = r1.get_json()
    assert len(b1["lines"]) == 2
    assert b1["total_scheduled_value"] == "50000.00"
    assert b1["sov_matches_contract_value"] is True

    r2 = client.get(f"/api/v1/projects/{pid}/prime-contract/sov", headers=hdr)
    assert r2.status_code == 200
    b2 = r2.get_json()
    assert len(b2["lines"]) == 2
    assert b2["lines"][0]["phase_code"] == "01"
