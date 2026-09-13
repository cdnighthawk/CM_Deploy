"""FinishWorks Field punch-list CRUD, directory, locations, and notify."""
from __future__ import annotations

import base64
import io
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any, Mapping

from werkzeug.datastructures import FileStorage

from flask import render_template
from sqlalchemy import func, or_, select

from ..extensions import db
from ..models import (
    AuditLog,
    Contact,
    Drawing,
    FieldPhoto,
    FieldPunchItem,
    Location,
    Project,
    ProjectDirectoryCompany,
    ProjectMember,
    PunchDistribution,
    PunchNotifyLog,
    User,
)
from ..models.field_punch import (
    PUNCH_IMPACTS,
    PUNCH_LISTS,
    PUNCH_OPEN_STATUSES,
    PUNCH_PRIORITIES,
    PUNCH_SOURCES,
    PUNCH_STATUSES,
    PUNCH_TRADES,
    PUNCH_TYPES,
)
from ._field_service import (
    FieldApiError,
    _parse_uuid,
    _require_project_access,
    create_field_photo,
    field_photo_public,
    first_upload_file,
)
from ._notifications import send_html_notification_email
from ._perms import CurrentUser
from ._serializers import iso

GC_CREATE_MSG = "GC punch items cannot be created from the field app in v1"


class PunchFieldError(FieldApiError):
    def __init__(self, message: str, status: int = 400, field: str | None = None):
        super().__init__(message, status)
        self.field = field


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_bool(raw: Any, default: bool = False) -> bool:
    if raw is None:
        return default
    if isinstance(raw, bool):
        return raw
    s = str(raw).strip().lower()
    if s in ("1", "true", "yes", "on"):
        return True
    if s in ("0", "false", "no", "off", ""):
        return False
    return default


def _enum(value: Any, allowed: tuple[str, ...], field: str, *, required: bool, default: str | None = None) -> str | None:
    if value is None or str(value).strip() == "":
        if required:
            raise PunchFieldError(f"{field} is required", 400, field)
        return default
    raw = str(value).strip().lower().replace(" ", "_").replace("-", "_")
    if raw not in allowed:
        raise PunchFieldError(f"invalid {field}", 400, field)
    return raw


def _title(raw: Any) -> str:
    title = str(raw or "").strip()
    if not title:
        raise PunchFieldError("title is required", 400, "title")
    if len(title) > 255:
        raise PunchFieldError("title must be at most 255 characters", 400, "title")
    return title


def _opt_str(raw: Any, maxlen: int) -> str | None:
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    return s[:maxlen]


def _opt_date(raw: Any, field: str) -> date | None:
    if raw is None or str(raw).strip() == "":
        return None
    try:
        return date.fromisoformat(str(raw).strip()[:10])
    except ValueError as exc:
        raise PunchFieldError(f"invalid {field}", 400, field) from exc


def _opt_float(raw: Any, field: str) -> float | None:
    if raw is None or raw == "":
        return None
    try:
        return float(raw)
    except (TypeError, ValueError) as exc:
        raise PunchFieldError(f"invalid {field}", 400, field) from exc


def _user_label(user: User | None) -> str:
    if user is None:
        return "FinishWorks Field"
    name = " ".join(x for x in (user.first_name, user.last_name) if x and str(x).strip()).strip()
    return name or (user.email or "FinishWorks Field")


def _audit(cu: CurrentUser, entity_id: uuid.UUID, action: str, message: str, changes: dict | None = None) -> None:
    db.session.add(
        AuditLog(
            user_id=cu.id,
            entity_type="punch_item",
            entity_id=entity_id,
            action=action,
            changes=changes,
            message=message,
        )
    )


def _next_number(project_id: uuid.UUID) -> int:
    current = db.session.scalar(
        select(func.coalesce(func.max(FieldPunchItem.number), 0)).where(FieldPunchItem.project_id == project_id)
    )
    return int(current or 0) + 1


