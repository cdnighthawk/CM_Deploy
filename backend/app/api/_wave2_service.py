"""Sage CM Wave 2 list/create/patch/delete plus inbox, companies, and timecards."""
from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping, Type

from sqlalchemy import func, or_, select

from ..extensions import db
from ..models import (
    AnticipatedCost,
    Company,
    CompanyInsurancePolicy,
    CompanyLicense,
    Contact,
    HrmsTimesheetEntry,
    HrmsTimesheetPeriod,
    Issue,
    IssueCompany,
    Meeting,
    Project,
    PunchlistItem,
    PurchaseOrderChangeOrder,
    QcChecklist,
    Rfi,
    SafetyIncident,
    SubInvoice,
    Submittal,
    TimeEntry,
    Transmittal,
    WorkOrder,
    WorkflowAmountRule,
    WorkflowInstance,
    WorkflowInstanceStep,
)
from ._perms import CurrentUser, is_company_readonly
from ._rfi_service import ApiError

PROJECT_KINDS: dict[str, tuple[Type, str, str]] = {
    "transmittals": (Transmittal, "transmittals", "TRN"),
    "punchlist": (PunchlistItem, "punchlist_items", "PUN"),
    "work-orders": (WorkOrder, "work_orders", "WO"),
    "anticipated-costs": (AnticipatedCost, "anticipated_costs", "AC"),
    "po-change-orders": (PurchaseOrderChangeOrder, "purchase_order_change_orders", "POCO"),
    "sub-invoices": (SubInvoice, "sub_invoices", "SINV"),
    "meetings": (Meeting, "meetings", "MTG"),
    "safety-incidents": (SafetyIncident, "safety_incidents", "INC"),
    "qc-checklists": (QcChecklist, "qc_checklists", "QC"),
}


def _can_view(cu: CurrentUser) -> bool:
    return cu.is_dev_admin or cu.has_role("admin", "superuser", "standard") or is_company_readonly(cu)


def _can_mutate(cu: CurrentUser) -> bool:
    return cu.is_dev_admin or cu.has_role("admin", "superuser", "standard")


def _project(project_id: uuid.UUID) -> Project:
    proj = db.session.get(Project, project_id)
    if proj is None or proj.deleted_at is not None:
        raise ApiError("project not found", 404)
    return proj


def _jsonable(val: Any) -> Any:
    if val is None:
        return None
    if isinstance(val, uuid.UUID):
        return str(val)
    if isinstance(val, datetime):
        return val.isoformat()
    if isinstance(val, date):
        return val.isoformat()
    if isinstance(val, Decimal):
        return float(val)
    if isinstance(val, (list, dict, bool, int, float, str)):
        return val
    return str(val)


def serialize_row(row) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for col in row.__table__.columns:
        out[col.name] = _jsonable(getattr(row, col.name))
    return out


def _next_number(model, project_id: uuid.UUID, prefix: str) -> str:
    n = db.session.scalar(select(func.count()).select_from(model).where(model.project_id == project_id)) or 0
    return f"{prefix}-{int(n) + 1:03d}"


def _parse_date(raw: Any) -> date | None:
    if raw is None or raw == "":
        return None
    if isinstance(raw, date) and not isinstance(raw, datetime):
        return raw
    try:
        return date.fromisoformat(str(raw).strip()[:10])
    except ValueError as e:
        raise ApiError(f"invalid date: {raw}") from e


def _parse_uuid(raw: Any) -> uuid.UUID | None:
    if raw is None or raw == "":
        return None
    try:
        return uuid.UUID(str(raw).strip())
    except ValueError as e:
        raise ApiError("invalid id") from e


def _apply_fields(row, data: Mapping[str, Any]) -> None:
    skip = {"id", "project_id", "created_at", "updated_at"}
    for col in row.__table__.columns:
        name = col.name
        if name in skip or name not in data:
            continue
        raw = data.get(name)
        try:
            pytype = col.type.python_type
        except (NotImplementedError, AttributeError):
            pytype = type(raw) if isinstance(raw, (list, dict)) else str
        if raw is None or raw == "":
            setattr(row, name, None if col.nullable else getattr(row, name))
            continue
        if pytype is date:
            setattr(row, name, _parse_date(raw))
        elif pytype is uuid.UUID:
            setattr(row, name, _parse_uuid(raw))
        elif pytype is Decimal:
            try:
                setattr(row, name, Decimal(str(raw).replace(",", "")))
            except (InvalidOperation, ValueError) as e:
                raise ApiError(f"invalid {name}") from e
        elif pytype is bool:
            setattr(row, name, bool(raw) if not isinstance(raw, str) else raw.strip().lower() in ("1", "true", "yes"))
        elif pytype is int:
            setattr(row, name, int(raw))
        elif pytype in (list, dict):
            setattr(row, name, raw if isinstance(raw, (list, dict)) else [])
        else:
            setattr(row, name, str(raw)[:500] if name in ("subject", "title") else (str(raw) if raw is not None else None))


