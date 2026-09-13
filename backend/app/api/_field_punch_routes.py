"""Field punch-list routes on the v1 blueprint (`/api/v1/...`)."""
from __future__ import annotations

from flask import Blueprint, jsonify, request

from ._field_punch_service import (
    PunchFieldError,
    attach_punch_photo,
    create_or_get_punch_item,
    delete_punch_item,
    first_upload_file,
    get_punch_item,
    list_field_directory,
    list_field_locations,
    list_punch_items,
    notify_punch_item,
    patch_punch_item,
    set_punch_status,
)
from ._field_routes import _parse_uuid_param, _project_exists
from ._field_service import FieldApiError
from ._perms import current_user


def _err(exc: FieldApiError):
    body: dict = {"error": exc.message}
    field = getattr(exc, "field", None)
    if field:
        body["field"] = field
    return jsonify(body), exc.status


def register_field_punch_routes(bp: Blueprint) -> None:
    @bp.get("/projects/<project_id>/punch-items")
    def get_project_punch_items(project_id: str):
        pid = _parse_uuid_param(project_id)
        if not pid:
            return jsonify({"error": "invalid project id"}), 400
        if not _project_exists(pid):
            return jsonify({"error": "project not found"}), 404
        try:
            return jsonify(
                list_punch_items(
                    pid,
                    current_user(),
                    list_name=(request.args.get("list") or "all").strip() or "all",
                    status=(request.args.get("status") or "").strip() or None,
                )
            )
        except FieldApiError as exc:
            return _err(exc)

    @bp.post("/projects/<project_id>/punch-items")
    def post_project_punch_item(project_id: str):
        pid = _parse_uuid_param(project_id)
        if not pid:
            return jsonify({"error": "invalid project id"}), 400
        if not _project_exists(pid):
            return jsonify({"error": "project not found"}), 404
        data = request.get_json(silent=True) or {}
        if not isinstance(data, dict):
            return jsonify({"error": "JSON body required"}), 400
        try:
            body, status = create_or_get_punch_item(pid, data, current_user())
            return jsonify(body), status
        except FieldApiError as exc:
            return _err(exc)

    @bp.get("/punch-items/<item_id>")
    def get_one_punch_item(item_id: str):
        iid = _parse_uuid_param(item_id)
        if not iid:
            return jsonify({"error": "invalid punch item id"}), 400
        try:
            return jsonify(get_punch_item(iid, current_user()))
        except FieldApiError as exc:
            return _err(exc)

    @bp.patch("/punch-items/<item_id>")
    def patch_one_punch_item(item_id: str):
        iid = _parse_uuid_param(item_id)
        if not iid:
            return jsonify({"error": "invalid punch item id"}), 400
        data = request.get_json(silent=True) or {}
        if not isinstance(data, dict):
            return jsonify({"error": "JSON body required"}), 400
        try:
            return jsonify(patch_punch_item(iid, data, current_user()))
        except FieldApiError as exc:
            return _err(exc)

    @bp.delete("/punch-items/<item_id>")
    def delete_one_punch_item(item_id: str):
        iid = _parse_uuid_param(item_id)
        if not iid:
            return jsonify({"error": "invalid punch item id"}), 400
        try:
            return jsonify(delete_punch_item(iid, current_user()))
        except FieldApiError as exc:
            return _err(exc)

    @bp.post("/punch-items/<item_id>/status")
    def post_punch_item_status(item_id: str):
        iid = _parse_uuid_param(item_id)
        if not iid:
            return jsonify({"error": "invalid punch item id"}), 400
        data = request.get_json(silent=True) or {}
        if not isinstance(data, dict):
            return jsonify({"error": "JSON body required"}), 400
        try:
            return jsonify(set_punch_status(iid, data, current_user()))
        except FieldApiError as exc:
            return _err(exc)

    @bp.post("/punch-items/<item_id>/photos")
    def post_punch_item_photo(item_id: str):
        iid = _parse_uuid_param(item_id)
        if not iid:
            return jsonify({"error": "invalid punch item id"}), 400
        form = request.form.to_dict() if request.form else {}
        if request.is_json:
            extra = request.get_json(silent=True) or {}
            if isinstance(extra, dict):
                form.update({k: extra[k] for k in extra if extra[k] is not None})
        try:
            return jsonify(attach_punch_photo(iid, first_upload_file(request.files), form, current_user())), 201
        except FieldApiError as exc:
            return _err(exc)

    @bp.post("/punch-items/<item_id>/notify")
    def post_punch_item_notify(item_id: str):
        iid = _parse_uuid_param(item_id)
        if not iid:
            return jsonify({"error": "invalid punch item id"}), 400
        data = request.get_json(silent=True) or {}
        if not isinstance(data, dict):
            data = {}
        try:
            return jsonify(notify_punch_item(iid, data, current_user()))
        except FieldApiError as exc:
            return _err(exc)

    @bp.get("/projects/<project_id>/directory")
    def get_project_field_directory(project_id: str):
        pid = _parse_uuid_param(project_id)
        if not pid:
            return jsonify({"error": "invalid project id"}), 400
        if not _project_exists(pid):
            return jsonify({"error": "project not found"}), 404
        try:
            return jsonify(list_field_directory(pid, current_user()))
        except FieldApiError as exc:
            return _err(exc)

    @bp.get("/projects/<project_id>/locations")
    def get_project_field_locations(project_id: str):
        pid = _parse_uuid_param(project_id)
        if not pid:
            return jsonify({"error": "invalid project id"}), 400
        if not _project_exists(pid):
            return jsonify({"error": "project not found"}), 404
        try:
            return jsonify(list_field_locations(pid, current_user()))
        except FieldApiError as exc:
            return _err(exc)
