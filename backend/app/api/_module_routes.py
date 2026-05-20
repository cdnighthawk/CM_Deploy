"""Map API paths to module codes for before_request enforcement."""
from __future__ import annotations

import re

# Longest-prefix-first tuples: (path_prefix, module_code or tuple of codes)
_PREFIX_RULES: list[tuple[str, str | tuple[str, ...]]] = [
    ("/api/ai", "ai"),
    ("/api/v1/admin/purge-test-users", "user_admin"),
    ("/api/v1/admin/users", "user_admin"),
    ("/api/v1/admin/roles", "user_admin"),
    ("/api/v1/hrms", "hrms"),
    ("/api/v1/hr/", "hr"),
    ("/api/v1/playbooks", "playbooks"),
    ("/api/v1/reports", "reports"),
    ("/api/v1/invoice-delivery-methods", "projects"),
    ("/api/v1/lead-estimates", ("leads", "estimate")),
    ("/api/v1/calendar-events", ("projects", "procurement")),
    ("/api/v1/projects", "projects"),
    ("/api/v1/rfis", "projects"),
    ("/api/v1/rfi-", "projects"),
    ("/api/v1/drawings", "projects"),
    ("/api/v1/spec-sections", "projects"),
    ("/api/v1/submittals", "projects"),
    ("/api/v1/documents", "documents"),
    ("/api/v1/commitments", "procurement"),
    ("/api/v1/material-orders", "procurement"),
    ("/api/v1/pay-applications", "procurement"),
    ("/api/v1/prime-contract", "procurement"),
    ("/api/v1/rfp", "procurement"),
    ("/api/v1/power-bi", "reports"),
    ("/api/v1/safety", "safety"),
    ("/api/v1/companies", "crm"),
    ("/api/v1/contacts", "crm"),
]

_EXEMPT_PREFIXES = (
    "/api/v1/auth/",
    "/api/v1/me",
    "/api/v1/permissions/",
    "/api/v1/__debug/",
    # Self-service hire wizard (application, I-9, W-4); auth enforced per route, not HR module role.
    "/api/v1/hr/me",
)

_EXEMPT_EXACT = frozenset(
    {
        "/api/v1/auth/status",
        "/api/v1/auth/register",
        "/api/v1/auth/mobile/login",
        "/api/v1/auth/mobile/refresh",
    }
)


def resolve_modules(path: str) -> tuple[str, ...] | None:
    """Return module code(s) for path, or None if route is not module-gated."""
    p = path.rstrip("/") or path
    if p in _EXEMPT_EXACT:
        return None
    for prefix in _EXEMPT_PREFIXES:
        if p.startswith(prefix):
            return None
    for prefix, mod in sorted(_PREFIX_RULES, key=lambda x: -len(x[0])):
        if p.startswith(prefix):
            if isinstance(mod, tuple):
                return mod
            return (mod,)
    return None
