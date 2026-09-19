"""Normalize material pricing CSV rows (Bobrick + updated vendor exports)."""
from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

# Canonical field -> accepted header variants (case-insensitive match on stripped names).
_HEADER_ALIASES: dict[str, tuple[str, ...]] = {
    "manufacturer": ("manufacturer", "vendor", "mfg", "brand", "supplier"),
    "manufacturer_url": (
        "manufacturer_url",
        "manufacturer url",
        "url",
        "source url",
        "source_url",
        "product url",
        "product_url",
        "link",
        "webpage",
        "website",
        "web site",
    ),
    "item": ("item", "part", "part number", "part #", "part no", "sku", "model", "catalog #", "catalog no"),
    "category": ("category", "type", "product type", "family", "product family"),
    "description": ("description", "desc", "product description", "name"),
    "mounting_type": ("mounting_type", "mounting type", "mounting", "mount type", "mount"),
    "cost": ("cost", "price", "unit price", "unit cost", "material cost"),
    "labor_per": ("labor per", "labor", "labor cost", "labor $", "install labor"),
    "labor_units_per_hour": (
        "labor_units_per_hour",
        "labor units per hour",
        "production rate",
        "units per hour",
        "units/hr",
    ),
    "labor_rate_unit": (
        "labor_rate_unit",
        "labor rate unit",
        "production unit",
        "rate unit",
    ),
    "unit_of_measure": ("unit of measure", "uom", "unit", "units"),
    "currency": ("currency",),
    "csi_spec_section": (
        "csi_spec_section",
        "csi spec",
        "csi spec section",
        "spec section",
        "spec",
        "masterformat",
        "division",
        "08 71 00",
        "087100",
    ),
    "size_width_in": ("size_width_in", "width_in", "width", "w"),
    "size_height_in": ("size_height_in", "height_in", "length_in", "height", "length", "h"),
    "size_depth_in": ("size_depth_in", "depth_in", "depth", "d"),
    "size": ("size", "sheet size", "wxh", "w x h"),
}

# Aliases that count as Construction Specialties when replacing that manufacturer.
_CS_MANUFACTURER_ALIASES = frozenset(
    {
        "construction specialties",
        "cs",
        "c/s",
        "c-s",
        "cs group",
        "c-s group",
        "c/s group",
    }
)

_INPRO_MANUFACTURER_ALIASES = frozenset(
    {
        "inpro",
        "inpro corporation",
        "inpro corp",
        "ipc",
    }
)

_SKU_PREFIXES = ("COLUMBIA-", "HOLLMAN-", "PENCO-", "INPRO-", "IPC-", "CS-")


def sku_key(item: str | None) -> str:
    """Normalize a catalog item for labor matching (strip vendor prefixes)."""
    s = (item or "").strip().upper()
    s = re.sub(r"[\s_]+", "-", s)
    for prefix in _SKU_PREFIXES:
        if s.startswith(prefix):
            s = s[len(prefix) :]
            break
    return s


def manufacturer_aliases(target: str) -> frozenset[str]:
    t = (target or "").strip().lower()
    if not t:
        return frozenset()
    if t in _CS_MANUFACTURER_ALIASES:
        return _CS_MANUFACTURER_ALIASES
    if t in _INPRO_MANUFACTURER_ALIASES:
        return _INPRO_MANUFACTURER_ALIASES
    return frozenset({t})


def is_target_manufacturer(name: str | None, target: str) -> bool:
    n = (name or "").strip().lower()
    if not n:
        return False
    return n in manufacturer_aliases(target)


@dataclass(frozen=True)
class CatalogOldRow:
    id: Any
    manufacturer: str
    item: str
    labor_per: Any = None


@dataclass
class CatalogReplacePlan:
    updates: list[tuple[Any, dict[str, object]]] = field(default_factory=list)
    inserts: list[dict[str, object]] = field(default_factory=list)
    delete_ids: list[Any] = field(default_factory=list)
    labor_copied: int = 0
    unmatched_new: int = 0
    ambiguous_keys: list[str] = field(default_factory=list)

    @property
    def updated_count(self) -> int:
        return len(self.updates)

    @property
    def inserted_count(self) -> int:
        return len(self.inserts)

    @property
    def deleted_count(self) -> int:
        return len(self.delete_ids)