def _photo_ids_from(data: Mapping[str, Any]) -> list[uuid.UUID]:
    raw: list[Any] = []
    if isinstance(data.get("photo_ids"), list):
        raw.extend(data.get("photo_ids") or [])
    if data.get("photo_id"):
        raw.append(data.get("photo_id"))
    photos = data.get("photos")
    if isinstance(photos, list):
        for entry in photos:
            if isinstance(entry, dict):
                raw.append(entry.get("id") or entry.get("photo_id"))
            else:
                raw.append(entry)
    ids: list[uuid.UUID] = []
    seen: set[uuid.UUID] = set()
    for item in raw:
        uid = _parse_uuid(item)
        if uid is None or uid in seen:
            continue
        seen.add(uid)
        ids.append(uid)
    return ids


def _link_photo_ids(row: FieldPunchItem, ids: list[uuid.UUID]) -> None:
    for pid in ids:
        photo = db.session.get(FieldPhoto, pid)
        if photo is None or photo.project_id != row.project_id:
            continue
        photo.punch_item_id = row.id
        if not photo.album:
            photo.album = "Punch"
        db.session.add(photo)


def _attach_inline_photos(row: FieldPunchItem, data: Mapping[str, Any], cu: CurrentUser) -> None:
    blobs: list[Any] = []
    for key in ("photos", "attachments", "images"):
        raw = data.get(key)
        if isinstance(raw, dict):
            blobs.append(raw)
        elif isinstance(raw, list):
            blobs.extend(raw)
    single = data.get("photo") or data.get("image") or data.get("data_url")
    if isinstance(single, (str, dict)):
        blobs.append(single)
    for i, entry in enumerate(blobs):
        mime = "image/jpeg"
        filename = f"punch-{i + 1}.jpg"
        payload = ""
        if isinstance(entry, str):
            payload = entry.strip()
        elif isinstance(entry, dict):
            payload = str(
                entry.get("data_url")
                or entry.get("data")
                or entry.get("base64")
                or entry.get("content")
                or ""
            ).strip()
            filename = str(entry.get("filename") or entry.get("name") or filename)[:300]
            if entry.get("mime_type"):
                mime = str(entry.get("mime_type")).strip() or mime
        if not payload.startswith("data:") and len(payload) < 80:
            continue
        if payload.startswith("data:") and "," in payload:
            header, payload = payload.split(",", 1)
            if ";" in header:
                mime = header[5:].split(";")[0].strip() or mime
        try:
            raw_bytes = base64.b64decode(payload, validate=False)
        except (ValueError, TypeError):
            continue
        if len(raw_bytes) < 32:
            continue
        upload = FileStorage(stream=io.BytesIO(raw_bytes), filename=filename, content_type=mime)
        create_field_photo(
            row.project_id,
            upload,
            {"album": "Punch", "punch_item_id": str(row.id)},
            cu,
        )


def _photo_looks_like_punch(photo: FieldPhoto, punch: FieldPunchItem) -> bool:
    album = (photo.album or "").strip().lower()
    caption = (photo.caption or "").strip().lower()
    loc = (photo.location_text or "").strip().lower()
    local = (punch.local_id or "").strip().lower()
    pid = str(punch.id).lower()
    title = (punch.title or "").strip().lower()
    if "punch" in album or album in {"camera", "photos", "crew punch"}:
        return True
    if local and (local in album or local in caption):
        return True
    if pid in album or pid in caption:
        return True
    if title and len(title) >= 8 and title in caption:
        return True
    if punch.location_text and (punch.location_text or "").strip().lower() and loc == (punch.location_text or "").strip().lower():
        return True
    if not album and not photo.daily_report_id and not photo.drawing_id:
        return True
    return False


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def claim_orphan_punch_photos(project_id: uuid.UUID) -> None:
    punches = list(
        db.session.scalars(
            select(FieldPunchItem).where(
                FieldPunchItem.project_id == project_id,
                FieldPunchItem.deleted_at.is_(None),
            )
        ).all()
    )
    if not punches:
        return
    by_local: dict[uuid.UUID, FieldPunchItem] = {}
    for punch in punches:
        local = _parse_uuid(punch.local_id)
        if local is not None:
            by_local[local] = punch
    claimed = False
    if by_local:
        misplaced = list(
            db.session.scalars(
                select(FieldPhoto).where(
                    FieldPhoto.project_id == project_id,
                    FieldPhoto.punch_item_id.in_(list(by_local.keys())),
                )
            ).all()
        )
        for photo in misplaced:
            punch = by_local.get(photo.punch_item_id)
            if punch is None or photo.punch_item_id == punch.id:
                continue
            photo.punch_item_id = punch.id
            if not photo.album:
                photo.album = "Punch"
            db.session.add(photo)
            claimed = True
    orphans = list(
        db.session.scalars(
            select(FieldPhoto).where(
                FieldPhoto.project_id == project_id,
                FieldPhoto.punch_item_id.is_(None),
                FieldPhoto.daily_report_id.is_(None),
            )
        ).all()
    )
    for photo in orphans:
        taken = _aware(photo.taken_at) or _aware(photo.created_at)
        best: FieldPunchItem | None = None
        best_delta: float | None = None
        for punch in punches:
            if not _photo_looks_like_punch(photo, punch):
                continue
            created = _aware(punch.created_at)
            if taken is None or created is None:
                if best is None:
                    best = punch
                continue
            delta = abs((taken - created).total_seconds())
            if delta > 14 * 24 * 3600:
                continue
            if best_delta is None or delta < best_delta:
                best = punch
                best_delta = delta
        if best is None:
            continue
        photo.punch_item_id = best.id
        if not photo.album:
            photo.album = "Punch"
        db.session.add(photo)
        claimed = True
    if claimed:
        db.session.commit()


