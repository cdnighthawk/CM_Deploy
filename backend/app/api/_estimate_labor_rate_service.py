"""Estimate labor-rate worksheet: load company wages and persist job conditions."""
from __future__ import annotations

import uuid
from typing import Any, Mapping

from sqlalchemy import select

from ..extensions import db
from ..models.estimate import Estimate
from ..models.wage_rate import WageRate
from ..project_labor_rates import (
    normalize_labor_rate_settings,
    ot_schedule,
    project_rate_breakdown,
    stored_labor_rate_settings,
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


def labor_rates_public(est: Estimate, *, settings: Mapping[str, Any] | None = None) -> dict[str, Any]:
    normalized = settings_for_estimate(est, settings)
    stored = stored_labor_rate_settings(normalized)
    book = current_labor_burden_book()
    rows, missing = _load_wage_rows(stored["wage_rate_ids"])
    trades: list[dict[str, Any]] = []
    for row in rows:
        breakdown = project_rate_breakdown(row, normalized, book)
        company = wage_rate_public(row, book)
        trades.append(
            {
                "wage_rate_id": str(row.id),
                "trade": row.trade,
                "state": row.state,
                "sub_area": row.sub_area,
                "year": row.year,
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


def save_labor_rates(est: Estimate, data: Mapping[str, Any] | None) -> dict[str, Any]:
    if estimate_is_locked(est):
        raise EstimateError(
            estimate_locked_payload()["error"],
            status=403,
            error_code="ESTIMATE_LOCKED",
        )
    incoming = data if isinstance(data, Mapping) else {}
    if isinstance(incoming.get("settings"), Mapping):
        payload = dict(incoming["settings"])
        if "wage_rate_ids" in incoming:
            payload["wage_rate_ids"] = incoming.get("wage_rate_ids")
    else:
        payload = dict(incoming)
    stored = stored_labor_rate_settings(settings_for_estimate(est, payload))
    rows, missing = _load_wage_rows(stored["wage_rate_ids"])
    stored["wage_rate_ids"] = [str(row.id) for row in rows]
    est.labor_rates = stored
    db.session.flush()
    out = labor_rates_public(est)
    if missing:
        out["missing_ids"] = missing
    return out
