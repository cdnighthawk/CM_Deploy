"""Bearer JWT + refresh tokens for USIS mobile (Expo) clients."""
from __future__ import annotations

import os
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from flask import current_app, jsonify, request
from sqlalchemy import select
from werkzeug.security import check_password_hash, generate_password_hash

from ..extensions import db
from ..models import MobileRefreshToken, User

_ACCESS_TYPE = "access"
_REFRESH_DAYS_DEFAULT = 30


def _mobile_access_ttl() -> timedelta:
    raw = (os.environ.get("USIS_MOBILE_ACCESS_TTL_MINUTES") or "60").strip()
    try:
        minutes = max(5, min(int(raw), 24 * 60))
    except ValueError:
        minutes = 60
    return timedelta(minutes=minutes)


def _mobile_refresh_ttl() -> timedelta:
    raw = (os.environ.get("USIS_MOBILE_REFRESH_TTL_DAYS") or str(_REFRESH_DAYS_DEFAULT)).strip()
    try:
        days = max(1, min(int(raw), 365))
    except ValueError:
        days = _REFRESH_DAYS_DEFAULT
    return timedelta(days=days)


def _hash_refresh_token(raw: str) -> str:
    return generate_password_hash(raw, method="pbkdf2:sha256")


def _verify_refresh_token(raw: str, stored_hash: str) -> bool:
    return check_password_hash(stored_hash, raw)


def _user_public(u: User) -> dict[str, Any]:
    return {
        "id": str(u.id),
        "email": u.email,
        "first_name": u.first_name,
        "last_name": u.last_name,
    }


def issue_access_token(user_id: uuid.UUID) -> tuple[str, int]:
    ttl = _mobile_access_ttl()
    now = datetime.now(timezone.utc)
    exp = now + ttl
    payload = {
        "sub": str(user_id),
        "type": _ACCESS_TYPE,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }
    token = jwt.encode(
        payload,
        current_app.config["SECRET_KEY"],
        algorithm="HS256",
    )
    if isinstance(token, bytes):
        token = token.decode("ascii")
    return token, int(ttl.total_seconds())


def decode_access_token(token: str) -> uuid.UUID | None:
    try:
        payload = jwt.decode(
            token,
            current_app.config["SECRET_KEY"],
            algorithms=["HS256"],
        )
    except jwt.PyJWTError:
        return None
    if payload.get("type") != _ACCESS_TYPE:
        return None
    return _parse_uuid(payload.get("sub"))


def _parse_uuid(raw: Any) -> uuid.UUID | None:
    if not raw:
        return None
    try:
        return uuid.UUID(str(raw).strip())
    except (TypeError, ValueError):
        return None


def _issue_refresh_token(user: User, *, device_label: str | None) -> str:
    raw = secrets.token_urlsafe(48)
    row = MobileRefreshToken(
        user_id=user.id,
        token_hash=_hash_refresh_token(raw),
        expires_at=datetime.now(timezone.utc) + _mobile_refresh_ttl(),
        device_label=(device_label or "").strip()[:120] or None,
    )
    db.session.add(row)
    db.session.flush()
    return raw


def _find_valid_refresh_row(raw: str) -> MobileRefreshToken | None:
    if not raw or len(raw) < 20:
        return None
    now = datetime.now(timezone.utc)
    candidates = db.session.scalars(
        select(MobileRefreshToken).where(
            MobileRefreshToken.revoked_at.is_(None),
            MobileRefreshToken.expires_at > now,
        )
    ).all()
    for row in candidates:
        if _verify_refresh_token(raw, row.token_hash):
            return row
    return None


def _revoke_refresh_row(row: MobileRefreshToken) -> None:
    if row.revoked_at is None:
        row.revoked_at = datetime.now(timezone.utc)
        db.session.add(row)


def authenticate_email_password(email: str, password: str) -> User | None:
    email_norm = email.strip().lower()
    if not email_norm or not password:
        return None
    u = db.session.scalar(
        select(User).where(User.email == email_norm, User.is_active.is_(True))
    )
    if u is None or not u.password_hash:
        return None
    if not check_password_hash(u.password_hash, password):
        return None
    return u


def register_mobile_auth_routes(bp) -> None:
    """Attach mobile auth routes to the v1 API blueprint."""

    @bp.post("/auth/mobile/login")
    def mobile_login():
        body = request.get_json(silent=True) or {}
        if not isinstance(body, dict):
            return jsonify({"error": "JSON body required"}), 400
        email = str(body.get("email") or "")
        password = str(body.get("password") or "")
        device_label = str(body.get("device_label") or "") or None

        u = authenticate_email_password(email, password)
        if u is None:
            return jsonify({"error": "invalid email or password"}), 401

        u.last_login_at = datetime.now(timezone.utc)
        db.session.add(u)
        access_token, expires_in = issue_access_token(u.id)
        refresh_token = _issue_refresh_token(u, device_label=device_label)
        db.session.commit()

        return jsonify(
            {
                "access_token": access_token,
                "refresh_token": refresh_token,
                "expires_in": expires_in,
                "token_type": "Bearer",
                "user": _user_public(u),
            }
        )

    @bp.post("/auth/mobile/refresh")
    def mobile_refresh():
        body = request.get_json(silent=True) or {}
        if not isinstance(body, dict):
            return jsonify({"error": "JSON body required"}), 400
        raw = str(body.get("refresh_token") or "").strip()
        row = _find_valid_refresh_row(raw)
        if row is None:
            return jsonify({"error": "invalid or expired refresh token"}), 401

        u = db.session.get(User, row.user_id)
        if u is None or not u.is_active:
            _revoke_refresh_row(row)
            db.session.commit()
            return jsonify({"error": "user inactive"}), 401

        _revoke_refresh_row(row)
        access_token, expires_in = issue_access_token(u.id)
        new_refresh = _issue_refresh_token(u, device_label=row.device_label)
        db.session.commit()

        return jsonify(
            {
                "access_token": access_token,
                "refresh_token": new_refresh,
                "expires_in": expires_in,
                "token_type": "Bearer",
                "user": _user_public(u),
            }
        )

    @bp.post("/auth/mobile/logout")
    def mobile_logout():
        body = request.get_json(silent=True) or {}
        if not isinstance(body, dict):
            return jsonify({"error": "JSON body required"}), 400
        raw = str(body.get("refresh_token") or "").strip()
        row = _find_valid_refresh_row(raw)
        if row is not None:
            _revoke_refresh_row(row)
            db.session.commit()
        return jsonify({"ok": True})


def bearer_user_from_request() -> User | None:
    """Resolve user from Authorization Bearer JWT if present."""
    auth = (request.headers.get("Authorization") or "").strip()
    if not auth.lower().startswith("bearer "):
        return None
    token = auth[7:].strip()
    if not token:
        return None
    uid = decode_access_token(token)
    if uid is None:
        return None
    u = db.session.get(User, uid)
    if u is None or not u.is_active:
        return None
    return u
