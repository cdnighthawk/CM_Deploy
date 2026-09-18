"""Production-rate labor math."""
from __future__ import annotations

from decimal import Decimal

from app.material_labor import (
    hours_per_unit,
    labor_hours_for_quantity,
    labor_hours_for_takeoff,
    labor_production_display,
    normalize_rate_unit,
)


def test_normalize_rate_units():
    assert normalize_rate_unit("SQFT Per Hour") == "SF"
    assert normalize_rate_unit("Feet per hour") == "LF"
    assert normalize_rate_unit("lf") == "LF"
    assert normalize_rate_unit("each") == "EA"
    assert normalize_rate_unit("") is None


def test_thirty_sf_per_hour():
    assert hours_per_unit(30) == Decimal("0.0333")
    assert labor_hours_for_quantity(30, 30) == Decimal("1.0000")
    assert labor_hours_for_quantity(90, 30) == Decimal("3.0000")
    assert labor_production_display(30, "SF") == "30 SF/hr"


def test_eight_lf_per_hour():
    assert hours_per_unit(8) == Decimal("0.1250")
    assert labor_hours_for_quantity(16, 8) == Decimal("2.0000")
    assert labor_production_display(8, "LF") == "8 LF/hr"
    assert labor_hours_for_quantity(16, 8, "FT", "LF") == Decimal("2.0000")
    assert labor_hours_for_quantity(192, 8, "IN", "LF") == Decimal("2.0000")
    assert labor_hours_for_quantity(1, 8, "EA", "LF") is None
    assert labor_hours_for_takeoff(
        3, "EA", catalog_uom="EA", labor_per=Decimal("0.1667")
    ) == Decimal("0.5001")
    assert (
        labor_hours_for_takeoff(
            16, "EA", catalog_uom="LF", labor_per=Decimal("0.1250"), units_per_hour=8, rate_unit="LF"
        )
        is None
    )
    assert labor_hours_for_takeoff(
        16, "FT", catalog_uom="LF", units_per_hour=8, rate_unit="LF"
    ) == Decimal("2.0000")


def test_rigid_sheet_sf_from_length_times_height():
    assert labor_hours_for_takeoff(
        90, "SF", catalog_uom="SF", units_per_hour=30, rate_unit="SF"
    ) == Decimal("3.0000")
    assert labor_hours_for_takeoff(
        20,
        "LF",
        catalog_uom="SF",
        units_per_hour=30,
        rate_unit="SF",
        size_width_in=Decimal("48"),
        size_height_in=Decimal("96"),
    ) == Decimal("5.3333")
    assert labor_hours_for_takeoff(
        1,
        "EA",
        catalog_uom="EA",
        units_per_hour=30,
        rate_unit="SF",
        size_width_in=Decimal("48"),
        size_height_in=Decimal("96"),
    ) == Decimal("1.0667")


def test_sync_ea_allows_sf_not_lf():
    from types import SimpleNamespace

    from app.material_labor import sync_material_labor

    ea_lf = SimpleNamespace(
        unit_of_measure="EA",
        labor_per=Decimal("0.1667"),
        labor_units_per_hour=Decimal("8"),
        labor_rate_unit="LF",
    )
    sync_material_labor(ea_lf)
    assert ea_lf.unit_of_measure == "EA"
    assert ea_lf.labor_per == Decimal("0.1667")
    assert ea_lf.labor_units_per_hour is None
    assert ea_lf.labor_rate_unit is None

    ea_sf = SimpleNamespace(
        unit_of_measure="EA",
        labor_per=None,
        labor_units_per_hour=Decimal("30"),
        labor_rate_unit="SF",
    )
    sync_material_labor(ea_sf)
    assert ea_sf.unit_of_measure == "SF"
    assert ea_sf.labor_rate_unit == "SF"
    assert ea_sf.labor_units_per_hour == Decimal("30")
    assert ea_sf.labor_per == Decimal("0.0333")
