"""Vendor line cards, CSI buy-from channels, and RFP vendor matching."""
from __future__ import annotations

import uuid
from typing import Any, Iterable, Mapping

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from ..csi_catalog import list_catalog, title_for_code
from ..csi_spec import format_csi_display, normalize_csi_spec_section
from ..extensions import db
from ..models.company import Company
from ..models.material_pricing import MaterialPrice
from ..models.product_catalog import ManufacturerProductData
from ..models.vendor_line_card import BUY_FROM, CsiBuyChannel, SUPPLY_ROLES, VendorLineCard
from ._perms import CurrentUser
from ._rfi_service import ApiError
from ._wave2_service import _can_mutate, _can_view

_MFR_KEYS = ("manufacturer", "mfr", "brand", "supplierName", "supplier_name")


def _require_company(company_id: uuid.UUID) -> Company:
    row = db.session.get(Company, company_id)
    if row is None or row.deleted_at is not None:
        raise ApiError("company not found", 404)
    return row


def normalize_manufacturer(raw: str | None) -> str:
    return " ".join(str(raw or "").split())[:120]


def csi_family(digits: str) -> str:
    if len(digits) != 6:
        return digits
    return digits[:4] + "00"


def csi_covers(listed: str, needed: str) -> bool:
    if not listed or not needed or len(listed) != 6 or len(needed) != 6:
        return False
    if listed == needed:
        return True
    if listed[4:6] == "00" and listed[:4] == needed[:4]:
        return True
    if needed[4:6] == "00" and needed[:4] == listed[:4]:
        return True
    return False


def parse_csi(raw: str | None) -> str:
    digits = normalize_csi_spec_section(raw)
    if not digits:
        raise ApiError("csi_spec_section is required (e.g. 10 21 00)", 400)
    return digits


def parse_supply_role(raw: Any) -> str | None:
    if raw in (None, ""):
        return None
    val = str(raw).strip().lower()
    if val in ("unset", "none", "null"):
        return None
    if val not in SUPPLY_ROLES:
        raise ApiError("supply_role must be manufacturer, distributor, or both", 400)
    return val


def parse_buy_from(raw: Any) -> str:
    val = str(raw or "").strip().lower()
    if val in ("vendor", "vendors", "dealer", "distributors"):
        val = "distributor"
    if val in ("mfr", "mfg", "direct"):
        val = "manufacturer"
    if val not in BUY_FROM:
        raise ApiError("buy_from must be manufacturer or distributor", 400)
    return val


def buy_from_for(csi: str, channels: Mapping[str, str]) -> str | None:
    if csi in channels:
        return channels[csi]
    family = csi_family(csi)
    if family in channels:
        return channels[family]
    return None


def role_fits(supply_role: str | None, buy_from: str | None) -> bool:
    if not buy_from:
        return True
    if not supply_role or supply_role == "both":
        return True
    return supply_role == buy_from


def _mfr_from_snapshot(snap: Any) -> str | None:
    if not isinstance(snap, dict):
        return None
    for key in _MFR_KEYS:
        val = snap.get(key)
        if val not in (None, ""):
            name = normalize_manufacturer(str(val))
            if name:
                return name
    return None


def rfp_needs(lines: Iterable[Any]) -> list[dict[str, str | None]]:
    needs: list[dict[str, str | None]] = []
    seen: set[tuple[str, str]] = set()
    for ln in lines:
        csi = normalize_csi_spec_section(getattr(ln, "csi_division", None))
        if not csi:
            continue
        mfr = _mfr_from_snapshot(getattr(ln, "product_snapshot", None))
        key = (csi, (mfr or "").lower())
        if key in seen:
            continue
        seen.add(key)
        needs.append({"csi": csi, "manufacturer": mfr})
    return needs


