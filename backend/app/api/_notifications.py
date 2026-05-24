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


def enqueue_email(log: "RfiNotificationLog", *, subject: str, body: str, to: str) -> dict[str, object]:
    return _dispatch(log_id=str(log.id), subject=subject, body=body, to=to)


def _dispatch(*, log_id: str, subject: str, body: str, to: str) -> dict[str, object]:
    """Send or queue one message. Caller must ``flush()`` the log row so ``log_id`` is valid."""
    celery = _celery_app()
    if celery is not None:
        try:
            celery.send_task(
                "rfi.send_email",
                kwargs={"log_id": log_id, "subject": subject, "body": body, "to": to},
            )
            return {"sent": False, "dry_run": False, "queued": True, "error": None}
        except Exception:  # pragma: no cover
            current_app.logger.exception("Celery dispatch failed; falling back to sync")

    if not _smtp_configured():
        current_app.logger.info(
            "RFI email (SMTP unset, dry-run): to=%s subj=%r", to, subject
        )
        if log_id and log_id != "None":
            _mark_log_delivered(log_id)
        return {"sent": False, "dry_run": True, "queued": False, "error": None}

    try:
        _send_via_smtplib(subject=subject, body=body, to=to)
        if log_id and log_id != "None":
            _mark_log_delivered(log_id)
        return {"sent": True, "dry_run": False, "queued": False, "error": None}
    except Exception as exc:
        current_app.logger.warning("Failed to send RFI email to %s: %s", to, exc)
        if log_id and log_id != "None":
            _mark_log_delivered(log_id, error=str(exc))
        return {"sent": False, "dry_run": False, "queued": False, "error": str(exc)}


def _send_via_smtplib(
    *,
    subject: str,
    body: str,
    to: str,
    html_body: str | None = None,
) -> None:  # pragma: no cover - I/O
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
    if html_body:
        msg.add_alternative(html_body, subtype="html")

    with smtplib.SMTP(host, port, timeout=30) as s:
        if use_tls:
            s.starttls()
        if user:
            s.login(user, pw)
        s.send_message(msg)


def send_plain_notification_email(*, to: str, subject: str, body: str) -> dict[str, object]:
    """Best-effort synchronous SMTP for non-RFI events (playbooks, compose page, etc.).

    Celery is not used here: ``rfi.send_email`` expects an ``rfi_notification_log`` row.
    Returns ``{sent, dry_run, error}`` for API feedback.
    """
    return send_html_notification_email(to=to, subject=subject, body=body, html_body=None)


def send_html_notification_email(
    *,
    to: str,
    subject: str,
    body: str,
    html_body: str | None,
) -> dict[str, object]:
    """Best-effort synchronous SMTP with optional HTML alternative body."""
    if not to:
        return {"sent": False, "dry_run": False, "error": "missing recipient email"}
    if not _smtp_configured():
        current_app.logger.info("Plain email (SMTP unset, dry-run): to=%s subj=%r", to, subject)
        return {"sent": False, "dry_run": True, "error": None}

    try:
        _send_via_smtplib(subject=subject, body=body, to=to, html_body=html_body)
        return {"sent": True, "dry_run": False, "error": None}
    except Exception as exc:  # pragma: no cover - I/O
        current_app.logger.warning("Failed to send plain email to %s: %s", to, exc)
        return {"sent": False, "dry_run": False, "error": str(exc)}


def send_compose_email(
    *,
    to: str,
    subject: str,
    body: str,
    cc: str | None = None,
) -> dict[str, object]:
    """Send mail from the W3CRM compose page (``POST /api/v1/messages/email``)."""
    recipients = [s.strip() for s in to.split(",") if s.strip()]
    if cc:
        recipients.extend(s.strip() for s in cc.split(",") if s.strip())
    if not recipients:
        return {"ok": False, "error": "'to' must include at least one email address", "sent": 0}

    sent = 0
    dry_run = False
    queued = False
    errors: list[str] = []
    for em in recipients:
        result = send_plain_notification_email(to=em, subject=subject, body=body)
        if result.get("dry_run"):
            dry_run = True
        if result.get("sent"):
            sent += 1
        elif result.get("error"):
            errors.append(f"{em}: {result['error']}")
    return {
        "ok": sent > 0 or dry_run,
        "sent": sent,
        "dry_run": dry_run,
        "queued": queued,
        "errors": errors,
    }


