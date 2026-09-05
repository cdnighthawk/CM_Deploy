"""Staff /api/hires and public /api/public/hire token APIs.

Mapping: User is the employee directory; HirePacket holds PII. See
``backend/HIRE_MAPPING.md``.
"""
from __future__ import annotations

import uuid
from io import BytesIO

from flask import Blueprint, jsonify, request, send_file

from ..services.hire_forms import I9_LIST_PRESETS, NOTICE_KEYS
from ._hire_service import (
    HireApiError,
    artifact_bytes,
    create_packet,
    directory,
    get_packet,
    get_settings_public,
    invite_packet,
    is_hr_full,
    i9_zip,
    link_user,
    list_audit,
    list_packets,
    lock_packet,
    packet_by_token,
    patch_packet,
    patch_settings,
    payroll_zip,
    payroll_flags,
    preview_pdf,
    public_get,
    public_patch,
    public_sign,
    require_hr_full,
    require_public_https,
    reveal_ssn,
    run_reminders,
    save_i9_copy,
    save_section2,
    save_voided_check,
    send_back,
    send_login,
    serialize_detail,
    void_packet,
)
from ._perms import current_user

bp = Blueprint("api_hires", __name__)


def _err(exc: HireApiError):
    payload = {"error": exc.message}
    extra = getattr(exc, "extra", None) or {}
    if extra:
        payload.update(extra)
    return jsonify(payload), exc.status


def _json() -> dict:
    data = request.get_json(silent=True) or {}
    return data if isinstance(data, dict) else {}


def _uuid(raw: str) -> uuid.UUID:
    try:
        return uuid.UUID(str(raw))
    except ValueError as exc:
        raise HireApiError("invalid id", 400) from exc


@bp.get("/api/hires")
def api_list():
    try:
        return jsonify(list_packets(current_user(), dict(request.args)))
    except HireApiError as exc:
        return _err(exc)


@bp.post("/api/hires")
def api_create():
    try:
        row = create_packet(_json(), current_user())
        return jsonify(serialize_detail(row, current_user())), 201
    except HireApiError as exc:
        return _err(exc)


@bp.get("/api/hires/settings")
def api_get_settings():
    try:
        require_hr_full(current_user())
        return jsonify(get_settings_public(reveal_secrets=False))
    except HireApiError as exc:
        return _err(exc)


@bp.patch("/api/hires/settings")
def api_patch_settings():
    try:
        return jsonify(patch_settings(_json(), current_user()))
    except HireApiError as exc:
        return _err(exc)


@bp.get("/api/hires/directory")
def api_directory():
    try:
        return jsonify(directory(current_user()))
    except HireApiError as exc:
        return _err(exc)


@bp.post("/api/hires/reminders/run")
def api_reminders():
    from ._integration_bc import cron_secret_matches
    from flask import current_app

    cu = current_user()
    if not (cu.is_dev_admin or is_hr_full(cu) or cron_secret_matches(request, current_app)):
        return jsonify({"error": "forbidden"}), 403
    return jsonify(run_reminders())


@bp.get("/api/hires/meta")
def api_meta():
    return jsonify(
        {
            "i9_presets": I9_LIST_PRESETS,
            "notices": [{"key": k, "title": t} for k, t in NOTICE_KEYS],
        }
    )


@bp.get("/api/hires/<pid>")
def api_get(pid: str):
    try:
        packet = get_packet(_uuid(pid))
        return jsonify(serialize_detail(packet, current_user()))
    except HireApiError as exc:
        return _err(exc)


@bp.patch("/api/hires/<pid>")
def api_patch(pid: str):
    try:
        packet = patch_packet(get_packet(_uuid(pid)), _json(), current_user())
        return jsonify(serialize_detail(packet, current_user()))
    except HireApiError as exc:
        return _err(exc)


@bp.post("/api/hires/<pid>/invite")
def api_invite(pid: str):
    try:
        return jsonify(invite_packet(get_packet(_uuid(pid)), current_user()))
    except HireApiError as exc:
        return _err(exc)


@bp.post("/api/hires/<pid>/resend")
def api_resend(pid: str):
    try:
        return jsonify(invite_packet(get_packet(_uuid(pid)), current_user(), resend=True))
    except HireApiError as exc:
        return _err(exc)


@bp.post("/api/hires/<pid>/void")
def api_void(pid: str):
    try:
        data = _json()
        packet = void_packet(get_packet(_uuid(pid)), str(data.get("reason") or ""), current_user())
        return jsonify(serialize_detail(packet, current_user()))
    except HireApiError as exc:
        return _err(exc)


@bp.post("/api/hires/<pid>/send-back")
def api_send_back(pid: str):
    try:
        packet = send_back(get_packet(_uuid(pid)), str(_json().get("note") or ""), current_user())
        return jsonify(serialize_detail(packet, current_user()))
    except HireApiError as exc:
        return _err(exc)


@bp.post("/api/hires/<pid>/lock")
def api_lock(pid: str):
    try:
        packet = lock_packet(get_packet(_uuid(pid)), current_user())
        return jsonify(serialize_detail(packet, current_user()))
    except HireApiError as exc:
        return _err(exc)


@bp.post("/api/hires/<pid>/reveal-ssn")
def api_reveal(pid: str):
    try:
        return jsonify(reveal_ssn(get_packet(_uuid(pid)), current_user()))
    except HireApiError as exc:
        return _err(exc)


