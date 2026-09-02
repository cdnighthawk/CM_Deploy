"""Office + field timekeeping: punches, OT recompute, flags, periods, live board."""
from __future__ import annotations

import csv
import io
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Mapping
from zoneinfo import ZoneInfo

from flask import request
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import selectinload

from ..extensions import db
from ..models import (
    AuditLog,
    CostCode,
    Document,
    EmployeeTimeProfile,
    EstimateLineItem,
    FieldPhoto,
    Project,
    ProjectGeofence,
    ProjectMember,
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
from ..models.field_ops import DEFAULT_GEOFENCE_RADIUS_M
from ..permissions.project_scope import user_can_access_project
from ..services.object_storage import UploadCategory, save_upload
from ._field_service import _num_or_none, _parse_dt, _parse_uuid
from ._in_app_notifications import create_in_app_notification
from ._perms import CurrentUser
from ._serializers import iso
from ._time_clock_math import paid_seconds
from ._time_geo import evaluate_project_fence
from ._time_ot import compute_day, compute_week
from ._time_policy import WEEKDAY_INDEX, load_time_policy, merge_policy, save_time_policy

PROCESS_TIMECARD = "timecard"

_PAYROLL_ROLES = ("admin", "superuser", "project_accountant", "hr_admin")
_SUPERVISOR_ROLES = (
    "admin",
    "superuser",
    "superintendent",
    "project_manager",
    "project_engineer",
    "standard",
)
_SKEW_SEC = 15 * 60


class TimeApiError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message = message
        self.status = status


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _tz(policy: Mapping[str, Any]) -> ZoneInfo:
    name = str(policy.get("timezone") or "America/Los_Angeles")
    try:
        return ZoneInfo(name)
    except Exception:
        return ZoneInfo("America/Los_Angeles")


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _local_date(dt: datetime, policy: Mapping[str, Any]) -> date:
    return _aware(dt).astimezone(_tz(policy)).date()  # type: ignore[union-attr]


def _week_bounds(d: date, policy: Mapping[str, Any]) -> tuple[date, date]:
    start_i = WEEKDAY_INDEX.get(str(policy.get("week_start") or "sunday"), 6)
    # Python Monday=0. Convert target weekday.
    py = (start_i) % 7
    delta = (d.weekday() - py) % 7
    start = d - timedelta(days=delta)
    return start, start + timedelta(days=6)


def _require_user(cu: CurrentUser) -> uuid.UUID:
    if cu.id is None:
        raise TimeApiError("sign in required", 401)
    return cu.id


def is_payroll(cu: CurrentUser) -> bool:
    return cu.is_dev_admin or cu.has_role(*_PAYROLL_ROLES)


def is_supervisor(cu: CurrentUser) -> bool:
    return cu.is_dev_admin or cu.has_role(*_SUPERVISOR_ROLES) or is_payroll(cu)


def can_see_rates(cu: CurrentUser) -> bool:
    return is_payroll(cu)


def _name(user: User | None) -> str:
    if user is None:
        return ""
    return " ".join(p for p in (user.first_name, user.last_name) if p).strip() or (user.email or "")


def _client_id(data: Mapping[str, Any]) -> uuid.UUID:
    cid = _parse_uuid(data.get("local_id") or data.get("client_id"))
    if cid is None:
        raise TimeApiError("local_id is required", 400)
    return cid


def _source_of(data: Mapping[str, Any], *, default: str = "mobile") -> str:
    raw = str(data.get("source") or default).strip() or default
    if raw not in ("mobile", "supervisor_mobile", "web", "office_edit", "kiosk"):
        return default
    return raw


def _device_at(data: Mapping[str, Any]) -> datetime | None:
    return _parse_dt(data.get("device_at") or data.get("at") or data.get("occurred_at"))


def _punch_time(data: Mapping[str, Any], server: datetime) -> tuple[datetime, datetime | None, bool]:
    device = _device_at(data)
    at = device or server
    skew = False
    if device is not None:
        delta = abs((device - server).total_seconds())
        if delta > _SKEW_SEC:
            skew = True
    return at, device, skew


def _open_entry(user_id: uuid.UUID) -> TimeEntry | None:
    return db.session.scalar(select(TimeEntry).where(TimeEntry.user_id == user_id, TimeEntry.status != "closed", TimeEntry.voided.is_(False)))


def _entry_by_local(raw: Any) -> TimeEntry | None:
    uid = _parse_uuid(raw)
    if uid is None:
        return None
    return db.session.scalar(select(TimeEntry).where(or_(TimeEntry.id == uid, TimeEntry.client_id == uid)))


def _punch_by_local(cid: uuid.UUID) -> TimePunch | None:
    return db.session.scalar(select(TimePunch).where(TimePunch.client_id == cid))


def _period_locked(entry: TimeEntry, policy: Mapping[str, Any]) -> bool:
    if entry.locked:
        return True
    work = _local_date(entry.started_at, policy)
    period = db.session.scalar(
        select(TimecardPeriod).where(TimecardPeriod.period_start <= work, TimecardPeriod.period_end >= work)
    )
    return period is not None and period.status in ("locked", "exported")


def _can_act_for(cu: CurrentUser, user_id: uuid.UUID, project_id: uuid.UUID | None) -> bool:
    if cu.id == user_id or cu.is_dev_admin or is_payroll(cu):
        return True
    if not is_supervisor(cu):
        return False
    if project_id is None:
        return True
    return user_can_access_project(cu, project_id)


def _require_project(cu: CurrentUser, project_id: uuid.UUID) -> Project:
    project = db.session.get(Project, project_id)
    if project is None:
        raise TimeApiError("project not found", 404)
    if not user_can_access_project(cu, project_id) and not is_payroll(cu) and not cu.is_dev_admin:
        raise TimeApiError("project not found", 404)
    return project


def _resolve_time_cost_code(raw_id: uuid.UUID | None) -> uuid.UUID | None:
    if raw_id is None:
        return None
    row = db.session.get(TimeCostCode, raw_id)
    if row is None:
        return None
    return row.id


def _gps_status(lat: float | None, lon: float | None, data: Mapping[str, Any]) -> str:
    raw = str(data.get("gps_status") or "").strip().lower()
    if raw in ("ok", "denied", "unavailable", "stale"):
        return raw
    if lat is None or lon is None:
        return "denied"
    return "ok"


def _add_event(
    *,
    kind: str,
    entry: TimeEntry | None,
    user_id: uuid.UUID,
    occurred_at: datetime,
    data: Mapping[str, Any],
    client_id: uuid.UUID,
    lat: float | None,
    lon: float | None,
    acc: float | None,
    geofence_ok: bool | None,
    geofence_distance_m: float | None,
    source: str,
    performed_by: uuid.UUID | None,
    reason: str | None = None,
    payload: dict[str, Any] | None = None,
) -> TimePunch:
    punch = TimePunch(
        entry_id=entry.id if entry is not None else None,
        user_id=user_id,
        project_id=entry.project_id if entry is not None else _parse_uuid(data.get("project_id")),
        cost_code_id=entry.cost_code_id if entry is not None else None,
        time_cost_code_id=entry.time_cost_code_id if entry is not None else None,
        kind=kind,
        occurred_at=occurred_at,
        lat=lat,
        lon=lon,
        accuracy_m=acc,
        geofence_ok=geofence_ok,
        geofence_distance_m=geofence_distance_m,
        photo_id=_parse_uuid(data.get("photo_id")),
        note=(str(data.get("note") or "").strip() or None),
        client_id=client_id,
        source=source,
        performed_by_id=performed_by,
        payload_json=payload,
        device_label=(str(data.get("device") or data.get("device_label") or "").strip() or None),
        reason=reason,
    )
    db.session.add(punch)
    return punch


def _open_flag(
    *,
    user_id: uuid.UUID,
    flag_type: str,
    entry: TimeEntry | None = None,
    project_id: uuid.UUID | None = None,
    work_date: date | None = None,
    detail: str | None = None,
) -> TimeFlag | None:
    stmt = select(TimeFlag).where(
        TimeFlag.user_id == user_id,
        TimeFlag.flag_type == flag_type,
        TimeFlag.status == "open",
    )
    if entry is not None:
        stmt = stmt.where(TimeFlag.time_entry_id == entry.id)
    elif work_date is not None:
        stmt = stmt.where(TimeFlag.work_date == work_date)
    existing = db.session.scalar(stmt)
    if existing is not None:
        return existing
    row = TimeFlag(
        user_id=user_id,
        time_entry_id=entry.id if entry is not None else None,
        project_id=project_id or (entry.project_id if entry is not None else None),
        work_date=work_date,
        flag_type=flag_type,
        status="open",
        detail=detail,
    )
    db.session.add(row)
    return row


def _check_fence(
    project: Project,
    lat: float | None,
    lon: float | None,
    policy: Mapping[str, Any],
    override: bool,
    *,
    raise_block: bool = True,
) -> tuple[bool | None, float | None, str]:
    fence = db.session.scalar(select(ProjectGeofence).where(ProjectGeofence.project_id == project.id))
    plat = float(project.latitude) if project.latitude is not None else None
    plon = float(project.longitude) if project.longitude is not None else None
    radius = float(project.geofence_radius_m) if project.geofence_radius_m is not None else float(DEFAULT_GEOFENCE_RADIUS_M)
    ok, dist, mode = evaluate_project_fence(
        fence=fence,
        project_lat=plat,
        project_lon=plon,
        project_radius_m=radius,
        lat=lat,
        lon=lon,
        default_mode=str(policy.get("geofence_default_mode") or "flag"),
    )
    if ok is False and mode == "block" and not override and raise_block:
        meters = f"{dist:.0f} m" if dist is not None else "unknown distance"
        raise TimeApiError(f"outside geofence ({meters})", 409)
    return ok, dist, mode


def _photo_ok(photo_id: uuid.UUID | None, project_id: uuid.UUID) -> uuid.UUID | None:
    if photo_id is None:
        return None
    photo = db.session.get(FieldPhoto, photo_id)
    if photo is None or photo.project_id != project_id:
        raise TimeApiError("photo not found", 400)
    return photo_id


def punch_public(row: TimePunch) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "entry_id": str(row.entry_id) if row.entry_id else None,
        "user_id": str(row.user_id) if row.user_id else None,
        "kind": row.kind,
        "event_type": row.kind,
        "occurred_at": iso(row.occurred_at),
        "at": iso(row.occurred_at),
        "lat": float(row.lat) if row.lat is not None else None,
        "lon": float(row.lon) if row.lon is not None else None,
        "acc": float(row.accuracy_m) if row.accuracy_m is not None else None,
        "accuracy_m": float(row.accuracy_m) if row.accuracy_m is not None else None,
        "geofence_ok": row.geofence_ok,
        "geofence_distance_m": float(row.geofence_distance_m) if row.geofence_distance_m is not None else None,
        "photo_id": str(row.photo_id) if row.photo_id else None,
        "note": row.note or "",
        "client_id": str(row.client_id),
        "local_id": str(row.client_id),
        "source": row.source,
        "performed_by_id": str(row.performed_by_id) if row.performed_by_id else None,
        "device": row.device_label,
        "reason": row.reason,
        "payload": row.payload_json,
    }