def _photos_for_punch(row: FieldPunchItem) -> list[FieldPhoto]:
    local_uid = _parse_uuid(row.local_id)
    match = FieldPhoto.punch_item_id == row.id
    if local_uid is not None:
        match = or_(match, FieldPhoto.punch_item_id == local_uid)
    linked = list(
        db.session.scalars(
            select(FieldPhoto).where(match).order_by(FieldPhoto.created_at.asc())
        ).all()
    )
    if linked:
        return linked
    created = _aware(row.created_at)
    if created is None:
        return []
    nearby = list(
        db.session.scalars(
            select(FieldPhoto)
            .where(
                FieldPhoto.project_id == row.project_id,
                FieldPhoto.daily_report_id.is_(None),
            )
            .order_by(FieldPhoto.created_at.asc())
        ).all()
    )
    out: list[FieldPhoto] = []
    for photo in nearby:
        if photo.punch_item_id and photo.punch_item_id != row.id:
            continue
        taken = _aware(photo.taken_at) or _aware(photo.created_at)
        if taken is None:
            continue
        delta = abs((taken - created).total_seconds())
        album = (photo.album or "").strip().lower()
        punchy = "punch" in album or album in {"camera", "photos", "crew punch"}
        if punchy and delta <= 14 * 24 * 3600:
            out.append(photo)
        elif delta <= 4 * 3600:
            out.append(photo)
        if len(out) >= 6:
            break
    return out


def punch_item_public(row: FieldPunchItem, *, include_photo_data: bool = False) -> dict[str, Any]:
    photos = _photos_for_punch(row)
    dists = list(
        db.session.scalars(
            select(PunchDistribution)
            .where(PunchDistribution.punch_item_id == row.id)
            .order_by(PunchDistribution.created_at.asc())
        ).all()
    )
    assignee = db.session.get(User, row.assignee_user_id) if row.assignee_user_id else None
    return {
        "id": str(row.id),
        "local_id": row.local_id,
        "project_id": str(row.project_id),
        "list": row.list,
        "number": row.number,
        "title": row.title,
        "description": row.description,
        "status": row.status,
        "type": row.type,
        "priority": row.priority,
        "location_text": row.location_text,
        "location_id": str(row.location_id) if row.location_id else None,
        "trade": row.trade,
        "assignee_user_id": str(row.assignee_user_id) if row.assignee_user_id else None,
        "assignee_name": _user_label(assignee) if assignee else None,
        "due_on": row.due_on.isoformat() if row.due_on else None,
        "schedule_impact": row.schedule_impact,
        "schedule_note": row.schedule_note,
        "cost_impact": row.cost_impact,
        "cost_note": row.cost_note,
        "drawing_id": str(row.drawing_id) if row.drawing_id else None,
        "revision_id": row.revision_id,
        "pin_x": row.pin_x,
        "pin_y": row.pin_y,
        "source": row.source,
        "external_id": row.external_id,
        "external_type": row.external_type,
        "gc_manager": row.gc_manager,
        "gc_approver": row.gc_approver,
        "notify_on_save": bool(row.notify_on_save),
        "last_notified_at": iso(row.last_notified_at) if row.last_notified_at else None,
        "created_by_id": str(row.created_by_id) if row.created_by_id else None,
        "updated_at": iso(row.updated_at),
        "created_at": iso(row.created_at),
        "photos": [field_photo_public(p, include_data=include_photo_data) for p in photos],
        "distribution": [
            {
                "id": str(d.id),
                "local_id": d.local_id,
                "contact_id": str(d.contact_id) if d.contact_id else None,
                "user_id": str(d.user_id) if d.user_id else None,
                "email": d.email,
                "name": d.name,
                "role": d.role,
                "notified_at": iso(d.notified_at) if d.notified_at else None,
            }
            for d in dists
        ],
    }


