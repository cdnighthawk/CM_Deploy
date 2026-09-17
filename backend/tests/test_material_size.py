"""Sheet size parse/display/order math."""
from __future__ import annotations

from decimal import Decimal

from app.material_size import (
    parse_sheet_size,
    parse_size_cell,
    sheet_area_sf,
    size_display,
    suggested_sheet_count,
)


def test_parse_inches_in_parens():
    w, h = parse_sheet_size('ASI Series 9100 Porcelain Markerboard 4x8 (48"x96")')
    assert w == Decimal("48")
    assert h == Decimal("96")


def test_parse_claridge_sku_inches():
    w, h = parse_sheet_size(None, "CLAR-CONCEPT-48X120")
    assert w == Decimal("48")
    assert h == Decimal("120")


def test_parse_feet_only():
    w, h = parse_sheet_size("Claridge LCS Deluxe Porcelain Markerboard 4x8")
    assert w == Decimal("48")
    assert h == Decimal("96")


def test_parse_size_cell_mixed_forms():
    assert parse_size_cell("48x96") == (Decimal("48"), Decimal("96"))
    assert parse_size_cell("4x8") == (Decimal("48"), Decimal("96"))


def test_size_display_and_area():
    assert size_display(48, 96) == "48×96"
    assert sheet_area_sf(48, 96) == 32.0


def test_suggested_sheets_rounds_up():
    assert suggested_sheet_count(100, "SF", 48, 96) == 4
    assert suggested_sheet_count(32, "sq ft", 48, 96) == 1
    assert suggested_sheet_count(100, "EA", 48, 96) is None
    assert suggested_sheet_count(100, "SF", None, None) is None
