"""Microsoft Graph outbound mail (unit tests, no network)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


def _graph_env(monkeypatch):
    monkeypatch.setenv("MS_ENTRA_TENANT_ID", "tenant-id")
    monkeypatch.setenv("MS_ENTRA_CLIENT_ID", "client-id")
    monkeypatch.setenv("MS_ENTRA_CLIENT_SECRET", "client-secret")
    monkeypatch.setenv("MAIL_FROM", "noreply@gousis.com")
    monkeypatch.delenv("MAIL_SERVER", raising=False)
    monkeypatch.delenv("MAIL_USERNAME", raising=False)


def test_graph_configured_with_entra_creds(monkeypatch):
    from app.api import _notifications as mail

    mail.reset_graph_token_cache()
    _graph_env(monkeypatch)
    assert mail._graph_configured() is True
    assert mail._mail_configured() is True


def test_system_mail_not_configured_without_from(monkeypatch):
    from app.api import _notifications as mail

    monkeypatch.setenv("MS_ENTRA_TENANT_ID", "tenant-id")
    monkeypatch.setenv("MS_ENTRA_CLIENT_ID", "client-id")
    monkeypatch.setenv("MS_ENTRA_CLIENT_SECRET", "client-secret")
    monkeypatch.delenv("MAIL_FROM", raising=False)
    assert mail._graph_configured() is True
    assert mail._mail_configured() is False
    assert mail._mail_configured(from_addr="charles@gousis.com") is True


def test_send_plain_uses_graph(monkeypatch, flask_app):
    from app.api import _notifications as mail

    mail.reset_graph_token_cache()
    _graph_env(monkeypatch)

    token_response = MagicMock()
    token_response.raise_for_status = MagicMock()
    token_response.json.return_value = {"access_token": "tok", "expires_in": 3600}

    send_response = MagicMock()
    send_response.status_code = 202
    send_response.text = ""

    client = MagicMock()
    client.__enter__.return_value = client
    client.__exit__.return_value = False
    client.post.side_effect = [token_response, send_response]

    with flask_app.app_context():
        with patch("httpx.Client", return_value=client):
            result = mail.send_plain_notification_email(
                to="applicant@example.com",
                subject="Test",
                body="Hello",
            )

    assert result["sent"] is True
    assert result["dry_run"] is False
    assert client.post.call_count == 2
    send_call = client.post.call_args_list[1]
    assert "sendMail" in send_call.args[0]
    assert send_call.kwargs["json"]["message"]["subject"] == "Test"


def test_compose_sends_as_user_mailbox(monkeypatch, flask_app):
    from app.api import _notifications as mail

    mail.reset_graph_token_cache()
    _graph_env(monkeypatch)

    token_response = MagicMock()
    token_response.raise_for_status = MagicMock()
    token_response.json.return_value = {"access_token": "tok", "expires_in": 3600}
    send_response = MagicMock()
    send_response.status_code = 202
    send_response.text = ""
    client = MagicMock()
    client.__enter__.return_value = client
    client.__exit__.return_value = False
    client.post.side_effect = [token_response, send_response]

    with flask_app.app_context():
        with patch("httpx.Client", return_value=client):
            result = mail.send_compose_email(
                to="sub@example.com",
                subject="RFI",
                body="Please review",
                from_addr="charles@gousis.com",
            )

    assert result["ok"] is True
    send_url = client.post.call_args_list[1].args[0]
    assert "charles%40gousis.com" in send_url or "charles@gousis.com" in send_url


def test_send_plain_dry_run_when_unconfigured(monkeypatch, flask_app):
    from app.api import _notifications as mail

    monkeypatch.delenv("MAIL_SERVER", raising=False)
    monkeypatch.delenv("MAIL_USERNAME", raising=False)
    monkeypatch.delenv("MAIL_FROM", raising=False)
    monkeypatch.delenv("MS_ENTRA_CLIENT_SECRET", raising=False)
    with flask_app.app_context():
        result = mail.send_plain_notification_email(
            to="applicant@example.com",
            subject="Test",
            body="Hello",
        )
    assert result["sent"] is False
    assert result["dry_run"] is True


def _session_user(email: str):
    cu = MagicMock()
    cu.user = MagicMock()
    cu.user.email = email
    return cu


def test_list_mailbox_uses_session_email_not_query_mailbox(client, monkeypatch):
    from app.api import _notifications as mail
    from app.api import v1 as v1_mod

    staff = "charles@gousis.com"
    monkeypatch.setattr(v1_mod, "current_user", lambda: _session_user(staff))
    captured: list[str] = []

    def fake_http(method, url, **kwargs):
        captured.append(url)
        return {
            "value": [
                {
                    "id": "msg-1",
                    "subject": "Hello",
                    "from": {"emailAddress": {"name": "Pat", "address": "pat@example.com"}},
                    "toRecipients": [{"emailAddress": {"address": staff}}],
                    "receivedDateTime": "2026-08-23T12:00:00Z",
                    "isRead": False,
                    "bodyPreview": "Preview text",
                    "hasAttachments": False,
                }
            ]
        }

    monkeypatch.setattr(mail, "_graph_http", fake_http)
    r = client.get(
        "/api/v1/mail/messages",
        query_string={"folder": "inbox", "mailbox": "victim@gousis.com"},
    )
    assert r.status_code == 200
    body = r.get_json()
    assert body["mailbox"] == staff
    assert captured
    assert "victim@gousis.com" not in captured[0]
    assert "charles%40gousis.com" in captured[0] or "charles@gousis.com" in captured[0]
    assert body["items"][0]["subject"] == "Hello"
    assert body["items"][0]["is_read"] is False


def test_compose_route_ignores_client_from(client, monkeypatch):
    from app.api import _notifications as mail
    from app.api import v1 as v1_mod

    staff = "charles@gousis.com"
    monkeypatch.setattr(v1_mod, "current_user", lambda: _session_user(staff))
    seen: dict[str, str] = {}

    def fake_compose(**kwargs):
        seen.update(kwargs)
        return {"ok": True, "sent": 1, "dry_run": False, "queued": False, "errors": []}

    monkeypatch.setattr(mail, "send_compose_email", fake_compose)
    r = client.post(
        "/api/v1/messages/email",
        json={
            "to": "sub@example.com",
            "subject": "RFI",
            "message": "Please review",
            "from": "victim@gousis.com",
            "from_addr": "victim@gousis.com",
        },
    )
    assert r.status_code == 200
    assert seen.get("from_addr") == staff
    assert seen.get("to") == "sub@example.com"


def test_mailbox_graph_403_is_consent_error(client, monkeypatch):
    from app.api import _notifications as mail
    from app.api import v1 as v1_mod

    monkeypatch.setattr(v1_mod, "current_user", lambda: _session_user("charles@gousis.com"))

    def fake_http(method, url, **kwargs):
        raise mail.GraphMailError(403, "Access denied")

    monkeypatch.setattr(mail, "_graph_http", fake_http)
    r = client.get("/api/v1/mail/messages?folder=inbox")
    assert r.status_code == 403
    err = (r.get_json() or {}).get("error") or ""
    assert "Mail.ReadWrite" in err


def test_delete_mailbox_uses_session_user(client, monkeypatch):
    from app.api import _notifications as mail
    from app.api import v1 as v1_mod

    staff = "charles@gousis.com"
    monkeypatch.setattr(v1_mod, "current_user", lambda: _session_user(staff))
    captured: list[tuple[str, str]] = []

    def fake_http(method, url, **kwargs):
        captured.append((method, url))
        return None

    monkeypatch.setattr(mail, "_graph_http", fake_http)
    r = client.delete("/api/v1/mail/messages/AAMkAGI")
    assert r.status_code == 200
    assert captured
    assert captured[0][0] == "DELETE"
    assert "charles%40gousis.com" in captured[0][1] or "charles@gousis.com" in captured[0][1]
