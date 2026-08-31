"""CPR, owner CO, and SCO CRUD (Sage CM Wave 1)."""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping

from sqlalchemy import func, select

from ..extensions import db
from ..models import (
    ChangeProposalRequest,
    ChangeProposalRequestItem,
    Commitment,
    Company,
    CostCode,
    OwnerChangeOrder,
    OwnerChangeOrderItem,
    Project,
    ProjectContract,
    SubcontractChangeOrder,
    SubcontractChangeOrderItem,
)
from ._perms import CurrentUser, is_company_readonly
from ._rfi_service import ApiError

CHANGE_STATUSES = frozenset({"draft", "pending_submission", "pending", "not_approved", "approved"})
RESOURCES = frozenset({"material", "labor", "equipment", "subcontractor", "other"})


def _can_view(cu: CurrentUser) -> bool:
    return cu.is_dev_admin or cu.has_role("admin", "superuser", "standard") or is_company_readonly(cu)


def _can_mutate(cu: CurrentUser) -> bool:
    return cu.is_dev_admin or cu.has_role("admin", "superuser", "standard")


def _project(project_id: uuid.UUID) -> Project:
    proj = db.session.get(Project, project_id)
    if proj is None or proj.deleted_at is not None:
        raise ApiError("project not found", 404)
    return proj


def _parse_date(raw: Any) -> date | None:
    if raw is None or raw == "":
        return None
    if isinstance(raw, date):
        return raw
    try:
        return date.fromisoformat(str(raw).strip()[:10])
    except ValueError as e:
        raise ApiError(f"invalid date: {raw}") from e


def _dec(raw: Any, field: str, default: str | None = "0") -> Decimal:
    if raw is None or raw == "":
        if default is None:
            raise ApiError(f"{field} is required")
        return Decimal(default)
    try:
        return Decimal(str(raw).replace(",", "").strip())
    except (InvalidOperation, ValueError) as e:
        raise ApiError(f"invalid {field}") from e


def _uuid(raw: Any) -> uuid.UUID | None:
    if raw is None or raw == "":
        return None
    try:
        return uuid.UUID(str(raw).strip())
    except ValueError as e:
        raise ApiError("invalid id") from e


def _money(v: Decimal | None) -> float:
    return float((v or Decimal("0")).quantize(Decimal("0.01")))


def _next_number(model, project_id: uuid.UUID, prefix: str) -> str:
    n = db.session.scalar(select(func.count()).select_from(model).where(model.project_id == project_id)) or 0
    return f"{prefix}-{int(n) + 1:03d}"


def _item_total(qty: Decimal, price: Decimal) -> Decimal:
    return (qty * price).quantize(Decimal("0.01"))


def _apply_items(parent_items, raw_items: Any, item_cls, fk_name: str, parent_id: uuid.UUID) -> None:
    parent_items.clear()
    db.session.flush()
    if not isinstance(raw_items, list):
        return
    for i, raw in enumerate(raw_items):
        if not isinstance(raw, Mapping):
            continue
        qty = _dec(raw.get("quantity"), "quantity")
        price = _dec(raw.get("unit_price", raw.get("unit_cost")), "unit_price")
        cc = _uuid(raw.get("cost_code_id"))
        if cc and db.session.get(CostCode, cc) is None:
            raise ApiError("cost_code_id not found", 400)
        res = (str(raw.get("resource") or "").strip() or None)
        if res and res not in RESOURCES:
            raise ApiError("invalid resource")
        row = item_cls(
            **{fk_name: parent_id},
            cost_code_id=cc,
            sort_order=int(raw.get("sort_order") or i),
            description=str(raw.get("description") or "").strip()[:500],
            quantity=qty,
            unit=(str(raw.get("unit") or "").strip()[:40] or None),
            unit_price=price,
            line_total=_item_total(qty, price),
            resource=res,
        )
        db.session.add(row)


def _serialize_item(it) -> dict[str, Any]:
    return {
        "id": str(it.id),
        "cost_code_id": str(it.cost_code_id) if it.cost_code_id else None,
        "sort_order": it.sort_order,
        "description": it.description,
        "quantity": float(it.quantity),
        "unit": it.unit,
        "unit_price": float(it.unit_price),
        "line_total": _money(it.line_total),
        "resource": it.resource,
    }


