"""Door schedule import, opening CRUD helpers, and takeoff line expansion."""
from __future__ import annotations

import re
import uuid
from decimal import Decimal
from typing import Any, Mapping, Optional

from sqlalchemy import delete, func, select
from sqlalchemy.orm import joinedload

from ..csi_spec import is_door_hardware_section
from ..extensions import db
from ..models.door_hardware_set import DoorHardwareSet, DoorHardwareSetItem
from ..models.door_opening import DoorOpening
from ..models.lead_estimate import LeadEstimate
from ..models.material_pricing import MaterialPrice
from ..models.takeoff_line_item import TakeoffLineItem

_SIZE_RE = re.compile(
    r"(?P<w>[\d'\"./\s-]+?)\s*(?:x|×|\*)\s*(?P<h>[\d'\"./\s-]+)",
    re.IGNORECASE,
)
_HW_TO_HD_RE = re.compile(r"^HW-(\d+)$", re.IGNORECASE)
_HD_CODE_RE = re.compile(r"^HD-\d+$", re.IGNORECASE)


def _str_field(raw: Any, max_len: int) -> Optional[str]:
    if raw is None:
        return None
    s = str(raw).strip()
    return s[:max_len] if s else None


def _cell(row: Mapping[str, Any], column_map: Mapping[str, str], field: str) -> Any:
    header = column_map.get(field)
    if not header:
        return None
    return row.get(header)


def parse_size_value(raw: Any) -> tuple[Optional[str], Optional[str]]:
    """Parse combined size like ``3'-0\" x 7'-0\"`` into width/height strings."""
    if raw is None:
        return None, None
    s = str(raw).strip()
    if not s:
        return None, None
    m = _SIZE_RE.search(s)
    if m:
        return _str_field(m.group("w"), 40), _str_field(m.group("h"), 40)
    return _str_field(s, 40), None


def normalize_hardware_set_code(code: str | None) -> str | None:
    """Map HW-1 → HD-1; return uppercased code up to 60 chars."""
    if code is None:
        return None
    c = str(code).strip().upper()
    if not c:
        return None
    m = _HW_TO_HD_RE.match(c)
    if m:
        return f"HD-{m.group(1)}"
    return c[:60]


def row_to_opening_fields(row: Mapping[str, Any], column_map: Mapping[str, str]) -> dict[str, Any]:
    mark = _str_field(_cell(row, column_map, "mark"), 60) or ""
    width = _str_field(_cell(row, column_map, "width"), 40)
    height = _str_field(_cell(row, column_map, "height"), 40)
    if not width and not height:
        w2, h2 = parse_size_value(_cell(row, column_map, "size"))
        width = width or w2
        height = height or h2
    return {
        "mark": mark,
        "room": _str_field(_cell(row, column_map, "room"), 255),
        "width": width,
        "height": height,
        "door_type": _str_field(_cell(row, column_map, "door_type"), 120),
        "frame_type": _str_field(_cell(row, column_map, "frame_type"), 120),
        "hardware_set_code": normalize_hardware_set_code(
            _str_field(_cell(row, column_map, "hardware_set_code"), 60)
        ),
        "fire_rating": _str_field(_cell(row, column_map, "fire_rating"), 60),
        "handing": _str_field(_cell(row, column_map, "handing"), 60),
        "remarks": _str_field(_cell(row, column_map, "remarks"), 2000),
        "source_row": dict(row),
    }


def _section_for_mark(mark: str) -> str:
    m = (mark or "").strip()
    return f"Door {m}" if m else "Door (unmarked)"


def _size_label(opening: DoorOpening) -> str:
    parts = []
    if opening.width:
        parts.append(opening.width)
    if opening.height:
        parts.append(opening.height)
    return " x ".join(parts) if parts else ""


def load_hardware_sets_by_code() -> dict[str, DoorHardwareSet]:
    rows = db.session.scalars(
        select(DoorHardwareSet).options(joinedload(DoorHardwareSet.items))
    ).unique().all()
    out: dict[str, DoorHardwareSet] = {}
    for hs in rows:
        key = normalize_hardware_set_code(hs.code) or ""
        if not key:
            continue
        out[key] = hs
        hm = re.match(r"^HD-(\d+)$", key, re.I)
        if hm:
            out[f"HW-{hm.group(1)}"] = hs
    return out


