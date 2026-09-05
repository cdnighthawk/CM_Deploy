"""SSN / ABA routing validation for the public hire wizard."""
from __future__ import annotations

import re

from .hire_crypto import digits_only

_SSN_RE = re.compile(r"^\d{3}-?\d{2}-?\d{4}$")


def normalize_ssn(value: str | None) -> str:
    digits = digits_only(value)
    if len(digits) != 9:
        raise ValueError("SSN must be 9 digits")
    area, group, serial = digits[:3], digits[3:5], digits[5:]
    if area == "000" or area == "666" or area.startswith("9"):
        raise ValueError("SSN area number is not valid")
    if group == "00":
        raise ValueError("SSN group number is not valid")
    if serial == "0000":
        raise ValueError("SSN serial number is not valid")
    return f"{area}-{group}-{serial}"


def ssn_looks_valid(value: str | None) -> bool:
    try:
        normalize_ssn(value)
        return True
    except ValueError:
        return False


def aba_routing_valid(value: str | None) -> bool:
    digits = digits_only(value)
    if len(digits) != 9 or not digits.isdigit():
        return False
    d = [int(c) for c in digits]
    checksum = (3 * (d[0] + d[3] + d[6]) + 7 * (d[1] + d[4] + d[7]) + (d[2] + d[5] + d[8])) % 10
    return checksum == 0


def normalize_routing(value: str | None) -> str:
    digits = digits_only(value)
    if not aba_routing_valid(digits):
        raise ValueError("routing number failed checksum")
    return digits
