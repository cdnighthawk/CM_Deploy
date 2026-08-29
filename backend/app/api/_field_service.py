"""Daily reports and field photos for the FinishWorks field app."""
from __future__ import annotations

import copy
import uuid
from datetime import date, datetime, timezone
from typing import Any, Mapping

from sqlalchemy import select

from ..extensions import db
from ..models import DailyReport, Drawing, FieldPhoto
from ..models.field_ops import DAILY_REPORT_STATUSES, DEFAULT_DAILY_SECTIONS
from ..services.object_storage import UploadCategory, save_upload, send_stored_file, stored_exists
from ._perms import CurrentUser
from ._serializers import iso


class FieldApiError(Exception):
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


def _parse_dt(raw: Any) -> datetime | None:
    if raw is None or raw == "":
        return None
    s = str(raw).strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _parse_uuid(raw: Any) -> uuid.UUID | None:
    if raw is None or raw == "":
        return None
    try:
        return uuid.UUID(str(raw).strip())
    except (TypeError, ValueError):
        return None


def _num_or_none(v: Any) -> float | None:
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def empty_sections() -> dict[str, Any]:
    return copy.deepcopy(DEFAULT_DAILY_SECTIONS)


def merge_sections(existing: Mapping[str, Any] | None, incoming: Mapping[str, Any] | None) -> dict[str, Any]:
    """Last-write-wins on top-level section keys. Never drops unknown keys already stored."""
    out = empty_sections()
    if isinstance(existing, Mapping):
        for key, val in existing.items():
            out[str(key)] = copy.deepcopy(val)
    if isinstance(incoming, Mapping):
        for key, val in incoming.items():
            out[str(key)] = copy.deepcopy(val)
    return out


def _require_project_access(cu: CurrentUser, project_id: uuid.UUID) -> None:
    from ..permissions.project_scope import user_can_access_project

    if not user_can_access_project(cu, project_id):
        raise FieldApiError("project not found", 404)


def _can_edit_completed(cu: CurrentUser) -> bool:
    if cu.is_dev_admin:
        return True
    user = cu.user
    if user is not None and getattr(user, "is_superuser", False):
        return True
    return cu.has_role("admin")


def daily_report_public(row: DailyReport) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "project_id": str(row.project_id),
        "date": row.report_date.isoformat(),
        "status": row.status,
        "sections": row.sections if isinstance(row.sections, dict) else empty_sections(),
        "updated_at": iso(row.updated_at),
        "completed_at": iso(row.completed_at) if row.completed_at else None,
        "created_at": iso(row.created_at),
    }


def get_or_create_daily_report(project_id: uuid.UUID, report_date: date, cu: CurrentUser) -> dict[str, Any]:
    row = db.session.scalar(
        select(DailyReport).where(
            DailyReport.project_id == project_id,
            DailyReport.report_date == report_date,
        )
    )
    if row is None:
        row = DailyReport(
            project_id=project_id,
            report_date=report_date,
            status="draft",
            sections=empty_sections(),
            created_by_user_id=cu.id,
        )
        db.session.add(row)
        db.session.commit()
        db.session.refresh(row)
    return {"item": daily_report_public(row), "entity": "daily_report"}


def put_daily_report(report_id: uuid.UUID, data: Mapping[str, Any], cu: CurrentUser) -> dict[str, Any]:
    row = db.session.get(DailyReport, report_id)
    if row is None:
        raise FieldApiError("daily report not found", 404)
    _require_project_access(cu, row.project_id)
    if row.status == "complete" and not _can_edit_completed(cu):
        raise FieldApiError("daily report is complete and locked", 403)

    if "sections" in data:
        incoming = data.get("sections")
        if incoming is not None and not isinstance(incoming, Mapping):
            raise FieldApiError("sections must be an object", 400)
        row.sections = merge_sections(row.sections, incoming if isinstance(incoming, Mapping) else None)
        # Flag JSONB mutation for SQLAlchemy.
        from sqlalchemy.orm.attributes import flag_modified

        flag_modified(row, "sections")

    if "status" in data and data.get("status") is not None:
        status = str(data.get("status")).strip().lower()
        if status not in DAILY_REPORT_STATUSES:
            raise FieldApiError("status must be draft or complete", 400)
        row.status = status
        if status == "complete" and row.completed_at is None:
            row.completed_at = datetime.now(timezone.utc)
        if status == "draft":
            row.completed_at = None

    db.session.add(row)
    db.session.commit()
    db.session.refresh(row)
    return {"item": daily_report_public(row), "entity": "daily_report"}


def field_photo_object_name(photo_id: uuid.UUID) -> str:
    return f"{photo_id}.jpg"


def field_photo_public(row: FieldPhoto) -> dict[str, Any]:
    lat = row.lat
    lon = row.lon
    return {
        "id": str(row.id),
        "project_id": str(row.project_id),
        "file_url": f"/api/v1/photos/{row.id}/file",
        "taken_at": iso(row.taken_at) if row.taken_at else None,
        "lat": float(lat) if lat is not None else None,
        "lon": float(lon) if lon is not None else None,
        "caption": row.caption or "",
        "location_text": row.location_text or "",
        "drawing_id": str(row.drawing_id) if row.drawing_id else None,
        "daily_report_id": str(row.daily_report_id) if row.daily_report_id else None,
        "created_at": iso(row.created_at),
    }