def list_punch_items(
    project_id: uuid.UUID,
    cu: CurrentUser,
    *,
    list_name: str | None,
    status: str | None,
) -> dict[str, Any]:
    _require_project_access(cu, project_id)
    claim_orphan_punch_photos(project_id)
    stmt = select(FieldPunchItem).where(
        FieldPunchItem.project_id == project_id,
        FieldPunchItem.deleted_at.is_(None),
    )
    if list_name and list_name != "all":
        lst = _enum(list_name, PUNCH_LISTS, "list", required=True)
        stmt = stmt.where(FieldPunchItem.list == lst)
    if status:
        st = _enum(status, PUNCH_STATUSES, "status", required=True)
        stmt = stmt.where(FieldPunchItem.status == st)
    rows = list(db.session.scalars(stmt.order_by(FieldPunchItem.updated_at.desc())).all())
    ours_open = sum(1 for r in rows if r.list == "ours" and r.status in PUNCH_OPEN_STATUSES)
    gc_open = sum(1 for r in rows if r.list == "gc" and r.status in PUNCH_OPEN_STATUSES)
    if list_name in (None, "", "all"):
        ours_open = db.session.scalar(
            select(func.count()).select_from(FieldPunchItem).where(
                FieldPunchItem.project_id == project_id,
                FieldPunchItem.deleted_at.is_(None),
                FieldPunchItem.list == "ours",
                FieldPunchItem.status.in_(PUNCH_OPEN_STATUSES),
            )
        ) or 0
        gc_open = db.session.scalar(
            select(func.count()).select_from(FieldPunchItem).where(
                FieldPunchItem.project_id == project_id,
                FieldPunchItem.deleted_at.is_(None),
                FieldPunchItem.list == "gc",
                FieldPunchItem.status.in_(PUNCH_OPEN_STATUSES),
            )
        ) or 0
    return {
        "items": [punch_item_public(r) for r in rows],
        "open_count": int(ours_open),
        "ours_open": int(ours_open),
        "gc_open": int(gc_open),
        "entity": "punch_items",
    }


def _replace_distribution(row: FieldPunchItem, items: Any) -> None:
    if items is None:
        return
    if not isinstance(items, list):
        raise PunchFieldError("distribution must be a list", 400, "distribution")
    existing = list(
        db.session.scalars(select(PunchDistribution).where(PunchDistribution.punch_item_id == row.id)).all()
    )
    keep: set[int] = set()
    for entry in items:
        if not isinstance(entry, dict):
            continue
        email = str(entry.get("email") or "").strip().lower()
        contact_id = _parse_uuid(entry.get("contact_id"))
        user_id = _parse_uuid(entry.get("user_id"))
        if contact_id:
            contact = db.session.get(Contact, contact_id)
            if contact is None:
                raise PunchFieldError("unknown contact_id", 400, "distribution")
            if not email:
                email = (contact.email or "").strip().lower()
            name = _opt_str(entry.get("name"), 200) or " ".join(
                x for x in (contact.first_name, contact.last_name) if x
            ).strip()
        else:
            name = _opt_str(entry.get("name"), 200)
        if not email:
            continue
        local_id = _opt_str(entry.get("local_id"), 64)
        found = None
        if local_id:
            found = next((d for d in existing if d.local_id == local_id), None)
        if found is None:
            found = next((d for d in existing if (d.email or "").lower() == email), None)
        if found is None:
            found = PunchDistribution(punch_item_id=row.id, email=email)
            db.session.add(found)
            existing.append(found)
        found.local_id = local_id or found.local_id
        found.email = email
        found.contact_id = contact_id
        found.user_id = user_id
        found.name = name
        found.role = _opt_str(entry.get("role"), 80)
        keep.add(id(found))
    for d in existing:
        if id(d) in keep:
            continue
        if d.notified_at is not None:
            continue
        db.session.delete(d)