def _overlay_labor(payload: dict[str, object], old_labor: Any) -> tuple[dict[str, object], bool]:
    out = dict(payload)
    if out.get("labor_per") is None and old_labor is not None:
        out["labor_per"] = old_labor
        return out, True
    return out, False


def plan_manufacturer_replace(
    old_rows: list[CatalogOldRow],
    payloads: list[dict[str, object]],
    target_manufacturer: str,
) -> CatalogReplacePlan:
    """Replace one manufacturer: keep unique SKU labor, delete leftover old rows."""
    old_cs = [r for r in old_rows if is_target_manufacturer(r.manufacturer, target_manufacturer)]
    assigned: set[Any] = set()
    plan = CatalogReplacePlan()

    for payload in payloads:
        item = str(payload.get("item") or "")
        new_mfr = str(payload.get("manufacturer") or "").strip().lower()
        unassigned = [r for r in old_cs if r.id not in assigned]
        exact_item = [r for r in unassigned if r.item == item]
        named = [r for r in exact_item if (r.manufacturer or "").strip().lower() == new_mfr]

        chosen: CatalogOldRow | None = None
        skip_labor = False
        key = sku_key(item)

        if len(named) == 1:
            chosen = named[0]
        elif len(exact_item) == 1:
            chosen = exact_item[0]
        elif len(exact_item) > 1:
            skip_labor = True
            plan.ambiguous_keys.append(item)
            chosen = named[0] if named else exact_item[0]
        else:
            sku_hits = [r for r in unassigned if sku_key(r.item) == key]
            if len(sku_hits) == 1:
                chosen = sku_hits[0]
            elif len(sku_hits) > 1:
                skip_labor = True
                plan.ambiguous_keys.append(key)
                plan.inserts.append(dict(payload))
                plan.unmatched_new += 1
                continue

        if chosen is None:
            plan.inserts.append(dict(payload))
            plan.unmatched_new += 1
            continue

        assigned.add(chosen.id)
        if skip_labor:
            fields = dict(payload)
            if fields.get("labor_per") is None:
                fields.pop("labor_per", None)
            plan.updates.append((chosen.id, fields))
            continue
        fields, copied = _overlay_labor(payload, chosen.labor_per)
        if copied:
            plan.labor_copied += 1
        plan.updates.append((chosen.id, fields))

    plan.delete_ids = [r.id for r in old_cs if r.id not in assigned]
    return plan


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
    from app.material_url import split_description_url

    description, manufacturer_url = split_description_url(
        description, _blank_to_none(_get_cell(row, col_map, "manufacturer_url"))
    )
    mounting_type = _blank_to_none(_get_cell(row, col_map, "mounting_type"))
    cost = _parse_decimal(_get_cell(row, col_map, "cost"))
    labor_per = _parse_decimal(_get_cell(row, col_map, "labor_per"))
    labor_units_per_hour = (
        _parse_decimal(_get_cell(row, col_map, "labor_units_per_hour"))
        if "labor_units_per_hour" in col_map
        else None
    )
    labor_rate_unit = None
    if "labor_rate_unit" in col_map:
        from app.material_labor import normalize_rate_unit

        labor_rate_unit = normalize_rate_unit(_get_cell(row, col_map, "labor_rate_unit"))
    uom = _blank_to_none(_get_cell(row, col_map, "unit_of_measure")) or "EA"
    currency = (_blank_to_none(_get_cell(row, col_map, "currency")) or "USD").upper()[:3]
    csi_raw = _blank_to_none(_get_cell(row, col_map, "csi_spec_section"))
    csi_spec_section = None
    if csi_raw:
        from app.csi_spec import normalize_csi_spec_section

        csi_spec_section = normalize_csi_spec_section(csi_raw)
    from app.locker_csi import infer_locker_csi

    inferred_csi = infer_locker_csi(
        manufacturer=manufacturer,
        item=item,
        category=category,
        description=description,
        csi_spec_section=csi_spec_section,
    )
    if inferred_csi:
        csi_spec_section = inferred_csi

    from app.material_size import parse_inch_value, parse_size_cell

    size_width_in = parse_inch_value(_get_cell(row, col_map, "size_width_in")) if "size_width_in" in col_map else None
    size_height_in = parse_inch_value(_get_cell(row, col_map, "size_height_in")) if "size_height_in" in col_map else None
    size_depth_in = parse_inch_value(_get_cell(row, col_map, "size_depth_in")) if "size_depth_in" in col_map else None
    if (size_width_in is None or size_height_in is None) and "size" in col_map:
        parsed_w, parsed_h = parse_size_cell(_get_cell(row, col_map, "size"))
        if size_width_in is None:
            size_width_in = parsed_w
        if size_height_in is None:
            size_height_in = parsed_h

    payload: dict[str, object] = {
        "manufacturer": manufacturer[:120],
        "manufacturer_url": manufacturer_url,
        "item": item[:120],
        "category": category[:120] if category else None,
        "csi_spec_section": csi_spec_section,
        "description": description,
        "mounting_type": mounting_type[:120] if mounting_type else None,
        "cost": cost,
        "labor_per": labor_per,
        "labor_units_per_hour": labor_units_per_hour,
        "labor_rate_unit": labor_rate_unit,
        "currency": currency,
        "unit_of_measure": uom[:20],
    }
    if labor_units_per_hour is not None and labor_rate_unit:
        from types import SimpleNamespace

        from app.material_labor import sync_material_labor

        tmp = SimpleNamespace(
            labor_units_per_hour=labor_units_per_hour,
            labor_rate_unit=labor_rate_unit,
            labor_per=labor_per,
            unit_of_measure=payload["unit_of_measure"],
        )
        sync_material_labor(tmp)
        payload["labor_per"] = tmp.labor_per
        payload["labor_units_per_hour"] = tmp.labor_units_per_hour
        payload["labor_rate_unit"] = tmp.labor_rate_unit
        payload["unit_of_measure"] = tmp.unit_of_measure
    if (
        "size_width_in" in col_map
        or "size_height_in" in col_map
        or "size_depth_in" in col_map
        or "size" in col_map
    ):
        payload["size_width_in"] = size_width_in
        payload["size_height_in"] = size_height_in
        payload["size_depth_in"] = size_depth_in
    return payload


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


