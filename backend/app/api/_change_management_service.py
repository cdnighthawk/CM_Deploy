"""CPR, owner CO, and SCO CRUD (Sage CM Wave 1)."""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping

from flask import request
from sqlalchemy import func, select

from ..extensions import db
from ..models import (
    AuditLog,
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
from ..models.change_management import CPR_STATUSES, PRIME_CO_STATUSES, SCO_STATUSES
from ._perms import CurrentUser, is_company_readonly
from ._rfi_service import ApiError

CHANGE_STATUSES = frozenset({"draft", "pending_submission", "pending", "not_approved", "approved"})
CPR_STATUS_SET = frozenset(CPR_STATUSES)
PRIME_CO_STATUS_SET = frozenset(PRIME_CO_STATUSES)
SCO_STATUS_SET = frozenset(SCO_STATUSES)
CPR_ORIGINS = frozenset({"tm_ticket", "rfi", "field_condition", "gc_request", "other"})
RESOURCES = frozenset({"material", "labor", "equipment", "subcontractor", "other"})


def _audit(
    cu: CurrentUser,
    entity_type: str,
    entity_id: uuid.UUID,
    action: str,
    message: str,
    changes: dict[str, Any] | None = None,
) -> None:
    db.session.add(
        AuditLog(
            user_id=cu.id if cu else None,
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            message=message,
            changes=changes,
            ip_address=(request.remote_addr or "")[:45] if request else None,
            user_agent=(request.user_agent.string or "")[:500] if request else None,
        )
    )


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


def _apply_header(row, data: Mapping[str, Any], allowed: frozenset[str] = CHANGE_STATUSES) -> None:
    if "subject" in data:
        row.subject = str(data.get("subject") or "").strip()[:500]
    if "status" in data:
        st = str(data.get("status") or "").strip()
        if st not in allowed:
            raise ApiError("invalid status")
        if st != row.status:
            row.status = st
            if "status_date" not in data:
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


def _require_lines(raw_items: Any) -> None:
    if not isinstance(raw_items, list) or not raw_items:
        raise ApiError("at least one line item is required")


def _adjust_contract_value(contract: ProjectContract, delta: Decimal) -> None:
    current = Decimal(str(contract.contract_value or 0))
    nxt = (current + delta).quantize(Decimal("0.01"))
    contract.contract_value = float(nxt)
    if contract.is_primary:
        proj = db.session.get(Project, contract.project_id)
        if proj is not None:
            proj.contract_value = float(nxt)


def _sync_prime_contract_value(row: OwnerChangeOrder, amount: Decimal) -> None:
    should_apply = row.status == "approved" and bool(row.approved_revises_contract)
    applied = row.contract_value_applied
    if should_apply and (applied is None or applied == 0):
        if not row.prime_contract_id:
            raise ApiError("owner contract is required to revise contract value")
        contract = db.session.get(ProjectContract, row.prime_contract_id)
        if contract is None or contract.project_id != row.project_id:
            raise ApiError("owner contract not found", 400)
        _adjust_contract_value(contract, amount)
        row.contract_value_applied = amount
    elif (not should_apply) and applied:
        if row.prime_contract_id:
            contract = db.session.get(ProjectContract, row.prime_contract_id)
            if contract is not None:
                _adjust_contract_value(contract, -Decimal(str(applied)))
        row.contract_value_applied = None


def _sync_sco_value(row: SubcontractChangeOrder, amount: Decimal) -> None:
    applied = row.value_applied
    if row.status == "approved" and (applied is None or applied == 0):
        comm = db.session.get(Commitment, row.commitment_id)
        if comm is None:
            raise ApiError("subcontract not found", 404)
        current = Decimal(str(comm.total_amount or 0))
        comm.total_amount = (current + amount).quantize(Decimal("0.01"))
        row.value_applied = amount
    elif row.status != "approved" and applied:
        comm = db.session.get(Commitment, row.commitment_id)
        if comm is not None:
            current = Decimal(str(comm.total_amount or 0))
            comm.total_amount = (current - Decimal(str(applied))).quantize(Decimal("0.01"))
        row.value_applied = None


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


def _apply_cpr_extras(row: ChangeProposalRequest, data: Mapping[str, Any]) -> None:
    if "response_due_date" in data:
        row.response_due_date = _parse_date(data.get("response_due_date"))
    if "needed_by_date" in data:
        row.response_due_date = _parse_date(data.get("needed_by_date"))
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
    if "origin" in data:
        origin = str(data.get("origin") or "other").strip() or "other"
        if origin not in CPR_ORIGINS:
            raise ApiError("invalid origin")
        row.origin = origin
    if "source_tm_ticket_id" in data:
        row.source_tm_ticket_id = _uuid(data.get("source_tm_ticket_id"))
    if "source_rfi_id" in data:
        row.source_rfi_id = _uuid(data.get("source_rfi_id"))


def _serialize_cpr(row: ChangeProposalRequest) -> dict[str, Any]:
    out = _header_common(row)
    out["title"] = row.subject
    out["prime_contract_id"] = str(row.prime_contract_id) if row.prime_contract_id else None
    out["response_due_date"] = row.response_due_date.isoformat() if row.response_due_date else None
    out["needed_by_date"] = out["response_due_date"]
    out["impacted_company_id"] = str(row.impacted_company_id) if row.impacted_company_id else None
    out["impacted_company_name"] = row.impacted_company.name if row.impacted_company else None
    out["schedule_impact_days"] = row.schedule_impact_days
    out["origin"] = row.origin or "other"
    out["source_tm_ticket_id"] = str(row.source_tm_ticket_id) if row.source_tm_ticket_id else None
    out["source_rfi_id"] = str(row.source_rfi_id) if row.source_rfi_id else None
    linked = db.session.scalars(
        select(OwnerChangeOrder).where(OwnerChangeOrder.cpr_id == row.id).order_by(OwnerChangeOrder.created_at.desc())
    ).first()
    out["prime_co_id"] = str(linked.id) if linked else None
    out["prime_co_number"] = linked.number if linked else None
    return out


def get_cpr(project_id: uuid.UUID, cpr_id: uuid.UUID, cu: CurrentUser) -> dict[str, Any]:
    if not _can_view(cu):
        raise ApiError("forbidden", 403)
    row = db.session.get(ChangeProposalRequest, cpr_id)
    if row is None or row.project_id != project_id:
        raise ApiError("CPR not found", 404)
    return {"item": _serialize_cpr(row), "entity": "change_proposal_request"}


def create_cpr(project_id: uuid.UUID, data: Mapping[str, Any], cu: CurrentUser) -> dict[str, Any]:
    if not _can_mutate(cu):
        raise ApiError("forbidden", 403)
    _project(project_id)
    subject = str(data.get("subject") or data.get("title") or "").strip()
    if not subject:
        raise ApiError("subject is required")
    _require_lines(data.get("items"))
    row = ChangeProposalRequest(
        project_id=project_id,
        subject=subject[:500],
        number=str(data.get("number") or "").strip() or _next_number(ChangeProposalRequest, project_id, "CPR"),
        created_by_user_id=cu.id,
        origin="other",
    )
    _apply_header(row, data, CPR_STATUS_SET)
    _apply_cpr_extras(row, data)
    db.session.add(row)
    db.session.flush()
    _apply_items(row.items, data.get("items"), ChangeProposalRequestItem, "cpr_id", row.id)
    _audit(cu, "change_proposal_request", row.id, "create", f"Created CPR {row.number}", {"amount": _header_common(row)["amount"]})
    db.session.commit()
    return {"item": _serialize_cpr(row), "entity": "change_proposal_request"}


def patch_cpr(project_id: uuid.UUID, cpr_id: uuid.UUID, data: Mapping[str, Any], cu: CurrentUser) -> dict[str, Any]:
    if not _can_mutate(cu):
        raise ApiError("forbidden", 403)
    row = db.session.get(ChangeProposalRequest, cpr_id)
    if row is None or row.project_id != project_id:
        raise ApiError("CPR not found", 404)
    before_status = row.status
    before_amount = _header_common(row)["amount"]
    _apply_header(row, data, CPR_STATUS_SET)
    _apply_cpr_extras(row, data)
    if "number" in data and data.get("number"):
        row.number = str(data.get("number")).strip()[:40]
    if "items" in data:
        _require_lines(data.get("items"))
        _apply_items(row.items, data.get("items"), ChangeProposalRequestItem, "cpr_id", row.id)
    after = _serialize_cpr(row)
    if before_status != row.status:
        _audit(cu, "change_proposal_request", row.id, "status", f"CPR {row.number} {before_status} → {row.status}")
    if before_amount != after["amount"]:
        _audit(cu, "change_proposal_request", row.id, "amount", f"CPR {row.number} amount {before_amount} → {after['amount']}")
    db.session.commit()
    return {"item": after, "entity": "change_proposal_request"}


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
    out["title"] = row.subject
    out["prime_contract_id"] = str(row.prime_contract_id) if row.prime_contract_id else None
    contract = row.prime_contract
    out["contract_number"] = contract.contract_number if contract else None
    out["contract_title"] = contract.title if contract else None
    out["cpr_id"] = str(row.cpr_id) if row.cpr_id else None
    out["source_cpr_id"] = out["cpr_id"]
    out["schedule_impact_days"] = row.schedule_impact_days
    out["approved_revises_contract"] = bool(row.approved_revises_contract)
    out["contract_value_applied"] = _money(row.contract_value_applied) if row.contract_value_applied is not None else None
    out["source_tm_ticket_id"] = str(row.source_tm_ticket_id) if row.source_tm_ticket_id else None
    out["gc_company_id"] = str(row.gc_company_id) if row.gc_company_id else None
    gc = db.session.get(Company, row.gc_company_id) if row.gc_company_id else None
    out["gc_company_name"] = gc.name if gc else None
    out["revises_contract"] = bool(row.approved_revises_contract)
    return out


def get_co(project_id: uuid.UUID, co_id: uuid.UUID, cu: CurrentUser) -> dict[str, Any]:
    if not _can_view(cu):
        raise ApiError("forbidden", 403)
    row = db.session.get(OwnerChangeOrder, co_id)
    if row is None or row.project_id != project_id:
        raise ApiError("change order not found", 404)
    return {"item": _serialize_co(row), "entity": "owner_change_order"}


def _apply_co_extras(row: OwnerChangeOrder, data: Mapping[str, Any]) -> None:
    if "prime_contract_id" in data:
        row.prime_contract_id = _uuid(data.get("prime_contract_id"))
    if "approved_revises_contract" in data:
        raw = data.get("approved_revises_contract")
        if isinstance(raw, str):
            row.approved_revises_contract = raw.strip().lower() in ("1", "true", "yes", "on")
        else:
            row.approved_revises_contract = bool(raw)
    if "source_tm_ticket_id" in data:
        row.source_tm_ticket_id = _uuid(data.get("source_tm_ticket_id"))
    if "gc_company_id" in data:
        row.gc_company_id = _uuid(data.get("gc_company_id"))
    if "cpr_id" in data and data.get("cpr_id"):
        row.cpr_id = _uuid(data.get("cpr_id"))


def create_co(project_id: uuid.UUID, data: Mapping[str, Any], cu: CurrentUser) -> dict[str, Any]:
    if not _can_mutate(cu):
        raise ApiError("forbidden", 403)
    _project(project_id)
    subject = str(data.get("subject") or data.get("title") or "").strip()
    cpr = None
    cpr_id = _uuid(data.get("cpr_id") or data.get("source_cpr_id"))
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
    _apply_header(row, data, PRIME_CO_STATUS_SET)
    _apply_co_extras(row, data)
    if cpr is not None:
        if not row.prime_contract_id:
            row.prime_contract_id = cpr.prime_contract_id
        if row.schedule_impact_days is None:
            row.schedule_impact_days = cpr.schedule_impact_days
        if not row.gc_company_id:
            row.gc_company_id = cpr.impacted_company_id
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
    if not items:
        items = [{"description": subject[:500], "quantity": 1, "unit": "LS", "unit_price": 0}]
    _apply_items(row.items, items, OwnerChangeOrderItem, "change_order_id", row.id)
    amount = Decimal(str(_header_common(row)["amount"]))
    _sync_prime_contract_value(row, amount)
    _audit(cu, "owner_change_order", row.id, "create", f"Created prime CO {row.number}", {"amount": float(amount)})
    db.session.commit()
    return {"item": _serialize_co(row), "entity": "owner_change_order"}


def patch_co(project_id: uuid.UUID, co_id: uuid.UUID, data: Mapping[str, Any], cu: CurrentUser) -> dict[str, Any]:
    if not _can_mutate(cu):
        raise ApiError("forbidden", 403)
    row = db.session.get(OwnerChangeOrder, co_id)
    if row is None or row.project_id != project_id:
        raise ApiError("change order not found", 404)
    before_status = row.status
    before_amount = _header_common(row)["amount"]
    _apply_header(row, data, PRIME_CO_STATUS_SET)
    _apply_co_extras(row, data)
    if "number" in data and data.get("number"):
        row.number = str(data.get("number")).strip()[:40]
    if "items" in data:
        _require_lines(data.get("items"))
        _apply_items(row.items, data.get("items"), OwnerChangeOrderItem, "change_order_id", row.id)
    amount = Decimal(str(_header_common(row)["amount"]))
    _sync_prime_contract_value(row, amount)
    if before_status != row.status:
        _audit(cu, "owner_change_order", row.id, "status", f"Prime CO {row.number} {before_status} → {row.status}")
    if before_amount != float(amount):
        _audit(cu, "owner_change_order", row.id, "amount", f"Prime CO {row.number} amount {before_amount} → {float(amount)}")
    # TODO(workflow_engine_cursor.md): bind process_key=change_order when seeded; v1 uses status enum.
    db.session.commit()
    return {"item": _serialize_co(row), "entity": "owner_change_order"}


def convert_cpr_to_prime_co(project_id: uuid.UUID, cpr_id: uuid.UUID, cu: CurrentUser) -> dict[str, Any]:
    if not _can_mutate(cu):
        raise ApiError("forbidden", 403)
    cpr = db.session.get(ChangeProposalRequest, cpr_id)
    if cpr is None or cpr.project_id != project_id:
        raise ApiError("CPR not found", 404)
    if cpr.status not in ("accepted", "under_review", "approved"):
        raise ApiError("CPR must be accepted or under review to convert")
    existing = db.session.scalars(select(OwnerChangeOrder).where(OwnerChangeOrder.cpr_id == cpr.id)).first()
    if existing is not None:
        raise ApiError("CPR already converted")
    created = create_co(
        project_id,
        {
            "cpr_id": str(cpr.id),
            "subject": cpr.subject,
            "status": "draft",
            "prime_contract_id": str(cpr.prime_contract_id) if cpr.prime_contract_id else None,
            "approved_revises_contract": False,
            "items": [
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
            ],
        },
        cu,
    )
    cpr.status = "converted"
    cpr.status_date = date.today()
    _audit(cu, "change_proposal_request", cpr.id, "convert", f"Converted CPR {cpr.number} to prime CO")
    db.session.commit()
    created["cpr"] = _serialize_cpr(cpr)
    return created


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
    comm = row.commitment
    out["subcontract_number"] = (comm.reference_number or comm.title) if comm else None
    vendor = comm.vendor if comm else None
    out["vendor_name"] = vendor.name if vendor else None
    out["vendor_company_id"] = str(comm.vendor_company_id) if comm else None
    out["value_applied"] = _money(row.value_applied) if row.value_applied is not None else None
    return out


def get_sco(project_id: uuid.UUID, sco_id: uuid.UUID, cu: CurrentUser) -> dict[str, Any]:
    if not _can_view(cu):
        raise ApiError("forbidden", 403)
    row = db.session.get(SubcontractChangeOrder, sco_id)
    if row is None or row.project_id != project_id:
        raise ApiError("SCO not found", 404)
    return {"item": _serialize_sco(row), "entity": "subcontract_change_order"}


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
    _require_lines(data.get("items"))
    row = SubcontractChangeOrder(
        project_id=project_id,
        commitment_id=cid,
        subject=subject[:500],
        number=str(data.get("number") or "").strip() or _next_number(SubcontractChangeOrder, project_id, "SCO"),
        created_by_user_id=cu.id,
    )
    _apply_header(row, data, SCO_STATUS_SET)
    db.session.add(row)
    db.session.flush()
    _apply_items(row.items, data.get("items"), SubcontractChangeOrderItem, "sco_id", row.id)
    amount = Decimal(str(_header_common(row)["amount"]))
    _sync_sco_value(row, amount)
    _audit(cu, "subcontract_change_order", row.id, "create", f"Created SCO {row.number}", {"amount": float(amount)})
    db.session.commit()
    return {"item": _serialize_sco(row), "entity": "subcontract_change_order"}


def patch_sco(project_id: uuid.UUID, sco_id: uuid.UUID, data: Mapping[str, Any], cu: CurrentUser) -> dict[str, Any]:
    if not _can_mutate(cu):
        raise ApiError("forbidden", 403)
    row = db.session.get(SubcontractChangeOrder, sco_id)
    if row is None or row.project_id != project_id:
        raise ApiError("SCO not found", 404)
    before_status = row.status
    before_amount = _header_common(row)["amount"]
    _apply_header(row, data, SCO_STATUS_SET)
    if "number" in data and data.get("number"):
        row.number = str(data.get("number")).strip()[:40]
    if "commitment_id" in data:
        cid = _uuid(data.get("commitment_id"))
        if cid:
            comm = db.session.get(Commitment, cid)
            if comm is None or comm.project_id != project_id or comm.commitment_kind != "subcontract":
                raise ApiError("subcontract not found", 400)
            row.commitment_id = cid
    if "items" in data:
        _require_lines(data.get("items"))
        _apply_items(row.items, data.get("items"), SubcontractChangeOrderItem, "sco_id", row.id)
    amount = Decimal(str(_header_common(row)["amount"]))
    _sync_sco_value(row, amount)
    if before_status != row.status:
        _audit(cu, "subcontract_change_order", row.id, "status", f"SCO {row.number} {before_status} → {row.status}")
    if before_amount != float(amount):
        _audit(cu, "subcontract_change_order", row.id, "amount", f"SCO {row.number} amount {before_amount} → {float(amount)}")
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
