"""X-Usis-User-Id / ?as_user= impersonation is development-only."""
from __future__ import annotations

import uuid

import pytest

from app.extensions import db
from app.models import User


@pytest.fixture
def no_dev_admin(monkeypatch):
    monkeypatch.setenv("USIS_API_DEV_ALLOW_ANY", "0")


def _mk_user(email_prefix: str = "actor") -> User:
    u = User(email=f"{email_prefix}_{uuid.uuid4().hex[:8]}@t.com", is_active=True)
    db.session.add(u)
    db.session.commit()
    return u


def test_actor_header_works_in_development(client, no_dev_admin):
    with client.application.app_context():
        u = _mk_user("dev_ok")
        uid = str(u.id)

    r = client.get("/api/v1/me", headers={"X-Usis-User-Id": uid})
    assert r.status_code == 200
    assert r.get_json()["item"]["id"] == uid


def test_actor_header_ignored_in_production(client, no_dev_admin, monkeypatch):
    monkeypatch.setenv("FLASK_ENV", "production")
    monkeypatch.delenv("USIS_ALLOW_ACTOR_HEADER", raising=False)
    with client.application.app_context():
        target = _mk_user("prod_target")
        signed = _mk_user("prod_sess")
        target_id, signed_id = str(target.id), str(signed.id)

    denied = client.get("/api/v1/me", headers={"X-Usis-User-Id": target_id})
    assert denied.status_code == 401

    qs = client.get(f"/api/v1/me?as_user={target_id}")
    assert qs.status_code == 401

    with client.session_transaction() as sess:
        sess["user_id"] = signed_id
    hijack = client.get("/api/v1/me", headers={"X-Usis-User-Id": target_id})
    assert hijack.status_code == 200
    assert hijack.get_json()["item"]["id"] == signed_id


def test_actor_header_explicit_opt_in_in_production(client, no_dev_admin, monkeypatch):
    monkeypatch.setenv("FLASK_ENV", "production")
    monkeypatch.setenv("USIS_ALLOW_ACTOR_HEADER", "1")
    with client.application.app_context():
        u = _mk_user("forced")
        uid = str(u.id)

    r = client.get("/api/v1/me", headers={"X-Usis-User-Id": uid})
    assert r.status_code == 200
    assert r.get_json()["item"]["id"] == uid
