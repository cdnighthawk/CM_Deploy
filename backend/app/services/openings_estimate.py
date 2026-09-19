"""Job-scoped openings register, hardware sets, reconcile, apply, extract, draft RFPs."""
from __future__ import annotations

import csv
import io
import re
import secrets
import uuid
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable, Mapping

from sqlalchemy import delete, func, select
from sqlalchemy.orm import joinedload

from ..extensions import db
from ..models import AuditLog, Estimate, TakeoffLineItem
from ..models.door_opening import DoorOpening
from ..models.hardware_set import HARDWARE_CATEGORIES, HardwareSet, HardwareSetItem
from ..models.opening_type import OpeningType
from ..models.rfp import Rfp
from ..api._rfi_service import ApiError

OPENING_CSV_HEADERS = (
    "mark",
    "qty",
    "leaf_count",
    "width_in",
    "height_in",
    "thickness_in",
    "hand",
    "fire_rating_min",
    "material",
    "door_type_code",
    "frame_type_code",
    "frame_material",
    "frame_construction",
    "wall_thickness_in",
    "frame_gauge",
    "hardware_set_no",
    "location",
    "sheet_ref",
    "remarks",
    "scope_flag",
)
SET_CSV_HEADERS = ("set_no", "title", "finish_default", "fire_required", "pair_set", "electrified", "notes")
ITEM_CSV_HEADERS = (
    "set_no",
    "seq",
    "qty",
    "qty_unit",
    "category",
    "description",
    "manufacturer",
    "catalog",
    "function",
    "finish",
    "size",
    "notes",
)

HANDS = frozenset({"LH", "RH", "LHR", "RHR", "LHRB", "RHRB", "PAIR", "unknown"})
SCOPE_FLAGS = frozenset({"in", "out", "nic", "existing", "alt"})
MATERIALS = frozenset({"hm", "wood", "aluminum", "frp", "stainless", "other"})
FRAME_MATERIALS = frozenset({"hm", "wood", "aluminum", "existing", "other"})
FRAME_CONSTRUCTIONS = frozenset({"kd", "welded", "existing", "unknown"})
SOURCES = frozenset({"manual", "csv", "ai_schedule", "ai_spec"})
CATEGORIES = frozenset(HARDWARE_CATEGORIES)
ELECTRIFIED_CATEGORIES = frozenset({"position_switch", "power"})
BLOCKING_FLAGS = frozenset({"unconfirmed", "missing_set", "unknown_set"})

FLAG_SEVERITY = {
    "missing_set": "high",
    "unknown_set": "high",
    "orphan_set": "low",
    "pair_mismatch": "high",
    "rating_mismatch": "high",
    "hinge_count": "med",
    "schedule_spec_set": "high",
    "two_sets": "high",
    "no_size": "med",
    "no_hand": "low",
    "electrified": "info",
    "nic": "info",
    "addendum": "med",
    "unconfirmed": "high",
}

DEFAULT_OPENING_LABOR = {
    "frame_kd_hm": Decimal("0.75"),
    "frame_welded_hm": Decimal("1.25"),
    "door_standard": Decimal("1.75"),
    "door_exit_device": Decimal("2.75"),
    "closer_adjust": Decimal("0.50"),
    "rated_extra": Decimal("0.25"),
}

_SET_NO_RE = re.compile(r"^(?:SET[\s_-]*|HW[\s_-]*|HD[\s_-]*)?(.+)$", re.I)
_RANGE_RE = re.compile(r"^(\d+)\s*[–-]\s*(\d+)$")
_MARK_PREFIX_RANGE = re.compile(r"^([A-Za-z]+)?(\d+)\s*[–-]\s*([A-Za-z]+)?(\d+)$")
EXTRACT_MAX_PAGES = 20


class OpeningsError(ApiError):
    pass


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _dec(raw: Any, default: Decimal | None = None) -> Decimal | None:
    if raw is None or raw == "":
        return default
    try:
        return Decimal(str(raw))
    except (InvalidOperation, ValueError) as exc:
        raise OpeningsError(f"invalid number: {raw}") from exc


def _int(raw: Any, default: int | None = None) -> int | None:
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except (TypeError, ValueError) as exc:
        raise OpeningsError(f"invalid integer: {raw}") from exc


def _str(raw: Any, max_len: int) -> str | None:
    if raw is None:
        return None
    s = str(raw).strip()
    return s[:max_len] if s else None


def normalize_set_no(raw: str | None) -> str:
    if raw is None:
        return ""
    s = str(raw).strip().upper()
    if not s:
        return ""
    m = _SET_NO_RE.match(s)
    core = (m.group(1) if m else s).strip()
    core = re.sub(r"^0+(\d)", r"\1", core) if re.match(r"^0+\d", core) else core
    return core[:60]


def display_set_no(raw: str | None) -> str:
    s = _str(raw, 60) or ""
    return s


def expand_mark_range(mark: str) -> list[str]:
    raw = (mark or "").strip()
    if not raw:
        return []
    m = _MARK_PREFIX_RANGE.match(raw.replace("typical", "").strip())
    if not m:
        return [raw[:60]]
    p1, a, p2, b = m.group(1) or "", int(m.group(2)), m.group(3) or "", int(m.group(4))
    prefix = p1 or p2
    if (p1 and p2 and p1 != p2) or a > b or (b - a) > 200:
        return [raw[:60]]
    return [f"{prefix}{n}"[:60] for n in range(a, b + 1)]


def load_estimate(estimate_id: uuid.UUID) -> Estimate:
    est = db.session.get(Estimate, estimate_id)
    if est is None:
        raise OpeningsError("estimate not found", 404)
    return est


def _audit(cu, entity_id: uuid.UUID | None, action: str, changes: dict[str, Any] | None = None) -> None:
    db.session.add(
        AuditLog(
            user_id=cu.user.id if cu and getattr(cu, "user", None) else None,
            entity_type="openings_estimate",
            entity_id=entity_id,
            action=action,
            changes=changes or {},
        )
    )


