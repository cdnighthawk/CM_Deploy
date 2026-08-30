"""Desktop Projects → Queue (``GET /api/v1/project-queue``)."""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.extensions import db
from app.models import Project, ProjectMember, Role, RoleModulePermission, User, UserRole


@pytest.fixture
def no_dev_admin(monkeypatch):
    monkeypatch.setenv("USIS_API_DEV_ALLOW_ANY", "0")


def _user_with_projects(email_prefix: str = "pq", *, superuser: bool = False) -> User:
    role = db.session.scalar(select(Role).where(Role.code == "project-queue-test"))
    if role is None:
        role = Role(code="project-queue-test", name="Project queue test")
        db.session.add(role)
        db.session.flush()
        db.session.add(
            RoleModulePermission(role_id=role.id, module_code="projects", access_level="write")
        )
    u = User(
        email=f"{email_prefix}_{uuid.uuid4().hex[:8]}@gousis.com",
        first_name="Queue",
        last_name="Projects",
        is_active=True,
        is_superuser=superuser,
    )
    db.session.add(u)
    db.session.flush()
    db.session.add(UserRole(user_id=u.id, role_id=role.id))
    return u


def test_project_queue_requires_sign_in(client, no_dev_admin):
    r = client.get("/api/v1/project-queue")
    assert r.status_code == 401
    assert "authentication required" in (r.get_json() or {}).get("error", "")


def test_project_queue_returns_desktop_items(client, no_dev_admin):
    with client.application.app_context():
        u = _user_with_projects(superuser=True)
        p = Project(
            name="Harbor School",
            number="26-104",
            status="active",
            project_type="commercial",
            city="Tucson",
            state="AZ",
            postal_code="85701",
            address_line1="100 Main",
        )
        db.session.add(p)
        db.session.commit()
        uid = str(u.id)
        pid = str(p.id)

    r = client.get("/api/v1/project-queue", headers={"X-Usis-User-Id": uid})
    assert r.status_code == 200, r.get_data(as_text=True)
    match = next(x for x in r.get_json()["items"] if x["id"] == pid)
    assert match["name"] == "Harbor School"
    assert match["number"] == "26-104"
    assert match["status"] == "active"
    assert match["projectType"] == "commercial"
    assert match["city"] == "Tucson"
    assert match["state"] == "AZ"
    assert match["siteZip"] == "85701"
    assert match["siteAddress"] == "100 Main"


def test_project_queue_hides_planning_for_company_wide(client, no_dev_admin):
    suffix = uuid.uuid4().hex[:8]
    with client.application.app_context():
        u = _user_with_projects(superuser=True)
        keep = Project(name=f"Keep {suffix}", status="active", project_type="commercial")
        planning = Project(name=f"Plan {suffix}", status="planning", project_type="commercial")
        db.session.add_all([keep, planning])
        db.session.commit()
        uid = str(u.id)
        keep_id, planning_id = str(keep.id), str(planning.id)

    r = client.get("/api/v1/project-queue", headers={"X-Usis-User-Id": uid})
    assert r.status_code == 200
    ids = {x["id"] for x in r.get_json()["items"]}
    assert keep_id in ids
    assert planning_id not in ids


def test_project_queue_assigned_user_sees_own_planning_job(client, no_dev_admin):
    with client.application.app_context():
        u = _user_with_projects()
        planning = Project(name="Assigned Planning", status="planning", project_type="commercial")
        other = Project(name="Other Planning", status="planning", project_type="commercial")
        db.session.add_all([planning, other])
        db.session.flush()
        db.session.add(ProjectMember(user_id=u.id, project_id=planning.id))
        db.session.commit()
        uid = str(u.id)
        pid, other_id = str(planning.id), str(other.id)

    r = client.get("/api/v1/project-queue", headers={"X-Usis-User-Id": uid})
    assert r.status_code == 200
    ids = {x["id"] for x in r.get_json()["items"]}
    assert pid in ids
    assert other_id not in ids
