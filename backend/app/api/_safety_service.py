"""Daily pre-task safety plans (Appendix E) and safety dashboard counts."""
from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any, Mapping

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.attributes import flag_modified

from ..extensions import db
from ..models import DailyPretask, Project, SafetyTrainingRecord, User
from ..models.safety import (
    DEFAULT_COMPANY_NAME,
    PRETASK_CHECKLIST_KEYS,
    PRETASK_STATUSES,
    default_pretask_attendees,
    default_pretask_tasks,
    empty_pretask_checklist,
)
from ._perms import CurrentUser
from ._serializers import iso


class SafetyApiError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message = message
        self.status = status


def _parse_date(raw: Any) -> date | None:
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    try:
        return date.fromisoformat(s[:10])
    except ValueError:
        return None


def _parse_uuid(raw: Any) -> uuid.UUID | None:
    if raw is None or raw == "":
        return None
    try:
        return uuid.UUID(str(raw).strip())
    except (TypeError, ValueError):
        return None


def _user_display_name(user: User | None) -> str:
    if user is None:
        return ""
    name = " ".join(p for p in (user.first_name, user.last_name) if p).strip()
    return name or (user.email or "")


def _require_project_access(cu: CurrentUser, project_id: uuid.UUID) -> Project:
    from ..permissions.project_scope import user_can_access_project

    project = db.session.get(Project, project_id)
    if project is None or getattr(project, "deleted_at", None) is not None:
        raise SafetyApiError("project not found", 404)
    if not user_can_access_project(cu, project_id):
        raise SafetyApiError("project not found", 404)
    return project


def _can_edit_submitted(cu: CurrentUser) -> bool:
    if cu.is_dev_admin:
        return True
    user = cu.user
    if user is not None and getattr(user, "is_superuser", False):
        return True
    return cu.has_role("admin") or cu.has_role("safety_manager")


def _normalize_checklist(raw: Any) -> dict[str, bool]:
    out = empty_pretask_checklist()
    if not isinstance(raw, Mapping):
        return out
    for key in PRETASK_CHECKLIST_KEYS:
        if key in raw:
            out[key] = bool(raw.get(key))
    return out


def _normalize_tasks(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return default_pretask_tasks()
    out: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, Mapping):
            continue
        out.append(
            {
                "jha_complete": bool(item.get("jha_complete")),
                "task": str(item.get("task") or "").strip(),
                "hazards": str(item.get("hazards") or "").strip(),
                "steps": str(item.get("steps") or "").strip(),
            }
        )
    return out or default_pretask_tasks()


def _normalize_attendees(raw: Any) -> list[dict[str, str]]:
    if not isinstance(raw, list):
        return default_pretask_attendees()
    out: list[dict[str, str]] = []
    for item in raw:
        if not isinstance(item, Mapping):
            continue
        out.append(
            {
                "print_name": str(item.get("print_name") or "").strip(),
                "signature": str(item.get("signature") or "").strip(),
            }
        )
    return out or default_pretask_attendees()


def _text(raw: Any, limit: int | None = None) -> str:
    s = "" if raw is None else str(raw)
    if limit is not None:
        return s[:limit]
    return s


def _new_draft(
    project_id: uuid.UUID,
    work_date: date,
    cu: CurrentUser,
    *,
    client_id: uuid.UUID | None = None,
) -> DailyPretask:
    if cu.id is None:
        raise SafetyApiError("sign in required", 401)
    return DailyPretask(
        project_id=project_id,
        work_date=work_date,
        crew_lead_user_id=cu.id,
        client_id=client_id,
        company_name=DEFAULT_COMPANY_NAME,
        area_of_work="",
        status="draft",
        checklist=empty_pretask_checklist(),
        tasks=default_pretask_tasks(),
        attendees=default_pretask_attendees(),
        created_by_user_id=cu.id,
    )


