"""Estimate labor-rate worksheet: copy company wages onto the project and price labor tasks."""
from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any, Mapping

from sqlalchemy import or_, select

from ..extensions import db
from ..models.estimate import Estimate
from ..models.takeoff_line_item import TakeoffLineItem
from ..models.wage_rate import WageRate
from ..project_labor_rates import (
    _MAX_TRADES,
    merge_trade_snapshots,
    normalize_labor_crew,
    normalize_labor_rate_settings,
    ot_schedule,
    project_rate_breakdown,
    snapshot_wage_package,
    stored_labor_crew,
    stored_labor_rate_settings,
    suggested_unit_cost,
)
from ._estimate_service import EstimateError, estimate_is_locked, estimate_locked_payload
from ._wage_rate_service import current_labor_burden_book, wage_rate_public


def lead_default_state(est: Estimate) -> str:
    lead = est.lead_estimate
    if lead is None:
        return ""
    loc = lead.location if isinstance(getattr(lead, "location", None), dict) else {}
    return str(loc.get("state") or "").strip()


def settings_for_estimate(est: Estimate, raw: Mapping[str, Any] | None = None) -> dict[str, Any]:
    src = raw if isinstance(raw, Mapping) else (est.labor_rates if isinstance(est.labor_rates, dict) else {})
    return normalize_labor_rate_settings(src, default_state=lead_default_state(est))


def _load_wage_rows(ids: list[str]) -> tuple[list[WageRate], list[str]]:
    if not ids:
        return [], []
    uuids: list[uuid.UUID] = []
    for raw in ids:
        try:
            uuids.append(uuid.UUID(str(raw)))
        except (ValueError, TypeError):
            continue
    if not uuids:
        return [], list(ids)
    rows = list(db.session.scalars(select(WageRate).where(WageRate.id.in_(uuids))).all())
    by_id = {str(row.id): row for row in rows}
    ordered: list[WageRate] = []
    missing: list[str] = []
    for raw in ids:
        row = by_id.get(str(raw))
        if row is None:
            missing.append(str(raw))
        else:
            ordered.append(row)
    return ordered, missing


def _trade_sources(
    ids: list[str],
    *,
    snapshots: list[dict[str, Any]] | None = None,
    live_rows: list[WageRate] | None = None,
) -> tuple[list[Any], list[str]]:
    live_by_id = {str(row.id): row for row in (live_rows or [])}
    snap_by_id = {str(s.get("wage_rate_id") or ""): s for s in (snapshots or []) if s.get("wage_rate_id")}
    ordered: list[Any] = []
    missing: list[str] = []
    for raw in ids:
        key = str(raw)
        if key in snap_by_id:
            ordered.append(snap_by_id[key])
        elif key in live_by_id:
            ordered.append(live_by_id[key])
        else:
            missing.append(key)
    return ordered, missing


def _persist_labor_rates(
    est: Estimate,
    stored: dict[str, Any],
    snapshots: list[dict[str, Any]],
) -> None:
    payload = dict(stored)
    payload["wage_rate_ids"] = [str(s.get("wage_rate_id") or "") for s in snapshots if s.get("wage_rate_id")]
    payload["trades"] = snapshots
    est.labor_rates = payload