def _header_common(row) -> dict[str, Any]:
    items = list(row.items or [])
    total = sum((it.line_total or Decimal("0")) for it in items)
    return {
        "id": str(row.id),
        "project_id": str(row.project_id),
        "number": row.number,
        "subject": row.subject,
        "status": row.status,
        "status_date": row.status_date.isoformat() if row.status_date else None,
        "issue_date": row.issue_date.isoformat() if row.issue_date else None,
        "notes": row.notes,
        "amount": _money(total),
        "items": [_serialize_item(it) for it in items],
    }


def _apply_header(row, data: Mapping[str, Any]) -> None:
    if "subject" in data:
        row.subject = str(data.get("subject") or "").strip()[:500]
    if "status" in data:
        st = str(data.get("status") or "").strip()
        if st not in CHANGE_STATUSES:
            raise ApiError("invalid status")
        row.status = st
        if st == "approved" and not row.status_date:
            row.status_date = date.today()
    if "status_date" in data:
        row.status_date = _parse_date(data.get("status_date"))
    if "issue_date" in data:
        row.issue_date = _parse_date(data.get("issue_date"))
    if "notes" in data:
        row.notes = None if data.get("notes") is None else (str(data.get("notes")).strip() or None)
    if "schedule_impact_days" in data and hasattr(row, "schedule_impact_days"):
        raw = data.get("schedule_impact_days")
        row.schedule_impact_days = None if raw in (None, "") else int(raw)


def list_cprs(project_id: uuid.UUID, cu: CurrentUser) -> dict[str, Any]:
    if not _can_view(cu):
        raise ApiError("forbidden", 403)
    _project(project_id)
    rows = db.session.scalars(
        select(ChangeProposalRequest)
        .where(ChangeProposalRequest.project_id == project_id)
        .order_by(ChangeProposalRequest.created_at.desc())
    ).all()
    return {"entity": "change_proposal_requests", "items": [_serialize_cpr(r) for r in rows]}


def _serialize_cpr(row: ChangeProposalRequest) -> dict[str, Any]:
    out = _header_common(row)
    out["prime_contract_id"] = str(row.prime_contract_id) if row.prime_contract_id else None
    out["response_due_date"] = row.response_due_date.isoformat() if row.response_due_date else None
    out["impacted_company_id"] = str(row.impacted_company_id) if row.impacted_company_id else None
    out["impacted_company_name"] = row.impacted_company.name if row.impacted_company else None
    out["schedule_impact_days"] = row.schedule_impact_days
    return out


def create_cpr(project_id: uuid.UUID, data: Mapping[str, Any], cu: CurrentUser) -> dict[str, Any]:
    if not _can_mutate(cu):
        raise ApiError("forbidden", 403)
    _project(project_id)
    subject = str(data.get("subject") or "").strip()
    if not subject:
        raise ApiError("subject is required")
    row = ChangeProposalRequest(
        project_id=project_id,
        subject=subject[:500],
        number=str(data.get("number") or "").strip() or _next_number(ChangeProposalRequest, project_id, "CPR"),
        created_by_user_id=cu.id,
    )
    _apply_header(row, data)
    if "response_due_date" in data:
        row.response_due_date = _parse_date(data.get("response_due_date"))
    if "impacted_company_id" in data:
        cid = _uuid(data.get("impacted_company_id"))
        if cid and db.session.get(Company, cid) is None:
            raise ApiError("impacted company not found", 400)
        row.impacted_company_id = cid
    if "prime_contract_id" in data:
        pcid = _uuid(data.get("prime_contract_id"))
        if pcid and db.session.get(ProjectContract, pcid) is None:
            raise ApiError("prime contract not found", 400)
        row.prime_contract_id = pcid
    db.session.add(row)
    db.session.flush()
    _apply_items(row.items, data.get("items"), ChangeProposalRequestItem, "cpr_id", row.id)
    db.session.commit()
    return {"item": _serialize_cpr(row), "entity": "change_proposal_request"}


