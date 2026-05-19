"""Agent loop: Grok chat + client-side tool execution."""
from __future__ import annotations

import json
from typing import Any

from flask import current_app

from ..api._perms import CurrentUser
from . import config
from .grok_client import ChatCompletionResult, GrokClientError, ToolCall, chat_completion
from .prompts import build_system_prompt
from .tools import run_tool, tool_schemas_for_grok


class AgentError(Exception):
    def __init__(self, message: str, *, status: int = 500):
        super().__init__(message)
        self.message = message
        self.status = status


def _normalize_messages(messages: list[Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for m in messages:
        if not isinstance(m, dict):
            continue
        role = str(m.get("role") or "").strip().lower()
        if role not in ("user", "assistant", "system"):
            continue
        content = m.get("content")
        if content is None:
            content = ""
        if not isinstance(content, str):
            content = str(content)
        if role == "system":
            continue
        out.append({"role": role, "content": content})
    return out


def _assistant_message_dict(result: ChatCompletionResult) -> dict[str, Any]:
    msg: dict[str, Any] = {"role": "assistant", "content": result.content or ""}
    if result.tool_calls:
        msg["tool_calls"] = [
            {
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.name,
                    "arguments": json.dumps(tc.arguments),
                },
            }
            for tc in result.tool_calls
        ]
    return msg


def run_chat(
    *,
    messages: list[Any],
    mode: str | None,
    cu: CurrentUser,
) -> dict[str, Any]:
    if not config.is_configured():
        raise AgentError("AI is not configured (set USIS_AI_ENABLED=1 and USIS_XAI_API_KEY)", status=503)

    conv: list[dict[str, Any]] = [
        {"role": "system", "content": build_system_prompt(mode)},
        *_normalize_messages(messages),
    ]
    tools = tool_schemas_for_grok()
    tool_log: list[dict[str, Any]] = []
    max_rounds = config.max_tool_rounds()

    for round_idx in range(max_rounds):
        try:
            result = chat_completion(messages=conv, tools=tools)
        except GrokClientError as exc:
            raise AgentError(exc.message, status=exc.status or 502) from exc

        if not result.tool_calls:
            return {
                "message": {
                    "role": "assistant",
                    "content": result.content or "",
                },
                "tool_calls_made": tool_log,
                "rounds": round_idx + 1,
                "provider": "xai",
                "model": config.xai_model(),
            }

        conv.append(_assistant_message_dict(result))
        for tc in result.tool_calls:
            tool_out = run_tool(tc.name, tc.arguments, cu)
            tool_log.append(
                {
                    "name": tc.name,
                    "arguments": tc.arguments,
                    "result": tool_out,
                }
            )
            conv.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.id or f"call_{tc.name}_{round_idx}",
                    "content": json.dumps(tool_out, default=str),
                }
            )

    current_app.logger.warning("ai agent hit max tool rounds (%s)", max_rounds)
    raise AgentError(f"maximum tool rounds exceeded ({max_rounds})", status=500)
