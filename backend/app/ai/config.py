"""Environment configuration for the AI layer."""
from __future__ import annotations

import os


def ai_enabled() -> bool:
    raw = (os.environ.get("USIS_AI_ENABLED") or "").strip().lower()
    return raw in ("1", "true", "yes", "on")


def xai_api_key() -> str:
    return (os.environ.get("USIS_XAI_API_KEY") or "").strip()


def xai_model() -> str:
    return (os.environ.get("USIS_XAI_MODEL") or "grok-4-1-fast").strip()


def xai_base_url() -> str:
    return (os.environ.get("USIS_XAI_BASE_URL") or "https://api.x.ai/v1").strip().rstrip("/")


def max_tool_rounds() -> int:
    try:
        return max(1, min(int(os.environ.get("USIS_AI_MAX_TOOL_ROUNDS", "8")), 20))
    except ValueError:
        return 8


def request_timeout_sec() -> float:
    try:
        return max(5.0, float(os.environ.get("USIS_AI_REQUEST_TIMEOUT_SEC", "120")))
    except ValueError:
        return 120.0


def is_configured() -> bool:
    return ai_enabled() and bool(xai_api_key())
