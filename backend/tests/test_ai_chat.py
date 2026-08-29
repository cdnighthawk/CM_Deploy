"""Tests for /api/ai Grok chat and RBAC tools."""
from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest
from sqlalchemy import inspect, select, text

from app.ai.attachments import AttachmentError, merge_user_content, process_attachments
from app.ai.grok_client import ChatCompletionResult, ToolCall
from app.ai.tools.executor import run_tool
from app.api._perms import CurrentUser
from app.extensions import db
from app.models import LeadEstimate, User


def _db_ok(flask_app) -> bool:
    try:
        with flask_app.app_context():
            db.session.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


@pytest.fixture
def ai_enabled(monkeypatch):
    monkeypatch.setenv("USIS_AI_ENABLED", "1")
    monkeypatch.setenv("USIS_XAI_API_KEY", "test-key")


def test_ai_status_disabled(client, monkeypatch):
    monkeypatch.setenv("USIS_AI_ENABLED", "0")
    monkeypatch.delenv("USIS_XAI_API_KEY", raising=False)
    r = client.get("/api/ai/status")
    assert r.status_code == 200
    data = r.get_json()
    assert data["enabled"] is False
    assert data["provider"] == "xai"


def test_ai_status_enabled(client, ai_enabled):
    r = client.get("/api/ai/status")
    assert r.status_code == 200
    data = r.get_json()
    assert data["enabled"] is True
    assert "list_projects" in data["tools_available"]


def test_ai_chat_not_configured(client, monkeypatch):
    monkeypatch.setenv("USIS_AI_ENABLED", "0")
    monkeypatch.delenv("USIS_XAI_API_KEY", raising=False)
    r = client.post(
        "/api/ai/chat",
        json={"messages": [{"role": "user", "content": "hi"}]},
    )
    assert r.status_code == 503


def test_ai_chat_tool_loop(client, ai_enabled):
    calls = [
        ChatCompletionResult(
            content=None,
            tool_calls=[
                ToolCall(id="call_1", name="list_projects", arguments={"limit": 5}),
            ],
        ),
        ChatCompletionResult(content="You have no projects in scope.", tool_calls=[]),
    ]

    def fake_chat(**kwargs):
        return calls.pop(0)

    fake_tool_result = {
        "ok": True,
        "entity": "projects",
        "items": [],
        "total": 0,
        "limit": 5,
        "offset": 0,
    }

    with patch("app.ai.agent.chat_completion", side_effect=fake_chat):
        with patch("app.ai.agent.run_tool", return_value=fake_tool_result):
            r = client.post(
                "/api/ai/chat",
                json={"messages": [{"role": "user", "content": "List my projects"}]},
            )
    assert r.status_code == 200
    body = r.get_json()
    assert body["message"]["role"] == "assistant"
    assert len(body["tool_calls_made"]) == 1
    assert body["tool_calls_made"][0]["name"] == "list_projects"
    assert body["tool_calls_made"][0]["result"]["ok"] is True


def test_process_attachments_text_file():
    import base64

    data = base64.b64encode(b"Door schedule: 12 units").decode("ascii")
    text, images, summaries = process_attachments(
        [{"kind": "file", "name": "doors.txt", "mime": "text/plain", "data": data}]
    )
    assert "Door schedule" in text
    assert images == []
    assert summaries[0]["name"] == "doors.txt"


def test_process_attachments_blocks_private_url():
    try:
        process_attachments([{"kind": "url", "url": "http://127.0.0.1/secret"}])
        assert False, "expected AttachmentError"
    except AttachmentError as exc:
        assert "not allowed" in exc.message


def test_merge_user_content_images():
    merged = merge_user_content(
        "What is this?",
        "",
        [{"type": "image_url", "image_url": {"url": "https://example.com/a.png"}}],
    )
    assert isinstance(merged, list)
    assert merged[0]["text"] == "What is this?"
    assert merged[1]["type"] == "image_url"


def test_ai_chat_with_attachment(client, ai_enabled):
    import base64

    calls = [ChatCompletionResult(content="Saw the door count.", tool_calls=[])]

    def fake_chat(**kwargs):
        msgs = kwargs.get("messages") or []
        last = msgs[-1]["content"]
        assert isinstance(last, str)
        assert "12 units" in last
        return calls.pop(0)

    with patch("app.ai.agent.chat_completion", side_effect=fake_chat):
        r = client.post(
            "/api/ai/chat",
            json={
                "messages": [{"role": "user", "content": "Summarize this"}],
                "attachments": [
                    {
                        "kind": "file",
                        "name": "doors.txt",
                        "mime": "text/plain",
                        "data": base64.b64encode(b"Door schedule: 12 units").decode("ascii"),
                    }
                ],
            },
        )
    assert r.status_code == 200
    assert "Saw the door count" in r.get_json()["message"]["content"]


