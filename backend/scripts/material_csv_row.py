"""Normalize material pricing CSV rows (Bobrick + updated vendor exports)."""
from __future__ import annotations

import csv
from decimal import Decimal, InvalidOperation
from pathlib import Path

# Canonical field -> accepted header variants (case-insensitive match on stripped names).
_HEADER_ALIASES: dict[str, tuple[str, ...]] = {
    "manufacturer": ("manufacturer", "vendor", "mfg", "brand", "supplier"),
    "item": ("item", "part", "part number", "part #", "part no", "sku", "model", "catalog #", "catalog no"),
    "category": ("category", "type", "product type"),
    "description": ("description", "desc", "product description", "name"),
    "mounting_type": ("mounting type", "mounting", "mount type", "mount"),
    "cost": ("cost", "price", "unit price", "unit cost", "material cost"),
    "labor_per": ("labor per", "labor", "labor cost", "labor $", "install labor"),
    "unit_of_measure": ("unit of measure", "uom", "unit", "units"),
    "currency": ("currency",),
    "csi_spec_section": (
        "csi spec",
        "csi spec section",
        "spec section",
        "spec",
        "masterformat",
        "division",
        "08 71 00",
        "087100",
    ),
}


def _blank_to_none(s: str | None) -> str | None:
    if s is None:
        return None
    stripped = s.strip()
    return None if stripped == "" else stripped


def _parse_decimal(raw: str | None) -> Decimal | None:
    s = (raw or "").strip().replace("$", "").replace(",", "")
    if s == "":
        return None
    try:
        return Decimal(s)
    except InvalidOperation as exc:
        raise ValueError(f"invalid decimal: {raw!r}") from exc


def _normalize_header_map(fieldnames: list[str] | None) -> dict[str, str]:
    """Map canonical keys to actual CSV column names."""
    if not fieldnames:
        raise ValueError("CSV has no header row")
    lower_to_actual: dict[str, str] = {}
    for name in fieldnames:
        key = (name or "").strip().lower()
        if key and key not in lower_to_actual:
            lower_to_actual[key] = name.strip()

    resolved: dict[str, str] = {}
    for canonical, aliases in _HEADER_ALIASES.items():
        for alias in aliases:
            if alias in lower_to_actual:
                resolved[canonical] = lower_to_actual[alias]
                break
    if "manufacturer" not in resolved or "item" not in resolved:
        missing = {"manufacturer", "item"} - set(resolved)
        raise ValueError(
            f"CSV missing required columns {sorted(missing)}; headers were: {fieldnames!r}"
        )
    return resolved


def _get_cell(row: dict[str, str], col_map: dict[str, str], key: str) -> str | None:
    col = col_map.get(key)
    if not col:
        return None
    return row.get(col)


def row_to_payload(row: dict[str, str], col_map: dict[str, str]) -> dict[str, object]:
    manufacturer = _blank_to_none(_get_cell(row, col_map, "manufacturer"))
    item = _blank_to_none(_get_cell(row, col_map, "item"))
    if not manufacturer or not item:
        raise ValueError("Manufacturer and Item are required (got blank values)")

    category = _blank_to_none(_get_cell(row, col_map, "category"))
    description = _blank_to_none(_get_cell(row, col_map, "description"))
    mounting_type = _blank_to_none(_get_cell(row, col_map, "mounting_type"))
    cost = _parse_decimal(_get_cell(row, col_map, "cost"))
    labor_per = _parse_decimal(_get_cell(row, col_map, "labor_per"))
    uom = _blank_to_none(_get_cell(row, col_map, "unit_of_measure")) or "EA"
    currency = (_blank_to_none(_get_cell(row, col_map, "currency")) or "USD").upper()[:3]
    csi_raw = _blank_to_none(_get_cell(row, col_map, "csi_spec_section"))
    csi_spec_section = None
    if csi_raw:
        from app.csi_spec import normalize_csi_spec_section

        csi_spec_section = normalize_csi_spec_section(csi_raw)

    return {
        "manufacturer": manufacturer[:120],
        "item": item[:120],
        "category": category[:120] if category else None,
        "csi_spec_section": csi_spec_section,
        "description": description,
        "mounting_type": mounting_type[:120] if mounting_type else None,
        "cost": cost,
        "labor_per": labor_per,
        "currency": currency,
        "unit_of_measure": uom[:20],
    }


def read_material_csv(csv_path: Path) -> list[dict[str, object]]:
    payloads: list[dict[str, object]] = []
    with csv_path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        col_map = _normalize_header_map(list(reader.fieldnames or []))
        for row in reader:
            if not any((v or "").strip() for v in row.values()):
                continue
            payloads.append(row_to_payload(row, col_map))
    return payloads
