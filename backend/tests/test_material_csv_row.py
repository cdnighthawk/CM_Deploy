"""Unit tests for material CSV normalization (no database)."""
from __future__ import annotations

import csv
import tempfile
from pathlib import Path

from scripts.material_csv_row import read_material_csv


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


def test_read_vendor_alias_headers():
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
