"""In-app staff messenger."""
from __future__ import annotations

import uuid

import pytest

from app.extensions import db
from app.models import User


@pytest.fixture
def no_dev_admin(monkeypatch):
    monkeypatch.setenv("USIS_API_DEV_ALLOW_ANY", "0")


def _user(email: str, first: str, last: str) -> User:
    u = User(email=email, first_name=first, last_name=last, is_active=True)
    db.session.add(u)
    db.session.flush()
    return u


def test_send_and_receive_message(client, no_dev_admin):
    from app.api._messenger_service import register_on_app

    register_on_app(client.application)
    with client.application.app_context():
        alice = _user("alice_" + uuid.uuid4().hex[:8] + "@t.com", "Alice", "Stone")
        bob = _user("bob_" + uuid.uuid4().hex[:8] + "@t.com", "Bob", "River")
        db.session.commit()
        alice_id = str(alice.id)
        bob_id = str(bob.id)

    opened = client.post(
        "/api/v1/me/chat/conversations",
        json={"user_id": bob_id},
        headers={"X-Usis-User-Id": alice_id},
    )
    assert opened.status_code == 200, opened.get_data(as_text=True)
    conv_id = opened.get_json()["item"]["id"]
    assert opened.get_json()["item"]["other"]["name"] == "Bob River"

    sent = client.post(
        f"/api/v1/me/chat/conversations/{conv_id}/messages",
        json={"body": "Need you on the jobsite at 7."},
        headers={"X-Usis-User-Id": alice_id},
    )
    assert sent.status_code == 200, sent.get_data(as_text=True)
    body = sent.get_json()["item"]
    assert body["body"] == "Need you on the jobsite at 7."
    assert body["mine"] is True

    listed = client.get(
        "/api/v1/me/chat/conversations",
        headers={"X-Usis-User-Id": bob_id},
    )
    assert listed.status_code == 200
    items = listed.get_json()["items"]
    assert len(items) == 1
    assert items[0]["unread"] == 1
    assert items[0]["other"]["name"] == "Alice Stone"
    assert "jobsite" in items[0]["last_message"]["body"]

    inbox = client.get(
        f"/api/v1/me/chat/conversations/{conv_id}/messages",
        headers={"X-Usis-User-Id": bob_id},
    )
    assert inbox.status_code == 200
    msgs = inbox.get_json()["items"]
    assert len(msgs) == 1
    assert msgs[0]["mine"] is False
    assert msgs[0]["body"] == "Need you on the jobsite at 7."

    unread = client.get("/api/v1/me/chat/unread-count", headers={"X-Usis-User-Id": bob_id})
    assert unread.get_json()["unread"] == 1

    read = client.post(
        f"/api/v1/me/chat/conversations/{conv_id}/read",
        headers={"X-Usis-User-Id": bob_id},
    )
    assert read.status_code == 200
    assert read.get_json()["item"]["unread"] == 0

    again = client.get("/api/v1/me/chat/unread-count", headers={"X-Usis-User-Id": bob_id})
    assert again.get_json()["unread"] == 0

    reply = client.post(
        f"/api/v1/me/chat/conversations/{conv_id}/messages",
        json={"body": "On my way."},
        headers={"X-Usis-User-Id": bob_id},
    )
    assert reply.status_code == 200

    polled = client.get(
        f"/api/v1/me/chat/conversations/{conv_id}/messages?after={body['id']}",
        headers={"X-Usis-User-Id": alice_id},
    )
    assert polled.status_code == 200
    new_msgs = polled.get_json()["items"]
    assert len(new_msgs) == 1
    assert new_msgs[0]["body"] == "On my way."

    people = client.get(
        "/api/v1/me/chat/users?q=bob",
        headers={"X-Usis-User-Id": alice_id},
    )
    assert people.status_code == 200
    names = [u["name"] for u in people.get_json()["items"]]
    assert "Bob River" in names
    assert "Alice Stone" not in names


def test_cannot_message_self(client, no_dev_admin):
    from app.api._messenger_service import register_on_app

    register_on_app(client.application)
    with client.application.app_context():
        u = _user("solo_" + uuid.uuid4().hex[:8] + "@t.com", "Solo", "User")
        db.session.commit()
        uid = str(u.id)

    r = client.post(
        "/api/v1/me/chat/conversations",
        json={"user_id": uid},
        headers={"X-Usis-User-Id": uid},
    )
    assert r.status_code == 400


def test_messenger_requires_sign_in(client, no_dev_admin):
    from app.api._messenger_service import register_on_app

    register_on_app(client.application)
    r = client.get("/api/v1/me/chat/conversations")
    assert r.status_code in (401, 403)


def test_reuses_existing_conversation(client, no_dev_admin):
    from app.api._messenger_service import register_on_app

    register_on_app(client.application)
    with client.application.app_context():
        a = _user("a_" + uuid.uuid4().hex[:8] + "@t.com", "Ann", "One")
        b = _user("b_" + uuid.uuid4().hex[:8] + "@t.com", "Ben", "Two")
        db.session.commit()
        aid, bid = str(a.id), str(b.id)

    first = client.post(
        "/api/v1/me/chat/conversations",
        json={"user_id": bid},
        headers={"X-Usis-User-Id": aid},
    )
    second = client.post(
        "/api/v1/me/chat/conversations",
        json={"user_id": aid},
        headers={"X-Usis-User-Id": bid},
    )
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.get_json()["item"]["id"] == second.get_json()["item"]["id"]
