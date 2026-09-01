"""HTTP routes for estimating spec-package automation."""
from __future__ import annotations

from typing import Mapping

from flask import Blueprint, request

from ..extensions import db
from ..models import SpecTradeMap
from ._estimate_spec_package import (
    analyze_estimate,
    apply_model_output,
    confirm_products,
    confirm_sections,
    create_draft_rfps,
    ensure_trade_map,
    get_scan_payload,
    grok_allowed,
    latest_scan,
    patch_mentions,
    patch_sections,
    patch_vendors,
    suggest_vendors,
)
from ._perms import current_user
from ._rfi_service import ApiError
from .v1 import _jsonify, _parse_uuid_param


def _load_est(estimate_id: str):
    from ._estimate_spec_package import _load_estimate

    eid = _parse_uuid_param(estimate_id)
    if not eid:
        raise ApiError("invalid estimate id", 400)
    return _load_estimate(eid)


def register_estimate_spec_routes(bp: Blueprint) -> None:
    @bp.get("/spec-trade-map")
    def list_spec_trade_map():
        rows = ensure_trade_map()
        return _jsonify(
            {
                "entity": "spec_trade_map",
                "items": [
                    {
                        "id": str(r.id),
                        "csi_prefix": r.csi_prefix,
                        "trade_label": r.trade_label,
                        "enabled": bool(r.enabled),
                        "default_in_scope": bool(r.default_in_scope),
                        "sort_order": r.sort_order,
                    }
                    for r in rows
                ],
            }
        )

    @bp.patch("/spec-trade-map/<row_id>")
    def patch_spec_trade_map(row_id: str):
        cu = current_user()
        if not (cu.is_dev_admin or cu.has_role("admin", "superuser")):
            return _jsonify({"error": "not allowed to amend trade map"}), 403
        rid = _parse_uuid_param(row_id)
        if not rid:
            return _jsonify({"error": "invalid id"}), 400
        row = db.session.get(SpecTradeMap, rid)
        if row is None:
            return _jsonify({"error": "not found"}), 404
        data = request.get_json(silent=True)
        if not isinstance(data, Mapping):
            return _jsonify({"error": "expected JSON object body"}), 400
        if "enabled" in data:
            row.enabled = bool(data.get("enabled"))
        if "default_in_scope" in data:
            row.default_in_scope = bool(data.get("default_in_scope"))
        if "trade_label" in data:
            row.trade_label = str(data.get("trade_label") or row.trade_label)[:200]
        db.session.commit()
        return _jsonify({"item": {"id": str(row.id), "csi_prefix": row.csi_prefix, "enabled": row.enabled}})

    @bp.get("/estimates/<estimate_id>/spec-scan")
    def get_estimate_spec_scan(estimate_id: str):
        try:
            est = _load_est(estimate_id)
        except ApiError as exc:
            return _jsonify({"error": exc.message}), exc.status
        show = str(request.args.get("show_out_of_trade") or "").strip() in ("1", "true", "yes")
        payload = get_scan_payload(est, show_out_of_trade=show)
        payload["entity"] = "estimate_spec_scan"
        payload["grok_allowed"] = grok_allowed(est.project_id or (est.lead_estimate.project_id if est.lead_estimate else None))
        return _jsonify(payload)

    @bp.post("/estimates/<estimate_id>/spec-scan/analyze")
    def analyze_estimate_spec_scan(estimate_id: str):
        cu = current_user()
        data = request.get_json(silent=True)
        if not isinstance(data, Mapping):
            data = {}
        try:
            est = _load_est(estimate_id)
            provider = str(data.get("provider") or "llama4-scout").strip() or "llama4-scout"
            if provider == "grok" and not grok_allowed(
                est.project_id or (est.lead_estimate.project_id if est.lead_estimate else None)
            ):
                provider = "llama4-scout"
            scan = analyze_estimate(
                est,
                cu=cu,
                provider=provider,
                text=(str(data.get("text") or "").strip() or None),
                model_output=data.get("model_output") or data.get("output"),
            )
            db.session.commit()
        except ApiError as exc:
            db.session.rollback()
            return _jsonify({"error": exc.message}), exc.status
        show = bool(data.get("show_out_of_trade"))
        payload = get_scan_payload(est, show_out_of_trade=show)
        payload["entity"] = "estimate_spec_scan"
        return _jsonify(payload)

    @bp.post("/estimates/<estimate_id>/spec-scan/apply-model")
    def apply_estimate_spec_model(estimate_id: str):
        cu = current_user()
        data = request.get_json(silent=True)
        if not isinstance(data, Mapping):
            return _jsonify({"error": "expected JSON object body"}), 400
        try:
            est = _load_est(estimate_id)
            scan = latest_scan(est.id)
            if scan is None:
                scan = analyze_estimate(est, cu=cu, model_output=data)
            else:
                apply_model_output(scan, data.get("output") or data, cu=cu)
            db.session.commit()
        except ApiError as exc:
            db.session.rollback()
            return _jsonify({"error": exc.message}), exc.status
        payload = get_scan_payload(est, show_out_of_trade=bool(data.get("show_out_of_trade")))
        payload["entity"] = "estimate_spec_scan"
        return _jsonify(payload)

    @bp.patch("/estimates/<estimate_id>/spec-scan/sections")
    def patch_estimate_spec_sections(estimate_id: str):
        data = request.get_json(silent=True)
        if not isinstance(data, Mapping):
            return _jsonify({"error": "expected JSON object body"}), 400
        items = data.get("items") or data.get("sections") or []
        if not isinstance(items, list):
            return _jsonify({"error": "items must be a list"}), 400
        try:
            est = _load_est(estimate_id)
            scan = latest_scan(est.id)
            if scan is None:
                raise ApiError("no scan yet — analyze specs first", 404)
            patch_sections(scan, items)
            db.session.commit()
        except ApiError as exc:
            db.session.rollback()
            return _jsonify({"error": exc.message}), exc.status
        return _jsonify(get_scan_payload(est, show_out_of_trade=bool(data.get("show_out_of_trade"))) | {"entity": "estimate_spec_scan"})

    @bp.post("/estimates/<estimate_id>/spec-scan/confirm-sections")
    def confirm_estimate_spec_sections(estimate_id: str):
        cu = current_user()
        data = request.get_json(silent=True)
        if not isinstance(data, Mapping):
            data = {}
        try:
            est = _load_est(estimate_id)
            scan = latest_scan(est.id)
            if scan is None:
                raise ApiError("no scan yet — analyze specs first", 404)
            if isinstance(data.get("items") or data.get("sections"), list):
                patch_sections(scan, list(data.get("items") or data.get("sections") or []))
            confirm_sections(scan, cu=cu)
            db.session.commit()
        except ApiError as exc:
            db.session.rollback()
            return _jsonify({"error": exc.message}), exc.status
        return _jsonify(get_scan_payload(est, show_out_of_trade=bool(data.get("show_out_of_trade"))) | {"entity": "estimate_spec_scan"})

    @bp.patch("/estimates/<estimate_id>/spec-scan/mentions")
    def patch_estimate_spec_mentions(estimate_id: str):
        data = request.get_json(silent=True)
        if not isinstance(data, Mapping):
            return _jsonify({"error": "expected JSON object body"}), 400
        items = data.get("items") or data.get("mentions") or []
        if not isinstance(items, list):
            return _jsonify({"error": "items must be a list"}), 400
        try:
            est = _load_est(estimate_id)
            scan = latest_scan(est.id)
            if scan is None:
                raise ApiError("no scan yet", 404)
            patch_mentions(scan, items)
            db.session.commit()
        except ApiError as exc:
            db.session.rollback()
            return _jsonify({"error": exc.message}), exc.status
        return _jsonify(get_scan_payload(est, show_out_of_trade=bool(data.get("show_out_of_trade"))) | {"entity": "estimate_spec_scan"})

    @bp.post("/estimates/<estimate_id>/spec-scan/confirm-products")
    def confirm_estimate_spec_products(estimate_id: str):
        cu = current_user()
        data = request.get_json(silent=True)
        if not isinstance(data, Mapping):
            data = {}
        try:
            est = _load_est(estimate_id)
            scan = latest_scan(est.id)
            if scan is None:
                raise ApiError("no scan yet", 404)
            if isinstance(data.get("items"), list):
                patch_mentions(scan, list(data.get("items") or []))
            confirm_products(scan, cu=cu)
            db.session.commit()
        except ApiError as exc:
            db.session.rollback()
            return _jsonify({"error": exc.message}), exc.status
        return _jsonify(get_scan_payload(est, show_out_of_trade=bool(data.get("show_out_of_trade"))) | {"entity": "estimate_spec_scan"})

    @bp.post("/estimates/<estimate_id>/spec-scan/suggest-vendors")
    def suggest_estimate_spec_vendors(estimate_id: str):
        try:
            est = _load_est(estimate_id)
            scan = latest_scan(est.id)
            if scan is None:
                raise ApiError("no scan yet", 404)
            suggest_vendors(scan)
            db.session.commit()
        except ApiError as exc:
            db.session.rollback()
            return _jsonify({"error": exc.message}), exc.status
        return _jsonify(get_scan_payload(est) | {"entity": "estimate_spec_scan"})

    @bp.patch("/estimates/<estimate_id>/spec-scan/vendors")
    def patch_estimate_spec_vendors(estimate_id: str):
        data = request.get_json(silent=True)
        if not isinstance(data, Mapping):
            return _jsonify({"error": "expected JSON object body"}), 400
        items = data.get("items") or data.get("vendors") or []
        if not isinstance(items, list):
            return _jsonify({"error": "items must be a list"}), 400
        try:
            est = _load_est(estimate_id)
            scan = latest_scan(est.id)
            if scan is None:
                raise ApiError("no scan yet", 404)
            patch_vendors(scan, items)
            db.session.commit()
        except ApiError as exc:
            db.session.rollback()
            return _jsonify({"error": exc.message}), exc.status
        return _jsonify(get_scan_payload(est) | {"entity": "estimate_spec_scan"})

    @bp.post("/estimates/<estimate_id>/spec-scan/draft-rfps")
    def draft_estimate_spec_rfps(estimate_id: str):
        cu = current_user()
        data = request.get_json(silent=True)
        if not isinstance(data, Mapping):
            data = {}
        try:
            est = _load_est(estimate_id)
            scan = latest_scan(est.id)
            if scan is None:
                raise ApiError("no scan yet", 404)
            if isinstance(data.get("vendors"), list):
                patch_vendors(scan, list(data.get("vendors") or []))
            rfps = create_draft_rfps(
                scan,
                cu=cu,
                grouping=str(data.get("grouping") or "per_vendor"),
                takeoff_line_ids=list(data.get("takeoff_line_ids") or [])
                if isinstance(data.get("takeoff_line_ids"), list)
                else None,
            )
            db.session.commit()
        except ApiError as exc:
            db.session.rollback()
            return _jsonify({"error": exc.message}), exc.status
        payload = get_scan_payload(est)
        payload["entity"] = "estimate_spec_scan"
        payload["rfps"] = [{"id": str(r.id), "title": r.title, "status": r.status} for r in rfps]
        return _jsonify(payload), 201
