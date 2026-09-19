"""Prevailing wage rates (state / sub-area / year / trade)."""
from __future__ import annotations

import csv
import io
import uuid
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping

from sqlalchemy import delete, func, or_, select
from sqlalchemy.exc import IntegrityError

from ..extensions import db
from ..models.wage_rate import WageRate
from ._rfi_service import ApiError

_RATE_FIELDS = (
    "basic_hourly_rate",
    "health_welfare",
    "pension",
    "vacation_holiday",
    "other_payments",
    "training",
)

_EDITABLE = (
    "state",
    "sub_area",
    "year",
    "trade",
    *_RATE_FIELDS,
    "notes",
    "is_assumed",
)


def _blank(v: Any) -> str:
    return str(v or "").strip()


def _optional_decimal(val: Any) -> Decimal | None:
    if val is None:
        return None
    if isinstance(val, bool):
        raise ApiError("invalid number", 400)
    if isinstance(val, Decimal):
        return val
    s = str(val).strip()
    if s == "":
        return None
    try:
        return Decimal(s)
    except InvalidOperation as exc:
        raise ApiError("invalid number", 400) from exc


def _optional_bool(val: Any) -> bool:
    if isinstance(val, bool):
        return val
    s = str(val or "").strip().lower()
    return s in ("1", "true", "yes", "y", "on")


def _assumed_from_notes(notes: str | None, explicit: Any | None = None) -> bool:
    if explicit is not None:
        return _optional_bool(explicit)
    return "assumed" in (notes or "").lower()


def wage_total_loaded(w: WageRate) -> float:
    total = Decimal("0")
    for col in (
        w.basic_hourly_rate,
        w.health_welfare,
        w.pension,
        w.vacation_holiday,
        w.other_payments,
        w.training,
    ):
        if col is not None:
            total += col
    return float(total.quantize(Decimal("0.0001")))


def wage_rate_public(w: WageRate) -> dict[str, Any]:
    return {
        "id": str(w.id),
        "state": w.state,
        "sub_area": w.sub_area,
        "year": w.year,
        "trade": w.trade,
        "basic_hourly_rate": float(w.basic_hourly_rate) if w.basic_hourly_rate is not None else None,
        "health_welfare": float(w.health_welfare) if w.health_welfare is not None else None,
        "pension": float(w.pension) if w.pension is not None else None,
        "vacation_holiday": float(w.vacation_holiday) if w.vacation_holiday is not None else None,
        "other_payments": float(w.other_payments) if w.other_payments is not None else None,
        "training": float(w.training) if w.training is not None else None,
        "notes": w.notes,
        "is_assumed": bool(w.is_assumed),
        "total_loaded_hourly": wage_total_loaded(w),
    }


def values_from_mapping(data: Mapping[str, Any], *, partial: bool = False) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if not partial or "state" in data:
        state = _blank(data.get("state"))
        if not state:
            raise ApiError("state is required", 400)
        out["state"] = state[:80]
    if not partial or "sub_area" in data:
        out["sub_area"] = _blank(data.get("sub_area"))[:80]
    if not partial or "year" in data:
        year_raw = data.get("year")
        try:
            year = int(str(year_raw).strip())
        except (TypeError, ValueError) as exc:
            raise ApiError("year is required", 400) from exc
        if year < 1900 or year > 2100:
            raise ApiError("invalid year", 400)
        out["year"] = year
    if not partial or "trade" in data:
        trade = _blank(data.get("trade"))
        if not trade:
            raise ApiError("trade is required", 400)
        out["trade"] = trade[:120]
    for field in _RATE_FIELDS:
        if partial and field not in data:
            continue
        out[field] = _optional_decimal(data.get(field))
    if not partial or "notes" in data:
        notes = _blank(data.get("notes")) or None
        if notes:
            notes = notes[:255]
        out["notes"] = notes
    if not partial or "is_assumed" in data or "notes" in data:
        notes_val = out["notes"] if "notes" in out else _blank(data.get("notes")) or None
        explicit = data.get("is_assumed") if "is_assumed" in data else None
        out["is_assumed"] = _assumed_from_notes(notes_val, explicit)
    return out


def csv_row_values(norm: Mapping[str, str]) -> dict[str, Any]:
    return values_from_mapping(
        {
            "state": norm.get("state", ""),
            "sub_area": norm.get("sub_area", ""),
            "year": norm.get("year", ""),
            "trade": norm.get("trade", ""),
            "basic_hourly_rate": norm.get("basic_hourly_rate", ""),
            "health_welfare": norm.get("health_welfare", ""),
            "pension": norm.get("pension", ""),
            "vacation_holiday": norm.get("vacation_holiday", ""),
            "other_payments": norm.get("other_payments", ""),
            "training": norm.get("training", ""),
            "notes": norm.get("notes", ""),
        }
    )


