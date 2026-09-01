"""HTTP routes for vendor line cards and CSI buy paths."""
from __future__ import annotations

import uuid

from flask import Blueprint, jsonify, request

from ._perms import current_user
from ._rfi_service import ApiError
from . import _vendor_line_card as vlc
from . import _wave2_service as wave2_svc
from . import _rfp_body_service as rfp_body


def _jsonify(obj):
    return jsonify(obj)


def _parse_uuid_param(raw: str | None):
    if not raw:
        return None
    try:
        return uuid.UUID(str(raw).strip())
    except ValueError:
        return None


def _err(exc: ApiError):
    return _jsonify({"error": exc.message}), exc.status


def _enhanced_vendor_directory(rfp, *, q: str = "", trade: str = "", suggested: bool = False):
    from flask import has_request_context

    if has_request_context() and not suggested:
        suggested = (request.args.get("suggested") or "").strip().lower() in ("1", "true", "yes")
    return _vendor_directory_impl(rfp, q=q, trade=trade, suggested=suggested)


def _vendor_directory_impl(rfp, *, q: str = "", trade: str = "", suggested: bool = False):
    from sqlalchemy import select

    from ..extensions import db
    from ..models.company import Company, Contact
    from ..models.vendor_line_card import VendorLineCard

    types = tuple(t for t in rfp_body.VENDOR_COMPANY_TYPES if t in ("vendor", "subcontractor", "other"))
    needle = (q or "").strip()
    stmt = select(Company).where(Company.deleted_at.is_(None), Company.company_type.in_(types))
    if needle:
        stmt = stmt.where(Company.name.ilike(f"%{needle}%"))
    if suggested:
        stmt = stmt.where(Company.id.in_(select(VendorLineCard.company_id).distinct()))
    stmt = stmt.order_by(Company.name.asc()).limit(500 if needle or suggested else 400)
    rows = list(db.session.scalars(stmt).all())
    trade_n = (trade or "").strip().lower()
    needs = vlc.rfp_needs(rfp_body.all_line_items(rfp))
    channels = vlc.load_channels()
    cards_by = vlc.load_cards_by_company([c.id for c in rows])
    out = []
    for c in rows:
        if needle and needle.lower() not in (c.name or "").lower():
            continue
        specialties = c.trade_specialties
        trade_blob = ""
        if isinstance(specialties, dict):
            trade_blob = " ".join(str(v) for v in specialties.values()).lower()
        elif isinstance(specialties, list):
            trade_blob = " ".join(str(v) for v in specialties).lower()
        elif specialties:
            trade_blob = str(specialties).lower()
        if trade_n and trade_blob and trade_n not in trade_blob and trade_n not in (c.name or "").lower():
            continue
        match = vlc.match_line_card(
            supply_role=getattr(c, "supply_role", None),
            cards=cards_by.get(c.id) or [],
            needs=needs,
            channels=channels,
        )
        if suggested and needs and not match["matched"]:
            continue
        contacts = list(
            db.session.scalars(
                select(Contact).where(Contact.company_id == c.id).order_by(Contact.is_primary.desc())
            ).all()
        )
        email = (getattr(c, "quote_email", None) or "").strip() or (c.email or "").strip()
        primary = next((ct for ct in contacts if ct.is_primary and (ct.email or "").strip()), None)
        if primary is not None:
            email = (primary.email or email).strip()
        if not email:
            with_email = next((ct for ct in contacts if (ct.email or "").strip()), None)
            if with_email is not None:
                email = (with_email.email or "").strip()
        out.append(
            {
                "id": str(c.id),
                "name": c.name,
                "company_type": c.company_type,
                "supply_role": getattr(c, "supply_role", None),
                "email": email or None,
                "missing_email": not bool(email),
                "company_edit_url": f"usis-companies.html?id={c.id}",
                "trade_specialties": specialties,
                "matched": match["matched"],
                "match_score": match["match_score"],
                "match_reason": match["match_reason"],
                "contacts": [
                    {
                        "id": str(ct.id),
                        "name": " ".join(p for p in (ct.first_name or "", ct.last_name or "") if p).strip() or c.name,
                        "email": (ct.email or "").strip() or None,
                        "title": ct.title,
                        "is_primary": bool(ct.is_primary),
                    }
                    for ct in contacts
                ],
            }
        )
    out.sort(key=lambda x: (-int(x.get("match_score") or 0), (x.get("name") or "").lower()))
    return out