def list_project_kind(project_id: uuid.UUID, kind: str, cu: CurrentUser) -> dict[str, Any]:
    if not _can_view(cu):
        raise ApiError("forbidden", 403)
    _project(project_id)
    spec = PROJECT_KINDS.get(kind)
    if spec is None:
        raise ApiError("unknown kind", 400)
    model, entity, _prefix = spec
    rows = db.session.scalars(select(model).where(model.project_id == project_id).order_by(model.created_at.desc())).all()
    return {"entity": entity, "items": [serialize_row(r) for r in rows]}


def create_project_kind(project_id: uuid.UUID, kind: str, data: Mapping[str, Any], cu: CurrentUser) -> dict[str, Any]:
    if not _can_mutate(cu):
        raise ApiError("forbidden", 403)
    _project(project_id)
    spec = PROJECT_KINDS.get(kind)
    if spec is None:
        raise ApiError("unknown kind", 400)
    model, entity, prefix = spec
    row = model(project_id=project_id)
    if getattr(row, "id", None) is None:
        row.id = uuid.uuid4()
    _apply_fields(row, data)
    title = getattr(row, "subject", None) or getattr(row, "title", None)
    if not title:
        raise ApiError("subject or title is required")
    if kind == "po-change-orders" and not getattr(row, "commitment_id", None):
        raise ApiError("commitment_id is required")
    if hasattr(row, "number") and not getattr(row, "number", None):
        row.number = _next_number(model, project_id, prefix)
    db.session.add(row)
    db.session.commit()
    return {"item": serialize_row(row), "entity": entity}


def patch_project_kind(
    project_id: uuid.UUID, kind: str, row_id: uuid.UUID, data: Mapping[str, Any], cu: CurrentUser
) -> dict[str, Any]:
    if not _can_mutate(cu):
        raise ApiError("forbidden", 403)
    spec = PROJECT_KINDS.get(kind)
    if spec is None:
        raise ApiError("unknown kind", 400)
    model, entity, _prefix = spec
    row = db.session.get(model, row_id)
    if row is None or row.project_id != project_id:
        raise ApiError("not found", 404)
    _apply_fields(row, data)
    db.session.commit()
    return {"item": serialize_row(row), "entity": entity}


def delete_project_kind(project_id: uuid.UUID, kind: str, row_id: uuid.UUID, cu: CurrentUser) -> None:
    if not _can_mutate(cu):
        raise ApiError("forbidden", 403)
    spec = PROJECT_KINDS.get(kind)
    if spec is None:
        raise ApiError("unknown kind", 400)
    model, _entity, _prefix = spec
    row = db.session.get(model, row_id)
    if row is None or row.project_id != project_id:
        raise ApiError("not found", 404)
    db.session.delete(row)
    db.session.commit()


def list_companies(cu: CurrentUser, q: str = "", limit: int = 50) -> dict[str, Any]:
    if not _can_view(cu):
        raise ApiError("forbidden", 403)
    stmt = select(Company).where(Company.deleted_at.is_(None)).order_by(Company.name.asc())
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(Company.name.ilike(like), Company.email.ilike(like)))
    rows = db.session.scalars(stmt.limit(max(1, min(limit, 200)))).all()
    return {"entity": "companies", "items": [_company_public(c) for c in rows]}


def _company_public(c: Company) -> dict[str, Any]:
    return {
        "id": str(c.id),
        "name": c.name,
        "company_type": c.company_type,
        "phone": c.phone,
        "email": c.email,
        "city": c.city,
        "state": c.state,
        "website": c.website,
        "notes": c.notes,
    }


