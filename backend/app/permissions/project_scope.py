"""Project-level access scoping (assigned jobs vs company-wide)."""
from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Optional

from sqlalchemy import false, select, true

from ..extensions import db
from ..models import Project, ProjectMember

if TYPE_CHECKING:
    from ..api._perms import CurrentUser

ALL_PROJECTS_ROLE_CODES = frozenset({"admin", "executive", "superuser"})


def can_see_all_projects_for(
    *,
    role_codes: frozenset[str],
    is_superuser: bool = False,
    is_dev_admin: bool = False,
) -> bool:
    if is_dev_admin or is_superuser:
        return True
    return bool(role_codes & ALL_PROJECTS_ROLE_CODES)


def can_see_all_projects(cu: "CurrentUser") -> bool:
    return can_see_all_projects_for(
        role_codes=cu.role_codes,
        is_superuser=bool(cu.user and cu.user.is_superuser),
        is_dev_admin=cu.is_dev_admin,
    )


def assigned_project_ids(cu: "CurrentUser") -> Optional[frozenset[uuid.UUID]]:
    """Return None when the user may see all projects; else assigned project IDs."""
    if can_see_all_projects(cu):
        return None
    if cu.id is None:
        return frozenset()
    rows = db.session.scalars(
        select(ProjectMember.project_id).where(ProjectMember.user_id == cu.id)
    ).all()
    return frozenset(rows)


def assigned_project_count(cu: "CurrentUser") -> Optional[int]:
    ids = assigned_project_ids(cu)
    if ids is None:
        return None
    return len(ids)


def project_scope_label(cu: "CurrentUser") -> str:
    return "all" if can_see_all_projects(cu) else "assigned"


def project_scope_for_user(
    user_id: uuid.UUID | None,
    role_codes: frozenset[str],
    *,
    is_superuser: bool = False,
    is_dev_admin: bool = False,
) -> str:
    if can_see_all_projects_for(
        role_codes=role_codes, is_superuser=is_superuser, is_dev_admin=is_dev_admin
    ):
        return "all"
    return "assigned"


def assigned_project_count_for_user(user_id: uuid.UUID | None) -> Optional[int]:
    if user_id is None:
        return 0
    rows = db.session.scalars(
        select(ProjectMember.project_id).where(ProjectMember.user_id == user_id)
    ).all()
    return len(rows)


def _project_row_exists(project_id: uuid.UUID) -> bool:
    return (
        db.session.scalar(
            select(Project.id).where(Project.id == project_id, Project.deleted_at.is_(None))
        )
        is not None
    )


def user_can_access_project(cu: "CurrentUser", project_id: uuid.UUID) -> bool:
    if not _project_row_exists(project_id):
        return False
    allowed = assigned_project_ids(cu)
    if allowed is None:
        return True
    return project_id in allowed


def project_access_clause(cu: "CurrentUser"):
    """SQLAlchemy filter for Project queries; use with .where(clause)."""
    allowed = assigned_project_ids(cu)
    if allowed is None:
        return true()
    if not allowed:
        return false()
    return Project.id.in_(allowed)