def get_hardware_set_by_code(code: str) -> DoorHardwareSet | None:
    norm = normalize_hardware_set_code(code)
    if not norm:
        return None
    return db.session.scalar(
        select(DoorHardwareSet)
        .options(joinedload(DoorHardwareSet.items))
        .where(DoorHardwareSet.code == norm)
    )


def get_hardware_set_by_id(hs_id: uuid.UUID) -> DoorHardwareSet | None:
    return db.session.scalar(
        select(DoorHardwareSet)
        .options(joinedload(DoorHardwareSet.items))
        .where(DoorHardwareSet.id == hs_id)
    )


def validate_hardware_set_code(code: str) -> str:
    norm = normalize_hardware_set_code(code)
    if not norm or not _HD_CODE_RE.match(norm):
        raise ValueError("code must match HD-<number> (e.g. HD-1)")
    return norm


def _parse_material_pricing_id(raw: Any) -> uuid.UUID | None:
    if raw is None or raw == "":
        return None
    try:
        return uuid.UUID(str(raw))
    except ValueError as exc:
        raise ValueError("invalid material_pricing_id") from exc


def _validate_hardware_material(material_pricing_id: uuid.UUID | None) -> None:
    if material_pricing_id is None:
        return
    mp = db.session.get(MaterialPrice, material_pricing_id)
    if mp is None:
        raise ValueError("material_pricing_id not found")
    if not is_door_hardware_section(mp.csi_spec_section):
        raise ValueError("material must be CSI spec section 08 71 00 (087100)")


def create_hardware_set(code: str, name: str, description: str | None = None) -> DoorHardwareSet:
    norm = validate_hardware_set_code(code)
    existing = db.session.scalar(select(DoorHardwareSet).where(DoorHardwareSet.code == norm))
    if existing is not None:
        raise ValueError(f"hardware set {norm} already exists")
    hs = DoorHardwareSet(code=norm, name=(name or "").strip()[:255], description=description)
    db.session.add(hs)
    db.session.flush()
    return hs


def update_hardware_set(hs: DoorHardwareSet, *, name: str | None = None, description: str | None = None) -> DoorHardwareSet:
    if name is not None:
        hs.name = str(name).strip()[:255]
    if description is not None:
        hs.description = str(description).strip()[:500] if str(description).strip() else None
    return hs


def add_hardware_set_item(hs: DoorHardwareSet, data: Mapping[str, Any]) -> DoorHardwareSetItem:
    mp_id = _parse_material_pricing_id(data.get("material_pricing_id"))
    _validate_hardware_material(mp_id)
    sort_ix = db.session.scalar(
        select(func.coalesce(func.max(DoorHardwareSetItem.sort_order), -1)).where(
            DoorHardwareSetItem.hardware_set_id == hs.id
        )
    )
    qty = data.get("default_qty", 1)
    try:
        qty_dec = Decimal(str(qty))
    except Exception as exc:
        raise ValueError("invalid default_qty") from exc
    uc = data.get("default_unit_cost", 0)
    try:
        uc_dec = Decimal(str(uc))
    except Exception as exc:
        raise ValueError("invalid default_unit_cost") from exc
    ct = str(data.get("cost_type") or "M").strip().upper()[:1] or "M"
    if ct not in ("L", "M", "E", "S", "O"):
        ct = "M"
    item = DoorHardwareSetItem(
        hardware_set_id=hs.id,
        label=str(data.get("label") or "").strip()[:255],
        cost_type=ct,
        default_qty=qty_dec,
        unit=str(data.get("unit") or "EA").strip()[:50] or "EA",
        default_unit_cost=uc_dec,
        material_pricing_id=mp_id,
        sort_order=int(sort_ix if sort_ix is not None else -1) + 1,
    )
    db.session.add(item)
    db.session.flush()
    return item


