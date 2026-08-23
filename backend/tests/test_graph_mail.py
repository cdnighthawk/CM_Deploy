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
