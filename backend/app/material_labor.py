"""Production-rate labor: hours = quantity ÷ units-per-hour."""
from __future__ import annotations

import re
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

RATE_SF = "SF"
RATE_LF = "LF"
RATE_EA = "EA"
RATE_UNITS = (RATE_SF, RATE_LF, RATE_EA)
_HOUR_QUANT = Decimal("0.0001")

_SF_ALIASES = frozenset(
    {
        "sf",
        "s.f",
        "s.f.",
        "sqft",
        "sq.ft",
        "sq.ft.",
        "sq ft",
        "sq. ft",
        "sq. ft.",
        "square foot",
        "square feet",
        "sqft per hour",
        "sf/hr",
        "sf/h",
    }
)
_LF_ALIASES = frozenset(
    {
        "lf",
        "lin ft",
        "lin. ft",
        "linear foot",
        "linear feet",
        "ft",
        "feet",
        "foot",
        "feet per hour",
        "lf/hr",
        "lf/h",
        "ft/hr",
    }
)
_EA_ALIASES = frozenset({"ea", "each", "pc", "pcs", "piece", "unit"})


def _dec(raw: Any) -> Decimal | None:
    if raw is None or raw == "":
        return None
    if isinstance(raw, Decimal):
        return raw
    try:
        return Decimal(str(raw).strip())
    except Exception:
        return None


def normalize_rate_unit(raw: str | None) -> str | None:
    """Map a production-rate unit to SF, LF, or EA."""
    if raw is None:
        return None
    s = re.sub(r"\s+", " ", str(raw).strip().lower())
    if not s:
        return None
    s = s.replace("per hour", "").replace("/hour", "").replace("/hr", "").strip()
    if s in _SF_ALIASES or s.startswith("sq"):
        return RATE_SF
    if s in _LF_ALIASES:
        return RATE_LF
    if s in _EA_ALIASES:
        return RATE_EA
    if s in {"sf", "lf", "ea"}:
        return s.upper()
    return None


def hours_per_unit(units_per_hour: Any) -> Decimal | None:
    """Hours for one catalog unit: 1 / production rate."""
    rate = _dec(units_per_hour)
    if rate is None or rate <= 0:
        return None
    return (Decimal(1) / rate).quantize(_HOUR_QUANT, rounding=ROUND_HALF_UP)


def _norm_measure(raw: str | None) -> str:
    return re.sub(r"\s+", " ", (raw or "").strip().lower())


def _height_ft(size_width_in: Any = None, size_height_in: Any = None) -> Decimal | None:
    h = _dec(size_height_in) or _dec(size_width_in)
    if h is None or h <= 0:
        return None
    return h / Decimal(12)


def _sheet_area_sf(size_width_in: Any = None, size_height_in: Any = None) -> Decimal | None:
    w = _dec(size_width_in)
    h = _dec(size_height_in)
    if w is None or h is None or w <= 0 or h <= 0:
        return None
    return (w * h) / Decimal(144)


def quantity_in_rate_unit(
    quantity: Any,
    takeoff_unit: str | None,
    rate_unit: str | None,
    *,
    size_width_in: Any = None,
    size_height_in: Any = None,
) -> Decimal | None:
    """Convert a takeoff quantity into the production-rate unit (LF or SF).

    EA never converts into linear feet. Rigid sheet / FRP convert into SF
    from takeoff SF, or from length × sheet height, or from sheet count × area.
    """
    qty = _dec(quantity)
    if qty is None:
        return None
    target = normalize_rate_unit(rate_unit)
    src = normalize_rate_unit(takeoff_unit) if takeoff_unit else None
    if target == RATE_EA:
        return None
    if src == RATE_EA and target == RATE_LF:
        return None
    if not target:
        return qty
    if not takeoff_unit:
        return qty
    if src == target:
        return qty
    raw = _norm_measure(takeoff_unit)
    if target == RATE_LF:
        if raw in {"in", "inch", "inches", '"'}:
            return qty / Decimal(12)
        if src == RATE_LF:
            return qty
        return None
    if target == RATE_SF:
        if src == RATE_SF:
            return qty
        if src == RATE_EA:
            area = _sheet_area_sf(size_width_in, size_height_in)
            return qty * area if area is not None else None
        height_ft = _height_ft(size_width_in, size_height_in)
        if height_ft is None:
            return None
        if src == RATE_LF:
            return qty * height_ft
        if raw in {"in", "inch", "inches", '"'}:
            return (qty / Decimal(12)) * height_ft
    return None