def update_hardware_set_item(item: DoorHardwareSetItem, data: Mapping[str, Any]) -> DoorHardwareSetItem:
    if "label" in data:
        item.label = str(data.get("label") or "").strip()[:255]
    if "cost_type" in data:
        ct = str(data.get("cost_type") or "M").strip().upper()[:1] or "M"
        item.cost_type = ct if ct in ("L", "M", "E", "S", "O") else "M"
    if "default_qty" in data:
        item.default_qty = Decimal(str(data.get("default_qty")))
    if "unit" in data:
        item.unit = str(data.get("unit") or "EA").strip()[:50] or "EA"
    if "default_unit_cost" in data:
        item.default_unit_cost = Decimal(str(data.get("default_unit_cost")))
    if "material_pricing_id" in data:
        mp_id = _parse_material_pricing_id(data.get("material_pricing_id"))
        _validate_hardware_material(mp_id)
        item.material_pricing_id = mp_id
    if "sort_order" in data:
        item.sort_order = int(data.get("sort_order"))
    return item


def delete_hardware_set_item(item: DoorHardwareSetItem) -> None:
    db.session.delete(item)


def _next_line_sort(lead_estimate_id: uuid.UUID) -> int:
    m = db.session.scalar(
        select(func.coalesce(func.max(TakeoffLineItem.sort_order), -1)).where(
            TakeoffLineItem.lead_estimate_id == lead_estimate_id
        )
    )
    return int(m if m is not None else -1) + 1


def _make_line(
    opening: DoorOpening,
    *,
    line_role: str,
    description: str,
    cost_type: str,
    quantity: Decimal,
    unit: str,
    unit_cost: Decimal,
    sort_order: int,
    hardware_set: Optional[str] = None,
    material_pricing_id: Optional[uuid.UUID] = None,
) -> TakeoffLineItem:
    ext = (quantity * unit_cost).quantize(Decimal("0.01"))
    md: dict[str, Any] = {"source": "door_schedule", "component": line_role}
    if hardware_set:
        md["hardware_set"] = hardware_set
    t = TakeoffLineItem(
        lead_estimate_id=opening.lead_estimate_id,
        project_id=opening.project_id,
        door_opening_id=opening.id,
        line_role=line_role,
        section=_section_for_mark(opening.mark),
        sort_order=sort_order,
        description=description[:500],
        quantity=quantity,
        unit=unit[:50] or "EA",
        unit_cost=unit_cost,
        extended_total=ext,
        cost_type=(cost_type or "M")[:20].upper()[:1] or "M",
        takeoff_location=opening.room,
        measurement_data=md,
        material_pricing_id=material_pricing_id,
    )
    if t.cost_type not in ("L", "M", "E", "S", "O"):
        t.cost_type = "M"
    return t


