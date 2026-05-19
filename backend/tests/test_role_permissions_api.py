"""Role module permissions API and enforcement."""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import delete, select

from app.extensions import db
from app.models import Role, RoleModulePermission, User, UserRole
from app.permissions.access import effective_permissions_for_user


@pytest.fixture
def no_dev_admin(monkeypatch):
    monkeypatch.setenv("USIS_API_DEV_ALLOW_ANY", "0")


@pytest.fixture
def standard_role(client, no_dev_admin):
    with client.application.app_context():
        role = db.session.scalar(select(Role).where(Role.code == "standard"))
        if role is None:
            role = Role(code="standard", name="Standard")
            db.session.add(role)
            db.session.flush()
        db.session.execute(delete(RoleModulePermission).where(RoleModulePermission.role_id == role.id))
        db.session.add(
            RoleModulePermission(role_id=role.id, module_code="leads", access_level="write")
        )
        db.session.add(
            RoleModulePermission(role_id=role.id, module_code="user_admin", access_level="none")
        )
        db.session.commit()
        yield role


def test_list_roles_includes_permissions(client, standard_role):
    with client.application.app_context():
        admin = User(
            email="perm_admin_" + uuid.uuid4().hex[:8] + "@t.com",
            is_active=True,
            is_superuser=True,
        )
        db.session.add(admin)
        db.session.commit()
        uid = str(admin.id)

    r = client.get("/api/v1/admin/roles", headers={"X-Usis-User-Id": uid})
    assert r.status_code == 200
    items = r.get_json()["items"]
    std = next(x for x in items if x["code"] == "standard")
    assert std["permissions"]["leads"] == "write"
    assert std["permissions"]["user_admin"] == "none"


def test_patch_role_permissions(client, standard_role):
    with client.application.app_context():
        admin = User(
            email="perm_patch_" + uuid.uuid4().hex[:8] + "@t.com",
            is_active=True,
            is_superuser=True,
        )
        db.session.add(admin)
        db.session.commit()
        uid = str(admin.id)
        rid = str(standard_role.id)

    r = client.patch(
        f"/api/v1/admin/roles/{rid}",
        headers={"X-Usis-User-Id": uid},
        json={"permissions": {"projects": "read", "user_admin": "none"}},
    )
    assert r.status_code == 200
    perms = r.get_json()["item"]["permissions"]
    assert perms["projects"] == "read"


def test_me_includes_project_scope_for_cm_role(client):
    with client.application.app_context():
        role = db.session.scalar(select(Role).where(Role.code == "project_manager"))
        if role is None:
            role = Role(code="project_manager", name="Project Manager")
            db.session.add(role)
            db.session.flush()
        u = User(email="pm_cap_" + uuid.uuid4().hex[:8] + "@t.com", is_active=True)
        db.session.add(u)
        db.session.flush()
        db.session.add(UserRole(user_id=u.id, role_id=role.id))
        db.session.commit()
        uid = str(u.id)

    r = client.get("/api/v1/me", headers={"X-Usis-User-Id": uid})
    assert r.status_code == 200
    caps = r.get_json()["capabilities"]
    assert caps["project_scope"] == "assigned"
    assert caps["assigned_project_count"] == 0


def test_me_includes_capabilities(client, standard_role):
    with client.application.app_context():
        u = User(email="perm_me_" + uuid.uuid4().hex[:8] + "@t.com", is_active=True)
        db.session.add(u)
        db.session.flush()
        db.session.add(UserRole(user_id=u.id, role_id=standard_role.id))
        db.session.commit()
        uid = str(u.id)

    r = client.get("/api/v1/me", headers={"X-Usis-User-Id": uid})
    assert r.status_code == 200
    body = r.get_json()
    assert "capabilities" in body
    assert body["capabilities"]["modules"]["leads"] == "write"
    assert body["capabilities"]["modules"]["user_admin"] == "none"


def test_module_guard_blocks_admin_users(client, standard_role):
    with client.application.app_context():
        u = User(email="perm_blk_" + uuid.uuid4().hex[:8] + "@t.com", is_active=True)
        db.session.add(u)
        db.session.flush()
        db.session.add(UserRole(user_id=u.id, role_id=standard_role.id))
        db.session.commit()
        uid = str(u.id)

    r = client.get("/api/v1/admin/users", headers={"X-Usis-User-Id": uid})
    assert r.status_code == 403


def test_effective_permissions_merge(client, standard_role):
    with client.application.app_context():
        role2 = Role(code="extra_" + uuid.uuid4().hex[:6], name="Extra")
        db.session.add(role2)
        db.session.flush()
        db.session.add(
            RoleModulePermission(role_id=role2.id, module_code="projects", access_level="admin")
        )
        u = User(email="merge_" + uuid.uuid4().hex[:8] + "@t.com", is_active=True)
        db.session.add(u)
        db.session.flush()
        db.session.add(UserRole(user_id=u.id, role_id=standard_role.id))
        db.session.add(UserRole(user_id=u.id, role_id=role2.id))
        db.session.commit()
        db.session.refresh(u)
        perms = effective_permissions_for_user(u)
        assert perms["projects"] == "admin"
        assert perms["leads"] == "write"