def labor_hours_for_takeoff(
    quantity: Any,
    takeoff_unit: str | None,
    *,
    catalog_uom: str | None,
    labor_per: Any = None,
    units_per_hour: Any = None,
    rate_unit: str | None = None,
    size_width_in: Any = None,
    size_height_in: Any = None,
) -> Decimal | None:
    """Hours for a takeoff line.

    EA catalog items use hours-per-each unless labor is an SF production
    rate (rigid sheet / FRP: length × height = SF). Feet-per-hour never
    applies to EA.
    """
    qty = _dec(quantity)
    if qty is None:
        return None
    takeoff = normalize_rate_unit(takeoff_unit) if takeoff_unit else None
    catalog = normalize_rate_unit(catalog_uom)
    rate_u = normalize_rate_unit(rate_unit)
    sf_rate = bool(units_per_hour) and rate_u == RATE_SF
    if catalog == RATE_EA and not sf_rate:
        hours_each = _dec(labor_per)
        if hours_each is None:
            return None
        return (qty * hours_each).quantize(_HOUR_QUANT, rounding=ROUND_HALF_UP)
    if takeoff == RATE_EA and not sf_rate:
        hours_each = _dec(labor_per) if catalog == RATE_EA else None
        if hours_each is None:
            return None
        return (qty * hours_each).quantize(_HOUR_QUANT, rounding=ROUND_HALF_UP)
    if units_per_hour:
        return labor_hours_for_quantity(
            qty,
            units_per_hour,
            takeoff_unit,
            rate_unit,
            size_width_in=size_width_in,
            size_height_in=size_height_in,
        )
    hours_each = _dec(labor_per)
    if hours_each is None:
        return None
    return (qty * hours_each).quantize(_HOUR_QUANT, rounding=ROUND_HALF_UP)


def labor_hours_for_quantity(
    quantity: Any,
    units_per_hour: Any,
    takeoff_unit: str | None = None,
    rate_unit: str | None = None,
    *,
    size_width_in: Any = None,
    size_height_in: Any = None,
) -> Decimal | None:
    """Install hours from a production rate. EA × LF/hr is not used."""
    rate = _dec(units_per_hour)
    if rate is None or rate <= 0:
        return None
    takeoff = normalize_rate_unit(takeoff_unit)
    unit = normalize_rate_unit(rate_unit)
    if unit == RATE_EA or (takeoff == RATE_EA and unit == RATE_LF):
        return None
    qty = quantity_in_rate_unit(
        quantity,
        takeoff_unit,
        rate_unit,
        size_width_in=size_width_in,
        size_height_in=size_height_in,
    )
    if qty is None:
        return None
    return (qty / rate).quantize(_HOUR_QUANT, rounding=ROUND_HALF_UP)


def labor_production_display(units_per_hour: Any, rate_unit: str | None) -> str | None:
    rate = _dec(units_per_hour)
    unit = normalize_rate_unit(rate_unit)
    if rate is None or unit is None:
        return None
    if rate == rate.to_integral_value():
        qty = str(int(rate))
    else:
        qty = format(rate.normalize(), "f")
    return f"{qty} {unit}/hr"


def sync_material_labor(row: Any) -> None:
    """Derive ``labor_per`` from a production rate.

    EA items stay hours-per-each for feet-per-hour. SQFT-per-hour (rigid
    sheet / FRP) is allowed on EA catalog rows and sets UOM to SF.
    """
    catalog = normalize_rate_unit(getattr(row, "unit_of_measure", None))
    rate = _dec(getattr(row, "labor_units_per_hour", None))
    unit = normalize_rate_unit(getattr(row, "labor_rate_unit", None))
    if catalog == RATE_EA and unit == RATE_LF:
        row.labor_units_per_hour = None
        row.labor_rate_unit = None
        return
    if rate is None or unit is None:
        return
    if rate <= 0:
        return
    if unit not in (RATE_SF, RATE_LF):
        return
    hours = hours_per_unit(rate)
    if hours is None:
        return
    row.labor_units_per_hour = rate
    row.labor_rate_unit = unit
    row.labor_per = hours
    if unit == RATE_SF or catalog in (None, unit):
        row.unit_of_measure = unit
