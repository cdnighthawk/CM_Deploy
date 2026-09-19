"""Unit tests for material CSV normalization (no database)."""
from __future__ import annotations

import csv
import tempfile
from decimal import Decimal
from pathlib import Path

from scripts.material_csv_row import (
    CatalogOldRow,
    is_target_manufacturer,
    plan_manufacturer_replace,
    read_material_csv,
    sku_key,
)


def test_read_bobrick_style_headers():
    with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(
            ["Manufacturer", "Item", "Category", "Cost", "Description", "Mounting Type", "Labor Per"]
        )
        w.writerow(["Bobrick", "B-123", "Grab Bar", "45.00", "Stainless bar", "Surface", "12.5"])
        path = Path(f.name)
    try:
        rows = read_material_csv(path)
        assert len(rows) == 1
        assert rows[0]["manufacturer"] == "Bobrick"
        assert rows[0]["item"] == "B-123"
        assert str(rows[0]["cost"]) == "45.00"
        assert rows[0]["mounting_type"] == "Surface"
    finally:
        path.unlink(missing_ok=True)


def test_read_url_and_family_aliases():
    with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Manufacturer", "SKU", "Family", "Description", "URL", "CSI Spec Section"])
        w.writerow(
            [
                "JL Industries",
                "C1013F10",
                "Fire Extinguisher Cabinet",
                "Ambassador surface cabinet",
                "https://www.activarcpg.com/product/ambassador-series-steel/",
                "10 44 00",
            ]
        )
        path = Path(f.name)
    try:
        rows = read_material_csv(path)
        assert rows[0]["category"] == "Fire Extinguisher Cabinet"
        assert rows[0]["csi_spec_section"] == "104400"
        assert rows[0]["manufacturer_url"] == "https://www.activarcpg.com/product/ambassador-series-steel/"
        assert rows[0]["description"] == "Ambassador surface cabinet"
        assert "activarcpg.com" not in (rows[0]["description"] or "")
    finally:
        path.unlink(missing_ok=True)


def test_read_trailing_url_from_description():
    with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Manufacturer", "Item", "Description"])
        w.writerow(
            [
                "Inpro",
                "INPRO-333",
                "Inpro Extension Roller 333 | https://www.inprocorp.com/products/extension-roller-333",
            ]
        )
        path = Path(f.name)
    try:
        rows = read_material_csv(path)
        assert rows[0]["description"] == "Inpro Extension Roller 333"
        assert rows[0]["manufacturer_url"] == "https://www.inprocorp.com/products/extension-roller-333"
    finally:
        path.unlink(missing_ok=True)


def test_read_production_rate_derives_hours():
    with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(
            ["Manufacturer", "Item", "Production rate", "Production unit", "Unit of measure"]
        )
        w.writerow(["Pawling", "HR-100", "8", "Feet per hour", "LF"])
        path = Path(f.name)
    try:
        rows = read_material_csv(path)
        assert rows[0]["labor_units_per_hour"] == Decimal("8")
        assert rows[0]["labor_rate_unit"] == "LF"
        assert rows[0]["labor_per"] == Decimal("0.1250")
        assert rows[0]["unit_of_measure"] == "LF"
    finally:
        path.unlink(missing_ok=True)


def test_read_sqft_rate_converts_ea_catalog_uom():
    with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(
            ["Manufacturer", "Item", "Production rate", "Production unit", "Labor"]
        )
        w.writerow(["Inpro", "INPRO-405", "30", "SQFT Per Hour", "0.1667"])
        path = Path(f.name)
    try:
        rows = read_material_csv(path)
        assert rows[0]["unit_of_measure"] == "SF"
        assert rows[0]["labor_units_per_hour"] == Decimal("30")
        assert rows[0]["labor_rate_unit"] == "SF"
        assert rows[0]["labor_per"] == Decimal("0.0333")
    finally:
        path.unlink(missing_ok=True)


def test_read_size_columns():
    with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Manufacturer", "Item", "Size"])
        w.writerow(["Claridge", "CLAR-LCS-48X96", "4x8"])
        path = Path(f.name)
    try:
        rows = read_material_csv(path)
        assert rows[0]["size_width_in"] == Decimal("48") or str(rows[0]["size_width_in"]) == "48"
        assert rows[0]["size_height_in"] == Decimal("96") or str(rows[0]["size_height_in"]) == "96"
    finally:
        path.unlink(missing_ok=True)
    with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Vendor", "Part Number", "Unit Price", "Description"])
        w.writerow(["Acme", "X-9", "9.99", "Widget"])
        path = Path(f.name)
    try:
        rows = read_material_csv(path)
        assert rows[0]["manufacturer"] == "Acme"
        assert rows[0]["item"] == "X-9"
    finally:
        path.unlink(missing_ok=True)


