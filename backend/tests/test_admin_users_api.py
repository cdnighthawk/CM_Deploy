"""API tests for admin user directory (users + roles)."""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.extensions import db
from app.models import Role, User, UserRole


@pytest.fixture
def no_dev_admin(monkeypatch):
    monkeypatch.setenv("USIS_API_DEV_ALLOW_ANY", "0")


def test_admin_users_requires_admin(client, no_dev_admin):
    with client.application.app_context():
        role = db.session.scalar(select(Role).where(Role.code == "standard"))
        if role is None:
            role = Role(code="standard", name="Standard")
            db.session.add(role)
            db.session.flush()
        u = User(email="std_" + uuid.uuid4().hex[:8] + "@t.com", first_name="S", last_name="T")
        db.session.add(u)
        db.session.flush()
        db.session.add(UserRole(user_id=u.id, role_id=role.id))
        uid = str(u.id)
        db.session.commit()

    r = client.get("/api/v1/admin/users", headers={"X-Usis-User-Id": uid})
    assert r.status_code == 403


def test_admin_users_crud_superuser(client, no_dev_admin):
    with client.application.app_context():
        role = db.session.scalar(select(Role).where(Role.code == "standard"))
        if role is None:
            role = Role(code="standard", name="Standard")
            db.session.add(role)
            db.session.flush()
        admin = User(
            email="adm_" + uuid.uuid4().hex[:8] + "@t.com",
            first_name="Admin",
            last_name="User",
            is_superuser=True,
        )
        db.session.add(admin)
        db.session.flush()
        aid = str(admin.id)
        rid = str(role.id)
        db.session.commit()

    hdr = {"X-Usis-User-Id": aid}

    r0 = client.get("/api/v1/admin/roles", headers=hdr)
    assert r0.status_code == 200
    roles = r0.get_json()["items"]
    std = next(x for x in roles if x["code"] == "standard")
    assert std is not None
    assert "permissions" in std
    assert isinstance(std["permissions"], dict)

    r1 = client.get("/api/v1/admin/users", headers=hdr)
    assert r1.status_code == 200
    assert r1.get_json()["total"] >= 1

    email = "newu_" + uuid.uuid4().hex[:8] + "@t.com"
    r2 = client.post(
        "/api/v1/admin/users",
        json={
            "email": email,
            "first_name": "New",
            "last_name": "Person",
            "password": "secret123",
            "role_ids": [rid],
        },
        headers=hdr,
    )
    assert r2.status_code == 201, r2.get_data(as_text=True)
    new_id = r2.get_json()["item"]["id"]
    assert r2.get_json()["item"]["has_password"] is True

    r3 = client.patch(
        f"/api/v1/admin/users/{new_id}",
        json={"first_name": "Updated", "is_active": True, "role_ids": []},
        headers=hdr,
    )
    assert r3.status_code == 200
    assert r3.get_json()["item"]["first_name"] == "Updated"
    assert r3.get_json()["item"]["roles"] == []

    r4 = client.get(f"/api/v1/admin/users/{new_id}", headers=hdr)
    assert r4.status_code == 200
    assert r4.get_json()["item"]["email"] == email


def test_admin_create_invalid_email(client, no_dev_admin):
    with client.application.app_context():
        admin = User(email="adm2_" + uuid.uuid4().hex[:8] + "@t.com", is_superuser=True)
        db.session.add(admin)
        db.session.flush()
        aid = str(admin.id)
        db.session.commit()
    hdr = {"X-Usis-User-Id": aid}
    r = client.post(
        "/api/v1/admin/users",
        json={"email": "not-an-email"},
        headers=hdr,
    )
    assert r.status_code == 400


def test_admin_users_exclude_applicants_and_delete_staff(client, no_dev_admin):
    from app.permissions.applicant import assign_applicant_role

    with client.application.app_context():
        role = db.session.scalar(select(Role).where(Role.code == "standard"))
        if role is None:
            role = Role(code="standard", name="Standard")
            db.session.add(role)
            db.session.flush()
        admin = User(
            email="adm_del_" + uuid.uuid4().hex[:8] + "@t.com",
            first_name="Admin",
            last_name="Delete",
            is_superuser=True,
        )
        staff = User(
            email="staff_del_" + uuid.uuid4().hex[:8] + "@t.com",
            first_name="Staff",
            last_name="Person",
        )
        applicant = User(
            email="appl_del_" + uuid.uuid4().hex[:8] + "@t.com",
            first_name="Job",
            last_name="Applicant",
        )
        db.session.add_all([admin, staff, applicant])
        db.session.flush()
        db.session.add(UserRole(user_id=staff.id, role_id=role.id))
        assign_applicant_role(applicant)
        aid = str(admin.id)
        staff_id = str(staff.id)
        applicant_id = str(applicant.id)
        staff_email = staff.email
        applicant_email = applicant.email
        db.session.commit()

    hdr = {"X-Usis-User-Id": aid}

    listed = client.get("/api/v1/admin/users?limit=500", headers=hdr)
    assert listed.status_code == 200
    emails = {row["email"] for row in listed.get_json()["items"]}
    assert staff_email in emails
    assert applicant_email not in emails

    included = client.get("/api/v1/admin/users?limit=500&include_applicants=1", headers=hdr)
    assert included.status_code == 200
    included_emails = {row["email"] for row in included.get_json()["items"]}
    assert applicant_email in included_emails

    refuse_applicant = client.delete(
        f"/api/v1/admin/users/{applicant_id}",
        json={"confirm": True},
        headers=hdr,
    )
    assert refuse_applicant.status_code == 400

    refuse_self = client.delete(
        f"/api/v1/admin/users/{aid}",
        json={"confirm": True},
        headers=hdr,
    )
    assert refuse_self.status_code == 400

    deleted = client.delete(
        f"/api/v1/admin/users/{staff_id}",
        json={"confirm": True},
        headers=hdr,
    )
    assert deleted.status_code == 200, deleted.get_data(as_text=True)
    assert deleted.get_json()["deleted"] is True

    gone = client.get(f"/api/v1/admin/users/{staff_id}", headers=hdr)
    assert gone.status_code == 404