def _conflicts_payload(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        active = list(raw.get("active") or [])
        dismissed = list(raw.get("dismissed") or [])
        return {"active": [str(x) for x in active], "dismissed": dismissed}
    return {"active": [], "dismissed": []}


def _set_active_flags(row: DoorOpening | HardwareSet, flags: list[str]) -> None:
    payload = _conflicts_payload(getattr(row, "conflicts", None))
    payload["active"] = sorted(set(flags))
    row.conflicts = payload


def _dismissed_keys(row: DoorOpening | HardwareSet) -> set[str]:
    payload = _conflicts_payload(getattr(row, "conflicts", None))
    out: set[str] = set()
    for item in payload.get("dismissed") or []:
        if isinstance(item, dict) and item.get("key"):
            out.add(str(item["key"]))
        elif isinstance(item, str):
            out.add(item)
    return out


def opening_set_no(op: DoorOpening) -> str:
    return display_set_no(op.hardware_set_no or op.hardware_set_code)


def sets_by_normalized(estimate_id: uuid.UUID) -> dict[str, HardwareSet]:
    rows = db.session.scalars(
        select(HardwareSet)
        .options(joinedload(HardwareSet.items))
        .where(HardwareSet.estimate_id == estimate_id)
    ).unique().all()
    return {hs.set_no_normalized: hs for hs in rows if hs.set_no_normalized}


def list_openings(estimate_id: uuid.UUID) -> list[DoorOpening]:
    return list(
        db.session.scalars(
            select(DoorOpening)
            .where(DoorOpening.estimate_id == estimate_id)
            .order_by(DoorOpening.sort_order.asc(), DoorOpening.created_at.asc())
        ).all()
    )


def list_sets(estimate_id: uuid.UUID) -> list[HardwareSet]:
    return list(
        db.session.scalars(
            select(HardwareSet)
            .options(joinedload(HardwareSet.items))
            .where(HardwareSet.estimate_id == estimate_id)
            .order_by(HardwareSet.set_no_normalized.asc())
        ).unique().all()
    )


def list_types(estimate_id: uuid.UUID) -> list[OpeningType]:
    return list(
        db.session.scalars(
            select(OpeningType)
            .where(OpeningType.estimate_id == estimate_id)
            .order_by(OpeningType.kind.asc(), OpeningType.code.asc())
        ).all()
    )


def expected_hinge_qty(height_in: Decimal | None) -> Decimal:
    if height_in is None or height_in <= 0:
        return Decimal("3")
    by_rule = max(3, int((height_in + Decimal("29.999")) // 30))
    extra = 1 if height_in >= Decimal("90") else 0
    return Decimal(max(3, by_rule + extra if height_in >= 90 and by_rule < 4 else by_rule))


def compute_opening_flags(op: DoorOpening, sets: dict[str, HardwareSet]) -> list[str]:
    flags: list[str] = []
    scope = (op.scope_flag or "in").lower()
    if scope == "nic":
        flags.append("nic")
    if op.confirmed_at is None and (op.source or "") in ("ai_schedule", "ai_spec"):
        flags.append("unconfirmed")
    set_no = opening_set_no(op)
    norm = normalize_set_no(set_no)
    if scope == "in":
        if not norm:
            flags.append("missing_set")
        elif norm not in sets:
            flags.append("unknown_set")
        else:
            hs = sets[norm]
            leaf = Decimal(op.leaf_count or 1)
            if leaf >= 2 and not hs.pair_set:
                flags.append("pair_mismatch")
            if leaf < 2 and hs.pair_set:
                flags.append("pair_mismatch")
            rated = int(op.fire_rating_min or 0)
            if rated >= 20 and hs.fire_required is False:
                flags.append("rating_mismatch")
            hinge_qty = sum(
                (it.qty or Decimal("0")) for it in hs.items if (it.category or "") == "hinge"
            )
            if hinge_qty and op.height_in:
                expect = expected_hinge_qty(Decimal(op.height_in))
                if hinge_qty != expect:
                    flags.append("hinge_count")
            if hs.electrified or any((it.category or "") in ELECTRIFIED_CATEGORIES for it in hs.items):
                flags.append("electrified")
    if op.width_in is None or op.height_in is None:
        flags.append("no_size")
    hand = (op.hand or op.handing or "").strip()
    if not hand or hand.lower() == "unknown":
        flags.append("no_hand")
    return flags


def compute_set_flags(hs: HardwareSet, openings: list[DoorOpening]) -> list[str]:
    flags: list[str] = []
    if hs.confirmed_at is None and False:
        flags.append("unconfirmed")
    in_scope = [
        op
        for op in openings
        if (op.scope_flag or "in") == "in" and normalize_set_no(opening_set_no(op)) == hs.set_no_normalized
    ]
    if hs.confirmed_at and not in_scope:
        flags.append("orphan_set")
    if hs.electrified or any((it.category or "") in ELECTRIFIED_CATEGORIES for it in hs.items):
        flags.append("electrified")
    return flags


def recompute_flags(estimate_id: uuid.UUID) -> dict[str, Any]:
    openings = list_openings(estimate_id)
    sets = sets_by_normalized(estimate_id)
    set_rows = list(sets.values())
    for op in openings:
        _set_active_flags(op, compute_opening_flags(op, sets))
    for hs in set_rows:
        _set_active_flags(hs, compute_set_flags(hs, openings))
    return reconcile_counts(openings, set_rows)


def reconcile_counts(openings: list[DoorOpening], sets: list[HardwareSet]) -> dict[str, Any]:
    in_scope = [op for op in openings if (op.scope_flag or "in") == "in"]
    set_norms = {hs.set_no_normalized for hs in sets}
    missing = 0
    unknown = 0
    unconfirmed = 0
    pair = 0
    rating = 0
    electrified = 0
    for op in in_scope:
        flags = set(_conflicts_payload(op.conflicts).get("active") or [])
        if "missing_set" in flags:
            missing += 1
        if "unknown_set" in flags:
            unknown += 1
        if "unconfirmed" in flags:
            unconfirmed += 1
        if "pair_mismatch" in flags:
            pair += 1
        if "rating_mismatch" in flags:
            rating += 1
        if "electrified" in flags:
            electrified += 1
    orphan = 0
    for hs in sets:
        flags = set(_conflicts_payload(hs.conflicts).get("active") or [])
        if "orphan_set" in flags:
            orphan += 1
        if "electrified" in flags:
            electrified += 1
    apply_blocked = any(
        set(_conflicts_payload(op.conflicts).get("active") or []) & BLOCKING_FLAGS for op in in_scope
    )
    return {
        "openings_in_scope": len(in_scope),
        "missing_set": missing,
        "unknown_set": unknown,
        "orphan_set": orphan,
        "pair_mismatch": pair,
        "rating_mismatch": rating,
        "unconfirmed": unconfirmed,
        "electrified": electrified,
        "apply_blocked": apply_blocked,
        "set_count": len(set_norms),
        "opening_count": len(openings),
    }


def empty_reconcile() -> dict[str, Any]:
    return {
        "openings_in_scope": 0,
        "missing_set": 0,
        "unknown_set": 0,
        "orphan_set": 0,
        "pair_mismatch": 0,
        "rating_mismatch": 0,
        "unconfirmed": 0,
        "electrified": 0,
        "apply_blocked": False,
        "set_count": 0,
        "opening_count": 0,
    }


def opening_public(op: DoorOpening) -> dict[str, Any]:
    flags = _conflicts_payload(op.conflicts)
    return {
        "id": str(op.id),
        "estimate_id": str(op.estimate_id) if op.estimate_id else None,
        "lead_estimate_id": str(op.lead_estimate_id) if op.lead_estimate_id else None,
        "project_id": str(op.project_id) if op.project_id else None,
        "mark": op.mark,
        "qty": float(op.qty or 1),
        "leaf_count": float(op.leaf_count or 1),
        "width_in": float(op.width_in) if op.width_in is not None else None,
        "height_in": float(op.height_in) if op.height_in is not None else None,
        "thickness_in": float(op.thickness_in) if op.thickness_in is not None else None,
        "hand": op.hand or op.handing,
        "fire_rating_min": op.fire_rating_min,
        "material": op.material,
        "door_type_code": op.door_type_code or op.door_type,
        "frame_type_code": op.frame_type_code or op.frame_type,
        "frame_material": op.frame_material,
        "frame_construction": op.frame_construction,
        "wall_thickness_in": float(op.wall_thickness_in) if op.wall_thickness_in is not None else None,
        "frame_gauge": op.frame_gauge,
        "hardware_set_no": opening_set_no(op),
        "location": op.location or op.room,
        "to_room": op.to_room,
        "from_room": op.from_room,
        "elevation": op.elevation,
        "sheet_ref": op.sheet_ref,
        "remarks": op.remarks,
        "scope_flag": op.scope_flag or "in",
        "source": op.source or "manual",
        "conflicts": flags,
        "confirmed_at": op.confirmed_at.isoformat() if op.confirmed_at else None,
        "confirmed_by": str(op.confirmed_by) if op.confirmed_by else None,
        "sort_order": op.sort_order,
        "width": op.width,
        "height": op.height,
        "room": op.room,
        "hardware_set_code": op.hardware_set_code,
    }


def item_public(it: HardwareSetItem) -> dict[str, Any]:
    return {
        "id": str(it.id),
        "seq": it.seq,
        "qty": float(it.qty or 0),
        "qty_unit": it.qty_unit or "ea",
        "category": it.category or "other",
        "description": it.description,
        "manufacturer": it.manufacturer,
        "catalog": it.catalog,
        "function": it.function,
        "finish": it.finish,
        "size": it.size,
        "alternates": it.alternates,
        "material_pricing_id": str(it.material_pricing_id) if it.material_pricing_id else None,
        "notes": it.notes,
    }


def set_public(hs: HardwareSet, openings: list[DoorOpening] | None = None) -> dict[str, Any]:
    used = []
    if openings is not None:
        used = [
            op.mark
            for op in openings
            if normalize_set_no(opening_set_no(op)) == hs.set_no_normalized and (op.scope_flag or "in") == "in"
        ]
    items = sorted(hs.items, key=lambda x: x.seq)
    return {
        "id": str(hs.id),
        "estimate_id": str(hs.estimate_id),
        "set_no": hs.set_no,
        "set_no_normalized": hs.set_no_normalized,
        "title": hs.title,
        "governs": hs.governs or "spec",
        "source_doc_id": str(hs.source_doc_id) if hs.source_doc_id else None,
        "finish_default": hs.finish_default,
        "fire_required": hs.fire_required,
        "pair_set": bool(hs.pair_set),
        "electrified": bool(hs.electrified),
        "notes": hs.notes,
        "confirmed_at": hs.confirmed_at.isoformat() if hs.confirmed_at else None,
        "conflicts": _conflicts_payload(hs.conflicts),
        "items": [item_public(it) for it in items],
        "used_by": used,
        "opening_count": len(used),
    }


def type_public(row: OpeningType) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "kind": row.kind,
        "code": row.code,
        "description": row.description,
        "notes": row.notes,
        "snapshot": row.snapshot,
    }


def openings_bundle(estimate_id: uuid.UUID) -> dict[str, Any]:
    recon = recompute_flags(estimate_id)
    openings = list_openings(estimate_id)
    sets = list_sets(estimate_id)
    types = list_types(estimate_id)
    return {
        "openings": [opening_public(op) for op in openings],
        "sets": [set_public(hs, openings) for hs in sets],
        "types": [type_public(t) for t in types],
        "reconcile": recon,
        "labor_defaults": labor_defaults_for_estimate(load_estimate(estimate_id)),
        "csv_headers": {
            "openings": list(OPENING_CSV_HEADERS),
            "sets": list(SET_CSV_HEADERS),
            "items": list(ITEM_CSV_HEADERS),
        },
    }


def _next_opening_sort(estimate_id: uuid.UUID) -> int:
    m = db.session.scalar(
        select(func.coalesce(func.max(DoorOpening.sort_order), -1)).where(DoorOpening.estimate_id == estimate_id)
    )
    return int(m if m is not None else -1) + 1


def _apply_opening_fields(op: DoorOpening, data: Mapping[str, Any], *, partial: bool = False) -> None:
    if "mark" in data or not partial:
        mark = _str(data.get("mark"), 60)
        if mark:
            op.mark = mark
    mapping = (
        ("location", 255),
        ("to_room", 255),
        ("from_room", 255),
        ("elevation", 80),
        ("sheet_ref", 80),
        ("door_type_code", 40),
        ("frame_type_code", 40),
        ("frame_gauge", 10),
        ("hardware_set_no", 60),
        ("remarks", 2000),
    )
    for field, ln in mapping:
        if field in data or not partial:
            val = _str(data.get(field), ln)
            setattr(op, field, val)
            if field == "location" and val:
                op.room = val
            if field == "hardware_set_no":
                op.hardware_set_code = val
            if field == "door_type_code" and val:
                op.door_type = val
            if field == "frame_type_code" and val:
                op.frame_type = val
    if "qty" in data or not partial:
        op.qty = _dec(data.get("qty"), Decimal("1")) or Decimal("1")
    if "leaf_count" in data or not partial:
        op.leaf_count = _dec(data.get("leaf_count"), Decimal("1")) or Decimal("1")
    for field in ("width_in", "height_in", "thickness_in", "wall_thickness_in"):
        if field in data or not partial:
            setattr(op, field, _dec(data.get(field)))
    if op.width_in is not None:
        op.width = f'{op.width_in}"'
    if op.height_in is not None:
        op.height = f'{op.height_in}"'
    if "hand" in data or not partial:
        hand = (_str(data.get("hand"), 20) or "").upper() or None
        if hand and hand not in HANDS:
            hand = "unknown"
        op.hand = hand
        op.handing = hand
    if "fire_rating_min" in data or not partial:
        op.fire_rating_min = _int(data.get("fire_rating_min"), 0)
        if op.fire_rating_min:
            op.fire_rating = f"{op.fire_rating_min} min"
    if "material" in data or not partial:
        mat = (_str(data.get("material"), 40) or "").lower() or None
        if mat and mat not in MATERIALS:
            mat = "other"
        op.material = mat
    if "frame_material" in data or not partial:
        fm = (_str(data.get("frame_material"), 40) or "").lower() or None
        if fm and fm not in FRAME_MATERIALS:
            fm = "other"
        op.frame_material = fm
    if "frame_construction" in data or not partial:
        fc = (_str(data.get("frame_construction"), 40) or "").lower() or None
        if fc and fc not in FRAME_CONSTRUCTIONS:
            fc = "unknown"
        op.frame_construction = fc
    if "scope_flag" in data or not partial:
        scope = (_str(data.get("scope_flag"), 20) or "in").lower()
        if scope not in SCOPE_FLAGS:
            scope = "in"
        op.scope_flag = scope
    if "source" in data and not partial:
        src = (_str(data.get("source"), 40) or "manual").lower()
        if src not in SOURCES:
            src = "manual"
        op.source = src
    if "confirmed_at" in data:
        if data.get("confirmed_at"):
            op.confirmed_at = _utcnow()
        else:
            op.confirmed_at = None


def create_opening(est: Estimate, data: Mapping[str, Any], cu=None) -> DoorOpening:
    marks = expand_mark_range(_str(data.get("mark"), 60) or "")
    if not marks:
        marks = [f"NEW-{_next_opening_sort(est.id) + 1}"]
    created: list[DoorOpening] = []
    for i, mark in enumerate(marks):
        existing = db.session.scalar(
            select(DoorOpening).where(DoorOpening.estimate_id == est.id, DoorOpening.mark == mark)
        )
        if existing is not None:
            raise OpeningsError(f"opening mark {mark} already exists")
        op = DoorOpening(
            estimate_id=est.id,
            lead_estimate_id=est.lead_estimate_id,
            project_id=est.project_id,
            mark=mark,
            sort_order=_next_opening_sort(est.id) + i,
            source=(_str(data.get("source"), 40) or "manual"),
            scope_flag="in",
            qty=Decimal("1"),
            leaf_count=Decimal("1"),
            confirmed_at=_utcnow() if (_str(data.get("source"), 40) or "manual") not in ("ai_schedule", "ai_spec") else None,
        )
        _apply_opening_fields(op, {**dict(data), "mark": mark}, partial=True)
        if op.source not in ("ai_schedule", "ai_spec") and op.confirmed_at is None:
            op.confirmed_at = _utcnow()
        db.session.add(op)
        created.append(op)
    db.session.flush()
    _audit(cu, est.id, "opening_create", {"marks": [o.mark for o in created]})
    recompute_flags(est.id)
    return created[0]


def patch_opening(est: Estimate, opening_id: uuid.UUID, data: Mapping[str, Any], cu=None) -> DoorOpening:
    op = db.session.get(DoorOpening, opening_id)
    if op is None or op.estimate_id != est.id:
        raise OpeningsError("opening not found", 404)
    before = {"scope_flag": op.scope_flag, "hardware_set_no": opening_set_no(op), "mark": op.mark}
    if "mark" in data:
        new_mark = _str(data.get("mark"), 60)
        if new_mark and new_mark != op.mark:
            clash = db.session.scalar(
                select(DoorOpening).where(
                    DoorOpening.estimate_id == est.id,
                    DoorOpening.mark == new_mark,
                    DoorOpening.id != op.id,
                )
            )
            if clash is not None:
                raise OpeningsError(f"opening mark {new_mark} already exists")
    _apply_opening_fields(op, data, partial=True)
    db.session.flush()
    _audit(
        cu,
        op.id,
        "opening_patch",
        {"from": before, "to": {"scope_flag": op.scope_flag, "hardware_set_no": opening_set_no(op), "mark": op.mark}},
    )
    recompute_flags(est.id)
    return op


def delete_opening(est: Estimate, opening_id: uuid.UUID, cu=None) -> None:
    op = db.session.get(DoorOpening, opening_id)
    if op is None or op.estimate_id != est.id:
        raise OpeningsError("opening not found", 404)
    mark = op.mark
    db.session.delete(op)
    db.session.flush()
    _audit(cu, est.id, "opening_delete", {"mark": mark})
    recompute_flags(est.id)


def confirm_opening(est: Estimate, opening_id: uuid.UUID, cu=None) -> DoorOpening:
    op = db.session.get(DoorOpening, opening_id)
    if op is None or op.estimate_id != est.id:
        raise OpeningsError("opening not found", 404)
    op.confirmed_at = _utcnow()
    if cu and getattr(cu, "user", None):
        op.confirmed_by = cu.user.id
    db.session.flush()
    _audit(cu, op.id, "confirm", {"mark": op.mark})
    recompute_flags(est.id)
    return op


def bulk_openings(est: Estimate, data: Mapping[str, Any], cu=None) -> list[DoorOpening]:
    ids = [_parse_uuid(x) for x in (data.get("opening_ids") or data.get("ids") or [])]
    ids = [x for x in ids if x]
    if not ids:
        raise OpeningsError("opening_ids is required")
    rows = list(
        db.session.scalars(
            select(DoorOpening).where(DoorOpening.estimate_id == est.id, DoorOpening.id.in_(ids))
        ).all()
    )
    patch: dict[str, Any] = {}
    if "scope_flag" in data:
        patch["scope_flag"] = data.get("scope_flag")
    if "hardware_set_no" in data:
        patch["hardware_set_no"] = data.get("hardware_set_no")
    if "door_type_code" in data:
        patch["door_type_code"] = data.get("door_type_code")
    if "frame_type_code" in data:
        patch["frame_type_code"] = data.get("frame_type_code")
    if "fire_rating_min" in data:
        patch["fire_rating_min"] = data.get("fire_rating_min")
    for op in rows:
        _apply_opening_fields(op, patch, partial=True)
    db.session.flush()
    _audit(cu, est.id, "opening_bulk", {"ids": [str(x.id) for x in rows], "patch": patch})
    recompute_flags(est.id)
    return rows


def duplicate_opening(est: Estimate, opening_id: uuid.UUID, cu=None) -> DoorOpening:
    op = db.session.get(DoorOpening, opening_id)
    if op is None or op.estimate_id != est.id:
        raise OpeningsError("opening not found", 404)
    base = op.mark or "NEW"
    m = re.match(r"^(.*?)(\d+)$", base)
    if m:
        prefix, num = m.group(1), int(m.group(2))
        nxt = f"{prefix}{num + 1}"
    else:
        nxt = f"{base}-2"
    payload = opening_public(op)
    payload["mark"] = nxt
    payload["source"] = "manual"
    return create_opening(est, payload, cu)


def dismiss_flag(est: Estimate, opening_id: uuid.UUID, key: str, reason: str, cu=None) -> DoorOpening:
    op = db.session.get(DoorOpening, opening_id)
    if op is None or op.estimate_id != est.id:
        raise OpeningsError("opening not found", 404)
    payload = _conflicts_payload(op.conflicts)
    dismissed = list(payload.get("dismissed") or [])
    dismissed.append(
        {
            "key": key,
            "reason": (reason or "")[:500],
            "at": _utcnow().isoformat(),
            "by": str(cu.user.id) if cu and getattr(cu, "user", None) else None,
        }
    )
    payload["dismissed"] = dismissed
    if key not in BLOCKING_FLAGS:
        payload["active"] = [f for f in (payload.get("active") or []) if f != key]
    op.conflicts = payload
    db.session.flush()
    _audit(cu, op.id, "flag_dismiss", {"key": key, "reason": reason, "mark": op.mark})
    return op


def _parse_uuid(raw: Any) -> uuid.UUID | None:
    if raw is None or raw == "":
        return None
    try:
        return uuid.UUID(str(raw))
    except (TypeError, ValueError):
        return None


def import_openings_csv(est: Estimate, rows: list[Mapping[str, Any]], *, source: str = "csv", cu=None) -> dict[str, Any]:
    created = 0
    updated = 0
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        mark_raw = _str(row.get("mark"), 80) or ""
        for mark in expand_mark_range(mark_raw) or []:
            existing = db.session.scalar(
                select(DoorOpening).where(DoorOpening.estimate_id == est.id, DoorOpening.mark == mark)
            )
            payload = dict(row)
            payload["mark"] = mark
            payload["source"] = source if source in SOURCES else "csv"
            if existing is None:
                create_opening(est, payload, cu)
                created += 1
            else:
                _apply_opening_fields(existing, payload, partial=True)
                if existing.source not in ("ai_schedule", "ai_spec"):
                    existing.confirmed_at = existing.confirmed_at or _utcnow()
                updated += 1
    db.session.flush()
    _audit(cu, est.id, "opening_import", {"created": created, "updated": updated})
    recompute_flags(est.id)
    return {"created": created, "updated": updated, "opening_count": len(list_openings(est.id))}


def export_openings_csv(est: Estimate) -> str:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=list(OPENING_CSV_HEADERS))
    w.writeheader()
    for op in list_openings(est.id):
        pub = opening_public(op)
        w.writerow({k: pub.get(k) if pub.get(k) is not None else "" for k in OPENING_CSV_HEADERS})
    return buf.getvalue()


def _boolish(raw: Any) -> bool:
    if isinstance(raw, bool):
        return raw
    return str(raw or "").strip().lower() in ("1", "true", "yes", "y", "on")


def _category(raw: Any) -> str:
    c = (_str(raw, 40) or "other").lower().replace(" ", "_")
    return c if c in CATEGORIES else "other"


def create_set(est: Estimate, data: Mapping[str, Any], cu=None) -> HardwareSet:
    raw_no = _str(data.get("set_no"), 60) or ""
    if not raw_no:
        raise OpeningsError("set_no is required")
    norm = normalize_set_no(raw_no)
    clash = db.session.scalar(
        select(HardwareSet).where(HardwareSet.estimate_id == est.id, HardwareSet.set_no_normalized == norm)
    )
    if clash is not None:
        raise OpeningsError(f"hardware set {raw_no} already exists")
    hs = HardwareSet(
        estimate_id=est.id,
        set_no=raw_no,
        set_no_normalized=norm,
        title=_str(data.get("title"), 255),
        governs=(_str(data.get("governs"), 20) or "spec"),
        finish_default=_str(data.get("finish_default"), 40),
        fire_required=None if data.get("fire_required") in (None, "") else _boolish(data.get("fire_required")),
        pair_set=_boolish(data.get("pair_set")),
        electrified=_boolish(data.get("electrified")),
        notes=_str(data.get("notes"), 4000),
        source_doc_id=_parse_uuid(data.get("source_doc_id")),
        confirmed_at=_utcnow() if data.get("source") not in ("ai_spec", "ai_schedule") else None,
    )
    db.session.add(hs)
    db.session.flush()
    for item in data.get("items") or []:
        if isinstance(item, Mapping):
            add_set_item(hs, item)
    _audit(cu, hs.id, "hardware_set_create", {"set_no": raw_no})
    recompute_flags(est.id)
    return hs


def patch_set(est: Estimate, set_id: uuid.UUID, data: Mapping[str, Any], cu=None) -> HardwareSet:
    hs = db.session.get(HardwareSet, set_id)
    if hs is None or hs.estimate_id != est.id:
        raise OpeningsError("hardware set not found", 404)
    if "set_no" in data:
        raw_no = _str(data.get("set_no"), 60) or hs.set_no
        norm = normalize_set_no(raw_no)
        clash = db.session.scalar(
            select(HardwareSet).where(
                HardwareSet.estimate_id == est.id,
                HardwareSet.set_no_normalized == norm,
                HardwareSet.id != hs.id,
            )
        )
        if clash is not None:
            raise OpeningsError(f"hardware set {raw_no} already exists")
        hs.set_no = raw_no
        hs.set_no_normalized = norm
    for field in ("title", "governs", "finish_default", "notes"):
        if field in data:
            setattr(hs, field, _str(data.get(field), 4000 if field == "notes" else 255))
    if "fire_required" in data:
        hs.fire_required = None if data.get("fire_required") in (None, "") else _boolish(data.get("fire_required"))
    if "pair_set" in data:
        hs.pair_set = _boolish(data.get("pair_set"))
    if "electrified" in data:
        hs.electrified = _boolish(data.get("electrified"))
    if "source_doc_id" in data:
        hs.source_doc_id = _parse_uuid(data.get("source_doc_id"))
    if data.get("confirmed") is True:
        hs.confirmed_at = _utcnow()
    db.session.flush()
    _audit(cu, hs.id, "hardware_set_patch", {"set_no": hs.set_no})
    recompute_flags(est.id)
    return hs


def delete_set(est: Estimate, set_id: uuid.UUID, cu=None) -> None:
    hs = db.session.get(HardwareSet, set_id)
    if hs is None or hs.estimate_id != est.id:
        raise OpeningsError("hardware set not found", 404)
    set_no = hs.set_no
    db.session.delete(hs)
    db.session.flush()
    _audit(cu, est.id, "hardware_set_delete", {"set_no": set_no})
    recompute_flags(est.id)


def add_set_item(hs: HardwareSet, data: Mapping[str, Any]) -> HardwareSetItem:
    seq = _int(data.get("seq"), None)
    if seq is None:
        seq = max([it.seq for it in hs.items], default=-1) + 1
    it = HardwareSetItem(
        hardware_set_id=hs.id,
        seq=seq,
        qty=_dec(data.get("qty"), Decimal("1")) or Decimal("1"),
        qty_unit=(_str(data.get("qty_unit"), 20) or "ea"),
        category=_category(data.get("category")),
        description=_str(data.get("description"), 500) or "",
        manufacturer=_str(data.get("manufacturer"), 200),
        catalog=_str(data.get("catalog"), 200),
        function=_str(data.get("function"), 80),
        finish=_str(data.get("finish"), 40),
        size=_str(data.get("size"), 80),
        notes=_str(data.get("notes"), 2000),
        material_pricing_id=_parse_uuid(data.get("material_pricing_id")),
        alternates=data.get("alternates") if isinstance(data.get("alternates"), (list, dict)) else None,
    )
    db.session.add(it)
    db.session.flush()
    return it


def patch_set_item(est: Estimate, item_id: uuid.UUID, data: Mapping[str, Any], cu=None) -> HardwareSetItem:
    it = db.session.get(HardwareSetItem, item_id)
    if it is None or it.hardware_set is None or it.hardware_set.estimate_id != est.id:
        raise OpeningsError("hardware set item not found", 404)
    if "seq" in data:
        it.seq = _int(data.get("seq"), it.seq) or it.seq
    if "qty" in data:
        it.qty = _dec(data.get("qty"), it.qty) or it.qty
    if "qty_unit" in data:
        it.qty_unit = _str(data.get("qty_unit"), 20) or it.qty_unit
    if "category" in data:
        it.category = _category(data.get("category"))
    for field, ln in (
        ("description", 500),
        ("manufacturer", 200),
        ("catalog", 200),
        ("function", 80),
        ("finish", 40),
        ("size", 80),
        ("notes", 2000),
    ):
        if field in data:
            setattr(it, field, _str(data.get(field), ln))
    if "material_pricing_id" in data:
        it.material_pricing_id = _parse_uuid(data.get("material_pricing_id"))
    db.session.flush()
    _audit(cu, it.hardware_set_id, "hardware_set_item_patch", {"item_id": str(it.id)})
    recompute_flags(est.id)
    return it


def delete_set_item(est: Estimate, item_id: uuid.UUID, cu=None) -> None:
    it = db.session.get(HardwareSetItem, item_id)
    if it is None or it.hardware_set is None or it.hardware_set.estimate_id != est.id:
        raise OpeningsError("hardware set item not found", 404)
    sid = it.hardware_set_id
    db.session.delete(it)
    db.session.flush()
    _audit(cu, sid, "hardware_set_item_delete", {"item_id": str(item_id)})
    recompute_flags(est.id)


def copy_set(est: Estimate, set_id: uuid.UUID, new_set_no: str, cu=None) -> HardwareSet:
    hs = db.session.get(HardwareSet, set_id)
    if hs is None or hs.estimate_id != est.id:
        raise OpeningsError("hardware set not found", 404)
    payload = set_public(hs, [])
    payload["set_no"] = new_set_no
    payload["items"] = [item_public(it) for it in hs.items]
    return create_set(est, payload, cu)


def copy_from_company(est: Estimate, code: str, cu=None) -> HardwareSet:
    from .door_schedule import get_hardware_set_by_code

    src = get_hardware_set_by_code(code)
    if src is None:
        raise OpeningsError("company hardware set not found", 404)
    items = []
    for it in sorted(src.items, key=lambda x: x.sort_order):
        items.append(
            {
                "seq": it.sort_order,
                "qty": float(it.default_qty or 1),
                "qty_unit": (it.unit or "ea").lower(),
                "category": "other",
                "description": it.label,
                "material_pricing_id": str(it.material_pricing_id) if it.material_pricing_id else None,
            }
        )
    return create_set(est, {"set_no": src.code, "title": src.name, "notes": src.description, "items": items}, cu)


def import_sets_csv(
    est: Estimate,
    set_rows: list[Mapping[str, Any]],
    item_rows: list[Mapping[str, Any]],
    cu=None,
) -> dict[str, Any]:
    created = 0
    for row in set_rows:
        if not isinstance(row, Mapping) or not _str(row.get("set_no"), 60):
            continue
        norm = normalize_set_no(str(row.get("set_no")))
        existing = db.session.scalar(
            select(HardwareSet).where(HardwareSet.estimate_id == est.id, HardwareSet.set_no_normalized == norm)
        )
        if existing is None:
            create_set(est, row, cu)
            created += 1
        else:
            patch_set(est, existing.id, row, cu)
    by_norm = sets_by_normalized(est.id)
    items_added = 0
    for row in item_rows:
        if not isinstance(row, Mapping):
            continue
        norm = normalize_set_no(_str(row.get("set_no"), 60) or "")
        hs = by_norm.get(norm)
        if hs is None:
            continue
        add_set_item(hs, row)
        items_added += 1
    db.session.flush()
    recompute_flags(est.id)
    _audit(cu, est.id, "hardware_set_import", {"sets": created, "items": items_added})
    return {"sets_created": created, "items_added": items_added}


def export_sets_csv(est: Estimate) -> tuple[str, str]:
    sets_buf = io.StringIO()
    items_buf = io.StringIO()
    sw = csv.DictWriter(sets_buf, fieldnames=list(SET_CSV_HEADERS))
    iw = csv.DictWriter(items_buf, fieldnames=list(ITEM_CSV_HEADERS))
    sw.writeheader()
    iw.writeheader()
    for hs in list_sets(est.id):
        sw.writerow(
            {
                "set_no": hs.set_no,
                "title": hs.title or "",
                "finish_default": hs.finish_default or "",
                "fire_required": "" if hs.fire_required is None else str(hs.fire_required).lower(),
                "pair_set": str(bool(hs.pair_set)).lower(),
                "electrified": str(bool(hs.electrified)).lower(),
                "notes": hs.notes or "",
            }
        )
        for it in sorted(hs.items, key=lambda x: x.seq):
            iw.writerow(
                {
                    "set_no": hs.set_no,
                    "seq": it.seq,
                    "qty": it.qty,
                    "qty_unit": it.qty_unit,
                    "category": it.category,
                    "description": it.description or "",
                    "manufacturer": it.manufacturer or "",
                    "catalog": it.catalog or "",
                    "function": it.function or "",
                    "finish": it.finish or "",
                    "size": it.size or "",
                    "notes": it.notes or "",
                }
            )
    return sets_buf.getvalue(), items_buf.getvalue()


def labor_defaults_for_estimate(est: Estimate) -> dict[str, float]:
    raw = est.labor_rates if isinstance(est.labor_rates, dict) else {}
    openings = raw.get("openings") if isinstance(raw.get("openings"), dict) else {}
    out: dict[str, float] = {}
    for key, seed in DEFAULT_OPENING_LABOR.items():
        val = openings.get(key, seed)
        try:
            out[key] = float(val)
        except (TypeError, ValueError):
            out[key] = float(seed)
    return out


def save_labor_defaults(est: Estimate, hours: Mapping[str, Any]) -> dict[str, float]:
    rates = dict(est.labor_rates) if isinstance(est.labor_rates, dict) else {}
    current = labor_defaults_for_estimate(est)
    for key in DEFAULT_OPENING_LABOR:
        if key in hours:
            current[key] = float(_dec(hours.get(key), Decimal(str(current[key]))) or 0)
    rates["openings"] = current
    est.labor_rates = rates
    return current


def _existing_frame(op: DoorOpening) -> bool:
    if (op.frame_material or "").lower() == "existing":
        return True
    remarks = (op.remarks or "").lower()
    return "e.t.r" in remarks or "existing to remain" in remarks or "etr" in remarks


def _in_scope_openings(estimate_id: uuid.UUID) -> list[DoorOpening]:
    return [op for op in list_openings(estimate_id) if (op.scope_flag or "in") == "in"]


def apply_blockers(estimate_id: uuid.UUID, *, door_frame_only: bool) -> list[str]:
    recon = recompute_flags(estimate_id)
    reasons: list[str] = []
    if recon["unconfirmed"]:
        reasons.append("unconfirmed extract rows on in-scope openings")
    if not door_frame_only and recon["missing_set"]:
        reasons.append("in-scope openings missing a hardware set")
    if not door_frame_only and recon["unknown_set"]:
        reasons.append("in-scope openings reference an unknown hardware set")
    return reasons


def _next_line_sort(estimate_id: uuid.UUID) -> int:
    m = db.session.scalar(
        select(func.coalesce(func.max(TakeoffLineItem.sort_order), -1)).where(
            TakeoffLineItem.estimate_id == estimate_id
        )
    )
    return int(m if m is not None else -1) + 1


def _opening_qty(op: DoorOpening) -> Decimal:
    return Decimal(op.qty or 1)


def _leaf_qty(op: DoorOpening) -> Decimal:
    return _opening_qty(op) * Decimal(op.leaf_count or 1)


def _hw_multiplier(op: DoorOpening, hs: HardwareSet) -> Decimal:
    return _opening_qty(op)


def _size_label(op: DoorOpening) -> str:
    w = op.width_in
    h = op.height_in
    if w is None and h is None:
        return (op.width or "") + ((" x " + op.height) if op.height else "")
    def _ft(inches: Decimal) -> str:
        whole = int(inches)
        feet = whole // 12
        rem = whole % 12
        return f"{feet}'-{rem}\""

    if w is not None and h is not None:
        return f"{_ft(Decimal(w))} × {_ft(Decimal(h))}"
    return f"{w or ''} × {h or ''}"


def _make_snapshot(
    *,
    line_role: str,
    manufacturer: str | None,
    catalog: str | None,
    description: str,
    attributes: dict[str, Any],
) -> dict[str, Any]:
    return {
        "configuratorKey": "opening_assembly",
        "schemaVersion": 1,
        "sourceKind": "opening",
        "lineRole": line_role,
        "manufacturer": manufacturer,
        "catalogNumber": catalog,
        "vendorDescription": description,
        "attributes": attributes,
    }


def _stable_key(parts: Iterable[Any]) -> str:
    return "|".join("" if p is None else str(p).strip().lower() for p in parts)


def plan_apply(
    est: Estimate,
    *,
    roll_up: bool = True,
    include_labor: bool = False,
    door_frame_only: bool = False,
    labor_hours: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    openings = _in_scope_openings(est.id)
    sets = sets_by_normalized(est.id)
    hours = labor_defaults_for_estimate(est)
    if labor_hours:
        for k, v in labor_hours.items():
            if k in hours:
                hours[k] = float(_dec(v, Decimal(str(hours[k]))) or 0)

    planned: list[dict[str, Any]] = []

    def add_or_merge(key: str, row: dict[str, Any]) -> None:
        if roll_up:
            for existing in planned:
                if existing.get("_key") == key:
                    existing["quantity"] = Decimal(existing["quantity"]) + Decimal(row["quantity"])
                    marks = list(existing["configuration"]["attributes"].get("openingMarks") or [])
                    for m in row["configuration"]["attributes"].get("openingMarks") or []:
                        if m not in marks:
                            marks.append(m)
                    existing["configuration"]["attributes"]["openingMarks"] = marks
                    existing["configuration"]["attributes"]["openingCount"] = len(marks)
                    return
        planned.append(row)

    for op in openings:
        marks = [op.mark]
        size = _size_label(op)
        door_desc = f"{op.material or 'door'} leaf {size} {op.door_type_code or ''} {op.fire_rating_min or 0} min".strip()
        door_key = _stable_key(
            ("door_leaf", op.material, op.width_in, op.height_in, op.fire_rating_min, op.door_type_code)
        )
        add_or_merge(
            door_key,
            {
                "_key": door_key,
                "line_role": "door_leaf",
                "section": "08 14" if (op.material or "") == "wood" else "08 11",
                "description": door_desc[:500],
                "quantity": _leaf_qty(op),
                "unit": "EA",
                "cost_type": "M",
                "unit_cost": Decimal("0"),
                "configuration": _make_snapshot(
                    line_role="door_leaf",
                    manufacturer=None,
                    catalog=op.door_type_code,
                    description=door_desc,
                    attributes={
                        "material": op.material,
                        "widthIn": float(op.width_in) if op.width_in is not None else None,
                        "heightIn": float(op.height_in) if op.height_in is not None else None,
                        "fireRatingMin": op.fire_rating_min,
                        "doorTypeCode": op.door_type_code,
                        "openingMarks": marks,
                        "openingCount": 1,
                    },
                ),
            },
        )
        if not _existing_frame(op):
            frame_desc = (
                f"{op.frame_material or 'hm'} frame {op.frame_construction or ''} {size} "
                f"ga {op.frame_gauge or ''} throat {op.wall_thickness_in or ''}"
            ).strip()
            frame_key = _stable_key(
                (
                    "frame",
                    op.frame_material,
                    op.frame_construction,
                    op.width_in,
                    op.height_in,
                    op.frame_gauge,
                    op.wall_thickness_in,
                )
            )
            add_or_merge(
                frame_key,
                {
                    "_key": frame_key,
                    "line_role": "frame",
                    "section": "08 12",
                    "description": frame_desc[:500],
                    "quantity": _opening_qty(op),
                    "unit": "EA",
                    "cost_type": "M",
                    "unit_cost": Decimal("0"),
                    "configuration": _make_snapshot(
                        line_role="frame",
                        manufacturer=None,
                        catalog=op.frame_type_code,
                        description=frame_desc,
                        attributes={
                            "material": op.frame_material,
                            "construction": op.frame_construction,
                            "frameGauge": op.frame_gauge,
                            "wallThicknessIn": float(op.wall_thickness_in) if op.wall_thickness_in is not None else None,
                            "openingMarks": marks,
                            "openingCount": 1,
                        },
                    ),
                },
            )
        if door_frame_only:
            continue
        hs = sets.get(normalize_set_no(opening_set_no(op)))
        if hs is None:
            continue
        has_exit = any((it.category or "") == "exit_device" for it in hs.items)
        has_closer = any((it.category or "") == "closer" for it in hs.items)
        for it in hs.items:
            desc = " ".join(
                x for x in (it.manufacturer, it.catalog, it.description or it.category) if x
            ).strip()
            finish = it.finish or hs.finish_default
            hw_key = _stable_key(("hardware_item", it.category, it.manufacturer, it.catalog, finish))
            qty = (it.qty or Decimal("0")) * _hw_multiplier(op, hs)
            add_or_merge(
                hw_key,
                {
                    "_key": hw_key,
                    "line_role": "hardware_item",
                    "section": "08 71",
                    "description": desc[:500] or (it.category or "hardware"),
                    "quantity": qty,
                    "unit": (it.qty_unit or "EA").upper(),
                    "cost_type": "M",
                    "unit_cost": Decimal("0"),
                    "configuration": _make_snapshot(
                        line_role="hardware_item",
                        manufacturer=it.manufacturer,
                        catalog=it.catalog,
                        description=desc,
                        attributes={
                            "category": it.category,
                            "hardwareSetNo": hs.set_no,
                            "finish": finish,
                            "openingMarks": marks,
                            "openingCount": 1,
                            "qtyPerOpening": float(it.qty or 0),
                            "fireRatingMin": op.fire_rating_min,
                        },
                    ),
                },
            )
        if include_labor:
            labor_rows: list[tuple[str, Decimal, str]] = []
            if not _existing_frame(op):
                if (op.frame_construction or "") == "welded":
                    labor_rows.append(("Frame welded HM", Decimal(str(hours["frame_welded_hm"])), "frame_welded_hm"))
                else:
                    labor_rows.append(("Frame KD HM", Decimal(str(hours["frame_kd_hm"])), "frame_kd_hm"))
            if has_exit:
                labor_rows.append(("Door + exit device", Decimal(str(hours["door_exit_device"])), "door_exit_device"))
            else:
                labor_rows.append(("Door + standard hardware", Decimal(str(hours["door_standard"])), "door_standard"))
            if has_closer:
                labor_rows.append(("Closer adjust", Decimal(str(hours["closer_adjust"])), "closer_adjust"))
            if int(op.fire_rating_min or 0) >= 20:
                labor_rows.append(("Rated assembly extra", Decimal(str(hours["rated_extra"])), "rated_extra"))
            for label, hrs, class_key in labor_rows:
                lkey = _stable_key(("labor", class_key))
                add_or_merge(
                    lkey,
                    {
                        "_key": lkey,
                        "line_role": "labor",
                        "section": "08 labor",
                        "description": label,
                        "quantity": hrs * _opening_qty(op),
                        "unit": "HR",
                        "cost_type": "L",
                        "unit_cost": Decimal("0"),
                        "configuration": _make_snapshot(
                            line_role="labor",
                            manufacturer=None,
                            catalog=class_key,
                            description=label,
                            attributes={"laborClass": class_key, "openingMarks": marks, "openingCount": 1},
                        ),
                    },
                )
    for row in planned:
        row.pop("_key", None)
        row["quantity"] = Decimal(row["quantity"])
    return planned


def apply_openings(
    est: Estimate,
    *,
    roll_up: bool = True,
    include_labor: bool = False,
    door_frame_only: bool = False,
    labor_hours: Mapping[str, Any] | None = None,
    preview: bool = False,
    cu=None,
) -> dict[str, Any]:
    reasons = apply_blockers(est.id, door_frame_only=door_frame_only)
    if reasons:
        raise OpeningsError("Apply blocked: " + "; ".join(reasons), 400)
    if labor_hours:
        save_labor_defaults(est, labor_hours)
    planned = plan_apply(
        est,
        roll_up=roll_up,
        include_labor=include_labor,
        door_frame_only=door_frame_only,
        labor_hours=labor_hours,
    )
    existing = list(
        db.session.scalars(
            select(TakeoffLineItem).where(
                TakeoffLineItem.estimate_id == est.id,
                TakeoffLineItem.source_kind == "opening",
            )
        ).all()
    )
    by_role_desc: dict[tuple[str, str], TakeoffLineItem] = {}
    for ln in existing:
        cfg = ln.configuration_json if isinstance(ln.configuration_json, dict) else {}
        role = (ln.line_role or cfg.get("lineRole") or "") + "|" + (ln.description or "")
        catalog = ""
        if isinstance(cfg, dict):
            catalog = str(cfg.get("catalogNumber") or "")
            cat = ""
            attrs = cfg.get("attributes") if isinstance(cfg.get("attributes"), dict) else {}
            cat = str(attrs.get("category") or attrs.get("laborClass") or "")
            role = f"{ln.line_role or cfg.get('lineRole')}|{cat}|{catalog}|{ln.description}"
        by_role_desc[role] = ln

    diffs: list[dict[str, Any]] = []
    used: set[uuid.UUID] = set()
    created = 0
    updated = 0
    sort = _next_line_sort(est.id)

    def match_key(row: dict[str, Any]) -> str:
        cfg = row["configuration"]
        attrs = cfg.get("attributes") or {}
        return f"{row['line_role']}|{attrs.get('category') or attrs.get('laborClass') or ''}|{cfg.get('catalogNumber') or ''}|{row['description']}"

    if preview:
        for row in planned:
            key = match_key(row)
            old = by_role_desc.get(key)
            diffs.append(
                {
                    "description": row["description"],
                    "line_role": row["line_role"],
                    "from_qty": float(old.quantity) if old is not None else None,
                    "to_qty": float(row["quantity"]),
                }
            )
        return {"preview": True, "diffs": diffs, "line_count": len(planned)}

    for row in planned:
        key = match_key(row)
        old = by_role_desc.get(key)
        qty = Decimal(row["quantity"])
        if old is not None:
            diffs.append(
                {
                    "description": row["description"],
                    "line_role": row["line_role"],
                    "from_qty": float(old.quantity or 0),
                    "to_qty": float(qty),
                }
            )
            old.quantity = qty
            old.description = row["description"][:500]
            old.section = row["section"]
            old.unit = row["unit"]
            old.line_role = row["line_role"]
            old.source_kind = "opening"
            old.configuration_json = row["configuration"]
            old.unit_cost = Decimal("0")
            old.extended_total = (qty * Decimal("0")).quantize(Decimal("0.01"))
            old.door_opening_id = None
            used.add(old.id)
            updated += 1
        else:
            ln = TakeoffLineItem(
                estimate_id=est.id,
                lead_estimate_id=est.lead_estimate_id,
                project_id=est.project_id,
                section=row["section"],
                sort_order=sort,
                description=row["description"][:500],
                quantity=qty,
                unit=row["unit"],
                unit_cost=Decimal("0"),
                extended_total=Decimal("0.00"),
                cost_type=row["cost_type"],
                line_role=row["line_role"],
                source_kind="opening",
                configuration_json=row["configuration"],
                door_opening_id=None,
            )
            db.session.add(ln)
            sort += 1
            created += 1
            diffs.append(
                {
                    "description": row["description"],
                    "line_role": row["line_role"],
                    "from_qty": None,
                    "to_qty": float(qty),
                }
            )
    stale = [ln for ln in existing if ln.id not in used]
    for ln in stale:
        db.session.delete(ln)
    db.session.flush()
    _audit(
        cu,
        est.id,
        "apply" if not existing else "reapply",
        {"created": created, "updated": updated, "removed": len(stale)},
    )
    return {
        "preview": False,
        "created": created,
        "updated": updated,
        "removed": len(stale),
        "diffs": diffs,
        "line_count": created + updated,
    }


def parse_extract_payload(data: Mapping[str, Any]) -> dict[str, Any]:
    warnings: list[str] = []
    openings: list[dict[str, Any]] = []
    sets: list[dict[str, Any]] = []
    if isinstance(data.get("openings"), list):
        openings = [x for x in data["openings"] if isinstance(x, Mapping)]
    if isinstance(data.get("sets"), list):
        sets = [x for x in data["sets"] if isinstance(x, Mapping)]
    if isinstance(data.get("warnings"), list):
        warnings = [str(x) for x in data["warnings"]]
    tsv = data.get("tsv") or data.get("pasted") or data.get("text")
    if tsv and not openings and not sets:
        openings, sets, extra = _parse_tsv(str(tsv), mode=str(data.get("mode") or ""))
        warnings.extend(extra)
    pages = data.get("pages") or data.get("page_range")
    page_count = 1
    if isinstance(pages, str) and "-" in pages:
        a, b = pages.split("-", 1)
        try:
            page_count = abs(int(b) - int(a)) + 1
        except ValueError:
            page_count = 1
    elif isinstance(pages, list):
        page_count = len(pages)
    if page_count > EXTRACT_MAX_PAGES:
        raise OpeningsError(f"Extract is capped at {EXTRACT_MAX_PAGES} pages per call")
    return {"openings": openings, "sets": sets, "warnings": warnings}


def _parse_tsv(text: str, *, mode: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    warnings: list[str] = []
    lines = [ln for ln in text.replace("\r\n", "\n").split("\n") if ln.strip()]
    if not lines:
        return [], [], ["empty TSV"]
    dialect = csv.Sniffer().sniff(lines[0], delimiters="\t,")
    reader = csv.DictReader(io.StringIO("\n".join(lines)), dialect=dialect)
    headers = [h.strip().lower() for h in (reader.fieldnames or [])]
    openings: list[dict[str, Any]] = []
    sets: list[dict[str, Any]] = []
    if mode == "hardware_set_extract" or "set_no" in headers and "category" in headers:
        grouped: dict[str, dict[str, Any]] = {}
        for row in reader:
            set_no = (row.get("set_no") or row.get("set") or "").strip()
            if not set_no:
                continue
            grouped.setdefault(set_no, {"set_no": set_no, "title": row.get("title") or "", "items": []})
            if row.get("category") or row.get("description"):
                grouped[set_no]["items"].append(
                    {
                        "qty": row.get("qty") or 1,
                        "category": row.get("category") or "other",
                        "description": row.get("description") or "",
                        "manufacturer": row.get("manufacturer") or "",
                        "catalog": row.get("catalog") or "",
                    }
                )
        sets = list(grouped.values())
    else:
        for row in reader:
            mark = (row.get("mark") or row.get("door") or row.get("door no") or "").strip()
            if not mark:
                continue
            openings.append(
                {
                    "mark": mark,
                    "width_in": row.get("width_in") or row.get("width"),
                    "height_in": row.get("height_in") or row.get("height"),
                    "hardware_set_no": row.get("hardware_set_no") or row.get("set") or row.get("hw"),
                    "hand": row.get("hand"),
                    "fire_rating_min": row.get("fire_rating_min") or row.get("rating"),
                    "material": row.get("material"),
                    "location": row.get("location") or row.get("room"),
                }
            )
    if "hand" not in headers and mode != "hardware_set_extract":
        warnings.append("column Hand missing on sheet")
    return openings, sets, warnings


def review_extract(est: Estimate, data: Mapping[str, Any]) -> dict[str, Any]:
    parsed = parse_extract_payload(data)
    return {
        "openings": parsed["openings"],
        "sets": parsed["sets"],
        "warnings": parsed["warnings"],
        "committed": False,
    }


def confirm_extract(est: Estimate, data: Mapping[str, Any], cu=None) -> dict[str, Any]:
    parsed = parse_extract_payload(data)
    mode = str(data.get("mode") or "")
    source = "ai_spec" if mode == "hardware_set_extract" else "ai_schedule"
    created_o = 0
    created_s = 0
    for row in parsed["openings"]:
        payload = dict(row)
        payload["source"] = source
        payload["confirmed_at"] = True
        create_opening(est, payload, cu)
        created_o += 1
    for row in parsed["sets"]:
        payload = dict(row)
        payload["confirmed"] = True
        create_set(est, payload, cu)
        created_s += 1
    for op in list_openings(est.id):
        if op.source in ("ai_schedule", "ai_spec") and op.confirmed_at is None:
            op.confirmed_at = _utcnow()
    for hs in list_sets(est.id):
        if hs.confirmed_at is None:
            hs.confirmed_at = _utcnow()
    db.session.flush()
    recompute_flags(est.id)
    _audit(cu, est.id, "extract_confirm", {"openings": created_o, "sets": created_s, "mode": mode})
    return {"committed": True, "openings_created": created_o, "sets_created": created_s}


def draft_rfps_from_openings(est: Estimate, cu=None, document_ids: list[str] | None = None) -> list[Rfp]:
    from ..api._rfp_body_service import attach_takeoff
    from ..api._rfp_quotes_service import new_mail_tag

    lines = list(
        db.session.scalars(
            select(TakeoffLineItem).where(
                TakeoffLineItem.estimate_id == est.id,
                TakeoffLineItem.source_kind == "opening",
            )
        ).all()
    )
    pkg_a = [ln for ln in lines if (ln.line_role or "") in ("door_leaf", "frame", "accessory")]
    pkg_b = [ln for ln in lines if (ln.line_role or "") == "hardware_item"]
    created: list[Rfp] = []

    def _make(title: str, chosen: list[TakeoffLineItem]) -> Rfp:
        r = Rfp(
            lead_estimate_id=est.lead_estimate_id,
            project_id=est.project_id,
            title=title[:500],
            public_token=secrets.token_urlsafe(32)[:64],
            mail_tag=new_mail_tag(),
            status="Draft",
            line_source="takeoff",
            source_estimate_id=est.id,
            show_line_table=True,
        )
        db.session.add(r)
        db.session.flush()
        if chosen:
            attach_takeoff(r, {"estimate_id": str(est.id), "takeoff_line_ids": [str(x.id) for x in chosen]})
        return r

    if pkg_a:
        created.append(_make("Doors & frames", pkg_a))
    if pkg_b:
        created.append(_make("Door hardware", pkg_b))
    if not created:
        raise OpeningsError("Apply openings to takeoff before drafting RFPs")
    _audit(cu, est.id, "draft_rfp", {"count": len(created), "titles": [r.title for r in created]})
    return created


def opening_sourced_lines(est: Estimate) -> list[TakeoffLineItem]:
    return list(
        db.session.scalars(
            select(TakeoffLineItem).where(
                TakeoffLineItem.estimate_id == est.id,
                TakeoffLineItem.source_kind == "opening",
            )
        ).all()
    )
