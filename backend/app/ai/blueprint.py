"""HTTP API for Grok-powered chat with database tools."""
from __future__ import annotations

from typing import Any

from flask import Blueprint, jsonify, request

from ..api._perms import current_user
from . import config
from . import store
from .agent import AgentError, run_chat
from .tools import tool_names

bp = Blueprint("api_ai", __name__, url_prefix="/api/ai")


def _jsonify(obj: Any):
    return jsonify(obj)


def _last_user_message(messages: list[Any], attachments: list[Any] | None) -> dict[str, Any]:
    content = ""
    extra_atts = None
    for m in reversed(messages):
        if isinstance(m, dict) and str(m.get("role") or "").lower() == "user":
            raw = m.get("content")
            content = raw if isinstance(raw, str) else str(raw or "")
            extra_atts = m.get("attachments")
            break
    return {
        "role": "user",
        "content": content,
        "attachments": store.slim_attachments(attachments or extra_atts),
    }


@bp.get("/status")
def ai_status():
    cu = current_user()
    return _jsonify(
        {
            "enabled": config.is_configured(),
            "provider": "xai",
            "model": config.xai_model() if config.ai_enabled() else None,
            "tools_available": tool_names() if config.is_configured() else [],
            "persisted": store.can_persist(cu),
        }
    )


@bp.get("/sessions")
def ai_sessions():
    return _jsonify(store.list_sessions(current_user()))


@bp.post("/sessions")
def ai_session_create():
    body = request.get_json(silent=True)
    if body is None:
        body = {}
    if not isinstance(body, dict):
        return _jsonify({"error": "expected JSON object body"}), 400
    messages = body.get("messages")
    if messages is not None and not isinstance(messages, list):
        return _jsonify({"error": "messages must be an array"}), 400
    created = store.create_session(
        current_user(),
        title=str(body.get("title") or "") or None,
        mode=str(body["mode"]) if body.get("mode") else None,
        messages=messages,
    )
    if created is None:
        return _jsonify({"error": "Sign in to save chats.", "persisted": False}), 401
    return _jsonify(created), 201


@bp.get("/sessions/<session_id>")
def ai_session_get(session_id: str):
    row = store.get_session(current_user(), session_id)
    if row is None:
        return _jsonify({"error": "not found"}), 404
    return _jsonify(row)


@bp.delete("/sessions/<session_id>")
def ai_session_delete(session_id: str):
    if not store.delete_session(current_user(), session_id):
        return _jsonify({"error": "not found"}), 404
    return _jsonify({"ok": True})


@bp.post("/chat")
def ai_chat():
    if not config.is_configured():
        return _jsonify({"error": "AI is not configured (USIS_AI_ENABLED and USIS_XAI_API_KEY required)"}), 503

    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return _jsonify({"error": "expected JSON object body"}), 400

    messages = body.get("messages")
    if not isinstance(messages, list) or not messages:
        return _jsonify({"error": "messages array is required"}), 400

    mode = body.get("mode")
    attachments = body.get("attachments")
    if attachments is not None and not isinstance(attachments, list):
        return _jsonify({"error": "attachments must be an array"}), 400
    session_id = body.get("session_id")
    if session_id is not None and not isinstance(session_id, str):
        return _jsonify({"error": "session_id must be a string"}), 400
    cu = current_user()

    try:
        result = run_chat(
            messages=messages,
            mode=str(mode) if mode else None,
            cu=cu,
            attachments=attachments,
        )
    except AgentError as exc:
        return _jsonify({"error": exc.message}), exc.status

    saved_id = store.append_turn(
        cu,
        session_id=session_id,
        mode=str(mode) if mode else None,
        user_message=_last_user_message(messages, result.get("attachments") or attachments),
        assistant_message={
            "role": "assistant",
            "content": (result.get("message") or {}).get("content") or "",
        },
    )
    return _jsonify(
        {
            "entity": "ai_chat",
            **result,
            "session_id": saved_id,
            "persisted": saved_id is not None,
        }
    )