# Finish-color SKUs (Charcoal 0077-FH, Ice White 410-SEI, HDPE Gray 9200, …) are not
# catalog styles. Style rows stay: BOB-DESIGNER-1040, BOB-DURALINE-*, ASI-HDPE, ASI-PC-STEEL.
_PARTITION_COLOR_ITEM = re.compile(
    r"^(?:BOB-DL-|BOB-DS-|BOB-SC-SCO|ASI-HDPE-\d|ASI-PC-\d)",
    re.IGNORECASE,
)


def is_partition_category(category: str | None) -> bool:
    text = (category or "").casefold()
    return "toilet partition" in text or "toilet compartment" in text


def is_partition_color_sku(
    *,
    item: str | None,
    category: str | None,
    description: str | None = None,
) -> bool:
    """True when the row is a partition finish color, not a style/material."""
    del description  # kept for call-site compatibility
    if not is_partition_category(category):
        return False
    sku = (item or "").strip()
    return bool(sku) and _PARTITION_COLOR_ITEM.match(sku) is not None


def drop_partition_color_skus(payloads: list[dict[str, object]]) -> list[dict[str, object]]:
    return [
        payload
        for payload in payloads
        if not is_partition_color_sku(
            item=str(payload.get("item") or "") or None,
            category=str(payload.get("category") or "") or None,
            description=str(payload.get("description") or "") or None,
        )
    ]
