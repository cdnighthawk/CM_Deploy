"""Procurement lookups — project directory, PO types, company profile, tax codes."""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import distinct, func, select

from ..extensions import db
from ..models import (
    CommitmentLineItem,
    Company,
    Contact,
    ProcurementPoType,
    Project,
    ProjectDirectoryCompany,
)
from ._perms import CurrentUser
from ._rfi_service import ApiError, _parse_uuid

PROCUREMENT_VENDOR_TYPES = frozenset({"vendor", "subcontractor", "gc", "other", "self"})


def _can_view(cu: CurrentUser) -> bool:
    if cu.is_dev_admin or cu.has_role("admin", "superuser", "standard"):
        return True
    return cu.has_role("read_only", "readonly")


def _can_mutate(cu: CurrentUser) -> bool:
    return cu.is_dev_admin or cu.has_role("admin", "superuser", "standard")


def _vendor_company_ok(c: Company) -> bool:
    return c.company_type in PROCUREMENT_VENDOR_TYPES


def _format_company_address(c: Company) -> str:
    parts: list[str] = []
    for attr in ("address_line1", "address_line2"):
        v = getattr(c, attr, None)
        if v and str(v).strip():
            parts.append(str(v).strip())
    city_state: list[str] = []
    if c.city and str(c.city).strip():
        city_state.append(str(c.city).strip())
    if c.state and str(c.state).strip():
        city_state.append(str(c.state).strip())
    if c.postal_code and str(c.postal_code).strip():
        city_state.append(str(c.postal_code).strip())
    if city_state:
        parts.append(", ".join(city_state))
    if c.country and str(c.country).strip() and str(c.country).strip().upper() != "US":
        parts.append(str(c.country).strip())
    return "\n".join(parts)


def format_project_address(p: Project) -> str:
    parts: list[str] = []
    for attr in ("address_line1", "address_line2"):
        v = getattr(p, attr, None)
        if v and str(v).strip():
            parts.append(str(v).strip())
    city_state: list[str] = []
    if p.city and str(p.city).strip():
        city_state.append(str(p.city).strip())
    if p.state and str(p.state).strip():
        city_state.append(str(p.state).strip())
    if p.postal_code and str(p.postal_code).strip():
        city_state.append(str(p.postal_code).strip())
    if city_state:
        parts.append(", ".join(city_state))
    return "\n".join(parts)


def list_po_types(cu: CurrentUser) -> dict[str, Any]:
    if not _can_view(cu):
        raise ApiError("forbidden", 403)
    rows = db.session.scalars(
        select(ProcurementPoType)
        .where(ProcurementPoType.is_active.is_(True))
        .order_by(ProcurementPoType.sort_order, ProcurementPoType.label)
    ).all()
    return {
        "items": [{"code": r.code, "label": r.label} for r in rows],
        "entity": "procurement_po_types",
    }


def list_directory_companies(
    project_id: uuid.UUID, cu: CurrentUser, q: str = "", limit: int = 20
) -> dict[str, Any]:
    if not _can_view(cu):
        raise ApiError("forbidden", 403)
    q_norm = (q or "").strip().lower()
    limit = max(1, min(limit, 50))
    stmt = (
        select(Company)
        .join(ProjectDirectoryCompany, ProjectDirectoryCompany.company_id == Company.id)
        .where(
            ProjectDirectoryCompany.project_id == project_id,
            Company.deleted_at.is_(None),
            Company.company_type.in_(tuple(PROCUREMENT_VENDOR_TYPES)),
        )
        .order_by(Company.name.asc())
        .limit(500)
    )
    rows = list(db.session.scalars(stmt).all())
    if not rows:
        rows = search_vendors_fallback(project_id, q_norm, limit=500)
    if q_norm:
        rows = [c for c in rows if q_norm in (c.name or "").lower()]
    return {
        "items": [
            {
                "id": str(c.id),
                "name": c.name,
                "company_type": c.company_type,
                "in_directory": is_company_in_directory(project_id, c.id),
            }
            for c in rows[:limit]
        ],
        "entity": "project_directory_companies",
    }


