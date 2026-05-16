"""Microsoft Entra SSO routes (``/auth/microsoft/*``)."""
from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest
from werkzeug.security import generate_password_hash

from app.extensions import db
from app.models import User


@pytest.fixture
def no_dev_admin(monkeypatch):
    monkeypatch.setenv("USIS_API_DEV_ALLOW_ANY", "0")


def test_microsoft_start_not_configured_redirects(client, no_dev_admin):
    r = client.get("/auth/microsoft/start", follow_redirects=False)
    assert r.status_code == 302
    loc = r.headers.get("Location") or ""
    assert "page-login.html" in loc
    assert "ms_error=not_configured" in loc


def test_microsoft_start_redirects_to_microsoft_when_configured(client, no_dev_admin, monkeypatch):
    monkeypatch.setenv("MS_ENTRA_TENANT_ID", "11111111-1111-1111-1111-111111111111")
    monkeypatch.setenv("MS_ENTRA_CLIENT_ID", "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    monkeypatch.setenv("MS_ENTRA_CLIENT_SECRET", "secret-value")
    monkeypatch.setenv("MS_ENTRA_REDIRECT_URI", "http://127.0.0.1:5000/auth/microsoft/callback")
    client.application.config["MS_ENTRA_TENANT_ID"] = "11111111-1111-1111-1111-111111111111"
    client.application.config["MS_ENTRA_CLIENT_ID"] = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    client.application.config["MS_ENTRA_CLIENT_SECRET"] = "secret-value"
    client.application.config["MS_ENTRA_REDIRECT_URI"] = "http://127.0.0.1:5000/auth/microsoft/callback"

    r = client.get(
        "/auth/microsoft/start",
        query_string={"next": "http://127.0.0.1:3000/usis-dashboard-dark.html"},
        follow_redirects=False,
    )
    assert r.status_code == 302
    loc = r.headers.get("Location") or ""
    assert loc.startswith("https://login.microsoftonline.com/")
    assert "oauth2/v2.0/authorize" in loc
    assert "client_id=aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa" in loc


def test_microsoft_callback_not_registered(client, no_dev_admin, monkeypatch):
    monkeypatch.setenv("MS_ENTRA_TENANT_ID", "11111111-1111-1111-1111-111111111111")
    monkeypatch.setenv("MS_ENTRA_CLIENT_ID", "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    monkeypatch.setenv("MS_ENTRA_CLIENT_SECRET", "secret-value")
    monkeypatch.setenv("MS_ENTRA_REDIRECT_URI", "http://127.0.0.1:5000/auth/microsoft/callback")
    cfg = client.application.config
    cfg["MS_ENTRA_TENANT_ID"] = "11111111-1111-1111-1111-111111111111"
    cfg["MS_ENTRA_CLIENT_ID"] = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    cfg["MS_ENTRA_CLIENT_SECRET"] = "secret-value"
    cfg["MS_ENTRA_REDIRECT_URI"] = "http://127.0.0.1:5000/auth/microsoft/callback"

    with client.session_transaction() as sess:
        sess["ms_entra_oauth_state"] = "st1"
        sess["ms_entra_oauth_next"] = "http://127.0.0.1:3000/usis-dashboard-dark.html"

    fake_payload = {"email": "ms_" + uuid.uuid4().hex[:8] + "@unknown.example", "tid": "11111111-1111-1111-1111-111111111111"}

    with patch("app.integrations.ms_entra_oidc.exchange_code_for_tokens", return_value={"id_token": "x"}):
        with patch("app.integrations.ms_entra_oidc.verify_id_token", return_value=fake_payload):
            with patch("app.integrations.ms_entra_oidc.claims_email", return_value=fake_payload["email"]):
                r = client.get(
                    "/auth/microsoft/callback?code=cc&state=st1",
                    follow_redirects=False,
                )
    assert r.status_code == 302
    assert "ms_error=not_registered" in (r.headers.get("Location") or "")


def test_microsoft_callback_logs_in_existing_user(client, no_dev_admin, monkeypatch):
    email = "ms_ok_" + uuid.uuid4().hex[:8] + "@t.com"
    with client.application.app_context():
        u = User(
            email=email,
            first_name="M",
            last_name="S",
            password_hash=generate_password_hash("pw"),
            is_active=True,
        )
        db.session.add(u)
        db.session.commit()
        uid = str(u.id)

    monkeypatch.setenv("MS_ENTRA_TENANT_ID", "11111111-1111-1111-1111-111111111111")
    monkeypatch.setenv("MS_ENTRA_CLIENT_ID", "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    monkeypatch.setenv("MS_ENTRA_CLIENT_SECRET", "secret-value")
    monkeypatch.setenv("MS_ENTRA_REDIRECT_URI", "http://127.0.0.1:5000/auth/microsoft/callback")
    cfg = client.application.config
    cfg["MS_ENTRA_TENANT_ID"] = "11111111-1111-1111-1111-111111111111"
    cfg["MS_ENTRA_CLIENT_ID"] = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    cfg["MS_ENTRA_CLIENT_SECRET"] = "secret-value"
    cfg["MS_ENTRA_REDIRECT_URI"] = "http://127.0.0.1:5000/auth/microsoft/callback"

    with client.session_transaction() as sess:
        sess["ms_entra_oauth_state"] = "st2"
        sess["ms_entra_oauth_next"] = "http://127.0.0.1:3000/usis-dashboard-dark.html"

    fake_payload = {"email": email, "tid": "11111111-1111-1111-1111-111111111111"}

    with patch("app.integrations.ms_entra_oidc.exchange_code_for_tokens", return_value={"id_token": "x"}):
        with patch("app.integrations.ms_entra_oidc.verify_id_token", return_value=fake_payload):
            with patch("app.integrations.ms_entra_oidc.claims_email", return_value=email):
                r = client.get("/auth/microsoft/callback?code=cc2&state=st2", follow_redirects=False)

    assert r.status_code == 302
    assert r.headers.get("Location") == "http://127.0.0.1:3000/usis-dashboard-dark.html"
    st = client.get("/api/v1/auth/status").get_json()
    assert st["authenticated"] is True
    assert st["user"]["id"] == uid
