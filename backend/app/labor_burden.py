"""Employer labor burden on prevailing-wage rates.

DIR / prevailing-wage rows are base wage plus fringes (health, pension,
vacation, training). The contractor's fully loaded estimating rate also
includes payroll taxes, unemployment, and workers' compensation. Those
percentages apply to taxable wages (basic hourly + vacation/holiday), not
to trust-paid fringes.

Federal payroll taxes are the same everywhere. Unemployment, workers' comp,
and other burden are set per state (CA, FL, HI, plus any others the company
adds).
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

FEDERAL_FIELDS: tuple[str, ...] = (
    "social_security_pct",
    "medicare_pct",
    "futa_pct",
)
STATE_FIELDS: tuple[str, ...] = (
    "suta_pct",
    "workers_comp_pct",
    "other_pct",
)

DEFAULT_LABOR_BURDEN: dict[str, float] = {
    "social_security_pct": 6.2,
    "medicare_pct": 1.45,
    "futa_pct": 0.6,
    "suta_pct": 0.0,
    "workers_comp_pct": 0.0,
    "other_pct": 0.0,
}

HOME_STATE_CODES: tuple[str, ...] = ("CA", "FL", "HI")

US_STATES: tuple[tuple[str, str], ...] = (
    ("AL", "Alabama"),
    ("AK", "Alaska"),
    ("AZ", "Arizona"),
    ("AR", "Arkansas"),
    ("CA", "California"),
    ("CO", "Colorado"),
    ("CT", "Connecticut"),
    ("DC", "District of Columbia"),
    ("DE", "Delaware"),
    ("FL", "Florida"),
    ("GA", "Georgia"),
    ("HI", "Hawaii"),
    ("ID", "Idaho"),
    ("IL", "Illinois"),
    ("IN", "Indiana"),
    ("IA", "Iowa"),
    ("KS", "Kansas"),
    ("KY", "Kentucky"),
    ("LA", "Louisiana"),
    ("ME", "Maine"),
    ("MD", "Maryland"),
    ("MA", "Massachusetts"),
    ("MI", "Michigan"),
    ("MN", "Minnesota"),
    ("MS", "Mississippi"),
    ("MO", "Missouri"),
    ("MT", "Montana"),
    ("NE", "Nebraska"),
    ("NV", "Nevada"),
    ("NH", "New Hampshire"),
    ("NJ", "New Jersey"),
    ("NM", "New Mexico"),
    ("NY", "New York"),
    ("NC", "North Carolina"),
    ("ND", "North Dakota"),
    ("OH", "Ohio"),
    ("OK", "Oklahoma"),
    ("OR", "Oregon"),
    ("PA", "Pennsylvania"),
    ("RI", "Rhode Island"),
    ("SC", "South Carolina"),
    ("SD", "South Dakota"),
    ("TN", "Tennessee"),
    ("TX", "Texas"),
    ("UT", "Utah"),
    ("VT", "Vermont"),
    ("VA", "Virginia"),
    ("WA", "Washington"),
    ("WV", "West Virginia"),
    ("WI", "Wisconsin"),
    ("WY", "Wyoming"),
)

_CODE_TO_NAME: dict[str, str] = {code: name for code, name in US_STATES}
_NAME_TO_CODE: dict[str, str] = {name.upper(): code for code, name in US_STATES}

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


def _field_pct(src: Mapping[str, Any], key: str, fallback: Mapping[str, Any] | None = None) -> float:
    if key in src and src.get(key) is not None and str(src.get(key)).strip() != "":
        return float(_pct(src.get(key)))
    if fallback is not None and key in fallback:
        return float(_pct(fallback[key]))
    return float(_pct(DEFAULT_LABOR_BURDEN[key]))


def normalize_state_code(raw: Any) -> str:
    s = str(raw or "").strip()
    if not s:
        return ""
    up = s.upper()
    if up in _CODE_TO_NAME:
        return up
    if up in _NAME_TO_CODE:
        return _NAME_TO_CODE[up]
    return up


def state_display_name(code: str) -> str:
    return _CODE_TO_NAME.get(code, code)


def normalize_labor_burden(raw: Mapping[str, Any] | None) -> dict[str, float]:
    src = raw if isinstance(raw, Mapping) else {}
    if "states" in src:
        return labor_burden_for_state(src, src.get("state") or "")
    out: dict[str, float] = {}
    for key, _label in BURDEN_FIELDS:
        out[key] = _field_pct(src, key)
    return out


def _state_rates(src: Mapping[str, Any], fallback: Mapping[str, float]) -> dict[str, float]:
    return {key: _field_pct(src, key, fallback) for key in STATE_FIELDS}


def _iter_raw_states(raw_states: Any) -> list[tuple[str, Mapping[str, Any]]]:
    if isinstance(raw_states, Mapping):
        return [(str(code), payload if isinstance(payload, Mapping) else {}) for code, payload in raw_states.items()]
    if isinstance(raw_states, list):
        out: list[tuple[str, Mapping[str, Any]]] = []
        for item in raw_states:
            if not isinstance(item, Mapping):
                continue
            out.append((str(item.get("state") or ""), item))
        return out
    return []


def normalize_labor_burden_book(raw: Mapping[str, Any] | None) -> dict[str, Any]:
    src = raw if isinstance(raw, Mapping) else {}
    federal = {key: _field_pct(src, key) for key in FEDERAL_FIELDS}
    defaults = {key: _field_pct(src, key) for key in STATE_FIELDS}
    states: dict[str, dict[str, float]] = {}
    for code_raw, payload in _iter_raw_states(src.get("states")):
        code = normalize_state_code(code_raw)
        if not code:
            continue
        states[code] = _state_rates(payload, defaults)
    if "states" not in src:
        for code in HOME_STATE_CODES:
            states[code] = dict(defaults)
    else:
        for code in HOME_STATE_CODES:
            states.setdefault(code, dict(defaults))
    return {**federal, **defaults, "states": states}


def labor_burden_for_state(book: Mapping[str, Any] | None, state: Any) -> dict[str, float]:
    normalized = normalize_labor_burden_book(book)
    code = normalize_state_code(state)
    state_rates = normalized["states"].get(code)
    if state_rates is None:
        state_rates = {key: normalized[key] for key in STATE_FIELDS}
    return {**{key: normalized[key] for key in FEDERAL_FIELDS}, **state_rates}


def public_labor_burden(book: Mapping[str, Any] | None) -> dict[str, Any]:
    normalized = normalize_labor_burden_book(book)
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for code in HOME_STATE_CODES:
        seen.add(code)
        rates = normalized["states"].get(code) or {key: normalized[key] for key in STATE_FIELDS}
        rows.append(_public_state_row(code, rates, locked=True))
    extras = [code for code in normalized["states"] if code not in seen]
    extras.sort(key=lambda code: (state_display_name(code), code))
    for code in extras:
        rows.append(_public_state_row(code, normalized["states"][code], locked=False))
    return {
        **{key: normalized[key] for key in FEDERAL_FIELDS},
        **{key: normalized[key] for key in STATE_FIELDS},
        "states": rows,
        "catalog": [{"state": code, "name": name} for code, name in US_STATES],
    }


def stored_labor_burden(book: Mapping[str, Any] | None) -> dict[str, Any]:
    normalized = normalize_labor_burden_book(book)
    return {
        **{key: normalized[key] for key in FEDERAL_FIELDS},
        **{key: normalized[key] for key in STATE_FIELDS},
        "states": {code: dict(rates) for code, rates in normalized["states"].items()},
    }


def _public_state_row(code: str, rates: Mapping[str, float], *, locked: bool) -> dict[str, Any]:
    return {
        "state": code,
        "name": state_display_name(code),
        "locked": locked,
        **{key: float(rates[key]) for key in STATE_FIELDS},
    }


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
    if isinstance(burden, Mapping) and "states" in burden:
        rates = labor_burden_for_state(burden, _attr(row, "state"))
    else:
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
