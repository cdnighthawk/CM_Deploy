"""Web-only timekeeping: live board, cards, flags, periods, geofence, settings."""
from __future__ import annotations

import csv
import io
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Mapping

from flask import Response, request
from sqlalchemy import func, or_, select
from sqlalchemy.orm import selectinload

from ..extensions import db
from ..models import (
    AuditLog,
    Document,
    EmployeeTimeProfile,
    Estimate,
    EstimateLineItem,
    Project,
    ProjectGeofence,
    ProjectTimeCostCode,
    TimeBreadcrumb,
    TimeCostCode,
    TimeEntry,
    TimeFlag,
    TimePunch,
    TimecardDay,
    TimecardPeriod,
    TimecardPeriodEmployee,
    User,
)
from ..permissions.project_scope import user_can_access_project
from ..services.object_storage import UploadCategory, save_upload
from ._field_service import _num_or_none, _parse_dt, _parse_uuid
from ._in_app_notifications import create_in_app_notification
from ._perms import CurrentUser
from ._serializers import iso
from ._time_clock_math import paid_seconds
from ._time_ot import compute_week
from ._time_policy import FINISH_TRADE_COST_CODES, load_time_policy, merge_policy, save_time_policy
from ._time_service import (
    TimeApiError,
    _after_punch,
    _can_act_for,
    _client_id,
    _envelope,
    _local_date,
    _name,
    _open_entry,
    _open_flag,
    _period_locked,
    _require_user,
    _source_of,
    _tz,
    _utcnow,
    _week_bounds,
    can_see_rates,
    ensure_current_period,
    is_payroll,
    is_supervisor,
    punch_public,
    recompute_day,
    time_entry_public,
)


def _user_map(ids: list[uuid.UUID]) -> dict[uuid.UUID, User]:
    if not ids:
        return {}
    rows = list(db.session.scalars(select(User).where(User.id.in_(ids))).all())
    return {u.id: u for u in rows}


def _project_map(ids: list[uuid.UUID]) -> dict[uuid.UUID, Project]:
    if not ids:
        return {}
    rows = list(db.session.scalars(select(Project).where(Project.id.in_(ids))).all())
    return {p.id: p for p in rows}


def _eligible_users() -> list[User]:
    profiles = list(db.session.scalars(select(EmployeeTimeProfile).where(EmployeeTimeProfile.is_clock_eligible.is_(True))).all())
    if profiles:
        ids = [p.user_id for p in profiles]
        return list(db.session.scalars(select(User).where(User.id.in_(ids), User.is_active.is_(True))).all())
    return list(db.session.scalars(select(User).where(User.is_active.is_(True)).limit(500)).all())


def live_board(cu: CurrentUser, project_id: uuid.UUID | None = None) -> dict[str, Any]:
    policy = load_time_policy()
    _require_user(cu)
    now = _utcnow()
    today = _local_date(now, policy)
    stmt = select(TimeEntry).options(selectinload(TimeEntry.punches)).where(TimeEntry.voided.is_(False), TimeEntry.status != "closed")
    if project_id is not None:
        stmt = stmt.where(TimeEntry.project_id == project_id)
    open_rows = list(db.session.scalars(stmt).all())
    if not is_payroll(cu) and not cu.is_dev_admin:
        open_rows = [r for r in open_rows if _can_act_for(cu, r.user_id, r.project_id)]
    users = _user_map([r.user_id for r in open_rows])
    projects = _project_map([r.project_id for r in open_rows])
    codes = {}
    cc_ids = [r.time_cost_code_id for r in open_rows if r.time_cost_code_id]
    if cc_ids:
        for c in db.session.scalars(select(TimeCostCode).where(TimeCostCode.id.in_(cc_ids))).all():
            codes[c.id] = f"{c.code} {c.name}".strip()

    n_hours = float(policy.get("open_punch_flag_after_hours") or 12)
    clocked, on_break, open_old = 0, 0, 0
    roster = []
    for row in open_rows:
        if row.status == "on_break":
            on_break += 1
            status = "break"
        else:
            clocked += 1
            status = "in"
        elapsed = paid_seconds(row.started_at, row.ended_at, [{"kind": p.kind, "occurred_at": p.occurred_at} for p in (row.punches or [])], now)
        if elapsed >= n_hours * 3600:
            open_old += 1
            _open_flag(user_id=row.user_id, flag_type="open_punch", entry=row, detail=f"Open more than {n_hours:g} hours")
        last_gps = None
        punches = sorted(row.punches or [], key=lambda p: p.occurred_at)
        for p in reversed(punches):
            if p.lat is not None:
                last_gps = {"lat": float(p.lat), "lon": float(p.lon), "at": iso(p.occurred_at), "acc": float(p.accuracy_m) if p.accuracy_m is not None else None}
                break
        day_start = None
        day_rows = list(
            db.session.scalars(
                select(TimeEntry)
                .where(
                    TimeEntry.user_id == row.user_id,
                    TimeEntry.voided.is_(False),
                    TimeEntry.started_at >= datetime(today.year, today.month, today.day, tzinfo=_tz(policy)).astimezone(timezone.utc),
                )
                .order_by(TimeEntry.started_at)
            ).all()
        )
        if day_rows:
            day_start = iso(day_rows[0].started_at)
        u = users.get(row.user_id)
        proj = projects.get(row.project_id)
        roster.append(
            {
                "entry": time_entry_public(row, now=now, policy=policy),
                "employee": _name(u),
                "user_id": str(row.user_id),
                "status": status,
                "project": f"{getattr(proj, 'number', '') or ''} {getattr(proj, 'name', '') or ''}".strip(),
                "cost_code": codes.get(row.time_cost_code_id) if row.time_cost_code_id else "",
                "since": iso(row.started_at),
                "elapsed_seconds": int(elapsed),
                "day_start": day_start,
                "gps": last_gps,
                "flag": row.offsite or (row.gps_status == "denied"),
            }
        )

    since7 = today - timedelta(days=7)
    flag_stmt = select(TimeFlag).where(TimeFlag.status == "open", or_(TimeFlag.work_date >= since7, TimeFlag.created_at >= now - timedelta(days=7)))
    flags = list(db.session.scalars(flag_stmt).all())
    def _count(*types: str) -> int:
        return sum(1 for f in flags if f.flag_type in types)

    unsigned = db.session.scalar(
        select(func.count()).select_from(TimecardDay).where(
            TimecardDay.work_date >= since7,
            TimecardDay.signed_at.is_(None),
            (TimecardDay.regular_hours + TimecardDay.ot_hours + TimecardDay.dt_hours) > 0,
        )
    ) or 0
    period = ensure_current_period(policy)
    period_days = list(
        db.session.scalars(
            select(TimecardDay).where(TimecardDay.work_date >= period.period_start, TimecardDay.work_date <= period.period_end)
        ).all()
    )
    hours_period = float(sum((d.regular_hours or 0) + (d.ot_hours or 0) + (d.dt_hours or 0) for d in period_days))
    ot_period = float(sum((d.ot_hours or 0) + (d.dt_hours or 0) for d in period_days))
    labor_cost = None
    if can_see_rates(cu):
        labor_cost = None
    return {
        "kpis": {
            "clocked_in": clocked,
            "on_break": on_break,
            "open_old": open_old,
            "flags_today": _count("offsite", "gps_denied"),
            "unsigned_7d": int(unsigned),
            "inaccurate_7d": _count("missing_signoff", "edited_after_sign", "overlap", "clock_skew", "cost_code_missing"),
            "meal_7d": _count("missing_meal", "missing_rest"),
            "injuries_7d": _count("injury_reported"),
            "hours_period": round(hours_period, 2),
            "ot_period": round(ot_period, 2),
            "labor_cost_period": labor_cost,
        },
        "roster": roster,
        "period": {"id": str(period.id), "start": period.period_start.isoformat(), "end": period.period_end.isoformat()},
        "updated_at": iso(now),
        "open_punch_flag_after_hours": n_hours,
        "entity": "time_live",
    }