def pretask_public(row: DailyPretask) -> dict[str, Any]:
    project = row.project
    lead = row.crew_lead
    return {
        "id": str(row.id),
        "project_id": str(row.project_id),
        "project_name": project.name if project is not None else "",
        "project_number": getattr(project, "number", None) if project is not None else None,
        "work_date": row.work_date.isoformat(),
        "crew_lead_user_id": str(row.crew_lead_user_id),
        "crew_lead_name": _user_display_name(lead),
        "daily_report_id": str(row.daily_report_id) if row.daily_report_id else None,
        "client_id": str(row.client_id) if row.client_id else None,
        "company_name": row.company_name or DEFAULT_COMPANY_NAME,
        "area_of_work": row.area_of_work or "",
        "status": row.status,
        "checklist": _normalize_checklist(row.checklist),
        "tasks": _normalize_tasks(row.tasks),
        "near_miss": bool(row.near_miss),
        "near_miss_notes": row.near_miss_notes or "",
        "required_permits": row.required_permits or "",
        "items_concerns": row.items_concerns or "",
        "quality_previous_day": row.quality_previous_day or "",
        "present_items_concerns": row.present_items_concerns or "",
        "attendees": _normalize_attendees(row.attendees),
        "supervisor_name": row.supervisor_name or "",
        "supervisor_signature": row.supervisor_signature or "",
        "submitted_at": iso(row.submitted_at) if row.submitted_at else None,
        "created_at": iso(row.created_at),
        "updated_at": iso(row.updated_at),
    }


def pretask_list_item(row: DailyPretask) -> dict[str, Any]:
    filled_tasks = sum(1 for t in _normalize_tasks(row.tasks) if t.get("task"))
    signed = sum(1 for a in _normalize_attendees(row.attendees) if a.get("print_name"))
    project = row.project
    return {
        "id": str(row.id),
        "project_id": str(row.project_id),
        "project_name": project.name if project is not None else "",
        "project_number": getattr(project, "number", None) if project is not None else None,
        "work_date": row.work_date.isoformat(),
        "area_of_work": row.area_of_work or "",
        "status": row.status,
        "crew_lead_name": _user_display_name(row.crew_lead),
        "task_count": filled_tasks,
        "attendee_count": signed,
        "near_miss": bool(row.near_miss),
        "submitted_at": iso(row.submitted_at) if row.submitted_at else None,
        "updated_at": iso(row.updated_at),
    }


def _apply_payload(row: DailyPretask, data: Mapping[str, Any]) -> None:
    if "company_name" in data:
        name = _text(data.get("company_name"), 255).strip() or DEFAULT_COMPANY_NAME
        row.company_name = name
    if "area_of_work" in data:
        row.area_of_work = _text(data.get("area_of_work"), 255).strip()
    if "checklist" in data:
        row.checklist = _normalize_checklist(data.get("checklist"))
        flag_modified(row, "checklist")
    if "tasks" in data:
        row.tasks = _normalize_tasks(data.get("tasks"))
        flag_modified(row, "tasks")
    if "near_miss" in data:
        row.near_miss = bool(data.get("near_miss"))
    if "near_miss_notes" in data:
        row.near_miss_notes = _text(data.get("near_miss_notes"))
    if "required_permits" in data:
        row.required_permits = _text(data.get("required_permits"))
    if "items_concerns" in data:
        row.items_concerns = _text(data.get("items_concerns"))
    if "quality_previous_day" in data:
        row.quality_previous_day = _text(data.get("quality_previous_day"))
    if "present_items_concerns" in data:
        row.present_items_concerns = _text(data.get("present_items_concerns"))
    if "attendees" in data:
        row.attendees = _normalize_attendees(data.get("attendees"))
        flag_modified(row, "attendees")
    if "supervisor_name" in data:
        row.supervisor_name = _text(data.get("supervisor_name"), 255).strip()
    if "supervisor_signature" in data:
        row.supervisor_signature = _text(data.get("supervisor_signature"))
    if "daily_report_id" in data:
        report_id = _parse_uuid(data.get("daily_report_id"))
        if data.get("daily_report_id") and report_id is None:
            raise SafetyApiError("invalid daily_report_id", 400)
        row.daily_report_id = report_id


def _validate_submit(row: DailyPretask) -> None:
    checklist = _normalize_checklist(row.checklist)
    missing = [key for key, ok in checklist.items() if not ok]
    if missing:
        raise SafetyApiError("complete the pre-start checklist before submitting", 400)
    tasks = [t for t in _normalize_tasks(row.tasks) if t.get("task")]
    if not tasks:
        raise SafetyApiError("add at least one task before submitting", 400)
    if not (row.supervisor_name or "").strip():
        raise SafetyApiError("supervisor printed name is required to submit", 400)
    if not (row.area_of_work or "").strip():
        raise SafetyApiError("area of work is required to submit", 400)


