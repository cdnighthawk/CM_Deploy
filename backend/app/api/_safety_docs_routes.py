"""Register safety document profile and packet routes on the v1 blueprint."""
from __future__ import annotations

from flask import Blueprint, Response, jsonify, request

from ._perms import current_user
from ._safety_docs_service import (
    get_company_doc,
    get_company_profile,
    get_packet,
    get_packet_html,
    get_project_profile,
    list_company_docs,
    publish_packet,
    put_company_profile,
    put_project_profile,
    regenerate_company_docs,
    regenerate_packet,
)
from ._safety_service import SafetyApiError


def _parse_uuid_param(raw: str | None):
    if not raw or not str(raw).strip():
        return None
    import uuid

    try:
        return uuid.UUID(str(raw).strip())
    except ValueError:
        return None


def _err(exc: SafetyApiError):
    return jsonify({"error": exc.message}), exc.status


def _json_body():
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return None
    return data


def _wants_html() -> bool:
    if (request.args.get("format") or "").strip().lower() == "html":
        return True
    accept = (request.headers.get("Accept") or "").lower()
    return "text/html" in accept and "application/json" not in accept.split(";")[0]


def register_safety_docs_routes(bp: Blueprint) -> None:
    @bp.get("/safety/company-profile")
    def get_safety_company_profile():
        try:
            return jsonify(get_company_profile(current_user()))
        except SafetyApiError as exc:
            return _err(exc)

    @bp.put("/safety/company-profile")
    def put_safety_company_profile():
        data = _json_body()
        if data is None:
            return jsonify({"error": "JSON body required"}), 400
        try:
            return jsonify(put_company_profile(data, current_user()))
        except SafetyApiError as exc:
            return _err(exc)

    @bp.post("/safety/company-docs/regenerate")
    def post_safety_company_docs_regenerate():
        try:
            return jsonify(regenerate_company_docs(current_user()))
        except SafetyApiError as exc:
            return _err(exc)

    @bp.get("/safety/company-docs")
    def get_safety_company_docs():
        try:
            return jsonify(list_company_docs(current_user()))
        except SafetyApiError as exc:
            return _err(exc)

    @bp.get("/safety/company-docs/<slug>")
    def get_safety_company_doc(slug: str):
        try:
            body = get_company_doc(slug, current_user())
        except SafetyApiError as exc:
            return _err(exc)
        if _wants_html():
            html = body["item"].get("html") or ""
            return Response(html, mimetype="text/html; charset=utf-8")
        return jsonify(body)

    @bp.get("/projects/<project_id>/safety-profile")
    def get_project_safety_profile(project_id: str):
        pid = _parse_uuid_param(project_id)
        if not pid:
            return jsonify({"error": "invalid project id"}), 400
        try:
            return jsonify(get_project_profile(pid, current_user()))
        except SafetyApiError as exc:
            return _err(exc)

    @bp.put("/projects/<project_id>/safety-profile")
    def put_project_safety_profile(project_id: str):
        pid = _parse_uuid_param(project_id)
        if not pid:
            return jsonify({"error": "invalid project id"}), 400
        data = _json_body()
        if data is None:
            return jsonify({"error": "JSON body required"}), 400
        try:
            return jsonify(put_project_profile(pid, data, current_user()))
        except SafetyApiError as exc:
            return _err(exc)

    @bp.post("/projects/<project_id>/safety-packet/regenerate")
    def post_project_safety_packet_regenerate(project_id: str):
        pid = _parse_uuid_param(project_id)
        if not pid:
            return jsonify({"error": "invalid project id"}), 400
        try:
            return jsonify(regenerate_packet(pid, current_user()))
        except SafetyApiError as exc:
            return _err(exc)

    @bp.get("/projects/<project_id>/safety-packet")
    def get_project_safety_packet(project_id: str):
        pid = _parse_uuid_param(project_id)
        if not pid:
            return jsonify({"error": "invalid project id"}), 400
        try:
            return jsonify(get_packet(pid, current_user()))
        except SafetyApiError as exc:
            return _err(exc)

    @bp.get("/projects/<project_id>/safety-packet/preview")
    def get_project_safety_packet_preview(project_id: str):
        pid = _parse_uuid_param(project_id)
        if not pid:
            return jsonify({"error": "invalid project id"}), 400
        try:
            html = get_packet_html(pid, current_user())
        except SafetyApiError as exc:
            return _err(exc)
        return Response(html, mimetype="text/html; charset=utf-8")

    @bp.post("/projects/<project_id>/safety-packet/publish")
    def post_project_safety_packet_publish(project_id: str):
        pid = _parse_uuid_param(project_id)
        if not pid:
            return jsonify({"error": "invalid project id"}), 400
        try:
            return jsonify(publish_packet(pid, current_user()))
        except SafetyApiError as exc:
            return _err(exc)
