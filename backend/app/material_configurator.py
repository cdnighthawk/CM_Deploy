"""Configurable catalog items: size/mount SKU plus selectable option groups."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Mapping

LARSEN_CABINET_KEY = "larsen_cabinet"

LARSEN_CABINET_SCHEMA: dict[str, Any] = {
    "key": LARSEN_CABINET_KEY,
    "label": "Larsen fire extinguisher cabinet",
    "groups": [
        {
            "id": "series",
            "label": "Series",
            "required": True,
            "default": "architectural",
            "choices": [
                {"id": "architectural", "label": "Architectural", "cost": "0"},
                {"id": "gemini", "label": "Gemini (frameless acrylic)", "cost": "35"},
                {"id": "cameo", "label": "Cameo (bubble door)", "cost": "0"},
                {"id": "occult", "label": "Occult (concealed hinge)", "cost": "108"},
                {"id": "medallion", "label": "Medallion (brass / bronze door)", "cost": "0"},
                {"id": "detention", "label": "Detention", "cost": "0"},
            ],
        },
        {
            "id": "material",
            "label": "Material",
            "required": True,
            "default": "steel",
            "choices": [
                {"id": "steel", "label": "Steel", "cost": "0"},
                {"id": "aluminum", "label": "Aluminum", "cost": "69"},
                {"id": "stainless", "label": "Stainless steel", "cost": "109"},
                {"id": "brass", "label": "Brass", "cost": "727"},
                {"id": "bronze", "label": "Bronze", "cost": "835"},
            ],
        },
        {
            "id": "door",
            "label": "Door style",
            "required": True,
            "default": "full_glazed",
            "choices": [
                {"id": "full_glazed", "label": "Full glazed", "cost": "0"},
                {"id": "solid", "label": "Solid door", "cost": "-11"},
                {"id": "vertical_duo", "label": "Vertical duo", "cost": "1"},
                {"id": "horizontal_duo", "label": "Horizontal duo", "cost": "1"},
            ],
        },
        {
            "id": "handle",
            "label": "Handle / lock",
            "required": True,
            "default": "standard",
            "choices": [
                {"id": "standard", "label": "Standard pull", "cost": "0"},
                {"id": "recessed", "label": "Recessed handle", "cost": "25"},
                {"id": "larsen_loc", "label": "Larsen-Loc", "cost": "0"},
            ],
        },
        {
            "id": "extras",
            "label": "Options",
            "multiple": True,
            "choices": [
                {"id": "flame_shield", "label": "Flame-Shield (fire-rated)"},
                {"id": "lettering", "label": "Die-cut lettering", "cost": "10"},
                {"id": "tempered", "label": "Tempered glazing"},
                {"id": "special_color", "label": "Special color", "cost": "75"},
                {"id": "vigilante", "label": "Vigilante alarm", "cost": "55"},
            ],
        },
    ],
}

SCHEMAS: dict[str, dict[str, Any]] = {LARSEN_CABINET_KEY: LARSEN_CABINET_SCHEMA}


@dataclass(frozen=True)
class ResolvedConfiguration:
    key: str
    snapshot: dict[str, Any]
    unit_cost: Decimal
    description: str
    labels: tuple[str, ...]


def schema_for(key: str | None) -> dict[str, Any] | None:
    if not key:
        return None
    schema = SCHEMAS.get(str(key).strip())
    return dict(schema) if schema else None


def public_schema(key: str | None) -> dict[str, Any] | None:
    schema = schema_for(key)
    if not schema:
        return None
    groups = []
    for group in schema.get("groups") or []:
        choices = []
        for choice in group.get("choices") or []:
            choices.append(
                {
                    "id": choice["id"],
                    "label": choice["label"],
                    "cost": _num(choice.get("cost")),
                }
            )
        groups.append(
            {
                "id": group["id"],
                "label": group["label"],
                "required": bool(group.get("required")),
                "multiple": bool(group.get("multiple")),
                "default": group.get("default"),
                "choices": choices,
            }
        )
    return {"key": schema["key"], "label": schema.get("label") or schema["key"], "groups": groups}


def _num(raw: Any) -> float:
    if raw in (None, ""):
        return 0.0
    return float(Decimal(str(raw)))


def _money(raw: Any) -> Decimal:
    if raw in (None, ""):
        return Decimal("0")
    return Decimal(str(raw))


def _choice_map(group: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {str(c["id"]): c for c in (group.get("choices") or []) if c.get("id")}


def _as_id_list(raw: Any) -> list[str]:
    if raw is None or raw == "":
        return []
    if isinstance(raw, str):
        return [raw.strip()] if raw.strip() else []
    if isinstance(raw, (list, tuple, set)):
        out: list[str] = []
        for item in raw:
            s = str(item).strip()
            if s and s not in out:
                out.append(s)
        return out
    return [str(raw).strip()]


def default_selections(schema: Mapping[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for group in schema.get("groups") or []:
        gid = str(group.get("id") or "")
        if not gid:
            continue
        if group.get("multiple"):
            out[gid] = list(group.get("default") or [])
        else:
            out[gid] = group.get("default")
    return out


def resolve_configuration(
    *,
    manufacturer: str | None,
    item: str | None,
    mounting_type: str | None,
    base_cost: Decimal | None,
    configurator_key: str | None,
    selections: Mapping[str, Any] | None = None,
) -> ResolvedConfiguration:
    schema = schema_for(configurator_key)
    if not schema:
        raise ValueError("catalog item is not configurable")
    merged = default_selections(schema)
    incoming = dict(selections or {})
    if "selections" in incoming and isinstance(incoming["selections"], Mapping):
        incoming = dict(incoming["selections"])
    merged.update({k: v for k, v in incoming.items() if v is not None})

    labels: list[str] = []
    extra_cost = Decimal("0")
    frozen: dict[str, Any] = {}
    for group in schema.get("groups") or []:
        gid = str(group["id"])
        choices = _choice_map(group)
        if group.get("multiple"):
            ids = _as_id_list(merged.get(gid))
            unknown = [cid for cid in ids if cid not in choices]
            if unknown:
                raise ValueError(f"unknown {group['label']} option: {unknown[0]}")
            frozen[gid] = ids
            for cid in ids:
                choice = choices[cid]
                extra_cost += _money(choice.get("cost"))
                labels.append(str(choice["label"]))
            continue
        cid = str(merged.get(gid) or "").strip()
        if not cid:
            if group.get("required"):
                raise ValueError(f"{group['label']} is required")
            frozen[gid] = None
            continue
        choice = choices.get(cid)
        if choice is None:
            raise ValueError(f"unknown {group['label']} option: {cid}")
        frozen[gid] = cid
        extra_cost += _money(choice.get("cost"))
        labels.append(str(choice["label"]))

    unit_cost = (base_cost or Decimal("0")) + extra_cost
    mfr = (manufacturer or "").strip() or "Catalog"
    sku = (item or "").strip()
    mount = (mounting_type or "").strip()
    head = " ".join(p for p in (mfr, sku, mount) if p)
    suffix = ", ".join(labels)
    description = f"{head} — {suffix}" if suffix else head
    snapshot = {
        "key": schema["key"],
        "selections": frozen,
        "labels": labels,
        "unit_cost": str(unit_cost.quantize(Decimal("0.0001"))),
    }
    return ResolvedConfiguration(
        key=str(schema["key"]),
        snapshot=snapshot,
        unit_cost=unit_cost,
        description=description[:500],
        labels=tuple(labels),
    )
