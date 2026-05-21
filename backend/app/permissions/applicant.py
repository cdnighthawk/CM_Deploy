"""Job applicants: self-service hire wizard only (no CM staff modules)."""
from __future__ import annotations

import uuid

from sqlalchemy import select

from ..extensions import db
from ..models import Role, User, UserRole
from .access import load_user_with_roles
from .modules import MODULE_CODES

APPLICANT_ROLE_CODE = "applicant"

# Static shell HTML an applicant may open (plus everything under ``assets/``).
APPLICANT_PUBLIC_SHELL_PAGES: frozenset[str] = frozenset(
    {
        "apply.html",
        "page-login.html",
        "page-register.html",
        "page-forgot-password.html",
        "page-reset-password.html",
        "page-lock-screen.html",
        "usis-hr-hire.html",
    }
)

# Default redirect when an applicant-only session hits staff HTML.
APPLICANT_APPLICATION_PATH = "/apply/application.html"

_APPLICANT_PERMISSIONS: dict[str, str] = {code: "none" for code in MODULE_CODES}


def applicant_permissions() -> dict[str, str]:
    return dict(_APPLICANT_PERMISSIONS)


def role_codes_for_user(user: User | None) -> frozenset[str]:
    if user is None:
        return frozenset()
    codes: set[str] = set()
    for ur in user.roles or ():
        if ur.role is not None and ur.role.code:
            codes.add(ur.role.code)
    return frozenset(codes)


def is_applicant_only_user(user: User | None) -> bool:
    """True when the user may use only the public hire / apply shell (no staff CM)."""
    if user is None or user.is_superuser:
        return False
    codes = role_codes_for_user(user)
    return codes == frozenset({APPLICANT_ROLE_CODE})


def is_applicant_public_shell_path(rel_path: str) -> bool:
    rel = (rel_path or "").replace("\\", "/").strip().lstrip("/")
    if not rel or rel.startswith("assets/"):
        return True
    lower = rel.lower()
    if lower.startswith("apply/"):
        return True
    name = lower.split("/")[-1]
    return name in APPLICANT_PUBLIC_SHELL_PAGES


def get_applicant_role() -> Role | None:
    return db.session.scalar(select(Role).where(Role.code == APPLICANT_ROLE_CODE))


def assign_applicant_role(user: User) -> None:
    """Ensure ``user`` has the applicant role (idempotent)."""
    role = get_applicant_role()
    if role is None:
        raise RuntimeError(f"role {APPLICANT_ROLE_CODE!r} is not seeded; run flask db upgrade")
    existing = {ur.role_id for ur in user.roles or () if ur.role_id is not None}
    if role.id in existing:
        return
    user.roles.append(UserRole(user_id=user.id, role_id=role.id))


def applicant_only_from_session(session_user_id: str | None) -> bool:
    if not session_user_id:
        return False
    try:
        uid = uuid.UUID(str(session_user_id).strip())
    except (ValueError, TypeError, AttributeError):
        return False
    user = load_user_with_roles(uid)
    return is_applicant_only_user(user)
