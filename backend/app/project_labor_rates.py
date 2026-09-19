"""Project-specific estimating rates on top of company prevailing wages.

Company loaded hourly is the DIR package plus employer burden (see
``labor_burden``). Job conditions convert to extra dollars per clock hour:

* mandated OT — 1.5x after 8/day and 40/week, 2.0x after 12/day, on basic
  wage only; extra taxable wages also pick up company burden
* per diem — dollars per day / hours per day (not burdened)
* housing — dollars per week / (days × hours) (not burdened)
* other — dollars per hour catch-all (not burdened)
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Mapping, Sequence
from uuid import UUID

from .labor_burden import (
    labor_burden_breakdown,
    normalize_state_code,
)

_HOUR = Decimal("0.0001")
_MONEY = Decimal("0.0001")
_ST_DAY = Decimal("8")
_DT_DAY = Decimal("12")
_ST_WEEK = Decimal("40")
_OT_MULT = Decimal("1.5")
_DT_MULT = Decimal("2")
_MAX_TRADES = 50

DEFAULT_HOURS_PER_DAY = Decimal("8")
DEFAULT_DAYS_PER_WEEK = Decimal("5")


def _dec(val: Any) -> Decimal:
    if val is None or val == "":
        return Decimal("0")
    if isinstance(val, Decimal):
        return val
    try:
        return Decimal(str(val))
    except Exception:
        return Decimal("0")


def _money(val: Decimal) -> Decimal:
    return val.quantize(_MONEY, rounding=ROUND_HALF_UP)


def _float(val: Decimal) -> float:
    return float(_money(val))


def _clamp_hours_per_day(val: Any, *, default: Decimal = DEFAULT_HOURS_PER_DAY) -> Decimal:
    n = _dec(val) if val is not None and str(val).strip() != "" else default
    if n < Decimal("0.25"):
        return Decimal("0.25")
    if n > Decimal("24"):
        return Decimal("24")
    return n.quantize(_HOUR, rounding=ROUND_HALF_UP)


def _clamp_days_per_week(val: Any, *, default: Decimal = DEFAULT_DAYS_PER_WEEK) -> Decimal:
    n = _dec(val) if val is not None and str(val).strip() != "" else default
    if n < Decimal("1"):
        return Decimal("1")
    if n > Decimal("7"):
        return Decimal("7")
    return n.quantize(_HOUR, rounding=ROUND_HALF_UP)


def _nonneg_money(val: Any) -> Decimal:
    n = _dec(val)
    if n < 0:
        return Decimal("0")
    return _money(n)


def _year(val: Any, *, default: int | None = None) -> int:
    fallback = int(datetime.now().year if default is None else default)
    if val is None or str(val).strip() == "":
        return fallback
    try:
        year = int(str(val).strip())
    except (TypeError, ValueError):
        return fallback
    if year < 1900 or year > 2100:
        return fallback
    return year


def _uuid_list(raw: Any) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, str):
        items = [raw]
    elif isinstance(raw, Sequence) and not isinstance(raw, (bytes, bytearray)):
        items = list(raw)
    else:
        return []
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        s = str(item or "").strip()
        if not s:
            continue
        try:
            key = str(UUID(s))
        except (ValueError, TypeError, AttributeError):
            continue
        if key in seen:
            continue
        seen.add(key)
        out.append(key)
        if len(out) >= _MAX_TRADES:
            break
    return out


def default_year() -> int:
    return int(datetime.now().year)


def normalize_labor_rate_settings(
    raw: Mapping[str, Any] | None,
    *,
    default_state: str = "",
    default_year: int | None = None,
) -> dict[str, Any]:
    src = raw if isinstance(raw, Mapping) else {}
    state = normalize_state_code(src.get("state") or "") or normalize_state_code(default_state)
    return {
        "state": state,
        "year": _year(src.get("year"), default=default_year),
        "sub_area": str(src.get("sub_area") or "").strip()[:80],
        "hours_per_day": _clamp_hours_per_day(src.get("hours_per_day")),
        "days_per_week": _clamp_days_per_week(src.get("days_per_week")),
        "per_diem_per_day": _nonneg_money(src.get("per_diem_per_day")),
        "housing_per_week": _nonneg_money(src.get("housing_per_week")),
        "other_hourly": _nonneg_money(src.get("other_hourly")),
        "wage_rate_ids": _uuid_list(src.get("wage_rate_ids")),
    }


def stored_labor_rate_settings(settings: Mapping[str, Any]) -> dict[str, Any]:
    normalized = normalize_labor_rate_settings(settings)
    return {
        "state": normalized["state"],
        "year": int(normalized["year"]),
        "sub_area": normalized["sub_area"],
        "hours_per_day": float(normalized["hours_per_day"]),
        "days_per_week": float(normalized["days_per_week"]),
        "per_diem_per_day": float(normalized["per_diem_per_day"]),
        "housing_per_week": float(normalized["housing_per_week"]),
        "other_hourly": float(normalized["other_hourly"]),
        "wage_rate_ids": list(normalized["wage_rate_ids"]),
    }


def settings_public(settings: Mapping[str, Any]) -> dict[str, Any]:
    return stored_labor_rate_settings(settings)


def ot_schedule(hours_per_day: Any, days_per_week: Any) -> dict[str, Any]:
    hours = _clamp_hours_per_day(hours_per_day)
    days = _clamp_days_per_week(days_per_week)
    clock = _money(hours * days)
    if clock <= 0:
        return {
            "hours_per_day": float(hours),
            "days_per_week": float(days),
            "clock_hours": 0.0,
            "st_hours": 0.0,
            "ot_hours": 0.0,
            "dt_hours": 0.0,
            "pay_factor": 1.0,
        }
    dt_day = max(hours - _DT_DAY, Decimal("0"))
    ot_day = max(min(hours, _DT_DAY) - _ST_DAY, Decimal("0"))
    st_day = min(hours, _ST_DAY)
    st = st_day * days
    ot = ot_day * days
    dt = dt_day * days
    if st > _ST_WEEK:
        extra = st - _ST_WEEK
        st = _ST_WEEK
        ot += extra
    pay_hours = st + (ot * _OT_MULT) + (dt * _DT_MULT)
    pay_factor = pay_hours / clock
    return {
        "hours_per_day": float(hours),
        "days_per_week": float(days),
        "clock_hours": _float(clock),
        "st_hours": _float(st),
        "ot_hours": _float(ot),
        "dt_hours": _float(dt),
        "pay_factor": float(pay_factor.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)),
    }


def _attr(row: Any, name: str) -> Any:
    if isinstance(row, Mapping):
        return row.get(name)
    return getattr(row, name, None)


def reimbursement_adders(settings: Mapping[str, Any]) -> dict[str, Decimal]:
    hours = _clamp_hours_per_day(settings.get("hours_per_day"))
    days = _clamp_days_per_week(settings.get("days_per_week"))
    clock = hours * days
    per_diem = _nonneg_money(settings.get("per_diem_per_day"))
    housing = _nonneg_money(settings.get("housing_per_week"))
    other = _nonneg_money(settings.get("other_hourly"))
    per_diem_hourly = _money(per_diem / hours) if hours > 0 else Decimal("0")
    housing_hourly = _money(housing / clock) if clock > 0 else Decimal("0")
    return {
        "per_diem_hourly": per_diem_hourly,
        "housing_hourly": housing_hourly,
        "other_hourly": other,
    }


def project_rate_breakdown(
    row: Any,
    settings: Mapping[str, Any],
    burden: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    normalized = normalize_labor_rate_settings(settings)
    company = labor_burden_breakdown(row, burden)
    schedule = ot_schedule(normalized["hours_per_day"], normalized["days_per_week"])
    pay_factor = Decimal(str(schedule["pay_factor"]))
    basic = _dec(_attr(row, "basic_hourly_rate"))
    ot_premium = _money(basic * (pay_factor - Decimal("1")))
    burden_pct = _dec(company.get("burden_pct"))
    extra_burden = _money(ot_premium * burden_pct / Decimal("100"))
    ot_hourly = _money(ot_premium + extra_burden)
    reimbursed = reimbursement_adders(normalized)
    company_loaded = _dec(company.get("total_loaded_hourly"))
    project_loaded = _money(
        company_loaded
        + ot_hourly
        + reimbursed["per_diem_hourly"]
        + reimbursed["housing_hourly"]
        + reimbursed["other_hourly"]
    )
    adders = [
        {"key": "ot", "label": "Mandated overtime", "amount": _float(ot_hourly)},
        {"key": "per_diem", "label": "Per diem", "amount": _float(reimbursed["per_diem_hourly"])},
        {"key": "housing", "label": "Housing", "amount": _float(reimbursed["housing_hourly"])},
        {"key": "other", "label": "Other", "amount": _float(reimbursed["other_hourly"])},
    ]
    return {
        "company_loaded_hourly": _float(company_loaded),
        "ot_hourly": _float(ot_hourly),
        "ot_premium_hourly": _float(ot_premium),
        "ot_burden_hourly": _float(extra_burden),
        "per_diem_hourly": _float(reimbursed["per_diem_hourly"]),
        "housing_hourly": _float(reimbursed["housing_hourly"]),
        "other_hourly": _float(reimbursed["other_hourly"]),
        "project_loaded_hourly": _float(project_loaded),
        "schedule": schedule,
        "company": company,
        "adders": adders,
    }


def compact_labor_rates_summary(raw: Mapping[str, Any] | None) -> dict[str, Any]:
    settings = stored_labor_rate_settings(normalize_labor_rate_settings(raw))
    return {
        "state": settings["state"],
        "year": settings["year"],
        "sub_area": settings["sub_area"],
        "hours_per_day": settings["hours_per_day"],
        "days_per_week": settings["days_per_week"],
        "per_diem_per_day": settings["per_diem_per_day"],
        "housing_per_week": settings["housing_per_week"],
        "other_hourly": settings["other_hourly"],
        "trade_count": len(settings["wage_rate_ids"]),
        "project_loaded_hourly": None,
    }