def create_company(data: Mapping[str, Any], cu: CurrentUser) -> dict[str, Any]:
    if not _can_mutate(cu):
        raise ApiError("forbidden", 403)
    name = str(data.get("name") or "").strip()
    if not name:
        raise ApiError("name is required")
    ctype = str(data.get("company_type") or "other").strip() or "other"
    row = Company(name=name[:255], company_type=ctype)
    for key in ("phone", "email", "website", "city", "state", "postal_code", "address_line1", "notes"):
        if key in data:
            setattr(row, key, (str(data.get(key) or "").strip() or None))
    db.session.add(row)
    db.session.commit()
    return {"item": _company_public(row), "entity": "company"}


def patch_company(company_id: uuid.UUID, data: Mapping[str, Any], cu: CurrentUser) -> dict[str, Any]:
    if not _can_mutate(cu):
        raise ApiError("forbidden", 403)
    row = db.session.get(Company, company_id)
    if row is None or row.deleted_at is not None:
        raise ApiError("company not found", 404)
    for key in ("name", "company_type", "phone", "email", "website", "city", "state", "postal_code", "address_line1", "notes"):
        if key in data:
            val = str(data.get(key) or "").strip() or None
            if key == "name" and not val:
                raise ApiError("name is required")
            setattr(row, key, val)
    db.session.commit()
    return {"item": _company_public(row), "entity": "company"}


def list_contacts(company_id: uuid.UUID, cu: CurrentUser) -> dict[str, Any]:
    if not _can_view(cu):
        raise ApiError("forbidden", 403)
    if db.session.get(Company, company_id) is None:
        raise ApiError("company not found", 404)
    rows = db.session.scalars(
        select(Contact).where(Contact.company_id == company_id).order_by(Contact.last_name, Contact.first_name)
    ).all()
    return {
        "entity": "contacts",
        "items": [
            {
                "id": str(c.id),
                "company_id": str(c.company_id) if c.company_id else None,
                "first_name": c.first_name,
                "last_name": c.last_name,
                "title": c.title,
                "email": c.email,
                "phone": c.phone,
                "is_primary": c.is_primary,
            }
            for c in rows
        ],
    }


def create_contact(company_id: uuid.UUID, data: Mapping[str, Any], cu: CurrentUser) -> dict[str, Any]:
    if not _can_mutate(cu):
        raise ApiError("forbidden", 403)
    if db.session.get(Company, company_id) is None:
        raise ApiError("company not found", 404)
    row = Contact(company_id=company_id)
    for key in ("first_name", "last_name", "title", "email", "phone", "mobile", "notes"):
        if key in data:
            setattr(row, key, (str(data.get(key) or "").strip() or None))
    if "is_primary" in data:
        row.is_primary = bool(data.get("is_primary"))
    db.session.add(row)
    db.session.commit()
    return list_contacts(company_id, cu)


def list_company_docs(company_id: uuid.UUID, kind: str, cu: CurrentUser) -> dict[str, Any]:
    if not _can_view(cu):
        raise ApiError("forbidden", 403)
    if db.session.get(Company, company_id) is None:
        raise ApiError("company not found", 404)
    model = CompanyInsurancePolicy if kind == "insurance" else CompanyLicense
    rows = db.session.scalars(select(model).where(model.company_id == company_id).order_by(model.created_at.desc())).all()
    return {"entity": kind, "items": [serialize_row(r) for r in rows]}


def create_company_doc(company_id: uuid.UUID, kind: str, data: Mapping[str, Any], cu: CurrentUser) -> dict[str, Any]:
    if not _can_mutate(cu):
        raise ApiError("forbidden", 403)
    if db.session.get(Company, company_id) is None:
        raise ApiError("company not found", 404)
    model = CompanyInsurancePolicy if kind == "insurance" else CompanyLicense
    row = model(company_id=company_id)
    if getattr(row, "id", None) is None:
        row.id = uuid.uuid4()
    _apply_fields(row, data)
    db.session.add(row)
    db.session.commit()
    return {"item": serialize_row(row), "entity": kind}


def delete_company_doc(company_id: uuid.UUID, kind: str, row_id: uuid.UUID, cu: CurrentUser) -> None:
    if not _can_mutate(cu):
        raise ApiError("forbidden", 403)
    model = CompanyInsurancePolicy if kind == "insurance" else CompanyLicense
    row = db.session.get(model, row_id)
    if row is None or row.company_id != company_id:
        raise ApiError("not found", 404)
    db.session.delete(row)
    db.session.commit()


