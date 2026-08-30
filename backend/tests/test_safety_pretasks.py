"""Daily pre-task safety plan API (Appendix E)."""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.extensions import db
from app.models import Project, ProjectMember, Role, User, UserRole


def _mk_user(prefix: str, role_code: str = "superintendent") -> User:
    role = db.session.scalar(select(Role).where(Role.code == role_code))
    if role is None:
        role = Role(code=role_code, name=role_code.replace("_", " ").title())
        db.session.add(role)
        db.session.flush()
    u = User(
        email=f"{prefix}_{uuid.uuid4().hex[:8]}@t.com",
        first_name=prefix.title(),
        last_name="Lead",
        is_active=True,
    )
    db.session.add(u)
    db.session.flush()
    db.session.add(UserRole(user_id=u.id, role_id=role.id))
    return u


def test_get_or_create_put_and_submit_pretask(client):
    with client.application.app_context():
        lead = _mk_user("crew")
        p = Project(name="Pretask-" + uuid.uuid4().hex[:8], number="26-104")
        db.session.add(p)
        db.session.flush()
        db.session.add(ProjectMember(user_id=lead.id, project_id=p.id))
        pid = str(p.id)
        uid = str(lead.id)
        db.session.commit()

    headers = {"X-Usis-User-Id": uid}
    r1 = client.get(f"/api/v1/projects/{pid}/daily-pretasks?date=2026-08-29", headers=headers)
    assert r1.status_code == 200, r1.get_data(as_text=True)
    body = r1.get_json()
    assert body["entity"] == "daily_pretask"
    assert body["item"]["work_date"] == "2026-08-29"
    assert body["item"]["status"] == "draft"
    assert body["item"]["company_name"] == "DOCON, INC"
    assert body["item"]["checklist"]["supervisor_walkthrough"] is False
    rid = body["item"]["id"]

    r2 = client.get(f"/api/v1/projects/{pid}/daily-pretasks?date=2026-08-29", headers=headers)
    assert r2.get_json()["item"]["id"] == rid

    payload = {
        "area_of_work": "basement/kitchen",
        "checklist": {
            "supervisor_walkthrough": True,
            "coordination_other_crafts": True,
            "equipment_check": True,
            "training_complete": True,
            "sufficient_personnel": True,
        },
        "tasks": [
            {
                "jha_complete": True,
                "task": "Move Material",
                "hazards": "Cut hands\nPull Muscles",
                "steps": "Wear Cut resistant Gloves\n2 person lift\nUse Cart for long movements",
            },
            {
                "jha_complete": False,
                "task": "Layout",
                "hazards": "Slip, Trip, Fall",
                "steps": "Ensure work area is clean and free of obstructions prior to work beginning",
            },
        ],
        "near_miss": False,
        "required_permits": "",
        "attendees": [{"print_name": "Jane Crew", "signature": "Jane Crew"}],
        "supervisor_name": "Charles Dossett",
        "supervisor_signature": "Charles Dossett",
    }
    r3 = client.put(f"/api/v1/daily-pretasks/{rid}", json=payload, headers=headers)
    assert r3.status_code == 200, r3.get_data(as_text=True)
    item = r3.get_json()["item"]
    assert item["area_of_work"] == "basement/kitchen"
    assert item["tasks"][0]["task"] == "Move Material"

    r4 = client.post(f"/api/v1/daily-pretasks/{rid}/submit", json={}, headers=headers)
    assert r4.status_code == 200, r4.get_data(as_text=True)
    assert r4.get_json()["item"]["status"] == "submitted"

    listed = client.get("/api/v1/safety/pretasks?date=2026-08-29", headers=headers)
    assert listed.status_code == 200
    items = listed.get_json()["items"]
    assert any(row["id"] == rid for row in items)

    summary = client.get("/api/v1/safety/summary", headers=headers)
    assert summary.status_code == 200
    counts = summary.get_json()["counts"]
    assert "pretasks_today" in counts
    assert "expiring_certs_30d" in counts


def test_submit_requires_checklist_and_task(client):
    with client.application.app_context():
        lead = _mk_user("req")
        p = Project(name="PretaskReq-" + uuid.uuid4().hex[:8])
        db.session.add(p)
        db.session.flush()
        db.session.add(ProjectMember(user_id=lead.id, project_id=p.id))
        pid = str(p.id)
        uid = str(lead.id)
        db.session.commit()

    headers = {"X-Usis-User-Id": uid}
    created = client.get(f"/api/v1/projects/{pid}/daily-pretasks?date=2026-08-28", headers=headers)
    rid = created.get_json()["item"]["id"]
    bad = client.post(f"/api/v1/safety/pretasks/{rid}/submit", json={}, headers=headers)
    assert bad.status_code == 400
    assert "checklist" in bad.get_json()["error"]


def test_client_id_replay_returns_same_row(client):
    cid = str(uuid.uuid4())
    with client.application.app_context():
        lead = _mk_user("cid")
        p = Project(name="PretaskCid-" + uuid.uuid4().hex[:8])
        db.session.add(p)
        db.session.flush()
        db.session.add(ProjectMember(user_id=lead.id, project_id=p.id))
        pid = str(p.id)
        uid = str(lead.id)
        db.session.commit()

    headers = {"X-Usis-User-Id": uid}
    first = client.post(
        f"/api/v1/projects/{pid}/daily-pretasks",
        json={"work_date": "2026-08-27", "client_id": cid, "area_of_work": "roof"},
        headers=headers,
    )
    assert first.status_code == 201, first.get_data(as_text=True)
    rid = first.get_json()["item"]["id"]

    second = client.post(
        f"/api/v1/projects/{pid}/daily-pretasks",
        json={"work_date": "2026-08-27", "client_id": cid, "area_of_work": "roof"},
        headers=headers,
    )
    assert second.status_code == 200
    assert second.get_json()["item"]["id"] == rid


@pytest.fixture
def no_dev_admin(monkeypatch):
    monkeypatch.setenv("USIS_API_DEV_ALLOW_ANY", "0")


def test_submitted_pretask_locked_for_field_user(client, no_dev_admin):
    with client.application.app_context():
        lead = _mk_user("foreman", "superintendent")
        job = Project(name="PretaskLock-" + uuid.uuid4().hex[:8])
        db.session.add(job)
        db.session.flush()
        db.session.add(ProjectMember(user_id=lead.id, project_id=job.id))
        db.session.commit()
        pid, uid = str(job.id), str(lead.id)

    headers = {"X-Usis-User-Id": uid}
    created = client.get(
        f"/api/v1/projects/{pid}/daily-pretasks?date=2026-08-26",
        headers=headers,
    )
    assert created.status_code == 200, created.get_data(as_text=True)
    rid = created.get_json()["item"]["id"]
    client.put(
        f"/api/v1/daily-pretasks/{rid}",
        json={
            "area_of_work": "level 2",
            "checklist": {
                "supervisor_walkthrough": True,
                "coordination_other_crafts": True,
                "equipment_check": True,
                "training_complete": True,
                "sufficient_personnel": True,
            },
            "tasks": [{"jha_complete": True, "task": "Cut Material", "hazards": "Cut hands", "steps": "Gloves"}],
            "supervisor_name": "Foreman Lead",
            "status": "submitted",
        },
        headers=headers,
    )
    locked = client.put(
        f"/api/v1/daily-pretasks/{rid}",
        json={"area_of_work": "changed"},
        headers=headers,
    )
    assert locked.status_code == 403
