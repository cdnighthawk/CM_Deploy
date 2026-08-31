"""Wave 1 CPR/CO and Wave 2 project documents + companies."""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.extensions import db
from app.models import Project, Role, User, UserRole


@pytest.fixture
def no_dev_admin(monkeypatch):
    monkeypatch.setenv("USIS_API_DEV_ALLOW_ANY", "0")


def _user_and_project():
    role = db.session.scalar(select(Role).where(Role.code == "standard"))
    if role is None:
        role = Role(code="standard", name="Standard")
        db.session.add(role)
        db.session.flush()
    u = User(email="w12_" + uuid.uuid4().hex[:8] + "@t.com", first_name="Wave", last_name="Test")
    db.session.add(u)
    db.session.flush()
    db.session.add(UserRole(user_id=u.id, role_id=role.id))
    p = Project(name="Wave-" + uuid.uuid4().hex[:8], contract_value="10000.00")
    db.session.add(p)
    db.session.flush()
    return str(u.id), str(p.id)


def test_cpr_and_owner_co(client, no_dev_admin):
    with client.application.app_context():
        uid, pid = _user_and_project()
        db.session.commit()
    hdr = {"X-Usis-User-Id": uid}

    r = client.post(f"/api/v1/projects/{pid}/cprs", headers=hdr, json={"subject": "Extra steel"})
    assert r.status_code == 201, r.get_data(as_text=True)
    cpr = r.get_json()["item"]
    assert cpr["subject"] == "Extra steel"
    assert cpr["number"]

    r2 = client.post(f"/api/v1/projects/{pid}/change-orders", headers=hdr, json={"cpr_id": cpr["id"]})
    assert r2.status_code == 201, r2.get_data(as_text=True)
    co = r2.get_json()["item"]
    assert co["subject"] == "Extra steel"
    assert co["cpr_id"] == cpr["id"]

    listed = client.get(f"/api/v1/projects/{pid}/change-orders", headers=hdr)
    assert listed.status_code == 200
    assert len(listed.get_json()["items"]) == 1


def test_wave2_punch_and_company(client, no_dev_admin):
    with client.application.app_context():
        uid, pid = _user_and_project()
        db.session.commit()
    hdr = {"X-Usis-User-Id": uid}

    r = client.post(
        f"/api/v1/projects/{pid}/wave2/punchlist",
        headers=hdr,
        json={"title": "Touch up paint", "location": "Lobby"},
    )
    assert r.status_code == 201, r.get_data(as_text=True)
    item = r.get_json()["item"]
    assert item["title"] == "Touch up paint"
    assert item["number"]

    listed = client.get(f"/api/v1/projects/{pid}/wave2/punchlist", headers=hdr)
    assert listed.status_code == 200
    assert listed.get_json()["items"][0]["id"] == item["id"]

    c = client.post("/api/v1/companies", headers=hdr, json={"name": "Acme Drywall", "company_type": "subcontractor"})
    assert c.status_code == 201, c.get_data(as_text=True)
    cid = c.get_json()["item"]["id"]

    ins = client.post(
        f"/api/v1/companies/{cid}/insurance",
        headers=hdr,
        json={"policy_type": "GL", "carrier": "Hartford", "expires_on": "2027-01-15"},
    )
    assert ins.status_code == 201, ins.get_data(as_text=True)
    assert ins.get_json()["item"]["carrier"] == "Hartford"

    open_items = client.get(f"/api/v1/projects/{pid}/open-items", headers=hdr)
    assert open_items.status_code == 200
    kinds = {row["kind"] for row in open_items.get_json()["items"]}
    assert "punch" in kinds
