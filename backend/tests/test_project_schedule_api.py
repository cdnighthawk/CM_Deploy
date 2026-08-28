"""API tests for project installation schedule (schedule-items)."""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.extensions import db
from app.models import Project, ProjectMember, Role, User, UserRole


@pytest.fixture
def no_dev_admin(monkeypatch):
    monkeypatch.setenv("USIS_API_DEV_ALLOW_ANY", "0")


def test_project_schedule_items_crud(client, no_dev_admin):
    with client.application.app_context():
        role = db.session.scalar(select(Role).where(Role.code == "standard"))
        if role is None:
            role = Role(code="standard", name="Standard")
            db.session.add(role)
            db.session.flush()
        u = User(email="sched_u_" + uuid.uuid4().hex[:8] + "@t.com", first_name="S", last_name="U")
        db.session.add(u)
        db.session.flush()
        db.session.add(UserRole(user_id=u.id, role_id=role.id))
        p = Project(name="SchedProj-" + uuid.uuid4().hex[:8])
        db.session.add(p)
        db.session.flush()
        db.session.add(ProjectMember(user_id=u.id, project_id=p.id))
        pid = str(p.id)
        uid = str(u.id)
        db.session.commit()

    hdr = {"X-Usis-User-Id": uid}

    r0 = client.get(f"/api/v1/projects/{pid}/schedule-items", headers=hdr)
    assert r0.status_code == 200, r0.get_data(as_text=True)
    assert r0.get_json()["items"] == []

    r_bad = client.post(
        f"/api/v1/projects/{pid}/schedule-items",
        json={"title": "A", "start_date": "2026-06-11", "end_date": "2026-06-01"},
        headers=hdr,
    )
    assert r_bad.status_code == 400

    r1 = client.post(
        f"/api/v1/projects/{pid}/schedule-items",
        json={
            "title": "1st floor bathrooms",
            "start_date": "2026-06-01",
            "end_date": "2026-06-10",
            "crew_label": " Crew A ",
        },
        headers=hdr,
    )
    assert r1.status_code == 201, r1.get_data(as_text=True)
    b1 = r1.get_json()["item"]
    assert b1["title"] == "1st floor bathrooms"
    assert b1["crew_label"] == "Crew A"
    iid = b1["id"]

    r2 = client.get(f"/api/v1/projects/{pid}/schedule-items", headers=hdr)
    assert r2.status_code == 200
    assert len(r2.get_json()["items"]) == 1

    r3 = client.patch(
        f"/api/v1/projects/{pid}/schedule-items/{iid}",
        json={"end_date": "2026-06-12", "crew_label": ""},
        headers=hdr,
    )
    assert r3.status_code == 200
    assert r3.get_json()["item"]["end_date"] == "2026-06-12"
    assert r3.get_json()["item"]["crew_label"] is None

    r4 = client.delete(f"/api/v1/projects/{pid}/schedule-items/{iid}", headers=hdr)
    assert r4.status_code == 200

    r5 = client.get(f"/api/v1/projects/{pid}/schedule-items", headers=hdr)
    assert r5.get_json()["items"] == []


def test_project_schedule_item_assignee_notifies_other_user(client, no_dev_admin):
    from app.models.hrms_core import HrmsNotification

    with client.application.app_context():
        role = db.session.scalar(select(Role).where(Role.code == "standard"))
        if role is None:
            role = Role(code="standard", name="Standard")
            db.session.add(role)
            db.session.flush()
        actor = User(
            email="sched_actor_" + uuid.uuid4().hex[:8] + "@t.com",
            first_name="Pat",
            last_name="Lee",
        )
        assignee = User(
            email="sched_asg_" + uuid.uuid4().hex[:8] + "@t.com",
            first_name="Morgan",
            last_name="Reyes",
        )
        db.session.add_all([actor, assignee])
        db.session.flush()
        db.session.add(UserRole(user_id=actor.id, role_id=role.id))
        db.session.add(UserRole(user_id=assignee.id, role_id=role.id))
        p = Project(name="SchedAssign-" + uuid.uuid4().hex[:8])
        db.session.add(p)
        db.session.flush()
        db.session.add(ProjectMember(user_id=actor.id, project_id=p.id))
        db.session.add(ProjectMember(user_id=assignee.id, project_id=p.id))
        pid = str(p.id)
        actor_id = str(actor.id)
        assignee_id = str(assignee.id)
        db.session.commit()

    hdr = {"X-Usis-User-Id": actor_id}
    r1 = client.post(
        f"/api/v1/projects/{pid}/schedule-items",
        json={
            "title": "Receive hardware",
            "start_date": "2026-09-01",
            "end_date": "2026-09-02",
            "assignee_user_id": assignee_id,
        },
        headers=hdr,
    )
    assert r1.status_code == 201, r1.get_data(as_text=True)
    item = r1.get_json()["item"]
    assert item["assignee_user_id"] == assignee_id
    assert item["assignee_name"] == "Morgan Reyes"
    iid = item["id"]

    with client.application.app_context():
        notes = db.session.scalars(
            select(HrmsNotification).where(HrmsNotification.user_id == uuid.UUID(assignee_id))
        ).all()
        assert len(notes) == 1
        assert "Receive hardware" in (notes[0].title or "")

    r_self = client.patch(
        f"/api/v1/projects/{pid}/schedule-items/{iid}",
        json={"assignee_user_id": actor_id},
        headers=hdr,
    )
    assert r_self.status_code == 200
    assert r_self.get_json()["item"]["assignee_user_id"] == actor_id

    with client.application.app_context():
        actor_notes = db.session.scalars(
            select(HrmsNotification).where(HrmsNotification.user_id == uuid.UUID(actor_id))
        ).all()
        assert actor_notes == []

    r_bad = client.patch(
        f"/api/v1/projects/{pid}/schedule-items/{iid}",
        json={"assignee_user_id": "not-a-uuid"},
        headers=hdr,
    )
    assert r_bad.status_code == 400
