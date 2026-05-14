"""CRUD helpers for project-scoped installation / work windows."""
from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from sqlalchemy import func, select

from ..extensions import db
from ..models import ProjectScheduleItem


def schedule_item_public(row: ProjectScheduleItem) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "project_id": str(row.project_id),
        "title": row.title,
        "start_date": row.start_date.isoformat(),
        "end_date": row.end_date.isoformat(),
        "crew_label": row.crew_label,
        "sort_order": row.sort_order,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def _parse_date(val: Any, field: str) -> date:
    if val is None:
        raise ValueError(f"missing {field}")
    if isinstance(val, date):
        return val
    s = str(val).strip()
    if len(s) >= 10:
        s = s[:10]
    return date.fromisoformat(s)


def _validate_range(start: date, end: date) -> None:
    if start > end:
        raise ValueError("start_date must be on or before end_date")


def _next_sort_order(project_id: uuid.UUID) -> int:
    m = db.session.scalar(
        select(func.coalesce(func.max(ProjectScheduleItem.sort_order), -1)).where(
            ProjectScheduleItem.project_id == project_id
        )
    )
    return int(m) + 1 if m is not None else 0


def list_schedule_items(project_id: uuid.UUID) -> list[dict[str, Any]]:
    q = (
        select(ProjectScheduleItem)
        .where(ProjectScheduleItem.project_id == project_id)
        .order_by(
            ProjectScheduleItem.sort_order,
            ProjectScheduleItem.start_date,
            ProjectScheduleItem.id,
        )
    )
    rows = db.session.scalars(q).all()
    return [schedule_item_public(r) for r in rows]


def _load_item(project_id: uuid.UUID, item_id: uuid.UUID) -> ProjectScheduleItem | None:
    return db.session.scalar(
        select(ProjectScheduleItem).where(
            ProjectScheduleItem.project_id == project_id,
            ProjectScheduleItem.id == item_id,
        )
    )


def create_schedule_item(project_id: uuid.UUID, data: dict[str, Any]) -> dict[str, Any]:
    title = (data.get("title") or "").strip()
    if not title:
        raise ValueError("title is required")
    start = _parse_date(data.get("start_date"), "start_date")
    end = _parse_date(data.get("end_date"), "end_date")
    _validate_range(start, end)
    crew_raw = data.get("crew_label")
    crew: str | None
    if crew_raw is None:
        crew = None
    else:
        crew_s = str(crew_raw).strip()
        crew = crew_s[:200] if crew_s else None
    if "sort_order" in data and data["sort_order"] is not None:
        try:
            sort_order_i = int(data["sort_order"])
        except (TypeError, ValueError) as e:
            raise ValueError("invalid sort_order") from e
    else:
        sort_order_i = _next_sort_order(project_id)
    row = ProjectScheduleItem(
        project_id=project_id,
        title=title[:300],
        start_date=start,
        end_date=end,
        crew_label=crew,
        sort_order=sort_order_i,
    )
    db.session.add(row)
    db.session.flush()
    return schedule_item_public(row)


def patch_schedule_item(project_id: uuid.UUID, item_id: uuid.UUID, data: dict[str, Any]) -> dict[str, Any] | None:
    row = _load_item(project_id, item_id)
    if row is None:
        return None
    if "title" in data:
        t = str(data["title"] or "").strip()
        if not t:
            raise ValueError("title cannot be empty")
        row.title = t[:300]
    start = row.start_date
    end = row.end_date
    if "start_date" in data:
        start = _parse_date(data["start_date"], "start_date")
    if "end_date" in data:
        end = _parse_date(data["end_date"], "end_date")
    _validate_range(start, end)
    row.start_date = start
    row.end_date = end
    if "crew_label" in data:
        cr = data["crew_label"]
        if cr is None or str(cr).strip() == "":
            row.crew_label = None
        else:
            row.crew_label = str(cr).strip()[:200]
    if "sort_order" in data and data["sort_order"] is not None:
        try:
            row.sort_order = int(data["sort_order"])
        except (TypeError, ValueError) as e:
            raise ValueError("invalid sort_order") from e
    db.session.flush()
    return schedule_item_public(row)


def delete_schedule_item(project_id: uuid.UUID, item_id: uuid.UUID) -> bool:
    row = _load_item(project_id, item_id)
    if row is None:
        return False
    db.session.delete(row)
    return True
