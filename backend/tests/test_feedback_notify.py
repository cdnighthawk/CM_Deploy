"""Employee confirms a report is resolved by closing it."""
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
CONFIRM_BASE = "https://www.usiscm.com/usis-issue-confirm.html"
SECRET = "test-secret-key"


def _sign(secret: str, payload: bytes) -> str:
    digest = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def _config():
    return SimpleNamespace(
        GITHUB_FEEDBACK_TOKEN="tok",
        GITHUB_FEEDBACK_OWNER="cdnighthawk",
        GITHUB_FEEDBACK_REPO="CM_Deploy",
    )


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


def test_build_status_email_asks_employee_to_close():
    message = feedback_svc.build_status_email(
        title="[idea] RFI should fill project info",
        reporter_name="Charles",
        status="Fixed",
        resolution="Create now copies the open project's fields.",
        issue_number=1,
        issue_url="https://github.com/cdnighthawk/CM_Deploy/issues/1",
        confirm_url="https://www.usiscm.com/usis-issue-confirm.html?token=abc",
    )
    assert message["subject"].startswith("Please confirm and close:")
    assert "confirm this is resolved by closing" in message["body"]
    assert "usis-issue-confirm.html?token=abc" in message["body"]


def test_resolution_comment_emails_confirm_link():
    sent = {}
    methods = []

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
        methods.append(request.method)
        if request.method == "GET":
            return httpx.Response(200, json=comments)
        assert request.method == "POST"
        assert feedback_svc.NOTIFIED_MARKER in request.content.decode()
        return httpx.Response(201, json={"id": 9})

    result = feedback_svc.handle_github_feedback_event(
        event="issue_comment",
        payload={
            "action": "created",
            "comment": {"body": "Resolution: Autofill project fields when opening RFI create from a project."},
            "issue": {
                "number": 1,
                "title": "[idea] RFI should fill project info",
                "body": CLOSED_BODY,
                "html_url": "https://github.com/cdnighthawk/CM_Deploy/issues/1",
            },
            "repository": {"full_name": "cdnighthawk/CM_Deploy"},
        },
        config=_config(),
        send_email=fake_send,
        confirm_base_url=CONFIRM_BASE,
        secret_key=SECRET,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    assert result["status"] == "sent"
    assert sent["to"] == "sam@gousis.com"
    assert "usis-issue-confirm.html?token=" in sent["body"]
    assert "PATCH" not in methods


def test_team_close_reopens_and_asks_reporter_to_close():
    sent = {}
    patched = []

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
        if request.method == "PATCH":
            patched.append(json.loads(request.content.decode()))
            return httpx.Response(200, json={})
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
        config=_config(),
        send_email=fake_send,
        confirm_base_url=CONFIRM_BASE,
        secret_key=SECRET,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    assert result["status"] == "sent"
    assert patched == [{"state": "open"}]
    assert "closing the issue" in sent["body"]


def test_team_close_after_employee_confirm_stays_closed():
    called = {"send": 0, "patch": 0}

    def fake_send(**kwargs):
        called["send"] += 1
        return {"sent": True, "dry_run": False, "error": None}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "PATCH":
            called["patch"] += 1
        return httpx.Response(
            200,
            json=[{"body": f"{feedback_svc.CONFIRMED_MARKER}\nclosed by reporter", "user": {"login": "bot"}}],
        )

    result = feedback_svc.notify_reporter_for_closed_issue(
        payload={
            "action": "closed",
            "issue": {"number": 2, "title": "x", "body": CLOSED_BODY, "state_reason": "completed"},
            "repository": {"full_name": "cdnighthawk/CM_Deploy"},
        },
        config=_config(),
        send_email=fake_send,
        confirm_base_url=CONFIRM_BASE,
        secret_key=SECRET,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    assert result["status"] == "already_confirmed"
    assert called["send"] == 0
    assert called["patch"] == 0


def test_notify_skips_when_already_waiting():
    called = {"send": 0}

    def fake_send(**kwargs):
        called["send"] += 1
        return {"sent": True, "dry_run": False, "error": None}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "PATCH":
            return httpx.Response(200, json={})
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
        config=_config(),
        send_email=fake_send,
        confirm_base_url=CONFIRM_BASE,
        secret_key=SECRET,
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
        config=_config(),
        send_email=lambda **kwargs: {"sent": True},
        confirm_base_url=CONFIRM_BASE,
        secret_key=SECRET,
    )
    assert result["status"] == "skipped"


def test_employee_close_confirms_and_closes_github():
    calls = []
    issue = {
        "number": 1,
        "title": "[idea] RFI should fill project info",
        "body": CLOSED_BODY,
        "state": "open",
        "state_reason": None,
    }
    comments = [{"body": "Resolution: Copied project fields.", "user": {"login": "cdnighthawk"}}]

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, str(request.url)))
        if request.method == "GET" and "/comments" in str(request.url):
            return httpx.Response(200, json=comments)
        if request.method == "GET":
            return httpx.Response(200, json=issue)
        if request.method == "POST":
            assert feedback_svc.CONFIRMED_MARKER in request.content.decode()
            return httpx.Response(201, json={"id": 3})
        body = json.loads(request.content.decode())
        assert body["state"] == "closed"
        return httpx.Response(200, json={})

    token = feedback_svc.mint_confirm_token(issue_number=1, email="sam@gousis.com", secret_key=SECRET)
    result = feedback_svc.confirm_issue_from_token(
        token=token,
        action="close",
        config=_config(),
        secret_key=SECRET,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    assert result["status"] == "closed"
    assert any(method == "PATCH" for method, _url in calls)


def test_employee_reject_keeps_issue_open():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and "/comments" in str(request.url):
            return httpx.Response(200, json=[])
        if request.method == "GET":
            return httpx.Response(
                200,
                json={"number": 1, "title": "x", "body": CLOSED_BODY, "state": "open"},
            )
        if request.method == "POST":
            assert feedback_svc.REJECTED_MARKER in request.content.decode()
            return httpx.Response(201, json={"id": 4})
        body = json.loads(request.content.decode())
        assert body["state"] == "open"
        return httpx.Response(200, json={})

    token = feedback_svc.mint_confirm_token(issue_number=1, email="sam@gousis.com", secret_key=SECRET)
    result = feedback_svc.confirm_issue_from_token(
        token=token,
        action="reject",
        config=_config(),
        secret_key=SECRET,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    assert result["status"] == "rejected"


def test_webhook_unconfigured(client, flask_app):
    flask_app.config["GITHUB_WEBHOOK_SECRET"] = ""
    r = client.post("/api/webhooks/github", data=b"{}", content_type="application/json")
    assert r.status_code == 503


def test_webhook_ping_and_events(client, flask_app, monkeypatch):
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

    def fake_handle(**kwargs):
        captured.update(kwargs)
        return {"ok": True, "status": "sent", "reason": "sam@gousis.com"}

    monkeypatch.setattr(feedback_svc, "handle_github_feedback_event", fake_handle)
    body = json.dumps({"action": "created", "comment": {"body": "Resolution: done"}}).encode()
    r = client.post(
        "/api/webhooks/github",
        data=body,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": _sign("whsec", body),
            "X-GitHub-Event": "issue_comment",
        },
    )
    assert r.status_code == 200
    assert captured["event"] == "issue_comment"


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


def test_confirm_routes_are_public(client, flask_app, monkeypatch):
    flask_app.config["USIS_API_DEV_ALLOW_ANY"] = False
    monkeypatch.setenv("USIS_API_DEV_ALLOW_ANY", "0")

    def fake_preview(**kwargs):
        return {
            "issue_number": 1,
            "title": "x",
            "reporter_name": "Sam",
            "status": "Fixed",
            "resolution": "Done",
            "already_confirmed": False,
            "state": "open",
        }

    monkeypatch.setattr(feedback_svc, "load_confirm_preview", fake_preview)
    r = client.get("/api/v1/feedback/issues/confirm?token=abc")
    assert r.status_code == 200
    assert r.get_json()["issue_number"] == 1
