"""Tests for /api/ai Grok chat and RBAC tools."""
from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest
from sqlalchemy import select, text

from app.ai.grok_client import ChatCompletionResult, ToolCall
from app.ai.tools.executor import run_tool
from app.api._perms import CurrentUser
from app.extensions import db
from app.models import LeadEstimate


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
