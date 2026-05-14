"""``GET/PATCH /api/v1/me`` — signed-in user profile."""
from __future__ import annotations

import uuid

import pytest
from werkzeug.security import generate_password_hash

from app.extensions import db
from app.models import User


@pytest.fixture
def no_dev_admin(monkeypatch):
    monkeypatch.setenv("USIS_API_DEV_ALLOW_ANY", "0")


def test_me_requires_session(client, no_dev_admin):
    r = client.get("/api/v1/me")
    assert r.status_code == 401


def test_me_get_and_patch(client, no_dev_admin):
    email = "prof_" + uuid.uuid4().hex[:8] + "@t.com"
    with client.application.app_context():
        u = User(
            email=email,
            first_name="Pat",
            last_name="Lee",
            phone="555-0000",
            password_hash=generate_password_hash("old-secret-9"),
            is_active=True,
            is_superuser=False,
        )
        db.session.add(u)
        db.session.commit()
        uid = str(u.id)

    client.post("/auth/login", data={"email": email, "password": "old-secret-9"})

    g = client.get("/api/v1/me")
    assert g.status_code == 200
    body = g.get_json()
    assert body["item"]["email"] == email
    assert body["item"]["first_name"] == "Pat"

    p = client.patch(
        "/api/v1/me",
        json={"first_name": "Patricia", "last_name": "Leeds", "phone": "555-1111"},
    )
    assert p.status_code == 200
    item = p.get_json()["item"]
    assert item["first_name"] == "Patricia"
    assert item["last_name"] == "Leeds"
    assert item["phone"] == "555-1111"

    pw = client.patch("/api/v1/me", json={"password": "new-secret-9"})
    assert pw.status_code == 200

    client.get("/auth/logout")
    bad = client.post("/auth/login", data={"email": email, "password": "old-secret-9"})
    assert bad.status_code == 302

    ok = client.post("/auth/login", data={"email": email, "password": "new-secret-9"})
    assert ok.status_code == 302
    me2 = client.get("/api/v1/me")
    assert me2.get_json()["item"]["id"] == uid


def test_me_patch_rejects_privilege_fields(client, no_dev_admin):
    email = "priv_" + uuid.uuid4().hex[:8] + "@t.com"
    with client.application.app_context():
        u = User(
            email=email,
            first_name="A",
            last_name="B",
            password_hash=generate_password_hash("pw-1"),
            is_active=True,
            is_superuser=False,
        )
        db.session.add(u)
        db.session.commit()

    client.post("/auth/login", data={"email": email, "password": "pw-1"})
    r = client.patch("/api/v1/me", json={"is_superuser": True})
    assert r.status_code == 400
    assert "is_superuser" in (r.get_json() or {}).get("error", "")
