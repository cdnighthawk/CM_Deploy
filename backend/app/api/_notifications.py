"""Email notification dispatch for the RFI tool.

Two paths are supported:

1. **Synchronous** (default in dev): a row is written to
   ``rfi_notification_log`` and, if Flask-Mail is configured (``MAIL_*``
   env vars), the email is sent inline. Otherwise the log row is the
   only record.

2. **Celery + Redis** (production): when ``CELERY_BROKER_URL`` is set
   and Celery is installed, emails are dispatched via the
   ``send_rfi_email_task`` background task so the HTTP request returns
   immediately.

Plug Procore's email triggers into the service layer by calling
``enqueue_rfi_email(log, rfi=...)`` from ``_rfi_service``.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from flask import current_app

if TYPE_CHECKING:
    from ..models import Rfi, RfiNotificationLog
    from ._perms import CurrentUser


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


def _smtp_configured() -> bool:
    return bool(
        os.environ.get("MAIL_SERVER")
        and os.environ.get("MAIL_USERNAME")
        and os.environ.get("MAIL_FROM")
    )


def _celery_app():  # pragma: no cover — optional dependency
    try:
        from ..celery_app import celery
    except Exception:
        return None
    return celery


def enqueue_rfi_email(
    log: "RfiNotificationLog",
    *,
    rfi: Optional["Rfi"] = None,
    actor: Optional["CurrentUser"] = None,
) -> None:
    """Schedule a Procore-style notification for an RFI event."""

    body_lines = []
    if rfi is not None:
        body_lines.append(f"RFI #{rfi.number} — {rfi.subject}")
        if rfi.question:
            body_lines.append("")
            body_lines.append("Question:")
            body_lines.append(rfi.question)
        if rfi.official_response:
            body_lines.append("")
            body_lines.append("Official Response:")
            body_lines.append(rfi.official_response)
    if actor is not None and actor.user is not None:
        body_lines.append("")
        body_lines.append(f"— sent by {actor.user.email}")
    body = "\n".join(body_lines)

    _dispatch(log_id=str(log.id), subject=log.subject or "RFI Update", body=body, to=log.recipient_email)


def enqueue_email(log: "RfiNotificationLog", *, subject: str, body: str, to: str) -> None:
    _dispatch(log_id=str(log.id), subject=subject, body=body, to=to)


def _dispatch(*, log_id: str, subject: str, body: str, to: str) -> None:
    celery = _celery_app()
    if celery is not None:
        try:
            celery.send_task(
                "rfi.send_email",
                kwargs={"log_id": log_id, "subject": subject, "body": body, "to": to},
            )
            return
        except Exception:  # pragma: no cover
            current_app.logger.exception("Celery dispatch failed; falling back to sync")

    if not _smtp_configured():
        current_app.logger.info(
            "RFI email (SMTP unset, dry-run): to=%s subj=%r", to, subject
        )
        _mark_log_delivered(log_id)
        return

    try:
        _send_via_smtplib(subject=subject, body=body, to=to)
        _mark_log_delivered(log_id)
    except Exception as exc:
        current_app.logger.warning("Failed to send RFI email to %s: %s", to, exc)
        _mark_log_delivered(log_id, error=str(exc))


def _send_via_smtplib(*, subject: str, body: str, to: str) -> None:  # pragma: no cover - I/O
    import smtplib
    from email.message import EmailMessage

    host = os.environ.get("MAIL_SERVER", "localhost")
    port = int(os.environ.get("MAIL_PORT") or "587")
    use_tls = (os.environ.get("MAIL_USE_TLS", "true").strip().lower() not in ("0", "false", "no", "off"))
    user = os.environ.get("MAIL_USERNAME") or ""
    pw = os.environ.get("MAIL_PASSWORD") or ""
    sender = os.environ.get("MAIL_FROM") or user

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = to
    msg.set_content(body)

    with smtplib.SMTP(host, port, timeout=30) as s:
        if use_tls:
            s.starttls()
        if user:
            s.login(user, pw)
        s.send_message(msg)


def send_plain_notification_email(*, to: str, subject: str, body: str) -> None:
    """Best-effort synchronous SMTP for non-RFI events (playbooks, etc.).

    Celery is not used here: ``rfi.send_email`` expects an ``rfi_notification_log`` row.
    """
    if not _smtp_configured():
        current_app.logger.info("Plain email (SMTP unset, dry-run): to=%s subj=%r", to, subject)
        return

    try:
        _send_via_smtplib(subject=subject, body=body, to=to)
    except Exception as exc:  # pragma: no cover - I/O
        current_app.logger.warning("Failed to send plain email to %s: %s", to, exc)


def _mark_log_delivered(log_id: str, *, error: Optional[str] = None) -> None:
    """Stamp ``rfi_notification_log.delivered_at`` / ``.error``."""
    from sqlalchemy import update

    from ..extensions import db
    from ..models import RfiNotificationLog

    stmt = (
        update(RfiNotificationLog)
        .where(RfiNotificationLog.id == log_id)
        .values(delivered_at=_utcnow() if error is None else None, error=error)
    )
    try:
        db.session.execute(stmt)
        db.session.flush()
    except Exception:  # pragma: no cover
        db.session.rollback()
        raise
