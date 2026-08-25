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
    name = None
    comp = client.get("company")
    if isinstance(comp, Mapping):
        raw = comp.get("name")
        name = str(raw).strip() if raw else None
    office = client.get("office")
    office_name = None
    if isinstance(office, Mapping):
        raw_office = office.get("name")
        office_name = str(raw_office).strip() if raw_office else None
    if name and office_name and office_name.lower() not in name.lower():
        return f"{name} - {office_name}"
    return name


def _loc_text(loc: Mapping[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = loc.get(key)
        if value and str(value).strip():
            return str(value).strip()
    return None


def desktop_queue_item(row: LeadEstimate) -> dict[str, Any]:
    """Shape expected by USISPdfApp ``CloudEstimate`` / ``GetEstimateQueueAsync``."""
    loc = row.location if isinstance(row.location, Mapping) else {}
    city, state = location_bits(loc)
    return {
        "leadEstimateId": str(row.id),
        "name": row.name or "",
        "number": row.number,
        "tradeName": row.trade_name,
        "submissionState": row.submission_state or "",
        "dueAt": iso(row.due_at),
        "city": city,
        "state": state,
        "siteZip": _loc_text(loc, "zip", "postalCode", "zipcode", "zipCode"),
        "siteAddress": _loc_text(loc, "complete", "streetName", "address", "street"),
        "gcName": client_company_name(row.client),
        "workflowBucket": row.workflow_bucket,
        "isParent": row.is_parent,
        "externalParentId": row.external_parent_id,
        "isArchived": bool(row.is_archived),
        "cloudEstimateId": str(row.primary_estimate_id) if row.primary_estimate_id else None,
        "estimateStatus": "Approved" if row.estimate_approved_at else None,
        "total": num_or_none(row.final_value),
    }


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
        "is_archived": row.is_archived,
        "is_parent": row.is_parent,
        "external_parent_id": row.external_parent_id,
        "members": row.members if isinstance(row.members, (dict, list)) else None,
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
