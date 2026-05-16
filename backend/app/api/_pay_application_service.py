"""Project pay applications (AIA G702–style summary + G703 / Textura-style SOV lines)."""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Mapping, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from ..extensions import db
from ..models import PayApplication, PayApplicationLine, Project
from ._perms import CurrentUser
from ._rfi_service import ApiError, _parse_dt

PAY_APP_STATUSES = frozenset({"draft", "submitted", "certified", "paid"})


def _is_admin(cu: CurrentUser) -> bool:
    return cu.is_dev_admin or cu.has_role("admin", "superuser")


def _is_writer(cu: CurrentUser) -> bool:
    return _is_admin(cu) or cu.has_role("standard")


def _can_view(cu: CurrentUser) -> bool:
    return _is_admin(cu) or _is_writer(cu) or cu.has_role("read_only", "readonly")


def _can_mutate(cu: CurrentUser) -> bool:
    return _is_admin(cu) or _is_writer(cu)


def _dec(v: Any) -> Decimal:
    if v is None or v == "":
        return Decimal("0")
    if isinstance(v, Decimal):
        return v
    try:
        return Decimal(str(v))
    except Exception:
        return Decimal("0")


def _iso_dt(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return dt.isoformat()


def _iso_date(d: date | None) -> str | None:
    if d is None:
        return None
    return d.isoformat()


def _money_str(d: Decimal | None) -> str | None:
    if d is None:
        return None
    return str(d.quantize(Decimal("0.01")))


def _serialize_line(li: PayApplicationLine) -> dict[str, Any]:
    return {
        "id": str(li.id),
        "pay_application_id": str(li.pay_application_id),
        "parent_id": str(li.parent_id) if li.parent_id else None,
        "sort_order": li.sort_order,
        "phase_code": li.phase_code,
        "description": li.description,
        "scheduled_value": _money_str(li.scheduled_value),
        "net_change_co": _money_str(li.net_change_co),
        "work_from_previous": _money_str(li.work_from_previous),
        "work_this_period": _money_str(li.work_this_period),
        "materials_stored": _money_str(li.materials_stored),
        "retention_to_date": _money_str(li.retention_to_date),
        "balance_to_complete": _money_str(li.balance_to_complete),
        "balance_due": _money_str(li.balance_due),
        "percent_complete": str(li.percent_complete) if li.percent_complete is not None else None,
        "created_at": _iso_dt(li.created_at),
        "updated_at": _iso_dt(li.updated_at),
    }


def _serialize_header(pa: PayApplication, include_line_count: bool = False) -> dict[str, Any]:
    row: dict[str, Any] = {
        "id": str(pa.id),
        "project_id": str(pa.project_id),
        "application_number": pa.application_number,
        "period_to": _iso_date(pa.period_to),
        "status": pa.status,
        "original_contract_sum": _money_str(pa.original_contract_sum),
        "net_change_by_change_orders": _money_str(pa.net_change_by_change_orders),
        "contract_sum_to_date": _money_str(pa.contract_sum_to_date),
        "total_completed_and_stored_to_date": _money_str(pa.total_completed_and_stored_to_date),
        "retainage_total": _money_str(pa.retainage_total),
        "total_earned_less_retainage": _money_str(pa.total_earned_less_retainage),
        "less_previous_certificates": _money_str(pa.less_previous_certificates),
        "current_payment_due": _money_str(pa.current_payment_due),
        "balance_to_finish_including_retainage": _money_str(pa.balance_to_finish_including_retainage),
        "architect_certified_amount": _money_str(pa.architect_certified_amount),
        "architect_certified_at": _iso_dt(pa.architect_certified_at),
        "notes": pa.notes,
        "textura_invoice_id": pa.textura_invoice_id,
        "created_at": _iso_dt(pa.created_at),
        "updated_at": _iso_dt(pa.updated_at),
    }
    if include_line_count:
        row["line_count"] = len(pa.lines) if pa.lines is not None else 0
    return row


def _prior_certified_payments_sum(project_id: uuid.UUID, before_application_number: int) -> Decimal:
    stmt = select(func.coalesce(func.sum(PayApplication.current_payment_due), 0)).where(
        PayApplication.project_id == project_id,
        PayApplication.application_number < before_application_number,
        PayApplication.status.in_(("submitted", "certified", "paid")),
    )
    val = db.session.scalar(stmt)
    if val is None:
        return Decimal("0")
    return Decimal(str(val)).quantize(Decimal("0.01"))


def _recalculate_application(pa: PayApplication) -> None:
    """Roll up SOV lines into G702-style header fields (simplified model)."""
    dzero = Decimal("0")
    lines = db.session.scalars(
        select(PayApplicationLine)
        .where(PayApplicationLine.pay_application_id == pa.id)
        .order_by(PayApplicationLine.sort_order, PayApplicationLine.id)
    ).all()

    l1 = pa.original_contract_sum if pa.original_contract_sum is not None else dzero
    l2 = pa.net_change_by_change_orders or dzero
    l3 = (l1 + l2).quantize(Decimal("0.01"))
    pa.contract_sum_to_date = l3

    sum_completed = dzero
    sum_retention = dzero
    for li in lines:
        sv = li.scheduled_value or dzero
        nco = li.net_change_co or dzero
        csum = (sv + nco).quantize(Decimal("0.01"))
        wf = li.work_from_previous or dzero
        wt = li.work_this_period or dzero
        ms = li.materials_stored or dzero
        completed = (wf + wt + ms).quantize(Decimal("0.01"))
        sum_completed += completed
        ret = li.retention_to_date or dzero
        sum_retention += ret
        btc = (csum - completed).quantize(Decimal("0.01"))
        li.balance_to_complete = btc
        li.balance_due = btc
        if li.percent_complete is None and csum > dzero:
            li.percent_complete = (completed / csum * Decimal("100")).quantize(Decimal("0.01"))

    l4 = sum_completed.quantize(Decimal("0.01"))
    l5 = sum_retention.quantize(Decimal("0.01"))
    l6 = (l4 - l5).quantize(Decimal("0.01"))
    l7 = _prior_certified_payments_sum(pa.project_id, pa.application_number).quantize(Decimal("0.01"))
    l8 = (l6 - l7).quantize(Decimal("0.01"))
    if l8 < dzero:
        l8 = dzero
    l9 = (l3 - l6).quantize(Decimal("0.01"))

    pa.total_completed_and_stored_to_date = l4
    pa.retainage_total = l5
    pa.total_earned_less_retainage = l6
    pa.less_previous_certificates = l7
    pa.current_payment_due = l8
    pa.balance_to_finish_including_retainage = l9


def _load_pay_application(project_id: uuid.UUID, pay_id: uuid.UUID) -> PayApplication | None:
    stmt = (
        select(PayApplication)
        .where(PayApplication.id == pay_id, PayApplication.project_id == project_id)
        .options(selectinload(PayApplication.lines))
    )
    return db.session.scalars(stmt).first()


def list_pay_applications(project_id: uuid.UUID, cu: CurrentUser) -> dict[str, Any]:
    if not _can_view(cu):
        raise ApiError("forbidden", 403)
    stmt = (
        select(PayApplication)
        .where(PayApplication.project_id == project_id)
        .options(selectinload(PayApplication.lines))
        .order_by(PayApplication.application_number.desc())
    )
    rows = db.session.scalars(stmt).unique().all()
    items = [_serialize_header(pa, include_line_count=True) for pa in rows]
    return {"items": items, "entity": "pay_applications"}


def get_pay_application_detail(project_id: uuid.UUID, pay_id: uuid.UUID, cu: CurrentUser) -> dict[str, Any]:
    if not _can_view(cu):
        raise ApiError("forbidden", 403)
    pa = _load_pay_application(project_id, pay_id)
    if pa is None:
        raise ApiError("pay application not found", 404)
    lines = sorted(pa.lines, key=lambda x: (x.sort_order, str(x.id)))
    return {
        "item": _serialize_header(pa),
        "lines": [_serialize_line(li) for li in lines],
        "entity": "pay_application",
    }


def create_pay_application(project_id: uuid.UUID, cu: CurrentUser, data: Mapping[str, Any]) -> dict[str, Any]:
    if not _can_mutate(cu):
        raise ApiError("forbidden", 403)
    proj = db.session.get(Project, project_id)
    if proj is None or proj.deleted_at is not None:
        raise ApiError("project not found", 404)

    max_no = db.session.scalar(
        select(func.max(PayApplication.application_number)).where(PayApplication.project_id == project_id)
    )
    next_no = int(max_no or 0) + 1

    pa = PayApplication(
        project_id=project_id,
        application_number=next_no,
        status="draft",
        net_change_by_change_orders=Decimal("0"),
    )
    if proj.contract_value is not None:
        pa.original_contract_sum = Decimal(str(proj.contract_value)).quantize(Decimal("0.01"))

    if data.get("period_to"):
        try:
            pa.period_to = date.fromisoformat(str(data["period_to"])[:10])
        except ValueError:
            pass
    if data.get("notes") is not None:
        pa.notes = str(data.get("notes") or "").strip() or None

    db.session.add(pa)
    db.session.flush()

    if isinstance(data.get("lines"), list):
        _replace_lines(pa, data["lines"], cu)

    _recalculate_application(pa)
    db.session.commit()
    pa = _load_pay_application(project_id, pa.id)
    assert pa is not None
    return get_pay_application_detail(project_id, pa.id, cu)


def _replace_lines(pa: PayApplication, raw_lines: list[Any], cu: CurrentUser) -> None:
    if not _can_mutate(cu):
        raise ApiError("forbidden", 403)
    if pa.status != "draft":
        raise ApiError("only draft pay applications can edit lines", 400)
    for li in list(pa.lines):
        db.session.delete(li)
    db.session.flush()

    for idx, raw in enumerate(raw_lines):
        if not isinstance(raw, Mapping):
            continue
        desc = str(raw.get("description") or "").strip()[:500]
        li = PayApplicationLine(
            pay_application_id=pa.id,
            parent_id=None,
            sort_order=int(raw.get("sort_order", idx)),
            phase_code=(str(raw.get("phase_code") or "").strip()[:40] or None),
            description=desc or f"Line {idx + 1}",
            scheduled_value=_dec(raw.get("scheduled_value")),
            net_change_co=_dec(raw.get("net_change_co")),
            work_from_previous=_dec(raw.get("work_from_previous")),
            work_this_period=_dec(raw.get("work_this_period")),
            materials_stored=_dec(raw.get("materials_stored")),
            retention_to_date=_dec(raw.get("retention_to_date")),
        )
        pct_raw = raw.get("percent_complete")
        if pct_raw is not None and pct_raw != "":
            li.percent_complete = _dec(pct_raw).quantize(Decimal("0.01"))
        db.session.add(li)
    db.session.flush()


def patch_pay_application(
    project_id: uuid.UUID, pay_id: uuid.UUID, cu: CurrentUser, data: Mapping[str, Any]
) -> dict[str, Any]:
    if not _can_mutate(cu):
        raise ApiError("forbidden", 403)
    pa = _load_pay_application(project_id, pay_id)
    if pa is None:
        raise ApiError("pay application not found", 404)

    orig_status = pa.status
    if orig_status != "draft":
        allowed = {"status", "architect_certified_amount", "architect_certified_at"}
        bad = [k for k in data if k not in allowed]
        if bad:
            raise ApiError("only status and architect certificate fields can change after submit", 400)

    if "status" in data and data["status"] is not None:
        st = str(data["status"]).strip().lower()
        if st not in PAY_APP_STATUSES:
            raise ApiError("invalid status", 400)
        pa.status = st

    if orig_status == "draft":
        if "original_contract_sum" in data:
            v = data.get("original_contract_sum")
            pa.original_contract_sum = None if v is None or v == "" else _dec(v).quantize(Decimal("0.01"))
        if "net_change_by_change_orders" in data:
            pa.net_change_by_change_orders = _dec(data.get("net_change_by_change_orders")).quantize(Decimal("0.01"))
        if "period_to" in data:
            pt = data.get("period_to")
            if pt is None or pt == "":
                pa.period_to = None
            else:
                try:
                    pa.period_to = date.fromisoformat(str(pt)[:10])
                except ValueError:
                    raise ApiError("invalid period_to", 400) from None
        if "notes" in data:
            pa.notes = str(data.get("notes") or "").strip() or None
        if isinstance(data.get("lines"), list):
            _replace_lines(pa, data["lines"], cu)

    if "architect_certified_amount" in data:
        ac = data.get("architect_certified_amount")
        pa.architect_certified_amount = None if ac is None or ac == "" else _dec(ac).quantize(Decimal("0.01"))
    if "architect_certified_at" in data:
        at = data.get("architect_certified_at")
        if at is None or at == "":
            pa.architect_certified_at = None
        else:
            pa.architect_certified_at = _parse_dt(at)

    _recalculate_application(pa)
    pa.updated_at = datetime.now(tz=timezone.utc)
    db.session.commit()
    return get_pay_application_detail(project_id, pay_id, cu)


def delete_pay_application(project_id: uuid.UUID, pay_id: uuid.UUID, cu: CurrentUser) -> None:
    if not _can_mutate(cu):
        raise ApiError("forbidden", 403)
    pa = _load_pay_application(project_id, pay_id)
    if pa is None:
        raise ApiError("pay application not found", 404)
    if pa.status != "draft":
        raise ApiError("only draft pay applications can be deleted", 400)
    db.session.delete(pa)
    db.session.commit()
