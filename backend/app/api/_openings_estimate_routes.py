"""Estimate-scoped openings (door / frame / hardware) workspace."""
from __future__ import annotations

from flask import Blueprint, Response, request

from ..extensions import db
from ..services.openings_estimate import (
    OpeningsError,
    add_set_item,
    apply_openings,
    bulk_openings,
    confirm_extract,
    confirm_opening,
    copy_from_company,
    copy_set,
    create_opening,
    create_set,
    delete_opening,
    delete_set,
    delete_set_item,
    dismiss_flag,
    draft_rfps_from_openings,
    duplicate_opening,
    empty_reconcile,
    export_openings_csv,
    export_sets_csv,
    import_openings_csv,
    import_sets_csv,
    item_public,
    load_estimate,
    openings_bundle,
    opening_public,
    patch_opening,
    patch_set,
    patch_set_item,
    recompute_flags,
    review_extract,
    save_labor_defaults,
    set_public,
)
from ._perms import current_user
from ._rfi_service import ApiError
from .v1 import _jsonify, _parse_uuid_param


def _err(exc: Exception):
    status = getattr(exc, "status", 400)
    return _jsonify({"error": getattr(exc, "message", str(exc))}), status


def _est(estimate_id: str):
    eid = _parse_uuid_param(estimate_id)
    if not eid:
        raise OpeningsError("invalid estimate id", 400)
    return load_estimate(eid)