def test_read_width_depth_height_fractions():
    with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "manufacturer",
                "item",
                "category",
                "csi_spec_section",
                "description",
                "width",
                "depth",
                "height",
                "mounting_type",
                "currency",
                "unit_of_measure",
            ]
        )
        w.writerow(
            [
                "Penco",
                "PENCO-6001V",
                "Locker",
                "10 51 00",
                'Penco Vanguard. Locker. 12"W x 12"D x 13-5/8"H',
                "12",
                "12",
                "13-5/8",
                "Floor",
                "USD",
                "EA",
            ]
        )
        path = Path(f.name)
    try:
        rows = read_material_csv(path)
        assert rows[0]["size_width_in"] == Decimal("12")
        assert rows[0]["size_depth_in"] == Decimal("12")
        assert rows[0]["size_height_in"] == Decimal("13.625")
        assert rows[0]["csi_spec_section"] == "105113"
        assert rows[0]["mounting_type"] == "Floor"
    finally:
        path.unlink(missing_ok=True)


def test_sku_key_strips_penco_prefix():
    assert sku_key("PENCO-6001V") == "6001V"
    assert sku_key("6001V") == "6001V"


def test_sku_key_strips_cs_prefix():
    assert sku_key("CS-BG-10") == "BG-10"
    assert sku_key("bg-10") == "BG-10"
    assert sku_key("CS_SCR_48") == "SCR-48"
    assert sku_key("  cs-hrb-4c  ") == "HRB-4C"


def test_sku_key_strips_inpro_prefix():
    assert sku_key("INPRO-2500") == "2500"
    assert sku_key("2500") == "2500"
    assert sku_key("IPC-1600") == "1600"


def test_cs_manufacturer_aliases():
    assert is_target_manufacturer("CS", "Construction Specialties")
    assert is_target_manufacturer("C/S", "Construction Specialties")
    assert is_target_manufacturer("Construction Specialties", "Construction Specialties")
    assert not is_target_manufacturer("Bobrick", "Construction Specialties")


def test_inpro_manufacturer_aliases():
    assert is_target_manufacturer("Inpro Corporation", "Inpro")
    assert is_target_manufacturer("IPC", "Inpro")
    assert is_target_manufacturer("Inpro", "Inpro")
    assert not is_target_manufacturer("Construction Specialties", "Inpro")


def test_plan_copies_labor_from_unique_sku_match():
    old = [
        CatalogOldRow(id="old-bg", manufacturer="CS", item="BG-10", labor_per=1.5),
        CatalogOldRow(id="gone", manufacturer="Construction Specialties", item="OLD-GONE", labor_per=9),
        CatalogOldRow(id="bob", manufacturer="Bobrick", item="B-123", labor_per=0.25),
    ]
    payloads = [
        {
            "manufacturer": "Construction Specialties",
            "item": "CS-BG-10",
            "category": "Bumper Guard",
            "description": "BG-10",
            "labor_per": None,
            "cost": None,
        },
        {
            "manufacturer": "Construction Specialties",
            "item": "CS-SCR-48",
            "category": "Crash Rail",
            "description": "new",
            "labor_per": None,
            "cost": None,
        },
    ]
    plan = plan_manufacturer_replace(old, payloads, "Construction Specialties")
    assert plan.updated_count == 1
    assert plan.updates[0][0] == "old-bg"
    assert plan.updates[0][1]["item"] == "CS-BG-10"
    assert plan.updates[0][1]["labor_per"] == 1.5
    assert plan.labor_copied == 1
    assert plan.inserted_count == 1
    assert plan.inserts[0]["item"] == "CS-SCR-48"
    assert "gone" in plan.delete_ids
    assert "bob" not in plan.delete_ids


def test_plan_keeps_csv_labor_when_present():
    old = [CatalogOldRow(id="1", manufacturer="CS", item="BG-10", labor_per=1.5)]
    payloads = [
        {
            "manufacturer": "Construction Specialties",
            "item": "CS-BG-10",
            "labor_per": 0.4,
        }
    ]
    plan = plan_manufacturer_replace(old, payloads, "Construction Specialties")
    assert plan.updates[0][1]["labor_per"] == 0.4
    assert plan.labor_copied == 0


