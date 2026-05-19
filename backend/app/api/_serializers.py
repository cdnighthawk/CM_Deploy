"""Shared JSON serializers for API and AI tools."""
from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Mapping

from sqlalchemy import select

from ..extensions import db
from ..models import Company, Contact, LeadEstimate, Project


def iso(dt: datetime | date | None) -> str | None:
    if dt is None:
        return None
    if isinstance(dt, datetime):
        return dt.isoformat()
    return dt.isoformat()


def num_or_none(v: Decimal | float | None) -> float | None:
    if v is None:
        return None
    return float(v)


def location_bits(loc: Any) -> tuple[str | None, str | None]:
    if not isinstance(loc, Mapping):
        return None, None
    c = loc.get("city")
    s = loc.get("state")
    return (str(c).strip() if c else None, str(s).strip() if s else None)


def client_company_name(client: Any) -> str | None:
    if not isinstance(client, Mapping):
        return None
    comp = client.get("company")
    if isinstance(comp, Mapping):
        n = comp.get("name")
        return str(n).strip() if n else None
    return None


def lead_estimate_public(row: LeadEstimate) -> dict[str, Any]:
    city, state = location_bits(row.location)
    return {
        "id": str(row.id),
        "external_id": row.external_id,
        "project_id": str(row.project_id) if row.project_id else None,
        "name": row.name,
        "number": row.number,
        "trade_name": row.trade_name,
        "submission_state": row.submission_state,
        "source": row.source,
        "workflow_bucket": row.workflow_bucket,
        "due_at": iso(row.due_at),
        "bc_updated_at": iso(row.bc_updated_at),
        "company_name": client_company_name(row.client),
        "city": city,
        "state": state,
        "crm_stage": row.crm_stage,
        "win_probability": num_or_none(row.win_probability),
        "primary_estimate_id": str(row.primary_estimate_id) if row.primary_estimate_id else None,
        "primary_rfp_id": str(row.primary_rfp_id) if row.primary_rfp_id else None,
        "estimate_locked_at": iso(row.estimate_locked_at),
        "estimate_approved_at": iso(row.estimate_approved_at),
        "estimate_approved_by_user_id": str(row.estimate_approved_by_user_id)
        if row.estimate_approved_by_user_id
        else None,
    }


def primary_lead_detail_id_by_project_ids(project_ids: list[uuid.UUID]) -> dict[uuid.UUID, str]:
    if not project_ids:
        return {}
    q = (
        select(LeadEstimate)
        .where(LeadEstimate.project_id.in_(project_ids))
        .order_by(
            LeadEstimate.project_id.asc(),
            LeadEstimate.bc_updated_at.desc().nullslast(),
            LeadEstimate.id.asc(),
        )
    )
    rows = list(db.session.scalars(q).all())
    out: dict[uuid.UUID, str] = {}
    for le in rows:
        pid = le.project_id
        if pid is None or pid in out:
            continue
        ext = (le.external_id or "").strip()
        out[pid] = ext if ext else str(le.id)
    return out


def project_public(p: Project, *, primary_lead_detail_id: str | None = None) -> dict[str, Any]:
    city = p.city.strip() if p.city else None
    state = p.state.strip() if p.state else None
    d: dict[str, Any] = {
        "id": str(p.id),
        "number": p.number,
        "name": p.name,
        "city": city,
        "state": state,
        "status": p.status,
        "project_type": p.project_type,
        "updated_at": iso(p.updated_at),
    }
    if primary_lead_detail_id:
        d["primary_lead_detail_id"] = primary_lead_detail_id
    return d


def company_public(c: Company) -> dict[str, Any]:
    return {
        "id": str(c.id),
        "name": c.name,
        "company_type": c.company_type,
        "email": c.email,
        "phone": c.phone,
        "city": c.city,
        "state": c.state,
        "website": c.website,
        "updated_at": iso(c.updated_at),
    }


def contact_public(c: Contact) -> dict[str, Any]:
    name = " ".join(
        p for p in ((c.first_name or "").strip(), (c.last_name or "").strip()) if p
    ).strip()
    return {
        "id": str(c.id),
        "company_id": str(c.company_id) if c.company_id else None,
        "name": name or None,
        "first_name": c.first_name,
        "last_name": c.last_name,
        "title": c.title,
        "email": c.email,
        "phone": c.phone,
        "mobile": c.mobile,
        "is_primary": c.is_primary,
        "updated_at": iso(c.updated_at),
    }
