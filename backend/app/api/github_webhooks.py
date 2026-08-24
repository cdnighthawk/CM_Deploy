"""GitHub issue webhooks — email the reporter when their issue is closed.

Configure the repo webhook (Issues events) to POST
``https://www.usiscm.com/api/webhooks/github`` with ``GITHUB_WEBHOOK_SECRET``.
When closing, leave a comment that starts with ``Resolution:`` so the employee
gets the fix / won't-fix explanation.
"""
from __future__ import annotations

import json

import httpx
from flask import Blueprint, current_app, jsonify, request

from ..services import feedback as feedback_svc
from ._notifications import send_plain_notification_email

bp = Blueprint("github_webhooks", __name__)


@bp.post("/api/webhooks/github")
def github_webhook():
    secret = str(current_app.config.get("GITHUB_WEBHOOK_SECRET") or "").strip()
    if not secret:
        return jsonify({"error": "GITHUB_WEBHOOK_SECRET is not configured"}), 503

    payload = request.get_data(cache=True)
    signature = request.headers.get("X-Hub-Signature-256") or ""
    if not feedback_svc.verify_github_signature(
        secret=secret, payload=payload, signature_header=signature
    ):
        return jsonify({"error": "Invalid webhook signature"}), 400

    event = (request.headers.get("X-GitHub-Event") or "").strip()
    if event == "ping":
        return jsonify({"ok": True, "pong": True})
    if event != "issues":
        return jsonify({"ok": True, "status": "ignored", "reason": event or "unknown_event"})

    try:
        body = json.loads(payload.decode("utf-8") or "null")
    except (UnicodeDecodeError, json.JSONDecodeError):
        body = None
    if not isinstance(body, dict):
        return jsonify({"error": "JSON body required"}), 400

    with httpx.Client(timeout=15.0) as client:
        result = feedback_svc.notify_reporter_for_closed_issue(
            payload=body,
            config=current_app.config,
            send_email=send_plain_notification_email,
            client=client,
        )
    status = 502 if not result.get("ok") else 200
    return jsonify(result), status
