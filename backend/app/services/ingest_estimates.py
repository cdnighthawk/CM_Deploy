"""Read-only estimate + folder_path map for the Windows ACCDocs/Forma agent.

Does not provision folders. Reads ``estimates.folder_path`` set by
``estimate_folder_provision`` (PR #53). Job numbers are lead/project numbers
only — never the estimate UUID.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import joinedload

from ..extensions import db
from ..models import Estimate, LeadEstimate, Project
from .ingest import as_uuid, folder_to_project_number, lead_is_archived, text

DEFAULT_LIMIT = 500
MAX_LIMIT = 2000
MAX_SCAN = 5000


def _iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def human_job_number(*candidates: Any) -> str | None:
    """Lead number, else project number. Never a UUID (see PR #55)."""
    for raw in candidates:
        value = text(raw)
        if not value:
            continue
        if as_uuid(value) is not None:
            continue
        return value
    return None


def _hints(*values: Any) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for raw in values:
        value = text(raw)
        if not value:
            continue
        key = value.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(value)
    return out


def serialize_ingest_estimate(
    est: Estimate,
    *,
    lead: LeadEstimate | None,
    projects: dict[uuid.UUID, Project],
) -> dict[str, Any]:
    lead_project = None
    if lead is not None and lead.project_id is not None:
        lead_project = projects.get(lead.project_id) or getattr(lead, "project", None)
    est_project = projects.get(est.project_id) if est.project_id else None

    linked: list[Project] = []
    seen_ids: set[uuid.UUID] = set()
    for job in (est_project, lead_project):
        if job is None or job.id in seen_ids:
            continue
        if getattr(job, "deleted_at", None) is not None:
            continue
        seen_ids.add(job.id)
        linked.append(job)

    primary = linked[0] if linked else None
    lead_number = text(lead.number) if lead is not None else ""
    project_number = text(primary.number if primary is not None else None)
    job_number = human_job_number(lead_number, project_number, *(job.number for job in linked))
    lead_name = text(lead.name) if lead is not None else ""
    project_name = text(primary.name if primary is not None else None)
    archived = bool(lead is not None and lead_is_archived(lead))
    if primary is not None and (primary.status or "") == "archived":
        archived = True

    compact_projects = [
        {
            "id": str(job.id),
            "number": text(job.number) or None,
            "name": text(job.name) or None,
        }
        for job in linked
    ]
    folder_hints = _hints(
        job_number,
        lead_number,
        project_number,
        lead_name,
        project_name,
        est.name,
        *(job.number for job in linked),
        *(job.name for job in linked),
    )
    return {
        "id": str(est.id),
        "name": est.name,
        "job_number": job_number,
        "folder_path": text(est.folder_path) or None,
        "folder_provision_status": text(est.folder_provision_status) or None,
        "folder_provisioned_at": _iso(est.folder_provisioned_at),
        "is_current": bool(est.is_current),
        "lead_estimate_id": str(est.lead_estimate_id) if est.lead_estimate_id else None,
        "lead_number": lead_number or None,
        "lead_name": lead_name or None,
        "project_id": str(primary.id) if primary is not None else None,
        "project_number": project_number or None,
        "project_name": project_name or None,
        "projects": compact_projects,
        "folder_hints": folder_hints,
        "archived": archived,
        "updated_at": _iso(est.updated_at),
    }


def estimate_matches_query(item: dict[str, Any], query: str) -> bool:
    q = text(query).lower()
    if not q:
        return True
    number_guess = folder_to_project_number(query).lower()
    haystack: list[Any] = [
        item.get("id"),
        item.get("job_number"),
        item.get("name"),
        item.get("folder_path"),
        item.get("project_id"),
        item.get("project_number"),
        item.get("project_name"),
        item.get("lead_estimate_id"),
        item.get("lead_number"),
        item.get("lead_name"),
        *(item.get("folder_hints") or []),
    ]
    for job in item.get("projects") or []:
        if isinstance(job, dict):
            haystack.extend([job.get("id"), job.get("number"), job.get("name")])
    values = [str(v).lower() for v in haystack if v]
    return any(v == q or v == number_guess or number_guess in v or q in v for v in values)


def _parse_limit_offset(limit: Any, offset: Any) -> tuple[int, int]:
    try:
        lim = max(1, min(int(limit if limit not in (None, "") else DEFAULT_LIMIT), MAX_LIMIT))
        off = max(0, int(offset if offset not in (None, "") else 0))
    except (TypeError, ValueError) as exc:
        raise ValueError("invalid limit or offset") from exc
    return lim, off


def list_ingest_estimates(
    *,
    query: str = "",
    project_id: str | None = None,
    folder_provision_status: str | None = None,
    has_folder: bool | None = None,
    limit: Any = DEFAULT_LIMIT,
    offset: Any = 0,
) -> dict[str, Any]:
    lim, off = _parse_limit_offset(limit, offset)
    q = text(query)
    status = text(folder_provision_status).lower()
    pid = as_uuid(project_id)

    rows = list(
        db.session.scalars(
            select(Estimate)
            .options(joinedload(Estimate.lead_estimate).joinedload(LeadEstimate.project))
            .order_by(Estimate.updated_at.desc(), Estimate.created_at.desc())
            .limit(MAX_SCAN)
        )
        .unique()
        .all()
    )
    project_ids: set[uuid.UUID] = set()
    for est in rows:
        if est.project_id:
            project_ids.add(est.project_id)
        lead = est.lead_estimate
        if lead is not None and lead.project_id:
            project_ids.add(lead.project_id)
    projects: dict[uuid.UUID, Project] = {}
    if project_ids:
        for job in db.session.scalars(select(Project).where(Project.id.in_(project_ids))).all():
            projects[job.id] = job

    items: list[dict[str, Any]] = []
    for est in rows:
        lead = est.lead_estimate
        item = serialize_ingest_estimate(est, lead=lead, projects=projects)
        if pid is not None:
            ids = {as_uuid(item.get("project_id")), as_uuid(item.get("lead_estimate_id")), as_uuid(item.get("id"))}
            ids.update(as_uuid(job.get("id")) for job in (item.get("projects") or []) if isinstance(job, dict))
            if est.project_id:
                ids.add(est.project_id)
            if lead is not None:
                ids.add(lead.id)
                if lead.project_id:
                    ids.add(lead.project_id)
            if pid not in ids:
                continue
        if status and text(item.get("folder_provision_status")).lower() != status:
            continue
        if has_folder is True and not item.get("folder_path"):
            continue
        if has_folder is False and item.get("folder_path"):
            continue
        if q and not estimate_matches_query(item, q):
            continue
        items.append(item)

    total = len(items)
    page = items[off : off + lim]
    return {
        "estimates": page,
        "count": total,
        "limit": lim,
        "offset": off,
        "has_more": off + len(page) < total,
        "entity": "ingest_estimates",
    }
