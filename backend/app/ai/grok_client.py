"""xAI Grok chat completions (OpenAI-compatible API)."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

import httpx

from .config import request_timeout_sec, xai_api_key, xai_base_url, xai_model


class GrokClientError(Exception):
    def __init__(self, message: str, *, status: int | None = None):
        super().__init__(message)
        self.message = message
        self.status = status


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class ChatCompletionResult:
    content: str | None
    tool_calls: list[ToolCall] = field(default_factory=list)
    finish_reason: str | None = None


def _parse_arguments(raw: Any) -> dict[str, Any]:
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        s = raw.strip()
        if not s:
            return {}
        try:
            parsed = json.loads(s)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def chat_completion(
    *,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None = None,
    model: str | None = None,
) -> ChatCompletionResult:
    """Call Grok chat/completions and return assistant content and/or tool calls."""
    key = xai_api_key()
    if not key:
        raise GrokClientError("USIS_XAI_API_KEY is not configured")

    url = f"{xai_base_url()}/chat/completions"
    body: dict[str, Any] = {
        "model": model or xai_model(),
        "messages": messages,
    }
    if tools:
        body["tools"] = tools
        body["tool_choice"] = "auto"

    try:
        with httpx.Client(timeout=request_timeout_sec()) as client:
            resp = client.post(
                url,
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                },
                json=body,
            )
    except httpx.TimeoutException as exc:
        raise GrokClientError("Grok API request timed out") from exc
    except httpx.HTTPError as exc:
        raise GrokClientError(f"Grok API request failed: {exc}") from exc

    if resp.status_code >= 400:
        detail = resp.text[:500] if resp.text else resp.reason_phrase
        raise GrokClientError(f"Grok API error {resp.status_code}: {detail}", status=resp.status_code)

    data = resp.json()
    choices = data.get("choices") or []
    if not choices:
        raise GrokClientError("Grok API returned no choices")

    message = choices[0].get("message") or {}
    finish = choices[0].get("finish_reason")
    content = message.get("content")
    if content is not None and not isinstance(content, str):
        content = str(content)

    tool_calls_out: list[ToolCall] = []
    for tc in message.get("tool_calls") or []:
        fn = tc.get("function") or {}
        name = fn.get("name")
        if not name:
            continue
        tool_calls_out.append(
            ToolCall(
                id=str(tc.get("id") or ""),
                name=str(name),
                arguments=_parse_arguments(fn.get("arguments")),
            )
        )

    return ChatCompletionResult(
        content=content,
        tool_calls=tool_calls_out,
        finish_reason=finish,
    )
