"""Field time-clock punches, breaks, and job switches."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping

from sqlalchemy import or_, select

from ..extensions import db
from ..models import CostCode, FieldPhoto, Project, TimeEntry, TimePunch
from ..models.field_ops import DEFAULT_GEOFENCE_RADIUS_M, TIME_PUNCH_KINDS
from ._field_service import FieldApiError, _num_or_none, _parse_dt, _parse_uuid, _require_project_access
from ._perms import CurrentUser
from ._serializers import iso
from ._time_clock_math import evaluate_geofence, paid_seconds


def _require_user(cu: CurrentUser) -> uuid.UUID:
    if cu.id is None:
        raise FieldApiError("sign in required", 401)
    return cu.id


def _entry_by_client_or_id(raw: Any) -> TimeEntry | None:
    uid = _parse_uuid(raw)
    if uid is None:
        return None
    return db.session.scalar(
        select(TimeEntry).where(or_(TimeEntry.id == uid, TimeEntry.client_id == uid))
    )


def _punch_by_client(client_id: uuid.UUID) -> TimePunch | None:
    return db.session.scalar(select(TimePunch).where(TimePunch.client_id == client_id))


def _open_entry(user_id: uuid.UUID) -> TimeEntry | None:
    return db.session.scalar(
        select(TimeEntry).where(TimeEntry.user_id == user_id, TimeEntry.status != "closed")
    )


def _active_cost_codes(project_id: uuid.UUID) -> list[CostCode]:
    return list(
        db.session.scalars(
            select(CostCode)
            .where(CostCode.project_id == project_id, CostCode.is_active.is_(True))
            .order_by(CostCode.code)
        ).all()
    )


def _require_cost_code(project_id: uuid.UUID, cost_code_id: uuid.UUID | None) -> uuid.UUID | None:
    codes = _active_cost_codes(project_id)
    if not codes:
        return cost_code_id
    if cost_code_id is None:
        raise FieldApiError("cost_code_id is required for this project", 400)
    match = next((c for c in codes if c.id == cost_code_id), None)
    if match is None:
        raise FieldApiError("cost code not found", 400)
    return cost_code_id


def _photo_for_project(photo_id: uuid.UUID | None, project_id: uuid.UUID) -> uuid.UUID | None:
    if photo_id is None:
        return None
    photo = db.session.get(FieldPhoto, photo_id)
    if photo is None or photo.project_id != project_id:
        raise FieldApiError("photo not found", 400)
    return photo_id


def _project_fence(project: Project) -> tuple[float | None, float | None, float | None]:
    lat = float(project.latitude) if project.latitude is not None else None
    lon = float(project.longitude) if project.longitude is not None else None
    radius = float(project.geofence_radius_m) if project.geofence_radius_m is not None else float(DEFAULT_GEOFENCE_RADIUS_M)
    return lat, lon, radius


def _check_geofence(
    project: Project,
    lat: float | None,
    lon: float | None,
    override: bool,
) -> tuple[bool | None, float | None]:
    plat, plon, radius = _project_fence(project)
    ok, dist = evaluate_geofence(plat, plon, radius, lat, lon)
    if ok is False and not override:
        meters = f"{dist:.0f} m" if dist is not None else "unknown distance"
        raise FieldApiError(f"outside geofence ({meters}); set override_geofence to clock in anyway", 409)
    return ok, dist


def _parse_client_id(data: Mapping[str, Any], key: str = "client_id") -> uuid.UUID:
    cid = _parse_uuid(data.get(key))
    if cid is None:
        raise FieldApiError(f"{key} is required", 400)
    return cid


def _occurred_at(data: Mapping[str, Any]) -> datetime:
    at = _parse_dt(data.get("occurred_at"))
    return at or datetime.now(timezone.utc)


def _punch_public(row: TimePunch) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "entry_id": str(row.entry_id),
        "kind": row.kind,
        "occurred_at": iso(row.occurred_at),
        "lat": float(row.lat) if row.lat is not None else None,
        "lon": float(row.lon) if row.lon is not None else None,
        "accuracy_m": float(row.accuracy_m) if row.accuracy_m is not None else None,
        "geofence_ok": row.geofence_ok,
        "geofence_distance_m": float(row.geofence_distance_m) if row.geofence_distance_m is not None else None,
        "photo_id": str(row.photo_id) if row.photo_id else None,
        "note": row.note or "",
        "client_id": str(row.client_id),
    }


def time_entry_public(row: TimeEntry, *, now: datetime | None = None) -> dict[str, Any]:
    punches = list(row.punches or [])
    punches.sort(key=lambda p: p.occurred_at)
    clock = now or datetime.now(timezone.utc)
    seconds = paid_seconds(
        row.started_at,
        row.ended_at,
        [{"kind": p.kind, "occurred_at": p.occurred_at} for p in punches],
        clock,
    )
    return {
        "id": str(row.id),
        "user_id": str(row.user_id),
        "project_id": str(row.project_id),
        "cost_code_id": str(row.cost_code_id) if row.cost_code_id else None,
        "started_at": iso(row.started_at),
        "ended_at": iso(row.ended_at) if row.ended_at else None,
        "status": row.status,
        "note": row.note or "",
        "client_id": str(row.client_id),
        "clock_in_photo_id": str(row.clock_in_photo_id) if row.clock_in_photo_id else None,
        "clock_out_photo_id": str(row.clock_out_photo_id) if row.clock_out_photo_id else None,
        "paid_seconds": int(seconds),
        "punches": [_punch_public(p) for p in punches],
        "updated_at": iso(row.updated_at),
    }


def _envelope(entry: TimeEntry) -> dict[str, Any]:
    db.session.refresh(entry)
    entry.punches  # load
    return {"item": time_entry_public(entry), "entity": "time_entry"}


def _add_punch(
    entry: TimeEntry,
    *,
    kind: str,
    occurred_at: datetime,
    lat: float | None,
    lon: float | None,
    accuracy_m: float | None,
    geofence_ok: bool | None,
    geofence_distance_m: float | None,
    photo_id: uuid.UUID | None,
    note: str | None,
    client_id: uuid.UUID,
) -> TimePunch:
    if kind not in TIME_PUNCH_KINDS:
        raise FieldApiError("invalid punch kind", 400)
    punch = TimePunch(
        entry_id=entry.id,
        kind=kind,
        occurred_at=occurred_at,
        lat=lat,
        lon=lon,
        accuracy_m=accuracy_m,
        geofence_ok=geofence_ok,
        geofence_distance_m=geofence_distance_m,
        photo_id=photo_id,
        note=note,
        client_id=client_id,
    )
    db.session.add(punch)
    return punch


def clock_in(data: Mapping[str, Any], cu: CurrentUser) -> dict[str, Any]:
    user_id = _require_user(cu)
    client_id = _parse_client_id(data)
    existing_entry = db.session.scalar(select(TimeEntry).where(TimeEntry.client_id == client_id))
    if existing_entry is not None:
        return _envelope(existing_entry)
    existing_punch = _punch_by_client(client_id)
    if existing_punch is not None:
        entry = db.session.get(TimeEntry, existing_punch.entry_id)
        if entry is not None:
            return _envelope(entry)

    project_id = _parse_uuid(data.get("project_id"))
    if project_id is None:
        raise FieldApiError("project_id is required", 400)
    _require_project_access(cu, project_id)
    project = db.session.get(Project, project_id)
    if project is None:
        raise FieldApiError("project not found", 404)

    open_row = _open_entry(user_id)
    if open_row is not None:
        raise FieldApiError("already clocked in", 409)

    cost_code_id = _require_cost_code(project_id, _parse_uuid(data.get("cost_code_id")))
    lat = _num_or_none(data.get("lat"))
    lon = _num_or_none(data.get("lon"))
    override = bool(data.get("override_geofence"))
    ok, dist = _check_geofence(project, lat, lon, override)
    occurred = _occurred_at(data)
    photo_id = _photo_for_project(_parse_uuid(data.get("photo_id")), project_id)
    note = (str(data.get("note") or "").strip() or None)

    entry = TimeEntry(
        user_id=user_id,
        project_id=project_id,
        cost_code_id=cost_code_id,
        started_at=occurred,
        status="open",
        note=note,
        client_id=client_id,
        clock_in_photo_id=photo_id,
    )
    db.session.add(entry)
    db.session.flush()
    _add_punch(
        entry,
        kind="clock_in",
        occurred_at=occurred,
        lat=lat,
        lon=lon,
        accuracy_m=_num_or_none(data.get("accuracy_m")),
        geofence_ok=ok,
        geofence_distance_m=dist,
        photo_id=photo_id,
        note=note,
        client_id=client_id,
    )
    db.session.commit()
    return _envelope(entry)


def _owned_open(entry: TimeEntry | None, user_id: uuid.UUID) -> TimeEntry:
    if entry is None or entry.user_id != user_id:
        raise FieldApiError("time entry not found", 404)
    if entry.status == "closed":
        raise FieldApiError("time entry is closed", 409)
    return entry


def clock_out(data: Mapping[str, Any], cu: CurrentUser) -> dict[str, Any]:
    user_id = _require_user(cu)
    client_id = _parse_client_id(data)
    existing = _punch_by_client(client_id)
    if existing is not None:
        entry = db.session.get(TimeEntry, existing.entry_id)
        if entry is not None:
            return _envelope(entry)

    entry = _owned_open(_entry_by_client_or_id(data.get("entry_id")) or _open_entry(user_id), user_id)
    _require_project_access(cu, entry.project_id)
    project = db.session.get(Project, entry.project_id)
    if project is None:
        raise FieldApiError("project not found", 404)

    lat = _num_or_none(data.get("lat"))
    lon = _num_or_none(data.get("lon"))
    override = bool(data.get("override_geofence"))
    ok, dist = _check_geofence(project, lat, lon, override)
    occurred = _occurred_at(data)
    photo_id = _photo_for_project(_parse_uuid(data.get("photo_id")), entry.project_id)
    note = (str(data.get("note") or "").strip() or None)

    if entry.status == "on_break":
        _add_punch(
            entry,
            kind="break_end",
            occurred_at=occurred,
            lat=lat,
            lon=lon,
            accuracy_m=_num_or_none(data.get("accuracy_m")),
            geofence_ok=ok,
            geofence_distance_m=dist,
            photo_id=None,
            note=None,
            client_id=uuid.uuid4(),
        )

    _add_punch(
        entry,
        kind="clock_out",
        occurred_at=occurred,
        lat=lat,
        lon=lon,
        accuracy_m=_num_or_none(data.get("accuracy_m")),
        geofence_ok=ok,
        geofence_distance_m=dist,
        photo_id=photo_id,
        note=note,
        client_id=client_id,
    )
    entry.status = "closed"
    entry.ended_at = occurred
    entry.clock_out_photo_id = photo_id
    if note:
        entry.note = note
    db.session.add(entry)
    db.session.commit()
    return _envelope(entry)


def break_start(data: Mapping[str, Any], cu: CurrentUser) -> dict[str, Any]:
    user_id = _require_user(cu)
    client_id = _parse_client_id(data)
    existing = _punch_by_client(client_id)
    if existing is not None:
        entry = db.session.get(TimeEntry, existing.entry_id)
        if entry is not None:
            return _envelope(entry)

    entry = _owned_open(_entry_by_client_or_id(data.get("entry_id")) or _open_entry(user_id), user_id)
    if entry.status != "open":
        raise FieldApiError("already on break", 409)
    occurred = _occurred_at(data)
    _add_punch(
        entry,
        kind="break_start",
        occurred_at=occurred,
        lat=_num_or_none(data.get("lat")),
        lon=_num_or_none(data.get("lon")),
        accuracy_m=_num_or_none(data.get("accuracy_m")),
        geofence_ok=None,
        geofence_distance_m=None,
        photo_id=None,
        note=(str(data.get("note") or "").strip() or None),
        client_id=client_id,
    )
    entry.status = "on_break"
    db.session.add(entry)
    db.session.commit()
    return _envelope(entry)


def break_end(data: Mapping[str, Any], cu: CurrentUser) -> dict[str, Any]:
    user_id = _require_user(cu)
    client_id = _parse_client_id(data)
    existing = _punch_by_client(client_id)
    if existing is not None:
        entry = db.session.get(TimeEntry, existing.entry_id)
        if entry is not None:
            return _envelope(entry)

    entry = _owned_open(_entry_by_client_or_id(data.get("entry_id")) or _open_entry(user_id), user_id)
    if entry.status != "on_break":
        raise FieldApiError("not on break", 409)
    occurred = _occurred_at(data)
    _add_punch(
        entry,
        kind="break_end",
        occurred_at=occurred,
        lat=_num_or_none(data.get("lat")),
        lon=_num_or_none(data.get("lon")),
        accuracy_m=_num_or_none(data.get("accuracy_m")),
        geofence_ok=None,
        geofence_distance_m=None,
        photo_id=None,
        note=(str(data.get("note") or "").strip() or None),
        client_id=client_id,
    )
    entry.status = "open"
    db.session.add(entry)
    db.session.commit()
    return _envelope(entry)


def switch_job(data: Mapping[str, Any], cu: CurrentUser) -> dict[str, Any]:
    user_id = _require_user(cu)
    client_id = _parse_client_id(data)
    existing = _punch_by_client(client_id)
    if existing is not None:
        # Return the new open entry if this switch already ran.
        open_row = _open_entry(user_id)
        if open_row is not None:
            return _envelope(open_row)
        old = db.session.get(TimeEntry, existing.entry_id)
        if old is not None:
            return _envelope(old)

    old = _owned_open(_entry_by_client_or_id(data.get("entry_id")) or _open_entry(user_id), user_id)
    project_id = _parse_uuid(data.get("project_id"))
    if project_id is None:
        raise FieldApiError("project_id is required", 400)
    _require_project_access(cu, project_id)
    project = db.session.get(Project, project_id)
    if project is None:
        raise FieldApiError("project not found", 404)

    cost_code_id = _require_cost_code(project_id, _parse_uuid(data.get("cost_code_id")))
    lat = _num_or_none(data.get("lat"))
    lon = _num_or_none(data.get("lon"))
    override = bool(data.get("override_geofence"))
    ok, dist = _check_geofence(project, lat, lon, override)
    occurred = _occurred_at(data)
    photo_id = _photo_for_project(_parse_uuid(data.get("photo_id")), project_id)
    note = (str(data.get("note") or "").strip() or None)
    new_client = _parse_uuid(data.get("new_entry_client_id")) or uuid.uuid4()

    if old.status == "on_break":
        _add_punch(
            old,
            kind="break_end",
            occurred_at=occurred,
            lat=lat,
            lon=lon,
            accuracy_m=_num_or_none(data.get("accuracy_m")),
            geofence_ok=ok,
            geofence_distance_m=dist,
            photo_id=None,
            note=None,
            client_id=uuid.uuid4(),
        )

    _add_punch(
        old,
        kind="switch",
        occurred_at=occurred,
        lat=lat,
        lon=lon,
        accuracy_m=_num_or_none(data.get("accuracy_m")),
        geofence_ok=ok,
        geofence_distance_m=dist,
        photo_id=None,
        note=note,
        client_id=client_id,
    )
    old.status = "closed"
    old.ended_at = occurred
    db.session.add(old)
    db.session.flush()

    new_entry = TimeEntry(
        user_id=user_id,
        project_id=project_id,
        cost_code_id=cost_code_id,
        started_at=occurred,
        status="open",
        note=note,
        client_id=new_client,
        clock_in_photo_id=photo_id,
    )
    db.session.add(new_entry)
    db.session.flush()
    _add_punch(
        new_entry,
        kind="clock_in",
        occurred_at=occurred,
        lat=lat,
        lon=lon,
        accuracy_m=_num_or_none(data.get("accuracy_m")),
        geofence_ok=ok,
        geofence_distance_m=dist,
        photo_id=photo_id,
        note=note,
        client_id=new_client,
    )
    db.session.commit()
    return _envelope(new_entry)


def list_me(cu: CurrentUser) -> dict[str, Any]:
    user_id = _require_user(cu)
    now = datetime.now(timezone.utc)
    since = (now - timedelta(days=7)).replace(hour=0, minute=0, second=0, microsecond=0)
    rows = list(
        db.session.scalars(
            select(TimeEntry)
            .where(TimeEntry.user_id == user_id, TimeEntry.started_at >= since)
            .order_by(TimeEntry.started_at.desc())
        ).all()
    )
    open_row = next((r for r in rows if r.status != "closed"), _open_entry(user_id))
    today = now.date()
    today_rows = [r for r in rows if r.started_at.astimezone(timezone.utc).date() == today]
    return {
        "open": time_entry_public(open_row, now=now) if open_row is not None else None,
        "today": [time_entry_public(r, now=now) for r in today_rows],
        "items": [time_entry_public(r, now=now) for r in rows],
        "entity": "time_clock",
    }


def list_cost_codes(project_id: uuid.UUID, cu: CurrentUser) -> dict[str, Any]:
    _require_project_access(cu, project_id)
    items = [
        {
            "id": str(c.id),
            "project_id": str(c.project_id),
            "code": c.code,
            "description": c.description or "",
            "is_active": c.is_active,
        }
        for c in _active_cost_codes(project_id)
    ]
    return {"items": items, "total": len(items), "entity": "cost_codes"}
