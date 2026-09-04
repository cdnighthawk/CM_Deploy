"""Accounts payable API under ``/api/v1/ap``."""
from __future__ import annotations

import uuid

from flask import Blueprint, jsonify, request

from ..api._perms import current_user
from ._invoice_service import InvoiceError
from ._invoice_service import (
    approve_invoice,
    create_invoice,
    get_invoice,
    list_approvals,
    list_commitments,
    list_invoices,
    list_projects,
    list_vendors,
    mark_paid,
    reject_invoice,
    send_file,
    submit_invoice,
    sync_mailbox,
    update_invoice,
    upload_file,
    void_invoice,
)
from ._mailbox import invoice_mailbox, mailbox_ready

ap_bp = Blueprint("ap", __name__, url_prefix="/api/v1/ap")


def _handle(fn):
    try:
        return fn()
    except InvoiceError as exc:
        return jsonify({"error": exc.message, "entity": "vendor_invoice"}), exc.status


def _parse_uuid(raw: str | None) -> uuid.UUID | None:
    if not raw:
        return None
    try:
        return uuid.UUID(str(raw).strip())
    except (ValueError, TypeError):
        return None


@ap_bp.get("/health")
def ap_health():
    return jsonify({"status": "ok", "module": "ap"})


@ap_bp.get("/mailbox")
def ap_mailbox_status():
    return jsonify(
        {
            "entity": "ap_mailbox",
            "item": {"mailbox": invoice_mailbox(), "graph_configured": mailbox_ready()},
        }
    )


@ap_bp.post("/mailbox/sync")
def ap_mailbox_sync():
    from flask import current_app

    from ..api._integration_bc import cron_secret_matches

    cu = current_user()
    as_cron = cron_secret_matches(request, current_app)
    return _handle(
        lambda: jsonify({"entity": "ap_mailbox_sync", "item": sync_mailbox(cu, as_cron=as_cron)})
    )


@ap_bp.get("/lookups/vendors")
def ap_vendors():
    q = (request.args.get("q") or "").strip() or None
    return jsonify({"entity": "ap_vendors", "items": list_vendors(q)})


@ap_bp.get("/lookups/projects")
def ap_projects():
    q = (request.args.get("q") or "").strip() or None
    return jsonify({"entity": "ap_projects", "items": list_projects(current_user(), q)})


@ap_bp.get("/lookups/commitments")
def ap_commitments():
    pid = _parse_uuid(request.args.get("project_id"))
    vid = _parse_uuid(request.args.get("vendor_company_id"))
    return _handle(
        lambda: jsonify({"entity": "ap_commitments", "items": list_commitments(current_user(), pid, vid)})
    )


@ap_bp.get("/invoices")
def ap_invoices_list():
    status = (request.args.get("status") or "").strip() or None
    pid = _parse_uuid(request.args.get("project_id"))
    return jsonify({"entity": "vendor_invoices", "items": list_invoices(current_user(), status=status, project_id=pid)})


@ap_bp.get("/invoices/approvals")
def ap_invoices_approvals():
    return jsonify({"entity": "vendor_invoice_approvals", "items": list_approvals(current_user())})


@ap_bp.post("/invoices")
def ap_invoices_create():
    data = request.get_json(silent=True) or {}
    return _handle(lambda: jsonify({"entity": "vendor_invoice", "item": create_invoice(current_user(), data)}))


@ap_bp.get("/invoices/<uuid:invoice_id>")
def ap_invoice_detail(invoice_id: uuid.UUID):
    return _handle(lambda: jsonify({"entity": "vendor_invoice", "item": get_invoice(current_user(), invoice_id)}))


@ap_bp.patch("/invoices/<uuid:invoice_id>")
def ap_invoice_patch(invoice_id: uuid.UUID):
    data = request.get_json(silent=True) or {}
    return _handle(lambda: jsonify({"entity": "vendor_invoice", "item": update_invoice(current_user(), invoice_id, data)}))


@ap_bp.post("/invoices/<uuid:invoice_id>/submit")
def ap_invoice_submit(invoice_id: uuid.UUID):
    data = request.get_json(silent=True) or {}
    return _handle(lambda: jsonify({"entity": "vendor_invoice", "item": submit_invoice(current_user(), invoice_id, data)}))


@ap_bp.post("/invoices/<uuid:invoice_id>/approve")
def ap_invoice_approve(invoice_id: uuid.UUID):
    return _handle(lambda: jsonify({"entity": "vendor_invoice", "item": approve_invoice(current_user(), invoice_id)}))


@ap_bp.post("/invoices/<uuid:invoice_id>/reject")
def ap_invoice_reject(invoice_id: uuid.UUID):
    data = request.get_json(silent=True) or {}
    return _handle(lambda: jsonify({"entity": "vendor_invoice", "item": reject_invoice(current_user(), invoice_id, data)}))


@ap_bp.post("/invoices/<uuid:invoice_id>/mark-paid")
def ap_invoice_paid(invoice_id: uuid.UUID):
    data = request.get_json(silent=True) or {}
    return _handle(lambda: jsonify({"entity": "vendor_invoice", "item": mark_paid(current_user(), invoice_id, data)}))


@ap_bp.post("/invoices/<uuid:invoice_id>/void")
def ap_invoice_void(invoice_id: uuid.UUID):
    data = request.get_json(silent=True) or {}
    return _handle(lambda: jsonify({"entity": "vendor_invoice", "item": void_invoice(current_user(), invoice_id, data)}))


@ap_bp.post("/invoices/<uuid:invoice_id>/files")
def ap_invoice_upload(invoice_id: uuid.UUID):
    return _handle(lambda: jsonify({"entity": "vendor_invoice", "item": upload_file(current_user(), invoice_id)}))


@ap_bp.get("/invoices/<uuid:invoice_id>/files/<uuid:file_id>/file")
def ap_invoice_file(invoice_id: uuid.UUID, file_id: uuid.UUID):
    return _handle(lambda: send_file(current_user(), invoice_id, file_id))