def labor_rates_public(est: Estimate, *, settings: Mapping[str, Any] | None = None) -> dict[str, Any]:
    normalized = settings_for_estimate(est, settings)
    stored = stored_labor_rate_settings(normalized)
    book = current_labor_burden_book()
    raw = est.labor_rates if isinstance(est.labor_rates, dict) else {}
    ids = stored["wage_rate_ids"]
    if not ids and isinstance(raw.get("wage_rate_ids"), list):
        ids = [str(x) for x in raw["wage_rate_ids"]]
    snapshots = merge_trade_snapshots(wage_rate_ids=ids, existing=raw)
    live_rows, _live_missing = _load_wage_rows(ids)
    live_by_id = {str(row.id): row for row in live_rows}
    sources, missing = _trade_sources(ids, snapshots=snapshots, live_rows=live_rows)
    trades: list[dict[str, Any]] = []
    for row in sources:
        breakdown = project_rate_breakdown(row, normalized, book)
        snap = snapshot_wage_package(row)
        company_row = live_by_id.get(str(snap.get("wage_rate_id") or ""))
        if company_row is not None:
            company = wage_rate_public(company_row, book)
        else:
            company = dict(breakdown.get("company") or {})
            company.update(
                {
                    "trade": snap.get("trade"),
                    "state": snap.get("state"),
                    "sub_area": snap.get("sub_area"),
                    "year": snap.get("year"),
                    "basic_hourly_rate": snap.get("basic_hourly_rate"),
                    "health_welfare": snap.get("health_welfare"),
                    "pension": snap.get("pension"),
                    "vacation_holiday": snap.get("vacation_holiday"),
                    "other_payments": snap.get("other_payments"),
                    "training": snap.get("training"),
                    "workers_comp_pct": snap.get("workers_comp_pct"),
                    "notes": snap.get("notes"),
                    "is_assumed": bool(snap.get("is_assumed")),
                    "total_loaded_hourly": breakdown["company_loaded_hourly"],
                }
            )
        trades.append(
            {
                "wage_rate_id": snap.get("wage_rate_id"),
                "trade": snap.get("trade") or getattr(row, "trade", None),
                "state": snap.get("state") or getattr(row, "state", None),
                "sub_area": snap.get("sub_area") if snap.get("sub_area") is not None else getattr(row, "sub_area", None),
                "year": snap.get("year") if snap.get("year") is not None else getattr(row, "year", None),
                "company_loaded_hourly": breakdown["company_loaded_hourly"],
                "ot_hourly": breakdown["ot_hourly"],
                "ot_premium_hourly": breakdown["ot_premium_hourly"],
                "ot_burden_hourly": breakdown["ot_burden_hourly"],
                "per_diem_hourly": breakdown["per_diem_hourly"],
                "housing_hourly": breakdown["housing_hourly"],
                "other_hourly": breakdown["other_hourly"],
                "project_loaded_hourly": breakdown["project_loaded_hourly"],
                "adders": breakdown["adders"],
                "company": company,
                "from_company": company_row is not None,
            }
        )
    first = trades[0]["project_loaded_hourly"] if trades else None
    return {
        "estimate_id": str(est.id),
        "locked": estimate_is_locked(est),
        "settings": stored,
        "schedule": ot_schedule(stored["hours_per_day"], stored["days_per_week"]),
        "trades": trades,
        "missing_ids": missing,
        "trade_count": len(trades),
        "project_loaded_hourly": first,
    }


def _incoming_settings(est: Estimate, data: Mapping[str, Any] | None) -> dict[str, Any]:
    incoming = data if isinstance(data, Mapping) else {}
    if isinstance(incoming.get("settings"), Mapping):
        payload = dict(incoming["settings"])
        if "wage_rate_ids" in incoming:
            payload["wage_rate_ids"] = incoming.get("wage_rate_ids")
    else:
        payload = dict(incoming)
    return settings_for_estimate(est, payload)


def save_labor_rates(est: Estimate, data: Mapping[str, Any] | None) -> dict[str, Any]:
    if estimate_is_locked(est):
        raise EstimateError(
            estimate_locked_payload()["error"],
            status=403,
            error_code="ESTIMATE_LOCKED",
        )
    incoming = data if isinstance(data, Mapping) else {}
    normalized = _incoming_settings(est, incoming)
    stored = stored_labor_rate_settings(normalized)
    refresh = bool(incoming.get("refresh_from_company"))
    rows, missing_live = _load_wage_rows(stored["wage_rate_ids"])
    live_ids = {str(row.id) for row in rows}
    existing = None if refresh else (est.labor_rates if isinstance(est.labor_rates, dict) else None)
    existing_snaps = merge_trade_snapshots(wage_rate_ids=stored["wage_rate_ids"], existing=existing)
    snap_ids = {str(s.get("wage_rate_id") or "") for s in existing_snaps}
    kept: list[str] = []
    seen: set[str] = set()
    for wid in stored["wage_rate_ids"]:
        if wid in seen:
            continue
        seen.add(wid)
        if wid in live_ids or (not refresh and wid in snap_ids):
            kept.append(wid)
    stored["wage_rate_ids"] = kept
    snapshots = merge_trade_snapshots(
        wage_rate_ids=kept,
        existing=existing,
        fresh=rows,
    )
    _persist_labor_rates(est, stored, snapshots)
    db.session.flush()
    out = labor_rates_public(est)
    missing = [mid for mid in missing_live if mid not in snap_ids]
    if missing:
        out["missing_ids"] = missing
    return out


