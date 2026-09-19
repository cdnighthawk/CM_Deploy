"""Employer labor burden on prevailing-wage rates.

DIR / prevailing-wage rows are base wage plus fringes (health, pension,
vacation, training). The contractor's fully loaded estimating rate also
includes payroll taxes, unemployment, and workers' compensation. Those
percentages apply to taxable wages (basic hourly + vacation/holiday), not
to trust-paid fringes.
"""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Mapping

_HOUR = Decimal("0.0001")
_PCT = Decimal("0.0001")

BURDEN_FIELDS: tuple[tuple[str, str], ...] = (
    ("social_security_pct", "Social Security"),
    ("medicare_pct", "Medicare"),
    ("futa_pct", "Federal unemployment (FUTA)"),
    ("suta_pct", "State unemployment"),
    ("workers_comp_pct", "Workers' compensation"),
    ("other_pct", "Other (GL, etc.)"),
)

DEFAULT_LABOR_BURDEN: dict[str, float] = {
    "social_security_pct": 6.2,
    "medicare_pct": 1.45,
    "futa_pct": 0.6,
    "suta_pct": 0.0,
    "workers_comp_pct": 0.0,
    "other_pct": 0.0,
}

_FRINGE_ATTRS = (
    "basic_hourly_rate",
    "health_welfare",
    "pension",
    "vacation_holiday",
    "other_payments",
    "training",
)


def _dec(val: Any) -> Decimal:
    if val is None or val == "":
        return Decimal("0")
    if isinstance(val, Decimal):
        return val
    try:
        return Decimal(str(val))
    except Exception:
        return Decimal("0")


def _pct(val: Any) -> Decimal:
    n = _dec(val)
    if n < 0:
        return Decimal("0")
    if n > Decimal("100"):
        return Decimal("100")
    return n.quantize(_PCT, rounding=ROUND_HALF_UP)


def _money(val: Decimal) -> Decimal:
    return val.quantize(_HOUR, rounding=ROUND_HALF_UP)


def _float(val: Decimal) -> float:
    return float(_money(val))


def normalize_labor_burden(raw: Mapping[str, Any] | None) -> dict[str, float]:
    src = raw if isinstance(raw, Mapping) else {}
    out: dict[str, float] = {}
    for key, _label in BURDEN_FIELDS:
        if key in src and src.get(key) is not None and str(src.get(key)).strip() != "":
            out[key] = float(_pct(src.get(key)))
        else:
            out[key] = float(_pct(DEFAULT_LABOR_BURDEN[key]))
    return out


def _attr(row: Any, name: str) -> Any:
    if isinstance(row, Mapping):
        return row.get(name)
    return getattr(row, name, None)


def fringe_hourly(row: Any) -> Decimal:
    total = Decimal("0")
    for name in _FRINGE_ATTRS:
        val = _attr(row, name)
        if val is not None and str(val).strip() != "":
            total += _dec(val)
    return _money(total)


def taxable_hourly(row: Any) -> Decimal:
    total = Decimal("0")
    for name in ("basic_hourly_rate", "vacation_holiday"):
        val = _attr(row, name)
        if val is not None and str(val).strip() != "":
            total += _dec(val)
    return _money(total)


def labor_burden_breakdown(
    row: Any,
    burden: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    rates = normalize_labor_burden(burden)
    override = _attr(row, "workers_comp_pct")
    if override is not None and str(override).strip() != "":
        rates["workers_comp_pct"] = float(_pct(override))
    taxable = taxable_hourly(row)
    fringe = fringe_hourly(row)
    lines: list[dict[str, Any]] = []
    burden_total = Decimal("0")
    pct_total = Decimal("0")
    for key, label in BURDEN_FIELDS:
        pct = _pct(rates[key])
        amount = _money(taxable * pct / Decimal("100"))
        lines.append(
            {
                "key": key,
                "label": label,
                "pct": float(pct),
                "amount": float(amount),
            }
        )
        burden_total += amount
        pct_total += pct
    loaded = _money(fringe + burden_total)
    return {
        "taxable_hourly": _float(taxable),
        "fringe_hourly": _float(fringe),
        "burden_hourly": _float(burden_total),
        "burden_pct": float(pct_total.quantize(_PCT, rounding=ROUND_HALF_UP)),
        "total_loaded_hourly": _float(loaded),
        "workers_comp_pct": rates["workers_comp_pct"],
        "lines": lines,
    }
