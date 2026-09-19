"""Accurate Partitions seed is brands and heights, not scraped WordPress chrome."""
from __future__ import annotations

import csv
from pathlib import Path

CSV = Path(__file__).resolve().parents[1] / "data" / "catalog" / "accurate_partitions.csv"


def test_accurate_partitions_csv_is_brands_and_heights():
    with CSV.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) >= 20
    heights = {float(r["size_height_in"]) for r in rows}
    assert {48, 58, 64, 72, 96, 120} <= heights
    brands = " ".join(r["description"] for r in rows).lower()
    for name in (
        "alpaco classic",
        "alpaco elegance",
        "solid plastic (hdpe)",
        "powder coated",
        "stainless steel",
        "moisture guard",
        "black core phenolic",
        "color-thru phenolic",
        "maximum privacy",
    ):
        assert name in brands, name
    blob = " ".join(r["description"] for r in rows)
    assert "single.php" not in blob
    assert "Specification Generator" not in blob
    assert all(r["manufacturer"] == "Accurate Partitions" for r in rows)
    assert all(r["size_height_in"].strip() for r in rows)
    items = " ".join(r["item"] for r in rows).lower()
    for name in ("alpaco classic", "alpaco elegance", "hdpe", "powder coated", "stainless", "maximum privacy"):
        assert name in items, name
    assert all(any(ch.isdigit() for ch in r["item"]) for r in rows)
