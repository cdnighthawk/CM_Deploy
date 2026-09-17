"""Visual-display category recode without touching CSI."""
from __future__ import annotations

from types import SimpleNamespace

from app.material_category import (
    GLASSBOARD,
    MARKERBOARD_ACCESSORY,
    PORCELAIN_MARKERBOARD,
    TACKBOARD,
    planned_category_update,
    recode_category,
)


def test_porcelain_and_glass_and_tack():
    assert (
        recode_category(
            "Markerboards",
            description='ASI Series 9100 Porcelain Markerboard 4x8 (48"x96")',
            item="ASI-9100-408",
            csi_spec_section="101100",
        )
        == PORCELAIN_MARKERBOARD
    )
    assert (
        recode_category(
            "Markerboards",
            description="Claridge Custom Print / Logo Glass Markerboard",
            item="CLAR-GLASS-CUSTOM",
            csi_spec_section="10 11 00",
        )
        == GLASSBOARD
    )
    assert (
        recode_category(
            "Tackboards",
            description="ASI Natural Cork Tackboard",
            item="ASI-TACK-CORK",
            csi_spec_section="101100",
        )
        == TACKBOARD
    )
    assert (
        recode_category(
            "Markerboard Accessories",
            description="ASI Magnetic Marker Tray 12\"",
            item="ASI-MAG-TRAY-12",
            csi_spec_section="101100",
        )
        == MARKERBOARD_ACCESSORY
    )


def test_does_not_change_csi_and_skips_unrelated():
    assert recode_category("Corner Guard", description="CS 8PH", csi_spec_section="102600") == "Corner Guard"
    assert recode_category("Handrail/Crash Rail", description="Acrovyn Handrail HRB", item="CS-HRB") == "Handrail"


def test_planned_update_only_when_changed():
    row = SimpleNamespace(
        category="Markerboards",
        description="Claridge LCS Deluxe Porcelain Markerboard 4x8",
        item="CLAR-LCS-DELUXE-48X96",
        csi_spec_section="101100",
    )
    assert planned_category_update(row) == PORCELAIN_MARKERBOARD
    row.category = PORCELAIN_MARKERBOARD
    assert planned_category_update(row) is None