def time_entry_public(row: TimeEntry, *, now: datetime | None = None, policy: Mapping[str, Any] | None = None) -> dict[str, Any]:
    punches = list(row.punches or [])
    punches.sort(key=lambda p: p.occurred_at)
    clock = now or _utcnow()
    seconds = paid_seconds(
        row.started_at,
        row.ended_at,
        [{"kind": p.kind, "occurred_at": p.occurred_at} for p in punches],
        clock,
    )
    pol = policy or load_time_policy()
    return {
        "id": str(row.id),
        "user_id": str(row.user_id),
        "project_id": str(row.project_id),
        "cost_code_id": str(row.time_cost_code_id or row.cost_code_id) if (row.time_cost_code_id or row.cost_code_id) else None,
        "job_cost_code_id": str(row.cost_code_id) if row.cost_code_id else None,
        "time_cost_code_id": str(row.time_cost_code_id) if row.time_cost_code_id else None,
        "started_at": iso(row.started_at),
        "start_at": iso(row.started_at),
        "ended_at": iso(row.ended_at) if row.ended_at else None,
        "end_at": iso(row.ended_at) if row.ended_at else None,
        "status": row.status,
        "entry_type": row.entry_type or "work",
        "note": row.note or "",
        "client_id": str(row.client_id),
        "local_id": str(row.client_id),
        "source": row.source,
        "offsite": bool(row.offsite),
        "gps_status": row.gps_status,
        "locked": bool(row.locked),
        "voided": bool(row.voided),
        "clock_in_photo_id": str(row.clock_in_photo_id) if row.clock_in_photo_id else None,
        "clock_out_photo_id": str(row.clock_out_photo_id) if row.clock_out_photo_id else None,
        "paid_seconds": int(seconds),
        "work_date": _local_date(row.started_at, pol).isoformat(),
        "punches": [punch_public(p) for p in punches],
        "updated_at": iso(row.updated_at),
    }


