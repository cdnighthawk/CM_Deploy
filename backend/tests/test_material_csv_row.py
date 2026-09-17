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
        assert "activarcpg.com" in (rows[0]["description"] or "")
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


def test_cs_csv_is_a_repo_seed():
    from scripts.db_csv_paths import repo_catalog_seed_csvs

    names = {p.name for p in repo_catalog_seed_csvs()}
    assert "construction_specialties.csv" in names
    assert "construction_specialties_cubicle_curtain.csv" in names
    assert "inpro_wall_protection.csv" in names


def test_cs_curtain_seed_csv_reads():
    from scripts.db_csv_paths import repo_catalog_dir

    path = repo_catalog_dir() / "construction_specialties_cubicle_curtain.csv"
    rows = read_material_csv(path)
    assert len(rows) == 34
    assert {r["manufacturer"] for r in rows} == {"Construction Specialties"}
    assert {r["csi_spec_section"] for r in rows} == {"102123"}
    assert any(r["item"] == "CS-6062" for r in rows)
    assert any(r["item"] == "CS-traditional-curtains" for r in rows)


def test_inpro_seed_csv_reads():
    from scripts.db_csv_paths import repo_catalog_dir

    path = repo_catalog_dir() / "inpro_wall_protection.csv"
    rows = read_material_csv(path)
    assert len(rows) == 1042
    assert {r["manufacturer"] for r in rows} == {"Inpro"}
    assert all(r["labor_per"] is None for r in rows)
    assert all(r["cost"] is None for r in rows)
    assert {r["csi_spec_section"] for r in rows} == {"102600", "081400"}


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
