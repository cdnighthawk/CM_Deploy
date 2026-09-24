"""Map locker catalog rows onto the five 10 51 xx spec sections."""
from __future__ import annotations

import re
from typing import Any

from .csi_spec import digits_from_csi

LOCKER_PARENT = "105100"
METAL_LOCKERS = "105113"
PLASTIC_LOCKERS = "105126"
PHENOLIC_LOCKERS = "105129"
WOOD_LAMINATE_LOCKERS = "105133"
WIRE_MESH_LOCKERS = "105143"

SPECIFIC_LOCKER_CSI = frozenset(
    {
        METAL_LOCKERS,
        PLASTIC_LOCKERS,
        PHENOLIC_LOCKERS,
        WOOD_LAMINATE_LOCKERS,
        WIRE_MESH_LOCKERS,
    }
)

_LOCKER_RE = re.compile(r"locker", re.I)
_PHENOLIC_RE = re.compile(r"phenolic", re.I)
_MESH_RE = re.compile(r"wire\s*mesh|\bmesh\b|security cage", re.I)
_WOOD_RE = re.compile(r"laminate|\bhpl\b|\bplam\b|wood locker|wood and laminate", re.I)
_PLASTIC_RE = re.compile(r"\bhdpe\b|plastic", re.I)
_METAL_RE = re.compile(r"\bmetal\b|\bsteel\b|welded", re.I)


def _blob(*parts: str | None) -> str:
    return " ".join(p for p in parts if (p or "").strip())


def is_locker_row(
    *,
    manufacturer: str | None = None,
    item: str | None = None,
    category: str | None = None,
    description: str | None = None,
    csi_spec_section: str | None = None,
) -> bool:
    digits = digits_from_csi(csi_spec_section)
    if digits and digits.startswith("1051"):
        return True
    if (manufacturer or "").strip().lower() == "penco":
        return True
    return bool(_LOCKER_RE.search(_blob(item, category, description)))


def infer_locker_csi(
    *,
    manufacturer: str | None = None,
    item: str | None = None,
    category: str | None = None,
    description: str | None = None,
    csi_spec_section: str | None = None,
) -> str | None:
    """Return a 6-digit locker CSI code, or the current CSI when this is not a locker."""
    current = digits_from_csi(csi_spec_section)
    if not is_locker_row(
        manufacturer=manufacturer,
        item=item,
        category=category,
        description=description,
        csi_spec_section=csi_spec_section,
    ):
        return current

    text = _blob(item, description, category)
    if _PHENOLIC_RE.search(text):
        return PHENOLIC_LOCKERS
    if _MESH_RE.search(text):
        return WIRE_MESH_LOCKERS
    if _WOOD_RE.search(text):
        return WOOD_LAMINATE_LOCKERS
    if _PLASTIC_RE.search(text):
        return PLASTIC_LOCKERS
    if _METAL_RE.search(text):
        return METAL_LOCKERS
    if (manufacturer or "").strip().lower() == "penco":
        return METAL_LOCKERS
    return current or LOCKER_PARENT


def planned_locker_csi_update(row: Any) -> str | None:
    """CSI to write when a catalog row is still on the generic locker parent (or blank)."""
    inferred = infer_locker_csi(
        manufacturer=getattr(row, "manufacturer", None),
        item=getattr(row, "item", None),
        category=getattr(row, "category", None),
        description=getattr(row, "description", None),
        csi_spec_section=getattr(row, "csi_spec_section", None),
    )
    current = digits_from_csi(getattr(row, "csi_spec_section", None))
    if not inferred or inferred == current:
        return None
    return inferred
