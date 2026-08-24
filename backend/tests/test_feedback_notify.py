"""Email the employee when their GitHub issue is closed."""
from __future__ import annotations

import hashlib
import hmac
import json
from types import SimpleNamespace

import httpx

from app.services import feedback as feedback_svc


CLOSED_BODY = """## Something broke

### Reporter
**From:** Sam Lee
**Email:** sam@gousis.com
"""


def _sign(secret: str, payload: bytes) -> str:
    digest = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def test_parse_reporter_from_line_and_marker():
    assert feedback_svc.parse_reporter_email(CLOSED_BODY) == "sam@gousis.com"
    assert feedback_svc.parse_reporter_name(CLOSED_BODY) == "Sam Lee"
    marked = "<!-- usis-reporter-email: pat@gousis.com -->\n**Email:** old@gousis.com"
    assert feedback_svc.parse_reporter_email(marked) == "pat@gousis.com"


def test_extract_resolution_prefers_resolution_comment():
    comments = [
        {"body": "looking into this", "user": {"login": "cdnighthawk"}},
        {"body": "Resolution: RFI create now copies project name and number.", "user": {"login": "cdnighthawk"}},
    ]
    extracted = feedback_svc.extract_resolution(comments, "completed")
    assert extracted["status"] == "Fixed"
    assert "copies project name" in extracted["resolution"]


def test_extract_resolution_not_planned_fallback():
    extracted = feedback_svc.extract_resolution([], "not_planned")
    assert extracted["status"] == "Not fixed"
    assert "will not be changed" in extracted["resolution"]


def test_build_status_email_includes_title_and_status():
    message = feedback_svc.build_status_email(
        title="[idea] RFI should fill project info",
        reporter_name="Charles",
        status="Fixed",
        resolution="Create now copies the open project's fields.",
        issue_number=1,
        issue_url="https://github.com/cdnighthawk/CM_Deploy/issues/1",
    )
    assert message["subject"].startswith("Fixed:")
    assert "Hi Charles," in message["body"]
    assert "Create now copies" in message["body"]
    assert "issue #1" in message["body"]


def test_notify_closed_issue_sends_and_marks(monkeypatch):
    sent = {}

    def fake_send(**kwargs):
        sent.update(kwargs)
        return {"sent": True, "dry_run": False, "error": None}

    comments = [
        {
            "body": "Resolution: Autofill project fields when opening RFI create from a project.",
            "user": {"login": "cdnighthawk"},
        }
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200, json=comments)
        assert request.method == "POST"
        assert feedback_svc.NOTIFIED_MARKER in request.content.decode()
        return httpx.Response(201, json={"id": 9})

    result = feedback_svc.notify_reporter_for_closed_issue(
        payload={
            "action": "closed",
            "issue": {
                "number": 1,
                "title": "[idea] RFI should fill project info",
                "body": CLOSED_BODY,
                "state_reason": "completed",
                "html_url": "https://github.com/cdnighthawk/CM_Deploy/issues/1",
            },
            "repository": {"full_name": "cdnighthawk/CM_Deploy"},
        },
        config=SimpleNamespace(
            GITHUB_FEEDBACK_TOKEN="tok",
            GITHUB_FEEDBACK_OWNER="cdnighthawk",
            GITHUB_FEEDBACK_REPO="CM_Deploy",
        ),
        send_email=fake_send,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    assert result["status"] == "sent"
    assert sent["to"] == "sam@gousis.com"
    assert "Autofill project fields" in sent["body"]


def test_notify_skips_when_already_marked():
    called = {"send": 0}

    def fake_send(**kwargs):
        called["send"] += 1
        return {"sent": True, "dry_run": False, "error": None}

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=[{"body": f"{feedback_svc.NOTIFIED_MARKER}\nalready sent", "user": {"login": "bot"}}],
        )

    result = feedback_svc.notify_reporter_for_closed_issue(
        payload={
            "action": "closed",
            "issue": {"number": 2, "title": "x", "body": CLOSED_BODY, "state_reason": "completed"},
            "repository": {"full_name": "cdnighthawk/CM_Deploy"},
        },
        config=SimpleNamespace(
            GITHUB_FEEDBACK_TOKEN="tok",
            GITHUB_FEEDBACK_OWNER="cdnighthawk",
            GITHUB_FEEDBACK_REPO="CM_Deploy",
        ),
        send_email=fake_send,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    assert result["status"] == "already_notified"
    assert called["send"] == 0


def test_notify_skips_without_reporter_email():
    result = feedback_svc.notify_reporter_for_closed_issue(
        payload={
            "action": "closed",
            "issue": {"number": 3, "title": "x", "body": "no email here", "state_reason": "completed"},
            "repository": {"full_name": "cdnighthawk/CM_Deploy"},
        },
        config=SimpleNamespace(
            GITHUB_FEEDBACK_TOKEN="tok",
            GITHUB_FEEDBACK_OWNER="cdnighthawk",
            GITHUB_FEEDBACK_REPO="CM_Deploy",
        ),
        send_email=lambda **kwargs: {"sent": True},
    )
    assert result["status"] == "skipped"


def test_webhook_unconfigured(client, flask_app):
    flask_app.config["GITHUB_WEBHOOK_SECRET"] = ""
    r = client.post("/api/webhooks/github", data=b"{}", content_type="application/json")
    assert r.status_code == 503


def test_webhook_ping_and_closed(client, flask_app, monkeypatch):
    flask_app.config["GITHUB_WEBHOOK_SECRET"] = "whsec"
    ping = b'{"zen":"ok"}'
    r = client.post(
        "/api/webhooks/github",
        data=ping,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": _sign("whsec", ping),
            "X-GitHub-Event": "ping",
        },
    )
    assert r.status_code == 200
    assert r.get_json()["pong"] is True

    captured = {}

    def fake_notify(**kwargs):
        captured.update(kwargs)
        return {"ok": True, "status": "sent", "reason": "sam@gousis.com"}

    monkeypatch.setattr(feedback_svc, "notify_reporter_for_closed_issue", fake_notify)
    body = json.dumps({"action": "closed", "issue": {"number": 1}}).encode()
    r = client.post(
        "/api/webhooks/github",
        data=body,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": _sign("whsec", body),
            "X-GitHub-Event": "issues",
        },
    )
    assert r.status_code == 200
    assert r.get_json()["status"] == "sent"
    assert captured["payload"]["action"] == "closed"


def test_webhook_rejects_bad_signature(client, flask_app):
    flask_app.config["GITHUB_WEBHOOK_SECRET"] = "whsec"
    r = client.post(
        "/api/webhooks/github",
        data=b"{}",
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": "sha256=deadbeef",
            "X-GitHub-Event": "issues",
        },
    )
    assert r.status_code == 400
