"""Default module permissions per role code (seeded on migration)."""
from __future__ import annotations

from .modules import MODULE_CODES

_ALL_ADMIN = {code: "admin" for code in MODULE_CODES}

_STANDARD: dict[str, str] = {
    "dashboard": "read",
    "leads": "write",
    "estimate": "write",
    "projects": "write",
    "safety": "write",
    "crm": "write",
    "documents": "write",
    "hr": "read",
    "hrms": "read",
    "playbooks": "write",
    "user_admin": "none",
    "procurement": "write",
    "reports": "read",
}

_READ_ONLY: dict[str, str] = {
    "dashboard": "read",
    "leads": "read",
    "estimate": "read",
    "projects": "read",
    "safety": "read",
    "crm": "read",
    "documents": "read",
    "hr": "read",
    "hrms": "read",
    "playbooks": "read",
    "user_admin": "none",
    "procurement": "read",
    "reports": "read",
}

_HR_ADMIN: dict[str, str] = {
    "dashboard": "read",
    "leads": "read",
    "estimate": "read",
    "projects": "read",
    "safety": "read",
    "crm": "none",
    "documents": "read",
    "hr": "admin",
    "hrms": "admin",
    "playbooks": "read",
    "user_admin": "none",
    "procurement": "none",
    "reports": "read",
}

_HR_MANAGER: dict[str, str] = {
    "dashboard": "read",
    "leads": "none",
    "estimate": "none",
    "projects": "none",
    "safety": "read",
    "crm": "none",
    "documents": "read",
    "hr": "write",
    "hrms": "write",
    "playbooks": "read",
    "user_admin": "none",
    "procurement": "none",
    "reports": "none",
}

_HR_EMPLOYEE: dict[str, str] = {
    "dashboard": "read",
    "leads": "none",
    "estimate": "none",
    "projects": "none",
    "safety": "read",
    "crm": "none",
    "documents": "read",
    "hr": "read",
    "hrms": "read",
    "playbooks": "read",
    "user_admin": "none",
    "procurement": "none",
    "reports": "none",
}

_EXECUTIVE: dict[str, str] = {
    **{k: "read" for k in MODULE_CODES},
    "user_admin": "none",
    "hr": "write",
    "hrms": "write",
    "reports": "admin",
}

# Users with no roles: dashboard read only
_NO_ROLE: dict[str, str] = {code: "none" for code in MODULE_CODES}
_NO_ROLE["dashboard"] = "read"

DEFAULTS_BY_ROLE_CODE: dict[str, dict[str, str]] = {
    "admin": _ALL_ADMIN,
    "superuser": _ALL_ADMIN,
    "standard": _STANDARD,
    "read_only": _READ_ONLY,
    "readonly": _READ_ONLY,
    "hr_admin": _HR_ADMIN,
    "hr_manager": _HR_MANAGER,
    "hr_employee": _HR_EMPLOYEE,
    "executive": _EXECUTIVE,
}
