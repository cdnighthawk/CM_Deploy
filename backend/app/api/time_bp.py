"""Shared timekeeping API for office web and FinishWorks Field."""
from __future__ import annotations

import uuid
from datetime import date

from flask import Blueprint, Response, jsonify, request

from ._field_service import _parse_uuid
from ._perms import current_user
from ._time_office import (
    add_entry,
    approve_period,
    cards_summary,
    export_period,
    get_entry,
    get_geofence,
    get_settings,
    ingest_breadcrumbs,
    job_cost,
    list_entries,
    list_events,
    list_flags,
    list_periods,
    list_time_cost_codes,
    live_board,
    lock_period,
    manpower_prefill,
    map_live,
    patch_entry,
    period_detail,
    period_pdf_html,
    put_geofence,
    put_settings,
    resolve_flag,
    sign_day,
    sign_period,
    split_entry,
    upsert_time_cost_code,
    void_entry,
)
from ._time_service import TimeApiError, list_me, punch

bp = Blueprint("api_time", __name__, url_prefix="/api/time")


def _err(exc: TimeApiError):
    return jsonify({"error": exc.message}), exc.status


def _json() -> dict:
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return {}
    return data


def _uuid_arg(raw: str, label: str) -> uuid.UUID:
    uid = _parse_uuid(raw)
    if uid is None:
        raise TimeApiError(f"invalid {label}", 400)
    return uid


def _date_arg(raw: str, label: str = "date") -> date:
    try:
        return date.fromisoformat(str(raw).strip()[:10])
    except ValueError as exc:
        raise TimeApiError(f"invalid {label}", 400) from exc


@bp.post("/punch")
def post_punch():
    try:
        item = punch(_json(), current_user())
        action = str((_json() or {}).get("action") or "")
        return jsonify(item), (201 if action == "clock_in" else 200)
    except TimeApiError as exc:
        return _err(exc)


@bp.get("/me")
def get_me():
    try:
        return jsonify(list_me(current_user()))
    except TimeApiError as exc:
        return _err(exc)


@bp.get("/live")
def get_live():
    try:
        return jsonify(live_board(current_user(), _parse_uuid(request.args.get("project_id"))))
    except TimeApiError as exc:
        return _err(exc)


@bp.get("/entries")
def get_entries():
    try:
        return jsonify(list_entries(current_user(), request.args))
    except TimeApiError as exc:
        return _err(exc)


@bp.post("/entries")
def post_entries():
    try:
        return jsonify(add_entry(_json(), current_user())), 201
    except TimeApiError as exc:
        return _err(exc)


@bp.get("/entries/<entry_id>")
def get_one_entry(entry_id: str):
    try:
        return jsonify(get_entry(_uuid_arg(entry_id, "entry id"), current_user()))
    except TimeApiError as exc:
        return _err(exc)


@bp.patch("/entries/<entry_id>")
def patch_one_entry(entry_id: str):
    try:
        return jsonify(patch_entry(_uuid_arg(entry_id, "entry id"), _json(), current_user()))
    except TimeApiError as exc:
        return _err(exc)


@bp.post("/entries/<entry_id>/split")
def post_split(entry_id: str):
    try:
        return jsonify(split_entry(_uuid_arg(entry_id, "entry id"), _json(), current_user()))
    except TimeApiError as exc:
        return _err(exc)


@bp.delete("/entries/<entry_id>")
def delete_entry(entry_id: str):
    try:
        return jsonify(void_entry(_uuid_arg(entry_id, "entry id"), _json(), current_user()))
    except TimeApiError as exc:
        return _err(exc)


@bp.post("/breadcrumbs")
def post_breadcrumbs():
    try:
        return jsonify(ingest_breadcrumbs(_json(), current_user()))
    except TimeApiError as exc:
        return _err(exc)


@bp.get("/events")
def get_events():
    try:
        return jsonify(list_events(current_user(), request.args))
    except TimeApiError as exc:
        return _err(exc)


@bp.get("/flags")
def get_flags():
    try:
        return jsonify(list_flags(current_user(), request.args))
    except TimeApiError as exc:
        return _err(exc)


@bp.post("/flags/<flag_id>/accept")
def post_flag_accept(flag_id: str):
    try:
        return jsonify(resolve_flag(_uuid_arg(flag_id, "flag id"), "accept", _json(), current_user()))
    except TimeApiError as exc:
        return _err(exc)


@bp.post("/flags/<flag_id>/dismiss")
def post_flag_dismiss(flag_id: str):
    try:
        return jsonify(resolve_flag(_uuid_arg(flag_id, "flag id"), "dismiss", _json(), current_user()))
    except TimeApiError as exc:
        return _err(exc)