def patch_cpr(project_id: uuid.UUID, cpr_id: uuid.UUID, data: Mapping[str, Any], cu: CurrentUser) -> dict[str, Any]:
    if not _can_mutate(cu):
        raise ApiError("forbidden", 403)
    row = db.session.get(ChangeProposalRequest, cpr_id)
    if row is None or row.project_id != project_id:
        raise ApiError("CPR not found", 404)
    _apply_header(row, data)
    if "response_due_date" in data:
        row.response_due_date = _parse_date(data.get("response_due_date"))
    if "impacted_company_id" in data:
        row.impacted_company_id = _uuid(data.get("impacted_company_id"))
    if "number" in data and data.get("number"):
        row.number = str(data.get("number")).strip()[:40]
    if "items" in data:
        _apply_items(row.items, data.get("items"), ChangeProposalRequestItem, "cpr_id", row.id)
    db.session.commit()
    return {"item": _serialize_cpr(row), "entity": "change_proposal_request"}


def delete_cpr(project_id: uuid.UUID, cpr_id: uuid.UUID, cu: CurrentUser) -> None:
    if not _can_mutate(cu):
        raise ApiError("forbidden", 403)
    row = db.session.get(ChangeProposalRequest, cpr_id)
    if row is None or row.project_id != project_id:
        raise ApiError("CPR not found", 404)
    db.session.delete(row)
    db.session.commit()


def list_cos(project_id: uuid.UUID, cu: CurrentUser) -> dict[str, Any]:
    if not _can_view(cu):
        raise ApiError("forbidden", 403)
    _project(project_id)
    rows = db.session.scalars(
        select(OwnerChangeOrder)
        .where(OwnerChangeOrder.project_id == project_id)
        .order_by(OwnerChangeOrder.created_at.desc())
    ).all()
    return {"entity": "owner_change_orders", "items": [_serialize_co(r) for r in rows]}


def _serialize_co(row: OwnerChangeOrder) -> dict[str, Any]:
    out = _header_common(row)
    out["prime_contract_id"] = str(row.prime_contract_id) if row.prime_contract_id else None
    out["cpr_id"] = str(row.cpr_id) if row.cpr_id else None
    out["schedule_impact_days"] = row.schedule_impact_days
    return out


def create_co(project_id: uuid.UUID, data: Mapping[str, Any], cu: CurrentUser) -> dict[str, Any]:
    if not _can_mutate(cu):
        raise ApiError("forbidden", 403)
    _project(project_id)
    subject = str(data.get("subject") or "").strip()
    cpr = None
    cpr_id = _uuid(data.get("cpr_id"))
    if cpr_id:
        cpr = db.session.get(ChangeProposalRequest, cpr_id)
        if cpr is None or cpr.project_id != project_id:
            raise ApiError("CPR not found", 404)
        if not subject:
            subject = cpr.subject
    if not subject:
        raise ApiError("subject is required")
    row = OwnerChangeOrder(
        project_id=project_id,
        subject=subject[:500],
        number=str(data.get("number") or "").strip() or _next_number(OwnerChangeOrder, project_id, "CO"),
        cpr_id=cpr_id,
        created_by_user_id=cu.id,
    )
    _apply_header(row, data)
    if "prime_contract_id" in data:
        row.prime_contract_id = _uuid(data.get("prime_contract_id"))
    elif cpr is not None:
        row.prime_contract_id = cpr.prime_contract_id
        row.schedule_impact_days = cpr.schedule_impact_days
    db.session.add(row)
    db.session.flush()
    items = data.get("items")
    if items is None and cpr is not None:
        items = [
            {
                "cost_code_id": str(it.cost_code_id) if it.cost_code_id else None,
                "description": it.description,
                "quantity": float(it.quantity),
                "unit": it.unit,
                "unit_price": float(it.unit_price),
                "resource": it.resource,
                "sort_order": it.sort_order,
            }
            for it in cpr.items
        ]
    _apply_items(row.items, items, OwnerChangeOrderItem, "change_order_id", row.id)
    db.session.commit()
    return {"item": _serialize_co(row), "entity": "owner_change_order"}


