"""Larsen cabinet seed is size + mounting SKUs with a shared configurator."""
from __future__ import annotations

from decimal import Decimal

from scripts.db_csv_paths import repo_catalog_dir, repo_catalog_seed_csvs
from scripts.material_csv_row import is_target_manufacturer, read_material_csv, sku_key

_SEED = repo_catalog_dir() / "larsen_cabinets.csv"
_MOUNTS = {"Recessed", "Semi-Recessed", "Surface", "Trimless"}
_SKUS = {
    "LARS-2409-R",
    "LARS-2409-SR",
    "LARS-2409-SM",
    "LARS-2409-RT",
    "LARS-2712-R",
    "LARS-2712-SR",
    "LARS-2712-SM",
    "LARS-2712-RT",
    "LARS-2720-R",
    "LARS-3612-R",
    "LARS-3612-SM",
}


def test_repo_catalog_includes_larsen_seed():
    assert _SEED.is_file()
    assert _SEED.resolve() in {p.resolve() for p in repo_catalog_seed_csvs()}


def test_larsen_seed_is_size_and_mount_only():
    rows = read_material_csv(_SEED)
    items = [r["item"] for r in rows]
    assert set(items) == _SKUS
    assert len(items) == len(set(items))
    assert {r["manufacturer"] for r in rows} == {"Larsen"}
    assert {r["category"] for r in rows} == {"Fire Extinguisher Cabinet"}
    assert {r["csi_spec_section"] for r in rows} == {"104400"}
    assert {r["configurator_key"] for r in rows} == {"larsen_cabinet"}
    assert {r["mounting_type"] for r in rows} == _MOUNTS
    assert all(r["labor_per"] == Decimal("0.75") for r in rows)
    assert all(str(r.get("manufacturer_url") or "").startswith("http") for r in rows)
    sample = next(r for r in rows if r["item"] == "LARS-2409-R")
    assert sample["cost"] == Decimal("184.00")
    assert sample["size_width_in"] == Decimal("24")
    assert sample["size_height_in"] == Decimal("9.5")
    assert "FG" not in "".join(items)
    assert "LARSENS-" not in "".join(items)


def test_larsen_aliases_and_sku_key():
    assert is_target_manufacturer("Larsens", "Larsen")
    assert is_target_manufacturer("Larsen's Manufacturing", "Larsen")
    assert sku_key("LARS-2409-R") == "2409-R"
    assert sku_key("LARSENS-2409-R") == "2409-R"
