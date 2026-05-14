"""Power BI embed: service principal acquires AAD token and report embed token.

Set in environment (see ``.env.example``):

- ``POWERBI_TENANT_ID`` — Azure AD tenant GUID
- ``POWERBI_CLIENT_ID`` — App registration (service principal) client id
- ``POWERBI_CLIENT_SECRET`` — Client secret
- ``POWERBI_WORKSPACE_ID`` — Power BI workspace (group) id
- ``POWERBI_REPORT_ID`` — Report id inside that workspace

The Azure app must have Power BI API delegated/application permissions as required
for ``GenerateToken`` (typically the service principal is added as Member/Admin
on the workspace, or use a dedicated capacity with appropriate settings).
"""
from __future__ import annotations

import os
from typing import Any

import httpx

from ._perms import CurrentUser
from ._rfi_service import ApiError

_POWERBI_SCOPE = "https://analysis.windows.net/powerbi/api/.default"
_TOKEN_URL = "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"
_API_BASE = "https://api.powerbi.com/v1.0/myorg"

_REQUIRED_ENV = (
    "POWERBI_TENANT_ID",
    "POWERBI_CLIENT_ID",
    "POWERBI_CLIENT_SECRET",
    "POWERBI_WORKSPACE_ID",
    "POWERBI_REPORT_ID",
)


def is_configured() -> bool:
    return all((os.environ.get(k) or "").strip() for k in _REQUIRED_ENV)


def _can_view_embed(cu: CurrentUser) -> bool:
    if cu.is_dev_admin or cu.has_role("admin", "superuser", "standard", "read_only", "readonly"):
        return True
    return False


def _missing_env_keys() -> list[str]:
    return [k for k in _REQUIRED_ENV if not (os.environ.get(k) or "").strip()]


def _aad_access_token() -> str:
    tenant = (os.environ.get("POWERBI_TENANT_ID") or "").strip()
    cid = (os.environ.get("POWERBI_CLIENT_ID") or "").strip()
    sec = (os.environ.get("POWERBI_CLIENT_SECRET") or "").strip()
    url = _TOKEN_URL.format(tenant=tenant)
    with httpx.Client(timeout=45.0) as client:
        r = client.post(
            url,
            data={
                "client_id": cid,
                "client_secret": sec,
                "scope": _POWERBI_SCOPE,
                "grant_type": "client_credentials",
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
    if r.status_code != 200:
        raise ApiError(
            f"Azure AD token failed ({r.status_code}): {r.text[:500]}",
            502,
        )
    data = r.json()
    tok = data.get("access_token")
    if not tok:
        raise ApiError("Azure AD response missing access_token", 502)
    return str(tok)


def get_embed_config(cu: CurrentUser) -> dict[str, Any]:
    """Return JSON for the browser Power BI client (embed URL + short-lived token)."""
    if not _can_view_embed(cu):
        raise ApiError("forbidden", 403)

    missing = _missing_env_keys()
    if missing:
        return {
            "entity": "powerbi_embed",
            "configured": False,
            "missing_env": missing,
            "message": "Power BI is not configured. Add the POWERBI_* variables from .env.example.",
        }

    workspace = (os.environ.get("POWERBI_WORKSPACE_ID") or "").strip()
    report_id = (os.environ.get("POWERBI_REPORT_ID") or "").strip()
    aad = _aad_access_token()
    auth = {"Authorization": f"Bearer {aad}"}

    with httpx.Client(timeout=45.0) as client:
        gr = client.get(f"{_API_BASE}/groups/{workspace}/reports/{report_id}", headers=auth)
        if gr.status_code != 200:
            raise ApiError(
                f"Power BI Get Report failed ({gr.status_code}): {gr.text[:500]}",
                502,
            )
        rep = gr.json()
        embed_url = rep.get("embedUrl")
        if not embed_url:
            raise ApiError("Power BI report response missing embedUrl", 502)

        gt = client.post(
            f"{_API_BASE}/groups/{workspace}/reports/{report_id}/GenerateToken",
            headers={**auth, "Content-Type": "application/json"},
            json={"accessLevel": "View"},
        )
        if gt.status_code != 200:
            raise ApiError(
                f"Power BI GenerateToken failed ({gt.status_code}): {gt.text[:500]}",
                502,
            )
        tok_body = gt.json()
    embed_tok = tok_body.get("token")
    exp = tok_body.get("expiration")
    if not embed_tok:
        raise ApiError("Power BI GenerateToken response missing token", 502)

    return {
        "entity": "powerbi_embed",
        "configured": True,
        "embedUrl": embed_url,
        "embedToken": embed_tok,
        "reportId": report_id,
        "workspaceId": workspace,
        "tokenExpiry": exp,
    }
