"""Admin directory: users and roles (requires admin / superuser)."""
from __future__ import annotations

import re
import uuid
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import selectinload
from werkzeug.security import generate_password_hash

from ..extensions import db
from ..models import Role, User, UserRole
from ._perms import CurrentUser, can_manage_directory_users


class ApiError(Exception):
    def __init__(self, message: str, status: int = 400):
        self.message = message
        self.status = status


def _require_admin(cu: CurrentUser) -> None:
    if not can_manage_directory_users(cu):
        raise ApiError("Admin privileges required to manage users.", 403)


def _iso(dt: Any) -> str | None:
    if dt is None:
        return None
    return dt.isoformat()


def user_public(u: User) -> dict[str, Any]:
    roles: list[dict[str, Any]] = []
    for ur in u.roles or ():
        if ur.role is None:
            continue
        roles.append(
            {
                "id": str(ur.role.id),
                "code": ur.role.code,
                "name": ur.role.name,
            }
        )
    roles.sort(key=lambda r: (r.get("code") or "", r.get("name") or ""))
    return {
        "id": str(u.id),
        "email": u.email,
        "first_name": u.first_name,
        "last_name": u.last_name,
        "phone": u.phone,
        "is_active": u.is_active,
        "is_superuser": u.is_superuser,
        "has_password": bool(u.password_hash),
        "last_login_at": _iso(u.last_login_at),
        "created_at": _iso(u.created_at),
        "updated_at": _iso(u.updated_at),
        "roles": roles,
    }


def role_public(r: Role) -> dict[str, Any]:
    return {
        "id": str(r.id),
        "code": r.code,
        "name": r.name,
        "description": r.description,
    }


def list_roles(cu: CurrentUser) -> list[dict[str, Any]]:
    _require_admin(cu)
    q = select(Role).order_by(Role.code.asc())
    rows = db.session.scalars(q).all()
    return [role_public(r) for r in rows]