def list_entries(cu: CurrentUser, args: Mapping[str, Any]) -> dict[str, Any]:
    policy = load_time_policy()
    actor = _require_user(cu)
    stmt = select(TimeEntry).options(selectinload(TimeEntry.punches)).where(TimeEntry.voided.is_(False))
    uid = _parse_uuid(args.get("user_id"))
    pid = _parse_uuid(args.get("project_id"))
    if uid:
        stmt = stmt.where(TimeEntry.user_id == uid)
    elif not is_supervisor(cu) and not is_payroll(cu):
        stmt = stmt.where(TimeEntry.user_id == actor)
    if pid:
        stmt = stmt.where(TimeEntry.project_id == pid)
    d0 = args.get("from") or args.get("start")
    d1 = args.get("to") or args.get("end")
    if d0:
        try:
            start = date.fromisoformat(str(d0)[:10])
            stmt = stmt.where(TimeEntry.started_at >= datetime(start.year, start.month, start.day, tzinfo=_tz(policy)).astimezone(timezone.utc))
        except ValueError:
            pass
    if d1:
        try:
            end = date.fromisoformat(str(d1)[:10]) + timedelta(days=1)
            stmt = stmt.where(TimeEntry.started_at < datetime(end.year, end.month, end.day, tzinfo=_tz(policy)).astimezone(timezone.utc))
        except ValueError:
            pass
    rows = list(db.session.scalars(stmt.order_by(TimeEntry.started_at.desc()).limit(500)).all())
    rows = [r for r in rows if _can_act_for(cu, r.user_id, r.project_id)]
    return {"items": [time_entry_public(r, policy=policy) for r in rows], "entity": "time_entries"}


def get_entry(entry_id: uuid.UUID, cu: CurrentUser) -> dict[str, Any]:
    row = db.session.get(TimeEntry, entry_id)
    if row is None:
        raise TimeApiError("time entry not found", 404)
    if not _can_act_for(cu, row.user_id, row.project_id):
        raise TimeApiError("time entry not found", 404)
    return _envelope(row)


def _audit_edit(cu: CurrentUser, entry: TimeEntry, before: dict[str, Any], after: dict[str, Any], reason: str) -> None:
    db.session.add(
        AuditLog(
            user_id=cu.id,
            entity_type="time_entry",
            entity_id=entry.id,
            action="edit",
            message=reason,
            changes={"before": before, "after": after, "reason": reason},
        )
    )


def _clear_sign_if_needed(entry: TimeEntry, policy: Mapping[str, Any], cu: CurrentUser) -> None:
    work = _local_date(entry.started_at, policy)
    day = db.session.scalar(select(TimecardDay).where(TimecardDay.user_id == entry.user_id, TimecardDay.work_date == work))
    sign_event = db.session.scalar(
        select(TimePunch).where(TimePunch.user_id == entry.user_id, TimePunch.kind == "sign").limit(1)
    )
    signed = bool(day is not None and (day.signed_at is not None or day.signature_png_url)) or sign_event is not None
    if not signed:
        return
    if day is not None:
        day.signed_at = None
        day.signature_png_url = None
        day.employee_attested_accurate = False
        db.session.add(day)
    pe = db.session.scalar(
        select(TimecardPeriodEmployee).where(TimecardPeriodEmployee.user_id == entry.user_id, TimecardPeriodEmployee.signed_at.is_not(None))
    )
    if pe is not None:
        pe.signed_at = None
        pe.signature_png_url = None
        db.session.add(pe)
    _open_flag(
        user_id=entry.user_id,
        flag_type="edited_after_sign",
        entry=entry,
        work_date=work,
        detail="Office edited after employee signed",
    )
    _add_office_event(entry, "unsign", cu, reason="edited after sign")


def _add_office_event(entry: TimeEntry, kind: str, cu: CurrentUser, reason: str | None, extra: dict[str, Any] | None = None) -> None:
    db.session.add(
        TimePunch(
            entry_id=entry.id,
            user_id=entry.user_id,
            project_id=entry.project_id,
            kind=kind,
            occurred_at=_utcnow(),
            client_id=uuid.uuid4(),
            source="office_edit",
            performed_by_id=cu.id,
            reason=reason,
            payload_json=extra,
        )
    )


def patch_entry(entry_id: uuid.UUID, data: Mapping[str, Any], cu: CurrentUser) -> dict[str, Any]:
    policy = load_time_policy()
    row = db.session.get(TimeEntry, entry_id)
    if row is None:
        raise TimeApiError("time entry not found", 404)
    if not _can_act_for(cu, row.user_id, row.project_id):
        raise TimeApiError("not allowed", 403)
    if not is_supervisor(cu) and cu.id != row.user_id:
        raise TimeApiError("not allowed", 403)
    reason = str(data.get("reason") or "").strip()
    if not reason:
        raise TimeApiError("reason is required", 400)
    if _period_locked(row, policy) and not is_payroll(cu):
        raise TimeApiError("period is locked", 409)
    before = time_entry_public(row, policy=policy)
    if "project_id" in data:
        pid = _parse_uuid(data.get("project_id"))
        if pid:
            row.project_id = pid
    if "cost_code_id" in data or "time_cost_code_id" in data:
        raw = _parse_uuid(data.get("time_cost_code_id") or data.get("cost_code_id"))
        row.time_cost_code_id = raw
    if "start_at" in data or "started_at" in data:
        dt = _parse_dt(data.get("start_at") or data.get("started_at"))
        if dt:
            row.started_at = dt
    if "end_at" in data or "ended_at" in data:
        dt = _parse_dt(data.get("end_at") or data.get("ended_at"))
        row.ended_at = dt
        if dt:
            row.status = "closed"
    if "note" in data:
        row.note = str(data.get("note") or "").strip() or None
    row.source = "office_edit"
    db.session.add(row)
    _add_office_event(row, "edit", cu, reason, extra={"before": before})
    _clear_sign_if_needed(row, policy, cu)
    _after_punch(row, policy)
    _audit_edit(cu, row, before, time_entry_public(row, policy=policy), reason)
    db.session.commit()
    return _envelope(row, policy)


