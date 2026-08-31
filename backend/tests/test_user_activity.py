"""Per-user last login and activity tracking."""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select
from werkzeug.security import generate_password_hash

from app.extensions import db
from app.models import Role, User, UserActivityEvent, UserRole


@pytest.fixture
def no_dev_admin(monkeypatch):
    monkeypatch.setenv("USIS_API_DEV_ALLOW_ANY", "0")


def _admin(client) -> str:
    email = "act_adm_" + uuid.uuid4().hex[:8] + "@t.com"
    with client.application.app_context():
        u = User(
            email=email,
            first_name="Act",
            last_name="Admin",
            is_superuser=True,
            is_active=True,
            password_hash=generate_password_hash("pw-act-1"),
        )
        db.session.add(u)
        db.session.flush()
        uid = str(u.id)
        db.session.commit()
        return uid


def test_password_login_sets_last_login_and_event(client, no_dev_admin):
    email = "act_login_" + uuid.uuid4().hex[:8] + "@t.com"
    with client.application.app_context():
        u = User(
            email=email,
            first_name="Pat",
            last_name="Login",
            password_hash=generate_password_hash("correct-horse"),
            is_active=True,
        )
        db.session.add(u)
        db.session.flush()
        uid = u.id
        db.session.commit()

    ok = client.post(
        "/auth/login",
        data={"email": email, "password": "correct-horse"},
        follow_redirects=False,
    )
    assert ok.status_code == 302

    with client.application.app_context():
        u = db.session.get(User, uid)
        assert u is not None
        assert u.last_login_at is not None
        assert u.last_seen_at is not None
        n = db.session.scalar(
            select(UserActivityEvent)
            .where(UserActivityEvent.user_id == uid, UserActivityEvent.event_type == "login")
            .order_by(UserActivityEvent.created_at.desc())
        )
        assert n is not None
        assert "password" in (n.summary or "")


def test_page_view_and_admin_activity(client, no_dev_admin):
    aid = _admin(client)
    hdr = {"X-Usis-User-Id": aid}

    r = client.post(
        "/api/v1/me/activity/page-view",
        json={"path": "/construction/projects.html", "title": "USIS"},
        headers=hdr,
    )
    assert r.status_code == 200, r.get_data(as_text=True)
    body = r.get_json()
    assert body["ok"] is True
    assert body["recorded"] is True

    dup = client.post(
        "/api/v1/me/activity/page-view",
        json={"path": "/construction/projects.html"},
        headers=hdr,
    )
    assert dup.status_code == 200
    assert dup.get_json()["recorded"] is False

    summary = client.get("/api/v1/admin/activity/summary?days=7", headers=hdr)
    assert summary.status_code == 200
    items = summary.get_json()["items"]
    me = next(x for x in items if x["id"] == aid)
    assert me["last_seen_at"] is not None
    assert me["actions_today"] >= 1

    feed = client.get(f"/api/v1/admin/activity?user_id={aid}&event_type=page_view", headers=hdr)
    assert feed.status_code == 200
    rows = feed.get_json()["items"]
    assert any("Project" in (x.get("summary") or "") or "projects" in (x.get("path") or "") for x in rows)


def test_api_write_is_logged(client, no_dev_admin):
    aid = _admin(client)
    hdr = {"X-Usis-User-Id": aid, "Content-Type": "application/json"}
    email = "act_new_" + uuid.uuid4().hex[:8] + "@t.com"
    r = client.post(
        "/api/v1/admin/users",
        json={"email": email, "first_name": "New", "last_name": "Staff"},
        headers=hdr,
    )
    assert r.status_code == 201, r.get_data(as_text=True)

    feed = client.get(f"/api/v1/admin/activity?user_id={aid}&event_type=api_write", headers=hdr)
    assert feed.status_code == 200
    summaries = [x.get("summary") or "" for x in feed.get_json()["items"]]
    assert any("user account" in s.lower() or "admin/users" in s.lower() for s in summaries)


def test_activity_requires_admin(client, no_dev_admin):
    with client.application.app_context():
        role = db.session.scalar(select(Role).where(Role.code == "standard"))
        if role is None:
            role = Role(code="standard", name="Standard")
            db.session.add(role)
            db.session.flush()
        u = User(email="act_std_" + uuid.uuid4().hex[:8] + "@t.com", first_name="S", last_name="T")
        db.session.add(u)
        db.session.flush()
        db.session.add(UserRole(user_id=u.id, role_id=role.id))
        uid = str(u.id)
        db.session.commit()

    r = client.get("/api/v1/admin/activity", headers={"X-Usis-User-Id": uid})
    assert r.status_code == 403


def test_admin_users_include_last_seen(client, no_dev_admin):
    aid = _admin(client)
    hdr = {"X-Usis-User-Id": aid}
    r = client.get("/api/v1/admin/users?limit=5", headers=hdr)
    assert r.status_code == 200
    item = r.get_json()["items"][0]
    assert "last_login_at" in item
    assert "last_seen_at" in item
