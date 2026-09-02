"""Field time-clock punches — thin wrappers over the shared time service."""
from __future__ import annotations

import uuid
from typing import Any, Mapping

from sqlalchemy import select

from ..extensions import db
from ..models import CostCode
from ._field_service import FieldApiError, _require_project_access
from ._perms import CurrentUser
from ._time_service import TimeApiError, list_me as unified_list_me, punch as unified_punch


def _wrap_punch(data: Mapping[str, Any], cu: CurrentUser, action: str) -> dict[str, Any]:
    payload = dict(data)
    payload["action"] = action
    if "local_id" not in payload and "client_id" in payload:
        payload["local_id"] = payload.get("client_id")
    try:
        return unified_punch(payload, cu)
    except TimeApiError as exc:
        raise FieldApiError(exc.message, exc.status) from exc


def clock_in(data: Mapping[str, Any], cu: CurrentUser) -> dict[str, Any]:
    return _wrap_punch(data, cu, "clock_in")


def clock_out(data: Mapping[str, Any], cu: CurrentUser) -> dict[str, Any]:
    return _wrap_punch(data, cu, "clock_out")


def break_start(data: Mapping[str, Any], cu: CurrentUser) -> dict[str, Any]:
    return _wrap_punch(data, cu, "break_start")


def break_end(data: Mapping[str, Any], cu: CurrentUser) -> dict[str, Any]:
    return _wrap_punch(data, cu, "break_end")


def switch_job(data: Mapping[str, Any], cu: CurrentUser) -> dict[str, Any]:
    return _wrap_punch(data, cu, "switch")


def list_me(cu: CurrentUser) -> dict[str, Any]:
    try:
        return unified_list_me(cu)
    except TimeApiError as exc:
        raise FieldApiError(exc.message, exc.status) from exc


def list_cost_codes(project_id: uuid.UUID, cu: CurrentUser) -> dict[str, Any]:
    _require_project_access(cu, project_id)
    jcc = list(
        db.session.scalars(
            select(CostCode).where(CostCode.project_id == project_id, CostCode.is_active.is_(True)).order_by(CostCode.code)
        ).all()
    )
    items = [
        {
            "id": str(c.id),
            "project_id": str(c.project_id),
            "code": c.code,
            "description": c.description or "",
            "is_active": c.is_active,
        }
        for c in jcc
    ]
    return {"items": items, "total": len(items), "entity": "cost_codes"}
