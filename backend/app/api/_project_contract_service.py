"""CRUD for owner/prime contracts on a project (one owner, many contracts)."""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping

from sqlalchemy import func, select

from ..extensions import db
from ..models import Company, Project, ProjectContract
from ._perms import CurrentUser, is_company_readonly
from ._rfi_service import ApiError


def _is_admin(cu: CurrentUser) -> bool:
    return cu.is_dev_admin or cu.has_role("admin", "superuser")


def _is_writer(cu: CurrentUser) -> bool:
    return _is_admin(cu) or cu.has_role("standard")


def _can_view(cu: CurrentUser) -> bool:
    return _is_admin(cu) or _is_writer(cu) or is_company_readonly(cu)


def _can_mutate(cu: CurrentUser) -> bool:
    return _is_admin(cu) or _is_writer(cu)


def _parse_date(raw: Any) -> date | None:
    if raw is None or raw == "":
        return None
    if isinstance(raw, date):
        return raw
    s = str(raw).strip()
    if not s:
        return None
    try:
        return date.fromisoformat(s[:10])
    except ValueError as e:
        raise ApiError(f"invalid date: {s}") from e


def _parse_decimal(raw: Any, field: str) -> Decimal | None:
    if raw is None or raw == "":
        return None
    try:
        return Decimal(str(raw).replace(",", "").strip())
    except (InvalidOperation, ValueError) as e:
        raise ApiError(f"invalid {field}") from e


def _money_or_none(v: Any) -> float | None:
    if v is None:
        return None
    try:
        return float(Decimal(str(v)).quantize(Decimal("0.01")))
    except (InvalidOperation, ValueError, TypeError):
        return None


def _iso(d: date | None) -> str | None:
    return d.isoformat() if d else None


def _load_project(project_id: uuid.UUID) -> Project:
    proj = db.session.get(Project, project_id)
    if proj is None or proj.deleted_at is not None:
        raise ApiError("project not found", 404)
    return proj


def _serialize(row: ProjectContract) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "project_id": str(row.project_id),
        "contract_number": row.contract_number,
        "title": row.title,
        "contract_value": _money_or_none(row.contract_value),
        "contract_date": _iso(row.contract_date),
        "start_date": _iso(row.start_date),
        "substantial_completion_date": _iso(row.substantial_completion_date),
        "closeout_date": _iso(row.closeout_date),
        "retention_percentage": _money_or_none(row.retention_percentage),
        "is_primary": bool(row.is_primary),
        "sort_order": row.sort_order,
        "notes": row.notes,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def _owner_payload(proj: Project) -> dict[str, Any]:
    name = None
    if proj.owner_company_id:
        owner = db.session.get(Company, proj.owner_company_id)
        if owner is not None and owner.deleted_at is None:
            name = owner.name
    return {
        "owner_company_id": str(proj.owner_company_id) if proj.owner_company_id else None,
        "owner_company_name": name,
    }


def _rows_for_project(project_id: uuid.UUID) -> list[ProjectContract]:
    return list(
        db.session.scalars(
            select(ProjectContract)
            .where(ProjectContract.project_id == project_id)
            .order_by(
                ProjectContract.is_primary.desc(),
                ProjectContract.sort_order.asc(),
                ProjectContract.created_at.asc(),
            )
        ).all()
    )


def _project_has_contract_fields(proj: Project) -> bool:
    return any(
        (
            proj.contract_value is not None,
            proj.contract_date is not None,
            proj.start_date is not None,
            proj.substantial_completion_date is not None,
            proj.closeout_date is not None,
            proj.retention_percentage is not None,
        )
    )


def _seed_primary_from_project(proj: Project) -> ProjectContract:
    row = ProjectContract(
        project_id=proj.id,
        contract_number=(proj.number or None),
        title="Prime contract",
        contract_value=proj.contract_value,
        contract_date=proj.contract_date,
        start_date=proj.start_date,
        substantial_completion_date=proj.substantial_completion_date,
        closeout_date=proj.closeout_date,
        retention_percentage=proj.retention_percentage,
        is_primary=True,
        sort_order=0,
    )
    db.session.add(row)
    db.session.flush()
    return row


def ensure_primary_from_project(proj: Project) -> ProjectContract | None:
    """Create a primary row from project Job-info fields when the list is empty."""
    existing = _rows_for_project(proj.id)
    if existing:
        return next((r for r in existing if r.is_primary), existing[0])
    if not _project_has_contract_fields(proj):
        return None
    return _seed_primary_from_project(proj)


def sync_primary_from_project(proj: Project) -> None:
    """Keep the primary contract aligned when Job info saves contract fields."""
    rows = _rows_for_project(proj.id)
    primary = next((r for r in rows if r.is_primary), None)
    if primary is None:
        if _project_has_contract_fields(proj):
            _seed_primary_from_project(proj)
        return
    primary.contract_value = proj.contract_value
    primary.contract_date = proj.contract_date
    primary.start_date = proj.start_date
    primary.substantial_completion_date = proj.substantial_completion_date
    primary.closeout_date = proj.closeout_date
    primary.retention_percentage = proj.retention_percentage
    db.session.flush()


def _apply_primary_to_project(proj: Project, row: ProjectContract) -> None:
    proj.contract_value = float(row.contract_value) if row.contract_value is not None else None
    proj.contract_date = row.contract_date
    proj.start_date = row.start_date
    proj.substantial_completion_date = row.substantial_completion_date
    proj.closeout_date = row.closeout_date
    proj.retention_percentage = (
        float(row.retention_percentage) if row.retention_percentage is not None else None
    )


