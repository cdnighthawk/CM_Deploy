"""API tests for multiple owner contracts on a project."""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.extensions import db
from app.models import Project, ProjectContract, Role, User, UserRole


@pytest.fixture
def no_dev_admin(monkeypatch):
    monkeypatch.setenv("USIS_API_DEV_ALLOW_ANY", "0")


def _standard_user_and_project(contract_value="100000.00"):
    role = db.session.scalar(select(Role).where(Role.code == "standard"))
    if role is None:
        role = Role(code="standard", name="Standard")
        db.session.add(role)
        db.session.flush()
    u = User(email="pc_" + uuid.uuid4().hex[:8] + "@t.com", first_name="Pat", last_name="Contract")
    db.session.add(u)
    db.session.flush()
    db.session.add(UserRole(user_id=u.id, role_id=role.id))
    p = Project(name="MultiContract-" + uuid.uuid4().hex[:8], contract_value=contract_value)
    db.session.add(p)
    db.session.flush()
    return str(u.id), str(p.id)


def test_project_contracts_list_add_and_primary(client, no_dev_admin):
    with client.application.app_context():
        uid, pid = _standard_user_and_project()
        db.session.commit()

    hdr = {"X-Usis-User-Id": uid}

    r0 = client.get(f"/api/v1/projects/{pid}/contracts", headers=hdr)
    assert r0.status_code == 200, r0.get_data(as_text=True)
    b0 = r0.get_json()
    assert b0["entity"] == "project_contracts"
    assert len(b0["items"]) == 1
    assert b0["items"][0]["is_primary"] is True
    assert b0["items"][0]["title"] == "Prime contract"
    assert float(b0["items"][0]["contract_value"]) == 100000.0
    primary_id = b0["items"][0]["id"]

    r1 = client.post(
        f"/api/v1/projects/{pid}/contracts",
        headers=hdr,
        json={
            "title": "Phase 2 interiors",
            "contract_number": "C-200",
            "contract_value": "25000.00",
            "contract_date": "2026-03-01",
        },
    )
    assert r1.status_code == 201, r1.get_data(as_text=True)
    extra = r1.get_json()["item"]
    assert extra["title"] == "Phase 2 interiors"
    assert extra["is_primary"] is False
    extra_id = extra["id"]

    r2 = client.get(f"/api/v1/projects/{pid}/contracts", headers=hdr)
    assert r2.status_code == 200
    b2 = r2.get_json()
    assert len(b2["items"]) == 2
    assert float(b2["total_contract_value"]) == 125000.0
    assert b2["primary_id"] == primary_id

    r3 = client.patch(
        f"/api/v1/projects/{pid}/contracts/{extra_id}",
        headers=hdr,
        json={"is_primary": True},
    )
    assert r3.status_code == 200, r3.get_data(as_text=True)
    assert r3.get_json()["item"]["is_primary"] is True

    r4 = client.get(f"/api/v1/projects/{pid}", headers=hdr)
    assert r4.status_code == 200
    assert float(r4.get_json()["item"]["contract_value"]) == 25000.0

    r5 = client.delete(f"/api/v1/projects/{pid}/contracts/{primary_id}", headers=hdr)
    assert r5.status_code == 204

    r6 = client.delete(f"/api/v1/projects/{pid}/contracts/{extra_id}", headers=hdr)
    assert r6.status_code == 400

    with client.application.app_context():
        rows = list(db.session.scalars(select(ProjectContract).where(ProjectContract.project_id == uuid.UUID(pid))))
        assert len(rows) == 1
        assert rows[0].is_primary is True
        assert rows[0].title == "Phase 2 interiors"


def test_project_contracts_first_row_on_empty_project(client, no_dev_admin):
    with client.application.app_context():
        uid, pid = _standard_user_and_project(contract_value=None)
        db.session.commit()

    hdr = {"X-Usis-User-Id": uid}
    r0 = client.get(f"/api/v1/projects/{pid}/contracts", headers=hdr)
    assert r0.status_code == 200, r0.get_data(as_text=True)
    assert r0.get_json()["items"] == []

    r1 = client.post(
        f"/api/v1/projects/{pid}/contracts",
        headers=hdr,
        json={"title": "Base bid", "contract_value": "50000.00"},
    )
    assert r1.status_code == 201, r1.get_data(as_text=True)
    item = r1.get_json()["item"]
    assert item["is_primary"] is True
    assert item["title"] == "Base bid"

    r2 = client.get(f"/api/v1/projects/{pid}", headers=hdr)
    assert r2.status_code == 200
    assert float(r2.get_json()["item"]["contract_value"]) == 50000.0

    r3 = client.post(
        f"/api/v1/projects/{pid}/contracts",
        headers=hdr,
        json={"title": "Phase 2", "contract_value": "12000.00"},
    )
    assert r3.status_code == 201, r3.get_data(as_text=True)
    assert r3.get_json()["item"]["is_primary"] is False

    r4 = client.get(f"/api/v1/projects/{pid}/contracts", headers=hdr)
    assert r4.status_code == 200
    body = r4.get_json()
    assert len(body["items"]) == 2
    assert float(body["total_contract_value"]) == 62000.0


def test_project_contracts_require_title(client, no_dev_admin):
    with client.application.app_context():
        uid, pid = _standard_user_and_project()
        db.session.commit()

    hdr = {"X-Usis-User-Id": uid}
    r = client.post(f"/api/v1/projects/{pid}/contracts", headers=hdr, json={"contract_value": "1"})
    assert r.status_code == 400
    assert "title" in (r.get_json() or {}).get("error", "").lower()