def add_entry(data: Mapping[str, Any], cu: CurrentUser) -> dict[str, Any]:
    policy = load_time_policy()
    actor = _require_user(cu)
    if not is_supervisor(cu) and not is_payroll(cu):
        raise TimeApiError("not allowed", 403)
    reason = str(data.get("reason") or "").strip()
    if not reason:
        raise TimeApiError("reason is required", 400)
    user_id = _parse_uuid(data.get("user_id")) or actor
    project_id = _parse_uuid(data.get("project_id"))
    if project_id is None:
        raise TimeApiError("project_id is required", 400)
    start = _parse_dt(data.get("start_at") or data.get("started_at"))
    end = _parse_dt(data.get("end_at") or data.get("ended_at"))
    if start is None:
        raise TimeApiError("start_at is required", 400)
    cid = _parse_uuid(data.get("local_id") or data.get("client_id")) or uuid.uuid4()
    existing = db.session.scalar(select(TimeEntry).where(TimeEntry.client_id == cid))
    if existing is not None:
        return _envelope(existing, policy)
    entry = TimeEntry(
        user_id=user_id,
        project_id=project_id,
        time_cost_code_id=_parse_uuid(data.get("time_cost_code_id") or data.get("cost_code_id")),
        started_at=start,
        ended_at=end,
        status="closed" if end else "open",
        note=str(data.get("note") or "").strip() or None,
        client_id=cid,
        entry_type=str(data.get("entry_type") or "work"),
        source="office_edit",
        punched_by_id=actor,
    )
    if entry.status == "open" and _open_entry(user_id) is not None:
        raise TimeApiError("already clocked in", 409)
    db.session.add(entry)
    db.session.flush()
    _add_office_event(entry, "manual_add", cu, reason)
    _clear_sign_if_needed(entry, policy, cu)
    _after_punch(entry, policy)
    db.session.commit()
    return _envelope(entry, policy)


def split_entry(entry_id: uuid.UUID, data: Mapping[str, Any], cu: CurrentUser) -> dict[str, Any]:
    policy = load_time_policy()
    row = db.session.get(TimeEntry, entry_id)
    if row is None:
        raise TimeApiError("time entry not found", 404)
    if not is_supervisor(cu) and not is_payroll(cu):
        raise TimeApiError("not allowed", 403)
    reason = str(data.get("reason") or "").strip() or "split"
    at = _parse_dt(data.get("at"))
    if at is None:
        raise TimeApiError("at is required", 400)
    if at <= row.started_at or (row.ended_at is not None and at >= row.ended_at):
        raise TimeApiError("split time must be inside the punch", 400)
    if _period_locked(row, policy) and not is_payroll(cu):
        raise TimeApiError("period is locked", 409)
    end = row.ended_at
    status = row.status
    row.ended_at = at
    row.status = "closed"
    db.session.add(row)
    db.session.flush()
    new_start = at + timedelta(seconds=1)
    new_entry = TimeEntry(
        user_id=row.user_id,
        project_id=_parse_uuid(data.get("project_id")) or row.project_id,
        cost_code_id=row.cost_code_id,
        time_cost_code_id=_parse_uuid(data.get("cost_code_id") or data.get("time_cost_code_id")) or row.time_cost_code_id,
        started_at=new_start,
        ended_at=end,
        status=status if end is None else "closed",
        client_id=uuid.uuid4(),
        entry_type=row.entry_type or "work",
        source="office_edit",
        punched_by_id=cu.id,
        note=row.note,
    )
    db.session.add(new_entry)
    db.session.flush()
    _add_office_event(row, "split", cu, reason, extra={"new_entry_id": str(new_entry.id), "at": iso(at)})
    _clear_sign_if_needed(row, policy, cu)
    _after_punch(row, policy)
    _after_punch(new_entry, policy)
    db.session.commit()
    return {"item": time_entry_public(row, policy=policy), "next": time_entry_public(new_entry, policy=policy), "entity": "time_entry"}


def void_entry(entry_id: uuid.UUID, data: Mapping[str, Any], cu: CurrentUser) -> dict[str, Any]:
    policy = load_time_policy()
    row = db.session.get(TimeEntry, entry_id)
    if row is None:
        raise TimeApiError("time entry not found", 404)
    if not is_supervisor(cu) and not is_payroll(cu):
        raise TimeApiError("not allowed", 403)
    reason = str(data.get("reason") or "").strip()
    if not reason:
        raise TimeApiError("reason is required", 400)
    if _period_locked(row, policy) and not is_payroll(cu):
        raise TimeApiError("period is locked", 409)
    row.voided = True
    row.void_reason = reason
    row.status = "closed"
    if row.ended_at is None:
        row.ended_at = _utcnow()
    db.session.add(row)
    _add_office_event(row, "delete_void", cu, reason)
    _clear_sign_if_needed(row, policy, cu)
    _after_punch(row, policy)
    db.session.commit()
    return {"ok": True, "id": str(row.id), "entity": "time_entry"}


def ingest_breadcrumbs(data: Mapping[str, Any], cu: CurrentUser) -> dict[str, Any]:
    policy = load_time_policy()
    user_id = _require_user(cu)
    if policy.get("track_off_clock"):
        pass
    open_row = _open_entry(user_id)
    if open_row is None:
        return {"accepted": 0, "entity": "time_breadcrumbs"}
    items = data.get("items") if isinstance(data.get("items"), list) else [data]
    min_iv = int(policy.get("breadcrumb_min_interval_sec") or 180)
    last = db.session.scalar(
        select(TimeBreadcrumb).where(TimeBreadcrumb.user_id == user_id).order_by(TimeBreadcrumb.at.desc())
    )
    accepted = 0
    for raw in items:
        if not isinstance(raw, Mapping):
            continue
        lat = _num_or_none(raw.get("lat"))
        lon = _num_or_none(raw.get("lon"))
        at = _parse_dt(raw.get("at")) or _utcnow()
        if lat is None or lon is None:
            continue
        if last is not None and (at - last.at).total_seconds() < min_iv:
            continue
        row = TimeBreadcrumb(
            user_id=user_id,
            project_id=open_row.project_id,
            time_entry_id=open_row.id,
            at=at,
            lat=lat,
            lon=lon,
            acc=_num_or_none(raw.get("acc") if raw.get("acc") is not None else raw.get("accuracy_m")),
        )
        db.session.add(row)
        last = row
        accepted += 1
    db.session.commit()
    return {"accepted": accepted, "entity": "time_breadcrumbs"}


