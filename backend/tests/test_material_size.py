"""Sheet size parse/display/order math."""
from __future__ import annotations

from decimal import Decimal

from app.material_size import (
    parse_inch_value,
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


def test_parse_inch_fractions_and_decimals():
    assert parse_inch_value("13-5/8") == Decimal("13.625")
    assert parse_inch_value("13 5/8") == Decimal("13.625")
    assert parse_inch_value("16-1/4") == Decimal("16.25")
    assert parse_inch_value("36-1/2") == Decimal("36.5")
    assert parse_inch_value("5/8") == Decimal("0.625")
    assert parse_inch_value("36.5") == Decimal("36.5")
    assert parse_inch_value("12") == Decimal("12")
    assert parse_inch_value("") is None
    assert parse_inch_value(None) is None
    assert parse_inch_value("20/60") is None
    assert parse_inch_value("1/1/2004") is None
    assert parse_inch_value("66158") is None


def test_size_display_and_area():
    assert size_display(48, 96) == "48×96"
    assert size_display(12, Decimal("13.625"), 18) == "12×18×13.625"
    assert sheet_area_sf(48, 96) == 32.0


def test_suggested_sheets_rounds_up():
    assert suggested_sheet_count(100, "SF", 48, 96) == 4
    assert suggested_sheet_count(32, "sq ft", 48, 96) == 1
    assert suggested_sheet_count(100, "EA", 48, 96) is None
    assert suggested_sheet_count(100, "SF", None, None) is None
