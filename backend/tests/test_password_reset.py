"""Password reset email flow (unit tests, no database)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch


def test_password_reset_request_api_ok(client):
    with patch("app.services.password_reset.request_password_reset") as req:
        req.return_value = {"ok": True, "sent": True, "dry_run": False}
        r = client.post(
            "/api/v1/auth/password-reset/request",
            json={"email": "user@example.com"},
        )
    assert r.status_code == 200
    body = r.get_json()
    assert body["ok"] is True
    assert "message" in body
    req.assert_called_once_with("user@example.com")


def test_password_reset_confirm_api_ok(client):
    with patch("app.services.password_reset.confirm_password_reset") as confirm:
        r = client.post(
            "/api/v1/auth/password-reset/confirm",
            json={"token": "abc", "password": "new-password-9"},
        )
    assert r.status_code == 200
    confirm.assert_called_once_with("abc", "new-password-9")


def test_password_reset_confirm_validation_error(client):
    with patch("app.services.password_reset.confirm_password_reset") as confirm:
        confirm.side_effect = ValueError("invalid or expired reset link")
        r = client.post(
            "/api/v1/auth/password-reset/confirm",
            json={"token": "bad", "password": "new-password-9"},
        )
    assert r.status_code == 400
    assert "invalid" in r.get_json()["error"]


def test_send_password_reset_email_builds_link(flask_app):
    with flask_app.app_context():
        from app.api._notifications import send_password_reset_email

        with patch("app.api._notifications.send_plain_notification_email") as send:
            send.return_value = {"sent": True, "dry_run": False}
            send_password_reset_email(to="user@example.com", reset_token="secret-token")
        body = send.call_args.kwargs["body"]
        assert "secret-token" in body
        assert "page-reset-password.html" in body


def test_request_password_reset_skips_users_without_password(flask_app):
    with flask_app.app_context():
        from app.services import password_reset as pw_reset

        user = MagicMock()
        user.email = "sso@example.com"
        user.password_hash = None
        with patch("app.services.password_reset.db") as db_mock:
            db_mock.session.scalar.return_value = user
            result = pw_reset.request_password_reset("sso@example.com")
    assert result["sent"] is False