def rebuild_opening_lines(
    opening: DoorOpening,
    hardware_sets: Optional[dict[str, DoorHardwareSet]] = None,
    *,
    preserve_priced: bool = True,
) -> list[TakeoffLineItem]:
    """Replace door-schedule takeoff lines for one opening (door + frame + hardware template)."""
    if hardware_sets is None:
        hardware_sets = load_hardware_sets_by_code()

    existing = list(
        db.session.scalars(
            select(TakeoffLineItem).where(TakeoffLineItem.door_opening_id == opening.id)
        ).all()
    )
    priced_ids = set()
    if preserve_priced:
        for ln in existing:
            if (ln.unit_cost and ln.unit_cost > 0) or ln.material_pricing_id:
                priced_ids.add((ln.line_role or "", ln.description or ""))

    db.session.execute(delete(TakeoffLineItem).where(TakeoffLineItem.door_opening_id == opening.id))

    sort_base = _next_line_sort(opening.lead_estimate_id)
    created: list[TakeoffLineItem] = []
    size = _size_label(opening)
    mark = (opening.mark or "").strip() or "—"
    dt = opening.door_type or "Door"
    ft = opening.frame_type or "Frame"

    door_desc = f"{dt} — {mark}"
    if size:
        door_desc += f" ({size})"
    frame_desc = f"{ft} — {mark}"
    if size:
        frame_desc += f" ({size})"

    skeleton = [
        ("door", door_desc, "M", Decimal("1"), "EA", Decimal("0")),
        ("frame", frame_desc, "M", Decimal("1"), "EA", Decimal("0")),
    ]
    for i, (role, desc, ct, qty, unit, uc) in enumerate(skeleton):
        if preserve_priced and (role, desc) in priced_ids:
            continue
        ln = _make_line(
            opening,
            line_role=role,
            description=desc,
            cost_type=ct,
            quantity=qty,
            unit=unit,
            unit_cost=uc,
            sort_order=sort_base + i,
        )
        db.session.add(ln)
        created.append(ln)

    hw_code = normalize_hardware_set_code(opening.hardware_set_code) or ""
    hs = hardware_sets.get(hw_code) if hw_code else None
    if hs:
        for j, item in enumerate(sorted(hs.items, key=lambda x: x.sort_order)):
            desc = f"{hs.code} — {item.label}"
            if preserve_priced and ("hardware", desc) in priced_ids:
                continue
            ln = _make_line(
                opening,
                line_role="hardware",
                description=desc,
                cost_type=item.cost_type,
                quantity=item.default_qty,
                unit=item.unit,
                unit_cost=item.default_unit_cost,
                sort_order=sort_base + len(skeleton) + j,
                hardware_set=hs.code,
                material_pricing_id=item.material_pricing_id,
            )
            db.session.add(ln)
            created.append(ln)

    return created


def expand_hardware_for_opening(opening: DoorOpening) -> list[TakeoffLineItem]:
    """Re-apply hardware template; removes prior hardware lines only."""
    db.session.execute(
        delete(TakeoffLineItem).where(
            TakeoffLineItem.door_opening_id == opening.id,
            TakeoffLineItem.line_role == "hardware",
        )
    )
    hardware_sets = load_hardware_sets_by_code()
    hw_code = normalize_hardware_set_code(opening.hardware_set_code) or ""
    hs = hardware_sets.get(hw_code) if hw_code else None
    if not hs:
        return []
    sort_base = _next_line_sort(opening.lead_estimate_id)
    created: list[TakeoffLineItem] = []
    for j, item in enumerate(sorted(hs.items, key=lambda x: x.sort_order)):
        ln = _make_line(
            opening,
            line_role="hardware",
            description=f"{hs.code} — {item.label}",
            cost_type=item.cost_type,
            quantity=item.default_qty,
            unit=item.unit,
            unit_cost=item.default_unit_cost,
            sort_order=sort_base + j,
            hardware_set=hs.code,
            material_pricing_id=item.material_pricing_id,
        )
        db.session.add(ln)
        created.append(ln)
    return created


def opening_extended_total(opening: DoorOpening) -> Decimal:
    lines = db.session.scalars(
        select(TakeoffLineItem).where(TakeoffLineItem.door_opening_id == opening.id)
    ).all()
    return sum((ln.extended_total or Decimal("0")) for ln in lines)


def door_opening_public(opening: DoorOpening, *, include_lines: bool = True) -> dict[str, Any]:
    out: dict[str, Any] = {
        "id": str(opening.id),
        "lead_estimate_id": str(opening.lead_estimate_id),
        "project_id": str(opening.project_id) if opening.project_id else None,
        "mark": opening.mark,
        "room": opening.room,
        "width": opening.width,
        "height": opening.height,
        "door_type": opening.door_type,
        "frame_type": opening.frame_type,
        "hardware_set_code": opening.hardware_set_code,
        "fire_rating": opening.fire_rating,
        "handing": opening.handing,
        "remarks": opening.remarks,
        "sort_order": opening.sort_order,
        "import_batch_id": str(opening.import_batch_id) if opening.import_batch_id else None,
        "extended_total": float(opening_extended_total(opening)),
    }
    if include_lines:
        lines = list(
            db.session.scalars(
                select(TakeoffLineItem)
                .where(TakeoffLineItem.door_opening_id == opening.id)
                .order_by(TakeoffLineItem.sort_order.asc(), TakeoffLineItem.created_at.asc())
            ).all()
        )
        out["takeoff_line_count"] = len(lines)
    else:
        out["takeoff_line_count"] = db.session.scalar(
            select(func.count()).select_from(TakeoffLineItem).where(
                TakeoffLineItem.door_opening_id == opening.id
            )
        ) or 0
    return out