def _envelope(entry: TimeEntry, policy: Mapping[str, Any] | None = None) -> dict[str, Any]:
    db.session.refresh(entry)
    _ = entry.punches
    return {"item": time_entry_public(entry, policy=policy), "entity": "time_entry"}


def ensure_current_period(policy: Mapping[str, Any] | None = None, on: date | None = None) -> TimecardPeriod:
    pol = policy or load_time_policy()
    today = on or _utcnow().astimezone(_tz(pol)).date()
    start, end = _week_bounds(today, pol)
    row = db.session.scalar(
        select(TimecardPeriod).where(TimecardPeriod.period_start == start, TimecardPeriod.period_end == end)
    )
    if row is None:
        row = TimecardPeriod(period_start=start, period_end=end, status="open", policy_json=dict(pol))
        db.session.add(row)
        db.session.commit()
    return row


def recompute_day(user_id: uuid.UUID, work_date: date, policy: Mapping[str, Any] | None = None) -> TimecardDay:
    pol = policy or load_time_policy()
    tz = _tz(pol)
    start_local = datetime(work_date.year, work_date.month, work_date.day, tzinfo=tz)
    end_local = start_local + timedelta(days=1)
    start_utc = start_local.astimezone(timezone.utc)
    end_utc = end_local.astimezone(timezone.utc)
    rows = list(
        db.session.scalars(
            select(TimeEntry)
            .options(selectinload(TimeEntry.punches))
            .where(
                TimeEntry.user_id == user_id,
                TimeEntry.voided.is_(False),
                TimeEntry.started_at < end_utc,
                or_(TimeEntry.ended_at.is_(None), TimeEntry.ended_at > start_utc),
            )
            .order_by(TimeEntry.started_at)
        ).all()
    )
    payload = [
        {
            "start_at": r.started_at,
            "end_at": r.ended_at,
            "entry_type": r.entry_type or "work",
            "punches": [{"kind": p.kind, "occurred_at": p.occurred_at} for p in (r.punches or [])],
        }
        for r in rows
    ]
    result = compute_day(payload, pol, now=_utcnow())
    day = db.session.scalar(select(TimecardDay).where(TimecardDay.user_id == user_id, TimecardDay.work_date == work_date))
    signed_at = day.signed_at if day is not None else None
    signed_ip = day.signed_ip if day is not None else None
    sig = day.signature_png_url if day is not None else None
    attested = day.employee_attested_accurate if day is not None else False
    injury = day.injury_reported if day is not None else False
    injury_note = day.injury_note if day is not None else None
    if day is None:
        day = TimecardDay(user_id=user_id, work_date=work_date)
        db.session.add(day)
    day.regular_hours = Decimal(str(result.regular_hours))
    day.ot_hours = Decimal(str(result.ot_hours))
    day.dt_hours = Decimal(str(result.dt_hours))
    day.premium_hours = Decimal(str(result.premium_hours))
    day.meal_minutes = Decimal(str(result.meal_minutes))
    day.signed_at = signed_at
    day.signed_ip = signed_ip
    day.signature_png_url = sig
    day.employee_attested_accurate = attested
    day.injury_reported = injury
    day.injury_note = injury_note
    if "missing_meal" in result.premium_flags:
        _open_flag(user_id=user_id, flag_type="missing_meal", work_date=work_date, detail="No unpaid meal ≥ 30 min before the 5th hour")
    project_id = rows[0].project_id if rows else None
    if "missing_meal" in result.premium_flags and project_id:
        pass
    db.session.flush()
    return day