def list_events(cu: CurrentUser, args: Mapping[str, Any]) -> dict[str, Any]:
    _require_user(cu)
    stmt = select(TimePunch)
    uid = _parse_uuid(args.get("user_id"))
    if uid:
        stmt = stmt.where(TimePunch.user_id == uid)
    elif not is_supervisor(cu) and not is_payroll(cu):
        stmt = stmt.where(TimePunch.user_id == cu.id)
    action = str(args.get("action") or args.get("kind") or "").strip()
    if action:
        stmt = stmt.where(TimePunch.kind == action)
    pid = _parse_uuid(args.get("project_id"))
    if pid:
        stmt = stmt.where(TimePunch.project_id == pid)
    src = str(args.get("source") or "").strip()
    if src:
        stmt = stmt.where(TimePunch.source == src)
    rows = list(db.session.scalars(stmt.order_by(TimePunch.occurred_at.desc()).limit(500)).all())
    users = _user_map([p.user_id for p in rows if p.user_id] + [p.performed_by_id for p in rows if p.performed_by_id])
    projects = _project_map([p.project_id for p in rows if p.project_id])
    items = []
    for p in rows:
        proj = projects.get(p.project_id) if p.project_id else None
        items.append(
            {
                **punch_public(p),
                "employee": _name(users.get(p.user_id)) if p.user_id else "",
                "performed_by": _name(users.get(p.performed_by_id)) if p.performed_by_id else "",
                "project": f"{getattr(proj, 'number', '') or ''} {getattr(proj, 'name', '') or ''}".strip() if proj else "",
            }
        )
    return {"items": items, "entity": "time_events"}


def list_flags(cu: CurrentUser, args: Mapping[str, Any]) -> dict[str, Any]:
    _require_user(cu)
    stmt = select(TimeFlag)
    status = str(args.get("status") or "open").strip()
    if status and status != "all":
        stmt = stmt.where(TimeFlag.status == status)
    ftype = str(args.get("type") or args.get("flag_type") or "").strip()
    if ftype:
        types = [t.strip() for t in ftype.split(",") if t.strip()]
        stmt = stmt.where(TimeFlag.flag_type.in_(types))
    uid = _parse_uuid(args.get("user_id"))
    if uid:
        stmt = stmt.where(TimeFlag.user_id == uid)
    rows = list(db.session.scalars(stmt.order_by(TimeFlag.created_at.desc()).limit(400)).all())
    users = _user_map([f.user_id for f in rows])
    projects = _project_map([f.project_id for f in rows if f.project_id])
    items = []
    for f in rows:
        proj = projects.get(f.project_id) if f.project_id else None
        items.append(
            {
                "id": str(f.id),
                "when": iso(f.created_at),
                "user_id": str(f.user_id),
                "employee": _name(users.get(f.user_id)),
                "project_id": str(f.project_id) if f.project_id else None,
                "project": f"{getattr(proj, 'number', '') or ''} {getattr(proj, 'name', '') or ''}".strip() if proj else "",
                "type": f.flag_type,
                "detail": f.detail,
                "status": f.status,
                "assignee": str(f.assigned_to) if f.assigned_to else None,
                "time_entry_id": str(f.time_entry_id) if f.time_entry_id else None,
                "work_date": f.work_date.isoformat() if f.work_date else None,
            }
        )
    return {"items": items, "entity": "time_flags"}


def resolve_flag(flag_id: uuid.UUID, action: str, data: Mapping[str, Any], cu: CurrentUser) -> dict[str, Any]:
    if not is_supervisor(cu) and not is_payroll(cu):
        raise TimeApiError("not allowed", 403)
    row = db.session.get(TimeFlag, flag_id)
    if row is None:
        raise TimeApiError("flag not found", 404)
    reason = str(data.get("reason") or "").strip()
    if action in ("accept", "dismiss") and not reason:
        raise TimeApiError("reason is required", 400)
    if action == "accept":
        row.status = "accepted"
    elif action == "dismiss":
        row.status = "dismissed"
    else:
        raise TimeApiError("unknown action", 400)
    row.reason = reason
    row.resolved_by = cu.id
    row.resolved_at = _utcnow()
    db.session.add(row)
    db.session.commit()
    return {"item": {"id": str(row.id), "status": row.status}, "entity": "time_flag"}


def cards_summary(cu: CurrentUser, args: Mapping[str, Any]) -> dict[str, Any]:
    policy = load_time_policy()
    _require_user(cu)
    period_id = _parse_uuid(args.get("period_id"))
    period = db.session.get(TimecardPeriod, period_id) if period_id else ensure_current_period(policy)
    if period is None:
        raise TimeApiError("period not found", 404)
    days = list(
        db.session.scalars(
            select(TimecardDay).where(TimecardDay.work_date >= period.period_start, TimecardDay.work_date <= period.period_end)
        ).all()
    )
    by_user: dict[uuid.UUID, list[TimecardDay]] = {}
    for d in days:
        by_user.setdefault(d.user_id, []).append(d)
    users = _user_map(list(by_user))
    flags = list(
        db.session.scalars(
            select(TimeFlag).where(TimeFlag.status == "open", TimeFlag.work_date >= period.period_start, TimeFlag.work_date <= period.period_end)
        ).all()
    )
    flag_by_user: dict[uuid.UUID, list[str]] = {}
    for f in flags:
        flag_by_user.setdefault(f.user_id, []).append(f.flag_type)
    pes = {pe.user_id: pe for pe in db.session.scalars(select(TimecardPeriodEmployee).where(TimecardPeriodEmployee.period_id == period.id)).all()}
    items = []
    for uid, udays in by_user.items():
        week = compute_week(
            [
                {
                    "regular_hours": float(d.regular_hours or 0),
                    "ot_hours": float(d.ot_hours or 0),
                    "dt_hours": float(d.dt_hours or 0),
                    "premium_hours": float(d.premium_hours or 0),
                    "work_hours": float((d.regular_hours or 0) + (d.ot_hours or 0) + (d.dt_hours or 0)),
                }
                for d in sorted(udays, key=lambda x: x.work_date)
            ],
            period.policy_json or policy,
        )
        pe = pes.get(uid)
        items.append(
            {
                "user_id": str(uid),
                "employee": _name(users.get(uid)),
                "emp_signed": bool(pe.signed_at) if pe else any(d.signed_at for d in udays),
                "super_approved": bool(pe.approved_at) if pe else False,
                "flags": sorted(set(flag_by_user.get(uid, []))),
                "regular": week["regular_hours"],
                "ot": week["ot_hours"],
                "dt": week["dt_hours"],
                "premium": week["premium_hours"],
                "total": week["work_hours"],
                "days": [
                    {
                        "date": d.work_date.isoformat(),
                        "regular": float(d.regular_hours or 0),
                        "ot": float(d.ot_hours or 0),
                        "dt": float(d.dt_hours or 0),
                        "signed": bool(d.signed_at),
                        "injury": bool(d.injury_reported),
                    }
                    for d in sorted(udays, key=lambda x: x.work_date)
                ],
            }
        )
    items.sort(key=lambda x: x["employee"] or "")
    return {
        "period": {
            "id": str(period.id),
            "start": period.period_start.isoformat(),
            "end": period.period_end.isoformat(),
            "status": period.status,
        },
        "items": items,
        "entity": "timecard_cards",
    }


