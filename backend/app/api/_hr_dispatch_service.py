"""HR employee dispatch paperwork — per project revisions."""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Any, Mapping, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from ..extensions import db
from ..models import HrEmployeeDispatch, HrEmployeePayScale, Project
from ._perms import CurrentUser
from ._rfi_service import ApiError, _parse_uuid


def _can_view_hr_employee_detail(cu: CurrentUser, target_user_id: uuid.UUID) -> bool:
    if cu.is_dev_admin:
        return True
    if cu.has_role("admin", "hr_admin", "executive"):
        return True
    if cu.id is not None and cu.id == target_user_id:
        return True
    return False


def _can_edit_hr_employee_records(cu: CurrentUser) -> bool:
    return cu.is_dev_admin or cu.has_role("admin", "hr_admin", "executive")


def _iso(d: date | None) -> str | None:
    if d is None:
        return None
    return d.isoformat()


def _parse_date(raw: Any) -> date | None:
    if raw is None or raw == "":
        return None
    if isinstance(raw, date):
        return raw
    s = str(raw).strip()
    if not s:
        return None
    try:
        return date.fromisoformat(s[:10])
    except ValueError:
        return None


def _dec(v: Any) -> Decimal | None:
    if v is None:
        return None
    try:
        return Decimal(str(v))
    except Exception:
        return None


def _dispatch_public(row: HrEmployeeDispatch, project_name: str | None = None) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "user_id": str(row.user_id),
        "project_id": str(row.project_id),
        "project_name": project_name,
        "revision": row.revision,
        "effective_date": _iso(row.effective_date),
        "supersedes_id": str(row.supersedes_id) if row.supersedes_id else None,
        "pay_scale_id": str(row.pay_scale_id) if row.pay_scale_id else None,
        "hourly_rate_snapshot": str(row.hourly_rate_snapshot) if row.hourly_rate_snapshot is not None else None,
        "notes": row.notes,
        "union_document_file_id": str(row.union_document_file_id) if row.union_document_file_id else None,
        "document_id": str(row.document_id) if row.document_id else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def list_employee_dispatches(user_id: uuid.UUID, cu: CurrentUser) -> dict[str, Any]:
    if not _can_view_hr_employee_detail(cu, user_id):
        raise ApiError("forbidden", 403)
    stmt = (
        select(HrEmployeeDispatch, Project.name)
        .join(Project, Project.id == HrEmployeeDispatch.project_id)
        .where(HrEmployeeDispatch.user_id == user_id)
        .order_by(Project.name.asc(), HrEmployeeDispatch.revision.desc())
    )
    rows = db.session.execute(stmt).all()
    items = [_dispatch_public(d, pname) for d, pname in rows]
    return {"entity": "hr_employee_dispatches", "items": items}


def create_employee_dispatch(user_id: uuid.UUID, data: Mapping[str, Any], cu: CurrentUser) -> dict[str, Any]:
    if not _can_edit_hr_employee_records(cu):
        raise ApiError("forbidden", 403)
    project_id = _parse_uuid(data.get("project_id"))
    if not project_id:
        raise ApiError("project_id is required", 400)
    proj = db.session.get(Project, project_id)
    if proj is None:
        raise ApiError("project not found", 404)

    prev_id = _parse_uuid(data.get("supersedes_id"))
    prev: HrEmployeeDispatch | None = None
    if prev_id:
        prev = db.session.get(HrEmployeeDispatch, prev_id)
        if prev is None or prev.user_id != user_id:
            raise ApiError("invalid supersedes_id", 400)
        if prev.project_id != project_id:
            raise ApiError("supersedes dispatch must be same project", 400)

    max_rev = db.session.scalar(
        select(func.coalesce(func.max(HrEmployeeDispatch.revision), 0)).where(
            HrEmployeeDispatch.user_id == user_id,
            HrEmployeeDispatch.project_id == project_id,
        )
    )
    revision = int(max_rev or 0) + 1

    pay_scale_id = _parse_uuid(data.get("pay_scale_id"))
    hourly_snap = _dec(data.get("hourly_rate_snapshot"))
    if pay_scale_id:
        ps = db.session.get(HrEmployeePayScale, pay_scale_id)
        if ps is None or ps.user_id != user_id:
            raise ApiError("invalid pay_scale_id", 400)
        if hourly_snap is None and ps.hourly_rate is not None:
            hourly_snap = ps.hourly_rate

    row = HrEmployeeDispatch(
        user_id=user_id,
        project_id=project_id,
        revision=revision,
        effective_date=_parse_date(data.get("effective_date")) or date.today(),
        supersedes_id=prev.id if prev else None,
        pay_scale_id=pay_scale_id,
        hourly_rate_snapshot=hourly_snap,
        notes=(str(data.get("notes")).strip() or None) if data.get("notes") is not None else None,
        union_document_file_id=_parse_uuid(data.get("union_document_file_id")),
        document_id=_parse_uuid(data.get("document_id")),
    )
    db.session.add(row)
    db.session.commit()
    pname = proj.name
    return {"entity": "hr_employee_dispatch", "item": _dispatch_public(row, pname)}
