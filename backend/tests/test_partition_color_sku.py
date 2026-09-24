"""Finish colors are not catalog styles for toilet partitions."""
from __future__ import annotations

from scripts.material_csv_row import drop_partition_color_skus, is_partition_color_sku


def test_bobrick_and_asi_color_skus_are_not_styles():
    assert is_partition_color_sku(
        item="BOB-DL-0077-FH",
        category="Toilet Partitions",
        description="Bobrick DuraLineSeries CGL - Charcoal 0077-FH",
    )
    assert is_partition_color_sku(
        item="BOB-DS-1500-60",
        category="Toilet Partitions",
        description="Bobrick DesignerSeries HPL - Grey 1500-60",
    )
    assert is_partition_color_sku(
        item="BOB-SC-SCO46",
        category="Toilet Partitions",
        description="Bobrick SierraSeries SCRC - Desert Beige SCO46",
    )
    assert is_partition_color_sku(
        item="ASI-HDPE-9200",
        category="Toilet Partitions",
        description="ASI Solid Plastic HDPE - Gray 9200",
    )
    assert is_partition_color_sku(
        item="ASI-PC-2000",
        category="Toilet Partitions",
        description="ASI Powder Coated Steel - White 2000",
    )


def test_style_and_accessory_rows_stay():
    for item, description in (
        ("BOB-DESIGNER-1040", "Bobrick DesignerSeries HPL Toilet Partition"),
        ("BOB-DURALINE-1080", "Bobrick DuraLineSeries CGL Toilet Partition (Class B)"),
        ("BOB-SIERRA-1090", "Bobrick SierraSeries SCRC Toilet Partition"),
        ("BOB-PRIVADA", "Bobrick PRIVADA Cubicles"),
        ("BOB-GAPFREE", "Bobrick Gap-Free Privacy Option"),
        ("ASI-HDPE", "ASI Solid Plastic HDPE Toilet Partition"),
        ("ASI-PC-STEEL", "ASI Powder Coated Steel Toilet Partition"),
        ("ASI-PHEN-CT", "ASI Color-Thru Phenolic Toilet Partition"),
        ("ASI-US-HDPE", "ASI Urinal Screen - Solid Plastic HDPE"),
        ("BOB-US-DURALINE", "Bobrick Urinal Screen - DuraLineSeries CGL"),
        ("B-6806", "Grab Bar"),
    ):
        category = "Toilet Accessories" if item == "B-6806" else "Toilet Partitions"
        assert not is_partition_color_sku(
            item=item, category=category, description=description
        ), item


def test_drop_partition_color_skus_keeps_styles():
    kept = drop_partition_color_skus(
        [
            {
                "item": "BOB-DL-410-SEI",
                "category": "Toilet Partitions",
                "description": "Bobrick DuraLineSeries CGL - Ice White 410-SEI",
            },
            {
                "item": "BOB-DESIGNER-1040",
                "category": "Toilet Partitions",
                "description": "Bobrick DesignerSeries HPL Toilet Partition",
            },
        ]
    )
    assert [row["item"] for row in kept] == ["BOB-DESIGNER-1040"]
