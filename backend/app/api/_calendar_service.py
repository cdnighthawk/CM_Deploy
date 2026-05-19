"""Aggregate project-scoped dates into categorized calendar events for FullCalendar."""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import and_, select
from sqlalchemy import false as sa_false

from ..extensions import db
from ..models import Project, ProjectMaterialOrder, ProjectScheduleItem, Rfi, Rfp, Submittal
from ..permissions.project_scope import assigned_project_ids, user_can_access_project
from ._perms import CurrentUser

CALENDAR_CATEGORIES = frozenset(
    {
        "procurement_order",
        "procurement_delivery",
        "schedule",
        "rfi",
        "submittal",
        "rfp",
        "project_milestone",
    }
)

CATEGORY_PRESETS: dict[str, frozenset[str]] = {
    "procurement": frozenset({"procurement_order", "procurement_delivery", "rfp"}),
    "project": frozenset({"schedule", "rfi", "submittal", "project_milestone"}),
    "all": CALENDAR_CATEGORIES,
}

CATEGORY_LABELS: dict[str, str] = {
    "procurement_order": "Order by",
    "procurement_delivery": "Expected delivery",
    "schedule": "Installation window",
    "rfi": "RFI due",
    "submittal": "Submittal due",
    "rfp": "RFP due",
    "project_milestone": "Project milestone",
}

_PROJECT_MILESTONE_FIELDS: tuple[tuple[str, str], ...] = (
    ("contract_date", "Contract date"),
    ("start_date", "Project start"),
    ("substantial_completion_date", "Substantial completion"),
    ("closeout_date", "Closeout"),
    ("invoice_due_date", "Invoice due"),
)


def _parse_date_param(raw: str | None) -> date | None:
    if not raw or not str(raw).strip():
        return None
    try:
        return date.fromisoformat(str(raw).strip()[:10])
    except ValueError:
        return None


def _dt_to_date(val: datetime | None) -> date | None:
    if val is None:
        return None
    if val.tzinfo is not None:
        return val.astimezone(timezone.utc).date()
    return val.date()


def _event_overlaps_range(ev_start: date, ev_end: date, range_start: date | None, range_end: date | None) -> bool:
    if range_start and ev_end < range_start:
        return False
    if range_end and ev_start > range_end:
        return False
    return True


def _project_filter_ids(cu: CurrentUser, project_id: uuid.UUID | None) -> list[uuid.UUID] | None:
    """Return explicit project id list to query, or None meaning all accessible projects."""
    if project_id is not None:
        if not user_can_access_project(cu, project_id):
            return []
        return [project_id]
    allowed = assigned_project_ids(cu)
    if allowed is None:
        return None
    return list(allowed)


def _project_scope_filter(cu: CurrentUser, project_id: uuid.UUID | None, model_project_col):
    """SQLAlchemy filter limiting rows to accessible, non-deleted projects."""
    ids = _project_filter_ids(cu, project_id)
    if ids is not None and not ids:
        return sa_false()
    clauses = [Project.deleted_at.is_(None)]
    if ids is not None:
        clauses.append(model_project_col.in_(ids))
    return and_(*clauses)


def _resolve_categories(
    categories_param: str | None,
    preset_param: str | None,
) -> frozenset[str]:
    if preset_param:
        key = preset_param.strip().lower()
        if key in CATEGORY_PRESETS:
            return CATEGORY_PRESETS[key]
    if categories_param:
        parts = {p.strip().lower() for p in categories_param.split(",") if p.strip()}
        chosen = parts & CALENDAR_CATEGORIES
        if chosen:
            return frozenset(chosen)
    return CALENDAR_CATEGORIES


def _append_event(
    events: list[dict[str, Any]],
    *,
    event_id: str,
    category: str,
    project_id: uuid.UUID,
    project_name: str,
    project_number: str | None,
    title: str,
    start: date,
    end: date,
    url: str,
    source_type: str,
    source_id: str,
    meta: dict[str, Any] | None = None,
) -> None:
    events.append(
        {
            "id": event_id,
            "category": category,
            "category_label": CATEGORY_LABELS.get(category, category),
            "source_type": source_type,
            "source_id": source_id,
            "project_id": str(project_id),
            "project_name": project_name,
            "project_number": project_number,
            "title": title,
            "start": start.isoformat(),
            "end": end.isoformat(),
            "all_day": True,
            "url": url,
            "meta": meta or {},
        }
    )


