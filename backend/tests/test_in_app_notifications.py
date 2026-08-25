"""Header in-app notifications."""
from __future__ import annotations

import uuid

import pytest

from app.api._in_app_notifications import create_in_app_notification
from app.extensions import db
from app.models import User


@pytest.fixture
def no_dev_admin(monkeypatch):
    monkeypatch.setenv("USIS_API_DEV_ALLOW_ANY", "0")


def test_list_and_mark_read(client, no_dev_admin):
    from app.api._in_app_notifications import register_on_app

    register_on_app(client.application)
    with client.application.app_context():
        u = User(email="notif_" + uuid.uuid4().hex[:8] + "@t.com", is_active=True)
        db.session.add(u)
        db.session.flush()
        create_in_app_notification(
            user_id=u.id,
            title="Projects access restored",
            body="You can open Projects again.",
            url="/construction/projects.html",
        )
        db.session.commit()
        uid = str(u.id)

    listed = client.get("/api/v1/me/notifications", headers={"X-Usis-User-Id": uid})
    assert listed.status_code == 200
    body = listed.get_json()
    assert body["unread"] == 1
    assert body["items"][0]["title"] == "Projects access restored"
    nid = body["items"][0]["id"]

    marked = client.post(
        f"/api/v1/me/notifications/{nid}/read",
        headers={"X-Usis-User-Id": uid},
    )
    assert marked.status_code == 200
    assert marked.get_json()["item"]["read"] is True

    again = client.get("/api/v1/me/notifications", headers={"X-Usis-User-Id": uid})
    assert again.get_json()["unread"] == 0


def test_notifications_require_sign_in(client, no_dev_admin):
    from app.api._in_app_notifications import register_on_app

    register_on_app(client.application)
    r = client.get("/api/v1/me/notifications")
    assert r.status_code in (401, 403)


def test_notify_user_by_email(client, no_dev_admin):
    from app.api._in_app_notifications import notify_user_by_email, register_on_app

    register_on_app(client.application)
    with client.application.app_context():
        email = "bell_" + uuid.uuid4().hex[:8] + "@t.com"
        u = User(email=email, is_active=True)
        db.session.add(u)
        db.session.flush()
        row = notify_user_by_email(
            email=email,
            title="Please confirm issue #10",
            body="The issue is closed.",
            url="/usis-issue-confirm.html?issue=10",
        )
        db.session.commit()
        uid = str(u.id)
        assert row is not None
        assert row.payload.get("url") == "/usis-issue-confirm.html?issue=10"

    listed = client.get("/api/v1/me/notifications", headers={"X-Usis-User-Id": uid})
    assert listed.status_code == 200
    item = listed.get_json()["items"][0]
    assert item["url"] == "/usis-issue-confirm.html?issue=10"
