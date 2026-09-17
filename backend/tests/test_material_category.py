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
    assert recode_category("Crash Rail", description="Acrovyn Crash Rail", item="CS-SCR-48") == "Crash Rail"


def test_rigid_sheet_inpro_and_cs_acrovyn():
    from app.material_category import RIGID_SHEET_WALL_PROTECTION

    assert (
        recode_category(
            "Wall Covering",
            description="Inpro Palladium Rigid Sheet 405 .040 4x8",
            item="INPRO-405",
            csi_spec_section="102600",
        )
        == RIGID_SHEET_WALL_PROTECTION
    )
    assert (
        recode_category(
            "Wall Covering",
            description="Inpro Rolled Palladium Rigid Sheet 305 100",
            item="INPRO-100",
            csi_spec_section="10 26 00",
        )
        == RIGID_SHEET_WALL_PROTECTION
    )
    assert (
        recode_category(
            "Wall Covering",
            description='Construction Specialties Acrovyn Wall Covering .040 4x8. Confirmed on CS product page: .040 rigid sheet',
            item="CS-.040-4x8",
            csi_spec_section="102600",
        )
        == RIGID_SHEET_WALL_PROTECTION
    )
    assert (
        recode_category(
            "Wall Covering",
            description="Construction Specialties Acrovyn Wall Covering .040 4x10 solid",
            item="CS-ACROVYN-WC-.040-4x10",
            csi_spec_section="102600",
        )
        == RIGID_SHEET_WALL_PROTECTION
    )
    assert (
        recode_category(
            "Trim",
            description="Aluminum Trim for Acrovyn Wall Covering .040",
            item="CS-ALUMINUM-TRIM-.040",
            csi_spec_section="102600",
        )
        == "Trim"
    )
    assert (
        recode_category(
            "Wall Covering",
            description="Top cap for Palladium rigid sheet",
            item="INPRO-407",
            csi_spec_section="102600",
        )
        == "Wall Covering"
    )


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
