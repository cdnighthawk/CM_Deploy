"""Project assignment scoping and membership APIs."""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.extensions import db
from app.models import Project, ProjectMember, Role, User, UserRole


@pytest.fixture
def no_dev_admin(monkeypatch):
    monkeypatch.setenv("USIS_API_DEV_ALLOW_ANY", "0")


def _mk_project(name: str = "Scope Test Job") -> Project:
    p = Project(name=name, status="active", project_type="commercial")
    db.session.add(p)
    db.session.flush()
    return p


def _mk_user_with_role(role_code: str, email_prefix: str = "scope") -> tuple[User, Role]:
    role = db.session.scalar(select(Role).where(Role.code == role_code))
    if role is None:
        role = Role(code=role_code, name=role_code.replace("_", " ").title())
        db.session.add(role)
        db.session.flush()
    u = User(email=f"{email_prefix}_{uuid.uuid4().hex[:8]}@t.com", is_active=True)
    db.session.add(u)
    db.session.flush()
    db.session.add(UserRole(user_id=u.id, role_id=role.id))
    db.session.commit()
    return u, role


def test_list_projects_scoped_to_assignments(client, no_dev_admin):
    with client.application.app_context():
        u, _ = _mk_user_with_role("project_manager")
        a = _mk_project("Job A")
        b = _mk_project("Job B")
        db.session.add(ProjectMember(user_id=u.id, project_id=a.id))
        db.session.commit()
        uid = str(u.id)
        aid, bid = str(a.id), str(b.id)

    r = client.get("/api/v1/projects", headers={"X-Usis-User-Id": uid})
    assert r.status_code == 200
    body = r.get_json()
    assert body["project_scope"] == "assigned"
    ids = {x["id"] for x in body["items"]}
    assert aid in ids
    assert bid not in ids


def test_get_project_denies_unassigned(client, no_dev_admin):
    with client.application.app_context():
        u, _ = _mk_user_with_role("field_readonly")
        a = _mk_project("Assigned")
        b = _mk_project("Other")
        db.session.add(ProjectMember(user_id=u.id, project_id=a.id))
        db.session.commit()
        uid = str(u.id)
        bid = str(b.id)

    ok = client.get(f"/api/v1/projects/{bid}", headers={"X-Usis-User-Id": uid})
    assert ok.status_code == 404


def test_executive_sees_all_projects(client, no_dev_admin):
    with client.application.app_context():
        u, _ = _mk_user_with_role("executive")
        _mk_project("X1")
        _mk_project("X2")
        db.session.commit()
        uid = str(u.id)

    r = client.get("/api/v1/projects?limit=2000", headers={"X-Usis-User-Id": uid})
    assert r.status_code == 200
    body = r.get_json()
    assert body["project_scope"] == "all"
    assert body["total"] >= 2


def test_zero_assignments_empty_list(client, no_dev_admin):
    with client.application.app_context():
        u, _ = _mk_user_with_role("superintendent")
        _mk_project("Orphan")
        db.session.commit()
        uid = str(u.id)

    r = client.get("/api/v1/projects", headers={"X-Usis-User-Id": uid})
    assert r.status_code == 200
    assert r.get_json()["items"] == []
    assert r.get_json()["total"] == 0


def test_admin_put_user_project_memberships(client, no_dev_admin):
    with client.application.app_context():
        admin = User(
            email=f"scope_admin_{uuid.uuid4().hex[:8]}@t.com",
            is_active=True,
            is_superuser=True,
        )
        db.session.add(admin)
        target, _ = _mk_user_with_role("project_engineer", "pe")
        p1 = _mk_project("M1")
        p2 = _mk_project("M2")
        db.session.commit()
        admin_id = str(admin.id)
        target_id = str(target.id)
        p1_id, p2_id = str(p1.id), str(p2.id)

    r = client.put(
        f"/api/v1/admin/users/{target_id}/project-memberships",
        headers={"X-Usis-User-Id": admin_id},
        json={"project_ids": [p1_id, p2_id]},
    )
    assert r.status_code == 200
    assert set(r.get_json()["project_ids"]) == {p1_id, p2_id}

    r2 = client.get(
        f"/api/v1/admin/users/{target_id}/project-memberships",
        headers={"X-Usis-User-Id": admin_id},
    )
    assert r2.status_code == 200
    assert len(r2.get_json()["project_ids"]) == 2


def test_non_admin_cannot_set_memberships(client, no_dev_admin):
    with client.application.app_context():
        u, _ = _mk_user_with_role("project_manager")
        other, _ = _mk_user_with_role("field_readonly", "fr")
        p = _mk_project()
        db.session.commit()
        uid, other_id, pid = str(u.id), str(other.id), str(p.id)

    r = client.put(
        f"/api/v1/admin/users/{other_id}/project-memberships",
        headers={"X-Usis-User-Id": uid},
        json={"project_ids": [pid]},
    )
    assert r.status_code == 403


def test_me_capabilities_project_scope(client, no_dev_admin):
    with client.application.app_context():
        u, _ = _mk_user_with_role("estimator")
        db.session.commit()
        uid = str(u.id)

    r = client.get("/api/v1/me", headers={"X-Usis-User-Id": uid})
    assert r.status_code == 200
    caps = r.get_json()["capabilities"]
    assert caps["project_scope"] == "assigned"
    assert caps["assigned_project_count"] == 0
