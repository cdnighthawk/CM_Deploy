"""Microsoft Entra ID (Azure AD) OAuth 2.0 / OpenID Connect — authorization code flow."""
from __future__ import annotations

import urllib.parse
from typing import Any

import httpx
import jwt
from jwt import PyJWKClient

_MS_AUTH = "https://login.microsoftonline.com"


def entra_fully_configured(cfg: dict[str, Any]) -> bool:
    return bool(
        (cfg.get("MS_ENTRA_TENANT_ID") or "").strip()
        and (cfg.get("MS_ENTRA_CLIENT_ID") or "").strip()
        and (cfg.get("MS_ENTRA_CLIENT_SECRET") or "").strip()
        and (cfg.get("MS_ENTRA_REDIRECT_URI") or "").strip()
    )


def build_authorize_url(
    *,
    tenant: str,
    client_id: str,
    redirect_uri: str,
    state: str,
    scopes: str,
) -> str:
    q = urllib.parse.urlencode(
        {
            "client_id": client_id,
            "response_type": "code",
            "redirect_uri": redirect_uri,
            "response_mode": "query",
            "scope": scopes,
            "state": state,
            "prompt": "select_account",
        },
        quote_via=urllib.parse.quote,
    )
    return f"{_MS_AUTH}/{urllib.parse.quote(tenant, safe='')}/oauth2/v2.0/authorize?{q}"


def exchange_code_for_tokens(
    *,
    tenant: str,
    client_id: str,
    client_secret: str,
    redirect_uri: str,
    code: str,
    timeout: float = 30.0,
) -> dict[str, Any]:
    token_url = f"{_MS_AUTH}/{urllib.parse.quote(tenant, safe='')}/oauth2/v2.0/token"
    data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
    }
    with httpx.Client(timeout=timeout) as client:
        r = client.post(
            token_url,
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
    if r.status_code != 200:
        raise RuntimeError(f"token endpoint {r.status_code}: {r.text[:400]}")
    return r.json()


def verify_id_token(*, id_token: str, client_id: str, tenant_id: str) -> dict[str, Any]:
    """Validate signature (JWKS) and audience; issuer must be login.microsoftonline.com."""
    jwks_url = f"{_MS_AUTH}/{urllib.parse.quote(tenant_id, safe='')}/discovery/v2.0/keys"
    jwks_client = PyJWKClient(jwks_url)
    signing_key = jwks_client.get_signing_key_from_jwt(id_token)
    payload = jwt.decode(
        id_token,
        signing_key.key,
        algorithms=["RS256"],
        audience=client_id,
        options={"verify_exp": True, "verify_aud": True, "verify_iss": False},
    )
    iss = str(payload.get("iss") or "")
    if not iss.startswith(f"{_MS_AUTH}/") or not iss.endswith("/v2.0"):
        raise ValueError("invalid id_token issuer")
    tid = str(payload.get("tid") or "").lower()
    tcfg = tenant_id.strip().lower()
    if tcfg not in ("common", "organizations", "consumers") and tid and tid != tcfg:
        raise ValueError("id_token tenant does not match configured tenant")
    return payload


def claims_email(payload: dict[str, Any]) -> str:
    for key in ("email", "preferred_username", "upn"):
        v = payload.get(key)
        if v and str(v).strip():
            return str(v).strip().lower()
    return ""
