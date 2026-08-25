"""Unified issues tracker: persist status and ingest AI reviews + RFIs."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Mapping

from sqlalchemy import func, or_, select

from ..extensions import db
from ..models import AuditLog, Drawing, DrawingAnnotation, Project, Rfi, User
from ..models.issue import Issue, IssueEvent
from ._perms import CurrentUser

STATUSES = ("New", "Triaged", "In Progress", "Pending Review", "Resolved", "Closed")
SEVERITIES = ("Critical", "Major", "Minor")
SOURCES = ("ai_review", "rfi", "punch", "field", "safety", "manual")
OPEN_STATUSES = ("New", "Triaged", "In Progress", "Pending Review")


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc).isoformat()
    return value.isoformat()


def _text(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def _user_name(user_id: uuid.UUID | None) -> str:
    if not user_id:
        return ""
    user = db.session.get(User, user_id)
    if not user:
        return ""
    name = " ".join(p for p in (_text(user.first_name), _text(user.last_name)) if p)
    return name or _text(user.email)


def _project_name(project_id: uuid.UUID | None) -> str:
    if not project_id:
        return ""
    project = db.session.get(Project, project_id)
    if not project:
        return ""
    return _text(getattr(project, "name", None) or getattr(project, "title", None))


def default_status(*, source_type: str, severity: str) -> str:
    if source_type == "ai_review" and severity == "Critical":
        return "Triaged"
    return "New"


def _map_annotation_severity(raw: str | None) -> str:
    value = (raw or "").strip().lower()
    if value == "critical":
        return "Critical"
    if value == "major":
        return "Major"
    return "Minor"


def _map_rfi_status(raw: str | None) -> str:
    value = (raw or "").strip().lower()
    if value in ("closed", "void"):
        return "Closed"
    if value in ("open", "submitted"):
        return "In Progress"
    return "New"


def serialize_issue(row: Issue, *, include_events: bool = False) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": str(row.id),
        "project_id": str(row.project_id) if row.project_id else None,
        "project_name": _project_name(row.project_id),
        "source_type": row.source_type,
        "source_id": str(row.source_id) if row.source_id else None,
        "severity": row.severity,
        "status": row.status,
        "trade": row.trade or "General",
        "title": row.title,
        "description": row.description or "",
        "cbc_citation": row.cbc_citation or "",
        "cost_impact": float(row.cost_impact) if row.cost_impact is not None else None,
        "schedule_impact_days": row.schedule_impact_days,
        "assignee_id": str(row.assignee_id) if row.assignee_id else None,
        "assignee_name": _user_name(row.assignee_id),
        "due_date": _iso(row.due_date),
        "resolved_at": _iso(row.resolved_at),
        "created_by_id": str(row.created_by_id) if row.created_by_id else None,
        "created_by_name": _user_name(row.created_by_id),
        "drawing_id": str(row.drawing_id) if row.drawing_id else None,
        "sheet_number": row.sheet_number or "",
        "linked_rfi_id": str(row.linked_rfi_id) if row.linked_rfi_id else None,
        "linked_change_order_id": row.linked_change_order_id,
        "created_at": _iso(row.created_at),
        "updated_at": _iso(row.updated_at),
        "entity": "issue",
    }
    if include_events:
        events = list(row.events or [])
        payload["events"] = [
            {
                "id": str(event.id),
                "action": event.action,
                "detail": event.detail or "",
                "payload": event.payload,
                "created_by_id": str(event.created_by_id) if event.created_by_id else None,
                "created_by_name": _user_name(event.created_by_id),
                "created_at": _iso(event.created_at),
            }
            for event in events
        ]
    return payload


def summarize(rows: list[Issue]) -> dict[str, Any]:
    by_status = {status: 0 for status in STATUSES}
    open_critical = 0
    open_total = 0
    for row in rows:
        if row.status in by_status:
            by_status[row.status] += 1
        if row.status in OPEN_STATUSES:
            open_total += 1
            if row.severity == "Critical":
                open_critical += 1
    return {"open_critical": open_critical, "open_total": open_total, "by_status": by_status}


def _add_event(issue: Issue, cu: CurrentUser | None, action: str, detail: str | None = None, payload: dict | None = None) -> None:
    db.session.add(
        IssueEvent(
            issue_id=issue.id,
            action=action,
            detail=detail,
            payload=payload,
            created_by_id=cu.id if cu else None,
        )
    )
    db.session.add(
        AuditLog(
            user_id=cu.id if cu else None,
            entity_type="issue",
            entity_id=issue.id,
            action=action,
            changes=payload,
            message=detail,
        )
    )


def _find_by_source(source_type: str, source_id: uuid.UUID) -> Issue | None:
    return db.session.scalar(
        select(Issue).where(Issue.source_type == source_type, Issue.source_id == source_id)
    )


def upsert_from_annotation(ann: DrawingAnnotation, cu: CurrentUser | None = None) -> Issue | None:
    if ann.type != "ai_review":
        return None
    drawing = db.session.get(Drawing, ann.drawing_id)
    project_id = getattr(drawing, "project_id", None) if drawing else None
    data = ann.data if isinstance(ann.data, dict) else {}
    title = _text(data.get("title") or data.get("summary") or getattr(drawing, "sheet_title", None) or "AI review finding")
    severity = _map_annotation_severity(ann.severity)
    existing = _find_by_source("ai_review", ann.id)
    if existing:
        existing.title = title
        existing.description = _text(data.get("description") or data.get("detail") or existing.description)
        existing.severity = severity
        existing.project_id = project_id or existing.project_id
        existing.drawing_id = ann.drawing_id
        existing.sheet_number = getattr(drawing, "sheet_number", None) or existing.sheet_number
        existing.cost_impact = ann.cost_impact if ann.cost_impact is not None else existing.cost_impact
        existing.schedule_impact_days = ann.delay_impact_days if ann.delay_impact_days is not None else existing.schedule_impact_days
        return existing
    issue = Issue(
        project_id=project_id,
        source_type="ai_review",
        source_id=ann.id,
        severity=severity,
        status=default_status(source_type="ai_review", severity=severity),
        trade=_text(data.get("trade")) or "General",
        title=title[:500],
        description=_text(data.get("description") or data.get("detail")) or None,
        cbc_citation=_text(data.get("cbc_citation") or data.get("citation")) or None,
        cost_impact=ann.cost_impact,
        schedule_impact_days=ann.delay_impact_days,
        created_by_id=ann.created_by_user_id or (cu.id if cu else None),
        drawing_id=ann.drawing_id,
        sheet_number=getattr(drawing, "sheet_number", None),
    )
    db.session.add(issue)
    db.session.flush()
    _add_event(issue, cu, "ingested", "Created from AI review")
    return issue


def upsert_from_rfi(rfi: Rfi, cu: CurrentUser | None = None) -> Issue:
    existing = _find_by_source("rfi", rfi.id)
    title = _text(rfi.subject) or f"RFI #{getattr(rfi, 'number', '')}".strip()
    if existing:
        existing.title = title[:500]
        existing.description = rfi.question or existing.description
        existing.project_id = rfi.project_id
        existing.cost_impact = rfi.cost_impact if rfi.cost_impact is not None else existing.cost_impact
        existing.schedule_impact_days = rfi.schedule_impact_days if rfi.schedule_impact_days is not None else existing.schedule_impact_days
        existing.sheet_number = getattr(rfi, "drawing_number_text", None) or existing.sheet_number
        existing.drawing_id = getattr(rfi, "drawing_id", None) or existing.drawing_id
        existing.linked_rfi_id = rfi.id
        return existing
    issue = Issue(
        project_id=rfi.project_id,
        source_type="rfi",
        source_id=rfi.id,
        severity="Major",
        status=_map_rfi_status(rfi.status),
        trade="General",
        title=title[:500],
        description=rfi.question,
        cost_impact=rfi.cost_impact,
        schedule_impact_days=rfi.schedule_impact_days,
        created_by_id=rfi.created_by_user_id or (cu.id if cu else None),
        drawing_id=getattr(rfi, "drawing_id", None),
        sheet_number=getattr(rfi, "drawing_number_text", None),
        linked_rfi_id=rfi.id,
    )
    db.session.add(issue)
    db.session.flush()
    _add_event(issue, cu, "ingested", "Created from RFI")
    return issue


def sync_sources(project_id: uuid.UUID | None = None) -> None:
    ann_q = select(DrawingAnnotation).where(DrawingAnnotation.type == "ai_review")
    if project_id:
        ann_q = ann_q.join(Drawing, Drawing.id == DrawingAnnotation.drawing_id).where(Drawing.project_id == project_id)
    for ann in db.session.scalars(ann_q).all():
        upsert_from_annotation(ann)

    rfi_q = select(Rfi)
    if hasattr(Rfi, "is_deleted"):
        rfi_q = rfi_q.where(Rfi.is_deleted.is_(False))
    if project_id:
        rfi_q = rfi_q.where(Rfi.project_id == project_id)
    rfis = db.session.scalars(rfi_q).all()
    for rfi in rfis:
        upsert_from_rfi(rfi)
    db.session.flush()


def list_issues(filters: Mapping[str, Any], cu: CurrentUser) -> dict[str, Any]:
    project_id = filters.get("project_id")
    sync_sources(project_id)
    q = select(Issue)
    if project_id:
        q = q.where(Issue.project_id == project_id)
    status = _text(filters.get("status"))
    if status in STATUSES:
        q = q.where(Issue.status == status)
    severity = _text(filters.get("severity"))
    if severity in SEVERITIES:
        q = q.where(Issue.severity == severity)
    trade = _text(filters.get("trade"))
    if trade:
        q = q.where(Issue.trade == trade)
    source_type = _text(filters.get("source_type"))
    if source_type in SOURCES:
        q = q.where(Issue.source_type == source_type)
    search = _text(filters.get("search") or filters.get("q")).lower()
    if search:
        like = f"%{search}%"
        q = q.where(
            or_(
                func.lower(Issue.title).like(like),
                func.lower(func.coalesce(Issue.description, "")).like(like),
                func.lower(func.coalesce(Issue.sheet_number, "")).like(like),
                func.lower(func.coalesce(Issue.trade, "")).like(like),
            )
        )
    rows = list(db.session.scalars(q.order_by(Issue.updated_at.desc()).limit(500)).all())
    db.session.commit()
    return {
        "items": [serialize_issue(row) for row in rows],
        "summary": summarize(rows),
        "entity": "issues",
    }


def get_issue(issue_id: uuid.UUID) -> dict[str, Any] | None:
    row = db.session.get(Issue, issue_id)
    if row is None:
        return None
    return serialize_issue(row, include_events=True)


def create_issue(data: Mapping[str, Any], cu: CurrentUser) -> dict[str, Any]:
    title = _text(data.get("title"))
    if not title:
        raise ValueError("Add a title.")
    source_type = _text(data.get("source_type")) or "manual"
    if source_type not in SOURCES:
        raise ValueError("Choose a valid source type.")
    severity = _text(data.get("severity")) or "Minor"
    if severity not in SEVERITIES:
        raise ValueError("Choose a valid severity.")
    status = _text(data.get("status"))
    if status not in STATUSES:
        status = default_status(source_type=source_type, severity=severity)
    project_raw = _text(data.get("project_id"))
    project_id = uuid.UUID(project_raw) if project_raw else None
    source_raw = _text(data.get("source_id"))
    source_id = uuid.UUID(source_raw) if source_raw else None
    issue = Issue(
        project_id=project_id,
        source_type=source_type,
        source_id=source_id,
        severity=severity,
        status=status,
        trade=_text(data.get("trade")) or "General",
        title=title[:500],
        description=_text(data.get("description")) or None,
        cbc_citation=_text(data.get("cbc_citation")) or None,
        created_by_id=cu.id,
        drawing_id=uuid.UUID(_text(data.get("drawing_id"))) if _text(data.get("drawing_id")) else None,
        sheet_number=_text(data.get("sheet_number")) or None,
    )
    db.session.add(issue)
    db.session.flush()
    _add_event(issue, cu, "created", f"Created from {source_type}")
    db.session.commit()
    return serialize_issue(issue, include_events=True)


def update_status(issue_id: uuid.UUID, status: str, cu: CurrentUser) -> dict[str, Any]:
    if status not in STATUSES:
        raise ValueError("Choose a valid status.")
    row = db.session.get(Issue, issue_id)
    if row is None:
        raise KeyError("Issue not found.")
    previous = row.status
    row.status = status
    if status in ("Resolved", "Closed"):
        row.resolved_at = row.resolved_at or datetime.now(timezone.utc)
    else:
        row.resolved_at = None
    _add_event(row, cu, "status", f"{previous} → {status}", {"from": previous, "to": status})
    db.session.commit()
    return serialize_issue(row, include_events=True)


def assign_issue(issue_id: uuid.UUID, assignee_id: uuid.UUID | None, cu: CurrentUser) -> dict[str, Any]:
    row = db.session.get(Issue, issue_id)
    if row is None:
        raise KeyError("Issue not found.")
    row.assignee_id = assignee_id
    _add_event(row, cu, "assign", "Assignee updated" if assignee_id else "Assignee cleared", {"assignee_id": str(assignee_id) if assignee_id else None})
    db.session.commit()
    return serialize_issue(row, include_events=True)


def create_rfi_from_issue(issue_id: uuid.UUID, cu: CurrentUser) -> dict[str, Any]:
    row = db.session.get(Issue, issue_id)
    if row is None:
        raise KeyError("Issue not found.")
    prefill = {
        "kind": "rfi",
        "issue_id": str(row.id),
        "project_id": str(row.project_id) if row.project_id else None,
        "subject": row.title,
        "question": row.description or row.title,
        "trade": row.trade,
        "drawing_number": row.sheet_number,
    }
    if not row.linked_rfi_id:
        row.linked_rfi_id = None
    _add_event(row, cu, "create-rfi", "Prepared RFI from issue", prefill)
    db.session.commit()
    from urllib.parse import quote

    redirect = "construction/rfi-create.html"
    if row.project_id:
        redirect += f"?project_id={row.project_id}&subject={quote(row.title)}"
    return {"issue": serialize_issue(row, include_events=True), "prefill": prefill, "redirect_to": redirect}


def create_co_from_issue(issue_id: uuid.UUID, cu: CurrentUser) -> dict[str, Any]:
    row = db.session.get(Issue, issue_id)
    if row is None:
        raise KeyError("Issue not found.")
    prefill = {
        "kind": "change_order",
        "issue_id": str(row.id),
        "project_id": str(row.project_id) if row.project_id else None,
        "subject": f"CO from issue: {row.title}",
        "description": row.description or row.title,
        "cost_impact": float(row.cost_impact) if row.cost_impact is not None else None,
    }
    row.linked_change_order_id = row.linked_change_order_id or f"pending:{row.id}"
    _add_event(row, cu, "create-co", "Prepared change order from issue", prefill)
    db.session.commit()
    redirect = "construction/rfis.html"
    if row.linked_rfi_id:
        redirect = f"construction/rfi-detail.html?id={row.linked_rfi_id}"
    elif row.project_id:
        redirect = f"construction/rfis.html?project_id={row.project_id}"
    return {"issue": serialize_issue(row, include_events=True), "prefill": prefill, "redirect_to": redirect}
