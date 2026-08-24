"""CSI MasterFormat spec section normalization (e.g. 08 71 00 door hardware)."""
from __future__ import annotations

import re

_DOOR_HARDWARE_CANONICAL = "087100"
# 08 71 00 Title — or 087100 Title — used when reading spec-book PDFs.
CSI_LINE_RE = re.compile(
    r"(?m)(?<![\d.])(?:(\d{2})\s+(\d{2})\s+(\d{2})|(\d{6}))(?:\s+[—\-:]\s*|\s+)([A-Za-z][A-Za-z0-9 /,&.'()\-]{1,90})"
)
CSI_CODE_RE = re.compile(r"(?<![\d.])(?:(\d{2})\s+(\d{2})\s+(\d{2})|(\d{6}))(?![\d.])")


def digits_from_csi(raw: str | None) -> str | None:
    """Return the 6-digit CSI number, or None if the value is not a section code."""
    if raw is None:
        return None
    digits = re.sub(r"\D", "", str(raw).strip())
    if len(digits) == 6:
        return digits
    return None


def format_csi_display(raw: str | None) -> str | None:
    """Format a section as ``08 71 00``. Returns None if it is not 6 digits."""
    digits = digits_from_csi(raw) or normalize_csi_spec_section(raw)
    if not digits or len(digits) != 6:
        return None
    return f"{digits[0:2]} {digits[2:4]} {digits[4:6]}"


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