def _apply_ours_fields(row: FieldPunchItem, data: Mapping[str, Any], *, creating: bool) -> None:
    if "title" in data or creating:
        row.title = _title(data.get("title") if "title" in data else row.title)
    if "description" in data or creating:
        row.description = _opt_str(data.get("description"), 8000)
    if "type" in data or creating:
        row.type = _enum(data.get("type"), PUNCH_TYPES, "type", required=False)
    if "priority" in data or creating:
        row.priority = _enum(data.get("priority"), PUNCH_PRIORITIES, "priority", required=False, default="normal") or "normal"
    if "location_text" in data or creating:
        row.location_text = _opt_str(data.get("location_text"), 255)
    if "location_id" in data or creating:
        loc_id = _parse_uuid(data.get("location_id"))
        if data.get("location_id") and loc_id is None:
            raise PunchFieldError("invalid location_id", 400, "location_id")
        if loc_id is not None:
            loc = db.session.get(Location, loc_id)
            if loc is None or loc.project_id != row.project_id:
                raise PunchFieldError("location not found", 400, "location_id")
        row.location_id = loc_id
    if "trade" in data or creating:
        trade = _opt_str(data.get("trade"), 80)
        if trade:
            trade = trade.lower().replace(" ", "_")
            if trade not in PUNCH_TRADES:
                raise PunchFieldError("invalid trade", 400, "trade")
        row.trade = trade
    if "due_on" in data or creating:
        row.due_on = _opt_date(data.get("due_on"), "due_on")
    if "schedule_impact" in data or creating:
        row.schedule_impact = _enum(
            data.get("schedule_impact"), PUNCH_IMPACTS, "schedule_impact", required=False, default="none"
        ) or "none"
    if "schedule_note" in data or creating:
        row.schedule_note = _opt_str(data.get("schedule_note"), 500)
    if "cost_impact" in data or creating:
        row.cost_impact = _enum(data.get("cost_impact"), PUNCH_IMPACTS, "cost_impact", required=False, default="none") or "none"
    if "cost_note" in data or creating:
        row.cost_note = _opt_str(data.get("cost_note"), 500)
    if "drawing_id" in data or creating:
        did = _parse_uuid(data.get("drawing_id"))
        if data.get("drawing_id") and did is None:
            raise PunchFieldError("invalid drawing_id", 400, "drawing_id")
        if did is not None and db.session.get(Drawing, did) is None:
            raise PunchFieldError("drawing not found", 400, "drawing_id")
        row.drawing_id = did
    if "revision_id" in data or creating:
        row.revision_id = _opt_str(data.get("revision_id"), 80)
    if "pin_x" in data or creating:
        row.pin_x = _opt_float(data.get("pin_x"), "pin_x")
    if "pin_y" in data or creating:
        row.pin_y = _opt_float(data.get("pin_y"), "pin_y")
    if "notify_on_save" in data or creating:
        row.notify_on_save = _as_bool(data.get("notify_on_save"))


def _apply_assignee(row: FieldPunchItem, data: Mapping[str, Any], *, creating: bool) -> None:
    if "assignee_user_id" not in data and not creating:
        return
    raw = data.get("assignee_user_id")
    uid = _parse_uuid(raw)
    if raw and uid is None:
        raise PunchFieldError("invalid assignee_user_id", 400, "assignee_user_id")
    if uid is not None and db.session.get(User, uid) is None:
        raise PunchFieldError("assignee not found", 400, "assignee_user_id")
    row.assignee_user_id = uid


