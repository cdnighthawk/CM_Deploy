"""Autodesk APS OAuth 2.0 (3-legged): authorize URL, code exchange, refresh."""
from __future__ import annotations

from typing import Any
from urllib.parse import urlencode

import httpx

AUTH_BASE = "https://developer.api.autodesk.com/authentication/v2"
TOKEN_URL = f"{AUTH_BASE}/token"


def build_authorize_url(
    *,
    client_id: str,
    redirect_uri: str,
    scopes: str,
    state: str,
) -> str:
    q = urlencode(
        {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scope": scopes.strip(),
            "state": state,
        }
    )
    return f"{AUTH_BASE}/authorize?{q}"


def _post_token_form(body: dict[str, str]) -> dict[str, Any]:
    r = httpx.post(
        TOKEN_URL,
        data=body,
        headers={"Accept": "application/json"},
        timeout=60.0,
    )
    r.raise_for_status()
    data = r.json()
    if not isinstance(data, dict):
        raise ValueError("token response is not a JSON object")
    return data


def exchange_authorization_code(
    *,
    client_id: str,
    client_secret: str,
    code: str,
    redirect_uri: str,
) -> dict[str, Any]:
    return _post_token_form(
        {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": client_id,
            "client_secret": client_secret,
        }
    )


def refresh_access_token(
    *,
    client_id: str,
    client_secret: str,
    refresh_token: str,
) -> dict[str, Any]:
    return _post_token_form(
        {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": client_id,
            "client_secret": client_secret,
        }
    )