def _project_base_url(project_id: uuid.UUID) -> str:
    return f"construction/project-detail.html?id={project_id}"


def list_calendar_events(
    cu: CurrentUser,
    *,
    project_id: uuid.UUID | None = None,
    categories: frozenset[str] | None = None,
    range_start: date | None = None,
    range_end: date | None = None,
) -> dict[str, Any]:
    cats = categories or CALENDAR_CATEGORIES
    project_ids = _project_filter_ids(cu, project_id)
    if project_ids is not None and not project_ids:
        return {"items": [], "categories": sorted(cats), "entity": "calendar_events"}

    events: list[dict[str, Any]] = []

    # --- Schedule (installation windows) ---
    if "schedule" in cats:
        q = (
            select(ProjectScheduleItem, Project)
            .join(Project, Project.id == ProjectScheduleItem.project_id)
            .where(_project_scope_filter(cu, project_id, ProjectScheduleItem.project_id))
            .order_by(ProjectScheduleItem.start_date, ProjectScheduleItem.id)
        )
        for row, proj in db.session.execute(q):
            if not _event_overlaps_range(row.start_date, row.end_date, range_start, range_end):
                continue
            label = row.title
            if row.crew_label:
                label = f"{label} · {row.crew_label}"
            _append_event(
                events,
                event_id=f"schedule:{row.id}",
                category="schedule",
                project_id=proj.id,
                project_name=proj.name,
                project_number=proj.number,
                title=label,
                start=row.start_date,
                end=row.end_date,
                url=_project_base_url(proj.id),
                source_type="schedule_item",
                source_id=str(row.id),
                meta={"crew_label": row.crew_label},
            )

    # --- Procurement: material orders ---
    if "procurement_order" in cats or "procurement_delivery" in cats:
        q = (
            select(ProjectMaterialOrder, Project)
            .join(Project, Project.id == ProjectMaterialOrder.project_id)
            .where(
                _project_scope_filter(cu, project_id, ProjectMaterialOrder.project_id),
                ProjectMaterialOrder.status != "cancelled",
            )
            .order_by(ProjectMaterialOrder.expected_delivery_date, ProjectMaterialOrder.id)
        )
        for order, proj in db.session.execute(q):
            vendor = (order.vendor_name or "").strip() or "Vendor"
            base_title = order.description or order.commitment_id
            if "procurement_order" in cats and order.order_date:
                start = order.order_date
                end = order.order_date
                if _event_overlaps_range(start, end, range_start, range_end):
                    _append_event(
                        events,
                        event_id=f"procurement_order:{order.id}",
                        category="procurement_order",
                        project_id=proj.id,
                        project_name=proj.name,
                        project_number=proj.number,
                        title=f"Order by: {vendor}",
                        start=start,
                        end=end,
                        url=_project_base_url(proj.id),
                        source_type="material_order",
                        source_id=str(order.id),
                        meta={"status": order.status, "vendor_name": vendor},
                    )
            if "procurement_delivery" in cats and order.expected_delivery_date:
                start = order.expected_delivery_date
                end = order.expected_delivery_date
                if _event_overlaps_range(start, end, range_start, range_end):
                    _append_event(
                        events,
                        event_id=f"procurement_delivery:{order.id}",
                        category="procurement_delivery",
                        project_id=proj.id,
                        project_name=proj.name,
                        project_number=proj.number,
                        title=f"Delivery: {vendor}",
                        start=start,
                        end=end,
                        url=_project_base_url(proj.id),
                        source_type="material_order",
                        source_id=str(order.id),
                        meta={"status": order.status, "vendor_name": vendor},
                    )

    # --- RFIs ---
    if "rfi" in cats:
        q = (
            select(Rfi, Project)
            .join(Project, Project.id == Rfi.project_id)
            .where(
                _project_scope_filter(cu, project_id, Rfi.project_id),
                Rfi.is_deleted.is_(False),
                Rfi.due_at.is_not(None),
            )
            .order_by(Rfi.due_at, Rfi.id)
        )
        for rfi, proj in db.session.execute(q):
            due = _dt_to_date(rfi.due_at)
            if due is None:
                continue
            if not _event_overlaps_range(due, due, range_start, range_end):
                continue
            num = f"RFI #{rfi.number}" if rfi.number is not None else "RFI"
            _append_event(
                events,
                event_id=f"rfi:{rfi.id}",
                category="rfi",
                project_id=proj.id,
                project_name=proj.name,
                project_number=proj.number,
                title=f"{num}: {rfi.subject}",
                start=due,
                end=due,
                url=f"construction/rfi-detail.html?id={rfi.id}",
                source_type="rfi",
                source_id=str(rfi.id),
                meta={"status": rfi.status},
            )

    # --- Submittals ---
    if "submittal" in cats:
        q = (
            select(Submittal, Project)
            .join(Project, Project.id == Submittal.project_id)
            .where(
                _project_scope_filter(cu, project_id, Submittal.project_id),
                Submittal.due_at.is_not(None),
            )
            .order_by(Submittal.due_at, Submittal.id)
        )
        for sub, proj in db.session.execute(q):
            due = _dt_to_date(sub.due_at)
            if due is None:
                continue
            if not _event_overlaps_range(due, due, range_start, range_end):
                continue
            num = f"Submittal #{sub.number}" if sub.number is not None else "Submittal"
            _append_event(
                events,
                event_id=f"submittal:{sub.id}",
                category="submittal",
                project_id=proj.id,
                project_name=proj.name,
                project_number=proj.number,
                title=f"{num}: {sub.title}",
                start=due,
                end=due,
                url=f"construction/submittal-detail.html?id={sub.id}&project_id={proj.id}",
                source_type="submittal",
                source_id=str(sub.id),
                meta={"status": sub.status},
            )

    # --- RFPs ---
    if "rfp" in cats:
        q = (
            select(Rfp, Project)
            .join(Project, Project.id == Rfp.project_id)
            .where(
                Rfp.due_at.is_not(None),
                _project_scope_filter(cu, project_id, Rfp.project_id),
            )
            .order_by(Rfp.due_at, Rfp.id)
        )
        for rfp, proj in db.session.execute(q):
            due = _dt_to_date(rfp.due_at)
            if due is None:
                continue
            if not _event_overlaps_range(due, due, range_start, range_end):
                continue
            title = (rfp.title or "").strip() or "RFP"
            _append_event(
                events,
                event_id=f"rfp:{rfp.id}",
                category="rfp",
                project_id=proj.id,
                project_name=proj.name,
                project_number=proj.number,
                title=f"RFP due: {title}",
                start=due,
                end=due,
                url=f"usis-rfp-detail.html?id={rfp.id}",
                source_type="rfp",
                source_id=str(rfp.id),
                meta={"status": rfp.status},
            )

    # --- Project milestones ---
    if "project_milestone" in cats:
        q = select(Project).where(_project_scope_filter(cu, project_id, Project.id))
        for proj in db.session.scalars(q).all():
            for field, label in _PROJECT_MILESTONE_FIELDS:
                val: date | None = getattr(proj, field, None)
                if val is None:
                    continue
                if not _event_overlaps_range(val, val, range_start, range_end):
                    continue
                _append_event(
                    events,
                    event_id=f"project_milestone:{proj.id}:{field}",
                    category="project_milestone",
                    project_id=proj.id,
                    project_name=proj.name,
                    project_number=proj.number,
                    title=f"{label}: {proj.name}",
                    start=val,
                    end=val,
                    url=_project_base_url(proj.id),
                    source_type="project",
                    source_id=str(proj.id),
                    meta={"milestone_field": field},
                )

    events.sort(key=lambda e: (e["start"], e.get("project_name") or "", e["title"]))
    return {
        "items": events,
        "categories": sorted(cats),
        "entity": "calendar_events",
        "project_id": str(project_id) if project_id else None,
    }
