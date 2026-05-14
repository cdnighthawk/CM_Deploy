"""Project-scoped prime contract schedule of values (master SOV)."""
from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any, Mapping

from sqlalchemy import select

from ..extensions import db
from ..models import PrimeContractSovLine, Project
from ._perms import CurrentUser
from ._rfi_service import ApiError


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


def _money_str(d: Decimal | None) -> str | None:
    if d is None:
        return None
    return str(d.quantize(Decimal("0.01")))


def _iso_dt(dt: Any) -> str | None:
    if dt is None:
        return None
    return dt.isoformat()


def _parse_uuid_opt(raw: Any) -> uuid.UUID | None:
    if raw is None or raw == "":
        return None
    try:
        return uuid.UUID(str(raw))
    except (ValueError, TypeError):
        return None


def _serialize_line(li: PrimeContractSovLine) -> dict[str, Any]:
    return {
        "id": str(li.id),
        "project_id": str(li.project_id),
        "parent_id": str(li.parent_id) if li.parent_id else None,
        "sort_order": li.sort_order,
        "phase_code": li.phase_code,
        "description": li.description,
        "scheduled_value": _money_str(li.scheduled_value),
        "created_at": _iso_dt(li.created_at),
        "updated_at": _iso_dt(li.updated_at),
    }


def get_prime_contract_sov(project_id: uuid.UUID, cu: CurrentUser) -> dict[str, Any]:
    if not _can_view(cu):
        raise ApiError("forbidden", 403)
    proj = db.session.get(Project, project_id)
    if proj is None or proj.deleted_at is not None:
        raise ApiError("project not found", 404)

    stmt = (
        select(PrimeContractSovLine)
        .where(PrimeContractSovLine.project_id == project_id)
        .order_by(PrimeContractSovLine.sort_order, PrimeContractSovLine.id)
    )
    rows = list(db.session.scalars(stmt).all())
    total = Decimal("0")
    for li in rows:
        total += li.scheduled_value or Decimal("0")
    contract_val: Decimal | None = None
    if proj.contract_value is not None:
        contract_val = _dec(proj.contract_value).quantize(Decimal("0.01"))

    return {
        "entity": "prime_contract_sov",
        "lines": [_serialize_line(li) for li in rows],
        "total_scheduled_value": _money_str(total),
        "contract_value": _money_str(contract_val) if contract_val is not None else None,
        "sov_matches_contract_value": (
            contract_val is not None and total == contract_val if contract_val is not None else None
        ),
    }


def put_prime_contract_sov(project_id: uuid.UUID, cu: CurrentUser, data: Mapping[str, Any]) -> dict[str, Any]:
    if not _can_mutate(cu):
        raise ApiError("forbidden", 403)
    proj = db.session.get(Project, project_id)
    if proj is None or proj.deleted_at is not None:
        raise ApiError("project not found", 404)

    raw_lines = data.get("lines")
    if not isinstance(raw_lines, list):
        raise ApiError("body must include a lines array", 400)

    for li in db.session.scalars(select(PrimeContractSovLine).where(PrimeContractSovLine.project_id == project_id)):
        db.session.delete(li)
    db.session.flush()

    for idx, raw in enumerate(raw_lines):
        if not isinstance(raw, Mapping):
            continue
        desc = str(raw.get("description") or "").strip()[:500]
        parent_id = _parse_uuid_opt(raw.get("parent_id"))
        li = PrimeContractSovLine(
            project_id=project_id,
            parent_id=parent_id,
            sort_order=int(raw.get("sort_order", idx)),
            phase_code=(str(raw.get("phase_code") or "").strip()[:40] or None),
            description=desc or f"Line {idx + 1}",
            scheduled_value=_dec(raw.get("scheduled_value")).quantize(Decimal("0.01")),
        )
        db.session.add(li)
    db.session.commit()
    return get_prime_contract_sov(project_id, cu)
