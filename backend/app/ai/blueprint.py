"""HTTP API for Grok-powered chat with database tools."""
from __future__ import annotations

from typing import Any

from flask import Blueprint, jsonify, request

from ..api._perms import current_user
from . import config
from .agent import AgentError, run_chat
from .tools import tool_names

bp = Blueprint("api_ai", __name__, url_prefix="/api/ai")


def _jsonify(obj: Any):
    return jsonify(obj)


@bp.get("/status")
def ai_status():
    return _jsonify(
        {
            "enabled": config.is_configured(),
            "provider": "xai",
            "model": config.xai_model() if config.ai_enabled() else None,
            "tools_available": tool_names() if config.is_configured() else [],
        }
    )


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
    cu = current_user()

    try:
        result = run_chat(messages=messages, mode=str(mode) if mode else None, cu=cu)
    except AgentError as exc:
        return _jsonify({"error": exc.message}), exc.status

    return _jsonify({"entity": "ai_chat", **result})
