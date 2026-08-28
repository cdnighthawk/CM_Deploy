"""Submittal QC + amendable workflow HTTP API."""
from __future__ import annotations

import uuid
from typing import Any

from flask import Blueprint, Response, request

from ._perms import current_user
from ._rfi_service import ApiError, _parse_uuid
from . import _submittal_qc as qc
from . import _workflow_service as wf
from ..submittals.checklist_templates import list_templates

submittals_bp = Blueprint("submittals_api", __name__, url_prefix="/api/submittals")
workflows_bp = Blueprint("workflows_api", __name__, url_prefix="/api/workflows")


def _jsonify(obj: Any):
    from flask import jsonify

    return jsonify(obj)


def _err(exc: ApiError):
    return _jsonify({"error": exc.message}), exc.status


def _sid(raw: str) -> uuid.UUID:
    sid = _parse_uuid(raw)
    if sid is None:
        raise ApiError("invalid id", 400)
    return sid


@submittals_bp.get("")
def list_submittals():
    try:
        return _jsonify(qc.list_register(current_user(), request.args))
    except ApiError as exc:
        return _err(exc)


@submittals_bp.get("/templates")
def get_templates():
    return _jsonify(
        list_templates(
            spec_section=request.args.get("spec_section"),
            trade=request.args.get("trade"),
        )
    )


@submittals_bp.get("/dashboard-summary")
def dashboard_summary():
    pid = _parse_uuid(request.args.get("project_id"))
    try:
        return _jsonify(qc.dashboard_summary(current_user(), pid))
    except ApiError as exc:
        return _err(exc)


@submittals_bp.post("")
def create_submittal():
    data = request.get_json(silent=True) or {}
    try:
        return _jsonify(qc.create_from_api(data, current_user())), 201
    except ApiError as exc:
        return _err(exc)


@submittals_bp.get("/<submittal_id>")
def get_submittal(submittal_id: str):
    try:
        return _jsonify(qc.get_detail(_sid(submittal_id), current_user()))
    except ApiError as exc:
        return _err(exc)


@submittals_bp.patch("/<submittal_id>")
def patch_submittal(submittal_id: str):
    data = request.get_json(silent=True) or {}
    try:
        return _jsonify(qc.patch_qc(_sid(submittal_id), data, current_user()))
    except ApiError as exc:
        return _err(exc)


@submittals_bp.post("/<submittal_id>/revisions")
def post_revision(submittal_id: str):
    try:
        return _jsonify(qc.create_revision(_sid(submittal_id), current_user())), 201
    except ApiError as exc:
        return _err(exc)


@submittals_bp.post("/<submittal_id>/revisions/<rev_id>/documents")
def post_revision_document(submittal_id: str, rev_id: str):
    data = request.get_json(silent=True) or {}
    try:
        return _jsonify(qc.attach_revision_document(_sid(submittal_id), _sid(rev_id), data, current_user())), 201
    except ApiError as exc:
        return _err(exc)


@submittals_bp.post("/<submittal_id>/revisions/<rev_id>/completeness")
def post_completeness(submittal_id: str, rev_id: str):
    try:
        return _jsonify(qc.recompute_completeness(_sid(submittal_id), _sid(rev_id), current_user()))
    except ApiError as exc:
        return _err(exc)


@submittals_bp.post("/<submittal_id>/revisions/<rev_id>/ai-review")
def post_ai_review(submittal_id: str, rev_id: str):
    data = request.get_json(silent=True) or {}
    try:
        return _jsonify(qc.persist_ai_review(_sid(submittal_id), _sid(rev_id), data, current_user()))
    except ApiError as exc:
        return _err(exc)


@submittals_bp.patch("/<submittal_id>/revisions/<rev_id>/checklist")
def patch_checklist(submittal_id: str, rev_id: str):
    data = request.get_json(silent=True) or {}
    try:
        return _jsonify(qc.patch_checklist(_sid(submittal_id), _sid(rev_id), data, current_user()))
    except ApiError as exc:
        return _err(exc)


@submittals_bp.post("/<submittal_id>/revisions/<rev_id>/stamp")
def post_stamp(submittal_id: str, rev_id: str):
    data = request.get_json(silent=True) or {}
    try:
        return _jsonify(qc.apply_stamp(_sid(submittal_id), _sid(rev_id), data, current_user()))
    except ApiError as exc:
        return _err(exc)


@submittals_bp.post("/<submittal_id>/assign")
def post_assign(submittal_id: str):
    data = request.get_json(silent=True) or {}
    try:
        return _jsonify(qc.assign_reviewer(_sid(submittal_id), data, current_user()))
    except ApiError as exc:
        return _err(exc)


@submittals_bp.post("/<submittal_id>/transmit-to-ae")
def post_transmit(submittal_id: str):
    data = request.get_json(silent=True) or {}
    try:
        return _jsonify(qc.transmit_to_ae(_sid(submittal_id), data, current_user()))
    except ApiError as exc:
        return _err(exc)


@submittals_bp.post("/<submittal_id>/ae-action")
def post_ae_action(submittal_id: str):
    data = request.get_json(silent=True) or {}
    try:
        return _jsonify(qc.log_ae_action(_sid(submittal_id), data, current_user()))
    except ApiError as exc:
        return _err(exc)


@submittals_bp.get("/<submittal_id>/controlled-copy")
def get_controlled_copy(submittal_id: str):
    try:
        html = qc.controlled_copy_html(_sid(submittal_id), current_user())
    except ApiError as exc:
        return _err(exc)
    return Response(html, mimetype="text/html")


@workflows_bp.get("/definitions")
def list_definitions():
    process_key = (request.args.get("process_key") or wf.PROCESS_SUBMITTAL_QC).strip()
    pid = _parse_uuid(request.args.get("project_id"))
    return _jsonify(wf.list_definitions(process_key, pid))


@workflows_bp.post("/definitions")
def publish_definition():
    data = request.get_json(silent=True) or {}
    try:
        definition = wf.publish_definition(data, current_user())
        return _jsonify(wf.definition_public(definition)), 201
    except ApiError as exc:
        return _err(exc)


@workflows_bp.get("/queues")
def list_queues():
    process_key = (request.args.get("process_key") or wf.PROCESS_SUBMITTAL_QC).strip()
    return _jsonify(wf.list_queues(process_key))


@workflows_bp.put("/queues/<queue_key>/members")
def put_queue_members(queue_key: str):
    data = request.get_json(silent=True) or {}
    process_key = str(data.get("process_key") or wf.PROCESS_SUBMITTAL_QC).strip()
    raw_ids = data.get("user_ids") or data.get("userIds") or []
    ids = []
    for x in raw_ids:
        uid = _parse_uuid(x)
        if uid:
            ids.append(uid)
    try:
        return _jsonify(wf.set_queue_members(process_key, queue_key, ids, current_user()))
    except ApiError as exc:
        return _err(exc)


@workflows_bp.post("/instances/<instance_id>/assign")
def assign_instance(instance_id: str):
    data = request.get_json(silent=True) or {}
    try:
        inst = wf.assign_instance_step(_sid(instance_id), data, current_user())
        return _jsonify(wf.instance_public(inst))
    except ApiError as exc:
        return _err(exc)
