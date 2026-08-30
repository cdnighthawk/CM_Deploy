"""Routes for independent estimates per lead (see CURSOR-GUIDANCE-BACKEND-Estimates)."""
from __future__ import annotations

from typing import Any, Mapping

from flask import Blueprint, Response, request

from ..extensions import db
from ..models import AuditLog, Estimate
from . import _document_render_service as document_render_svc
from . import _estimate_service as est_svc
from . import _estimator_scripts as scripts
from . import _rfi_service as rfi_svc
from ._rfi_service import ApiError
from ._perms import current_user
from . import v1 as v1_mod
from .v1 import (
    _apply_takeoff_payload,
    _iso,
    _jsonify,
    _lead_estimate_detail,
    _parse_uuid_param,
    _resolve_lead,
    _takeoff_line_public,
    _takeoff_locked_response,
    _takeoff_writes_enabled,
)


def _err(exc: est_svc.EstimateError):
    body: dict[str, Any] = {"error": exc.message}
    if exc.error_code:
        body["error_code"] = exc.error_code
    return _jsonify(body), exc.status


def _audit(cu, entity_id, action: str, changes: dict[str, Any] | None = None) -> None:
    db.session.add(
        AuditLog(
            user_id=cu.user.id if cu.user else None,
            entity_type="estimate",
            entity_id=entity_id,
            action=action,
            changes=changes,
        )
    )


def _get_estimate(estimate_id: str) -> Estimate | None:
    eid = _parse_uuid_param(estimate_id)
    if not eid:
        return None
    return db.session.get(Estimate, eid)


def _estimate_detail_item(est: Estimate) -> dict[str, Any]:
    lead = est.lead_estimate
    if lead is not None:
        out = _lead_estimate_detail(lead, estimate=est)
        out["lead_id"] = str(lead.id)
        out["lead_estimate_id"] = str(lead.id)
        out["lead"] = est_svc.lead_snapshot(lead)
    else:
        out = {
            "lead_id": None,
            "lead_estimate_id": None,
            "lead": None,
            "takeoff_lines": [_takeoff_line_public(x) for x in est_svc.takeoff_lines_for_estimate(est.id)],
            "takeoff_line_count": 0,
        }
        out["takeoff_line_count"] = len(out["takeoff_lines"])
    out.update(est_svc.estimate_summary_public(est))
    out["id"] = str(est.id)
    out["created_by_email"] = est_svc.created_by_email(est.created_by_id)
    return out