def list_amount_rules(cu: CurrentUser) -> dict[str, Any]:
    if not _can_view(cu):
        raise ApiError("forbidden", 403)
    rows = db.session.scalars(select(WorkflowAmountRule).order_by(WorkflowAmountRule.min_amount.asc())).all()
    return {"entity": "workflow_amount_rules", "items": [serialize_row(r) for r in rows]}


def create_amount_rule(data: Mapping[str, Any], cu: CurrentUser) -> dict[str, Any]:
    if not _can_mutate(cu):
        raise ApiError("forbidden", 403)
    ttype = str(data.get("transaction_type") or "").strip()
    if not ttype:
        raise ApiError("transaction_type is required")
    row = WorkflowAmountRule(transaction_type=ttype)
    if getattr(row, "id", None) is None:
        row.id = uuid.uuid4()
    _apply_fields(row, data)
    db.session.add(row)
    db.session.commit()
    return {"item": serialize_row(row), "entity": "workflow_amount_rule"}


def matching_amount_rules(transaction_type: str, amount: Decimal) -> list[WorkflowAmountRule]:
    rows = db.session.scalars(
        select(WorkflowAmountRule).where(
            WorkflowAmountRule.transaction_type == transaction_type,
            WorkflowAmountRule.is_active.is_(True),
            WorkflowAmountRule.min_amount <= amount,
        )
    ).all()
    return list(rows)


def set_issue_companies(issue_id: uuid.UUID, company_ids: list[Any], cu: CurrentUser) -> dict[str, Any]:
    if not _can_mutate(cu):
        raise ApiError("forbidden", 403)
    issue = db.session.get(Issue, issue_id)
    if issue is None:
        raise ApiError("issue not found", 404)
    existing = db.session.scalars(select(IssueCompany).where(IssueCompany.issue_id == issue_id)).all()
    for row in existing:
        db.session.delete(row)
    for raw in company_ids:
        cid = _parse_uuid(raw.get("company_id") if isinstance(raw, Mapping) else raw)
        if not cid:
            continue
        if db.session.get(Company, cid) is None:
            continue
        role = raw.get("role") if isinstance(raw, Mapping) else None
        db.session.add(IssueCompany(issue_id=issue_id, company_id=cid, role=(str(role).strip()[:80] if role else None)))
    db.session.commit()
    return list_issue_companies(issue_id, cu)


def list_issue_companies(issue_id: uuid.UUID, cu: CurrentUser) -> dict[str, Any]:
    if not _can_view(cu):
        raise ApiError("forbidden", 403)
    rows = db.session.scalars(select(IssueCompany).where(IssueCompany.issue_id == issue_id)).all()
    items = []
    for row in rows:
        company = db.session.get(Company, row.company_id)
        items.append(
            {
                "id": str(row.id),
                "company_id": str(row.company_id),
                "name": company.name if company else None,
                "role": row.role,
            }
        )
    return {"entity": "issue_companies", "items": items}


def workflow_inbox(cu: CurrentUser) -> dict[str, Any]:
    if not _can_view(cu):
        raise ApiError("forbidden", 403)
    if not cu.id:
        return {"entity": "workflow_inbox", "items": []}
    rows = db.session.scalars(
        select(WorkflowInstanceStep)
        .where(
            WorkflowInstanceStep.assignee_user_id == cu.id,
            WorkflowInstanceStep.status.in_(("pending", "open")),
        )
        .order_by(WorkflowInstanceStep.created_at.desc())
        .limit(100)
    ).all()
    items = []
    for step in rows:
        inst = db.session.get(WorkflowInstance, step.instance_id) if getattr(step, "instance_id", None) else None
        items.append(
            {
                "id": str(step.id),
                "status": step.status,
                "subject_type": getattr(inst, "subject_type", None) if inst else None,
                "subject_id": str(inst.subject_id) if inst and inst.subject_id else None,
                "created_at": step.created_at.isoformat() if step.created_at else None,
            }
        )
    return {"entity": "workflow_inbox", "items": items}