def _with_location_alias(data: Mapping[str, Any]) -> dict[str, Any]:
    body = dict(data)
    if not str(body.get("location_text") or "").strip() and body.get("room") is not None:
        body["location_text"] = body.get("room")
    return body


def create_or_get_punch_item(project_id: uuid.UUID, data: Mapping[str, Any], cu: CurrentUser) -> tuple[dict[str, Any], int]:
    _require_project_access(cu, project_id)
    data = _with_location_alias(data)
    local_id = str(data.get("local_id") or "").strip() or str(uuid.uuid4())
    existing = db.session.scalar(select(FieldPunchItem).where(FieldPunchItem.local_id == local_id))
    if existing is not None:
        if existing.project_id != project_id:
            raise PunchFieldError("local_id already used", 409, "local_id")
        _link_photo_ids(existing, _photo_ids_from(data))
        _attach_inline_photos(existing, data, cu)
        db.session.commit()
        claim_orphan_punch_photos(existing.project_id)
        return {"item": punch_item_public(existing), "entity": "punch_item"}, 200

    list_name = _enum(data.get("list") or "ours", PUNCH_LISTS, "list", required=True) or "ours"
    if list_name == "gc":
        raise PunchFieldError(GC_CREATE_MSG, 403, "list")

    row = FieldPunchItem(
        local_id=local_id[:64],
        project_id=project_id,
        list="ours",
        number=_next_number(project_id),
        title=_title(data.get("title")),
        status=_enum(data.get("status") or "open", PUNCH_STATUSES, "status", required=False, default="open") or "open",
        priority="normal",
        schedule_impact="none",
        cost_impact="none",
        source=_enum(data.get("source") or "internal", PUNCH_SOURCES, "source", required=False, default="internal")
        or "internal",
        created_by_id=cu.id,
        assignee_user_id=cu.id,
    )
    _apply_ours_fields(row, data, creating=True)
    _apply_assignee(row, data, creating=True)
    if row.assignee_user_id is None:
        row.assignee_user_id = cu.id
    db.session.add(row)
    db.session.flush()
    _replace_distribution(row, data.get("distribution"))
    _link_photo_ids(row, _photo_ids_from(data))
    _attach_inline_photos(row, data, cu)
    _audit(cu, row.id, "create", f"Created punch item {row.number}: {row.title}")
    should_notify = _as_bool(data.get("notify_on_save"))
    if should_notify:
        send_punch_notify(row, cu, persist=False)
    db.session.commit()
    claim_orphan_punch_photos(row.project_id)
    db.session.refresh(row)
    return {"item": punch_item_public(row), "entity": "punch_item"}, 201


def _get_item(item_id: uuid.UUID, cu: CurrentUser) -> FieldPunchItem:
    row = db.session.get(FieldPunchItem, item_id)
    if row is None or row.deleted_at is not None:
        raise PunchFieldError("punch item not found", 404)
    _require_project_access(cu, row.project_id)
    return row


def get_punch_item(item_id: uuid.UUID, cu: CurrentUser) -> dict[str, Any]:
    row = _get_item(item_id, cu)
    claim_orphan_punch_photos(row.project_id)
    return {"item": punch_item_public(row, include_photo_data=True), "entity": "punch_item"}


def patch_punch_item(item_id: uuid.UUID, data: Mapping[str, Any], cu: CurrentUser) -> dict[str, Any]:
    row = _get_item(item_id, cu)
    data = _with_location_alias(data)
    if row.list == "gc":
        _apply_assignee(row, data, creating=False)
        if "status" in data:
            _set_status(row, data.get("status"), cu)
        if "distribution" in data:
            _replace_distribution(row, data.get("distribution"))
    else:
        if row.status == "closed" and "status" not in data:
            raise PunchFieldError("closed items can only be reopened", 400, "status")
        _apply_ours_fields(row, data, creating=False)
        _apply_assignee(row, data, creating=False)
        if "status" in data:
            _set_status(row, data.get("status"), cu)
        if "distribution" in data:
            _replace_distribution(row, data.get("distribution"))
        if "notify_on_save" in data and data.get("notify_on_save"):
            send_punch_notify(row, cu, persist=False)
    _link_photo_ids(row, _photo_ids_from(data))
    _attach_inline_photos(row, data, cu)
    _audit(cu, row.id, "update", f"Updated punch item {row.number}")
    db.session.add(row)
    db.session.commit()
    db.session.refresh(row)
    return {"item": punch_item_public(row), "entity": "punch_item"}