@bp.post("/api/hires/<pid>/i9/section2")
def api_i9_s2(pid: str):
    try:
        packet = save_section2(get_packet(_uuid(pid)), _json(), current_user())
        return jsonify(serialize_detail(packet, current_user()))
    except HireApiError as exc:
        return _err(exc)


@bp.post("/api/hires/<pid>/i9/copies")
def api_i9_copy(pid: str):
    try:
        f = request.files.get("file")
        if f is None or not f.filename:
            raise HireApiError("file is required")
        return jsonify(save_i9_copy(get_packet(_uuid(pid)), f, request.form.get("list_kind") or "A", current_user()))
    except HireApiError as exc:
        return _err(exc)


@bp.post("/api/hires/<pid>/link-user")
def api_link(pid: str):
    try:
        return jsonify(link_user(get_packet(_uuid(pid)), current_user()))
    except HireApiError as exc:
        return _err(exc)


@bp.post("/api/hires/<pid>/send-login")
def api_send_login(pid: str):
    try:
        return jsonify(send_login(get_packet(_uuid(pid)), current_user()))
    except HireApiError as exc:
        return _err(exc)


@bp.post("/api/hires/<pid>/payroll-flags")
def api_flags(pid: str):
    try:
        packet = payroll_flags(get_packet(_uuid(pid)), _json(), current_user())
        return jsonify(serialize_detail(packet, current_user()))
    except HireApiError as exc:
        return _err(exc)


@bp.get("/api/hires/<pid>/payroll-packet")
@bp.get("/api/hires/<pid>/payroll-packet.zip")
def api_payroll_zip(pid: str):
    try:
        packet = get_packet(_uuid(pid))
        payload = payroll_zip(packet, current_user())
        return send_file(
            BytesIO(payload),
            mimetype="application/zip",
            as_attachment=True,
            download_name="payroll-setup.zip",
        )
    except HireApiError as exc:
        return _err(exc)


@bp.get("/api/hires/<pid>/i9-packet")
@bp.get("/api/hires/<pid>/i9-packet.zip")
def api_i9_zip(pid: str):
    try:
        packet = get_packet(_uuid(pid))
        payload = i9_zip(packet, current_user())
        return send_file(
            BytesIO(payload),
            mimetype="application/zip",
            as_attachment=True,
            download_name="i9-packet.zip",
        )
    except HireApiError as exc:
        return _err(exc)


@bp.get("/api/hires/<pid>/preview/<form_key>")
def api_staff_preview(pid: str, form_key: str):
    try:
        cu = current_user()
        require_hr_full(cu)
        packet = get_packet(_uuid(pid))
        payload, name = preview_pdf(packet, form_key, draft=not bool(packet.employee_signed_at))
        return send_file(BytesIO(payload), mimetype="application/pdf", as_attachment=False, download_name=name)
    except HireApiError as exc:
        return _err(exc)


@bp.get("/api/hires/<pid>/audit")
def api_audit(pid: str):
    try:
        return jsonify(list_audit(get_packet(_uuid(pid)), current_user()))
    except HireApiError as exc:
        return _err(exc)


@bp.get("/api/public/hire/<token>")
def pub_get(token: str):
    try:
        return jsonify(public_get(token))
    except HireApiError as exc:
        return _err(exc)


@bp.patch("/api/public/hire/<token>")
def pub_patch(token: str):
    try:
        return jsonify(public_patch(token, _json()))
    except HireApiError as exc:
        return _err(exc)


@bp.post("/api/public/hire/<token>/sign")
def pub_sign(token: str):
    try:
        return jsonify(public_sign(token, _json()))
    except HireApiError as exc:
        return _err(exc)


@bp.post("/api/public/hire/<token>/voided-check")
def pub_voided_check(token: str):
    try:
        f = request.files.get("file")
        if f is None or not f.filename:
            raise HireApiError("file is required")
        return jsonify(save_voided_check(token, f))
    except HireApiError as exc:
        return _err(exc)


@bp.get("/api/public/hire/<token>/preview/<form_key>")
def pub_preview(token: str, form_key: str):
    try:
        require_public_https()
        packet = packet_by_token(token)
        payload, name, mime = artifact_bytes(packet, form_key, None, allow_public=True)
        return send_file(BytesIO(payload), mimetype=mime, as_attachment=False, download_name=name)
    except HireApiError as exc:
        return _err(exc)


@bp.get("/api/public/hire/<token>/packet")
def pub_packet(token: str):
    try:
        require_public_https()
        packet = packet_by_token(token)
        if not packet.employee_signed_at:
            raise HireApiError("packet is not signed yet", 409)
        payload, name = preview_pdf(packet, "w4", draft=False)
        # signed packet download is the frozen PDFs as a zip built without SSN CSV
        from ._hire_service import preview_pdf as _prev
        import zipfile

        buf = BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for key in ("w4", "i9", "de4", "dd_auth", "notices"):
                body, fname = _prev(packet, key, draft=False)
                zf.writestr(fname, body)
        return send_file(BytesIO(buf.getvalue()), mimetype="application/zip", as_attachment=True, download_name="signed-packet.zip")
    except HireApiError as exc:
        return _err(exc)