def match_line_card(
    *,
    supply_role: str | None,
    cards: Iterable[tuple[str, str]],
    needs: Iterable[Mapping[str, str | None]],
    channels: Mapping[str, str],
) -> dict[str, Any]:
    card_list = [(c, m) for c, m in cards]
    reasons: list[str] = []
    score = 0
    matched_needs = 0
    for need in needs:
        csi = str(need.get("csi") or "")
        if len(csi) != 6:
            continue
        buy_from = buy_from_for(csi, channels)
        if not role_fits(supply_role, buy_from):
            continue
        covering = [(c, m) for c, m in card_list if csi_covers(c, csi)]
        if not covering:
            continue
        brands = {m for _, m in covering if m}
        unspecified = any(not m for _, m in covering)
        need_mfr = normalize_manufacturer(need.get("manufacturer"))
        if need_mfr and brands and not unspecified:
            if not any(need_mfr.lower() == b.lower() for b in brands):
                continue
        matched_needs += 1
        score += 10
        disp = format_csi_display(csi) or csi
        if need_mfr:
            reasons.append(f"{disp} · {need_mfr}")
            score += 5
        elif brands:
            reasons.append(f"{disp} · " + ", ".join(sorted(brands, key=str.lower)))
        else:
            reasons.append(disp)
    return {
        "matched": matched_needs > 0,
        "match_score": score,
        "match_reason": "; ".join(reasons[:4]) if reasons else None,
        "matched_need_count": matched_needs,
    }


def load_channels() -> dict[str, str]:
    rows = db.session.scalars(select(CsiBuyChannel)).all()
    return {r.csi_spec_section: r.buy_from for r in rows}


def load_cards_by_company(company_ids: Iterable[uuid.UUID]) -> dict[uuid.UUID, list[tuple[str, str]]]:
    ids = list(company_ids)
    out: dict[uuid.UUID, list[tuple[str, str]]] = {i: [] for i in ids}
    if not ids:
        return out
    rows = db.session.scalars(select(VendorLineCard).where(VendorLineCard.company_id.in_(ids))).all()
    for row in rows:
        out.setdefault(row.company_id, []).append((row.csi_spec_section, row.manufacturer or ""))
    return out


def _card_public(row: VendorLineCard) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "company_id": str(row.company_id),
        "csi_spec_section": row.csi_spec_section,
        "csi_display": format_csi_display(row.csi_spec_section),
        "csi_title": title_for_code(row.csi_spec_section),
        "manufacturer": row.manufacturer or None,
    }


def _grouped_cards(rows: list[VendorLineCard]) -> list[dict[str, Any]]:
    groups: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for row in rows:
        csi = row.csi_spec_section
        if csi not in groups:
            order.append(csi)
            groups[csi] = {
                "csi_spec_section": csi,
                "csi_display": format_csi_display(csi),
                "csi_title": title_for_code(csi),
                "manufacturers": [],
            }
        if row.manufacturer:
            groups[csi]["manufacturers"].append(_card_public(row))
    return [groups[k] for k in order]


def list_line_card(company_id: uuid.UUID, cu: CurrentUser) -> dict[str, Any]:
    if not _can_view(cu):
        raise ApiError("forbidden", 403)
    company = _require_company(company_id)
    rows = list(
        db.session.scalars(
            select(VendorLineCard)
            .where(VendorLineCard.company_id == company_id)
            .order_by(VendorLineCard.csi_spec_section, VendorLineCard.manufacturer)
        ).all()
    )
    return {
        "entity": "vendor_line_card",
        "company_id": str(company.id),
        "supply_role": company.supply_role,
        "items": [_card_public(r) for r in rows],
        "specs": _grouped_cards(rows),
    }


def add_line_card(company_id: uuid.UUID, data: Mapping[str, Any], cu: CurrentUser) -> dict[str, Any]:
    if not _can_mutate(cu):
        raise ApiError("forbidden", 403)
    _require_company(company_id)
    csi = parse_csi(data.get("csi_spec_section") or data.get("csi"))
    manufacturers: list[str] = []
    raw_list = data.get("manufacturers")
    if isinstance(raw_list, list):
        manufacturers = [normalize_manufacturer(x) for x in raw_list if normalize_manufacturer(str(x or ""))]
    single = normalize_manufacturer(data.get("manufacturer"))
    if single:
        manufacturers.append(single)
    manufacturers = list(dict.fromkeys(manufacturers))

    existing = list(
        db.session.scalars(
            select(VendorLineCard).where(
                VendorLineCard.company_id == company_id,
                VendorLineCard.csi_spec_section == csi,
            )
        ).all()
    )
    if manufacturers:
        for blank in [r for r in existing if not r.manufacturer]:
            db.session.delete(blank)
        have = {(r.manufacturer or "").lower() for r in existing if r.manufacturer}
        for name in manufacturers:
            if name.lower() in have:
                continue
            db.session.add(VendorLineCard(company_id=company_id, csi_spec_section=csi, manufacturer=name))
            have.add(name.lower())
    elif not existing:
        db.session.add(VendorLineCard(company_id=company_id, csi_spec_section=csi, manufacturer=""))
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise ApiError("that spec and manufacturer is already on this line card", 409)
    return list_line_card(company_id, cu)