def test_plan_ambiguous_sku_skips_labor_copy():
    old = [
        CatalogOldRow(id="a", manufacturer="CS", item="BG-10", labor_per=1.0),
        CatalogOldRow(id="b", manufacturer="C/S", item="BG-10", labor_per=2.0),
    ]
    payloads = [
        {
            "manufacturer": "Construction Specialties",
            "item": "CS-BG-10",
            "labor_per": None,
        }
    ]
    plan = plan_manufacturer_replace(old, payloads, "Construction Specialties")
    assert plan.ambiguous_keys == ["BG-10"]
    assert plan.labor_copied == 0
    assert plan.inserted_count == 1
    assert plan.updates == []
    assert set(plan.delete_ids) == {"a", "b"}


def test_cs_seed_csv_reads():
    from scripts.db_csv_paths import repo_catalog_dir

    path = repo_catalog_dir() / "construction_specialties.csv"
    rows = read_material_csv(path)
    assert len(rows) == 420
    assert {r["manufacturer"] for r in rows} == {"Construction Specialties"}
    assert all(r["labor_per"] is None for r in rows)
    assert all(r["cost"] is None for r in rows)
    assert {r["csi_spec_section"] for r in rows} == {"102600"}
    assert sum(1 for r in rows if str(r.get("manufacturer_url") or "").startswith("http")) > 400


def test_cs_csv_is_a_repo_seed():
    from scripts.db_csv_paths import repo_catalog_seed_csvs

    names = {p.name for p in repo_catalog_seed_csvs()}
    assert "construction_specialties.csv" in names
    assert "construction_specialties_cubicle_curtain.csv" in names
    assert "inpro_wall_protection.csv" in names
    assert "penco_lockers.csv" in names
    assert "hollman_lockers.csv" in names
    assert "columbia_lockers.csv" in names
    assert "asi_lockers.csv" in names


def test_cs_curtain_seed_csv_reads():
    from scripts.db_csv_paths import repo_catalog_dir

    path = repo_catalog_dir() / "construction_specialties_cubicle_curtain.csv"
    rows = read_material_csv(path)
    assert len(rows) == 34
    assert {r["manufacturer"] for r in rows} == {"Construction Specialties"}
    assert {r["csi_spec_section"] for r in rows} == {"102123"}
    assert any(r["item"] == "CS-6062" for r in rows)
    assert any(r["item"] == "CS-traditional-curtains" for r in rows)
    assert all(str(r.get("manufacturer_url") or "").startswith("http") for r in rows)


def test_inpro_seed_csv_reads():
    from scripts.db_csv_paths import repo_catalog_dir

    path = repo_catalog_dir() / "inpro_wall_protection.csv"
    rows = read_material_csv(path)
    assert len(rows) == 1042
    assert {r["manufacturer"] for r in rows} == {"Inpro"}
    assert all(r["labor_per"] is None for r in rows)
    assert all(r["cost"] is None for r in rows)
    assert {r["csi_spec_section"] for r in rows} == {"102600", "081400"}
    assert str(rows[0].get("manufacturer_url") or "").startswith("http")


def test_penco_seed_csv_reads():
    from scripts.db_csv_paths import repo_catalog_dir

    path = repo_catalog_dir() / "penco_lockers.csv"
    rows = read_material_csv(path)
    assert len(rows) >= 2800
    assert {r["manufacturer"] for r in rows} == {"Penco"}
    assert {r["csi_spec_section"] for r in rows} == {"105113"}
    sample = next(r for r in rows if r["item"] == "PENCO-6001V")
    assert sample["size_width_in"] == Decimal("12")
    assert sample["size_depth_in"] == Decimal("12")
    assert sample["size_height_in"] == Decimal("13.625")
    assert any(r.get("size_depth_in") is not None for r in rows)


def test_hollman_seed_csv_reads():
    from scripts.db_csv_paths import repo_catalog_dir

    path = repo_catalog_dir() / "hollman_lockers.csv"
    rows = read_material_csv(path)
    assert len(rows) >= 500
    assert {r["manufacturer"] for r in rows} == {"Hollman"}
    sample = next(r for r in rows if r["item"] == "HOLLMAN-A1-LAM-12x15x60")
    assert sample["size_width_in"] == Decimal("12")
    assert sample["size_depth_in"] == Decimal("15")
    assert sample["size_height_in"] == Decimal("60")
    assert sample["csi_spec_section"] == "105133"
    assert sample["mounting_type"] == "Floor"