def _wage_query(
    *,
    q: str = "",
    state: str = "",
    year: int | None = None,
    trade: str = "",
    sub_area: str | None = None,
):
    stmt = select(WageRate)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            or_(
                WageRate.state.ilike(like),
                WageRate.sub_area.ilike(like),
                WageRate.trade.ilike(like),
                WageRate.notes.ilike(like),
            )
        )
    if state:
        stmt = stmt.where(WageRate.state == state)
    if year is not None:
        stmt = stmt.where(WageRate.year == year)
    if trade:
        stmt = stmt.where(WageRate.trade.ilike(f"%{trade}%"))
    if sub_area is not None and sub_area != "":
        stmt = stmt.where(WageRate.sub_area == sub_area)
    return stmt.order_by(
        WageRate.year.desc(),
        WageRate.state.asc(),
        WageRate.trade.asc(),
        WageRate.sub_area.asc(),
    )


def list_wage_rates(
    *,
    q: str = "",
    state: str = "",
    year: int | None = None,
    trade: str = "",
    sub_area: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> dict[str, Any]:
    limit = max(1, min(int(limit), 500))
    offset = max(0, int(offset))
    base = _wage_query(q=q, state=state, year=year, trade=trade, sub_area=sub_area)
    total = db.session.scalar(select(func.count()).select_from(base.order_by(None).subquery())) or 0
    rows = db.session.scalars(base.offset(offset).limit(limit)).all()
    return {
        "items": [wage_rate_public(w) for w in rows],
        "entity": "wage_rates",
        "total": int(total),
        "limit": limit,
        "offset": offset,
    }


def wage_rate_facets() -> dict[str, Any]:
    states = [
        r
        for r in db.session.scalars(select(WageRate.state).distinct().order_by(WageRate.state.asc())).all()
        if r
    ]
    years = [
        int(r)
        for r in db.session.scalars(select(WageRate.year).distinct().order_by(WageRate.year.desc())).all()
        if r is not None
    ]
    trades = [
        r
        for r in db.session.scalars(select(WageRate.trade).distinct().order_by(WageRate.trade.asc())).all()
        if r
    ]
    return {"states": states, "years": years, "trades": trades, "entity": "wage_rate_facets"}


def get_wage_rate(row_id: uuid.UUID) -> dict[str, Any]:
    row = db.session.get(WageRate, row_id)
    if row is None:
        raise ApiError("wage rate not found", 404)
    return wage_rate_public(row)


def create_wage_rate(data: Mapping[str, Any]) -> dict[str, Any]:
    values = values_from_mapping(data)
    row = WageRate(id=uuid.uuid4(), **values)
    db.session.add(row)
    try:
        db.session.commit()
    except IntegrityError as exc:
        db.session.rollback()
        raise ApiError("a wage rate for that state, area, year, and trade already exists", 409) from exc
    return wage_rate_public(row)


def patch_wage_rate(row_id: uuid.UUID, data: Mapping[str, Any]) -> dict[str, Any]:
    row = db.session.get(WageRate, row_id)
    if row is None:
        raise ApiError("wage rate not found", 404)
    updates = {k: v for k, v in data.items() if k in _EDITABLE}
    if not updates:
        raise ApiError("no editable fields in body", 400)
    values = values_from_mapping(updates, partial=True)
    for field, value in values.items():
        setattr(row, field, value)
    try:
        db.session.commit()
    except IntegrityError as exc:
        db.session.rollback()
        raise ApiError("a wage rate for that state, area, year, and trade already exists", 409) from exc
    return wage_rate_public(row)


def delete_wage_rate(row_id: uuid.UUID) -> dict[str, Any]:
    row = db.session.get(WageRate, row_id)
    if row is None:
        raise ApiError("wage rate not found", 404)
    db.session.delete(row)
    db.session.commit()
    return {"ok": True, "id": str(row_id), "entity": "wage_rates"}


def import_wage_rates_csv(text: str, *, replace: bool = False) -> dict[str, Any]:
    reader = csv.DictReader(io.StringIO((text or "").lstrip("\ufeff")))
    if not reader.fieldnames:
        raise ApiError("csv has no header row", 400)
    created = 0
    updated = 0
    skipped = 0
    if replace:
        db.session.execute(delete(WageRate))
        db.session.flush()
        existing: dict[tuple[str, str, int, str], WageRate] = {}
    else:
        existing = {
            (r.state, r.sub_area, r.year, r.trade): r
            for r in db.session.scalars(select(WageRate)).all()
        }
    for raw in reader:
        norm = {str(k).strip().lower(): (v if v is not None else "") for k, v in raw.items()}
        try:
            values = csv_row_values(norm)
        except ApiError:
            skipped += 1
            continue
        key = (values["state"], values["sub_area"], values["year"], values["trade"])
        row = existing.get(key)
        if row is None:
            row = WageRate(**values)
            db.session.add(row)
            existing[key] = row
            created += 1
        else:
            for field, value in values.items():
                setattr(row, field, value)
            updated += 1
    db.session.commit()
    return {
        "created": created,
        "updated": updated,
        "skipped": skipped,
        "total": created + updated,
        "entity": "wage_rates",
    }
