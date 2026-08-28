"""CRUD helpers for project-scoped installation / work windows."""
from __future__ import annotations

import uuid
from datetime import date, timedelta
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import selectinload

from ..extensions import db
from ..models import Project, ProjectScheduleItem, User
from ._in_app_notifications import create_in_app_notification
from ._notifications import send_plain_notification_email
from ._perms import CurrentUser


def _user_display_name(u: User | None) -> str | None:
    if u is None:
        return None
    name = " ".join(p for p in (u.first_name, u.last_name) if p).strip()
    return name or (u.email or None)


def schedule_item_public(row: ProjectScheduleItem) -> dict[str, Any]:
    assignee = row.assignee
    return {
        "id": str(row.id),
        "project_id": str(row.project_id),
        "title": row.title,
        "start_date": row.start_date.isoformat(),
        "end_date": row.end_date.isoformat(),
        "crew_label": row.crew_label,
        "assignee_user_id": str(row.assignee_user_id) if row.assignee_user_id else None,
        "assignee_name": _user_display_name(assignee),
        "assignee_email": assignee.email if assignee else None,
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


def _parse_assignee_user_id(data: dict[str, Any]) -> uuid.UUID | None:
    raw = data.get("assignee_user_id")
    if raw is None and "assignee_id" in data:
        raw = data.get("assignee_id")
    if raw is None or str(raw).strip() == "":
        return None
    try:
        uid = uuid.UUID(str(raw).strip())
    except (TypeError, ValueError) as e:
        raise ValueError("invalid assignee_user_id") from e
    user = db.session.get(User, uid)
    if user is None or not user.is_active:
        raise ValueError("assignee not found")
    return uid


def _schedule_item_url(project_id: uuid.UUID) -> str:
    return f"/construction/project-detail.html?id={project_id}"


def notify_schedule_assignee(
    row: ProjectScheduleItem,
    *,
    event: str,
    actor: CurrentUser | None = None,
) -> None:
    """In-app + email when a calendar window is assigned or due soon."""
    if row.assignee_user_id is None:
        return
    user = row.assignee or db.session.get(User, row.assignee_user_id)
    if user is None:
        return
    actor_id = actor.id if actor is not None else None
    if actor_id is not None and user.id == actor_id:
        return
    project = row.project or db.session.get(Project, row.project_id)
    project_name = (project.name if project else None) or "Project"
    window = f"{row.start_date.isoformat()} – {row.end_date.isoformat()}"
    if event == "assigned":
        title = f"Calendar task assigned: {row.title}"
        body = f"{row.title} on {project_name} ({window})."
        if row.crew_label:
            body += f" Crew: {row.crew_label}."
        actor_email = actor.user.email if actor and actor.user else None
        if actor_email:
            body += f" Assigned by {actor_email}."
        subject = f"[USIS Calendar] Assigned: {row.title}"
    else:
        title = f"Calendar reminder: {row.title}"
        today = date.today()
        when = "today" if row.start_date <= today else "tomorrow"
        body = f"{row.title} on {project_name} starts {when} ({window})."
        if row.crew_label:
            body += f" Crew: {row.crew_label}."
        subject = f"[USIS Calendar] Reminder: {row.title}"
    url = _schedule_item_url(row.project_id)
    create_in_app_notification(user_id=user.id, title=title, body=body, url=url)
    if user.email:
        send_plain_notification_email(to=user.email, subject=subject, body=body + f"\n\n{url}")


def send_due_schedule_reminders(*, as_of: date | None = None) -> dict[str, Any]:
    """Notify assignees the day before or the morning a window starts. Once per day."""
    today = as_of or date.today()
    window_end = today + timedelta(days=1)
    rows = db.session.scalars(
        select(ProjectScheduleItem)
        .options(
            selectinload(ProjectScheduleItem.assignee),
            selectinload(ProjectScheduleItem.project),
        )
        .where(
            ProjectScheduleItem.assignee_user_id.is_not(None),
            ProjectScheduleItem.start_date >= today,
            ProjectScheduleItem.start_date <= window_end,
            or_(
                ProjectScheduleItem.reminder_sent_on.is_(None),
                ProjectScheduleItem.reminder_sent_on != today,
            ),
        )
    ).all()
    sent = 0
    for row in rows:
        notify_schedule_assignee(row, event="reminder")
        row.reminder_sent_on = today
        sent += 1
    if sent:
        db.session.flush()
    return {"sent": sent, "as_of": today.isoformat(), "entity": "calendar_reminders"}


def list_schedule_items(project_id: uuid.UUID) -> list[dict[str, Any]]:
    q = (
        select(ProjectScheduleItem)
        .options(selectinload(ProjectScheduleItem.assignee))
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
        select(ProjectScheduleItem)
        .options(selectinload(ProjectScheduleItem.assignee), selectinload(ProjectScheduleItem.project))
        .where(
            ProjectScheduleItem.project_id == project_id,
            ProjectScheduleItem.id == item_id,
        )
    )


def create_schedule_item(
    project_id: uuid.UUID,
    data: dict[str, Any],
    actor: CurrentUser | None = None,
) -> dict[str, Any]:
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
    assignee_id = None
    if "assignee_user_id" in data or "assignee_id" in data:
        assignee_id = _parse_assignee_user_id(data)
    row = ProjectScheduleItem(
        project_id=project_id,
        title=title[:300],
        start_date=start,
        end_date=end,
        crew_label=crew,
        assignee_user_id=assignee_id,
        sort_order=sort_order_i,
    )
    db.session.add(row)
    db.session.flush()
    if assignee_id:
        db.session.refresh(row, attribute_names=["assignee", "project"])
        notify_schedule_assignee(row, event="assigned", actor=actor)
    return schedule_item_public(row)


def patch_schedule_item(
    project_id: uuid.UUID,
    item_id: uuid.UUID,
    data: dict[str, Any],
    actor: CurrentUser | None = None,
) -> dict[str, Any] | None:
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
    prev_assignee = row.assignee_user_id
    if "assignee_user_id" in data or "assignee_id" in data:
        row.assignee_user_id = _parse_assignee_user_id(data)
        if row.assignee_user_id != prev_assignee:
            row.reminder_sent_on = None
    if "sort_order" in data and data["sort_order"] is not None:
        try:
            row.sort_order = int(data["sort_order"])
        except (TypeError, ValueError) as e:
            raise ValueError("invalid sort_order") from e
    db.session.flush()
    if row.assignee_user_id and row.assignee_user_id != prev_assignee:
        db.session.refresh(row, attribute_names=["assignee", "project"])
        notify_schedule_assignee(row, event="assigned", actor=actor)
    return schedule_item_public(row)


def delete_schedule_item(project_id: uuid.UUID, item_id: uuid.UUID) -> bool:
    row = _load_item(project_id, item_id)
    if row is None:
        return False
    db.session.delete(row)
    return True
