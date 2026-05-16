"""CSI MasterFormat spec section normalization (e.g. 08 71 00 door hardware)."""
from __future__ import annotations

import re

_DOOR_HARDWARE_CANONICAL = "087100"


def normalize_csi_spec_section(raw: str | None) -> str | None:
    """Normalize user/import input to 6-digit CSI section or None."""
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    digits = re.sub(r"\D", "", s)
    if len(digits) == 6:
        return digits
    if len(digits) == 8 and digits.startswith("08"):
        return digits[:6]
    lowered = s.lower().replace("_", " ")
    if "087100" in digits or "0871" in digits:
        return _DOOR_HARDWARE_CANONICAL
    if re.search(r"08\s*71\s*00", lowered) or "door hardware" in lowered:
        return _DOOR_HARDWARE_CANONICAL
    return None


def is_door_hardware_section(section: str | None) -> bool:
    return normalize_csi_spec_section(section) == _DOOR_HARDWARE_CANONICAL
