"""Register field-app daily report and photo routes on the v1 blueprint."""
from __future__ import annotations

from datetime import date

from flask import Blueprint, jsonify, request

from ._field_service import (
    FieldApiError,
    create_field_photo,
    get_or_create_daily_report,
    list_field_photos,
    put_daily_report,
    send_field_photo_file,
    update_field_photo,
)
from ._perms import current_user
from ._time_clock_service import (
    break_end,
    break_start,
    clock_in,
    clock_out,
    list_cost_codes,
    list_me,
    switch_job,
)


def _parse_uuid_param(raw: str | None):
    if not raw or not str(raw).strip():
        return None
    import uuid

    try:
        return uuid.UUID(str(raw).strip())
    except ValueError:
        return None


def _project_exists(project_id) -> bool:
    from ..permissions.project_scope import user_can_access_project

    return user_can_access_project(current_user(), project_id)


def _err(exc: FieldApiError):
    return jsonify({"error": exc.message}), exc.status


def register_field_routes(bp: Blueprint) -> None:
    @bp.get("/projects/<project_id>/daily-reports")
    def get_project_daily_report(project_id: str):
        pid = _parse_uuid_param(project_id)
        if not pid:
            return jsonify({"error": "invalid project id"}), 400
        if not _project_exists(pid):
            return jsonify({"error": "project not found"}), 404
        raw_date = (request.args.get("date") or "").strip()
        report_date = None
        if raw_date:
            try:
                report_date = date.fromisoformat(raw_date[:10])
            except ValueError:
                return jsonify({"error": "invalid date; use YYYY-MM-DD"}), 400
        else:
            report_date = date.today()
        try:
            return jsonify(get_or_create_daily_report(pid, report_date, current_user()))
        except FieldApiError as exc:
            return _err(exc)

    @bp.put("/daily-reports/<report_id>")
    def update_daily_report(report_id: str):
        rid = _parse_uuid_param(report_id)
        if not rid:
            return jsonify({"error": "invalid daily report id"}), 400
        data = request.get_json(silent=True) or {}
        if not isinstance(data, dict):
            return jsonify({"error": "JSON body required"}), 400
        try:
            return jsonify(put_daily_report(rid, data, current_user()))
        except FieldApiError as exc:
            return _err(exc)

    @bp.get("/projects/<project_id>/photos")
    def get_project_photos(project_id: str):
        pid = _parse_uuid_param(project_id)
        if not pid:
            return jsonify({"error": "invalid project id"}), 400
        if not _project_exists(pid):
            return jsonify({"error": "project not found"}), 404
        return jsonify(list_field_photos(pid))

    @bp.post("/projects/<project_id>/photos")
    def post_project_photo(project_id: str):
        pid = _parse_uuid_param(project_id)
        if not pid:
            return jsonify({"error": "invalid project id"}), 400
        if not _project_exists(pid):
            return jsonify({"error": "project not found"}), 404
        form = request.form.to_dict() if request.form else {}
        try:
            return jsonify(create_field_photo(pid, request.files.get("file"), form, current_user())), 201
        except FieldApiError as exc:
            return _err(exc)

    @bp.patch("/photos/<photo_id>")
    def patch_field_photo(photo_id: str):
        pid = _parse_uuid_param(photo_id)
        if not pid:
            return jsonify({"error": "invalid photo id"}), 400
        data = request.get_json(silent=True) or {}
        if not isinstance(data, dict):
            return jsonify({"error": "JSON body required"}), 400
        try:
            return jsonify(update_field_photo(pid, data, current_user()))
        except FieldApiError as exc:
            return _err(exc)

    @bp.get("/photos/<photo_id>/file")
    def get_field_photo_file(photo_id: str):
        pid = _parse_uuid_param(photo_id)
        if not pid:
            return jsonify({"error": "invalid photo id"}), 400
        try:
            return send_field_photo_file(pid, current_user())
        except FieldApiError as exc:
            return _err(exc)

    @bp.get("/projects/<project_id>/cost-codes")
    def get_project_cost_codes(project_id: str):
        pid = _parse_uuid_param(project_id)
        if not pid:
            return jsonify({"error": "invalid project id"}), 400
        if not _project_exists(pid):
            return jsonify({"error": "project not found"}), 404
        try:
            return jsonify(list_cost_codes(pid, current_user()))
        except FieldApiError as exc:
            return _err(exc)

    @bp.get("/time-clock/me")
    def get_time_clock_me():
        try:
            return jsonify(list_me(current_user()))
        except FieldApiError as exc:
            return _err(exc)

    def _json_body():
        data = request.get_json(silent=True) or {}
        if not isinstance(data, dict):
            return None
        return data

    @bp.post("/time-clock/clock-in")
    def post_time_clock_in():
        data = _json_body()
        if data is None:
            return jsonify({"error": "JSON body required"}), 400
        try:
            return jsonify(clock_in(data, current_user())), 201
        except FieldApiError as exc:
            return _err(exc)

    @bp.post("/time-clock/clock-out")
    def post_time_clock_out():
        data = _json_body()
        if data is None:
            return jsonify({"error": "JSON body required"}), 400
        try:
            return jsonify(clock_out(data, current_user()))
        except FieldApiError as exc:
            return _err(exc)

    @bp.post("/time-clock/break-start")
    def post_time_clock_break_start():
        data = _json_body()
        if data is None:
            return jsonify({"error": "JSON body required"}), 400
        try:
            return jsonify(break_start(data, current_user()))
        except FieldApiError as exc:
            return _err(exc)

    @bp.post("/time-clock/break-end")
    def post_time_clock_break_end():
        data = _json_body()
        if data is None:
            return jsonify({"error": "JSON body required"}), 400
        try:
            return jsonify(break_end(data, current_user()))
        except FieldApiError as exc:
            return _err(exc)

    @bp.post("/time-clock/switch")
    def post_time_clock_switch():
        data = _json_body()
        if data is None:
            return jsonify({"error": "JSON body required"}), 400
        try:
            return jsonify(switch_job(data, current_user()))
        except FieldApiError as exc:
            return _err(exc)
