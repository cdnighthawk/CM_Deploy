"""Issues tracker routes on the existing v1 blueprint."""
from __future__ import annotations

from flask import Blueprint, request

from ._issue_service import (
    assign_issue,
    create_co_from_issue,
    create_issue,
    create_rfi_from_issue,
    get_issue,
    list_issues,
    update_status,
)
from ._perms import current_user
from .v1 import _jsonify, _parse_uuid_param, _project_exists


def register_issue_routes(bp: Blueprint) -> None:
    @bp.get("/issues")
    def list_all_issues():
        project_id = _parse_uuid_param(request.args.get("project_id") or request.args.get("projectId"))
        if project_id and not _project_exists(project_id):
            return _jsonify({"error": "project not found"}), 404
        payload = list_issues(
            {
                "project_id": project_id,
                "status": request.args.get("status"),
                "severity": request.args.get("severity"),
                "trade": request.args.get("trade"),
                "source_type": request.args.get("source_type") or request.args.get("sourceType"),
                "search": request.args.get("search") or request.args.get("q"),
            },
            current_user(),
        )
        return _jsonify(payload)

    @bp.get("/issues/summary")
    def issues_summary():
        project_id = _parse_uuid_param(request.args.get("project_id") or request.args.get("projectId"))
        payload = list_issues({"project_id": project_id}, current_user())
        return _jsonify({"summary": payload.get("summary"), "entity": "issues_summary"})

    @bp.get("/projects/<project_id>/issues")
    def list_project_issues(project_id: str):
        pid = _parse_uuid_param(project_id)
        if not pid:
            return _jsonify({"error": "invalid project id"}), 400
        if not _project_exists(pid):
            return _jsonify({"error": "project not found"}), 404
        payload = list_issues(
            {
                "project_id": pid,
                "status": request.args.get("status"),
                "severity": request.args.get("severity"),
                "trade": request.args.get("trade"),
                "source_type": request.args.get("source_type") or request.args.get("sourceType"),
                "search": request.args.get("search") or request.args.get("q"),
            },
            current_user(),
        )
        return _jsonify(payload)

    @bp.post("/issues")
    @bp.post("/projects/<project_id>/issues")
    def create_tracker_issue(project_id: str | None = None):
        data = request.get_json(silent=True) or {}
        if not isinstance(data, dict):
            return _jsonify({"error": "expected JSON object body"}), 400
        if project_id and not data.get("project_id"):
            data = {**data, "project_id": project_id}
        pid = _parse_uuid_param(str(data.get("project_id") or ""))
        if pid and not _project_exists(pid):
            return _jsonify({"error": "project not found"}), 404
        try:
            issue = create_issue(data, current_user())
        except ValueError as exc:
            return _jsonify({"error": str(exc)}), 400
        return _jsonify({"issue": issue, "entity": "issue"}), 201

    @bp.get("/issues/<issue_id>")
    def get_tracker_issue(issue_id: str):
        iid = _parse_uuid_param(issue_id)
        if not iid:
            return _jsonify({"error": "invalid issue id"}), 400
        issue = get_issue(iid)
        if not issue:
            return _jsonify({"error": "issue not found"}), 404
        return _jsonify({"issue": issue, "entity": "issue"})

    @bp.patch("/issues/<issue_id>/status")
    def patch_tracker_issue_status(issue_id: str):
        iid = _parse_uuid_param(issue_id)
        if not iid:
            return _jsonify({"error": "invalid issue id"}), 400
        data = request.get_json(silent=True) or {}
        try:
            issue = update_status(iid, str(data.get("status") or ""), current_user())
        except ValueError as exc:
            return _jsonify({"error": str(exc)}), 400
        except KeyError:
            return _jsonify({"error": "issue not found"}), 404
        return _jsonify({"issue": issue, "entity": "issue"})

    @bp.post("/issues/<issue_id>/assign")
    def assign_tracker_issue(issue_id: str):
        iid = _parse_uuid_param(issue_id)
        if not iid:
            return _jsonify({"error": "invalid issue id"}), 400
        data = request.get_json(silent=True) or {}
        raw = data.get("assignee_id") or data.get("assigneeId")
        assignee_id = _parse_uuid_param(str(raw)) if raw else None
        try:
            issue = assign_issue(iid, assignee_id, current_user())
        except KeyError:
            return _jsonify({"error": "issue not found"}), 404
        return _jsonify({"issue": issue, "entity": "issue"})

    @bp.post("/issues/<issue_id>/create-rfi")
    def create_rfi_from_tracker_issue(issue_id: str):
        iid = _parse_uuid_param(issue_id)
        if not iid:
            return _jsonify({"error": "invalid issue id"}), 400
        try:
            return _jsonify(create_rfi_from_issue(iid, current_user()))
        except KeyError:
            return _jsonify({"error": "issue not found"}), 404

    @bp.post("/issues/<issue_id>/create-co")
    def create_co_from_tracker_issue(issue_id: str):
        iid = _parse_uuid_param(issue_id)
        if not iid:
            return _jsonify({"error": "invalid issue id"}), 400
        try:
            return _jsonify(create_co_from_issue(iid, current_user()))
        except KeyError:
            return _jsonify({"error": "issue not found"}), 404
