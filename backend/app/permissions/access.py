"""Resolve effective module access for users and roles."""
from __future__ import annotations

import re
import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from ..extensions import db
from ..models import Role, RoleModulePermission, User, UserRole
from .defaults import DEFAULTS_BY_ROLE_CODE, _NO_ROLE
from .modules import ALL_LEVELS, MODULE_CODES, MODULE_CATALOG, catalog_public

if TYPE_CHECKING:
    from ..api._perms import CurrentUser

LEVEL_RANK = {"none": 0, "read": 1, "write": 2, "admin": 3}


class ModuleAccessError(Exception):
    def __init__(self, message: str, status: int = 403):
        self.message = message
        self.status = status


def level_rank(level: str) -> int:
    return LEVEL_RANK.get(level, 0)


def normalize_level(raw: str | None) -> str:
    if raw is None:
        return "none"
    s = str(raw).strip().lower()
    if s in LEVEL_RANK:
        return s
    return "none"


def max_level(a: str, b: str) -> str:
    return a if level_rank(a) >= level_rank(b) else b


# Project lookup rows (CSI spec sections, locations, …) can be added with write.
# Line-card and buy-path rows are the same kind of directory maintenance.
# DELETE is admin elsewhere so contracts/RFIs stay protected.
_WRITE_LEVEL_DELETE_RE = re.compile(
    r"^/api/v1/(?:"
    r"projects/[^/]+/rfi-lookups/[^/]+/[^/]+|"
    r"csi-buy-channels/[^/]+|"
    r"companies/[^/]+/line-card/(?:specs/[^/]+|[^/]+)"
    r")/?$",
    re.IGNORECASE,
)


def http_method_min_level(method: str, path: str = "") -> str:
    m = (method or "GET").upper()
    if m in ("GET", "HEAD", "OPTIONS"):
        return "read"
    if m == "DELETE":
        p = (path or "").split("?", 1)[0].rstrip("/")
        if p and _WRITE_LEVEL_DELETE_RE.match(p):
            return "write"
        return "admin"
    if m in ("POST", "PUT", "PATCH"):
        return "write"
    return "read"


def fallback_permissions_for_role_code(role_code: str) -> dict[str, str]:
    defaults = DEFAULTS_BY_ROLE_CODE.get(role_code)
    if defaults:
        return dict(defaults)
    return dict(_NO_ROLE)


def permissions_dict_from_rows(rows: list[RoleModulePermission]) -> dict[str, str]:
    out: dict[str, str] = {code: "none" for code in MODULE_CODES}
    for row in rows:
        if row.module_code in MODULE_CODES:
            out[row.module_code] = normalize_level(row.access_level)
    return out


def permissions_for_role(role: Role) -> dict[str, str]:
    rows = list(role.module_permissions or ())
    if rows:
        return permissions_dict_from_rows(rows)
    return fallback_permissions_for_role_code(role.code)


def merge_role_permission_dicts(dicts: list[dict[str, str]]) -> dict[str, str]:
    merged: dict[str, str] = {code: "none" for code in MODULE_CODES}
    for d in dicts:
        for code in MODULE_CODES:
            merged[code] = max_level(merged[code], normalize_level(d.get(code)))
    return merged


def all_admin_permissions() -> dict[str, str]:
    return {code: "admin" for code in MODULE_CODES}


def effective_permissions_for_user(user: User | None) -> dict[str, str]:
    if user is None:
        return dict(_NO_ROLE)
    if user.is_superuser:
        return all_admin_permissions()
    role_codes = set()
    perm_dicts: list[dict[str, str]] = []
    for ur in user.roles or ():
        if ur.role is None:
            continue
        role_codes.add(ur.role.code)
        perm_dicts.append(permissions_for_role(ur.role))
    if "admin" in role_codes or "superuser" in role_codes:
        return all_admin_permissions()
    if not perm_dicts:
        return dict(_NO_ROLE)
    return merge_role_permission_dicts(perm_dicts)


def effective_permissions(cu: "CurrentUser") -> dict[str, str]:
    if cu.is_dev_admin:
        return all_admin_permissions()
    if getattr(cu, "module_access", None):
        return cu.module_access
    if cu.user is None:
        return dict(_NO_ROLE)
    return effective_permissions_for_user(cu.user)


def module_level(cu: "CurrentUser", module_code: str) -> str:
    if module_code not in MODULE_CODES:
        return "none"
    return effective_permissions(cu).get(module_code, "none")


def has_module_access(cu: "CurrentUser", module_code: str, min_level: str = "read") -> bool:
    return level_rank(module_level(cu, module_code)) >= level_rank(normalize_level(min_level))


def require_module(cu: "CurrentUser", module_code: str, min_level: str = "read") -> None:
    if cu.is_dev_admin:
        return
    if cu.user is None:
        raise ModuleAccessError("authentication required", 401)
    if not has_module_access(cu, module_code, min_level):
        raise ModuleAccessError(
            f"access denied: {module_code} requires {min_level} or higher",
            403,
        )


def require_module_for_request(
    cu: "CurrentUser", module_code: str, method: str, path: str = ""
) -> None:
    require_module(cu, module_code, http_method_min_level(method, path))


def load_user_with_roles(user_id: uuid.UUID) -> User | None:
    return db.session.scalar(
        select(User)
        .where(User.id == user_id)
        .options(
            selectinload(User.roles).selectinload(UserRole.role).selectinload(Role.module_permissions),
        )
    )


def capabilities_for_user(user: User | None, role_codes: frozenset[str], is_superuser: bool) -> dict[str, Any]:
    from .project_scope import assigned_project_count_for_user, project_scope_for_user

    perms = effective_permissions_for_user(user) if user else dict(_NO_ROLE)
    if is_superuser:
        perms = all_admin_permissions()
    scope = project_scope_for_user(
        user.id if user else None,
        role_codes,
        is_superuser=is_superuser,
    )
    can_admin_delete = bool(is_superuser)
    if not can_admin_delete:
        can_admin_delete = "admin" in role_codes or "superuser" in role_codes
    if not can_admin_delete:
        can_admin_delete = any(level_rank(v) >= level_rank("admin") for v in perms.values())
    out: dict[str, Any] = {
        "modules": perms,
        "role_codes": sorted(role_codes),
        "is_superuser": is_superuser,
        "can_admin_delete": can_admin_delete,
        "catalog": catalog_public(),
        "project_scope": scope,
    }
    if scope == "assigned":
        out["assigned_project_count"] = assigned_project_count_for_user(
            user.id if user else None
        )
    from .applicant import is_applicant_only_user

    out["applicant_only"] = is_applicant_only_user(user) if user else False
    return out


def validate_permissions_payload(raw: Any) -> dict[str, str]:
    if not isinstance(raw, dict):
        raise ValueError("permissions must be an object")
    out: dict[str, str] = {}
    for key, val in raw.items():
        code = str(key).strip()
        if code not in MODULE_CODES:
            raise ValueError(f"unknown module code: {code}")
        level = normalize_level(str(val) if val is not None else "none")
        if level not in ALL_LEVELS:
            raise ValueError(f"invalid access level for {code}")
        out[code] = level
    return out