def register_independent_estimate_routes(bp: Blueprint) -> None:
    def _list_for_lead(identifier: str):
        lead = _resolve_lead(identifier)
        if lead is None:
            return _jsonify({"error": "lead estimate not found"}), 404
        rows = est_svc.list_estimates_for_lead(lead)
        return _jsonify(
            {
                "items": [est_svc.estimate_summary_public(x) for x in rows],
                "entity": "estimates",
                "lead_estimate_id": str(lead.id),
            }
        )

    def _create_for_lead(identifier: str):
        lead = _resolve_lead(identifier)
        if lead is None:
            return _jsonify({"error": "lead estimate not found"}), 404
        data = request.get_json(silent=True)
        if not isinstance(data, Mapping):
            data = {}
        cu = current_user()
        try:
            est = est_svc.create_estimate(
                lead,
                data,
                user_id=cu.user.id if cu.user else None,
            )
        except est_svc.EstimateError as exc:
            return _err(exc)
        _audit(cu, est.id, "estimate_created", changes={"name": est.name})
        db.session.commit()
        return _jsonify({"item": _estimate_detail_item(est), "entity": "estimate"}), 201

    @bp.get("/leads/<lead_id>/estimates")
    def list_lead_job_estimates(lead_id: str):
        return _list_for_lead(lead_id)

    @bp.post("/leads/<lead_id>/estimates")
    def create_lead_job_estimate(lead_id: str):
        return _create_for_lead(lead_id)

    @bp.get("/lead-estimates/<identifier>/estimates")
    def list_lead_estimate_job_estimates(identifier: str):
        return _list_for_lead(identifier)

    @bp.post("/lead-estimates/<identifier>/estimates")
    def create_lead_estimate_job_estimate(identifier: str):
        return _create_for_lead(identifier)

    @bp.get("/leads/<lead_id>/drawing-sets")
    def list_lead_drawing_sets(lead_id: str):
        lead = _resolve_lead(lead_id)
        if lead is None:
            return _jsonify({"error": "lead estimate not found"}), 404
        rows = est_svc.list_drawing_sets(lead)
        return _jsonify(
            {
                "items": [est_svc.drawing_set_public(x) for x in rows],
                "entity": "drawing_sets",
                "lead_estimate_id": str(lead.id),
            }
        )

    @bp.post("/leads/<lead_id>/drawing-sets")
    def create_lead_drawing_set(lead_id: str):
        lead = _resolve_lead(lead_id)
        if lead is None:
            return _jsonify({"error": "lead estimate not found"}), 404
        data = request.get_json(silent=True)
        if not isinstance(data, Mapping):
            data = {}
        try:
            row = est_svc.create_drawing_set(lead, data)
        except est_svc.EstimateError as exc:
            return _err(exc)
        db.session.commit()
        return _jsonify({"item": est_svc.drawing_set_public(row), "entity": "drawing_set"}), 201

    @bp.get("/estimates/<estimate_id>")
    def get_job_estimate(estimate_id: str):
        est = _get_estimate(estimate_id)
        if est is None:
            return _jsonify({"error": "estimate not found"}), 404
        return _jsonify({"item": _estimate_detail_item(est), "entity": "estimate"})

    @bp.get("/estimates/<estimate_id>/bid-scope")
    def get_estimate_bid_scope(estimate_id: str):
        eid = _parse_uuid_param(estimate_id)
        if eid is None:
            return _jsonify({"error": "invalid estimate id"}), 400
        try:
            scope = scripts.get_scope(eid) or scripts.ensure_scope_from_standard(eid)
            db.session.commit()
            return _jsonify({"item": scripts.scope_public(scope), "entity": "estimate_bid_scope"})
        except ApiError as exc:
            return _jsonify({"error": exc.message}), exc.status

    @bp.put("/estimates/<estimate_id>/bid-scope")
    def put_estimate_bid_scope(estimate_id: str):
        eid = _parse_uuid_param(estimate_id)
        if eid is None:
            return _jsonify({"error": "invalid estimate id"}), 400
        data = request.get_json(silent=True) or {}
        try:
            scope = scripts.replace_scope(eid, data)
            db.session.commit()
            return _jsonify({"item": scripts.scope_public(scope), "entity": "estimate_bid_scope"})
        except ApiError as exc:
            return _jsonify({"error": exc.message}), exc.status

    @bp.post("/estimates/<estimate_id>/bid-scope/confirm")
    def confirm_estimate_bid_scope(estimate_id: str):
        eid = _parse_uuid_param(estimate_id)
        if eid is None:
            return _jsonify({"error": "invalid estimate id"}), 400
        try:
            scope = scripts.confirm_scope(eid)
            db.session.commit()
            return _jsonify({"item": scripts.scope_public(scope), "entity": "estimate_bid_scope"})
        except ApiError as exc:
            return _jsonify({"error": exc.message}), exc.status

    @bp.post("/estimates/<estimate_id>/bid-scope/enqueue")
    def enqueue_estimate_spec_scripts(estimate_id: str):
        eid = _parse_uuid_param(estimate_id)
        if eid is None:
            return _jsonify({"error": "invalid estimate id"}), 400
        try:
            out = scripts.enqueue_spec_scripts(eid, current_user())
            db.session.commit()
            return _jsonify(out)
        except ApiError as exc:
            return _jsonify({"error": exc.message}), exc.status

    @bp.delete("/estimates/<estimate_id>")
    def delete_job_estimate(estimate_id: str):
        if not _takeoff_writes_enabled():
            return _jsonify(
                {
                    "error": "takeoff writes disabled (set TAKEOFF_API_WRITES_ENABLED=1)",
                    "error_code": "TAKEOFF_WRITES_DISABLED",
                }
            ), 403
        est = _get_estimate(estimate_id)
        if est is None:
            return _jsonify({"error": "estimate not found"}), 404
        try:
            est_svc.delete_estimate(est)
        except est_svc.EstimateError as exc:
            return _err(exc)
        db.session.commit()
        return _jsonify({"ok": True})

    @bp.post("/estimates/<estimate_id>/lock")
    def lock_job_estimate(estimate_id: str):
        if not _takeoff_writes_enabled():
            return _jsonify(
                {
                    "error": "takeoff writes disabled (set TAKEOFF_API_WRITES_ENABLED=1)",
                    "error_code": "TAKEOFF_WRITES_DISABLED",
                }
            ), 403
        est = _get_estimate(estimate_id)
        if est is None:
            return _jsonify({"error": "estimate not found"}), 404
        cu = current_user()
        try:
            est_svc.lock_estimate(est)
        except est_svc.EstimateError as exc:
            return _err(exc)
        _audit(cu, est.id, "estimate_locked", changes={"estimate_locked_at": _iso(est.estimate_locked_at)})
        db.session.commit()
        return _jsonify({"item": _estimate_detail_item(est), "entity": "estimate"})

    @bp.post("/estimates/<estimate_id>/approve")
    def approve_job_estimate(estimate_id: str):
        if not _takeoff_writes_enabled():
            return _jsonify(
                {
                    "error": "takeoff writes disabled (set TAKEOFF_API_WRITES_ENABLED=1)",
                    "error_code": "TAKEOFF_WRITES_DISABLED",
                }
            ), 403
        est = _get_estimate(estimate_id)
        if est is None:
            return _jsonify({"error": "estimate not found"}), 404
        cu = current_user()
        try:
            est_svc.approve_estimate(est, user_id=cu.user.id if cu.user else None)
        except est_svc.EstimateError as exc:
            return _err(exc)
        _audit(
            cu,
            est.id,
            "estimate_approved",
            changes={"approved_at": _iso(est.approved_at), "estimate_locked_at": _iso(est.estimate_locked_at)},
        )
        db.session.commit()
        return _jsonify({"item": _estimate_detail_item(est), "entity": "estimate"})

    @bp.post("/estimates/<estimate_id>/unlock")
    def unlock_job_estimate(estimate_id: str):
        est = _get_estimate(estimate_id)
        if est is None:
            return _jsonify({"error": "estimate not found"}), 404
        cu = current_user()
        if not v1_mod._can_unlock_lead_estimate(cu):
            return _jsonify(
                {
                    "error": "admin or superuser role required to unlock estimates",
                    "error_code": "UNLOCK_FORBIDDEN",
                }
            ), 403
        try:
            prev = _iso(est.estimate_locked_at)
            est_svc.unlock_estimate(est)
        except est_svc.EstimateError as exc:
            return _err(exc)
        _audit(cu, est.id, "estimate_unlocked", changes={"previous_locked_at": prev})
        db.session.commit()
        return _jsonify({"item": _estimate_detail_item(est), "entity": "estimate"})

    @bp.get("/estimates/<estimate_id>/takeoff-lines")
    def list_estimate_takeoff_lines(estimate_id: str):
        est = _get_estimate(estimate_id)
        if est is None:
            return _jsonify({"error": "estimate not found"}), 404
        lines = est_svc.takeoff_lines_for_estimate(est.id)
        from ..services.employee_pc_cache import maybe_write_takeoff

        maybe_write_takeoff(
            est.project_id,
            lines,
            cloud_estimate_id=est.id,
            lead_estimate_id=est.lead_estimate_id,
        )
        return _jsonify(
            {
                "items": [_takeoff_line_public(x) for x in lines],
                "entity": "takeoff_line_items",
                "estimate_id": str(est.id),
                "lead_estimate_id": str(est.lead_estimate_id) if est.lead_estimate_id else None,
            }
        )

    @bp.post("/estimates/<estimate_id>/takeoff-lines")
    def create_estimate_takeoff_line(estimate_id: str):
        if not _takeoff_writes_enabled():
            return _jsonify(
                {
                    "error": "takeoff writes disabled (set TAKEOFF_API_WRITES_ENABLED=1)",
                    "error_code": "TAKEOFF_WRITES_DISABLED",
                }
            ), 403
        est = _get_estimate(estimate_id)
        if est is None:
            return _jsonify({"error": "estimate not found"}), 404
        if est_svc.estimate_is_locked(est):
            return _takeoff_locked_response()
        data = request.get_json(silent=True)
        if not isinstance(data, Mapping):
            data = {}
        try:
            from ..models import TakeoffLineItem

            t = TakeoffLineItem(
                estimate_id=est.id,
                lead_estimate_id=est.lead_estimate_id,
                project_id=est.project_id,
                sort_order=int(data["sort_order"])
                if data.get("sort_order") is not None
                else est_svc.next_sort_order(estimate_id=est.id),
            )
            _apply_takeoff_payload(t, data, partial=False)
        except (ValueError, TypeError) as exc:
            return _jsonify({"error": str(exc)}), 400
        db.session.add(t)
        db.session.commit()
        from ..services.employee_pc_cache import cache_takeoff_for_line

        cache_takeoff_for_line(t)
        return _jsonify({"item": _takeoff_line_public(t), "entity": "takeoff_line_item"}), 201

    @bp.get("/estimates/<estimate_id>/render/quote-report")
    def render_estimate_quote_report(estimate_id: str):
        est = _get_estimate(estimate_id)
        if est is None:
            return _jsonify({"error": "estimate not found"}), 404
        lead = est.lead_estimate
        if lead is None:
            return _jsonify({"error": "estimate is not attached to a lead"}), 400
        try:
            limit = int(request.args.get("line_limit", 500))
        except ValueError:
            return _jsonify({"error": "invalid line_limit"}), 400
        limit = max(0, min(limit, 5000))
        columns = request.args.get("columns")
        try:
            html = document_render_svc.render_quote_report_html(
                lead,
                current_user(),
                columns_raw=columns,
                line_limit=limit,
                estimate=est,
            )
            return Response(html, mimetype="text/html; charset=utf-8")
        except rfi_svc.ApiError as exc:
            from .v1 import _document_render_err

            return _document_render_err(exc)