def team_open_items(project_id: uuid.UUID, cu: CurrentUser) -> dict[str, Any]:
    if not _can_view(cu):
        raise ApiError("forbidden", 403)
    _project(project_id)
    items: list[dict[str, Any]] = []
    for rfi in db.session.scalars(
        select(Rfi).where(Rfi.project_id == project_id, Rfi.status.notin_(("closed", "closed_draft"))).limit(50)
    ).all():
        items.append({"kind": "rfi", "id": str(rfi.id), "title": rfi.subject or str(rfi.number), "status": rfi.status})
    for sub in db.session.scalars(
        select(Submittal).where(Submittal.project_id == project_id).limit(50)
    ).all():
        st = getattr(sub, "status", None) or ""
        if str(st).lower() in ("closed", "approved", "void"):
            continue
        items.append({"kind": "submittal", "id": str(sub.id), "title": getattr(sub, "title", None) or getattr(sub, "number", None), "status": st})
    for punch in db.session.scalars(
        select(PunchlistItem).where(PunchlistItem.project_id == project_id, PunchlistItem.status != "closed").limit(50)
    ).all():
        items.append({"kind": "punch", "id": str(punch.id), "title": punch.title, "status": punch.status})
    for iss in db.session.scalars(
        select(Issue).where(Issue.project_id == project_id, Issue.status.notin_(("Closed", "Resolved", "Done"))).limit(50)
    ).all():
        items.append({"kind": "issue", "id": str(iss.id), "title": iss.title, "status": iss.status})
    soon = date.today() + timedelta(days=30)
    for pol in db.session.scalars(select(CompanyInsurancePolicy).where(CompanyInsurancePolicy.expires_on.is_not(None)).limit(100)).all():
        if pol.expires_on and pol.expires_on <= soon:
            items.append(
                {
                    "kind": "insurance",
                    "id": str(pol.id),
                    "title": f"{pol.policy_type or 'Policy'} expires {pol.expires_on.isoformat()}",
                    "status": "expiring",
                }
            )
    return {"entity": "open_items", "items": items}


def convert_clock_to_timecard(cu: CurrentUser, data: Mapping[str, Any]) -> dict[str, Any]:
    if not _can_mutate(cu):
        raise ApiError("forbidden", 403)
    if not cu.id:
        raise ApiError("sign in required", 401)
    start = _parse_date(data.get("period_start")) or date.today() - timedelta(days=date.today().weekday())
    end = _parse_date(data.get("period_end")) or start + timedelta(days=6)
    period = db.session.scalar(
        select(HrmsTimesheetPeriod).where(
            HrmsTimesheetPeriod.user_id == cu.id,
            HrmsTimesheetPeriod.period_start == start,
        )
    )
    if period is None:
        period = HrmsTimesheetPeriod(user_id=cu.id, period_start=start, period_end=end, status="draft")
        db.session.add(period)
        db.session.flush()
    entries = db.session.scalars(
        select(TimeEntry).where(
            TimeEntry.user_id == cu.id,
            TimeEntry.status == "closed",
            TimeEntry.started_at >= datetime.combine(start, datetime.min.time()).replace(tzinfo=timezone.utc),
            TimeEntry.started_at < datetime.combine(end + timedelta(days=1), datetime.min.time()).replace(tzinfo=timezone.utc),
        )
    ).all()
    created = 0
    for ent in entries:
        already = db.session.scalar(select(HrmsTimesheetEntry).where(HrmsTimesheetEntry.time_entry_id == ent.id))
        if already:
            continue
        hours = Decimal("0")
        if ent.ended_at and ent.started_at:
            hours = Decimal(str(round((ent.ended_at - ent.started_at).total_seconds() / 3600, 2)))
        row = HrmsTimesheetEntry(
            period_id=period.id,
            work_date=ent.started_at.date(),
            hours_worked=hours,
            notes=ent.note,
            project_id=ent.project_id,
            cost_code_id=ent.cost_code_id,
            time_entry_id=ent.id,
        )
        db.session.add(row)
        created += 1
    db.session.commit()
    rows = db.session.scalars(select(HrmsTimesheetEntry).where(HrmsTimesheetEntry.period_id == period.id)).all()
    return {
        "entity": "timesheet_period",
        "item": {
            "id": str(period.id),
            "period_start": period.period_start.isoformat(),
            "period_end": period.period_end.isoformat(),
            "status": period.status,
            "converted": created,
            "entries": [
                {
                    "id": str(e.id),
                    "work_date": e.work_date.isoformat(),
                    "hours_worked": float(e.hours_worked),
                    "project_id": str(e.project_id) if e.project_id else None,
                    "cost_code_id": str(e.cost_code_id) if e.cost_code_id else None,
                    "notes": e.notes,
                }
                for e in rows
            ],
        },
    }