def add_directory_company(
    project_id: uuid.UUID, company_id: uuid.UUID, cu: CurrentUser
) -> dict[str, Any]:
    if not _can_mutate(cu):
        raise ApiError("forbidden", 403)
    project = db.session.get(Project, project_id)
    if project is None or project.deleted_at is not None:
        raise ApiError("project not found", 404)
    company = db.session.get(Company, company_id)
    if company is None or company.deleted_at is not None:
        raise ApiError("company not found", 404)
    if not _vendor_company_ok(company):
        raise ApiError("invalid company type for project directory", 400)
    existing = db.session.scalar(
        select(ProjectDirectoryCompany).where(
            ProjectDirectoryCompany.project_id == project_id,
            ProjectDirectoryCompany.company_id == company_id,
        )
    )
    if existing is None:
        db.session.add(ProjectDirectoryCompany(project_id=project_id, company_id=company_id))
        db.session.commit()
    return {
        "item": {
            "id": str(company_id),
            "name": company.name,
            "company_type": company.company_type,
            "in_directory": True,
        },
        "entity": "project_directory_company",
    }


def get_company_procurement_profile(company_id: uuid.UUID, cu: CurrentUser) -> dict[str, Any]:
    if not _can_view(cu):
        raise ApiError("forbidden", 403)
    company = db.session.get(Company, company_id)
    if company is None or company.deleted_at is not None:
        raise ApiError("company not found", 404)
    contacts = db.session.scalars(
        select(Contact).where(Contact.company_id == company_id).order_by(
            Contact.is_primary.desc(), Contact.last_name, Contact.first_name
        )
    ).all()

    def _contact_label(c: Contact) -> str:
        name = " ".join(x for x in (c.first_name, c.last_name) if x and str(x).strip()).strip()
        if c.title:
            return f"{name} ({c.title})" if name else str(c.title)
        return name or c.email or str(c.id)

    return {
        "item": {
            "id": str(company.id),
            "name": company.name,
            "company_type": company.company_type,
            "address": _format_company_address(company),
            "phone": company.phone,
            "email": company.email,
            "contacts": [
                {
                    "id": str(c.id),
                    "label": _contact_label(c),
                    "email": c.email,
                    "phone": c.phone or c.mobile,
                    "is_primary": c.is_primary,
                }
                for c in contacts
            ],
        },
        "entity": "company_procurement_profile",
    }


def list_tax_codes(project_id: uuid.UUID, cu: CurrentUser) -> dict[str, Any]:
    if not _can_view(cu):
        raise ApiError("forbidden", 403)
    from ..models import Commitment

    rows = db.session.scalars(
        select(distinct(CommitmentLineItem.tax_code))
        .join(Commitment, Commitment.id == CommitmentLineItem.commitment_id)
        .where(
            Commitment.project_id == project_id,
            CommitmentLineItem.tax_code.isnot(None),
            CommitmentLineItem.tax_code != "",
        )
        .order_by(CommitmentLineItem.tax_code)
    ).all()
    codes = [str(r).strip() for r in rows if r and str(r).strip()]
    defaults = ["EXEMPT", "TAXABLE"]
    seen: set[str] = set()
    items: list[dict[str, str]] = []
    for code in defaults + codes:
        if code not in seen:
            seen.add(code)
            items.append({"code": code, "label": code})
    return {"items": items, "entity": "tax_codes"}


def is_company_in_directory(project_id: uuid.UUID, company_id: uuid.UUID) -> bool:
    return (
        db.session.scalar(
            select(func.count())
            .select_from(ProjectDirectoryCompany)
            .where(
                ProjectDirectoryCompany.project_id == project_id,
                ProjectDirectoryCompany.company_id == company_id,
            )
        )
        or 0
    ) > 0


def search_vendors_fallback(
    project_id: uuid.UUID, q: str, limit: int = 20
) -> list[Company]:
    """When directory is empty, fall back to global vendor search."""
    q_norm = (q or "").strip().lower()
    limit = max(1, min(limit, 50))
    dir_count = (
        db.session.scalar(
            select(func.count())
            .select_from(ProjectDirectoryCompany)
            .where(ProjectDirectoryCompany.project_id == project_id)
        )
        or 0
    )
    if dir_count > 0:
        return []
    stmt = (
        select(Company)
        .where(
            Company.deleted_at.is_(None),
            Company.company_type.in_(tuple(PROCUREMENT_VENDOR_TYPES)),
        )
        .order_by(Company.name.asc())
        .limit(500)
    )
    rows = list(db.session.scalars(stmt).all())
    if q_norm:
        rows = [c for c in rows if q_norm in (c.name or "").lower()]
    return rows[:limit]