def _wrap_company_writes() -> None:
    orig_create = wave2_svc.create_company
    orig_patch = wave2_svc.patch_company
    orig_public = wave2_svc._company_public

    def _public(c):
        d = orig_public(c)
        d["supply_role"] = getattr(c, "supply_role", None)
        return d

    def _create(data, cu):
        item = orig_create(data, cu)
        if "supply_role" in data:
            from ..extensions import db
            from ..models.company import Company

            cid = uuid.UUID(item["item"]["id"])
            row = db.session.get(Company, cid)
            if row is not None:
                row.supply_role = vlc.parse_supply_role(data.get("supply_role"))
                db.session.commit()
                item["item"] = _public(row)
        else:
            item["item"]["supply_role"] = item["item"].get("supply_role")
        return item

    def _patch(company_id, data, cu):
        item = orig_patch(company_id, data, cu)
        if "supply_role" in data:
            from ..extensions import db
            from ..models.company import Company

            row = db.session.get(Company, company_id)
            if row is not None:
                row.supply_role = vlc.parse_supply_role(data.get("supply_role"))
                db.session.commit()
                item["item"] = _public(row)
        return item

    wave2_svc._company_public = _public
    wave2_svc.create_company = _create
    wave2_svc.patch_company = _patch


def register_vendor_line_card_routes(bp: Blueprint) -> None:
    _wrap_company_writes()
    rfp_body.vendor_directory = _enhanced_vendor_directory

    @bp.get("/csi-buy-channels")
    def list_csi_buy_channels():
        try:
            return _jsonify(vlc.list_buy_channels(current_user()))
        except ApiError as exc:
            return _err(exc)

    @bp.post("/csi-buy-channels")
    def upsert_csi_buy_channel():
        try:
            return _jsonify(vlc.upsert_buy_channel(request.get_json(silent=True) or {}, current_user()))
        except ApiError as exc:
            return _err(exc)

    @bp.delete("/csi-buy-channels/<csi>")
    def delete_csi_buy_channel(csi: str):
        try:
            return _jsonify(vlc.delete_buy_channel(csi, current_user()))
        except ApiError as exc:
            return _err(exc)

    @bp.get("/companies/line-card-options")
    def company_line_card_options():
        try:
            return _jsonify(vlc.line_card_options(current_user()))
        except ApiError as exc:
            return _err(exc)

    @bp.get("/companies/<company_id>/line-card")
    def list_company_line_card(company_id: str):
        cid = _parse_uuid_param(company_id)
        if not cid:
            return _jsonify({"error": "invalid company id"}), 400
        try:
            return _jsonify(vlc.list_line_card(cid, current_user()))
        except ApiError as exc:
            return _err(exc)

    @bp.post("/companies/<company_id>/line-card")
    def add_company_line_card(company_id: str):
        cid = _parse_uuid_param(company_id)
        if not cid:
            return _jsonify({"error": "invalid company id"}), 400
        try:
            return _jsonify(vlc.add_line_card(cid, request.get_json(silent=True) or {}, current_user())), 201
        except ApiError as exc:
            return _err(exc)

    @bp.delete("/companies/<company_id>/line-card/<row_id>")
    def delete_company_line_card_row(company_id: str, row_id: str):
        cid = _parse_uuid_param(company_id)
        rid = _parse_uuid_param(row_id)
        if not cid or not rid:
            return _jsonify({"error": "invalid id"}), 400
        try:
            return _jsonify(vlc.delete_line_card_row(cid, rid, current_user()))
        except ApiError as exc:
            return _err(exc)

    @bp.delete("/companies/<company_id>/line-card/specs/<csi>")
    def delete_company_line_card_spec(company_id: str, csi: str):
        cid = _parse_uuid_param(company_id)
        if not cid:
            return _jsonify({"error": "invalid company id"}), 400
        try:
            return _jsonify(vlc.delete_line_card_spec(cid, csi, current_user()))
        except ApiError as exc:
            return _err(exc)
