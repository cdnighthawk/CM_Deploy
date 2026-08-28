"""CSI / trade completeness templates for submittal QC (v1 seed)."""
from __future__ import annotations

from typing import Any

ALWAYS_ITEMS: list[dict[str, Any]] = [
    {"template_key": "always.project_match", "label": "Project name / number matches", "required": True},
    {"template_key": "always.spec_section", "label": "Spec section correct", "required": True},
    {"template_key": "always.revision", "label": "Revision identified", "required": True},
    {
        "template_key": "always.mfr_model",
        "label": "Manufacturer + exact model / family highlighted on cut sheet",
        "required": True,
    },
    {
        "template_key": "always.artifacts",
        "label": "Required artifacts present for type (product data / shop drawing / sample / cert)",
        "required": True,
    },
    {
        "template_key": "always.drawing_or_na",
        "label": "Linked to at least one drawing or explicitly N/A",
        "required": True,
    },
]

TRADE_ITEMS: dict[str, list[dict[str, Any]]] = {
    "09 29": [
        {"template_key": "gypsum.board_type", "label": "Board type (X, C, abuse, MR)", "required": True},
        {"template_key": "gypsum.thickness", "label": "Thickness", "required": True},
        {"template_key": "gypsum.ul_assembly", "label": "UL / rated assembly design vs drawing wall type", "required": True},
        {
            "template_key": "gypsum.fastener",
            "label": "Fastener / control joint notes if shop drawing",
            "required": False,
        },
    ],
    "09 91": [
        {"template_key": "paint.mpi_system", "label": "MPI system number", "required": True},
        {"template_key": "paint.sheen_color", "label": "Sheen + color vs finish schedule", "required": True},
        {"template_key": "paint.primer", "label": "Primer system vs substrate", "required": True},
        {"template_key": "paint.title24_voc", "label": "Title 24 VOC", "required": True},
        {"template_key": "paint.no_mix", "label": "Manufacturer system not mixed", "required": True},
    ],
    "09 65": [
        {"template_key": "floor.product", "label": "Exact product + wear layer", "required": True},
        {"template_key": "floor.adhesive", "label": "Adhesive system", "required": True},
        {"template_key": "floor.moisture", "label": "Moisture test method + limits", "required": True},
        {"template_key": "floor.transitions", "label": "Transitions / attic stock if specified", "required": False},
    ],
    "09 68": [
        {"template_key": "floor.product", "label": "Exact product + wear layer", "required": True},
        {"template_key": "floor.adhesive", "label": "Adhesive system", "required": True},
        {"template_key": "floor.moisture", "label": "Moisture test method + limits", "required": True},
        {"template_key": "floor.transitions", "label": "Transitions / attic stock if specified", "required": False},
    ],
    "09 51": [
        {"template_key": "ceiling.grid", "label": "Grid type / duty", "required": True},
        {"template_key": "ceiling.nrc_cac", "label": "Tile NRC / CAC", "required": True},
        {"template_key": "ceiling.fire", "label": "Fire-rated assembly", "required": True},
        {"template_key": "ceiling.seismic", "label": "Seismic / hanger notes (CA commercial)", "required": True},
    ],
    "10": [
        {
            "template_key": "div10.family_snapshot",
            "label": "Family + size + color + options vs frozen takeoff snapshot",
            "required": True,
        },
        {
            "template_key": "div10.library",
            "label": "Compare against imported material libraries (ASI, Penco, Inpro, Bobrick, Claridge, JL, Larsen, CS)",
            "required": True,
        },
    ],
}

TRADE_ALIASES = {
    "drywall": "09 29",
    "gypsum": "09 29",
    "paint": "09 91",
    "flooring": "09 65",
    "ceilings": "09 51",
    "ceiling": "09 51",
    "specialties": "10",
}


def _spec_prefixes(spec_section: str | None) -> list[str]:
    raw = (spec_section or "").strip()
    keys: list[str] = []
    if not raw:
        return keys
    compact = raw.replace("  ", " ")
    if compact.startswith("10"):
        keys.append("10")
    for prefix in ("09 29", "09 91", "09 65", "09 68", "09 51"):
        if compact.startswith(prefix):
            keys.append(prefix)
    return keys


def template_items_for(*, spec_section: str | None, trade: str | None) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in ALWAYS_ITEMS:
        items.append(dict(row))
        seen.add(row["template_key"])
    prefixes = _spec_prefixes(spec_section)
    alias = TRADE_ALIASES.get((trade or "").strip().lower())
    if alias and alias not in prefixes:
        prefixes.append(alias)
    for prefix in prefixes:
        for row in TRADE_ITEMS.get(prefix, []):
            if row["template_key"] in seen:
                continue
            items.append(dict(row))
            seen.add(row["template_key"])
    for i, row in enumerate(items):
        row["sort_order"] = i
        row["source"] = "template"
    return items


def list_templates(*, spec_section: str | None = None, trade: str | None = None) -> dict[str, Any]:
    return {
        "entity": "submittal_checklist_templates",
        "items": template_items_for(spec_section=spec_section, trade=trade),
        "spec_section": spec_section,
        "trade": trade,
    }