def hardware_set_public(hs: DoorHardwareSet) -> dict[str, Any]:
    items = sorted(hs.items, key=lambda x: x.sort_order)
    return {
        "id": str(hs.id),
        "code": hs.code,
        "name": hs.name,
        "description": hs.description,
        "items": [
            {
                "id": str(it.id),
                "label": it.label,
                "cost_type": it.cost_type,
                "default_qty": float(it.default_qty),
                "unit": it.unit,
                "default_unit_cost": float(it.default_unit_cost),
                "material_pricing_id": str(it.material_pricing_id) if it.material_pricing_id else None,
                "sort_order": it.sort_order,
            }
            for it in items
        ],
    }


def import_door_schedule(
    lead: LeadEstimate,
    rows: list[Mapping[str, Any]],
    column_map: Mapping[str, str],
    *,
    mode: str = "merge",
) -> dict[str, Any]:
    if mode not in ("merge", "replace"):
        raise ValueError("mode must be merge or replace")
    batch_id = uuid.uuid4()
    hardware_sets = load_hardware_sets_by_code()

    if mode == "replace":
        opening_ids = db.session.scalars(
            select(DoorOpening.id).where(DoorOpening.lead_estimate_id == lead.id)
        ).all()
        if opening_ids:
            db.session.execute(
                delete(TakeoffLineItem).where(TakeoffLineItem.door_opening_id.in_(opening_ids))
            )
        db.session.execute(delete(DoorOpening).where(DoorOpening.lead_estimate_id == lead.id))

    existing_by_mark: dict[str, DoorOpening] = {}
    if mode == "merge":
        for op in db.session.scalars(
            select(DoorOpening).where(DoorOpening.lead_estimate_id == lead.id)
        ).all():
            key = (op.mark or "").strip().upper()
            if key:
                existing_by_mark[key] = op

    created = 0
    updated = 0
    sort_ix = db.session.scalar(
        select(db.func.coalesce(db.func.max(DoorOpening.sort_order), -1)).where(
            DoorOpening.lead_estimate_id == lead.id
        )
    )
    sort_ix = int(sort_ix if sort_ix is not None else -1)

    for row in rows:
        if not isinstance(row, Mapping):
            continue
        fields = row_to_opening_fields(row, column_map)
        mark = fields["mark"]
        if not mark:
            mark = f"ROW-{sort_ix + 1}"
            fields["mark"] = mark[:60]
        key = mark.strip().upper()
        op = existing_by_mark.get(key) if mode == "merge" else None
        if op is None:
            sort_ix += 1
            op = DoorOpening(
                lead_estimate_id=lead.id,
                project_id=lead.project_id,
                sort_order=sort_ix,
                import_batch_id=batch_id,
                **{k: v for k, v in fields.items() if k != "source_row"},
            )
            op.source_row = fields.get("source_row")
            db.session.add(op)
            db.session.flush()
            existing_by_mark[key] = op
            created += 1
        else:
            for attr in (
                "room",
                "width",
                "height",
                "door_type",
                "frame_type",
                "hardware_set_code",
                "fire_rating",
                "handing",
                "remarks",
            ):
                setattr(op, attr, fields.get(attr))
            op.source_row = fields.get("source_row")
            op.import_batch_id = batch_id
            updated += 1
        rebuild_opening_lines(op, hardware_sets, preserve_priced=False)

    db.session.flush()
    openings = db.session.scalars(
        select(DoorOpening)
        .where(DoorOpening.lead_estimate_id == lead.id)
        .order_by(DoorOpening.sort_order.asc(), DoorOpening.created_at.asc())
    ).all()
    return {
        "import_batch_id": str(batch_id),
        "mode": mode,
        "created": created,
        "updated": updated,
        "opening_count": len(openings),
    }