@bp.get("/cards")
def get_cards():
    try:
        return jsonify(cards_summary(current_user(), request.args))
    except TimeApiError as exc:
        return _err(exc)


@bp.post("/days/<day>/sign")
def post_sign_day(day: str):
    try:
        return jsonify(sign_day(_date_arg(day), _json(), current_user()))
    except TimeApiError as exc:
        return _err(exc)


@bp.get("/periods")
def get_periods():
    try:
        return jsonify(list_periods(current_user()))
    except TimeApiError as exc:
        return _err(exc)


@bp.get("/periods/<period_id>")
def get_period(period_id: str):
    try:
        return jsonify(period_detail(_uuid_arg(period_id, "period id"), current_user()))
    except TimeApiError as exc:
        return _err(exc)


@bp.post("/periods/<period_id>/sign")
def post_period_sign(period_id: str):
    try:
        return jsonify(sign_period(_uuid_arg(period_id, "period id"), _json(), current_user()))
    except TimeApiError as exc:
        return _err(exc)


@bp.post("/periods/<period_id>/approve")
def post_period_approve(period_id: str):
    try:
        return jsonify(approve_period(_uuid_arg(period_id, "period id"), _json(), current_user()))
    except TimeApiError as exc:
        return _err(exc)


@bp.post("/periods/<period_id>/lock")
def post_period_lock(period_id: str):
    try:
        return jsonify(lock_period(_uuid_arg(period_id, "period id"), current_user(), unlock=False))
    except TimeApiError as exc:
        return _err(exc)


@bp.post("/periods/<period_id>/unlock")
def post_period_unlock(period_id: str):
    try:
        return jsonify(lock_period(_uuid_arg(period_id, "period id"), current_user(), unlock=True))
    except TimeApiError as exc:
        return _err(exc)


@bp.post("/periods/<period_id>/export")
def post_period_export(period_id: str):
    try:
        return jsonify(export_period(_uuid_arg(period_id, "period id"), current_user()))
    except TimeApiError as exc:
        return _err(exc)


@bp.get("/periods/<period_id>/pdf")
def get_period_pdf(period_id: str):
    try:
        html = period_pdf_html(_uuid_arg(period_id, "period id"), current_user())
        return Response(html, mimetype="text/html")
    except TimeApiError as exc:
        return _err(exc)


@bp.get("/cost-codes")
def get_cost_codes():
    try:
        return jsonify(list_time_cost_codes(current_user(), _parse_uuid(request.args.get("project_id"))))
    except TimeApiError as exc:
        return _err(exc)


@bp.post("/cost-codes")
def post_cost_code():
    try:
        return jsonify(upsert_time_cost_code(_json(), current_user())), 201
    except TimeApiError as exc:
        return _err(exc)


@bp.patch("/cost-codes/<code_id>")
def patch_cost_code(code_id: str):
    try:
        return jsonify(upsert_time_cost_code(_json(), current_user(), _uuid_arg(code_id, "cost code")))
    except TimeApiError as exc:
        return _err(exc)


@bp.get("/projects/<project_id>/geofence")
def get_project_geofence(project_id: str):
    try:
        return jsonify(get_geofence(_uuid_arg(project_id, "project id"), current_user()))
    except TimeApiError as exc:
        return _err(exc)


@bp.put("/projects/<project_id>/geofence")
def put_project_geofence(project_id: str):
    try:
        return jsonify(put_geofence(_uuid_arg(project_id, "project id"), _json(), current_user()))
    except TimeApiError as exc:
        return _err(exc)


@bp.get("/map")
def get_map():
    try:
        return jsonify(map_live(current_user(), request.args))
    except TimeApiError as exc:
        return _err(exc)


@bp.get("/job-cost")
def get_job_cost():
    try:
        pid = _parse_uuid(request.args.get("project_id"))
        if pid is None:
            raise TimeApiError("project_id is required", 400)
        d0 = _date_arg(request.args["from"]) if request.args.get("from") else None
        d1 = _date_arg(request.args["to"]) if request.args.get("to") else None
        return jsonify(job_cost(current_user(), pid, d0, d1))
    except TimeApiError as exc:
        return _err(exc)


@bp.get("/projects/<project_id>/manpower-prefill")
def get_manpower(project_id: str):
    try:
        day = _date_arg(request.args.get("date") or date.today().isoformat())
        return jsonify(manpower_prefill(_uuid_arg(project_id, "project id"), day, current_user()))
    except TimeApiError as exc:
        return _err(exc)


@bp.get("/settings")
def get_time_settings():
    try:
        return jsonify(get_settings(current_user()))
    except TimeApiError as exc:
        return _err(exc)


@bp.put("/settings")
def put_time_settings():
    try:
        return jsonify(put_settings(_json(), current_user()))
    except TimeApiError as exc:
        return _err(exc)