def register_openings_estimate_routes(bp: Blueprint) -> None:
    @bp.get("/estimates/<estimate_id>/openings")
    def list_estimate_openings(estimate_id: str):
        try:
            est = _est(estimate_id)
        except (OpeningsError, ApiError) as exc:
            return _err(exc)
        try:
            return _jsonify(openings_bundle(est.id))
        except Exception:
            return _jsonify(
                {
                    "openings": [],
                    "sets": [],
                    "types": [],
                    "reconcile": empty_reconcile(),
                }
            )

    @bp.get("/estimates/<estimate_id>/openings/reconcile")
    def get_openings_reconcile(estimate_id: str):
        try:
            est = _est(estimate_id)
            return _jsonify({"reconcile": recompute_flags(est.id)})
        except (OpeningsError, ApiError) as exc:
            return _err(exc)

    @bp.get("/estimates/<estimate_id>/openings/export")
    def export_estimate_openings(estimate_id: str):
        try:
            est = _est(estimate_id)
            csv_text = export_openings_csv(est)
        except (OpeningsError, ApiError) as exc:
            return _err(exc)
        return Response(csv_text, mimetype="text/csv")

    @bp.post("/estimates/<estimate_id>/openings/import")
    def import_estimate_openings(estimate_id: str):
        try:
            est = _est(estimate_id)
            data = request.get_json(silent=True) or {}
            rows = data.get("rows") or []
            if not isinstance(rows, list):
                return _jsonify({"error": "rows must be a list"}), 400
            summary = import_openings_csv(est, rows, source=str(data.get("source") or "csv"), cu=current_user())
            db.session.commit()
            bundle = openings_bundle(est.id)
            bundle.update(summary)
            return _jsonify(bundle), 201
        except (OpeningsError, ApiError) as exc:
            db.session.rollback()
            return _err(exc)

    @bp.post("/estimates/<estimate_id>/openings/bulk")
    def bulk_estimate_openings(estimate_id: str):
        try:
            est = _est(estimate_id)
            data = request.get_json(silent=True) or {}
            rows = bulk_openings(est, data, current_user())
            db.session.commit()
            return _jsonify({"items": [opening_public(x) for x in rows], "reconcile": recompute_flags(est.id)})
        except (OpeningsError, ApiError) as exc:
            db.session.rollback()
            return _err(exc)

    @bp.post("/estimates/<estimate_id>/openings/apply")
    def apply_estimate_openings(estimate_id: str):
        try:
            est = _est(estimate_id)
            data = request.get_json(silent=True) or {}
            result = apply_openings(
                est,
                roll_up=data.get("roll_up", True) is not False,
                include_labor=bool(data.get("include_labor") or data.get("labor")),
                door_frame_only=bool(data.get("door_frame_only")),
                labor_hours=data.get("labor_hours") if isinstance(data.get("labor_hours"), dict) else None,
                preview=bool(data.get("preview")),
                cu=current_user(),
            )
            db.session.commit()
            return _jsonify(result)
        except (OpeningsError, ApiError) as exc:
            db.session.rollback()
            return _err(exc)

    @bp.post("/estimates/<estimate_id>/openings/extract")
    def extract_estimate_openings(estimate_id: str):
        try:
            est = _est(estimate_id)
            data = request.get_json(silent=True) or {}
            return _jsonify(review_extract(est, data))
        except (OpeningsError, ApiError) as exc:
            return _err(exc)

    @bp.post("/estimates/<estimate_id>/openings/extract/confirm")
    def confirm_extract_estimate_openings(estimate_id: str):
        try:
            est = _est(estimate_id)
            data = request.get_json(silent=True) or {}
            if data.get("confirm") is False:
                return _jsonify({"committed": False, "openings_created": 0, "sets_created": 0})
            result = confirm_extract(est, data, current_user())
            db.session.commit()
            bundle = openings_bundle(est.id)
            bundle.update(result)
            return _jsonify(bundle)
        except (OpeningsError, ApiError) as exc:
            db.session.rollback()
            return _err(exc)

    @bp.post("/estimates/<estimate_id>/openings/draft-rfps")
    def draft_openings_rfps(estimate_id: str):
        try:
            est = _est(estimate_id)
            data = request.get_json(silent=True) or {}
            rfps = draft_rfps_from_openings(est, current_user(), data.get("document_ids"))
            db.session.commit()
            from ._rfp_quotes_service import serialize_rfp

            return _jsonify({"items": [serialize_rfp(r) for r in rfps], "entity": "rfps"}), 201
        except (OpeningsError, ApiError) as exc:
            db.session.rollback()
            return _err(exc)

    @bp.post("/estimates/<estimate_id>/openings/<oid>/duplicate")
    def duplicate_estimate_opening(estimate_id: str, oid: str):
        try:
            est = _est(estimate_id)
            opening_id = _parse_uuid_param(oid)
            if not opening_id:
                return _jsonify({"error": "invalid opening id"}), 400
            op = duplicate_opening(est, opening_id, current_user())
            db.session.commit()
            return _jsonify({"item": opening_public(op)}), 201
        except (OpeningsError, ApiError) as exc:
            db.session.rollback()
            return _err(exc)

    @bp.post("/estimates/<estimate_id>/openings/<oid>/confirm")
    def confirm_estimate_opening(estimate_id: str, oid: str):
        try:
            est = _est(estimate_id)
            opening_id = _parse_uuid_param(oid)
            if not opening_id:
                return _jsonify({"error": "invalid opening id"}), 400
            op = confirm_opening(est, opening_id, current_user())
            db.session.commit()
            return _jsonify({"item": opening_public(op), "reconcile": recompute_flags(est.id)})
        except (OpeningsError, ApiError) as exc:
            db.session.rollback()
            return _err(exc)

    @bp.post("/estimates/<estimate_id>/openings/<oid>/flags/<key>/dismiss")
    def dismiss_opening_flag(estimate_id: str, oid: str, key: str):
        try:
            est = _est(estimate_id)
            opening_id = _parse_uuid_param(oid)
            if not opening_id:
                return _jsonify({"error": "invalid opening id"}), 400
            data = request.get_json(silent=True) or {}
            op = dismiss_flag(est, opening_id, key, str(data.get("reason") or ""), current_user())
            db.session.commit()
            return _jsonify({"item": opening_public(op)})
        except (OpeningsError, ApiError) as exc:
            db.session.rollback()
            return _err(exc)

    @bp.post("/estimates/<estimate_id>/openings")
    def create_estimate_opening(estimate_id: str):
        try:
            est = _est(estimate_id)
            data = request.get_json(silent=True) or {}
            op = create_opening(est, data, current_user())
            db.session.commit()
            return _jsonify({"item": opening_public(op), "reconcile": recompute_flags(est.id)}), 201
        except (OpeningsError, ApiError) as exc:
            db.session.rollback()
            return _err(exc)

    @bp.patch("/estimates/<estimate_id>/openings/<oid>")
    def patch_estimate_opening(estimate_id: str, oid: str):
        try:
            est = _est(estimate_id)
            opening_id = _parse_uuid_param(oid)
            if not opening_id:
                return _jsonify({"error": "invalid opening id"}), 400
            op = patch_opening(est, opening_id, request.get_json(silent=True) or {}, current_user())
            db.session.commit()
            return _jsonify({"item": opening_public(op), "reconcile": recompute_flags(est.id)})
        except (OpeningsError, ApiError) as exc:
            db.session.rollback()
            return _err(exc)

    @bp.delete("/estimates/<estimate_id>/openings/<oid>")
    def delete_estimate_opening(estimate_id: str, oid: str):
        try:
            est = _est(estimate_id)
            opening_id = _parse_uuid_param(oid)
            if not opening_id:
                return _jsonify({"error": "invalid opening id"}), 400
            delete_opening(est, opening_id, current_user())
            db.session.commit()
            return _jsonify({"ok": True, "reconcile": recompute_flags(est.id)})
        except (OpeningsError, ApiError) as exc:
            db.session.rollback()
            return _err(exc)

    @bp.get("/estimates/<estimate_id>/hardware-sets")
    def list_estimate_hardware_sets(estimate_id: str):
        try:
            est = _est(estimate_id)
            bundle = openings_bundle(est.id)
            return _jsonify({"items": bundle["sets"], "reconcile": bundle["reconcile"]})
        except (OpeningsError, ApiError) as exc:
            return _err(exc)

    @bp.post("/estimates/<estimate_id>/hardware-sets/import")
    def import_estimate_hardware_sets(estimate_id: str):
        try:
            est = _est(estimate_id)
            data = request.get_json(silent=True) or {}
            summary = import_sets_csv(est, data.get("sets") or [], data.get("items") or [], current_user())
            db.session.commit()
            bundle = openings_bundle(est.id)
            bundle.update(summary)
            return _jsonify(bundle), 201
        except (OpeningsError, ApiError) as exc:
            db.session.rollback()
            return _err(exc)

    @bp.get("/estimates/<estimate_id>/hardware-sets/export")
    def export_estimate_hardware_sets(estimate_id: str):
        try:
            est = _est(estimate_id)
            sets_csv, items_csv = export_sets_csv(est)
            return _jsonify({"sets_csv": sets_csv, "items_csv": items_csv})
        except (OpeningsError, ApiError) as exc:
            return _err(exc)

    @bp.post("/estimates/<estimate_id>/hardware-sets/copy-from-company")
    def copy_company_hardware_set(estimate_id: str):
        try:
            est = _est(estimate_id)
            data = request.get_json(silent=True) or {}
            hs = copy_from_company(est, str(data.get("code") or ""), current_user())
            db.session.commit()
            return _jsonify({"item": set_public(hs, [])}), 201
        except (OpeningsError, ApiError) as exc:
            db.session.rollback()
            return _err(exc)

    @bp.post("/estimates/<estimate_id>/hardware-sets")
    def create_estimate_hardware_set(estimate_id: str):
        try:
            est = _est(estimate_id)
            hs = create_set(est, request.get_json(silent=True) or {}, current_user())
            db.session.commit()
            return _jsonify({"item": set_public(hs, [])}), 201
        except (OpeningsError, ApiError) as exc:
            db.session.rollback()
            return _err(exc)

    @bp.patch("/estimates/<estimate_id>/hardware-sets/<sid>")
    def patch_estimate_hardware_set(estimate_id: str, sid: str):
        try:
            est = _est(estimate_id)
            set_id = _parse_uuid_param(sid)
            if not set_id:
                return _jsonify({"error": "invalid set id"}), 400
            hs = patch_set(est, set_id, request.get_json(silent=True) or {}, current_user())
            db.session.commit()
            return _jsonify({"item": set_public(hs, [])})
        except (OpeningsError, ApiError) as exc:
            db.session.rollback()
            return _err(exc)

    @bp.post("/estimates/<estimate_id>/hardware-sets/<sid>/copy")
    def copy_estimate_hardware_set(estimate_id: str, sid: str):
        try:
            est = _est(estimate_id)
            set_id = _parse_uuid_param(sid)
            if not set_id:
                return _jsonify({"error": "invalid set id"}), 400
            data = request.get_json(silent=True) or {}
            hs = copy_set(est, set_id, str(data.get("set_no") or ""), current_user())
            db.session.commit()
            return _jsonify({"item": set_public(hs, [])}), 201
        except (OpeningsError, ApiError) as exc:
            db.session.rollback()
            return _err(exc)

    @bp.delete("/estimates/<estimate_id>/hardware-sets/<sid>")
    def delete_estimate_hardware_set(estimate_id: str, sid: str):
        try:
            est = _est(estimate_id)
            set_id = _parse_uuid_param(sid)
            if not set_id:
                return _jsonify({"error": "invalid set id"}), 400
            delete_set(est, set_id, current_user())
            db.session.commit()
            return _jsonify({"ok": True, "reconcile": recompute_flags(est.id)})
        except (OpeningsError, ApiError) as exc:
            db.session.rollback()
            return _err(exc)

    @bp.post("/estimates/<estimate_id>/hardware-sets/<sid>/items")
    def add_estimate_hardware_set_item(estimate_id: str, sid: str):
        try:
            est = _est(estimate_id)
            set_id = _parse_uuid_param(sid)
            if not set_id:
                return _jsonify({"error": "invalid set id"}), 400
            from ..models.hardware_set import HardwareSet

            hs = db.session.get(HardwareSet, set_id)
            if hs is None or hs.estimate_id != est.id:
                return _jsonify({"error": "hardware set not found"}), 404
            it = add_set_item(hs, request.get_json(silent=True) or {})
            db.session.commit()
            return _jsonify({"item": item_public(it), "set": set_public(hs, [])}), 201
        except (OpeningsError, ApiError) as exc:
            db.session.rollback()
            return _err(exc)

    @bp.patch("/estimates/<estimate_id>/hardware-set-items/<iid>")
    def patch_estimate_hardware_set_item(estimate_id: str, iid: str):
        try:
            est = _est(estimate_id)
            item_id = _parse_uuid_param(iid)
            if not item_id:
                return _jsonify({"error": "invalid item id"}), 400
            it = patch_set_item(est, item_id, request.get_json(silent=True) or {}, current_user())
            db.session.commit()
            return _jsonify({"item": item_public(it)})
        except (OpeningsError, ApiError) as exc:
            db.session.rollback()
            return _err(exc)

    @bp.delete("/estimates/<estimate_id>/hardware-set-items/<iid>")
    def delete_estimate_hardware_set_item(estimate_id: str, iid: str):
        try:
            est = _est(estimate_id)
            item_id = _parse_uuid_param(iid)
            if not item_id:
                return _jsonify({"error": "invalid item id"}), 400
            delete_set_item(est, item_id, current_user())
            db.session.commit()
            return _jsonify({"ok": True})
        except (OpeningsError, ApiError) as exc:
            db.session.rollback()
            return _err(exc)

    @bp.put("/estimates/<estimate_id>/openings/labor-defaults")
    def put_opening_labor_defaults(estimate_id: str):
        try:
            est = _est(estimate_id)
            data = request.get_json(silent=True) or {}
            hours = save_labor_defaults(est, data.get("hours") or data)
            db.session.commit()
            return _jsonify({"labor_defaults": hours})
        except (OpeningsError, ApiError) as exc:
            db.session.rollback()
            return _err(exc)
