"""Accept Microsoft 365 tokens from the USIS desktop app.

The website signs in with cookies. The desktop app sends
``Authorization: Bearer`` Graph tokens (``User.Read``). Those are not
mobile JWTs, so they used to look unsigned-in and Queue returned 401.
"""
from __future__ import annotations

from typing import Any

from flask import current_app
from sqlalchemy import func, select

from ..extensions import db
from ..integrations import ms_entra_oidc as mso
from ..models import User


def _bearer_token(authorization: str | None) -> str:
    raw = (authorization or "").strip()
    if not raw.lower().startswith("bearer "):
        return ""
    return raw[7:].strip()


def _email_allowed(email: str, domains: tuple[str, ...]) -> bool:
    if not domains:
        return True
    dom = email.rsplit("@", 1)[-1].lower() if "@" in email else ""
    return dom in {str(d).lower() for d in domains}


def _email_from_token(token: str, tenant: str, extra_audiences: tuple[str, ...]) -> str:
    try:
        payload = mso.verify_access_token(
            access_token=token,
            tenant_id=tenant,
            extra_audiences=extra_audiences,
        )
        email = mso.claims_email(payload)
        if email:
            return email
    except Exception:
        pass
    try:
        return mso.graph_email(mso.graph_me(token))
    except Exception:
        return ""


def entra_user_from_bearer(token: str | None = None, authorization: str | None = None) -> User | None:
    """Map a desktop Microsoft access token to an active CRM user."""
    raw = (token or "").strip() or _bearer_token(authorization)
    if not raw:
        return None
    cfg = current_app.config
    tenant = (cfg.get("MS_ENTRA_TENANT_ID") or "").strip()
    if not tenant:
        return None
    extra = tuple(
        a
        for a in (
            (cfg.get("MS_ENTRA_CLIENT_ID") or "").strip(),
            (cfg.get("MS_ENTRA_API_AUDIENCE") or "").strip(),
        )
        if a
    )
    email = _email_from_token(raw, tenant, extra)
    if not email or not _email_allowed(email, cfg.get("MS_ENTRA_ALLOWED_EMAIL_DOMAINS") or ()):
        return None
    u = db.session.scalar(select(User).where(func.lower(User.email) == email))
    if u is None or not u.is_active:
        return None
    return u


def desktop_token_identity(token: str) -> dict[str, Any] | None:
    """Test helper: return the resolved email without touching the database."""
    cfg = current_app.config
    tenant = (cfg.get("MS_ENTRA_TENANT_ID") or "").strip()
    if not tenant:
        return None
    extra = tuple(
        a
        for a in (
            (cfg.get("MS_ENTRA_CLIENT_ID") or "").strip(),
            (cfg.get("MS_ENTRA_API_AUDIENCE") or "").strip(),
        )
        if a
    )
    email = _email_from_token(token, tenant, extra)
    if not email:
        return None
    return {"email": email}
