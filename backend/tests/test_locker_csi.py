"""Locker CSI mapping onto 10 51 13 / 26 / 29 / 33 / 43."""
from types import SimpleNamespace

from app.locker_csi import infer_locker_csi, planned_locker_csi_update


def test_asi_families_map_to_material_sections():
    assert (
        infer_locker_csi(
            manufacturer="ASI",
            item="ASI-COMP-METAL",
            category="Lockers",
            description="ASI Competitor Metal Locker (Powder Coated Steel)",
            csi_spec_section="10 51 00",
        )
        == "105113"
    )
    assert (
        infer_locker_csi(
            manufacturer="ASI",
            item="ASI-PLASTIC-TRAD",
            category="Lockers",
            description="ASI Plastic Traditional HDPE Locker",
            csi_spec_section="105100",
        )
        == "105126"
    )
    assert (
        infer_locker_csi(
            manufacturer="ASI",
            item="ASI-PHEN-TRAD",
            category="Lockers",
            description="ASI Phenolic Traditional Locker",
            csi_spec_section="105100",
        )
        == "105129"
    )


def test_shared_asi_config_stays_on_parent():
    assert (
        infer_locker_csi(
            manufacturer="ASI",
            item="ASI-CONFIG-1TIER",
            category="Lockers",
            description="ASI Locker Configuration - Single-Tier",
            csi_spec_section="10 51 00",
        )
        == "105100"
    )
    assert (
        infer_locker_csi(
            manufacturer="ASI",
            item="ASI-SIZE-12x12x60",
            category="Lockers",
            description="ASI Locker Size 12x12x60",
            csi_spec_section="10 51 00",
        )
        == "105100"
    )


def test_wood_laminate_and_mesh():
    assert (
        infer_locker_csi(
            item="WOOD-CLUB",
            category="Lockers",
            description="Wood and laminate club locker",
        )
        == "105133"
    )
    assert (
        infer_locker_csi(
            item="MESH-CAGE",
            category="Lockers",
            description="Wire mesh storage locker",
        )
        == "105143"
    )


def test_toilet_partitions_are_not_lockers():
    assert (
        infer_locker_csi(
            manufacturer="ASI",
            item="ASI-PHEN-CT",
            category="Toilet Partitions",
            description="ASI Color-Thru Phenolic Toilet Partition",
            csi_spec_section="10 21 13",
        )
        == "102113"
    )


def test_planned_update_only_when_csi_changes():
    row = SimpleNamespace(
        manufacturer="ASI",
        item="ASI-TRAD-METAL",
        category="Lockers",
        description="ASI Traditional Metal Locker (Powder Coated Steel)",
        csi_spec_section="10 51 00",
    )
    assert planned_locker_csi_update(row) == "105113"
    row.csi_spec_section = "105113"
    assert planned_locker_csi_update(row) is None
