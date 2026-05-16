"""Mobile Bearer auth (``/api/v1/auth/mobile/*``)."""
from __future__ import annotations

import uuid

import jwt
import pytest
from werkzeug.security import generate_password_hash

from app.extensions import db
from app.models import User


@pytest.fixture
def no_dev_admin(monkeypatch):
    monkeypatch.setenv("USIS_API_DEV_ALLOW_ANY", "0")


def _create_user(client, email: str, password: str, *, active: bool = True) -> User:
    with client.application.app_context():
        u = User(
            email=email,
            first_name="M",
            last_name="T",
            password_hash=generate_password_hash(password),
            is_active=active,
        )
        db.session.add(u)
        db.session.commit()
        return u


def test_mobile_login_success(client, no_dev_admin):
    email = f"mobile_{uuid.uuid4().hex[:10]}@t.com"
    _create_user(client, email, "correct-horse")

    r = client.post(
        "/api/v1/auth/mobile/login",
        json={"email": email, "password": "correct-horse"},
    )
    assert r.status_code == 200
    body = r.get_json()
    assert body["token_type"] == "Bearer"
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["expires_in"] > 0
    assert body["user"]["email"] == email


def test_mobile_login_invalid_password(client, no_dev_admin):
    email = f"mobile_{uuid.uuid4().hex[:10]}@t.com"
    _create_user(client, email, "correct-horse")

    r = client.post(
        "/api/v1/auth/mobile/login",
        json={"email": email, "password": "wrong"},
    )
    assert r.status_code == 401


def test_mobile_login_inactive_user(client, no_dev_admin):
    email = f"mobile_{uuid.uuid4().hex[:10]}@t.com"
    _create_user(client, email, "correct-horse", active=False)

    r = client.post(
        "/api/v1/auth/mobile/login",
        json={"email": email, "password": "correct-horse"},
    )
    assert r.status_code == 401


def test_bearer_protects_projects(client, no_dev_admin):
    email = f"mobile_{uuid.uuid4().hex[:10]}@t.com"
    _create_user(client, email, "correct-horse")

    anon = client.get("/api/v1/projects")
    assert anon.status_code == 401

    login = client.post(
        "/api/v1/auth/mobile/login",
        json={"email": email, "password": "correct-horse"},
    )
    token = login.get_json()["access_token"]

    ok = client.get(
        "/api/v1/projects",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert ok.status_code == 200
    assert ok.get_json()["entity"] == "projects"


def test_auth_status_with_bearer(client, no_dev_admin):
    email = f"mobile_{uuid.uuid4().hex[:10]}@t.com"
    _create_user(client, email, "correct-horse")

    login = client.post(
        "/api/v1/auth/mobile/login",
        json={"email": email, "password": "correct-horse"},
    )
    token = login.get_json()["access_token"]

    st = client.get(
        "/api/v1/auth/status",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert st.status_code == 200
    body = st.get_json()
    assert body["authenticated"] is True
    assert body["user"]["email"] == email


def test_mobile_refresh_rotates(client, no_dev_admin):
    email = f"mobile_{uuid.uuid4().hex[:10]}@t.com"
    _create_user(client, email, "correct-horse")

    login = client.post(
        "/api/v1/auth/mobile/login",
        json={"email": email, "password": "correct-horse"},
    )
    old_refresh = login.get_json()["refresh_token"]

    ref = client.post(
        "/api/v1/auth/mobile/refresh",
        json={"refresh_token": old_refresh},
    )
    assert ref.status_code == 200
    body = ref.get_json()
    assert body["access_token"]
    assert body["refresh_token"] != old_refresh

    stale = client.post(
        "/api/v1/auth/mobile/refresh",
        json={"refresh_token": old_refresh},
    )
    assert stale.status_code == 401


def test_mobile_logout_revokes_refresh(client, no_dev_admin):
    email = f"mobile_{uuid.uuid4().hex[:10]}@t.com"
    _create_user(client, email, "correct-horse")

    login = client.post(
        "/api/v1/auth/mobile/login",
        json={"email": email, "password": "correct-horse"},
    )
    refresh = login.get_json()["refresh_token"]

    out = client.post(
        "/api/v1/auth/mobile/logout",
        json={"refresh_token": refresh},
    )
    assert out.status_code == 200

    ref = client.post(
        "/api/v1/auth/mobile/refresh",
        json={"refresh_token": refresh},
    )
    assert ref.status_code == 401


def test_expired_access_token_rejected(client, no_dev_admin):
    email = f"mobile_{uuid.uuid4().hex[:10]}@t.com"
    u = _create_user(client, email, "correct-horse")

    with client.application.app_context():
        from datetime import datetime, timedelta, timezone

        payload = {
            "sub": str(u.id),
            "type": "access",
            "iat": int(datetime.now(timezone.utc).timestamp()),
            "exp": int((datetime.now(timezone.utc) - timedelta(hours=1)).timestamp()),
        }
        bad = jwt.encode(
            payload,
            client.application.config["SECRET_KEY"],
            algorithm="HS256",
        )
        if isinstance(bad, bytes):
            bad = bad.decode("ascii")

    r = client.get(
        "/api/v1/projects",
        headers={"Authorization": f"Bearer {bad}"},
    )
    assert r.status_code == 401
