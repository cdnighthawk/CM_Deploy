"""GitHub issue webhooks — ask the reporter to confirm by closing.

Configure the repo webhook (Issues + Issue comments) to POST
``https://www.usiscm.com/api/webhooks/github`` with ``GITHUB_WEBHOOK_SECRET``.
Leave a ``Resolution:`` comment and keep the issue open. The employee closes it
from the email link to confirm it is resolved.
"""
from __future__ import annotations

import json

import httpx
from flask import Blueprint, current_app, jsonify, request

from ..services import feedback as feedback_svc
from ._notifications import public_app_origin, send_plain_notification_email

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
    if event not in {"issues", "issue_comment"}:
        return jsonify({"ok": True, "status": "ignored", "reason": event or "unknown_event"})

    try:
        body = json.loads(payload.decode("utf-8") or "null")
    except (UnicodeDecodeError, json.JSONDecodeError):
        body = None
    if not isinstance(body, dict):
        return jsonify({"error": "JSON body required"}), 400

    confirm_base_url = f"{public_app_origin()}/usis-issue-confirm.html"
    with httpx.Client(timeout=15.0) as client:
        result = feedback_svc.handle_github_feedback_event(
            event=event,
            payload=body,
            config=current_app.config,
            send_email=send_plain_notification_email,
            confirm_base_url=confirm_base_url,
            secret_key=str(current_app.config.get("SECRET_KEY") or ""),
            client=client,
        )
    status = 502 if not result.get("ok") else 200
    return jsonify(result), status
