"""Normalize material_pricing.category into stable product-type labels."""
from __future__ import annotations

from typing import Any

from .csi_spec import digits_from_csi

VISUAL_DISPLAY_DIGITS = "101100"

PORCELAIN_MARKERBOARD = "Porcelain Markerboard"
GLASSBOARD = "Glassboard"
TACKBOARD = "Tackboard"
BULLETIN_BOARD = "Bulletin Board"
DISPLAY_CASE = "Display Case"
MARKERBOARD_ACCESSORY = "Markerboard Accessory"

_PLURAL_MAP = {
    "tackboards": TACKBOARD,
    "bulletin boards": BULLETIN_BOARD,
    "display cases": DISPLAY_CASE,
    "markerboard accessories": MARKERBOARD_ACCESSORY,
}


def _blob(*parts: str | None) -> str:
    return " ".join(p for p in parts if (p or "").strip()).lower()


def _is_visual_display(csi_spec_section: str | None) -> bool:
    return digits_from_csi(csi_spec_section) == VISUAL_DISPLAY_DIGITS


def recode_category(
    category: str | None,
    *,
    description: str | None = None,
    item: str | None = None,
    csi_spec_section: str | None = None,
) -> str | None:
    """Return a cleaned category, or the original (stripped) value if unchanged."""
    current = (category or "").strip()
    blob = _blob(current, item, description)

    if current.lower() == "handrail/crash rail":
        product = _blob(item, description)
        has_hr = "handrail" in product
        has_cr = "crash" in product
        if has_hr and not has_cr:
            return "Handrail"
        if has_cr and not has_hr:
            return "Crash Rail"

    mapped = _PLURAL_MAP.get(current.lower())
    if mapped:
        current = mapped

    if not _is_visual_display(csi_spec_section):
        return current or None

    if (
        current == MARKERBOARD_ACCESSORY
        or "accessory" in (category or "").lower()
        or "marker tray" in blob
        or "map rail" in blob
        or "rare earth" in blob
        or "dry-erase marker" in blob
        or "dry erase marker" in blob
    ):
        return MARKERBOARD_ACCESSORY
    if current == DISPLAY_CASE or "trophy" in blob or "display case" in blob:
        return DISPLAY_CASE
    if current == BULLETIN_BOARD or "bulletin" in blob:
        return BULLETIN_BOARD
    if (
        current == TACKBOARD
        or "tackboard" in blob
        or "tack board" in blob
        or " cork" in f" {blob}"
        or "fabric tac" in blob
        or "vinyl tac" in blob
        or "forbo" in blob
    ):
        return TACKBOARD
    if current == GLASSBOARD or re_search_glass(blob):
        return GLASSBOARD
    if (
        current == PORCELAIN_MARKERBOARD
        or "porcelain" in blob
        or " lcs" in f" {blob}"
        or blob.startswith("lcs")
        or "markerboard" in blob
        or "whiteboard" in blob
        or current.lower() in {"markerboards", "markerboard"}
    ):
        if re_search_glass(blob):
            return GLASSBOARD
        return PORCELAIN_MARKERBOARD
    return current or None


def re_search_glass(blob: str) -> bool:
    return (
        "glassboard" in blob
        or "glass board" in blob
        or "glass marker" in blob
        or "logo glass" in blob
        or "custom print / logo glass" in blob
        or "marker wall-glass" in blob
        or "clar-glass" in blob
        or "clar-marker-wall-glass" in blob
    )


def planned_category_update(row: Any) -> str | None:
    """New category if it differs from the row, else None."""
    new = recode_category(
        getattr(row, "category", None),
        description=getattr(row, "description", None),
        item=getattr(row, "item", None),
        csi_spec_section=getattr(row, "csi_spec_section", None),
    )
    old = (getattr(row, "category", None) or "").strip() or None
    if new != old:
        return new
    return None
