"""Claridge visual-display seed for material_pricing."""
from __future__ import annotations

import json

import pytest

from scripts.claridge_catalog import SOURCE_INDEX, split_published_codes
from scripts.db_csv_paths import repo_catalog_dir, repo_catalog_seed_csvs
from scripts.load_material_pricing import should_truncate_catalog_file
from scripts.material_csv_row import read_material_csv

_SEED = repo_catalog_dir() / "claridge_visual_display.csv"
_SOURCE = repo_catalog_dir() / "claridge_source"

_FAMILIES = {
    "Series 1",
    "Series 2",
    "Series 5",
    "LCS Elite",
    "Arise Whiteboard",
    "Aspire Whiteboard",
    "Claridge Glass Whiteboard",
    "Grain Whiteboard",
    "LCS Deluxe Porcelain Whiteboards",
}
_MARKER_SKUS = {"S14X8LCS", "EE4X6LCS", "EM4X8LCS", "ASP-48", "GR48-MB", "GB4X6MGMI", "LCS2048R"}
_TACK_SKUS = {"S14X8COR", "S54X8TAN"}
_CASE_SKUS = {"1023", "2035"}


def test_repo_catalog_includes_claridge_seed():
    assert _SEED.is_file()
    assert _SEED.resolve() in {p.resolve() for p in repo_catalog_seed_csvs()}
    assert (_SOURCE / "products.json").is_file()
    assert (_SOURCE / "index_tiles.json").is_file()
    assert (_SOURCE / "report.json").is_file()


def test_claridge_seed_parses_to_real_skus():
    rows = read_material_csv(_SEED)
    items = [r["item"] for r in rows]
    assert len(rows) >= 600
    assert len(items) == len(set(items))
    assert _FAMILIES.issubset(set(items))
    assert _MARKER_SKUS.issubset(set(items))
    assert _TACK_SKUS.issubset(set(items))
    assert _CASE_SKUS.issubset(set(items))
    for row in rows:
        assert row["manufacturer"] == "Claridge"
        assert row["unit_of_measure"] == "EA"
        assert row["currency"] == "USD"
        assert row["csi_spec_section"] in {"101100", "101116", "101123", "101200"}
        desc = row["description"] or ""
        assert len(desc) > 40
        mfr_url = row.get("manufacturer_url") or ""
        assert "claridgeproducts.com" in (desc or mfr_url)
        assert "GBXxX" not in (row["item"] or "")
        assert "XxX" not in (row["item"] or "")


def test_claridge_source_matches_seed_and_index():
    report = json.loads((_SOURCE / "report.json").read_text(encoding="utf-8"))
    products = json.loads((_SOURCE / "products.json").read_text(encoding="utf-8"))
    tiles = json.loads((_SOURCE / "index_tiles.json").read_text(encoding="utf-8"))
    rows = read_material_csv(_SEED)

    assert report["source_index"] == SOURCE_INDEX
    assert report["unique_index_tiles"] == 55
    assert report["product_pages_ok"] == 55
    assert report["index_pages_scanned"] >= 1
    assert len(tiles) == 55
    assert len(products) == 55
    assert all(p.get("on_all_products_index") for p in products)
    assert report["counts"]["unique_products_or_families"] == 55
    assert report["counts"]["exact_skus_or_models"] == 596
    assert report["counts"]["catalog_rows_after_dedupe"] == len(rows)
    assert report["counts"]["skipped_or_ambiguous"] == 7

    published = []
    for product in products:
        for sku in product.get("published_skus") or []:
            assert split_published_codes(sku) == [sku]
            published.append(sku)
    assert len(published) == 596
    items = {r["item"] for r in rows}
    assert set(published).issubset(items)


def test_claridge_seed_covers_surfaces_and_traceability():
    rows = read_material_csv(_SEED)
    by_item = {r["item"]: r for r in rows}
    assert by_item["S14X8LCS"]["category"] == "Markerboard"
    assert by_item["S14X8LCS"]["csi_spec_section"] == "101116"
    assert "48" in (by_item["S14X8LCS"]["description"] or "") or "96" in (
        by_item["S14X8LCS"]["description"] or ""
    )
    assert by_item["S14X8COR"]["category"] == "Tackboard"
    assert by_item["S14X8COR"]["csi_spec_section"] == "101123"
    assert by_item["GB4X6MGMI"]["mounting_type"] == "Invisi-Mount"
    assert by_item["GB4X6MGM-TG"]["mounting_type"] == "Through-Glass Standoff"
    assert "Tech-Data" in (by_item["Series 1"]["description"] or "") or "tech-data" in (
        by_item["Series 1"]["description"] or ""
    ).lower()
    assert by_item["1023"]["category"] == "Display Case"
    assert by_item["Custom Print Glass Markerboard"]["category"] == "Markerboard"
    assert "not published as individual SKUs" in (
        by_item["Custom Print Glass Markerboard"]["description"] or ""
    )
    assert "HS46-2" not in by_item
    assert "HS46" in by_item


def test_repo_seeds_never_truncate_by_default():
    assert (
        should_truncate_catalog_file(
            index=0,
            is_repo_seed=True,
            truncate_flag=None,
            all_defaults=True,
            repo_seeds_only=False,
            path_count=3,
        )
        is False
    )
    assert (
        should_truncate_catalog_file(
            index=0,
            is_repo_seed=True,
            truncate_flag=None,
            all_defaults=False,
            repo_seeds_only=True,
            path_count=1,
        )
        is False
    )
    assert (
        should_truncate_catalog_file(
            index=0,
            is_repo_seed=False,
            truncate_flag=None,
            all_defaults=True,
            repo_seeds_only=False,
            path_count=3,
        )
        is True
    )


def test_claridge_seed_upsert_is_idempotent():
    from sqlalchemy import func, select, text

    try:
        from app import create_app
        from app.extensions import db
        from app.models.material_pricing import MaterialPrice
        from scripts.load_material_pricing import _upsert_payloads

        app = create_app()
    except Exception:
        pytest.skip("Flask app / database not available in this environment")

    rows = read_material_csv(_SEED)
    with app.app_context():
        try:
            db.session.execute(text("SELECT 1"))
        except Exception:
            pytest.skip("database not available in this environment")
        _upsert_payloads(db, MaterialPrice, rows)
        first = db.session.scalar(
            select(func.count())
            .select_from(MaterialPrice)
            .where(MaterialPrice.manufacturer == "Claridge")
        )
        _upsert_payloads(db, MaterialPrice, rows)
        second = db.session.scalar(
            select(func.count())
            .select_from(MaterialPrice)
            .where(MaterialPrice.manufacturer == "Claridge")
        )
        assert first == second
        assert first >= len(rows)

    client = app.test_client()
    r = client.get("/api/v1/material-prices?manufacturer=Claridge&limit=500")
    assert r.status_code == 200
    payload = r.get_json()
    assert payload["total"] >= len(rows)
    assert all(x.get("unit_of_measure") == "EA" for x in payload["items"])
    for sku in sorted(_MARKER_SKUS | {"Series 1", "LCS Elite"}):
        lookup = client.get(f"/api/v1/material-prices?manufacturer=Claridge&q={sku}&limit=50")
        assert lookup.status_code == 200
        found = {x["item"] for x in lookup.get_json()["items"]}
        assert sku in found, sku