def _after_punch(entry: TimeEntry, policy: Mapping[str, Any]) -> None:
    recompute_day(entry.user_id, _local_date(entry.started_at, policy), policy)


def punch(data: Mapping[str, Any], cu: CurrentUser, *, field_envelope: bool = True) -> dict[str, Any]:
    policy = load_time_policy()
    user_id = _require_user(cu)
    target_id = _parse_uuid(data.get("user_id")) or user_id
    if target_id != user_id and not is_supervisor(cu):
        raise TimeApiError("not allowed to punch for this user", 403)
    action = str(data.get("action") or "").strip().lower()
    if action not in ("clock_in", "clock_out", "break_start", "break_end", "switch"):
        raise TimeApiError("action must be clock_in, clock_out, break_start, break_end, or switch", 400)

    client_id = _client_id(data)
    existing_punch = _punch_by_local(client_id)
    if existing_punch is not None:
        entry = db.session.get(TimeEntry, existing_punch.entry_id) if existing_punch.entry_id else _open_entry(target_id)
        if action == "switch":
            entry = _open_entry(target_id) or entry
        if entry is not None:
            return _envelope(entry, policy)

    existing_entry = db.session.scalar(select(TimeEntry).where(TimeEntry.client_id == client_id))
    if existing_entry is not None and action == "clock_in":
        return _envelope(existing_entry, policy)

    server = _utcnow()
    at, device_at, skew = _punch_time(data, server)
    lat = _num_or_none(data.get("lat"))
    lon = _num_or_none(data.get("lon"))
    acc = _num_or_none(data.get("acc") if data.get("acc") is not None else data.get("accuracy_m"))
    source = _source_of(data, default="web" if str(data.get("source") or "") == "web" else "mobile")
    if source == "mobile" and (data.get("source") in (None, "")):
        source = "web" if request and request.path.startswith("/api/time") else "mobile"
    override = bool(data.get("override_geofence") or data.get("override"))
    if override and not is_supervisor(cu):
        raise TimeApiError("supervisor override required", 403)
    note = str(data.get("note") or "").strip() or None
    reason = str(data.get("reason") or "").strip() or None
    gps_status = _gps_status(lat, lon, data)
    performed_by = user_id

    def _fence(project: Project, *, raise_block: bool = True) -> tuple[bool | None, float | None, bool]:
        ok, dist, mode = _check_fence(project, lat, lon, policy, override, raise_block=raise_block)
        offsite = ok is False
        if offsite and mode == "flag":
            return ok, dist, True
        if offsite and mode == "block" and (override or not raise_block):
            return ok, dist, True
        return ok, dist, offsite

    if action == "clock_in":
        project_id = _parse_uuid(data.get("project_id"))
        if project_id is None:
            raise TimeApiError("project_id is required", 400)
        project = _require_project(cu, project_id)
        if _open_entry(target_id) is not None:
            raise TimeApiError("already clocked in", 409)
        if policy.get("require_cost_code") and not (_parse_uuid(data.get("cost_code_id")) or _parse_uuid(data.get("time_cost_code_id"))):
            raise TimeApiError("cost_code_id is required", 409)
        time_cc = _resolve_time_cost_code(_parse_uuid(data.get("cost_code_id")) or _parse_uuid(data.get("time_cost_code_id")))
        job_cc = None
        raw_cc = _parse_uuid(data.get("cost_code_id"))
        if raw_cc and time_cc is None:
            cc = db.session.get(CostCode, raw_cc)
            if cc is not None:
                job_cc = cc.id
        ok, dist, offsite = _fence(project)
        photo_id = _photo_ok(_parse_uuid(data.get("photo_id")), project_id)
        entry = TimeEntry(
            user_id=target_id,
            project_id=project_id,
            cost_code_id=job_cc,
            time_cost_code_id=time_cc,
            started_at=at,
            status="open",
            note=note,
            client_id=client_id,
            clock_in_photo_id=photo_id,
            entry_type="work",
            source=source,
            punched_by_id=performed_by,
            device_start_at=device_at,
            start_lat=lat,
            start_lon=lon,
            start_acc=acc,
            gps_status=gps_status,
            offsite=offsite,
            ip_address=(request.remote_addr if request else None),
            device_label=(str(data.get("device") or data.get("device_label") or "").strip() or None),
        )
        db.session.add(entry)
        db.session.flush()
        _add_event(
            kind="clock_in",
            entry=entry,
            user_id=target_id,
            occurred_at=at,
            data=data,
            client_id=client_id,
            lat=lat,
            lon=lon,
            acc=acc,
            geofence_ok=ok,
            geofence_distance_m=dist,
            source=source,
            performed_by=performed_by,
            reason=reason,
        )
        if offsite:
            _open_flag(user_id=target_id, flag_type="blocked_override" if override else "offsite", entry=entry, project_id=project_id, detail="Punch outside geofence")
        if gps_status == "denied":
            _open_flag(user_id=target_id, flag_type="gps_denied", entry=entry, project_id=project_id, detail="GPS denied or unavailable")
        if skew:
            _open_flag(user_id=target_id, flag_type="clock_skew", entry=entry, project_id=project_id, detail="Device clock more than 15 minutes from server")
        _after_punch(entry, policy)
        db.session.commit()
        return _envelope(entry, policy)

    entry = _owned_open(_entry_by_local(data.get("entry_id")) or _open_entry(target_id), target_id)
    if _period_locked(entry, policy) and not is_payroll(cu):
        raise TimeApiError("period is locked", 409)
    project = db.session.get(Project, entry.project_id)
    if project is None:
        raise TimeApiError("project not found", 404)
    ok, dist, offsite = _fence(project, raise_block=(action != "clock_out")) if action in ("clock_out", "switch") else (None, None, False)

    if action == "clock_out":
        if entry.status == "on_break":
            _add_event(
                kind="break_end",
                entry=entry,
                user_id=target_id,
                occurred_at=at,
                data=data,
                client_id=uuid.uuid4(),
                lat=lat,
                lon=lon,
                acc=acc,
                geofence_ok=ok,
                geofence_distance_m=dist,
                source=source,
                performed_by=performed_by,
            )
        photo_id = _photo_ok(_parse_uuid(data.get("photo_id")), entry.project_id)
        _add_event(
            kind="clock_out",
            entry=entry,
            user_id=target_id,
            occurred_at=at,
            data=data,
            client_id=client_id,
            lat=lat,
            lon=lon,
            acc=acc,
            geofence_ok=ok,
            geofence_distance_m=dist,
            source=source,
            performed_by=performed_by,
            reason=reason,
        )
        entry.status = "closed"
        entry.ended_at = at
        entry.device_end_at = device_at
        entry.end_lat = lat
        entry.end_lon = lon
        entry.end_acc = acc
        entry.clock_out_photo_id = photo_id
        if note:
            entry.note = note
        if offsite:
            entry.offsite = True
            _open_flag(user_id=target_id, flag_type="offsite", entry=entry, project_id=entry.project_id)
        db.session.add(entry)
        _after_punch(entry, policy)
        db.session.commit()
        return _envelope(entry, policy)

    if action == "break_start":
        if entry.status != "open":
            raise TimeApiError("already on break", 409)
        _add_event(
            kind="break_start",
            entry=entry,
            user_id=target_id,
            occurred_at=at,
            data=data,
            client_id=client_id,
            lat=lat,
            lon=lon,
            acc=acc,
            geofence_ok=None,
            geofence_distance_m=None,
            source=source,
            performed_by=performed_by,
        )
        entry.status = "on_break"
        db.session.add(entry)
        db.session.commit()
        return _envelope(entry, policy)

    if action == "break_end":
        if entry.status != "on_break":
            raise TimeApiError("not on break", 409)
        _add_event(
            kind="break_end",
            entry=entry,
            user_id=target_id,
            occurred_at=at,
            data=data,
            client_id=client_id,
            lat=lat,
            lon=lon,
            acc=acc,
            geofence_ok=None,
            geofence_distance_m=None,
            source=source,
            performed_by=performed_by,
        )
        entry.status = "open"
        db.session.add(entry)
        _after_punch(entry, policy)
        db.session.commit()
        return _envelope(entry, policy)

    # switch
    project_id = _parse_uuid(data.get("project_id")) or entry.project_id
    project = _require_project(cu, project_id)
    time_cc = _resolve_time_cost_code(_parse_uuid(data.get("cost_code_id")) or _parse_uuid(data.get("time_cost_code_id")))
    job_cc = None
    raw_cc = _parse_uuid(data.get("cost_code_id"))
    if raw_cc and time_cc is None:
        cc = db.session.get(CostCode, raw_cc)
        if cc is not None:
            job_cc = cc.id
    ok, dist, offsite = _fence(project)
    new_client = _parse_uuid(data.get("new_entry_client_id") or data.get("new_local_id")) or uuid.uuid4()
    if entry.status == "on_break":
        _add_event(
            kind="break_end",
            entry=entry,
            user_id=target_id,
            occurred_at=at,
            data=data,
            client_id=uuid.uuid4(),
            lat=lat,
            lon=lon,
            acc=acc,
            geofence_ok=ok,
            geofence_distance_m=dist,
            source=source,
            performed_by=performed_by,
        )
    _add_event(
        kind="switch",
        entry=entry,
        user_id=target_id,
        occurred_at=at,
        data=data,
        client_id=client_id,
        lat=lat,
        lon=lon,
        acc=acc,
        geofence_ok=ok,
        geofence_distance_m=dist,
        source=source,
        performed_by=performed_by,
        reason=reason,
    )
    entry.status = "closed"
    entry.ended_at = at
    entry.device_end_at = device_at
    db.session.add(entry)
    db.session.flush()
    gap_start = at + timedelta(seconds=1) if False else at  # gap ≤ 1s; zero is allowed
    new_entry = TimeEntry(
        user_id=target_id,
        project_id=project_id,
        cost_code_id=job_cc if job_cc is not None else entry.cost_code_id,
        time_cost_code_id=time_cc if time_cc is not None else entry.time_cost_code_id,
        started_at=gap_start,
        status="open",
        note=note,
        client_id=new_client,
        entry_type="work",
        source=source,
        punched_by_id=performed_by,
        device_start_at=device_at,
        start_lat=lat,
        start_lon=lon,
        start_acc=acc,
        gps_status=gps_status,
        offsite=offsite,
        device_label=(str(data.get("device") or "").strip() or None),
    )
    db.session.add(new_entry)
    db.session.flush()
    _add_event(
        kind="clock_in",
        entry=new_entry,
        user_id=target_id,
        occurred_at=gap_start,
        data=data,
        client_id=new_client,
        lat=lat,
        lon=lon,
        acc=acc,
        geofence_ok=ok,
        geofence_distance_m=dist,
        source=source,
        performed_by=performed_by,
    )
    _after_punch(entry, policy)
    _after_punch(new_entry, policy)
    db.session.commit()
    return _envelope(new_entry, policy)


