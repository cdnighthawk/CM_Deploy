"""Parse and format catalog sheet sizes (inches) for order math."""
from __future__ import annotations

import math
import re
from decimal import Decimal, InvalidOperation
from typing import Any

_INCH_PAIR = re.compile(
    r'(\d+(?:\.\d+)?)\s*["″]\s*[xX×]\s*(\d+(?:\.\d+)?)\s*["″]?',
    re.IGNORECASE,
)
_INCH_VALUE = re.compile(
    r"""
    ^\s*
    (?:
        (?P<mixed_whole>\d+(?:\.\d+)?)\s*[- ]\s*(?P<mixed_num>\d+)\s*/\s*(?P<mixed_den>\d+)
        |
        (?P<frac_num>\d+)\s*/\s*(?P<frac_den>\d+)
        |
        (?P<decimal>\d+(?:\.\d+)?)
    )
    \s*(?:["″]|in(?:ch(?:es)?)?)?\s*$
    """,
    re.VERBOSE | re.IGNORECASE,
)
_STANDARD_FRAC_DENS = frozenset(
    {Decimal(2), Decimal(4), Decimal(8), Decimal(16), Decimal(32), Decimal(64)}
)
_MAX_CATALOG_INCHES = Decimal(240)
_PAREN_PAIR = re.compile(
    r"\((\d+(?:\.\d+)?)\s*[xX×]\s*(\d+(?:\.\d+)?)\)",
)
_GENERIC_PAIR = re.compile(
    r"(?<![0-9])(\d+(?:\.\d+)?)\s*[xX×]\s*(\d+(?:\.\d+)?)(?![0-9])",
)
_SF_UNITS = frozenset(
    {
        "sf",
        "s.f.",
        "s.f",
        "sqft",
        "sq.ft",
        "sq.ft.",
        "sq ft",
        "sq. ft",
        "sq. ft.",
        "square feet",
        "square foot",
    }
)


def parse_inch_value(raw: Any) -> Decimal | None:
    """Parse a catalog inch cell: ``12``, ``36.5``, ``13-5/8``, ``5/8``.

    Dual sizes (``24/72``), Excel dates, and catalog numbers over 240" are
    ignored so a messy vendor export can still load.
    """
    if raw is None:
        return None
    if isinstance(raw, Decimal):
        value = raw
    else:
        s = str(raw).strip()
        if s == "":
            return None
        match = _INCH_VALUE.match(s)
        if not match:
            return None
        if match.group("mixed_whole") is not None:
            den = Decimal(match.group("mixed_den"))
            if den not in _STANDARD_FRAC_DENS:
                return None
            value = Decimal(match.group("mixed_whole")) + (
                Decimal(match.group("mixed_num")) / den
            )
        elif match.group("frac_num") is not None:
            den = Decimal(match.group("frac_den"))
            if den not in _STANDARD_FRAC_DENS:
                return None
            value = Decimal(match.group("frac_num")) / den
        else:
            value = Decimal(match.group("decimal"))
    if value <= 0 or value > _MAX_CATALOG_INCHES:
        return None
    return value


def _dec(raw: Any) -> Decimal | None:
    if raw is None or raw == "":
        return None
    if isinstance(raw, Decimal):
        return raw
    try:
        return Decimal(str(raw).strip())
    except (InvalidOperation, ValueError, ArithmeticError):
        return None


def _valid_inches(width: Decimal, height: Decimal) -> bool:
    if width <= 0 or height <= 0:
        return False
    if width > 240 or height > 240:
        return False
    if width < 12 and height < 12:
        return False
    return True


def _pair_to_inches(a: Decimal, b: Decimal, *, as_feet: bool) -> tuple[Decimal, Decimal] | None:
    w, h = (a * 12, b * 12) if as_feet else (a, b)
    if not _valid_inches(w, h):
        return None
    return w, h


def parse_sheet_size(*parts: str | None) -> tuple[Decimal | None, Decimal | None]:
    """Return (width_in, height_in) from description / SKU / a size cell."""
    blob = " ".join(p for p in parts if (p or "").strip())
    if not blob.strip():
        return None, None

    inch = _INCH_PAIR.search(blob)
    if inch:
        parsed = _pair_to_inches(_dec(inch.group(1)) or Decimal(0), _dec(inch.group(2)) or Decimal(0), as_feet=False)
        if parsed:
            return parsed

    paren = _PAREN_PAIR.search(blob)
    if paren:
        a = _dec(paren.group(1))
        b = _dec(paren.group(2))
        if a is not None and b is not None:
            as_feet = a <= 16 and b <= 16
            parsed = _pair_to_inches(a, b, as_feet=as_feet)
            if parsed:
                return parsed

    for match in _GENERIC_PAIR.finditer(blob):
        a = _dec(match.group(1))
        b = _dec(match.group(2))
        if a is None or b is None:
            continue
        as_feet = a <= 16 and b <= 16
        parsed = _pair_to_inches(a, b, as_feet=as_feet)
        if parsed:
            return parsed
    return None, None


def parse_size_cell(raw: str | None) -> tuple[Decimal | None, Decimal | None]:
    """Parse a dedicated size column (`48x96`, `4x8`, `48 96`)."""
    s = (raw or "").strip()
    if not s:
        return None, None
    return parse_sheet_size(s)


def size_display(width: Any, height: Any, depth: Any = None) -> str | None:
    w = _dec(width)
    h = _dec(height)
    d = _dec(depth)

    def _fmt(n: Decimal) -> str:
        if n == n.to_integral_value():
            return str(int(n))
        return format(n.normalize(), "f")

    if d is not None:
        parts = [x for x in (w, d, h) if x is not None]
        if not parts:
            return None
        return "×".join(_fmt(x) for x in parts)
    if w is None or h is None:
        return None
    return f"{_fmt(w)}×{_fmt(h)}"


def sheet_area_sf(width: Any, height: Any) -> float | None:
    w = _dec(width)
    h = _dec(height)
    if w is None or h is None or w <= 0 or h <= 0:
        return None
    area = (w * h) / Decimal(144)
    return float(area)


def is_square_foot_unit(unit: str | None) -> bool:
    u = re.sub(r"\s+", " ", (unit or "").strip().lower())
    return u in _SF_UNITS


def suggested_sheet_count(quantity: Any, unit: str | None, width: Any, height: Any) -> int | None:
    if not is_square_foot_unit(unit):
        return None
    area = sheet_area_sf(width, height)
    qty = _dec(quantity)
    if area is None or qty is None or area <= 0 or qty < 0:
        return None
    return int(math.ceil(float(qty) / area)) if qty > 0 else 0
