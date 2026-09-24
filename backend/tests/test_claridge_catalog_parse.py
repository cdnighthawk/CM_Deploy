"""Offline Claridge catalog parse rules (no network)."""
from __future__ import annotations

from scripts.claridge_catalog import (
    build_catalog_rows,
    classify_product,
    dedupe_catalog_rows,
    extract_index_tiles,
    extract_product_page,
    split_published_codes,
)


def test_split_published_codes_rejects_templates_and_notes():
    assert split_published_codes("S14X8LCS") == ["S14X8LCS"]
    assert split_published_codes("GB2X3MGMI, GB2X3MGM, GB2X3MGM-TG") == [
        "GB2X3MGMI",
        "GB2X3MGM",
        "GB2X3MGM-TG",
    ]
    assert split_published_codes('GBXxXMGMI') == []
    assert split_published_codes("Cork Tackboards = Hardboard Backer") == []
    assert split_published_codes("Add to the product number, -2, -3, or -4") == []
    assert split_published_codes("LCS") == []


def test_classify_product_uses_published_names():
    assert classify_product("Series 1", "series-1", "LCS Markerboard") == ("Markerboard", "101116")
    assert classify_product("Series 1", "series-1", "Claridge Cork Tackboard") == ("Tackboard", "101123")
    assert classify_product("370 Series Recessed Display Case", "370-series-recessed-display-case")[1] == "101200"
    assert classify_product("Adhesive Backed Marker Tray", "adhesive-backed-marker-tray")[0] == "Markerboard Accessory"


def test_extract_index_tiles_and_spec_table():
    index_html = """
    <div class="col-sm-12 col-lg-4 product-tile-container product-type-71">
      <a href="https://claridgeproducts.com/product/series-1/">
        <div class="product-name">Series 1</div>
        <div class="product-short-description">1-1/2" trim boards</div>
        <img src="https://claridgeproducts.com/wp-content/uploads/2021/07/Series-1-Hero.jpg" alt="Series 1">
      </a>
    </div>
    """
    tiles = extract_index_tiles(index_html, "https://claridgeproducts.com/products/all-products/")
    assert len(tiles) == 1
    assert tiles[0]["url"] == "https://claridgeproducts.com/product/series-1/"
    assert tiles[0]["name"] == "Series 1"

    product_html = """
    <h1>Series 1</h1>
    <meta name="description" content="Factory-framed Claridge boards.">
    <a href="https://claridgeproducts.com/wp-content/uploads/2023/09/Series-1_Tech-Data.pdf">Tech Data</a>
    <div class="product-specs-option col-12">LCS Markerboard</div>
    <div class="product-specs-code col-4">S14X8LCS</div>
    <div class="product-specs-size col-4">48" x 96"</div>
    <div class="product-specs-weight col-4">80 lbs</div>
    <div class="product-specs-option col-12">Claridge Cork Tackboard</div>
    <div class="product-specs-code col-4">S14X8COR</div>
    <div class="product-specs-size col-4">48" x 96"</div>
    <div class="product-specs-weight col-4">40 lbs</div>
    <div class="product-specs-option col-12">Cork Tackboards = Hardboard Backer. Fabric available upon request</div>
    """
    product = extract_product_page(product_html, "https://claridgeproducts.com/product/series-1/")
    assert product["published_skus"] == ["S14X8LCS", "S14X8COR"]
    assert product["documents"][0]["url"].endswith("Series-1_Tech-Data.pdf")

    rows, skipped = build_catalog_rows(product, tiles[0])
    items = [r["item"] for r in rows]
    assert items == ["Series 1", "S14X8LCS", "S14X8COR"]
    assert rows[1]["category"] == "Markerboard"
    assert rows[1]["csi_spec_section"] == "101116"
    assert rows[2]["category"] == "Tackboard"
    assert "claridgeproducts.com/product/series-1/" in rows[0]["url"]
    assert skipped == []
    assert product["option_labels"] == ["LCS Markerboard", "Claridge Cork Tackboard", "Cork Tackboards = Hardboard Backer. Fabric available upon request"]

    catalog, dupes = dedupe_catalog_rows(rows + [rows[1]])
    assert len(catalog) == 3
    assert dupes[0]["sku"] == "S14X8LCS"


def test_family_only_and_track_suffix_are_ambiguous_not_invented():
    product = {
        "url": "https://claridgeproducts.com/product/horizontal-sliding-system/",
        "title": "Horizontal Sliding System",
        "description": "Custom-built sliding units.",
        "documents": [],
        "images": [],
        "spec_rows": [{"sku": "HS46", "option_group": "Product Codes", "size": "48\" x 72\"", "weight": ""}],
        "option_labels": [
            "Horizontal Sliding System Product Codes",
            "Add to the product number, -2, -3, or -4 for the number of tracks.",
        ],
        "feature_bullets": [],
    }
    rows, skipped = build_catalog_rows(product)
    assert [r["item"] for r in rows] == ["Horizontal Sliding System", "HS46"]
    assert any("track-count" in s["reason"] for s in skipped)
    assert not any(r["item"].endswith("-2") for r in rows)

    custom = {
        "url": "https://claridgeproducts.com/product/custom-print-whiteboards/",
        "title": "Custom Print Glass Markerboard",
        "description": "Upload your own art.",
        "documents": [],
        "images": [],
        "spec_rows": [],
        "option_labels": [],
        "feature_bullets": [],
    }
    rows, skipped = build_catalog_rows(custom)
    assert [r["item"] for r in rows] == ["Custom Print Glass Markerboard"]
    assert any("no published Product Code" in s["reason"] for s in skipped)