def sign_day(work_date: date, data: Mapping[str, Any], cu: CurrentUser, *, commit: bool = True) -> dict[str, Any]:
    policy = load_time_policy()
    user_id = _parse_uuid(data.get("user_id")) or _require_user(cu)
    if user_id != cu.id and not is_supervisor(cu) and not is_payroll(cu):
        raise TimeApiError("not allowed", 403)
    day = recompute_day(user_id, work_date, policy)
    day.signed_at = _utcnow()
    day.signed_ip = request.remote_addr if request else None
    day.signature_png_url = str(data.get("signature_png") or data.get("signature_png_url") or "").strip() or day.signature_png_url
    day.employee_attested_accurate = bool(data.get("attested") if "attested" in data else True)
    day.injury_reported = bool(data.get("injury") or data.get("injury_reported"))
    day.injury_note = str(data.get("note") or data.get("injury_note") or "").strip() or None
    db.session.add(day)
    if day.injury_reported:
        _open_flag(user_id=user_id, flag_type="injury_reported", work_date=work_date, detail=day.injury_note or "Injury reported on sign-off")
    open_edit = list(
        db.session.scalars(
            select(TimeFlag).where(
                TimeFlag.user_id == user_id,
                TimeFlag.flag_type == "edited_after_sign",
                TimeFlag.status == "open",
                TimeFlag.work_date == work_date,
            )
        ).all()
    )
    for f in open_edit:
        f.status = "corrected"
        f.resolved_at = _utcnow()
        f.resolved_by = cu.id
    db.session.add(
        TimePunch(
            user_id=user_id,
            kind="sign",
            occurred_at=_utcnow(),
            client_id=uuid.uuid4(),
            source="web",
            performed_by_id=cu.id,
        )
    )
    if commit:
        db.session.commit()
    return {"item": {"work_date": work_date.isoformat(), "signed_at": iso(day.signed_at)}, "entity": "timecard_day"}


def sign_period(period_id: uuid.UUID, data: Mapping[str, Any], cu: CurrentUser) -> dict[str, Any]:
    period = db.session.get(TimecardPeriod, period_id)
    if period is None:
        raise TimeApiError("period not found", 404)
    user_id = _parse_uuid(data.get("user_id")) or _require_user(cu)
    if user_id != cu.id and not is_supervisor(cu):
        raise TimeApiError("not allowed", 403)
    pe = db.session.scalar(select(TimecardPeriodEmployee).where(TimecardPeriodEmployee.period_id == period.id, TimecardPeriodEmployee.user_id == user_id))
    if pe is None:
        pe = TimecardPeriodEmployee(period_id=period.id, user_id=user_id)
        db.session.add(pe)
    pe.signed_at = _utcnow()
    pe.signature_png_url = str(data.get("signature_png") or "").strip() or None
    pe.workflow_status = "employee_sign"
    d = period.period_start
    while d <= period.period_end:
        sign_day(d, {"user_id": str(user_id), "attested": True, "signature_png": data.get("signature_png")}, cu, commit=False)
        d += timedelta(days=1)
        db.session.flush()
    db.session.commit()
    create_in_app_notification(user_id=user_id, title="Timecard signed", body=f"Period {period.period_start}–{period.period_end} signed.", url="/time/me")
    return {"ok": True, "entity": "timecard_period_employee"}


def approve_period(period_id: uuid.UUID, data: Mapping[str, Any], cu: CurrentUser) -> dict[str, Any]:
    if not is_supervisor(cu) and not is_payroll(cu):
        raise TimeApiError("not allowed", 403)
    period = db.session.get(TimecardPeriod, period_id)
    if period is None:
        raise TimeApiError("period not found", 404)
    user_id = _parse_uuid(data.get("user_id"))
    if user_id is None:
        raise TimeApiError("user_id is required", 400)
    pe = db.session.scalar(select(TimecardPeriodEmployee).where(TimecardPeriodEmployee.period_id == period.id, TimecardPeriodEmployee.user_id == user_id))
    if pe is None:
        pe = TimecardPeriodEmployee(period_id=period.id, user_id=user_id)
        db.session.add(pe)
    pe.approved_at = _utcnow()
    pe.approved_by = cu.id
    pe.workflow_status = "supervisor_approve"
    db.session.add(
        TimePunch(
            user_id=user_id,
            kind="approve",
            occurred_at=_utcnow(),
            client_id=uuid.uuid4(),
            source="web",
            performed_by_id=cu.id,
            reason=str(data.get("comment") or data.get("reason") or "").strip() or None,
        )
    )
    db.session.commit()
    create_in_app_notification(user_id=user_id, title="Timecard approved", body="Your supervisor approved this period.", url="/time/me")
    return {"ok": True, "entity": "timecard_period_employee"}


def list_periods(cu: CurrentUser) -> dict[str, Any]:
    _require_user(cu)
    ensure_current_period()
    rows = list(db.session.scalars(select(TimecardPeriod).order_by(TimecardPeriod.period_start.desc()).limit(26)).all())
    return {
        "items": [
            {
                "id": str(p.id),
                "start": p.period_start.isoformat(),
                "end": p.period_end.isoformat(),
                "status": p.status,
                "exported_at": iso(p.exported_at),
            }
            for p in rows
        ],
        "entity": "timecard_periods",
    }


def _scan_period(period: TimecardPeriod, policy: Mapping[str, Any]) -> dict[str, Any]:
    now = _utcnow().astimezone(_tz(policy)).date()
    open_entries = db.session.scalar(
        select(func.count()).select_from(TimeEntry).where(
            TimeEntry.voided.is_(False),
            TimeEntry.status != "closed",
            TimeEntry.started_at >= datetime(period.period_start.year, period.period_start.month, period.period_start.day, tzinfo=_tz(policy)).astimezone(timezone.utc),
            TimeEntry.started_at < datetime(period.period_end.year, period.period_end.month, period.period_end.day, tzinfo=_tz(policy)).astimezone(timezone.utc) + timedelta(days=1),
        )
    ) or 0
    flags = list(
        db.session.scalars(
            select(TimeFlag).where(
                TimeFlag.status == "open",
                or_(
                    TimeFlag.work_date.between(period.period_start, period.period_end),
                    TimeFlag.work_date.is_(None),
                ),
            )
        ).all()
    )
    meal = [f for f in flags if f.flag_type in ("missing_meal", "missing_rest")]
    conflicts = [f for f in flags if f.flag_type in ("overlap", "clock_skew", "edited_after_sign")]
    days = list(
        db.session.scalars(
            select(TimecardDay).where(TimecardDay.work_date >= period.period_start, TimecardDay.work_date <= period.period_end)
        ).all()
    )
    with_hours = [d for d in days if ((d.regular_hours or 0) + (d.ot_hours or 0) + (d.dt_hours or 0)) > 0]
    unsigned = [d for d in with_hours if d.signed_at is None]
    pes = list(db.session.scalars(select(TimecardPeriodEmployee).where(TimecardPeriodEmployee.period_id == period.id)).all())
    unapproved = [pe for pe in pes if pe.approved_at is None]
    checks = [
        {"key": "period_complete", "label": "Period complete", "ok": period.period_end < now},
        {"key": "employees_signed", "label": "All employees signed", "ok": len(unsigned) == 0, "remaining": len(unsigned)},
        {"key": "supervisors_approved", "label": "All supervisors approved", "ok": len(unapproved) == 0, "remaining": len(unapproved)},
        {"key": "no_conflicts", "label": "No time entry conflicts", "ok": len(conflicts) == 0, "remaining": len(conflicts)},
        {"key": "entries_closed", "label": "All entries closed", "ok": int(open_entries) == 0, "remaining": int(open_entries)},
        {"key": "breaks_compliant", "label": "Breaks compliant", "ok": len(meal) == 0, "remaining": len(meal)},
        {"key": "flags_clear", "label": "Flags clear", "ok": len(flags) == 0, "remaining": len(flags)},
        {"key": "cards_locked", "label": "Time cards locked", "ok": period.status in ("locked", "exported")},
    ]
    return {"checks": checks, "pass": all(c["ok"] for c in checks if c["key"] != "cards_locked")}


