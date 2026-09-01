"""HTTP routes for Sage CM Wave 2."""
from __future__ import annotations

import uuid

from flask import Blueprint, jsonify, request

from ._perms import current_user
from ._rfi_service import ApiError
from . import _wave2_service as wave2_svc


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


def register_wave2_routes(bp: Blueprint) -> None:
    @bp.get("/projects/<project_id>/wave2/<kind>")
    def list_wave2(project_id: str, kind: str):
        pid = _parse_uuid_param(project_id)
        if not pid:
            return _jsonify({"error": "invalid project id"}), 400
        try:
            return _jsonify(wave2_svc.list_project_kind(pid, kind, current_user()))
        except ApiError as exc:
            return _err(exc)

    @bp.post("/projects/<project_id>/wave2/<kind>")
    def create_wave2(project_id: str, kind: str):
        pid = _parse_uuid_param(project_id)
        if not pid:
            return _jsonify({"error": "invalid project id"}), 400
        try:
            return _jsonify(wave2_svc.create_project_kind(pid, kind, request.get_json(silent=True) or {}, current_user())), 201
        except ApiError as exc:
            return _err(exc)

    @bp.patch("/projects/<project_id>/wave2/<kind>/<row_id>")
    def patch_wave2(project_id: str, kind: str, row_id: str):
        pid = _parse_uuid_param(project_id)
        rid = _parse_uuid_param(row_id)
        if not pid or not rid:
            return _jsonify({"error": "invalid id"}), 400
        try:
            return _jsonify(wave2_svc.patch_project_kind(pid, kind, rid, request.get_json(silent=True) or {}, current_user()))
        except ApiError as exc:
            return _err(exc)

    @bp.delete("/projects/<project_id>/wave2/<kind>/<row_id>")
    def delete_wave2(project_id: str, kind: str, row_id: str):
        pid = _parse_uuid_param(project_id)
        rid = _parse_uuid_param(row_id)
        if not pid or not rid:
            return _jsonify({"error": "invalid id"}), 400
        try:
            wave2_svc.delete_project_kind(pid, kind, rid, current_user())
            return ("", 204)
        except ApiError as exc:
            return _err(exc)

    @bp.get("/projects/<project_id>/open-items")
    def list_open_items(project_id: str):
        pid = _parse_uuid_param(project_id)
        if not pid:
            return _jsonify({"error": "invalid project id"}), 400
        try:
            return _jsonify(wave2_svc.team_open_items(pid, current_user()))
        except ApiError as exc:
            return _err(exc)

    @bp.get("/companies")
    def list_companies():
        q = (request.args.get("q") or "").strip()
        try:
            limit = int(request.args.get("limit") or 50)
        except ValueError:
            return _jsonify({"error": "invalid limit"}), 400
        try:
            return _jsonify(wave2_svc.list_companies(current_user(), q=q, limit=limit))
        except ApiError as exc:
            return _err(exc)

    @bp.post("/companies")
    def create_company():
        try:
            return _jsonify(wave2_svc.create_company(request.get_json(silent=True) or {}, current_user())), 201
        except ApiError as exc:
            return _err(exc)

    @bp.patch("/companies/<company_id>")
    def patch_company(company_id: str):
        cid = _parse_uuid_param(company_id)
        if not cid:
            return _jsonify({"error": "invalid company id"}), 400
        try:
            return _jsonify(wave2_svc.patch_company(cid, request.get_json(silent=True) or {}, current_user()))
        except ApiError as exc:
            return _err(exc)

    @bp.get("/companies/<company_id>/contacts")
    def list_contacts(company_id: str):
        cid = _parse_uuid_param(company_id)
        if not cid:
            return _jsonify({"error": "invalid company id"}), 400
        try:
            return _jsonify(wave2_svc.list_contacts(cid, current_user()))
        except ApiError as exc:
            return _err(exc)

    @bp.post("/companies/<company_id>/contacts")
    def create_contact(company_id: str):
        cid = _parse_uuid_param(company_id)
        if not cid:
            return _jsonify({"error": "invalid company id"}), 400
        try:
            return _jsonify(wave2_svc.create_contact(cid, request.get_json(silent=True) or {}, current_user())), 201
        except ApiError as exc:
            return _err(exc)

    @bp.get("/companies/<company_id>/<kind>")
    def list_company_docs(company_id: str, kind: str):
        if kind not in ("insurance", "licenses"):
            return _jsonify({"error": "unknown kind"}), 404
        cid = _parse_uuid_param(company_id)
        if not cid:
            return _jsonify({"error": "invalid company id"}), 400
        doc_kind = "insurance" if kind == "insurance" else "licenses"
        try:
            return _jsonify(wave2_svc.list_company_docs(cid, "insurance" if doc_kind == "insurance" else "license", current_user()))
        except ApiError as exc:
            return _err(exc)

    @bp.post("/companies/<company_id>/<kind>")
    def create_company_docs(company_id: str, kind: str):
        if kind not in ("insurance", "licenses"):
            return _jsonify({"error": "unknown kind"}), 404
        cid = _parse_uuid_param(company_id)
        if not cid:
            return _jsonify({"error": "invalid company id"}), 400
        try:
            return _jsonify(
                wave2_svc.create_company_doc(
                    cid, "insurance" if kind == "insurance" else "license", request.get_json(silent=True) or {}, current_user()
                )
            ), 201
        except ApiError as exc:
            return _err(exc)

    @bp.delete("/companies/<company_id>/<kind>/<row_id>")
    def delete_company_docs(company_id: str, kind: str, row_id: str):
        if kind not in ("insurance", "licenses"):
            return _jsonify({"error": "unknown kind"}), 404
        cid = _parse_uuid_param(company_id)
        rid = _parse_uuid_param(row_id)
        if not cid or not rid:
            return _jsonify({"error": "invalid id"}), 400
        try:
            wave2_svc.delete_company_doc(cid, "insurance" if kind == "insurance" else "license", rid, current_user())
            return ("", 204)
        except ApiError as exc:
            return _err(exc)

    @bp.get("/workflow-amount-rules")
    def list_amount_rules():
        try:
            return _jsonify(wave2_svc.list_amount_rules(current_user()))
        except ApiError as exc:
            return _err(exc)

    @bp.post("/workflow-amount-rules")
    def create_amount_rule():
        try:
            return _jsonify(wave2_svc.create_amount_rule(request.get_json(silent=True) or {}, current_user())), 201
        except ApiError as exc:
            return _err(exc)

    @bp.get("/workflow-inbox")
    def workflow_inbox():
        try:
            return _jsonify(wave2_svc.workflow_inbox(current_user()))
        except ApiError as exc:
            return _err(exc)

    @bp.get("/issues/<issue_id>/companies")
    def list_issue_companies(issue_id: str):
        iid = _parse_uuid_param(issue_id)
        if not iid:
            return _jsonify({"error": "invalid issue id"}), 400
        try:
            return _jsonify(wave2_svc.list_issue_companies(iid, current_user()))
        except ApiError as exc:
            return _err(exc)

    @bp.put("/issues/<issue_id>/companies")
    def put_issue_companies(issue_id: str):
        iid = _parse_uuid_param(issue_id)
        if not iid:
            return _jsonify({"error": "invalid issue id"}), 400
        data = request.get_json(silent=True) or {}
        raw = data.get("items") if isinstance(data, dict) else data
        if not isinstance(raw, list):
            raw = []
        try:
            return _jsonify(wave2_svc.set_issue_companies(iid, raw, current_user()))
        except ApiError as exc:
            return _err(exc)

    @bp.post("/me/timesheets/convert-clock")
    def convert_clock():
        try:
            return _jsonify(wave2_svc.convert_clock_to_timecard(current_user(), request.get_json(silent=True) or {}))
        except ApiError as exc:
            return _err(exc)

    from . import _vendor_line_card_routes as vlc_routes

    vlc_routes.register_vendor_line_card_routes(bp)
