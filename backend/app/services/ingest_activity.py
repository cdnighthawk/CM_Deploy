"""Read-only ingest dashboard aggregation from documents, drawings, and agent events."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.exc import ProgrammingError

from ..extensions import db
from ..models import Document, Drawing, Estimate, LeadEstimate, Project
from .ingest import as_uuid, text

INGEST_SOURCES = frozenset(
    {
        "autodesk_desktop_connector",
        "mass_ingest",
        "accdocs",
        "acc_docs",
        "forma",
        "acc_agent",
    }
)
EVENT_TYPES = frozenset({"rescan_complete", "new_project", "heartbeat", "upload", "error"})
ESTIMATE_SHARE_ROOT = r"Y:\Estimates"
ACCDOCS_WATCH_HINT = r"C:\Users\CharlesDossett\DC\ACCDocs\charles@gousis.com"
FOLDER_ATTRS = (
    "estimate_folder_path",
    "windows_folder_path",
    "job_folder_path",
    "folder_path",
    "unc_path",
    "local_folder_path",
)
FOLDER_KEYS = FOLDER_ATTRS + ("estimateFolderPath", "windowsFolderPath", "jobFolderPath")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _iso(dt: datetime | None) -> str | None:
    value = _aware(dt)
    return value.isoformat() if value is not None else None


def _tags(doc: Any) -> dict[str, Any]:
    raw = doc.get("tags") if isinstance(doc, dict) else getattr(doc, "tags", None)
    return dict(raw) if isinstance(raw, dict) else {}


def _source_of(doc: Any) -> str:
    tags = _tags(doc)
    return text(tags.get("source") or tags.get("sourceSystem")) or "other"


def _json_blob(*values: Any) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for value in values:
        if isinstance(value, dict):
            out.update(value)
    return out


def estimate_folder_hint(
    *,
    project: Project | None = None,
    lead: LeadEstimate | None = None,
    estimate: Estimate | None = None,
) -> str | None:
    """Return a known Y:\\Estimates path, or a number-based hint. Does not invent names."""
    for obj in (estimate, lead, project):
        if obj is None:
            continue
        for attr in FOLDER_ATTRS:
            raw = text(getattr(obj, attr, None))
            if raw:
                return raw
        extra = _json_blob(
            getattr(obj, "additional_info", None),
            getattr(obj, "raw_row", None),
            getattr(obj, "bid_location", None),
        )
        for key in FOLDER_KEYS:
            raw = text(extra.get(key))
            if raw:
                return raw
    number = text((project.number if project is not None else None) or (lead.number if lead is not None else None))
    name = text((project.name if project is not None else None) or (lead.name if lead is not None else None))
    if not number:
        return None
    suffix = f"{number} {name}".strip() if name else number
    return f"{ESTIMATE_SHARE_ROOT}\\{suffix}"


def _events_table_ready() -> bool:
    from sqlalchemy import inspect

    try:
        return "ingest_agent_events" in inspect(db.engine).get_table_names()
    except Exception:
        return False


def _errors_table_ready() -> bool:
    from sqlalchemy import inspect

    try:
        return "ingest_error_events" in inspect(db.engine).get_table_names()
    except Exception:
        return False


def record_agent_event(payload: dict[str, Any]) -> dict[str, Any]:
    from ..models.ingest_event import IngestAgentEvent

    if not _events_table_ready():
        raise RuntimeError("ingest_agent_events missing (run flask db upgrade)")
    event_type = text(payload.get("event_type") or payload.get("type") or payload.get("kind")).lower()
    if event_type not in EVENT_TYPES:
        raise ValueError("event_type must be rescan_complete, new_project, heartbeat, upload, or error")
    source = text(payload.get("source") or payload.get("sourceSystem") or "accdocs")[:40] or "accdocs"
    raw_when = payload.get("occurred_at") or payload.get("occurredAt") or payload.get("at")
    occurred = _utcnow()
    if isinstance(raw_when, str) and raw_when.strip():
        try:
            occurred = datetime.fromisoformat(raw_when.strip().replace("Z", "+00:00"))
        except ValueError:
            occurred = _utcnow()
    occurred = _aware(occurred) or _utcnow()
    uploaded = payload.get("uploaded_count")
    if uploaded is None:
        uploaded = payload.get("uploadedCount")
    try:
        uploaded_count = int(uploaded) if uploaded is not None and str(uploaded) != "" else None
    except (TypeError, ValueError):
        uploaded_count = None
    row = IngestAgentEvent(
        event_type=event_type,
        source=source,
        occurred_at=occurred,
        message=text(payload.get("message") or payload.get("detail_message"))[:4000] or None,
        project_id=as_uuid(payload.get("project_id") or payload.get("projectId")),
        lead_estimate_id=as_uuid(payload.get("lead_estimate_id") or payload.get("leadEstimateId")),
        project_number=text(payload.get("project_number") or payload.get("projectNumber") or payload.get("folder_name"))[
            :40
        ]
        or None,
        folder_name=text(payload.get("folder_name") or payload.get("folderName"))[:255] or None,
        uploaded_count=uploaded_count,
        host=text(payload.get("host") or payload.get("agent") or payload.get("agent_id"))[:120] or None,
        detail=payload.get("detail") if isinstance(payload.get("detail"), dict) else None,
    )
    db.session.add(row)
    db.session.flush()
    return public_event(row)


def public_event(row: Any) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "event_type": row.event_type,
        "source": row.source,
        "occurred_at": _iso(row.occurred_at or row.created_at),
        "message": row.message,
        "project_id": str(row.project_id) if row.project_id else None,
        "lead_estimate_id": str(row.lead_estimate_id) if row.lead_estimate_id else None,
        "project_number": row.project_number,
        "folder_name": row.folder_name,
        "uploaded_count": row.uploaded_count,
        "host": row.host,
        "entity": "ingest_event",
    }


def _parse_since(raw_since: str | None, raw_days: Any, default_days: int = 14) -> datetime:
    if raw_since:
        try:
            parsed = datetime.fromisoformat(str(raw_since).strip().replace("Z", "+00:00"))
            return _aware(parsed) or _utcnow() - timedelta(days=default_days)
        except ValueError:
            pass
    try:
        days = int(raw_days) if raw_days not in (None, "") else default_days
    except (TypeError, ValueError):
        days = default_days
    days = max(1, min(days, 365))
    return _utcnow() - timedelta(days=days)


def _doc_source_filter(kind: str, source_filter: str):
    clauses = []
    kind = text(kind).lower()
    if kind == "drawing":
        clauses.append(Document.document_type == "drawing")
    elif kind in {"document", "documents", "doc"}:
        clauses.append(Document.document_type != "drawing")
    source_filter = text(source_filter).lower()
    if source_filter in {"ingest", "accdocs", "agent"}:
        source_expr = func.lower(func.coalesce(Document.tags["source"].astext, ""))
        clauses.append(source_expr.in_(sorted(INGEST_SOURCES)))
    elif source_filter and source_filter not in {"all", "any"}:
        clauses.append(func.lower(func.coalesce(Document.tags["source"].astext, "")) == source_filter)
    return clauses


def _lead_for_project(project_id: uuid.UUID | None, tagged_lead_id: uuid.UUID | None) -> LeadEstimate | None:
    if tagged_lead_id is not None:
        lead = db.session.get(LeadEstimate, tagged_lead_id)
        if lead is not None:
            return lead
    if project_id is None:
        return None
    return db.session.scalar(
        select(LeadEstimate)
        .where(LeadEstimate.project_id == project_id)
        .order_by(LeadEstimate.bc_updated_at.desc().nullslast(), LeadEstimate.id.asc())
    )


def _current_estimate(lead: LeadEstimate | None, project_id: uuid.UUID | None) -> Estimate | None:
    if lead is not None:
        if lead.primary_estimate_id:
            est = db.session.get(Estimate, lead.primary_estimate_id)
            if est is not None:
                return est
        row = db.session.scalar(
            select(Estimate)
            .where(Estimate.lead_estimate_id == lead.id)
            .order_by(Estimate.is_current.desc(), Estimate.version.desc(), Estimate.created_at.desc())
        )
        if row is not None:
            return row
    if project_id is None:
        return None
    return db.session.scalar(
        select(Estimate)
        .where(Estimate.project_id == project_id)
        .order_by(Estimate.is_current.desc(), Estimate.version.desc(), Estimate.created_at.desc())
    )


def _row_get(row: Any, key: str, default: Any = None) -> Any:
    if isinstance(row, dict):
        return row.get(key, default)
    return getattr(row, key, default)


def serialize_activity_item(
    doc: Any,
    *,
    project: Project | None,
    lead: LeadEstimate | None,
    estimate: Estimate | None,
    first_upload_at: datetime | None,
) -> dict[str, Any]:
    tags = _tags(doc)
    source = _source_of(doc)
    dtype = _row_get(doc, "document_type")
    kind = "drawing" if dtype == "drawing" else "document"
    doc_id = _row_get(doc, "id")
    project_id = _row_get(doc, "project_id") or (project.id if project is not None else None)
    lead_id = as_uuid(tags.get("lead_estimate_id") or tags.get("leadEstimateId")) or (lead.id if lead else None)
    estimate_id = estimate.id if estimate is not None else None
    number = (
        text(tags.get("project_number") or tags.get("projectNumber"))
        or (project.number if project is not None else None)
        or (lead.number if lead is not None else None)
    )
    name = (project.name if project is not None else None) or (lead.name if lead is not None else None)
    first = _aware(first_upload_at)
    created = _aware(_row_get(doc, "created_at"))
    folder = estimate_folder_hint(project=project, lead=lead, estimate=estimate)
    return {
        "id": str(doc_id),
        "kind": kind,
        "document_type": dtype,
        "title": _row_get(doc, "title"),
        "filename": _row_get(doc, "original_filename") or _row_get(doc, "title"),
        "source": source,
        "source_id": text(tags.get("source_id") or tags.get("sourceId") or tags.get("relative_path")) or None,
        "folder_name": text(tags.get("folder_name") or tags.get("folderName")) or None,
        "created_at": _iso(_row_get(doc, "created_at")),
        "file_size_bytes": _row_get(doc, "file_size_bytes"),
        "project_id": str(project_id) if project_id else None,
        "project_number": number or None,
        "project_name": name,
        "lead_estimate_id": str(lead_id) if lead_id else None,
        "estimate_id": str(estimate_id) if estimate_id else None,
        "estimate_name": estimate.name if estimate is not None else None,
        "sheet_number": _row_get(doc, "sheet_number"),
        "sheet_title": _row_get(doc, "sheet_title"),
        "discipline": _row_get(doc, "discipline"),
        "file_url": _row_get(doc, "file_url"),
        "project_url": f"construction/project-detail.html?id={project_id}" if project_id else None,
        "estimate_url": (
            f"construction/estimate-detail.html?id={estimate_id or lead_id}" if (estimate_id or lead_id) else None
        ),
        "drawing_url": f"construction/drawing-viewer.html?drawing_id={doc_id}" if kind == "drawing" else None,
        "documents_url": (
            f"usis-documents-hub.html?project_id={project_id}" if project_id and kind != "drawing" else None
        ),
        "estimate_folder_path": folder,
        "is_new_project": bool(project_id and first is not None and created is not None and first >= created - timedelta(seconds=5)),
        "entity": "ingest_item",
    }


def _project_first_uploads(project_ids: list[uuid.UUID]) -> dict[uuid.UUID, datetime]:
    if not project_ids:
        return {}
    rows = db.session.execute(
        select(Document.project_id, func.min(Document.created_at))
        .where(Document.project_id.in_(project_ids))
        .group_by(Document.project_id)
    ).all()
    return {pid: _aware(ts) for pid, ts in rows if pid is not None and ts is not None}


def _open_error_count() -> int:
    if not _errors_table_ready():
        return 0
    from ..models.ingest_error import IngestErrorEvent

    try:
        return int(
            db.session.scalar(select(func.count()).select_from(IngestErrorEvent).where(IngestErrorEvent.status == "open"))
            or 0
        )
    except (ProgrammingError, ValueError):
        db.session.rollback()
        return 0


def _latest_events(limit: int = 12) -> list[dict[str, Any]]:
    if not _events_table_ready():
        return []
    from ..models.ingest_event import IngestAgentEvent

    try:
        rows = list(
            db.session.scalars(
                select(IngestAgentEvent).order_by(IngestAgentEvent.occurred_at.desc(), IngestAgentEvent.created_at.desc()).limit(
                    max(1, min(limit, 50))
                )
            ).all()
        )
    except ProgrammingError:
        db.session.rollback()
        return []
    return [public_event(row) for row in rows]


def _status_from_docs_and_events(
    *,
    last_upload: datetime | None,
    last_ingest_upload: datetime | None,
    events: list[dict[str, Any]],
) -> dict[str, Any]:
    last_event = events[0] if events else None
    last_rescan = next((e for e in events if e.get("event_type") == "rescan_complete"), None)
    last_heartbeat = next((e for e in events if e.get("event_type") == "heartbeat"), None)
    last_new = next((e for e in events if e.get("event_type") == "new_project"), None)
    last_agent_at = last_event.get("occurred_at") if last_event else None
    stale = False
    if last_agent_at:
        try:
            when = datetime.fromisoformat(str(last_agent_at).replace("Z", "+00:00"))
            stale = (_utcnow() - (_aware(when) or _utcnow())) > timedelta(minutes=45)
        except ValueError:
            stale = False
    elif last_upload is not None:
        stale = (_utcnow() - (_aware(last_upload) or _utcnow())) > timedelta(hours=6)
    return {
        "last_upload_at": _iso(last_upload),
        "last_successful_upload_at": _iso(last_ingest_upload or last_upload),
        "last_agent_event_at": last_agent_at,
        "last_rescan_at": (last_rescan or {}).get("occurred_at"),
        "last_heartbeat_at": (last_heartbeat or {}).get("occurred_at"),
        "last_event_type": (last_event or {}).get("event_type"),
        "agent_reporting": bool(events),
        "stale": stale,
        "open_error_count": _open_error_count(),
        "watch_hint": ACCDOCS_WATCH_HINT,
        "estimate_share_hint": ESTIMATE_SHARE_ROOT,
        "history_ui_hint": "Windows data-server history UI (run_history.bat, typically port 5050). Not hosted on Render.",
        "rescan_interval_hint": "15 minutes",
    }


def list_ingest_activity(
    *,
    kind: str = "all",
    source: str = "all",
    project_id: str | None = None,
    lead_estimate_id: str | None = None,
    q: str = "",
    since: str | None = None,
    days: Any = 14,
    limit: Any = 80,
    offset: Any = 0,
) -> dict[str, Any]:
    try:
        lim = max(1, min(int(limit), 300))
        off = max(0, int(offset))
    except (TypeError, ValueError):
        raise ValueError("invalid limit or offset")
    window_start = _parse_since(since, days)
    pid = as_uuid(project_id)
    lid = as_uuid(lead_estimate_id)
    query = text(q).lower()

    filters = [Document.created_at >= window_start, *_doc_source_filter(kind, source)]
    if pid is not None:
        filters.append(Document.project_id == pid)
    if lid is not None:
        filters.append(
            or_(
                Document.tags.contains({"lead_estimate_id": str(lid)}),
                Document.project_id.in_(select(LeadEstimate.project_id).where(LeadEstimate.id == lid)),
            )
        )
    if query:
        like = f"%{query}%"
        filters.append(
            or_(
                Document.title.ilike(like),
                Document.original_filename.ilike(like),
                Document.tags["source_id"].astext.ilike(like),
                Document.tags["folder_name"].astext.ilike(like),
                Document.tags["project_number"].astext.ilike(like),
            )
        )

    docs_t = Document.__table__
    draws_t = Drawing.__table__
    total = int(db.session.scalar(select(func.count()).select_from(docs_t).where(*filters)) or 0)
    rows = db.session.execute(
        select(
            docs_t.c.id,
            docs_t.c.project_id,
            docs_t.c.document_type,
            docs_t.c.title,
            docs_t.c.original_filename,
            docs_t.c.file_url,
            docs_t.c.file_size_bytes,
            docs_t.c.tags,
            docs_t.c.created_at,
            draws_t.c.sheet_number,
            draws_t.c.sheet_title,
            draws_t.c.discipline,
        )
        .select_from(docs_t.outerjoin(draws_t, draws_t.c.id == docs_t.c.id))
        .where(*filters)
        .order_by(docs_t.c.created_at.desc(), docs_t.c.id.desc())
        .offset(off)
        .limit(lim)
    ).mappings()
    docs = [dict(row) for row in rows]

    project_ids = [d.get("project_id") for d in docs if d.get("project_id")]
    projects = {}
    if project_ids:
        for row in db.session.scalars(select(Project).where(Project.id.in_(project_ids))).all():
            projects[row.id] = row
    first_uploads = _project_first_uploads(list({pid for pid in project_ids if pid is not None}))

    lead_cache: dict[tuple[uuid.UUID | None, uuid.UUID | None], LeadEstimate | None] = {}
    estimate_cache: dict[tuple[uuid.UUID | None, uuid.UUID | None], Estimate | None] = {}
    items: list[dict[str, Any]] = []
    for doc in docs:
        tags = _tags(doc)
        tagged_lead = as_uuid(tags.get("lead_estimate_id") or tags.get("leadEstimateId"))
        cache_key = (doc.get("project_id"), tagged_lead)
        if cache_key not in lead_cache:
            lead_cache[cache_key] = _lead_for_project(doc.get("project_id"), tagged_lead)
        lead = lead_cache[cache_key]
        est_key = (lead.id if lead else None, doc.get("project_id"))
        if est_key not in estimate_cache:
            estimate_cache[est_key] = _current_estimate(lead, doc.get("project_id"))
        project = projects.get(doc["project_id"]) if doc.get("project_id") else None
        items.append(
            serialize_activity_item(
                doc,
                project=project,
                lead=lead,
                estimate=estimate_cache[est_key],
                first_upload_at=first_uploads.get(doc["project_id"]) if doc.get("project_id") else None,
            )
        )

    project_summaries = _recent_project_summaries(window_start, source)
    last_upload = db.session.scalar(select(func.max(Document.created_at)))
    last_ingest = db.session.scalar(
        select(func.max(Document.created_at)).where(func.lower(func.coalesce(Document.tags["source"].astext, "")).in_(sorted(INGEST_SOURCES)))
    )
    events = _latest_events()
    return {
        "entity": "ingest_activity",
        "status": _status_from_docs_and_events(
            last_upload=last_upload,
            last_ingest_upload=last_ingest,
            events=events,
        ),
        "items": items,
        "projects": project_summaries,
        "events": events,
        "total": total,
        "limit": lim,
        "offset": off,
        "since": _iso(window_start),
    }


def _recent_project_summaries(window_start: datetime, source_filter: str) -> list[dict[str, Any]]:
    filters = [Document.created_at >= window_start, Document.project_id.is_not(None), *_doc_source_filter("all", source_filter)]
    counts = db.session.execute(
        select(
            Document.project_id,
            Document.document_type,
            func.count(Document.id),
            func.max(Document.created_at),
            func.min(Document.created_at),
        )
        .where(*filters)
        .group_by(Document.project_id, Document.document_type)
    ).all()
    by_project: dict[uuid.UUID, dict[str, Any]] = {}
    for pid, dtype, count, last_at, first_in_window in counts:
        if pid is None:
            continue
        bucket = by_project.setdefault(
            pid,
            {"drawing_count": 0, "document_count": 0, "last_upload_at": None, "first_in_window_at": None},
        )
        if dtype == "drawing":
            bucket["drawing_count"] += int(count)
        else:
            bucket["document_count"] += int(count)
        last = _aware(last_at)
        first = _aware(first_in_window)
        if last and (bucket["last_upload_at"] is None or last > bucket["last_upload_at"]):
            bucket["last_upload_at"] = last
        if first and (bucket["first_in_window_at"] is None or first < bucket["first_in_window_at"]):
            bucket["first_in_window_at"] = first

    project_ids = list(by_project.keys())
    if not project_ids:
        return []
    projects = {p.id: p for p in db.session.scalars(select(Project).where(Project.id.in_(project_ids))).all()}
    first_ever = _project_first_uploads(project_ids)
    out: list[dict[str, Any]] = []
    for pid, bucket in by_project.items():
        project = projects.get(pid)
        lead = _lead_for_project(pid, None)
        estimate = _current_estimate(lead, pid)
        first = first_ever.get(pid)
        is_new = bool(first and first >= window_start)
        out.append(
            {
                "project_id": str(pid),
                "project_number": (project.number if project is not None else None) or (lead.number if lead else None),
                "project_name": (project.name if project is not None else None) or (lead.name if lead else None),
                "lead_estimate_id": str(lead.id) if lead else None,
                "estimate_id": str(estimate.id) if estimate else None,
                "drawing_count": bucket["drawing_count"],
                "document_count": bucket["document_count"],
                "upload_count": bucket["drawing_count"] + bucket["document_count"],
                "last_upload_at": _iso(bucket["last_upload_at"]),
                "first_upload_at": _iso(first),
                "is_new": is_new,
                "project_url": f"construction/project-detail.html?id={pid}",
                "estimate_url": (
                    f"construction/estimate-detail.html?id={estimate.id if estimate else lead.id}"
                    if (estimate or lead)
                    else None
                ),
                "estimate_folder_path": estimate_folder_hint(project=project, lead=lead, estimate=estimate),
                "entity": "ingest_project",
            }
        )
    out.sort(key=lambda row: (0 if row["is_new"] else 1, -_sort_ts(row.get("last_upload_at"))))
    return out[:40]


def _sort_ts(raw: str | None) -> float:
    if not raw:
        return 0.0
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return 0.0
