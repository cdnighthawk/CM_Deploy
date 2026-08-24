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
    for key in ("email", "preferred_username", "upn", "unique_name"):
        v = payload.get(key)
        if v and str(v).strip() and "@" in str(v):
            return str(v).strip().lower()
    return ""


_GRAPH_AUDIENCES = frozenset(
    {
        "00000003-0000-0000-c000-000000000000",
        "https://graph.microsoft.com",
        "https://graph.microsoft.com/",
    }
)


def _audience_list(payload: dict[str, Any]) -> list[str]:
    aud = payload.get("aud")
    if isinstance(aud, list):
        return [str(v) for v in aud]
    if aud is None:
        return []
    return [str(aud)]


def _tenant_ok(payload: dict[str, Any], tenant_id: str) -> bool:
    tid = str(payload.get("tid") or "").lower()
    tcfg = tenant_id.strip().lower()
    if tcfg in ("common", "organizations", "consumers"):
        return True
    return not tid or tid == tcfg


def _issuer_ok(payload: dict[str, Any], tenant_id: str) -> bool:
    iss = str(payload.get("iss") or "")
    tenant = tenant_id.strip()
    allowed = {
        f"{_MS_AUTH}/{tenant}/v2.0",
        f"https://sts.windows.net/{tenant}/",
    }
    return iss in allowed or (
        iss.startswith(f"{_MS_AUTH}/") and iss.endswith("/v2.0") and _tenant_ok(payload, tenant_id)
    )


def verify_access_token(*, access_token: str, tenant_id: str, extra_audiences: tuple[str, ...] = ()) -> dict[str, Any]:
    """Validate a desktop / Graph access token. Audience may be Graph or a USIS app id."""
    jwks_url = f"{_MS_AUTH}/{urllib.parse.quote(tenant_id, safe='')}/discovery/v2.0/keys"
    jwks_client = PyJWKClient(jwks_url)
    signing_key = jwks_client.get_signing_key_from_jwt(access_token)
    payload = jwt.decode(
        access_token,
        signing_key.key,
        algorithms=["RS256"],
        options={"verify_exp": True, "verify_aud": False, "verify_iss": False},
    )
    if not _issuer_ok(payload, tenant_id):
        raise ValueError("invalid access token issuer")
    if not _tenant_ok(payload, tenant_id):
        raise ValueError("access token tenant does not match configured tenant")
    allowed = _GRAPH_AUDIENCES | {a.strip() for a in extra_audiences if a and a.strip()}
    actual = _audience_list(payload)
    if actual and not any(a in allowed for a in actual):
        raise ValueError("access token audience is not allowed")
    return payload


def graph_me(access_token: str, timeout: float = 15.0) -> dict[str, Any]:
    """Resolve the signed-in person when the access token is for Microsoft Graph."""
    with httpx.Client(timeout=timeout) as client:
        r = client.get(
            "https://graph.microsoft.com/v1.0/me?$select=mail,userPrincipalName,otherMails,givenName,surname,displayName",
            headers={"Authorization": f"Bearer {access_token}"},
        )
    if r.status_code != 200:
        raise RuntimeError(f"graph /me {r.status_code}: {r.text[:200]}")
    body = r.json()
    if not isinstance(body, dict):
        raise RuntimeError("graph /me returned a non-object")
    return body


def graph_email(profile: dict[str, Any]) -> str:
    for key in ("mail", "userPrincipalName"):
        v = profile.get(key)
        if v and str(v).strip() and "@" in str(v):
            return str(v).strip().lower()
    others = profile.get("otherMails")
    if isinstance(others, list):
        for v in others:
            if v and str(v).strip() and "@" in str(v):
                return str(v).strip().lower()
    return ""
