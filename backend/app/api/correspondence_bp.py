"""Correspondence file register + Graph ingest."""
from __future__ import annotations

from typing import Any

from flask import Blueprint, request

from ._perms import current_user
from ._rfi_service import ApiError, _parse_uuid
from . import _correspondence_service as corr

correspondence_bp = Blueprint("correspondence_api", __name__, url_prefix="/api/correspondence")


def _jsonify(obj: Any):
    from flask import jsonify

    return jsonify(obj)


def _err(exc: ApiError):
    return _jsonify({"error": exc.message}), exc.status


@correspondence_bp.get("")
def list_correspondence():
    try:
        return _jsonify(corr.list_items(current_user(), request.args))
    except ApiError as exc:
        return _err(exc)


@correspondence_bp.post("")
def create_correspondence_local():
    data = request.get_json(silent=True) or {}
    try:
        return _jsonify(corr.ingest_local_message(data, current_user())), 201
    except ApiError as exc:
        return _err(exc)


@correspondence_bp.post("/sync")
def sync_correspondence():
    try:
        return _jsonify(corr.sync_mailboxes(cu=current_user()))
    except ApiError as exc:
        return _err(exc)


@correspondence_bp.post("/<item_id>/file")
def file_correspondence(item_id: str):
    iid = _parse_uuid(item_id)
    if iid is None:
        return _jsonify({"error": "invalid id"}), 400
    data = request.get_json(silent=True) or {}
    pid = _parse_uuid(data.get("project_id"))
    if pid is None:
        return _jsonify({"error": "project_id required"}), 400
    try:
        return _jsonify(corr.file_to_project(iid, pid, current_user()))
    except ApiError as exc:
        return _err(exc)


@correspondence_bp.get("/<item_id>/download")
def download_correspondence(item_id: str):
    iid = _parse_uuid(item_id)
    if iid is None:
        return _jsonify({"error": "invalid id"}), 400
    try:
        return corr.download_message(iid, current_user())
    except ApiError as exc:
        return _err(exc)
