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


def size_display(width: Any, height: Any) -> str | None:
    w = _dec(width)
    h = _dec(height)
    if w is None or h is None:
        return None
    def _fmt(n: Decimal) -> str:
        if n == n.to_integral_value():
            return str(int(n))
        return format(n.normalize(), "f")

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