def list_field_photos(project_id: uuid.UUID) -> dict[str, Any]:
    rows = list(
        db.session.scalars(
            select(FieldPhoto).where(FieldPhoto.project_id == project_id).order_by(FieldPhoto.created_at.desc())
        ).all()
    )
    return {"items": [field_photo_public(r) for r in rows], "total": len(rows), "entity": "field_photos"}


def create_field_photo(
    project_id: uuid.UUID,
    file,
    form: Mapping[str, Any],
    cu: CurrentUser,
) -> dict[str, Any]:
    if file is None or not getattr(file, "filename", None):
        raise FieldApiError("missing file field (multipart form-data)", 400)

    drawing_id = _parse_uuid(form.get("drawing_id"))
    if form.get("drawing_id") and drawing_id is None:
        raise FieldApiError("invalid drawing_id", 400)
    if drawing_id is not None:
        drawing = db.session.get(Drawing, drawing_id)
        if drawing is None:
            raise FieldApiError("drawing not found", 404)

    report_id = _parse_uuid(form.get("daily_report_id"))
    if form.get("daily_report_id") and report_id is None:
        raise FieldApiError("invalid daily_report_id", 400)
    if report_id is not None:
        report = db.session.get(DailyReport, report_id)
        if report is None or report.project_id != project_id:
            raise FieldApiError("daily report not found", 404)

    filename = (getattr(file, "filename", None) or "photo.jpg")[:300]
    mime = (getattr(file, "mimetype", None) or "image/jpeg")[:120]
    row = FieldPhoto(
        project_id=project_id,
        daily_report_id=report_id,
        drawing_id=drawing_id,
        uploaded_by_user_id=cu.id,
        caption=(str(form.get("caption") or "").strip() or None),
        location_text=(str(form.get("location_text") or "").strip()[:300] or None),
        taken_at=_parse_dt(form.get("taken_at")),
        lat=_num_or_none(form.get("lat")),
        lon=_num_or_none(form.get("lon")),
        original_filename=filename,
        mime_type=mime,
    )
    db.session.add(row)
    db.session.flush()
    save_upload(UploadCategory.FIELD_PHOTOS, field_photo_object_name(row.id), file)
    db.session.commit()
    db.session.refresh(row)

    if report_id is not None:
        report = db.session.get(DailyReport, report_id)
        if report is not None and report.status != "complete":
            sections = merge_sections(report.sections, None)
            photos = sections.get("photos")
            if not isinstance(photos, list):
                photos = []
            pid = str(row.id)
            if pid not in photos:
                photos.append(pid)
            sections["photos"] = photos
            report.sections = sections
            from sqlalchemy.orm.attributes import flag_modified

            flag_modified(report, "sections")
            db.session.add(report)
            db.session.commit()

    return {"item": field_photo_public(row), "entity": "field_photo"}


def update_field_photo(photo_id: uuid.UUID, data: Mapping[str, Any], cu: CurrentUser) -> dict[str, Any]:
    """TODO: used by field apps to link a photo after capture (caption/location/drawing/report)."""
    row = db.session.get(FieldPhoto, photo_id)
    if row is None:
        raise FieldApiError("photo not found", 404)
    _require_project_access(cu, row.project_id)
    if "caption" in data:
        row.caption = (str(data.get("caption") or "").strip() or None)
    if "location_text" in data:
        text = str(data.get("location_text") or "").strip()[:300]
        row.location_text = text or None
    if "drawing_id" in data:
        drawing_id = _parse_uuid(data.get("drawing_id"))
        if data.get("drawing_id") and drawing_id is None:
            raise FieldApiError("invalid drawing_id", 400)
        if drawing_id is not None and db.session.get(Drawing, drawing_id) is None:
            raise FieldApiError("drawing not found", 404)
        row.drawing_id = drawing_id
    if "daily_report_id" in data:
        report_id = _parse_uuid(data.get("daily_report_id"))
        if data.get("daily_report_id") and report_id is None:
            raise FieldApiError("invalid daily_report_id", 400)
        if report_id is not None:
            report = db.session.get(DailyReport, report_id)
            if report is None or report.project_id != row.project_id:
                raise FieldApiError("daily report not found", 404)
        row.daily_report_id = report_id
    db.session.add(row)
    db.session.commit()
    db.session.refresh(row)
    return {"item": field_photo_public(row), "entity": "field_photo"}


def send_field_photo_file(photo_id: uuid.UUID, cu: CurrentUser):
    row = db.session.get(FieldPhoto, photo_id)
    if row is None:
        raise FieldApiError("photo not found", 404)
    _require_project_access(cu, row.project_id)
    name = field_photo_object_name(photo_id)
    if not stored_exists(UploadCategory.FIELD_PHOTOS, name):
        raise FieldApiError("file not found on server", 404)
    dl = (row.original_filename or "photo.jpg").replace('"', "")[:200]
    mime = (row.mime_type or "image/jpeg").strip() or "image/jpeg"
    resp = send_stored_file(UploadCategory.FIELD_PHOTOS, name, mimetype=mime, download_name=dl)
    if resp is None:
        raise FieldApiError("file not found on server", 404)
    return resp


# Used by unit tests without a Flask app context.
def merge_report_sections_for_test(existing: dict, incoming: dict) -> dict:
    return merge_sections(existing, incoming)
