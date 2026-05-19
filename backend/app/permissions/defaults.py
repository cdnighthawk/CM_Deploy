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
    "ai": "read",
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
    "ai": "read",
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
    "ai": "none",
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
    "ai": "none",
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
    "ai": "none",
}

_EXECUTIVE: dict[str, str] = {
    **{k: "read" for k in MODULE_CODES},
    "user_admin": "none",
    "hr": "write",
    "hrms": "write",
    "reports": "admin",
    "ai": "read",
}

_PROJECT_MANAGER: dict[str, str] = {
    "dashboard": "read",
    "leads": "read",
    "estimate": "read",
    "projects": "write",
    "safety": "write",
    "crm": "read",
    "documents": "write",
    "hr": "read",
    "hrms": "read",
    "playbooks": "write",
    "user_admin": "none",
    "procurement": "write",
    "reports": "read",
    "ai": "read",
}

_SUPERINTENDENT: dict[str, str] = {
    "dashboard": "read",
    "leads": "none",
    "estimate": "none",
    "projects": "write",
    "safety": "write",
    "crm": "none",
    "documents": "write",
    "hr": "read",
    "hrms": "read",
    "playbooks": "write",
    "user_admin": "none",
    "procurement": "read",
    "reports": "read",
    "ai": "read",
}

_PROJECT_ENGINEER: dict[str, str] = {
    "dashboard": "read",
    "leads": "none",
    "estimate": "read",
    "projects": "write",
    "safety": "read",
    "crm": "none",
    "documents": "write",
    "hr": "read",
    "hrms": "read",
    "playbooks": "read",
    "user_admin": "none",
    "procurement": "read",
    "reports": "read",
    "ai": "read",
}

_ESTIMATOR: dict[str, str] = {
    "dashboard": "read",
    "leads": "write",
    "estimate": "write",
    "projects": "read",
    "safety": "none",
    "crm": "write",
    "documents": "read",
    "hr": "none",
    "hrms": "none",
    "playbooks": "none",
    "user_admin": "none",
    "procurement": "none",
    "reports": "read",
    "ai": "read",
}

_PROJECT_ACCOUNTANT: dict[str, str] = {
    "dashboard": "read",
    "leads": "none",
    "estimate": "none",
    "projects": "read",
    "safety": "none",
    "crm": "none",
    "documents": "read",
    "hr": "none",
    "hrms": "read",
    "playbooks": "none",
    "user_admin": "none",
    "procurement": "write",
    "reports": "write",
    "ai": "read",
}

_SAFETY_MANAGER: dict[str, str] = {
    "dashboard": "read",
    "leads": "none",
    "estimate": "none",
    "projects": "read",
    "safety": "admin",
    "crm": "none",
    "documents": "read",
    "hr": "read",
    "hrms": "read",
    "playbooks": "read",
    "user_admin": "none",
    "procurement": "none",
    "reports": "read",
    "ai": "read",
}

_OFFICE_COORDINATOR: dict[str, str] = {
    "dashboard": "read",
    "leads": "read",
    "estimate": "none",
    "projects": "read",
    "safety": "read",
    "crm": "write",
    "documents": "write",
    "hr": "none",
    "hrms": "none",
    "playbooks": "read",
    "user_admin": "none",
    "procurement": "none",
    "reports": "none",
    "ai": "read",
}

_FIELD_READONLY: dict[str, str] = {
    "dashboard": "read",
    "leads": "none",
    "estimate": "none",
    "projects": "read",
    "safety": "read",
    "crm": "none",
    "documents": "read",
    "hr": "none",
    "hrms": "none",
    "playbooks": "read",
    "user_admin": "none",
    "procurement": "none",
    "reports": "none",
    "ai": "read",
}

# Users with no roles: dashboard read only
_NO_ROLE: dict[str, str] = {code: "none" for code in MODULE_CODES}
_NO_ROLE["dashboard"] = "read"

DEFAULTS_BY_ROLE_CODE: dict[str, dict[str, str]] = {
    "admin": _ALL_ADMIN,
    "superuser": _ALL_ADMIN,
    "executive": _EXECUTIVE,
    "project_manager": _PROJECT_MANAGER,
    "superintendent": _SUPERINTENDENT,
    "project_engineer": _PROJECT_ENGINEER,
    "estimator": _ESTIMATOR,
    "project_accountant": _PROJECT_ACCOUNTANT,
    "safety_manager": _SAFETY_MANAGER,
    "office_coordinator": _OFFICE_COORDINATOR,
    "field_readonly": _FIELD_READONLY,
    # Legacy codes (backward compatibility)
    "standard": _STANDARD,
    "read_only": _READ_ONLY,
    "readonly": _READ_ONLY,
    "hr_admin": _HR_ADMIN,
    "hr_manager": _HR_MANAGER,
    "hr_employee": _HR_EMPLOYEE,
}

CM_ROLE_DEFINITIONS: list[tuple[str, str, str]] = [
    ("admin", "Admin", "Full system access; all projects"),
    ("executive", "Executive", "Company-wide read; reports admin; all projects"),
    ("project_manager", "Project Manager", "Assigned projects; full project tools"),
    ("superintendent", "Superintendent", "Assigned projects; field leadership"),
    ("project_engineer", "Project Engineer", "Assigned projects; technical docs and RFIs"),
    ("estimator", "Estimator", "Assigned projects; leads and estimating"),
    ("project_accountant", "Project Accountant", "Assigned projects; procurement and reports"),
    ("safety_manager", "Safety Manager", "Assigned projects; safety admin"),
    ("office_coordinator", "Office Coordinator", "Assigned projects; CRM and documents"),
    ("field_readonly", "Field (read-only)", "Assigned projects; read-only access"),
]
