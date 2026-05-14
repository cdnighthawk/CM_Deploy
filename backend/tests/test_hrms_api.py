"""HRMS API smoke tests."""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.extensions import db
from app.models import Role, User, UserRole


@pytest.fixture
def no_dev_admin(monkeypatch):
    monkeypatch.setenv("USIS_API_DEV_ALLOW_ANY", "0")


def test_hrms_health_no_auth(client):
    r = client.get("/api/v1/hrms/health")
    assert r.status_code == 200
    assert r.get_json()["module"] == "hrms"


def test_hrms_dashboard_requires_user(client, no_dev_admin):
    r = client.get("/api/v1/hrms/dashboard")
    assert r.status_code == 401


def test_hrms_dashboard_ok_with_header(client, no_dev_admin):
    with client.application.app_context():
        u = User(email="hrms_" + uuid.uuid4().hex[:8] + "@t.com", first_name="H", last_name="R")
        db.session.add(u)
        db.session.flush()
        uid = str(u.id)
        db.session.commit()
    r = client.get("/api/v1/hrms/dashboard", headers={"X-Usis-User-Id": uid})
    assert r.status_code == 200
    body = r.get_json()
    assert body["entity"] == "hrms_dashboard"
    assert body["item"]["scope"] == "employee"
    assert "counts" in body["item"]


def test_hrms_admin_scope(client, no_dev_admin):
    with client.application.app_context():
        role = db.session.scalar(select(Role).where(Role.code == "hr_admin"))
        if role is None:
            role = Role(code="hr_admin", name="HR Admin")
            db.session.add(role)
            db.session.flush()
        u = User(email="hradm_" + uuid.uuid4().hex[:8] + "@t.com", first_name="A", last_name="D")
        db.session.add(u)
        db.session.flush()
        db.session.add(UserRole(user_id=u.id, role_id=role.id))
        uid = str(u.id)
        db.session.commit()
    r = client.get("/api/v1/hrms/dashboard", headers={"X-Usis-User-Id": uid})
    assert r.status_code == 200
    assert r.get_json()["item"]["scope"] == "admin"
