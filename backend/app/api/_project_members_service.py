"""Project membership assignment (user ↔ project scoping)."""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import selectinload

from ..extensions import db
from ..models import Project, ProjectMember, User
from ._perms import CurrentUser, can_manage_directory_users


class ApiError(Exception):
    def __init__(self, message: str, status: int = 400):
        self.message = message
        self.status = status


def _require_membership_admin(cu: CurrentUser) -> None:
    if not can_manage_directory_users(cu):
        raise ApiError("forbidden", 403)


def _parse_project_ids(raw: Any) -> list[uuid.UUID]:
    if not isinstance(raw, list):
        raise ApiError("project_ids must be an array")
    out: list[uuid.UUID] = []
    seen: set[uuid.UUID] = set()
    for item in raw:
        try:
            pid = uuid.UUID(str(item).strip())
        except (TypeError, ValueError):
            raise ApiError("invalid project id in project_ids")
        if pid in seen:
            continue
        seen.add(pid)
        out.append(pid)
    return out


def membership_public(pm: ProjectMember) -> dict[str, Any]:
    return {
        "user_id": str(pm.user_id),
        "project_id": str(pm.project_id),
        "member_role": pm.member_role,
        "created_at": pm.created_at.isoformat() if pm.created_at else None,
    }


def list_user_project_memberships(cu: CurrentUser, user_id: uuid.UUID) -> dict[str, Any] | None:
    _require_membership_admin(cu)
    u = db.session.get(User, user_id)
    if u is None:
        return None
    rows = db.session.scalars(
        select(ProjectMember)
        .where(ProjectMember.user_id == user_id)
        .order_by(ProjectMember.created_at.asc())
    ).all()
    project_ids = [str(r.project_id) for r in rows]
    return {
        "user_id": str(user_id),
        "project_ids": project_ids,
        "items": [membership_public(r) for r in rows],
    }


def set_user_project_memberships(
    cu: CurrentUser,
    user_id: uuid.UUID,
    data: dict[str, Any],
) -> dict[str, Any] | None:
    _require_membership_admin(cu)
    u = db.session.get(User, user_id)
    if u is None:
        return None
    if "project_ids" not in data:
        raise ApiError("project_ids required")
    project_ids = _parse_project_ids(data.get("project_ids"))
    if project_ids:
        found = set(
            db.session.scalars(
                select(Project.id).where(
                    Project.id.in_(project_ids),
                    Project.deleted_at.is_(None),
                )
            ).all()
        )
        missing = [pid for pid in project_ids if pid not in found]
        if missing:
            raise ApiError("one or more projects not found")
    db.session.execute(delete(ProjectMember).where(ProjectMember.user_id == user_id))
    actor_id = cu.id
    for pid in project_ids:
        db.session.add(
            ProjectMember(
                user_id=user_id,
                project_id=pid,
                created_by_id=actor_id,
            )
        )
    db.session.flush()
    return list_user_project_memberships(cu, user_id)


def list_project_members(cu: CurrentUser, project_id: uuid.UUID) -> dict[str, Any] | None:
    _require_membership_admin(cu)
    p = db.session.get(Project, project_id)
    if p is None or p.deleted_at is not None:
        return None
    rows = db.session.scalars(
        select(ProjectMember)
        .where(ProjectMember.project_id == project_id)
        .options(selectinload(ProjectMember.user))
        .order_by(ProjectMember.created_at.asc())
    ).all()
    members = []
    for pm in rows:
        u = pm.user
        members.append(
            {
                "user_id": str(pm.user_id),
                "email": u.email if u else None,
                "first_name": u.first_name if u else None,
                "last_name": u.last_name if u else None,
                "member_role": pm.member_role,
            }
        )
    return {"project_id": str(project_id), "members": members}


def set_project_members(
    cu: CurrentUser,
    project_id: uuid.UUID,
    data: dict[str, Any],
) -> dict[str, Any] | None:
    _require_membership_admin(cu)
    p = db.session.get(Project, project_id)
    if p is None or p.deleted_at is not None:
        return None
    raw_ids = data.get("user_ids")
    if not isinstance(raw_ids, list):
        raise ApiError("user_ids must be an array")
    user_ids: list[uuid.UUID] = []
    seen: set[uuid.UUID] = set()
    for item in raw_ids:
        try:
            uid = uuid.UUID(str(item).strip())
        except (TypeError, ValueError):
            raise ApiError("invalid user id in user_ids")
        if uid in seen:
            continue
        seen.add(uid)
        user_ids.append(uid)
    if user_ids:
        found = set(db.session.scalars(select(User.id).where(User.id.in_(user_ids))).all())
        if len(found) != len(user_ids):
            raise ApiError("one or more users not found")
    db.session.execute(delete(ProjectMember).where(ProjectMember.project_id == project_id))
    actor_id = cu.id
    for uid in user_ids:
        db.session.add(
            ProjectMember(
                user_id=uid,
                project_id=project_id,
                created_by_id=actor_id,
            )
        )
    db.session.flush()
    return list_project_members(cu, project_id)
