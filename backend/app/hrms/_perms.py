"""HRMS access helpers (roles + superuser + dev admin)."""
from __future__ import annotations

from ..api._perms import CurrentUser


def can_access_hrms(cu: CurrentUser) -> bool:
    """Any authenticated actor (or dev synthetic admin) may open HRMS shell; row-level rules come per-endpoint."""
    if cu.is_dev_admin:
        return True
    return cu.id is not None


def is_hr_admin(cu: CurrentUser) -> bool:
    if cu.is_dev_admin:
        return True
    return cu.has_role("admin", "superuser", "hr_admin")


def is_hr_manager(cu: CurrentUser) -> bool:
    return is_hr_admin(cu) or cu.has_role("hr_manager")
