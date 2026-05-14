"""Playbook checklist API (Plan 22)."""
from __future__ import annotations

import uuid

import pytest


@pytest.fixture
def playbook_company_and_user(flask_app):
    """Minimal company + user for template/run tests."""
    from app.extensions import db
    from app.models import Company, User

    with flask_app.app_context():
        c = Company(name="Playbook Test Co", company_type="self")
        db.session.add(c)
        db.session.flush()
        uid = uuid.uuid4()
        u = User(
            id=uid,
            email=f"playbook_tester_{uid.hex[:8]}@example.com",
            first_name="Play",
            last_name="Book",
            is_active=True,
            is_superuser=False,
        )
        db.session.add(u)
        db.session.commit()
        cid = c.id
        user_id = u.id
        em = u.email
    return {"company_id": str(cid), "user_id": str(user_id), "email": em}


def test_playbooks_templates_list_empty_ok(client):
    r = client.get("/api/v1/playbooks/templates")
    assert r.status_code == 200
    data = r.get_json()
    assert data.get("entity") == "checklist_templates"
    assert "items" in data


def test_playbooks_template_and_run_lifecycle(client, playbook_company_and_user):
    cid = playbook_company_and_user["company_id"]
    uid = playbook_company_and_user["user_id"]

    r = client.post(
        "/api/v1/playbooks/templates",
        json={"name": "Process change order", "description": "Test", "company_id": cid},
    )
    assert r.status_code == 201, r.get_data(as_text=True)
    tid = r.get_json()["item"]["id"]

    r = client.put(
        f"/api/v1/playbooks/templates/{tid}/steps",
        json={
            "steps": [
                {"title": "Step 1", "body": "First", "default_assignee_user_id": uid},
                {"title": "Step 2", "default_assignee_user_id": None},
            ]
        },
    )
    assert r.status_code == 200
    assert len(r.get_json()["steps"]) == 2

    r = client.post(
        "/api/v1/playbooks/runs",
        headers={"X-Usis-User-Id": uid},
        json={"template_id": tid, "title": "CO-123"},
    )
    assert r.status_code == 201, r.get_data(as_text=True)
    run = r.get_json()["item"]
    rid = run["id"]
    assert run["status"] == "open"
    assert run["step_count"] == 2
    step_ids = [s["id"] for s in run["steps"]]

    r = client.patch(
        f"/api/v1/playbooks/runs/{rid}/steps/{step_ids[0]}",
        headers={"X-Usis-User-Id": uid},
        json={"status": "done"},
    )
    assert r.status_code == 200
    assert r.get_json()["item"]["status"] == "done"

    r = client.patch(
        f"/api/v1/playbooks/runs/{rid}/steps/{step_ids[1]}",
        headers={"X-Usis-User-Id": uid},
        json={"status": "skipped"},
    )
    assert r.status_code == 200

    r = client.get(f"/api/v1/playbooks/runs/{rid}")
    assert r.status_code == 200
    assert r.get_json()["item"]["status"] == "complete"
    assert r.get_json()["item"]["progress_percent"] == 100
