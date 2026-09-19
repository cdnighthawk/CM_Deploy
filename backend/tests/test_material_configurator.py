"""Larsen cabinet option schema: size/mount SKU plus selectable extras."""
from __future__ import annotations

from decimal import Decimal

import pytest

from app.material_configurator import (
    LARSEN_CABINET_KEY,
    public_schema,
    resolve_configuration,
    schema_for,
)


def test_larsen_schema_is_registered():
    schema = public_schema(LARSEN_CABINET_KEY)
    assert schema is not None
    ids = [g["id"] for g in schema["groups"]]
    assert ids == ["series", "material", "door", "handle", "extras"]
    assert schema_for("missing") is None


def test_default_larsen_configuration_uses_base_cost():
    resolved = resolve_configuration(
        manufacturer="Larsen",
        item="LARS-2409-R",
        mounting_type="Recessed",
        base_cost=Decimal("184"),
        configurator_key=LARSEN_CABINET_KEY,
        selections=None,
    )
    assert resolved.unit_cost == Decimal("184")
    assert "Architectural" in resolved.description
    assert "Steel" in resolved.description
    assert "Full glazed" in resolved.description
    assert resolved.snapshot["selections"]["material"] == "steel"
    assert resolved.snapshot["selections"]["extras"] == []


def test_larsen_options_add_material_door_and_handle():
    resolved = resolve_configuration(
        manufacturer="Larsen",
        item="LARS-2712-SR",
        mounting_type="Semi-Recessed",
        base_cost=Decimal("281"),
        configurator_key=LARSEN_CABINET_KEY,
        selections={
            "series": "gemini",
            "material": "stainless",
            "door": "solid",
            "handle": "recessed",
            "extras": ["lettering", "flame_shield"],
        },
    )
    assert resolved.unit_cost == Decimal("449")  # 281+35+109-11+25+10
    assert "Gemini" in resolved.description
    assert "Stainless" in resolved.description
    assert "Solid door" in resolved.description
    assert "Recessed handle" in resolved.description
    assert "Die-cut lettering" in resolved.description
    assert "Flame-Shield" in resolved.description


def test_unknown_option_is_rejected():
    with pytest.raises(ValueError, match="unknown Material"):
        resolve_configuration(
            manufacturer="Larsen",
            item="LARS-2409-R",
            mounting_type="Recessed",
            base_cost=Decimal("184"),
            configurator_key=LARSEN_CABINET_KEY,
            selections={"material": "titanium"},
        )
