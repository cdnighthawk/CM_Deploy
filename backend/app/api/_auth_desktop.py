"""Accept Microsoft 365 tokens from the USIS desktop app.

The website signs in with cookies. The desktop app sends
``Authorization: Bearer`` Graph tokens (``User.Read``). Those are not
mobile JWTs, so they used to look unsigned-in and Queue returned 401.

Anyone who can sign into the USIS desktop app (Entra assignment) is
created as a CRM estimator on first Queue/API call if they are missing.
"""
from __future__ import annotations

from typing import Any

from flask import current_app
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from ..extensions import db
from ..integrations import ms_entra_oidc as mso
from ..models import Role, User, UserRole


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


def _add_email(emails: list[str], seen: set[str], raw: str | None) -> None:
    email = (raw or "").strip().lower()
    if not email or "@" not in email or email in seen:
        return
    seen.add(email)
    emails.append(email)


def _emails_from_token(token: str, tenant: str, extra_audiences: tuple[str, ...]) -> list[str]:
    emails: list[str] = []
    seen: set[str] = set()
    try:
        payload = mso.verify_access_token(
            access_token=token,
            tenant_id=tenant,
            extra_audiences=extra_audiences,
        )
        _add_email(emails, seen, mso.claims_email(payload))
        for key in ("email", "preferred_username", "upn", "unique_name"):
            _add_email(emails, seen, str(payload.get(key) or ""))
    except Exception:
        pass
    try:
        profile = mso.graph_me(token)
        _add_email(emails, seen, mso.graph_email(profile))
        for key in ("mail", "userPrincipalName"):
            _add_email(emails, seen, str(profile.get(key) or ""))
        others = profile.get("otherMails")
        if isinstance(others, list):
            for item in others:
                _add_email(emails, seen, str(item or ""))
    except Exception:
        pass
    return emails


def _email_from_token(token: str, tenant: str, extra_audiences: tuple[str, ...]) -> str:
    found = _emails_from_token(token, tenant, extra_audiences)
    return found[0] if found else ""


def _lookup_user(email: str) -> User | None:
    return db.session.scalar(select(User).where(func.lower(User.email) == email))


def _ensure_estimator_role(user: User) -> bool:
    """Give a new desktop user the estimator role so Queue is not a 403."""
    existing = db.session.scalar(select(UserRole.role_id).where(UserRole.user_id == user.id).limit(1))
    if existing is not None:
        return False
    role = db.session.scalar(select(Role).where(Role.code == "estimator"))
    if role is None:
        current_app.logger.warning("desktop entra: estimator role is missing")
        return False
    db.session.add(UserRole(user_id=user.id, role_id=role.id))
    db.session.expire(user, ["roles"])
    return True


def _create_desktop_user(email: str) -> User | None:
    u = User(email=email, password_hash=None, is_active=True, is_superuser=False)
    db.session.add(u)
    try:
        db.session.flush()
        _ensure_estimator_role(u)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return _lookup_user(email)
    current_app.logger.info("desktop entra created CRM user %s", email)
    return u


def entra_user_from_bearer(token: str | None = None, authorization: str | None = None) -> User | None:
    """Map a desktop Microsoft access token to an active CRM user."""
    raw = (token or "").strip() or _bearer_token(authorization)
    if not raw:
        return None
    cfg = current_app.config
    tenant = (cfg.get("MS_ENTRA_TENANT_ID") or "").strip()
    if not tenant:
        current_app.logger.warning("desktop entra rejected: ENTRA tenant is not configured")
        return None
    extra = tuple(
        a
        for a in (
            (cfg.get("MS_ENTRA_CLIENT_ID") or "").strip(),
            (cfg.get("MS_ENTRA_API_AUDIENCE") or "").strip(),
        )
        if a
    )
    emails = _emails_from_token(raw, tenant, extra)
    if not emails:
        current_app.logger.warning("desktop entra rejected: token had no email")
        return None
    domains = cfg.get("MS_ENTRA_ALLOWED_EMAIL_DOMAINS") or ()
    emails = [e for e in emails if _email_allowed(e, domains)]
    if not emails:
        current_app.logger.warning("desktop entra rejected: domain not allowed")
        return None
    u = None
    for email in emails:
        u = _lookup_user(email)
        if u is not None:
            break
    if u is None:
        u = _create_desktop_user(emails[0])
        if u is None:
            current_app.logger.warning("desktop entra rejected: could not create %s", emails[0])
            return None
        if not u.is_active:
            current_app.logger.warning("desktop entra rejected: inactive user %s", emails[0])
            return None
        return u
    if not u.is_active:
        current_app.logger.warning("desktop entra rejected: inactive user %s", u.email)
        return None
    if _ensure_estimator_role(u):
        db.session.commit()
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