def period_detail(period_id: uuid.UUID, cu: CurrentUser) -> dict[str, Any]:
    policy = load_time_policy()
    period = db.session.get(TimecardPeriod, period_id)
    if period is None:
        raise TimeApiError("period not found", 404)
    summary = cards_summary(cu, {"period_id": str(period.id)})
    scan = _scan_period(period, period.policy_json or policy)
    profiles = {p.user_id: p for p in db.session.scalars(select(EmployeeTimeProfile)).all()}
    for item in summary["items"]:
        uid = uuid.UUID(item["user_id"])
        prof = profiles.get(uid)
        item["classification"] = prof.classification if prof else None
        if can_see_rates(cu) and prof is not None and prof.hourly_rate is not None:
            item["rate"] = float(prof.hourly_rate)
        else:
            item["rate"] = None
    totals = {
        "regular": sum(i["regular"] for i in summary["items"]),
        "ot": sum(i["ot"] for i in summary["items"]),
        "dt": sum(i["dt"] for i in summary["items"]),
        "total": sum(i["total"] for i in summary["items"]),
    }
    return {"period": summary["period"], "scan": scan, "totals": totals, "items": summary["items"], "entity": "timecard_period"}


def lock_period(period_id: uuid.UUID, cu: CurrentUser, *, unlock: bool = False) -> dict[str, Any]:
    if not is_payroll(cu):
        raise TimeApiError("payroll admin only", 403)
    period = db.session.get(TimecardPeriod, period_id)
    if period is None:
        raise TimeApiError("period not found", 404)
    if unlock:
        period.status = "open"
        period.locked_at = None
        period.locked_by = None
        start = datetime(period.period_start.year, period.period_start.month, period.period_start.day, tzinfo=timezone.utc)
        end = datetime(period.period_end.year, period.period_end.month, period.period_end.day, tzinfo=timezone.utc) + timedelta(days=1)
        for r in db.session.scalars(select(TimeEntry).where(TimeEntry.started_at >= start, TimeEntry.started_at < end)).all():
            r.locked = False
            db.session.add(r)
    else:
        period.status = "locked"
        period.locked_at = _utcnow()
        period.locked_by = cu.id
        start = datetime(period.period_start.year, period.period_start.month, period.period_start.day, tzinfo=timezone.utc)
        end = datetime(period.period_end.year, period.period_end.month, period.period_end.day, tzinfo=timezone.utc) + timedelta(days=1)
        for r in db.session.scalars(select(TimeEntry).where(TimeEntry.started_at >= start, TimeEntry.started_at < end)).all():
            r.locked = True
            db.session.add(r)
        db.session.add(
            TimePunch(kind="lock", occurred_at=_utcnow(), client_id=uuid.uuid4(), source="office_edit", performed_by_id=cu.id, user_id=cu.id)
        )
    db.session.add(period)
    db.session.commit()
    return {"item": {"id": str(period.id), "status": period.status}, "entity": "timecard_period"}


def export_period(period_id: uuid.UUID, cu: CurrentUser) -> dict[str, Any]:
    if not is_payroll(cu):
        raise TimeApiError("payroll admin only", 403)
    policy = load_time_policy()
    period = db.session.get(TimecardPeriod, period_id)
    if period is None:
        raise TimeApiError("period not found", 404)
    frozen = period.policy_json or policy
    scan = _scan_period(period, frozen)
    if frozen.get("block_export_with_open_flags"):
        open_flags = [c for c in scan["checks"] if c["key"] in ("flags_clear", "breaks_compliant", "no_conflicts") and not c["ok"]]
        if open_flags:
            raise TimeApiError("export blocked: open flags remain", 409)
        if frozen.get("require_daily_signoff"):
            signed = next(c for c in scan["checks"] if c["key"] == "employees_signed")
            if not signed["ok"]:
                raise TimeApiError("export blocked: unsigned days remain", 409)
        if frozen.get("require_supervisor_approve_before_export"):
            appr = next(c for c in scan["checks"] if c["key"] == "supervisors_approved")
            if not appr["ok"]:
                raise TimeApiError("export blocked: supervisor approvals remain", 409)
    rows = list(
        db.session.scalars(
            select(TimeEntry)
            .options(selectinload(TimeEntry.punches))
            .where(
                TimeEntry.voided.is_(False),
                TimeEntry.started_at >= datetime(period.period_start.year, period.period_start.month, period.period_start.day, tzinfo=timezone.utc),
                TimeEntry.started_at < datetime(period.period_end.year, period.period_end.month, period.period_end.day, tzinfo=timezone.utc) + timedelta(days=1),
            )
            .order_by(TimeEntry.user_id, TimeEntry.started_at)
        ).all()
    )
    users = _user_map([r.user_id for r in rows])
    projects = _project_map([r.project_id for r in rows])
    profiles = {p.user_id: p for p in db.session.scalars(select(EmployeeTimeProfile)).all()}
    codes = {c.id: c for c in db.session.scalars(select(TimeCostCode)).all()}
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "employee_id",
            "employee_name",
            "classification",
            "project_number",
            "project_name",
            "cost_code",
            "date",
            "time_in",
            "time_out",
            "meal_minutes",
            "regular_hours",
            "ot_hours",
            "dt_hours",
            "premium_hours",
            "signed_at",
            "approved_at",
        ]
    )
    for r in rows:
        work = _local_date(r.started_at, frozen)
        day = db.session.scalar(select(TimecardDay).where(TimecardDay.user_id == r.user_id, TimecardDay.work_date == work))
        pe = db.session.scalar(
            select(TimecardPeriodEmployee).where(TimecardPeriodEmployee.period_id == period.id, TimecardPeriodEmployee.user_id == r.user_id)
        )
        proj = projects.get(r.project_id)
        cc = codes.get(r.time_cost_code_id) if r.time_cost_code_id else None
        prof = profiles.get(r.user_id)
        writer.writerow(
            [
                str(r.user_id),
                _name(users.get(r.user_id)),
                prof.classification if prof else "",
                getattr(proj, "number", "") or "",
                getattr(proj, "name", "") or "",
                f"{cc.code} {cc.name}".strip() if cc else "",
                work.isoformat(),
                iso(r.started_at),
                iso(r.ended_at) if r.ended_at else "",
                float(day.meal_minutes) if day else 0,
                float(day.regular_hours) if day else 0,
                float(day.ot_hours) if day else 0,
                float(day.dt_hours) if day else 0,
                float(day.premium_hours) if day else 0,
                iso(day.signed_at) if day and day.signed_at else "",
                iso(pe.approved_at) if pe and pe.approved_at else "",
            ]
        )
    payload = buf.getvalue().encode("utf-8")
    doc = Document(
        document_type="report",
        title=f"Payroll export {period.period_start}–{period.period_end}",
        original_filename=f"payroll-{period.period_start}.csv",
        mime_type="text/csv",
        uploaded_by_user_id=cu.id,
        tags={"entity": "timecard_period", "period_id": str(period.id)},
    )
    db.session.add(doc)
    db.session.flush()
    obj_name = f"{doc.id}.csv"
    save_upload(UploadCategory.DOCUMENTS, obj_name, io.BytesIO(payload))
    doc.file_url = f"/api/v1/documents/{doc.id}/file"
    doc.file_size_bytes = len(payload)
    period.exported_at = _utcnow()
    period.exported_by = cu.id
    period.export_file_url = doc.file_url
    period.status = "exported"
    db.session.add(period)
    db.session.commit()
    return {
        "item": {
            "id": str(period.id),
            "status": period.status,
            "file_url": doc.file_url,
            "document_id": str(doc.id),
            "csv": buf.getvalue(),
        },
        "entity": "timecard_export",
    }