def _set_status(row: FieldPunchItem, raw: Any, cu: CurrentUser) -> None:
    status = _enum(raw, PUNCH_STATUSES, "status", required=True)
    if status == row.status:
        return
    row.status = status or row.status
    row.status_changed_by_id = cu.id
    _audit(cu, row.id, "status", f"Status → {row.status}")


def set_punch_status(item_id: uuid.UUID, data: Mapping[str, Any], cu: CurrentUser) -> dict[str, Any]:
    row = _get_item(item_id, cu)
    _set_status(row, data.get("status"), cu)
    db.session.add(row)
    db.session.commit()
    db.session.refresh(row)
    return {"item": punch_item_public(row), "entity": "punch_item"}


def delete_punch_item(item_id: uuid.UUID, cu: CurrentUser) -> dict[str, Any]:
    row = _get_item(item_id, cu)
    row.deleted_at = _now()
    _audit(cu, row.id, "delete", f"Deleted punch item {row.number}: {row.title}")
    db.session.add(row)
    db.session.commit()
    return {"ok": True, "id": str(row.id), "entity": "punch_item"}


def attach_punch_photo(item_id: uuid.UUID, file, form: Mapping[str, Any], cu: CurrentUser) -> dict[str, Any]:
    row = _get_item(item_id, cu)
    photo_id = _parse_uuid(form.get("photo_id") or form.get("id"))
    if photo_id is not None:
        photo = db.session.get(FieldPhoto, photo_id)
        if photo is None or photo.project_id != row.project_id:
            raise PunchFieldError("photo not found", 404, "photo_id")
        photo.punch_item_id = row.id
        if not photo.album:
            photo.album = "Punch"
        db.session.add(photo)
        db.session.commit()
        return {"item": field_photo_public(photo), "entity": "field_photo"}
    upload = file if file is not None and getattr(file, "filename", None) else first_upload_file()
    merged = dict(form)
    merged.setdefault("album", "Punch")
    merged["punch_item_id"] = str(row.id)
    created = create_field_photo(row.project_id, upload, merged, cu)
    pid = _parse_uuid((created.get("item") or {}).get("id"))
    if pid:
        photo = db.session.get(FieldPhoto, pid)
        if photo is not None:
            photo.punch_item_id = row.id
            photo.album = photo.album or "Punch"
            db.session.add(photo)
            db.session.commit()
            db.session.refresh(photo)
            return {"item": field_photo_public(photo), "entity": "field_photo"}
    return created


