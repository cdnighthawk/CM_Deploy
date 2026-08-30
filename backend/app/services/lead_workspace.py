"""Shared planning project for a lead so drawings/specs attach to a job.

Leads often exist before a Project row. Drawings only have ``documents.project_id``,
so ingest and the website must create or reuse a workspace project and point the
lead and its estimates at it.
"""
from __future__ import annotations

import uuid
from typing import Mapping

from sqlalchemy import func, select

from ..extensions import db
from ..models import Document, Estimate, LeadEstimate, Project, ProjectMember, SpecSection


def drawing_project_for_lead(row: LeadEstimate) -> Project | None:
    """Project used by the shared drawing viewer: explicit link, else same job number."""
    if row.project_id:
        project = db.session.get(Project, row.project_id)
        if project is not None and project.deleted_at is None:
            return project
    number = (row.number or "").strip()
    if not number:
        return None
    return db.session.scalar(
        select(Project).where(
            Project.deleted_at.is_(None),
            func.lower(func.trim(Project.number)) == number.lower(),
        )
    )


def attach_lead_and_estimates(row: LeadEstimate, project_id: uuid.UUID) -> None:
    """Point the lead and any estimates that still lack a job at ``project_id``."""
    if row.project_id != project_id:
        row.project_id = project_id
    for est in db.session.scalars(select(Estimate).where(Estimate.lead_estimate_id == row.id)).all():
        if est.project_id is None:
            est.project_id = project_id


def sibling_workspace_ids(row: LeadEstimate, dest_id: uuid.UUID) -> list[uuid.UUID]:
    """Other live projects that share this job number (planning leftover, duplicate award)."""
    seen: set[uuid.UUID] = {dest_id}
    out: list[uuid.UUID] = []
    number = (row.number or "").strip()
    if not number:
        return out
    rows = db.session.scalars(
        select(Project.id).where(
            Project.deleted_at.is_(None),
            func.lower(func.trim(Project.number)) == number.lower(),
            Project.id != dest_id,
        )
    ).all()
    for pid in rows:
        if pid in seen:
            continue
        seen.add(pid)
        out.append(pid)
    return out


def move_workspace_artifacts(source_id: uuid.UUID, dest_id: uuid.UUID) -> dict[str, int]:
    """Move drawings/docs/specs from one project onto another. Skips spec codes already on dest."""
    if source_id == dest_id:
        return {"documents": 0, "spec_sections": 0}
    dest_codes = {
        code
        for code in db.session.scalars(select(SpecSection.code).where(SpecSection.project_id == dest_id)).all()
        if code
    }
    spec_moved = 0
    for spec in db.session.scalars(select(SpecSection).where(SpecSection.project_id == source_id)).all():
        if spec.code in dest_codes:
            continue
        spec.project_id = dest_id
        dest_codes.add(spec.code)
        spec_moved += 1
    docs = list(db.session.scalars(select(Document).where(Document.project_id == source_id)).all())
    for doc in docs:
        doc.project_id = dest_id
    return {"documents": len(docs), "spec_sections": spec_moved}


def collect_lead_artifacts(row: LeadEstimate, dest_id: uuid.UUID) -> dict[str, int]:
    """Bring drawings and specs from same-number leftover projects onto the job the UI opens."""
    totals = {"documents": 0, "spec_sections": 0, "sources": 0}
    for source_id in sibling_workspace_ids(row, dest_id):
        moved = move_workspace_artifacts(source_id, dest_id)
        totals["documents"] += moved["documents"]
        totals["spec_sections"] += moved["spec_sections"]
        totals["sources"] += 1
    return totals


def ensure_project_membership(project_id: uuid.UUID, user_id: uuid.UUID | None) -> None:
    if user_id is None:
        return
    existing = db.session.get(ProjectMember, {"user_id": user_id, "project_id": project_id})
    if existing is not None:
        return
    db.session.add(
        ProjectMember(
            user_id=user_id,
            project_id=project_id,
            member_role="estimator",
            created_by_id=user_id,
        )
    )


def ensure_lead_workspace_project(row: LeadEstimate, user_id: uuid.UUID | None = None) -> Project:
    """Reuse ``project_id`` or a job with the same number. Create planning only when needed."""
    existing = drawing_project_for_lead(row)
    if existing is not None:
        attach_lead_and_estimates(row, existing.id)
        ensure_project_membership(existing.id, user_id)
        return existing
    loc = row.location if isinstance(row.location, Mapping) else {}
    city_raw, state_raw = loc.get("city"), loc.get("state")
    city = str(city_raw).strip() if city_raw else None
    state = str(state_raw).strip() if state_raw else None
    name_raw = row.name or row.number or "Lead workspace"
    name = str(name_raw).strip()[:255] or "Lead workspace"
    number = (row.number or "").strip() or None
    if number:
        taken = db.session.scalar(
            select(Project.id).where(
                Project.deleted_at.is_(None),
                func.lower(func.trim(Project.number)) == number.lower(),
            )
        )
        if taken:
            number = None
    proj = Project(
        name=name,
        number=number[:50] if number else None,
        status="planning",
        project_type="commercial",
        city=city,
        state=state,
        notes="Created from lead/estimate workspace.",
    )
    db.session.add(proj)
    db.session.flush()
    attach_lead_and_estimates(row, proj.id)
    ensure_project_membership(proj.id, user_id)
    return proj