def patch_co(project_id: uuid.UUID, co_id: uuid.UUID, data: Mapping[str, Any], cu: CurrentUser) -> dict[str, Any]:
    if not _can_mutate(cu):
        raise ApiError("forbidden", 403)
    row = db.session.get(OwnerChangeOrder, co_id)
    if row is None or row.project_id != project_id:
        raise ApiError("change order not found", 404)
    _apply_header(row, data)
    if "number" in data and data.get("number"):
        row.number = str(data.get("number")).strip()[:40]
    if "items" in data:
        _apply_items(row.items, data.get("items"), OwnerChangeOrderItem, "change_order_id", row.id)
    db.session.commit()
    return {"item": _serialize_co(row), "entity": "owner_change_order"}


def delete_co(project_id: uuid.UUID, co_id: uuid.UUID, cu: CurrentUser) -> None:
    if not _can_mutate(cu):
        raise ApiError("forbidden", 403)
    row = db.session.get(OwnerChangeOrder, co_id)
    if row is None or row.project_id != project_id:
        raise ApiError("change order not found", 404)
    db.session.delete(row)
    db.session.commit()


def list_scos(project_id: uuid.UUID, cu: CurrentUser, commitment_id: uuid.UUID | None = None) -> dict[str, Any]:
    if not _can_view(cu):
        raise ApiError("forbidden", 403)
    _project(project_id)
    stmt = select(SubcontractChangeOrder).where(SubcontractChangeOrder.project_id == project_id)
    if commitment_id:
        stmt = stmt.where(SubcontractChangeOrder.commitment_id == commitment_id)
    rows = db.session.scalars(stmt.order_by(SubcontractChangeOrder.created_at.desc())).all()
    return {"entity": "subcontract_change_orders", "items": [_serialize_sco(r) for r in rows]}


def _serialize_sco(row: SubcontractChangeOrder) -> dict[str, Any]:
    out = _header_common(row)
    out["commitment_id"] = str(row.commitment_id)
    return out


def create_sco(project_id: uuid.UUID, data: Mapping[str, Any], cu: CurrentUser) -> dict[str, Any]:
    if not _can_mutate(cu):
        raise ApiError("forbidden", 403)
    _project(project_id)
    cid = _uuid(data.get("commitment_id"))
    if not cid:
        raise ApiError("commitment_id is required")
    comm = db.session.get(Commitment, cid)
    if comm is None or comm.project_id != project_id:
        raise ApiError("commitment not found", 404)
    if comm.commitment_kind != "subcontract":
        raise ApiError("SCO requires a subcontract")
    subject = str(data.get("subject") or "").strip()
    if not subject:
        raise ApiError("subject is required")
    row = SubcontractChangeOrder(
        project_id=project_id,
        commitment_id=cid,
        subject=subject[:500],
        number=str(data.get("number") or "").strip() or _next_number(SubcontractChangeOrder, project_id, "SCO"),
        created_by_user_id=cu.id,
    )
    _apply_header(row, data)
    db.session.add(row)
    db.session.flush()
    _apply_items(row.items, data.get("items"), SubcontractChangeOrderItem, "sco_id", row.id)
    db.session.commit()
    return {"item": _serialize_sco(row), "entity": "subcontract_change_order"}


def patch_sco(project_id: uuid.UUID, sco_id: uuid.UUID, data: Mapping[str, Any], cu: CurrentUser) -> dict[str, Any]:
    if not _can_mutate(cu):
        raise ApiError("forbidden", 403)
    row = db.session.get(SubcontractChangeOrder, sco_id)
    if row is None or row.project_id != project_id:
        raise ApiError("SCO not found", 404)
    _apply_header(row, data)
    if "number" in data and data.get("number"):
        row.number = str(data.get("number")).strip()[:40]
    if "items" in data:
        _apply_items(row.items, data.get("items"), SubcontractChangeOrderItem, "sco_id", row.id)
    db.session.commit()
    return {"item": _serialize_sco(row), "entity": "subcontract_change_order"}


def delete_sco(project_id: uuid.UUID, sco_id: uuid.UUID, cu: CurrentUser) -> None:
    if not _can_mutate(cu):
        raise ApiError("forbidden", 403)
    row = db.session.get(SubcontractChangeOrder, sco_id)
    if row is None or row.project_id != project_id:
        raise ApiError("SCO not found", 404)
    db.session.delete(row)
    db.session.commit()