def period_pdf_html(period_id: uuid.UUID, cu: CurrentUser) -> str:
    from flask import render_template_string

    detail = period_detail(period_id, cu)
    tmpl = """<!doctype html><html><head><meta charset="utf-8"><title>Timecard {{ p.start }} – {{ p.end }}</title>
    <style>body{font-family:sans-serif;color:#1F4E5F;padding:24px}table{border-collapse:collapse;width:100%}
    th,td{border:1px solid #ddd;padding:6px;font-size:12px}th{background:#F4F6F8}</style></head><body>
    <h1>USIS CM — Timecard</h1><p>Period {{ p.start }} – {{ p.end }} ({{ p.status }})</p>
    <p>I attest that these hours are complete and accurate and that no hours were worked off this card.</p>
    <table><thead><tr><th>Employee</th><th>Class</th><th>Reg</th><th>OT</th><th>DT</th><th>Total</th><th>Signed</th><th>Approved</th></tr></thead><tbody>
    {% for i in items %}<tr><td>{{ i.employee }}</td><td>{{ i.classification or '' }}</td>
    <td>{{ '%.2f'|format(i.regular) }}</td><td>{{ '%.2f'|format(i.ot) }}</td><td>{{ '%.2f'|format(i.dt) }}</td>
    <td>{{ '%.2f'|format(i.total) }}</td><td>{{ 'Yes' if i.emp_signed else 'No' }}</td>
    <td>{{ 'Yes' if i.super_approved else 'No' }}</td></tr>{% endfor %}
    </tbody></table></body></html>"""
    return render_template_string(tmpl, p=detail["period"], items=detail["items"])


def list_time_cost_codes(cu: CurrentUser, project_id: uuid.UUID | None = None) -> dict[str, Any]:
    _require_user(cu)
    rows = list(db.session.scalars(select(TimeCostCode).where(TimeCostCode.is_active.is_(True)).order_by(TimeCostCode.sort_order, TimeCostCode.code)).all())
    enabled = None
    if project_id is not None:
        links = list(db.session.scalars(select(ProjectTimeCostCode).where(ProjectTimeCostCode.project_id == project_id, ProjectTimeCostCode.is_enabled.is_(True))).all())
        if links:
            allow = {lnk.time_cost_code_id for lnk in links}
            rows = [r for r in rows if r.id in allow]
            enabled = {str(lnk.time_cost_code_id): {"favorite": lnk.favorite, "required": lnk.required} for lnk in links}
    return {
        "items": [
            {
                "id": str(r.id),
                "code": r.code,
                "name": r.name,
                "trade": r.trade,
                "is_billable": r.is_billable,
                "sort_order": r.sort_order,
                **(enabled.get(str(r.id), {}) if enabled else {}),
            }
            for r in rows
        ],
        "entity": "time_cost_codes",
    }


def upsert_time_cost_code(data: Mapping[str, Any], cu: CurrentUser, row_id: uuid.UUID | None = None) -> dict[str, Any]:
    if not is_payroll(cu):
        raise TimeApiError("payroll admin only", 403)
    row = db.session.get(TimeCostCode, row_id) if row_id else None
    if row_id and row is None:
        raise TimeApiError("cost code not found", 404)
    if row is None:
        row = TimeCostCode(code=str(data.get("code") or "").strip(), name=str(data.get("name") or "").strip())
        db.session.add(row)
    if "code" in data:
        row.code = str(data.get("code") or "").strip()
    if "name" in data:
        row.name = str(data.get("name") or "").strip()
    if "trade" in data:
        row.trade = str(data.get("trade") or "").strip() or None
    if "is_active" in data:
        row.is_active = bool(data.get("is_active"))
    if "is_billable" in data:
        row.is_billable = bool(data.get("is_billable"))
    if "sort_order" in data:
        row.sort_order = int(data.get("sort_order") or 0)
    db.session.commit()
    return {"item": {"id": str(row.id), "code": row.code, "name": row.name}, "entity": "time_cost_code"}


def get_geofence(project_id: uuid.UUID, cu: CurrentUser) -> dict[str, Any]:
    _require_user(cu)
    project = db.session.get(Project, project_id)
    if project is None:
        raise TimeApiError("project not found", 404)
    fence = db.session.scalar(select(ProjectGeofence).where(ProjectGeofence.project_id == project_id))
    item = {
        "project_id": str(project_id),
        "mode": fence.mode if fence else load_time_policy().get("geofence_default_mode"),
        "shape": fence.shape if fence else "circle",
        "center_lat": float(fence.center_lat) if fence and fence.center_lat is not None else (float(project.latitude) if project.latitude is not None else None),
        "center_lon": float(fence.center_lon) if fence and fence.center_lon is not None else (float(project.longitude) if project.longitude is not None else None),
        "radius_m": float(fence.radius_m) if fence and fence.radius_m is not None else (float(project.geofence_radius_m) if project.geofence_radius_m is not None else 250),
        "polygon_geojson": fence.polygon_geojson if fence else None,
        "reminder_mode": fence.reminder_mode if fence else "off",
        "shift_end_hour": fence.shift_end_hour if fence else None,
        "timezone": fence.timezone if fence else None,
    }
    return {"item": item, "entity": "project_geofence"}


