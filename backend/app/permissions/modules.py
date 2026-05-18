"""Company-wide module catalog for role-based access (matches construction nav)."""
from __future__ import annotations

from typing import Any, TypedDict

ALL_LEVELS = ("none", "read", "write", "admin")


class ModuleDef(TypedDict):
    code: str
    name: str
    description: str


MODULE_CATALOG: list[ModuleDef] = [
    {"code": "dashboard", "name": "Dashboard", "description": "Home dashboard"},
    {"code": "leads", "name": "Leads", "description": "Construction leads list"},
    {"code": "estimate", "name": "Estimate", "description": "Lead estimates / bidding"},
    {"code": "projects", "name": "Projects", "description": "Projects, RFIs, submittals, drawings"},
    {"code": "safety", "name": "Safety", "description": "Safety module"},
    {"code": "crm", "name": "CRM pipeline", "description": "CRM leads pipeline"},
    {"code": "documents", "name": "Documents", "description": "Documents hub"},
    {"code": "hr", "name": "HR", "description": "HR dashboard and employee records"},
    {"code": "hrms", "name": "HR suite", "description": "HRMS (leave, timesheets, etc.)"},
    {"code": "playbooks", "name": "Playbooks", "description": "Checklist playbooks"},
    {"code": "user_admin", "name": "User admin", "description": "Users and roles directory"},
    {"code": "procurement", "name": "Procurement", "description": "Commitments and procurement"},
    {"code": "reports", "name": "Reports", "description": "Reports"},
]

MODULE_CODES: frozenset[str] = frozenset(m["code"] for m in MODULE_CATALOG)


def catalog_public() -> list[dict[str, Any]]:
    return [dict(m) for m in MODULE_CATALOG]
