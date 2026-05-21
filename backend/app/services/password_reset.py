"""Password reset request + confirm (email link)."""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from werkzeug.security import generate_password_hash

from ..extensions import db
from ..models import PasswordResetToken, User

RESET_TOKEN_TTL = timedelta(hours=1)


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def request_password_reset(email: str) -> dict[str, object]:
    """Create a reset token and send email when the user can sign in with a password."""
    from ..api._notifications import send_password_reset_email

    normalized = (email or "").strip().lower()
    if not normalized:
        return {"ok": True, "sent": False, "dry_run": False}

    u = db.session.scalar(
        select(User).where(User.email == normalized, User.is_active.is_(True))
    )
    if u is None or not u.password_hash:
        return {"ok": True, "sent": False, "dry_run": False}

    db.session.execute(delete(PasswordResetToken).where(PasswordResetToken.user_id == u.id))

    raw_token = secrets.token_urlsafe(32)
    row = PasswordResetToken(
        user_id=u.id,
        token_hash=_hash_token(raw_token),
        expires_at=_utcnow() + RESET_TOKEN_TTL,
    )
    db.session.add(row)
    db.session.flush()

    mail_result = send_password_reset_email(to=u.email, reset_token=raw_token)
    return {
        "ok": True,
        "sent": bool(mail_result.get("sent")),
        "dry_run": bool(mail_result.get("dry_run")),
    }


def confirm_password_reset(token: str, new_password: str) -> None:
    """Set a new password from a valid reset token."""
    raw = (token or "").strip()
    if not raw:
        raise ValueError("reset token is required")
    if len(new_password or "") < 8:
        raise ValueError("password must be at least 8 characters")

    token_hash = _hash_token(raw)
    now = _utcnow()
    row = db.session.scalar(
        select(PasswordResetToken)
        .where(
            PasswordResetToken.token_hash == token_hash,
            PasswordResetToken.used_at.is_(None),
            PasswordResetToken.expires_at > now,
        )
        .limit(1)
    )
    if row is None:
        raise ValueError("invalid or expired reset link")

    u = db.session.get(User, row.user_id)
    if u is None or not u.is_active:
        raise ValueError("invalid or expired reset link")

    u.password_hash = generate_password_hash(new_password)
    row.used_at = now
    db.session.add(u)
    db.session.add(row)