def list_users(
    cu: CurrentUser,
    *,
    q: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    _require_admin(cu)
    qn = (q or "").strip().lower()
    stmt = select(User)
    count_stmt = select(func.count()).select_from(User)
    if qn:
        filt = or_(
            func.lower(User.email).contains(qn),
            func.lower(func.coalesce(User.first_name, "")).contains(qn),
            func.lower(func.coalesce(User.last_name, "")).contains(qn),
        )
        stmt = stmt.where(filt)
        count_stmt = count_stmt.where(filt)
    total = db.session.scalar(count_stmt) or 0
    stmt = (
        stmt.options(selectinload(User.roles).selectinload(UserRole.role))
        .order_by(User.email.asc())
        .offset(offset)
        .limit(limit)
    )
    rows = db.session.scalars(stmt).all()
    return [user_public(u) for u in rows], int(total)


def get_user(cu: CurrentUser, user_id: uuid.UUID) -> dict[str, Any] | None:
    _require_admin(cu)
    u = db.session.scalar(
        select(User)
        .where(User.id == user_id)
        .options(selectinload(User.roles).selectinload(UserRole.role))
    )
    if u is None:
        return None
    return user_public(u)


_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _normalize_email(raw: str) -> str:
    s = (raw or "").strip().lower()
    if not s:
        raise ApiError("email is required")
    if len(s) > 255:
        raise ApiError("email is too long")
    if not _EMAIL_RE.match(s):
        raise ApiError("invalid email format")
    return s


def _parse_role_ids(raw: Any) -> list[uuid.UUID]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ApiError("role_ids must be a list of UUID strings")
    out: list[uuid.UUID] = []
    for x in raw:
        try:
            out.append(uuid.UUID(str(x).strip()))
        except (TypeError, ValueError) as e:
            raise ApiError("invalid role id in role_ids") from e
    return out


def _set_roles(user: User, role_ids: list[uuid.UUID]) -> None:
    roles = db.session.scalars(select(Role).where(Role.id.in_(role_ids))).all() if role_ids else []
    if role_ids and len(roles) != len(set(role_ids)):
        raise ApiError("one or more role_ids are invalid")
    user.roles.clear()
    for r in roles:
        user.roles.append(UserRole(user_id=user.id, role_id=r.id))


def create_user(cu: CurrentUser, data: dict[str, Any]) -> dict[str, Any]:
    _require_admin(cu)
    if not isinstance(data, dict):
        raise ApiError("JSON body required")
    email = _normalize_email(str(data.get("email") or ""))
    existing = db.session.scalar(select(User.id).where(User.email == email))
    if existing is not None:
        raise ApiError("a user with this email already exists")
    fn = (data.get("first_name") or None)
    ln = (data.get("last_name") or None)
    phone = (data.get("phone") or None)
    if fn is not None:
        fn = str(fn).strip()[:120] or None
    if ln is not None:
        ln = str(ln).strip()[:120] or None
    if phone is not None:
        phone = str(phone).strip()[:50] or None
    is_active = data.get("is_active", True)
    if not isinstance(is_active, bool):
        raise ApiError("is_active must be boolean")
    is_superuser = data.get("is_superuser", False)
    if not isinstance(is_superuser, bool):
        raise ApiError("is_superuser must be boolean")
    pwd_raw = data.get("password")
    pwd_hash: str | None = None
    if pwd_raw is not None and str(pwd_raw).strip():
        pwd_hash = generate_password_hash(str(pwd_raw))
    u = User(
        email=email,
        first_name=fn,
        last_name=ln,
        phone=phone,
        is_active=is_active,
        is_superuser=is_superuser,
        password_hash=pwd_hash,
    )
    db.session.add(u)
    db.session.flush()
    role_ids = _parse_role_ids(data.get("role_ids"))
    _set_roles(u, role_ids)
    db.session.flush()
    db.session.refresh(u)
    return user_public(u)


def get_me(cu: CurrentUser) -> dict[str, Any]:
    """Return the signed-in user's directory row (same shape as admin ``get_user``)."""
    if cu.user is None:
        raise ApiError("authentication required", 401)
    uid = cu.user.id
    u = db.session.scalar(
        select(User)
        .where(User.id == uid)
        .options(selectinload(User.roles).selectinload(UserRole.role))
    )
    if u is None:
        raise ApiError("user not found", 404)
    return user_public(u)


def patch_me(cu: CurrentUser, data: dict[str, Any]) -> dict[str, Any]:
    """Update profile fields for the signed-in user only (no roles / superuser / active flags)."""
    if cu.user is None:
        raise ApiError("authentication required", 401)
    if not isinstance(data, dict):
        raise ApiError("JSON body required", 400)
    uid = cu.user.id
    u = db.session.scalar(
        select(User)
        .where(User.id == uid)
        .options(selectinload(User.roles).selectinload(UserRole.role))
    )
    if u is None:
        raise ApiError("user not found", 404)
    allowed = frozenset({"email", "first_name", "last_name", "phone", "password"})
    for key in data:
        if key not in allowed:
            raise ApiError(f"cannot update {key!r} on your own profile", 400)
    if "email" in data:
        email = _normalize_email(str(data.get("email") or ""))
        clash = db.session.scalar(select(User.id).where(User.email == email, User.id != uid))
        if clash is not None:
            raise ApiError("a user with this email already exists")
        u.email = email
    if "first_name" in data:
        v = data["first_name"]
        u.first_name = None if v is None else (str(v).strip()[:120] or None)
    if "last_name" in data:
        v = data["last_name"]
        u.last_name = None if v is None else (str(v).strip()[:120] or None)
    if "phone" in data:
        v = data["phone"]
        u.phone = None if v is None else (str(v).strip()[:50] or None)
    if "password" in data:
        pr = data["password"]
        if pr is None:
            raise ApiError("password cannot be null; omit the field to leave unchanged", 400)
        if str(pr).strip() == "":
            raise ApiError("password cannot be empty; omit the field to leave unchanged", 400)
        u.password_hash = generate_password_hash(str(pr))
    db.session.flush()
    db.session.refresh(u)
    return user_public(u)


def patch_user(cu: CurrentUser, user_id: uuid.UUID, data: dict[str, Any]) -> dict[str, Any] | None:
    _require_admin(cu)
    if not isinstance(data, dict):
        raise ApiError("JSON body required")
    u = db.session.scalar(
        select(User)
        .where(User.id == user_id)
        .options(selectinload(User.roles).selectinload(UserRole.role))
    )
    if u is None:
        return None
    if "email" in data:
        email = _normalize_email(str(data.get("email") or ""))
        clash = db.session.scalar(select(User.id).where(User.email == email, User.id != user_id))
        if clash is not None:
            raise ApiError("a user with this email already exists")
        u.email = email
    if "first_name" in data:
        v = data["first_name"]
        u.first_name = None if v is None else (str(v).strip()[:120] or None)
    if "last_name" in data:
        v = data["last_name"]
        u.last_name = None if v is None else (str(v).strip()[:120] or None)
    if "phone" in data:
        v = data["phone"]
        u.phone = None if v is None else (str(v).strip()[:50] or None)
    if "is_active" in data:
        if not isinstance(data["is_active"], bool):
            raise ApiError("is_active must be boolean")
        u.is_active = data["is_active"]
    if "is_superuser" in data:
        if not isinstance(data["is_superuser"], bool):
            raise ApiError("is_superuser must be boolean")
        u.is_superuser = data["is_superuser"]
    if "password" in data:
        pr = data["password"]
        if pr is None or str(pr).strip() == "":
            u.password_hash = None
        else:
            u.password_hash = generate_password_hash(str(pr))
    if "role_ids" in data:
        role_ids = _parse_role_ids(data.get("role_ids"))
        _set_roles(u, role_ids)
    db.session.flush()
    db.session.refresh(u)
    return user_public(u)