def public_app_origin() -> str:
    """Public site origin for links in outbound mail (no trailing slash)."""
    from urllib.parse import urlparse

    explicit = (os.environ.get("USIS_APP_PUBLIC_URL") or "").strip().rstrip("/")
    if explicit:
        return explicit

    redirect = (current_app.config.get("USIS_POST_LOGIN_REDIRECT") or "").strip()
    if redirect:
        parsed = urlparse(redirect)
        if parsed.scheme and parsed.netloc:
            return f"{parsed.scheme}://{parsed.netloc}"

    render_base = (os.environ.get("RENDER_EXTERNAL_URL") or "").strip().rstrip("/")
    if render_base:
        return render_base

    return "http://127.0.0.1:5000"


def public_login_url() -> str:
    """Sign-in page URL for outbound mail (same origin as the static shell)."""
    return f"{public_app_origin()}/page-login.html"


def public_reset_password_url(token: str) -> str:
    from urllib.parse import quote

    return f"{public_app_origin()}/page-reset-password.html?token={quote(token, safe='')}"


def send_job_offer_email(
    *,
    to: str,
    applicant_name: str,
    html_body: str | None = None,
) -> dict[str, object]:
    """Email applicant with link to view and accept their job offer."""
    if not to:
        return {"ok": False, "error": "missing recipient email"}

    offer_url = f"{public_app_origin()}/apply/offer.html"
    display = applicant_name.strip() or "there"
    body = "\n".join(
        [
            f"Hello {display},",
            "",
            "We are pleased to extend a job offer to you. Please sign in to the USIS applicant portal "
            "to review the offer letter and accept if you wish to proceed.",
            "",
            f"View your offer: {offer_url}",
            "",
            "After you accept, you will complete I-9 and W-4 forms in the portal.",
            "",
            "If you did not apply for employment with us, you can ignore this message.",
        ]
    )
    return send_html_notification_email(
        to=to,
        subject="Your job offer from DOCOM, INC.",
        body=body,
        html_body=html_body,
    )


def send_application_rejection_letter_email(*, user, hire_row) -> dict[str, object]:
    """Email applicant a formal rejection letter after HR denies their application."""
    from ..services.hr_application_letters import (
        rejection_letter_plain_text,
        rejection_letter_subject,
        render_rejection_letter_html,
    )

    to = (getattr(user, "email", None) or "").strip()
    if not to or hire_row is None:
        return {"sent": False, "dry_run": False, "error": "missing recipient email"}

    return send_html_notification_email(
        to=to,
        subject=rejection_letter_subject(),
        body=rejection_letter_plain_text(user=user, hire_row=hire_row),
        html_body=render_rejection_letter_html(user=user, hire_row=hire_row),
    )


def send_application_approval_letter_email(*, user, hire_row) -> dict[str, object]:
    """Email applicant a formal approval / welcome letter after they are hired."""
    from ..services.hr_application_letters import (
        approval_letter_plain_text,
        approval_letter_subject,
        render_approval_letter_html,
    )

    to = (getattr(user, "email", None) or "").strip()
    if not to or hire_row is None:
        return {"sent": False, "dry_run": False, "error": "missing recipient email"}

    login_url = public_login_url()
    return send_html_notification_email(
        to=to,
        subject=approval_letter_subject(),
        body=approval_letter_plain_text(user=user, hire_row=hire_row, login_url=login_url),
        html_body=render_approval_letter_html(user=user, hire_row=hire_row, login_url=login_url),
    )


def send_password_reset_email(*, to: str, reset_token: str) -> dict[str, object]:
    """Send a single-use password reset link."""
    url = public_reset_password_url(reset_token)
    body = "\n".join(
        [
            "We received a request to reset your USIS account password.",
            "",
            f"Reset your password: {url}",
            "",
            "This link expires in one hour. If you did not request a reset, you can ignore this email.",
        ]
    )
    return send_plain_notification_email(
        to=to,
        subject="Reset your USIS password",
        body=body,
    )


def send_user_invite_email(
    *,
    to: str,
    login_url: str | None = None,
    temporary_password_set: bool = False,
    invited_by: str | None = None,
) -> None:
    """Best-effort invite when an admin creates a user (``POST /api/v1/admin/users``)."""
    url = login_url or public_login_url()
    lines = [
        "You have been invited to use USIS Construction Management.",
        "",
        f"Sign in: {url}",
        f"Email: {to}",
    ]
    if temporary_password_set:
        lines.extend(
            [
                "",
                "Your administrator set a temporary password. Sign in and change it under your profile.",
            ]
        )
    else:
        lines.extend(
            [
                "",
                "If you use Microsoft sign-in for your organization, choose “Sign in with Microsoft”.",
                "Otherwise ask your administrator for a password or to set one for you.",
            ]
        )
    if invited_by:
        lines.extend(["", f"— invited by {invited_by}"])
    subject = "You're invited to USIS Construction Management"
    send_plain_notification_email(to=to, subject=subject, body="\n".join(lines))


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