def test_tool_denied_without_module(flask_app):
    cu = CurrentUser(
        user=None,
        role_codes=frozenset({"field_readonly"}),
        granular=frozenset(),
        module_access={
            "dashboard": "read",
            "projects": "none",
            "ai": "read",
        },
    )
    with flask_app.app_context():
        out = run_tool("list_projects", {"limit": 5}, cu)
    assert out["ok"] is False
    assert out["status"] == 403


def test_update_lead_locked_integration(flask_app, ai_enabled):
    if not _db_ok(flask_app):
        pytest.skip("PostgreSQL not available")
    from datetime import datetime, timezone

    eid = "ai-lock-" + uuid.uuid4().hex[:8]
    with flask_app.app_context():
        le = LeadEstimate(
            external_id=eid,
            name="Locked lead",
            crm_stage="New Lead",
            estimate_locked_at=datetime.now(timezone.utc),
        )
        db.session.add(le)
        db.session.commit()
        lid = str(le.id)

    cu = CurrentUser(
        user=None,
        role_codes=frozenset({"admin"}),
        granular=frozenset(),
        is_dev_admin=True,
        module_access={
            "leads": "write",
            "estimate": "write",
            "ai": "read",
        },
    )
    out = run_tool(
        "update_lead_estimate",
        {"lead_estimate_id": lid, "fields": {"crm_stage": "Estimating"}},
        cu,
    )
    assert out["ok"] is False
    assert out["status"] == 403

    with flask_app.app_context():
        row = db.session.scalar(select(LeadEstimate).where(LeadEstimate.external_id == eid))
        if row:
            db.session.delete(row)
            db.session.commit()


def _ai_tables_ok(flask_app) -> bool:
    if not _db_ok(flask_app):
        return False
    try:
        with flask_app.app_context():
            insp = inspect(db.engine)
            return insp.has_table("ai_chat_sessions") and insp.has_table("ai_chat_messages")
    except Exception:
        return False


def _make_chat_user(flask_app) -> str:
    email = "ai.chat." + uuid.uuid4().hex[:8] + "@t.com"
    with flask_app.app_context():
        u = User(
            email=email,
            first_name="Ada",
            last_name="Chat",
            is_active=True,
            is_superuser=False,
        )
        db.session.add(u)
        db.session.commit()
        return str(u.id)


def test_sessions_anonymous_not_persisted(client):
    r = client.get("/api/ai/sessions")
    assert r.status_code == 200
    data = r.get_json()
    assert data["persisted"] is False
    assert data["items"] == []


def test_chat_persists_by_user(client, flask_app, ai_enabled):
    if not _ai_tables_ok(flask_app):
        pytest.skip("ai_chat tables not migrated")
    uid = _make_chat_user(flask_app)
    other = _make_chat_user(flask_app)
    headers = {"X-Usis-User-Id": uid}

    with patch("app.ai.agent.chat_completion", return_value=ChatCompletionResult(content="Hello from Grok.", tool_calls=[])):
        r = client.post(
            "/api/ai/chat",
            json={"messages": [{"role": "user", "content": "Remember this later"}]},
            headers=headers,
        )
    assert r.status_code == 200
    body = r.get_json()
    assert body["persisted"] is True
    sid = body["session_id"]
    assert sid

    listed = client.get("/api/ai/sessions", headers=headers)
    assert listed.status_code == 200
    items = listed.get_json()["items"]
    assert any(i["id"] == sid for i in items)
    assert items[0]["title"].startswith("Remember this later")

    got = client.get(f"/api/ai/sessions/{sid}", headers=headers)
    assert got.status_code == 200
    msgs = got.get_json()["messages"]
    assert [m["role"] for m in msgs] == ["user", "assistant"]
    assert msgs[0]["content"] == "Remember this later"
    assert "Hello from Grok" in msgs[1]["content"]

    hidden = client.get(f"/api/ai/sessions/{sid}", headers={"X-Usis-User-Id": other})
    assert hidden.status_code == 404
    others = client.get("/api/ai/sessions", headers={"X-Usis-User-Id": other})
    assert others.get_json()["items"] == []


def test_create_and_delete_own_session(client, flask_app):
    if not _ai_tables_ok(flask_app):
        pytest.skip("ai_chat tables not migrated")
    uid = _make_chat_user(flask_app)
    headers = {"X-Usis-User-Id": uid}
    created = client.post(
        "/api/ai/sessions",
        json={"messages": [{"role": "user", "content": "Imported local chat"}]},
        headers=headers,
    )
    assert created.status_code == 201
    sid = created.get_json()["id"]
    gone = client.delete(f"/api/ai/sessions/{sid}", headers=headers)
    assert gone.status_code == 200
    assert client.get(f"/api/ai/sessions/{sid}", headers=headers).status_code == 404