def import_company_trades(est: Estimate, data: Mapping[str, Any] | None = None) -> dict[str, Any]:
    if estimate_is_locked(est):
        raise EstimateError(
            estimate_locked_payload()["error"],
            status=403,
            error_code="ESTIMATE_LOCKED",
        )
    incoming = data if isinstance(data, Mapping) else {}
    normalized = _incoming_settings(est, incoming)
    stored = stored_labor_rate_settings(normalized)
    if not stored["state"]:
        raise EstimateError("set a state before importing company trades")
    stmt = select(WageRate).where(
        WageRate.state == stored["state"],
        WageRate.year == int(stored["year"]),
    )
    area = stored["sub_area"]
    if area:
        stmt = stmt.where(or_(WageRate.sub_area == area, WageRate.sub_area == ""))
    stmt = stmt.order_by(WageRate.trade.asc(), WageRate.sub_area.asc()).limit(_MAX_TRADES)
    rows = list(db.session.scalars(stmt).all())
    have = list(stored["wage_rate_ids"])
    seen = set(have)
    added = 0
    for row in rows:
        key = str(row.id)
        if key in seen:
            continue
        have.append(key)
        seen.add(key)
        added += 1
        if len(have) >= _MAX_TRADES:
            break
    stored["wage_rate_ids"] = have
    live, missing = _load_wage_rows(have)
    snapshots = merge_trade_snapshots(
        wage_rate_ids=[str(r.id) for r in live],
        existing=est.labor_rates if isinstance(est.labor_rates, dict) else None,
        fresh=live,
    )
    _persist_labor_rates(est, stored, snapshots)
    db.session.flush()
    out = labor_rates_public(est)
    out["imported_count"] = added
    out["truncated"] = len(rows) >= _MAX_TRADES
    if missing:
        out["missing_ids"] = missing
    return out


def rates_by_id(est: Estimate | None) -> dict[str, dict[str, Any]]:
    if est is None:
        return {}
    public = labor_rates_public(est)
    return {str(row.get("wage_rate_id") or ""): row for row in public.get("trades") or [] if row.get("wage_rate_id")}


def ensure_project_trades(est: Estimate, wage_rate_ids: list[str]) -> dict[str, dict[str, Any]]:
    if not wage_rate_ids:
        return rates_by_id(est)
    raw = est.labor_rates if isinstance(est.labor_rates, dict) else {}
    stored = stored_labor_rate_settings(settings_for_estimate(est, raw))
    have = list(stored["wage_rate_ids"])
    seen = set(have)
    extra = [wid for wid in wage_rate_ids if wid and wid not in seen]
    if extra:
        live, _missing = _load_wage_rows(extra)
        for row in live:
            key = str(row.id)
            if key in seen:
                continue
            have.append(key)
            seen.add(key)
        stored["wage_rate_ids"] = have
        snapshots = merge_trade_snapshots(
            wage_rate_ids=have,
            existing=raw,
            fresh=live,
        )
        _persist_labor_rates(est, stored, snapshots)
        db.session.flush()
    return rates_by_id(est)