def put_geofence(project_id: uuid.UUID, data: Mapping[str, Any], cu: CurrentUser) -> dict[str, Any]:
    if not is_supervisor(cu) and not is_payroll(cu):
        raise TimeApiError("not allowed", 403)
    project = db.session.get(Project, project_id)
    if project is None:
        raise TimeApiError("project not found", 404)
    fence = db.session.scalar(select(ProjectGeofence).where(ProjectGeofence.project_id == project_id))
    if fence is None:
        fence = ProjectGeofence(project_id=project_id)
        db.session.add(fence)
    if "mode" in data and str(data.get("mode")) in ("flag", "block"):
        fence.mode = str(data.get("mode"))
    if "shape" in data and str(data.get("shape")) in ("circle", "polygon"):
        fence.shape = str(data.get("shape"))
    if "center_lat" in data:
        fence.center_lat = _num_or_none(data.get("center_lat"))
        project.latitude = fence.center_lat
    if "center_lon" in data:
        fence.center_lon = _num_or_none(data.get("center_lon"))
        project.longitude = fence.center_lon
    if "radius_m" in data:
        fence.radius_m = _num_or_none(data.get("radius_m"))
        if fence.radius_m is not None:
            project.geofence_radius_m = int(fence.radius_m)
    if "polygon_geojson" in data:
        fence.polygon_geojson = data.get("polygon_geojson") if isinstance(data.get("polygon_geojson"), dict) else None
    if "reminder_mode" in data:
        fence.reminder_mode = str(data.get("reminder_mode") or "off")
    if "shift_end_hour" in data:
        fence.shift_end_hour = int(data["shift_end_hour"]) if data.get("shift_end_hour") is not None else None
    db.session.add(project)
    db.session.commit()
    return get_geofence(project_id, cu)


def map_live(cu: CurrentUser, args: Mapping[str, Any]) -> dict[str, Any]:
    board = live_board(cu, _parse_uuid(args.get("project_id")))
    pins = []
    for row in board["roster"]:
        gps = row.get("gps")
        if not gps:
            continue
        pins.append(
            {
                "user_id": row["user_id"],
                "name": row["employee"],
                "lat": gps["lat"],
                "lon": gps["lon"],
                "status": row["status"],
                "project": row["project"],
                "cost_code": row.get("cost_code"),
            }
        )
    pings = []
    uid = _parse_uuid(args.get("user_id"))
    day_s = args.get("date")
    if uid and day_s:
        open_row = _open_entry(uid)
        # breadcrumbs only while they were on the clock that date — stored rows already require an open entry at write time
        try:
            day = date.fromisoformat(str(day_s)[:10])
        except ValueError:
            day = None
        if day:
            start = datetime(day.year, day.month, day.day, tzinfo=timezone.utc)
            crumbs = list(
                db.session.scalars(
                    select(TimeBreadcrumb).where(
                        TimeBreadcrumb.user_id == uid,
                        TimeBreadcrumb.at >= start,
                        TimeBreadcrumb.at < start + timedelta(days=1),
                    ).order_by(TimeBreadcrumb.at)
                ).all()
            )
            pings = [{"lat": float(c.lat), "lon": float(c.lon), "at": iso(c.at)} for c in crumbs]
    fences = []
    pid = _parse_uuid(args.get("project_id"))
    if pid:
        fences.append(get_geofence(pid, cu)["item"])
    return {"pins": pins, "pings": pings, "fences": fences, "entity": "time_map"}


def job_cost(cu: CurrentUser, project_id: uuid.UUID, d0: date | None, d1: date | None) -> dict[str, Any]:
    _require_user(cu)
    policy = load_time_policy()
    start = d0 or (_utcnow().astimezone(_tz(policy)).date() - timedelta(days=6))
    end = d1 or _utcnow().astimezone(_tz(policy)).date()
    rows = list(
        db.session.scalars(
            select(TimeEntry).options(selectinload(TimeEntry.punches)).where(
                TimeEntry.project_id == project_id,
                TimeEntry.voided.is_(False),
                TimeEntry.started_at >= datetime(start.year, start.month, start.day, tzinfo=timezone.utc),
                TimeEntry.started_at < datetime(end.year, end.month, end.day, tzinfo=timezone.utc) + timedelta(days=1),
            )
        ).all()
    )
    actual = 0.0
    by_code: dict[str, float] = {}
    for r in rows:
        hrs = paid_seconds(r.started_at, r.ended_at, [{"kind": p.kind, "occurred_at": p.occurred_at} for p in (r.punches or [])], _utcnow()) / 3600.0
        actual += hrs
        key = str(r.time_cost_code_id or "untagged")
        by_code[key] = by_code.get(key, 0.0) + hrs
    estimate_hours = None
    est = db.session.scalar(select(Estimate).where(Estimate.project_id == project_id).order_by(Estimate.updated_at.desc()))
    if est is not None:
        lines = list(db.session.scalars(select(EstimateLineItem).where(EstimateLineItem.estimate_id == est.id)).all())
        estimate_hours = float(len(lines)) if lines else None
    return {
        "project_id": str(project_id),
        "from": start.isoformat(),
        "to": end.isoformat(),
        "actual_hours": round(actual, 2),
        "estimate_hours": estimate_hours,
        "by_cost_code": by_code,
        "entity": "time_job_cost",
    }


def manpower_prefill(project_id: uuid.UUID, work_date: date, cu: CurrentUser) -> dict[str, Any]:
    _require_user(cu)
    policy = load_time_policy()
    start = datetime(work_date.year, work_date.month, work_date.day, tzinfo=_tz(policy)).astimezone(timezone.utc)
    end = start + timedelta(days=1)
    rows = list(
        db.session.scalars(
            select(TimeEntry).options(selectinload(TimeEntry.punches)).where(
                TimeEntry.project_id == project_id,
                TimeEntry.voided.is_(False),
                TimeEntry.started_at < end,
                or_(TimeEntry.ended_at.is_(None), TimeEntry.ended_at > start),
            )
        ).all()
    )
    users = _user_map([r.user_id for r in rows])
    by_person: dict[uuid.UUID, float] = {}
    for r in rows:
        hrs = paid_seconds(r.started_at, r.ended_at, [{"kind": p.kind, "occurred_at": p.occurred_at} for p in (r.punches or [])], min(_utcnow(), end)) / 3600.0
        by_person[r.user_id] = by_person.get(r.user_id, 0.0) + hrs
    items = [
        {"company": "USIS", "count": 1, "notes": f"{_name(users.get(uid))} — {hrs:.2f} h", "user_id": str(uid), "hours": round(hrs, 2)}
        for uid, hrs in by_person.items()
    ]
    return {"items": items, "headcount": len(items), "entity": "time_manpower"}


def get_settings(cu: CurrentUser) -> dict[str, Any]:
    _require_user(cu)
    codes = list_time_cost_codes(cu)
    return {"policy": load_time_policy(), "cost_codes": codes["items"], "can_edit": is_payroll(cu), "entity": "time_settings"}


def put_settings(data: Mapping[str, Any], cu: CurrentUser) -> dict[str, Any]:
    if not is_payroll(cu):
        raise TimeApiError("payroll admin only", 403)
    raw = data.get("policy") if isinstance(data.get("policy"), Mapping) else data
    save_time_policy(raw)
    db.session.commit()
    return get_settings(cu)