def delete_line_card_row(company_id: uuid.UUID, row_id: uuid.UUID, cu: CurrentUser) -> dict[str, Any]:
    if not _can_mutate(cu):
        raise ApiError("forbidden", 403)
    _require_company(company_id)
    row = db.session.get(VendorLineCard, row_id)
    if row is None or row.company_id != company_id:
        raise ApiError("not found", 404)
    db.session.delete(row)
    db.session.commit()
    return list_line_card(company_id, cu)


def delete_line_card_spec(company_id: uuid.UUID, csi_raw: str, cu: CurrentUser) -> dict[str, Any]:
    if not _can_mutate(cu):
        raise ApiError("forbidden", 403)
    _require_company(company_id)
    csi = parse_csi(csi_raw)
    rows = list(
        db.session.scalars(
            select(VendorLineCard).where(
                VendorLineCard.company_id == company_id,
                VendorLineCard.csi_spec_section == csi,
            )
        ).all()
    )
    for row in rows:
        db.session.delete(row)
    db.session.commit()
    return list_line_card(company_id, cu)


def list_buy_channels(cu: CurrentUser) -> dict[str, Any]:
    if not _can_view(cu):
        raise ApiError("forbidden", 403)
    rows = db.session.scalars(select(CsiBuyChannel).order_by(CsiBuyChannel.csi_spec_section)).all()
    items = []
    for r in rows:
        items.append(
            {
                "id": str(r.id),
                "csi_spec_section": r.csi_spec_section,
                "csi_display": format_csi_display(r.csi_spec_section),
                "csi_title": title_for_code(r.csi_spec_section),
                "buy_from": r.buy_from,
            }
        )
    return {"entity": "csi_buy_channels", "items": items}


def upsert_buy_channel(data: Mapping[str, Any], cu: CurrentUser) -> dict[str, Any]:
    if not _can_mutate(cu):
        raise ApiError("forbidden", 403)
    csi = parse_csi(data.get("csi_spec_section") or data.get("csi"))
    buy_from = parse_buy_from(data.get("buy_from"))
    row = db.session.scalar(select(CsiBuyChannel).where(CsiBuyChannel.csi_spec_section == csi))
    if row is None:
        row = CsiBuyChannel(csi_spec_section=csi, buy_from=buy_from)
        db.session.add(row)
    else:
        row.buy_from = buy_from
    db.session.commit()
    return list_buy_channels(cu)


def delete_buy_channel(csi_raw: str, cu: CurrentUser) -> dict[str, Any]:
    if not _can_mutate(cu):
        raise ApiError("forbidden", 403)
    csi = parse_csi(csi_raw)
    row = db.session.scalar(select(CsiBuyChannel).where(CsiBuyChannel.csi_spec_section == csi))
    if row is None:
        raise ApiError("not found", 404)
    db.session.delete(row)
    db.session.commit()
    return list_buy_channels(cu)


def line_card_options(cu: CurrentUser) -> dict[str, Any]:
    if not _can_view(cu):
        raise ApiError("forbidden", 403)
    sections = list_catalog(None, 5000)
    mfrs = set(db.session.scalars(select(MaterialPrice.manufacturer).distinct()).all())
    mfrs.update(db.session.scalars(select(ManufacturerProductData.manufacturer).distinct()).all())
    names = sorted({normalize_manufacturer(x) for x in mfrs if normalize_manufacturer(x)}, key=str.lower)
    return {
        "entity": "vendor_line_card_options",
        "csi_sections": sections,
        "manufacturers": names,
        "supply_roles": list(SUPPLY_ROLES),
        "buy_from": list(BUY_FROM),
    }
