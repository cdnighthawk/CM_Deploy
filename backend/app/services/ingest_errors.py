"""Record and list ingest failures so a bulk run can be reviewed after it dies."""
from __future__ import annotations

import traceback
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.exc import ProgrammingError, SQLAlchemyError

from ..extensions import db
from ..models.ingest_error import IngestErrorEvent
from .ingest import as_uuid, text


def _exc_detail(exc: BaseException | None) -> dict[str, Any]:
    if exc is None:
        return {}
    return {
        "exc_type": type(exc).__name__,
        "exc": str(exc)[:2000],
        "traceback": "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))[-4000:],
    }


def public(row: IngestErrorEvent) -> dict[str, Any]:
    detail = row.detail if isinstance(row.detail, dict) else {}
    return {
        "id": str(row.id),
        "created_at": row.created_at.isoformat() if row.created_at is not None else None,
        "batch_id": row.batch_id or None,
        "source": row.source,
        "relative_path": row.relative_path or "",
        "filename": row.filename or "",
        "kind": row.kind or "",
        "project_id": str(row.project_id) if row.project_id else None,
        "project_number": row.project_number or None,
        "http_status": row.http_status,
        "message": row.message,
        "detail": {k: detail[k] for k in ("exc_type", "exc") if k in detail},
        "status": row.status,
        "resolved_at": row.resolved_at.isoformat() if row.resolved_at is not None else None,
        "resolved_note": row.resolved_note or None,
        "actor_email": row.actor_email or None,
        "entity": "ingest_error",
    }


def _filename_of(relative_path: str, filename: str) -> str:
    name = text(filename)
    if name:
        return name[:500]
    rel = text(relative_path).replace("\\", "/")
    return (rel.split("/")[-1] if rel else "")[:500]


def record_upload_failure(
    *,
    source: str,
    metadata: dict[str, Any] | None,
    kind: str,
    message: str,
    http_status: int,
    exc: BaseException | None = None,
    actor_email: str | None = None,
) -> IngestErrorEvent | None:
    meta = metadata if isinstance(metadata, dict) else {}
    rel = text(
        meta.get("relative_path")
        or meta.get("relativePath")
        or meta.get("source_path")
        or meta.get("source_id")
        or meta.get("filename")
        or meta.get("file_name")
        or ""
    ).replace("\\", "/")
    project_id = as_uuid(meta.get("project_id") or meta.get("job_id") or meta.get("id"))
    batch_id = text(meta.get("batch_id") or meta.get("batchId"))[:64] or None
    return record_failure(
        source=source,
        message=message,
        relative_path=rel,
        filename=text(meta.get("filename") or meta.get("file_name")),
        kind=kind,
        batch_id=batch_id,
        project_id=project_id,
        project_number=text(meta.get("project_number") or meta.get("folder_name"))[:40],
        http_status=http_status,
        detail=_exc_detail(exc),
        actor_email=actor_email,
    )


def record_failure(
    *,
    source: str = "mass_ingest",
    message: str,
    relative_path: str = "",
    filename: str = "",
    kind: str = "",
    batch_id: str | None = None,
    project_id: uuid.UUID | None = None,
    project_number: str = "",
    http_status: int | None = None,
    detail: dict[str, Any] | None = None,
    actor_email: str | None = None,
) -> IngestErrorEvent | None:
    msg = text(message)[:4000] or "ingest failed"
    rel = text(relative_path).replace("\\", "/")
    batch = text(batch_id)[:64] or None
    try:
        existing = None
        if batch and rel:
            existing = db.session.scalars(
                select(IngestErrorEvent)
                .where(
                    IngestErrorEvent.batch_id == batch,
                    IngestErrorEvent.relative_path == rel,
                    IngestErrorEvent.status == "open",
                )
                .order_by(IngestErrorEvent.created_at.desc())
            ).first()
        row = existing or IngestErrorEvent()
        row.batch_id = batch
        row.source = (text(source) or "mass_ingest")[:40]
        row.relative_path = rel
        row.filename = _filename_of(rel, filename)
        row.kind = (text(kind) or "")[:20]
        row.project_id = project_id
        row.project_number = text(project_number)[:40] or None
        row.http_status = http_status
        row.message = msg
        row.detail = detail if isinstance(detail, dict) else None
        row.status = "open"
        row.actor_email = text(actor_email)[:255] or None
        if existing is None:
            db.session.add(row)
        db.session.flush()
        return row
    except (ProgrammingError, SQLAlchemyError):
        db.session.rollback()
        return None


def list_failures(
    *,
    batch_id: str | None = None,
    status: str | None = None,
    q: str | None = None,
    limit: int = 200,
    offset: int = 0,
) -> dict[str, Any]:
    limit = max(1, min(int(limit or 200), 500))
    offset = max(0, int(offset or 0))
    filters = []
    batch = text(batch_id)
    if batch:
        filters.append(IngestErrorEvent.batch_id == batch[:64])
    status_key = text(status).lower()
    if status_key in {"open", "resolved"}:
        filters.append(IngestErrorEvent.status == status_key)
    needle = text(q)
    if needle:
        like = f"%{needle}%"
        filters.append(
            or_(
                IngestErrorEvent.relative_path.ilike(like),
                IngestErrorEvent.filename.ilike(like),
                IngestErrorEvent.message.ilike(like),
                IngestErrorEvent.project_number.ilike(like),
            )
        )
    where = filters or [True]
    total = db.session.scalar(select(func.count()).select_from(IngestErrorEvent).where(*where)) or 0
    open_q = select(func.count()).select_from(IngestErrorEvent).where(IngestErrorEvent.status == "open")
    if batch:
        open_q = open_q.where(IngestErrorEvent.batch_id == batch[:64])
    open_count = db.session.scalar(open_q) or 0
    rows = db.session.scalars(
        select(IngestErrorEvent)
        .where(*where)
        .order_by(IngestErrorEvent.created_at.desc())
        .offset(offset)
        .limit(limit)
    ).all()
    return {
        "items": [public(row) for row in rows],
        "total": int(total),
        "open_count": int(open_count),
        "limit": limit,
        "offset": offset,
        "entity": "ingest_errors",
    }


def resolve_failure(error_id: uuid.UUID, *, note: str = "") -> IngestErrorEvent | None:
    row = db.session.get(IngestErrorEvent, error_id)
    if row is None:
        return None
    row.status = "resolved"
    row.resolved_at = datetime.now(tz=timezone.utc)
    row.resolved_note = text(note)[:2000] or None
    return row


def resolve_batch(batch_id: str, *, note: str = "") -> int:
    batch = text(batch_id)[:64]
    if not batch:
        return 0
    now = datetime.now(tz=timezone.utc)
    rows = db.session.scalars(
        select(IngestErrorEvent).where(
            IngestErrorEvent.batch_id == batch,
            IngestErrorEvent.status == "open",
        )
    ).all()
    for row in rows:
        row.status = "resolved"
        row.resolved_at = now
        row.resolved_note = text(note)[:2000] or None
    return len(rows)
