"""Register safety dashboard and daily pretask routes on the v1 blueprint."""
from __future__ import annotations

from datetime import date

from flask import Blueprint, jsonify, request

from ._safety_service import (
    SafetyApiError,
    create_pretask,
    get_or_create_pretask,
    get_pretask,
    list_pretasks,
    put_pretask,
    safety_summary,
    submit_pretask,
)
from ._perms import current_user


def _parse_uuid_param(raw: str | None):
    if not raw or not str(raw).strip():
        return None
    import uuid

    try:
        return uuid.UUID(str(raw).strip())
    except ValueError:
        return None


def _parse_date_arg(raw: str | None) -> date | None:
    if not raw or not str(raw).strip():
        return None
    try:
        return date.fromisoformat(str(raw).strip()[:10])
    except ValueError:
        raise SafetyApiError("invalid date; use YYYY-MM-DD", 400)


def _err(exc: SafetyApiError):
    return jsonify({"error": exc.message}), exc.status


def _json_body():
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return None
    return data


def register_safety_routes(bp: Blueprint) -> None:
    @bp.get("/safety/summary")
    def get_safety_summary():
        try:
            return jsonify(safety_summary(current_user()))
        except SafetyApiError as exc:
            return _err(exc)

    @bp.get("/safety/pretasks")
    def get_safety_pretasks():
        try:
            pid = _parse_uuid_param(request.args.get("project_id"))
            if request.args.get("project_id") and pid is None:
                return jsonify({"error": "invalid project id"}), 400
            work_date = _parse_date_arg(request.args.get("date"))
            date_from = _parse_date_arg(request.args.get("from"))
            date_to = _parse_date_arg(request.args.get("to"))
            raw_limit = (request.args.get("limit") or "50").strip()
            try:
                limit = int(raw_limit)
            except ValueError:
                return jsonify({"error": "invalid limit"}), 400
            return jsonify(
                list_pretasks(
                    current_user(),
                    project_id=pid,
                    work_date=work_date,
                    date_from=date_from,
                    date_to=date_to,
                    status=request.args.get("status"),
                    limit=limit,
                )
            )
        except SafetyApiError as exc:
            return _err(exc)

    @bp.get("/safety/pretasks/<pretask_id>")
    def get_safety_pretask(pretask_id: str):
        rid = _parse_uuid_param(pretask_id)
        if not rid:
            return jsonify({"error": "invalid daily pretask id"}), 400
        try:
            return jsonify(get_pretask(rid, current_user()))
        except SafetyApiError as exc:
            return _err(exc)

    @bp.put("/safety/pretasks/<pretask_id>")
    def put_safety_pretask(pretask_id: str):
        rid = _parse_uuid_param(pretask_id)
        if not rid:
            return jsonify({"error": "invalid daily pretask id"}), 400
        data = _json_body()
        if data is None:
            return jsonify({"error": "JSON body required"}), 400
        try:
            return jsonify(put_pretask(rid, data, current_user()))
        except SafetyApiError as exc:
            return _err(exc)

    @bp.post("/safety/pretasks/<pretask_id>/submit")
    def post_safety_pretask_submit(pretask_id: str):
        rid = _parse_uuid_param(pretask_id)
        if not rid:
            return jsonify({"error": "invalid daily pretask id"}), 400
        data = request.get_json(silent=True) or {}
        if data and not isinstance(data, dict):
            return jsonify({"error": "JSON body required"}), 400
        try:
            return jsonify(submit_pretask(rid, data if isinstance(data, dict) else {}, current_user()))
        except SafetyApiError as exc:
            return _err(exc)

    @bp.get("/projects/<project_id>/daily-pretasks")
    def get_project_daily_pretask(project_id: str):
        pid = _parse_uuid_param(project_id)
        if not pid:
            return jsonify({"error": "invalid project id"}), 400
        raw_date = (request.args.get("date") or "").strip()
        try:
            work_date = _parse_date_arg(raw_date) if raw_date else date.today()
        except SafetyApiError as exc:
            return _err(exc)
        client_id = _parse_uuid_param(request.args.get("client_id"))
        if request.args.get("client_id") and client_id is None:
            return jsonify({"error": "invalid client_id"}), 400
        try:
            return jsonify(get_or_create_pretask(pid, work_date, current_user(), client_id=client_id))
        except SafetyApiError as exc:
            return _err(exc)

    @bp.post("/projects/<project_id>/daily-pretasks")
    def post_project_daily_pretask(project_id: str):
        pid = _parse_uuid_param(project_id)
        if not pid:
            return jsonify({"error": "invalid project id"}), 400
        data = _json_body()
        if data is None:
            return jsonify({"error": "JSON body required"}), 400
        try:
            body = create_pretask(pid, data, current_user())
            return jsonify(body), 201 if body.get("created") else 200
        except SafetyApiError as exc:
            return _err(exc)

    @bp.put("/daily-pretasks/<pretask_id>")
    def put_daily_pretask(pretask_id: str):
        rid = _parse_uuid_param(pretask_id)
        if not rid:
            return jsonify({"error": "invalid daily pretask id"}), 400
        data = _json_body()
        if data is None:
            return jsonify({"error": "JSON body required"}), 400
        try:
            return jsonify(put_pretask(rid, data, current_user()))
        except SafetyApiError as exc:
            return _err(exc)

    @bp.post("/daily-pretasks/<pretask_id>/submit")
    def post_daily_pretask_submit(pretask_id: str):
        rid = _parse_uuid_param(pretask_id)
        if not rid:
            return jsonify({"error": "invalid daily pretask id"}), 400
        data = request.get_json(silent=True) or {}
        if data and not isinstance(data, dict):
            return jsonify({"error": "JSON body required"}), 400
        try:
            return jsonify(submit_pretask(rid, data if isinstance(data, dict) else {}, current_user()))
        except SafetyApiError as exc:
            return _err(exc)