def _parse_optional_uuid(raw: Any) -> uuid.UUID | None:
    if raw is None or raw == "":
        return None
    try:
        return uuid.UUID(str(raw).strip())
    except (ValueError, TypeError, AttributeError):
        raise ValueError("invalid wage_rate_id") from None


def apply_takeoff_labor(t: TakeoffLineItem, data: Mapping[str, Any], *, partial: bool) -> None:
    cost_type = str(t.cost_type or "M").upper()[:1]
    touching = (not partial) or any(k in data for k in ("wage_rate_id", "labor_crew", "cost_type", "apply_labor_rate"))
    if cost_type != "L":
        if touching or not partial:
            t.wage_rate_id = None
            t.labor_crew = None
        return
    if partial and "wage_rate_id" not in data and "labor_crew" not in data and not data.get("apply_labor_rate"):
        return
    if "labor_crew" in data or not partial:
        crew = normalize_labor_crew(data.get("labor_crew") if "labor_crew" in data or not partial else t.labor_crew)
    else:
        crew = normalize_labor_crew(t.labor_crew)
    if "wage_rate_id" in data or not partial:
        wid = _parse_optional_uuid(data.get("wage_rate_id"))
    else:
        wid = t.wage_rate_id
    if crew:
        try:
            wid = uuid.UUID(str(crew[0]["wage_rate_id"]))
        except (ValueError, TypeError, KeyError):
            pass
    t.wage_rate_id = wid
    t.labor_crew = stored_labor_crew(crew) or None
    apply_rate = bool(data.get("apply_labor_rate")) or ("unit_cost" not in data and ("wage_rate_id" in data or "labor_crew" in data or not partial))
    if not apply_rate:
        return
    est = None
    if t.estimate_id:
        est = db.session.get(Estimate, t.estimate_id)
    ids = [str(wid)] if wid else []
    ids.extend(str(row["wage_rate_id"]) for row in crew if row.get("wage_rate_id"))
    rate_map = ensure_project_trades(est, ids) if est is not None else {}
    computed = suggested_unit_cost(
        wage_rate_id=str(wid) if wid else None,
        labor_crew=crew,
        quantity=t.quantity,
        unit=t.unit,
        rates_by_id=rate_map,
    )
    if computed is not None:
        t.unit_cost = computed


def line_labor_public(t: TakeoffLineItem, labor_rates: Mapping[str, Any] | None = None) -> dict[str, Any]:
    crew = normalize_labor_crew(t.labor_crew)
    wid = str(t.wage_rate_id) if t.wage_rate_id else None
    rates = labor_rates
    if rates is None and t.estimate_id:
        est = db.session.get(Estimate, t.estimate_id)
        if est is not None:
            rates = labor_rates_public(est)
    by_id = {str(row.get("wage_rate_id") or ""): row for row in (rates or {}).get("trades") or [] if row.get("wage_rate_id")}
    enriched: list[dict[str, Any]] = []
    for row in crew:
        info = by_id.get(str(row.get("wage_rate_id") or "")) or {}
        enriched.append(
            {
                "wage_rate_id": row.get("wage_rate_id"),
                "hours": row.get("hours"),
                "trade": info.get("trade"),
                "project_loaded_hourly": info.get("project_loaded_hourly"),
            }
        )
    primary = by_id.get(wid or "") or {}
    if len(enriched) > 1:
        label = f"Crew ({len(enriched)} trades)"
    else:
        label = primary.get("trade") or (enriched[0].get("trade") if enriched else None)
    hourly = primary.get("project_loaded_hourly")
    if enriched and all(x.get("hours") is not None for x in enriched):
        total = Decimal("0")
        hours = Decimal("0")
        for row in enriched:
            rate = Decimal(str(row.get("project_loaded_hourly") or 0))
            hrs = Decimal(str(row.get("hours") or 0))
            total += rate * hrs
            hours += hrs
        if hours > 0:
            hourly = float(total / hours)
    return {
        "wage_rate_id": wid,
        "labor_crew": enriched,
        "labor_trade": label,
        "labor_rate_hourly": float(hourly) if hourly is not None else None,
    }
