"""Session login (``/auth/login``) and ``GET /api/v1/auth/status``."""
from __future__ import annotations

import uuid
from urllib.parse import quote, unquote

import pytest
from werkzeug.security import generate_password_hash

from app.extensions import db
from app.models import User


@pytest.fixture
def no_dev_admin(monkeypatch):
    monkeypatch.setenv("USIS_API_DEV_ALLOW_ANY", "0")


def test_auth_status_unauthenticated(client, no_dev_admin):
    r = client.get("/api/v1/auth/status")
    assert r.status_code == 200
    body = r.get_json()
    assert body["authenticated"] is False
    assert body["user"] is None
    assert body.get("microsoft_sso_enabled") is False


def test_login_get_redirects_to_shell_template(client):
    r = client.get(
        "/auth/login",
        headers={"Referer": "http://127.0.0.1:3000/construction/index.html"},
        follow_redirects=False,
    )
    assert r.status_code == 302
    loc = unquote(r.headers.get("Location") or "")
    assert "page-login.html" in loc
    assert loc.startswith("http://127.0.0.1:3000")


def test_login_get_redirect_preserves_next_query(client):
    target = "http://127.0.0.1:3000/usis-dashboard-dark.html"
    r = client.get(
        "/auth/login",
        query_string={"next": target},
        headers={"Referer": "http://127.0.0.1:3000/foo.html"},
        follow_redirects=False,
    )
    assert r.status_code == 302
    loc = unquote(r.headers.get("Location") or "")
    assert "page-login.html" in loc
    assert "next=" in loc
    assert "usis-dashboard" in loc


def test_session_login_and_auth_status(client, no_dev_admin):
    email = "login_" + uuid.uuid4().hex[:10] + "@t.com"
    with client.application.app_context():
        u = User(
            email=email,
            first_name="L",
            last_name="N",
            password_hash=generate_password_hash("correct-horse"),
            is_active=True,
        )
        db.session.add(u)
        db.session.commit()

    bad = client.post("/auth/login", data={"email": email, "password": "wrong"})
    assert bad.status_code == 302
    loc = unquote(bad.headers.get("Location") or "")
    assert "page-login.html" in loc
    assert "login_error=invalid" in loc

    ok = client.post(
        "/auth/login",
        data={"email": email, "password": "correct-horse", "remember": "1"},
        follow_redirects=False,
    )
    assert ok.status_code == 302

    st = client.get("/api/v1/auth/status")
    assert st.status_code == 200
    body = st.get_json()
    assert body["authenticated"] is True
    assert body["user"]["email"] == email
    assert body["user"]["first_name"] == "L"


def test_login_respects_safe_next_redirect(client, no_dev_admin):
    email = "next_" + uuid.uuid4().hex[:10] + "@t.com"
    with client.application.app_context():
        u = User(
            email=email,
            first_name="N",
            last_name="X",
            password_hash=generate_password_hash("pw-next-1"),
            is_active=True,
        )
        db.session.add(u)
        db.session.commit()

    target = "http://127.0.0.1:3000/usis-custom-landing.html"
    ok = client.post(
        "/auth/login",
        data={"email": email, "password": "pw-next-1", "next": target},
        follow_redirects=False,
    )
    assert ok.status_code == 302
    assert ok.headers.get("Location") == target


def test_login_respects_relative_next_redirect(client, no_dev_admin):
    email = "relnext_" + uuid.uuid4().hex[:10] + "@t.com"
    with client.application.app_context():
        u = User(
            email=email,
            first_name="R",
            last_name="N",
            password_hash=generate_password_hash("pw-rel-1"),
            is_active=True,
        )
        db.session.add(u)
        db.session.commit()

    ok = client.post(
        "/auth/login",
        data={"email": email, "password": "pw-rel-1", "next": "usis-hr-hire.html"},
        headers={"Referer": "http://127.0.0.1:3000/page-login.html?next=usis-hr-hire.html"},
        follow_redirects=False,
    )
    assert ok.status_code == 302
    assert ok.headers.get("Location") == "http://127.0.0.1:3000/usis-hr-hire.html"


def test_login_ignores_untrusted_next(client, no_dev_admin):
    email = "badnext_" + uuid.uuid4().hex[:8] + "@t.com"
    with client.application.app_context():
        u = User(
            email=email,
            first_name="B",
            last_name="N",
            password_hash=generate_password_hash("pw-bad-1"),
            is_active=True,
        )
        db.session.add(u)
        db.session.commit()

    ok = client.post(
        "/auth/login",
        data={
            "email": email,
            "password": "pw-bad-1",
            "next": "https://evil.example/phish",
        },
        follow_redirects=False,
    )
    assert ok.status_code == 302
    assert ok.headers.get("Location") == "http://127.0.0.1:3000/usis-dashboard-dark.html"


def test_logout_redirects_to_safe_next(client, no_dev_admin):
    email = "lo_" + uuid.uuid4().hex[:10] + "@t.com"
    with client.application.app_context():
        u = User(
            email=email,
            first_name="L",
            last_name="O",
            password_hash=generate_password_hash("pw-lo-1"),
            is_active=True,
        )
        db.session.add(u)
        db.session.commit()

    client.post("/auth/login", data={"email": email, "password": "pw-lo-1"})
    shell = "http://127.0.0.1:3000/page-login.html"

    out = client.get("/auth/logout?next=" + quote(shell, safe=""), follow_redirects=False)
    assert out.status_code == 302
    assert unquote(out.headers.get("Location") or "") == shell


def test_logout_clears_session(client, no_dev_admin):
    email = "out_" + uuid.uuid4().hex[:10] + "@t.com"
    with client.application.app_context():
        u = User(
            email=email,
            first_name="O",
            last_name="T",
            password_hash=generate_password_hash("pw-out-1"),
            is_active=True,
        )
        db.session.add(u)
        db.session.commit()

    client.post("/auth/login", data={"email": email, "password": "pw-out-1"})
    assert client.get("/api/v1/auth/status").get_json()["authenticated"] is True

    out = client.get("/auth/logout", follow_redirects=False)
    assert out.status_code == 302
    assert client.get("/api/v1/auth/status").get_json()["authenticated"] is False


def test_auth_register_creates_session_and_hire_wizard(client, no_dev_admin, monkeypatch):
    monkeypatch.setitem(client.application.config, "USIS_ALLOW_SELF_REGISTER", True)
    email = "hire_" + uuid.uuid4().hex[:10] + "@t.com"
    r = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "hire-test-pw",
            "first_name": "Pat",
            "last_name": "Applicant",
        },
    )
    assert r.status_code == 201
    assert r.get_json().get("ok") is True

    st = client.get("/api/v1/auth/status")
    assert st.get_json()["authenticated"] is True

    w = client.get("/api/v1/hr/me/hire-wizard")
    assert w.status_code == 200
    body = w.get_json()
    assert body.get("tasks")
    assert body["tasks"][0]["key"] == "account"
    assert body["tasks"][0]["status"] == "complete"