def test_sku_key_strips_hollman_prefix():
    assert sku_key("HOLLMAN-A1-LAM-12x15x60") == "A1-LAM-12X15X60"
    assert sku_key("A1-LAM-12x15x60") == "A1-LAM-12X15X60"


def test_columbia_seed_csv_reads():
    from scripts.db_csv_paths import repo_catalog_dir

    path = repo_catalog_dir() / "columbia_lockers.csv"
    rows = read_material_csv(path)
    assert len(rows) >= 1000
    assert {r["manufacturer"] for r in rows} == {"Columbia"}
    sample = next(r for r in rows if r["item"] == "COLUMBIA-1TIER-PHEN-12x12x36")
    assert sample["size_width_in"] == Decimal("12")
    assert sample["size_depth_in"] == Decimal("12")
    assert sample["size_height_in"] == Decimal("36")
    assert sample["csi_spec_section"] == "105129"
    assert sample["mounting_type"] == "Floor"


def test_sku_key_strips_columbia_prefix():
    assert sku_key("COLUMBIA-1TIER-PHEN-12x12x36") == "1TIER-PHEN-12X12X36"
    assert sku_key("1TIER-PHEN-12x12x36") == "1TIER-PHEN-12X12X36"


def test_asi_seed_csv_reads():
    from scripts.db_csv_paths import repo_catalog_dir

    path = repo_catalog_dir() / "asi_lockers.csv"
    rows = read_material_csv(path)
    assert len(rows) == 68
    assert {r["manufacturer"] for r in rows} == {"ASI"}
    by_csi = {r["csi_spec_section"] for r in rows}
    assert by_csi == {"105100", "105113", "105126", "105129"}
    assert next(r for r in rows if r["item"] == "ASI-COMP-METAL")["csi_spec_section"] == "105113"
    assert next(r for r in rows if r["item"] == "ASI-PLASTIC-TRAD")["csi_spec_section"] == "105126"
    assert next(r for r in rows if r["item"] == "ASI-PHEN-TRAD")["csi_spec_section"] == "105129"
    assert next(r for r in rows if r["item"] == "ASI-CONFIG-1TIER")["csi_spec_section"] == "105100"
    assert next(r for r in rows if r["item"] == "ASI-SIZE-12x12x60")["csi_spec_section"] == "105100"


def test_plan_copies_inpro_labor_from_unique_sku():
    old = [
        CatalogOldRow(id="old-2500", manufacturer="Inpro Corporation", item="2500", labor_per=0.75),
        CatalogOldRow(id="gone", manufacturer="Inpro", item="OLD-GONE", labor_per=9),
        CatalogOldRow(id="cs", manufacturer="Construction Specialties", item="CS-BG-10", labor_per=1.5),
    ]
    payloads = [
        {
            "manufacturer": "Inpro",
            "item": "INPRO-2500",
            "category": "Chair Rail",
            "labor_per": None,
        },
        {
            "manufacturer": "Inpro",
            "item": "INPRO-333",
            "category": "Accessory",
            "labor_per": None,
        },
    ]
    plan = plan_manufacturer_replace(old, payloads, "Inpro")
    assert plan.updated_count == 1
    assert plan.updates[0][0] == "old-2500"
    assert plan.updates[0][1]["item"] == "INPRO-2500"
    assert plan.updates[0][1]["labor_per"] == 0.75
    assert plan.labor_copied == 1
    assert plan.inserted_count == 1
    assert "gone" in plan.delete_ids
    assert "cs" not in plan.delete_ids


def test_plan_copies_penco_labor_from_unprefixed_sku():
    old = [CatalogOldRow(id="old-6001", manufacturer="Penco", item="6001V", labor_per=1)]
    payloads = [
        {
            "manufacturer": "Penco",
            "item": "PENCO-6001V",
            "category": "Locker",
            "labor_per": None,
        }
    ]
    plan = plan_manufacturer_replace(old, payloads, "Penco")
    assert plan.updated_count == 1
    assert plan.updates[0][0] == "old-6001"
    assert plan.updates[0][1]["item"] == "PENCO-6001V"
    assert plan.updates[0][1]["labor_per"] == 1
    assert plan.labor_copied == 1