def send_punch_notify(
    row: FieldPunchItem,
    cu: CurrentUser,
    *,
    persist: bool = True,
    contact_ids: set[str] | None = None,
) -> dict[str, Any]:
    dists = list(
        db.session.scalars(select(PunchDistribution).where(PunchDistribution.punch_item_id == row.id)).all()
    )
    if contact_ids:
        dists = [d for d in dists if d.contact_id and str(d.contact_id) in contact_ids]
    if not dists:
        return {"sent": 0, "item": punch_item_public(row), "entity": "punch_notify"}
    project = db.session.get(Project, row.project_id)
    photos = list(
        db.session.scalars(
            select(FieldPhoto).where(FieldPhoto.punch_item_id == row.id).order_by(FieldPhoto.created_at.asc()).limit(3)
        ).all()
    )
    sender = _user_label(cu.user)
    sent_at = _now()
    recipients: list[dict[str, Any]] = []
    for dist in dists:
        ctx = {
            "job_name": project.name if project else "",
            "job_number": (project.number if project else None) or "",
            "title": row.title,
            "number": row.number,
            "location": row.location_text or "",
            "trade": row.trade or "",
            "type": row.type or "",
            "priority": row.priority,
            "schedule_impact": row.schedule_impact,
            "schedule_note": row.schedule_note or "",
            "cost_impact": row.cost_impact,
            "cost_note": row.cost_note or "",
            "photo_urls": [field_photo_public(p).get("file_url") for p in photos],
            "photos_pending": len(photos) == 0,
            "sent_by": sender,
            "sent_at": sent_at.isoformat(),
            "web_hint": "Ask USIS office" if project is None else f"{project.name} — {row.title}. Ask USIS office.",
        }
        html = render_template("email/punch_notify.html", **ctx)
        text = render_template("email/punch_notify.txt", **ctx)
        subject = f"Punch item #{row.number or ''} — {row.title}"[:200]
        result = send_html_notification_email(
            to=dist.email,
            subject=subject,
            body=text,
            html_body=html,
        )
        dist.notified_at = sent_at
        db.session.add(dist)
        recipients.append(
            {
                "email": dist.email,
                "contact_id": str(dist.contact_id) if dist.contact_id else None,
                "sent": bool(result.get("sent") or result.get("dry_run")),
                "dry_run": bool(result.get("dry_run")),
                "error": result.get("error"),
            }
        )
    log = PunchNotifyLog(
        punch_item_id=row.id,
        sent_at=sent_at,
        recipients_json=recipients,
        channel="email",
        sent_by_id=cu.id,
    )
    db.session.add(log)
    row.last_notified_at = sent_at
    db.session.add(row)
    _audit(cu, row.id, "notify", f"Notified {len(dists)} contact(s)", {"recipients": recipients})
    if persist:
        db.session.commit()
        db.session.refresh(row)
    return {"sent": len(dists), "item": punch_item_public(row), "entity": "punch_notify"}


def notify_punch_item(item_id: uuid.UUID, data: Mapping[str, Any], cu: CurrentUser) -> dict[str, Any]:
    row = _get_item(item_id, cu)
    ids = data.get("distribution_contact_ids")
    wanted = {str(x) for x in ids} if isinstance(ids, list) and ids else None
    return send_punch_notify(row, cu, persist=True, contact_ids=wanted)


def list_field_directory(project_id: uuid.UUID, cu: CurrentUser) -> dict[str, Any]:
    _require_project_access(cu, project_id)
    items: list[dict[str, Any]] = []
    seen_emails: set[str] = set()
    links = list(
        db.session.scalars(select(ProjectDirectoryCompany).where(ProjectDirectoryCompany.project_id == project_id)).all()
    )
    for link in links:
        contacts = list(
            db.session.scalars(
                select(Contact).where(Contact.company_id == link.company_id).order_by(Contact.is_primary.desc())
            ).all()
        )
        for c in contacts:
            email = (c.email or "").strip().lower()
            if not email or email in seen_emails:
                continue
            seen_emails.add(email)
            name = " ".join(x for x in (c.first_name, c.last_name) if x).strip()
            items.append(
                {
                    "contact_id": str(c.id),
                    "user_id": None,
                    "email": email,
                    "name": name,
                    "role": link.directory_role,
                    "company_id": str(link.company_id),
                    "title": c.title,
                }
            )
    members = list(db.session.scalars(select(ProjectMember).where(ProjectMember.project_id == project_id)).all())
    for m in members:
        user = db.session.get(User, m.user_id)
        if user is None or not user.email:
            continue
        email = user.email.strip().lower()
        if email in seen_emails:
            continue
        seen_emails.add(email)
        items.append(
            {
                "contact_id": None,
                "user_id": str(user.id),
                "email": email,
                "name": _user_label(user),
                "role": m.member_role or "project_member",
                "company_id": None,
                "title": None,
            }
        )
    return {"items": items, "entity": "field_directory"}


def list_field_locations(project_id: uuid.UUID, cu: CurrentUser) -> dict[str, Any]:
    _require_project_access(cu, project_id)
    rows = list(
        db.session.scalars(
            select(Location)
            .where(Location.project_id == project_id, Location.is_active.is_(True))
            .order_by(Location.path)
        ).all()
    )
    return {
        "items": [{"id": str(r.id), "name": r.name, "path": r.path} for r in rows],
        "entity": "field_locations",
    }