def get_or_create_pretask(
    project_id: uuid.UUID,
    work_date: date,
    cu: CurrentUser,
    *,
    client_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    _require_project_access(cu, project_id)
    if cu.id is None:
        raise SafetyApiError("sign in required", 401)
    if client_id is not None:
        existing_client = db.session.scalar(select(DailyPretask).where(DailyPretask.client_id == client_id))
        if existing_client is not None:
            return {"item": pretask_public(existing_client), "entity": "daily_pretask", "created": False}
    row = db.session.scalar(
        select(DailyPretask).where(
            DailyPretask.project_id == project_id,
            DailyPretask.work_date == work_date,
            DailyPretask.crew_lead_user_id == cu.id,
        )
    )
    created = False
    if row is None:
        row = _new_draft(project_id, work_date, cu, client_id=client_id)
        db.session.add(row)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            row = db.session.scalar(
                select(DailyPretask).where(
                    DailyPretask.project_id == project_id,
                    DailyPretask.work_date == work_date,
                    DailyPretask.crew_lead_user_id == cu.id,
                )
            )
            if row is None:
                raise SafetyApiError("could not create daily pretask", 409)
        else:
            created = True
            db.session.refresh(row)
    return {"item": pretask_public(row), "entity": "daily_pretask", "created": created}


def create_pretask(project_id: uuid.UUID, data: Mapping[str, Any], cu: CurrentUser) -> dict[str, Any]:
    _require_project_access(cu, project_id)
    if cu.id is None:
        raise SafetyApiError("sign in required", 401)
    work_date = _parse_date(data.get("work_date")) or date.today()
    client_id = _parse_uuid(data.get("client_id"))
    if data.get("client_id") and client_id is None:
        raise SafetyApiError("invalid client_id", 400)
    if client_id is not None:
        existing_client = db.session.scalar(select(DailyPretask).where(DailyPretask.client_id == client_id))
        if existing_client is not None:
            return {"item": pretask_public(existing_client), "entity": "daily_pretask", "created": False}
    existing = db.session.scalar(
        select(DailyPretask).where(
            DailyPretask.project_id == project_id,
            DailyPretask.work_date == work_date,
            DailyPretask.crew_lead_user_id == cu.id,
        )
    )
    if existing is not None:
        if data:
            _apply_payload(existing, data)
            db.session.add(existing)
            db.session.commit()
            db.session.refresh(existing)
        return {"item": pretask_public(existing), "entity": "daily_pretask", "created": False}
    row = _new_draft(project_id, work_date, cu, client_id=client_id)
    _apply_payload(row, data)
    db.session.add(row)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise SafetyApiError("a pretask already exists for this project, date, and crew lead", 409)
    db.session.refresh(row)
    return {"item": pretask_public(row), "entity": "daily_pretask", "created": True}


def get_pretask(pretask_id: uuid.UUID, cu: CurrentUser) -> dict[str, Any]:
    row = db.session.get(DailyPretask, pretask_id)
    if row is None:
        raise SafetyApiError("daily pretask not found", 404)
    _require_project_access(cu, row.project_id)
    return {"item": pretask_public(row), "entity": "daily_pretask"}


def put_pretask(pretask_id: uuid.UUID, data: Mapping[str, Any], cu: CurrentUser) -> dict[str, Any]:
    row = db.session.get(DailyPretask, pretask_id)
    if row is None:
        raise SafetyApiError("daily pretask not found", 404)
    _require_project_access(cu, row.project_id)
    if row.status == "submitted" and not _can_edit_submitted(cu):
        raise SafetyApiError("daily pretask is submitted and locked", 403)
    _apply_payload(row, data)
    if "status" in data and data.get("status") is not None:
        status = str(data.get("status")).strip().lower()
        if status not in PRETASK_STATUSES:
            raise SafetyApiError("status must be draft or submitted", 400)
        if status == "submitted":
            _validate_submit(row)
            row.status = "submitted"
            if row.submitted_at is None:
                row.submitted_at = datetime.now(timezone.utc)
        elif status == "draft":
            if not _can_edit_submitted(cu) and row.status == "submitted":
                raise SafetyApiError("daily pretask is submitted and locked", 403)
            row.status = "draft"
            row.submitted_at = None
    db.session.add(row)
    db.session.commit()
    db.session.refresh(row)
    return {"item": pretask_public(row), "entity": "daily_pretask"}


def submit_pretask(pretask_id: uuid.UUID, data: Mapping[str, Any] | None, cu: CurrentUser) -> dict[str, Any]:
    payload = dict(data or {})
    payload["status"] = "submitted"
    return put_pretask(pretask_id, payload, cu)


def list_pretasks(
    cu: CurrentUser,
    *,
    project_id: uuid.UUID | None = None,
    work_date: date | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    status: str | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    from ..permissions.project_scope import assigned_project_ids

    q = select(DailyPretask)
    if project_id is not None:
        _require_project_access(cu, project_id)
        q = q.where(DailyPretask.project_id == project_id)
    else:
        allowed = assigned_project_ids(cu)
        if allowed is not None:
            if not allowed:
                return {"items": [], "total": 0, "entity": "daily_pretasks"}
            q = q.where(DailyPretask.project_id.in_(allowed))
    if work_date is not None:
        q = q.where(DailyPretask.work_date == work_date)
    if date_from is not None:
        q = q.where(DailyPretask.work_date >= date_from)
    if date_to is not None:
        q = q.where(DailyPretask.work_date <= date_to)
    if status:
        st = status.strip().lower()
        if st not in PRETASK_STATUSES:
            raise SafetyApiError("status must be draft or submitted", 400)
        q = q.where(DailyPretask.status == st)
    q = q.order_by(DailyPretask.work_date.desc(), DailyPretask.updated_at.desc())
    cap = max(1, min(int(limit), 200))
    rows = list(db.session.scalars(q.limit(cap)).all())
    return {"items": [pretask_list_item(r) for r in rows], "total": len(rows), "entity": "daily_pretasks"}


def safety_cert_counts() -> dict[str, int]:
    now = datetime.now(timezone.utc)
    soon = now + timedelta(days=30)
    expiring = int(
        db.session.scalar(
            select(func.count())
            .select_from(SafetyTrainingRecord)
            .where(
                SafetyTrainingRecord.expires_at.is_not(None),
                SafetyTrainingRecord.expires_at >= now,
                SafetyTrainingRecord.expires_at <= soon,
            )
        )
        or 0
    )
    overdue = int(
        db.session.scalar(
            select(func.count())
            .select_from(SafetyTrainingRecord)
            .where(
                SafetyTrainingRecord.expires_at.is_not(None),
                SafetyTrainingRecord.expires_at < now,
            )
        )
        or 0
    )
    return {"expiring_certs_30d": expiring, "training_overdue": overdue}


def safety_summary(cu: CurrentUser) -> dict[str, Any]:
    from ..permissions.project_scope import assigned_project_ids

    today = date.today()
    week_start = today - timedelta(days=6)
    allowed = assigned_project_ids(cu)

    def _count(*, work_date: date | None = None, date_from: date | None = None, status: str | None = None) -> int:
        q = select(func.count()).select_from(DailyPretask)
        if allowed is not None:
            if not allowed:
                return 0
            q = q.where(DailyPretask.project_id.in_(allowed))
        if work_date is not None:
            q = q.where(DailyPretask.work_date == work_date)
        if date_from is not None:
            q = q.where(DailyPretask.work_date >= date_from)
        if status:
            q = q.where(DailyPretask.status == status)
        return int(db.session.scalar(q) or 0)

    certs = safety_cert_counts()
    recent = list_pretasks(cu, limit=8)
    return {
        "entity": "safety_summary",
        "counts": {
            "pretasks_today": _count(work_date=today),
            "pretasks_submitted_today": _count(work_date=today, status="submitted"),
            "pretasks_this_week": _count(date_from=week_start),
            "expiring_certs_30d": certs["expiring_certs_30d"],
            "training_overdue": certs["training_overdue"],
            "open_incidents": 0,
            "observations_this_week": 0,
        },
        "recent_pretasks": recent["items"],
        "links": {
            "daily_pretask": "/usis-daily-pretask.html",
            "hr_dashboard": "/usis-hr-dashboard.html",
        },
    }