def _clear_other_primaries(project_id: uuid.UUID, keep_id: uuid.UUID) -> None:
    for row in _rows_for_project(project_id):
        if row.id != keep_id and row.is_primary:
            row.is_primary = False


def _apply_fields(row: ProjectContract, data: Mapping[str, Any]) -> None:
    if "title" in data:
        title = str(data.get("title") or "").strip()[:300]
        if not title:
            raise ApiError("title is required")
        row.title = title
    if "contract_number" in data:
        num = data.get("contract_number")
        row.contract_number = None if num is None or str(num).strip() == "" else str(num).strip()[:80]
    if "contract_value" in data:
        dec = _parse_decimal(data.get("contract_value"), "contract_value")
        row.contract_value = float(dec) if dec is not None else None
    if "contract_date" in data:
        row.contract_date = _parse_date(data.get("contract_date"))
    if "start_date" in data:
        row.start_date = _parse_date(data.get("start_date"))
    if "substantial_completion_date" in data:
        row.substantial_completion_date = _parse_date(data.get("substantial_completion_date"))
    if "closeout_date" in data:
        row.closeout_date = _parse_date(data.get("closeout_date"))
    if "retention_percentage" in data:
        dec = _parse_decimal(data.get("retention_percentage"), "retention_percentage")
        row.retention_percentage = float(dec) if dec is not None else None
    if "notes" in data:
        n = data.get("notes")
        row.notes = None if n is None else (str(n).strip() or None)
    if "sort_order" in data and data.get("sort_order") is not None:
        try:
            row.sort_order = int(data.get("sort_order"))
        except (TypeError, ValueError) as e:
            raise ApiError("invalid sort_order") from e


def _list_payload(proj: Project) -> dict[str, Any]:
    rows = _rows_for_project(proj.id)
    total = Decimal("0")
    has_value = False
    primary_id = None
    for row in rows:
        if row.is_primary:
            primary_id = str(row.id)
        if row.contract_value is not None:
            has_value = True
            total += Decimal(str(row.contract_value))
    out = {
        "entity": "project_contracts",
        "items": [_serialize(r) for r in rows],
        "primary_id": primary_id,
        "total_contract_value": float(total.quantize(Decimal("0.01"))) if has_value else None,
    }
    out.update(_owner_payload(proj))
    return out


def list_contracts(project_id: uuid.UUID, cu: CurrentUser) -> dict[str, Any]:
    if not _can_view(cu):
        raise ApiError("forbidden", 403)
    proj = _load_project(project_id)
    had_rows = bool(_rows_for_project(project_id))
    seeded = ensure_primary_from_project(proj)
    if seeded is not None and not had_rows:
        db.session.commit()
    else:
        db.session.flush()
    return _list_payload(proj)


def create_contract(project_id: uuid.UUID, data: Mapping[str, Any], cu: CurrentUser) -> dict[str, Any]:
    if not _can_mutate(cu):
        raise ApiError("forbidden", 403)
    if not isinstance(data, Mapping):
        raise ApiError("JSON body required")
    proj = _load_project(project_id)
    ensure_primary_from_project(proj)
    title = str(data.get("title") or "").strip()[:300]
    if not title:
        raise ApiError("title is required")
    existing = _rows_for_project(project_id)
    want_primary = bool(data.get("is_primary")) or not existing
    max_sort = db.session.scalar(
        select(func.max(ProjectContract.sort_order)).where(ProjectContract.project_id == project_id)
    )
    row = ProjectContract(
        project_id=project_id,
        title=title,
        is_primary=False,
        sort_order=int(max_sort or 0) + 1,
    )
    _apply_fields(row, data)
    row.title = title
    db.session.add(row)
    db.session.flush()
    if want_primary:
        _clear_other_primaries(project_id, row.id)
        row.is_primary = True
        _apply_primary_to_project(proj, row)
    db.session.commit()
    return {"entity": "project_contract", "item": _serialize(row)}


def patch_contract(
    project_id: uuid.UUID, contract_id: uuid.UUID, data: Mapping[str, Any], cu: CurrentUser
) -> dict[str, Any]:
    if not _can_mutate(cu):
        raise ApiError("forbidden", 403)
    if not isinstance(data, Mapping):
        raise ApiError("JSON body required")
    proj = _load_project(project_id)
    row = db.session.get(ProjectContract, contract_id)
    if row is None or row.project_id != project_id:
        raise ApiError("contract not found", 404)
    _apply_fields(row, data)
    if "is_primary" in data:
        if data.get("is_primary"):
            _clear_other_primaries(project_id, row.id)
            row.is_primary = True
        elif row.is_primary:
            others = [r for r in _rows_for_project(project_id) if r.id != row.id]
            if not others:
                raise ApiError("keep at least one primary contract")
            raise ApiError("set another contract as primary instead of unchecking this one")
    if row.is_primary:
        _apply_primary_to_project(proj, row)
    db.session.commit()
    return {"entity": "project_contract", "item": _serialize(row)}


def delete_contract(project_id: uuid.UUID, contract_id: uuid.UUID, cu: CurrentUser) -> None:
    if not _can_mutate(cu):
        raise ApiError("forbidden", 403)
    _load_project(project_id)
    row = db.session.get(ProjectContract, contract_id)
    if row is None or row.project_id != project_id:
        raise ApiError("contract not found", 404)
    if row.is_primary:
        others = [r for r in _rows_for_project(project_id) if r.id != row.id]
        if others:
            raise ApiError("set another contract as primary before deleting this one")
        raise ApiError("cannot delete the only primary contract")
    db.session.delete(row)
    db.session.commit()