def _owned_open(entry: TimeEntry | None, user_id: uuid.UUID) -> TimeEntry:
    if entry is None or entry.user_id != user_id:
        raise TimeApiError("time entry not found", 404)
    if entry.status == "closed" or entry.voided:
        raise TimeApiError("time entry is closed", 409)
    return entry


def list_me(cu: CurrentUser) -> dict[str, Any]:
    policy = load_time_policy()
    user_id = _require_user(cu)
    now = _utcnow()
    since = now - timedelta(days=14)
    rows = list(
        db.session.scalars(
            select(TimeEntry)
            .options(selectinload(TimeEntry.punches))
            .where(TimeEntry.user_id == user_id, TimeEntry.started_at >= since, TimeEntry.voided.is_(False))
            .order_by(TimeEntry.started_at.desc())
        ).all()
    )
    open_row = next((r for r in rows if r.status != "closed"), _open_entry(user_id))
    today = _local_date(now, policy)
    today_rows = [r for r in rows if _local_date(r.started_at, policy) == today]
    day = db.session.scalar(select(TimecardDay).where(TimecardDay.user_id == user_id, TimecardDay.work_date == today))
    period = ensure_current_period(policy)
    week_start, _week_end = _week_bounds(today, policy)
    week_days = list(
        db.session.scalars(
            select(TimecardDay).where(
                TimecardDay.user_id == user_id,
                TimecardDay.work_date >= week_start,
                TimecardDay.work_date <= today,
            )
        ).all()
    )
    period_days = list(
        db.session.scalars(
            select(TimecardDay).where(
                TimecardDay.user_id == user_id,
                TimecardDay.work_date >= period.period_start,
                TimecardDay.work_date <= period.period_end,
            )
        ).all()
    )

    def _sum_hours(days: list[TimecardDay]) -> dict[str, float]:
        return {
            "regular": float(sum((d.regular_hours or 0) for d in days)),
            "ot": float(sum((d.ot_hours or 0) for d in days)),
            "dt": float(sum((d.dt_hours or 0) for d in days)),
            "total": float(sum((d.regular_hours or 0) + (d.ot_hours or 0) + (d.dt_hours or 0) for d in days)),
        }

    sign_needed = any(d.signed_at is None and ((d.regular_hours or 0) + (d.ot_hours or 0) + (d.dt_hours or 0)) > 0 for d in period_days)
    re_sign = db.session.scalar(
        select(TimeFlag.id).where(
            TimeFlag.user_id == user_id,
            TimeFlag.flag_type == "edited_after_sign",
            TimeFlag.status == "open",
        )
    )
    projects_14: dict[str, float] = {}
    names: dict[str, str] = {}
    cutoff = now - timedelta(days=14)
    for r in rows:
        if r.started_at < cutoff:
            continue
        secs = paid_seconds(r.started_at, r.ended_at, [{"kind": p.kind, "occurred_at": p.occurred_at} for p in (r.punches or [])], now)
        key = str(r.project_id)
        projects_14[key] = projects_14.get(key, 0.0) + secs / 3600.0
        proj = db.session.get(Project, r.project_id)
        if proj is not None:
            names[key] = f"{proj.number or ''} {proj.name or ''}".strip()
    hours_by_project = [
        {"project_id": pid, "name": names.get(pid, ""), "hours": round(hrs, 2)}
        for pid, hrs in sorted(projects_14.items(), key=lambda kv: kv[1], reverse=True)[:8]
    ]
    profile = db.session.scalar(select(EmployeeTimeProfile).where(EmployeeTimeProfile.user_id == user_id))
    user = db.session.get(User, user_id)
    status = "out"
    if open_row is not None:
        status = "break" if open_row.status == "on_break" else "in"
    return {
        "open": time_entry_public(open_row, now=now, policy=policy) if open_row is not None else None,
        "today": [time_entry_public(r, now=now, policy=policy) for r in today_rows],
        "items": [time_entry_public(r, now=now, policy=policy) for r in rows],
        "status": status,
        "hours": {
            "today": _sum_hours([day] if day is not None else []),
            "week": _sum_hours(week_days),
            "period": _sum_hours(period_days),
        },
        "sign_ready": bool(sign_needed or re_sign),
        "period": {"id": str(period.id), "start": period.period_start.isoformat(), "end": period.period_end.isoformat(), "status": period.status},
        "hours_by_project": hours_by_project,
        "profile": {
            "classification": profile.classification if profile else None,
            "name": _name(user),
            "email": user.email if user else None,
            "phone": user.phone if user else None,
        },
        "web_punch_allowed": bool(policy.get("web_punch_allowed")),
        "policy": {"require_cost_code": bool(policy.get("require_cost_code")), "timezone": policy.get("timezone")},
        "entity": "time_clock",
    }
