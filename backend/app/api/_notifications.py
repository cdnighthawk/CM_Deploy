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

import base64
import os
import time
import urllib.parse
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Optional

from flask import current_app

if TYPE_CHECKING:
    from ..models import Rfi, RfiNotificationLog
    from ._perms import CurrentUser

_graph_token_cache: dict[str, object] = {"token": None, "expires_at": 0.0}

_GRAPH_BASE = "https://graph.microsoft.com/v1.0"
_MAIL_LIST_SELECT = (
    "id,subject,from,toRecipients,receivedDateTime,sentDateTime,"
    "isRead,bodyPreview,hasAttachments"
)
_MAIL_DETAIL_SELECT = (
    "id,subject,from,toRecipients,ccRecipients,receivedDateTime,"
    "sentDateTime,isRead,body,bodyPreview,hasAttachments"
)
_MAIL_FOLDERS = {
    "inbox": "inbox",
    "sent": "sentitems",
    "drafts": "drafts",
    "deleted": "deleteditems",
}
_GRAPH_ROOT = _GRAPH_BASE
_MAIL_LIST_FIELDS = _MAIL_LIST_SELECT
_MAIL_DETAIL_FIELDS = _MAIL_DETAIL_SELECT
_MAIL_FOLDER_MAP = _MAIL_FOLDERS


class GraphMailError(Exception):
    """Microsoft Graph mail call failed."""

    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        super().__init__(message)


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


def _mail_from() -> str:
    return (os.environ.get("MAIL_FROM") or "").strip()


def _graph_configured() -> bool:
    """True when the Entra app can call Graph sendMail (any mailbox)."""
    transport = (os.environ.get("MAIL_TRANSPORT") or "auto").strip().lower()
    if transport == "smtp":
        return False
    return bool(
        (os.environ.get("MS_ENTRA_TENANT_ID") or "").strip()
        and (os.environ.get("MS_ENTRA_CLIENT_ID") or "").strip()
        and (os.environ.get("MS_ENTRA_CLIENT_SECRET") or "").strip()
    )


def _allowed_from_domains() -> set[str]:
    raw = (os.environ.get("MAIL_ALLOWED_FROM_DOMAINS") or "").strip()
    if raw:
        return {d.strip().lower() for d in raw.split(",") if d.strip()}
    out: set[str] = {"gousis.com"}
    try:
        for d in current_app.config.get("MS_ENTRA_ALLOWED_EMAIL_DOMAINS") or ():
            if d:
                out.add(str(d).strip().lower())
    except RuntimeError:
        pass
    system = _mail_from()
    if "@" in system:
        out.add(system.rsplit("@", 1)[-1].lower())
    return out


def _resolve_from(from_addr: str | None) -> str:
    """Mailbox Graph/SMTP send as. Staff mail uses the signed-in user; system mail uses MAIL_FROM."""
    candidate = (from_addr or "").strip() or _mail_from()
    if not candidate or "@" not in candidate:
        return _mail_from()
    domain = candidate.rsplit("@", 1)[-1].lower()
    if domain not in _allowed_from_domains():
        current_app.logger.warning("Refusing send-as %s; using MAIL_FROM", candidate)
        return _mail_from()
    return candidate


def _smtp_env_configured() -> bool:
    return bool(
        (os.environ.get("MAIL_SERVER") or "").strip()
        and (os.environ.get("MAIL_USERNAME") or "").strip()
        and _mail_from()
    )


def _mail_configured(*, from_addr: str | None = None) -> bool:
    sender = _resolve_from(from_addr) if (from_addr or _mail_from()) else ""
    if not sender:
        return False
    return _graph_configured() or _smtp_env_configured()


def _smtp_configured() -> bool:
    """True if any outbound transport is ready (Graph or SMTP)."""
    return _mail_configured()


def reset_graph_token_cache() -> None:
    _graph_token_cache["token"] = None
    _graph_token_cache["expires_at"] = 0.0


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

    actor_email = None
    if actor is not None and getattr(actor, "user", None) is not None:
        actor_email = (actor.user.email or "").strip() or None
    _dispatch(
        log_id=str(log.id),
        subject=log.subject or "RFI Update",
        body=body,
        to=log.recipient_email,
        from_addr=actor_email,
    )


def enqueue_email(
    log: "RfiNotificationLog",
    *,
    subject: str,
    body: str,
    to: str,
    from_addr: str | None = None,
) -> dict[str, object]:
    return _dispatch(log_id=str(log.id), subject=subject, body=body, to=to, from_addr=from_addr)


def _dispatch(
    *,
    log_id: str,
    subject: str,
    body: str,
    to: str,
    from_addr: str | None = None,
) -> dict[str, object]:
    """Send or queue one message. Caller must ``flush()`` the log row so ``log_id`` is valid."""
    celery = _celery_app()
    if celery is not None:
        try:
            celery.send_task(
                "rfi.send_email",
                kwargs={
                    "log_id": log_id,
                    "subject": subject,
                    "body": body,
                    "to": to,
                    "from_addr": from_addr,
                },
            )
            return {"sent": False, "dry_run": False, "queued": True, "error": None}
        except Exception:  # pragma: no cover
            current_app.logger.exception("Celery dispatch failed; falling back to sync")

    if not _mail_configured(from_addr=from_addr):
        current_app.logger.info(
            "RFI email (mail unset, dry-run): to=%s subj=%r", to, subject
        )
        if log_id and log_id != "None":
            _mark_log_delivered(log_id)
        return {"sent": False, "dry_run": True, "queued": False, "error": None}

    try:
        _deliver_email(subject=subject, body=body, to=to, from_addr=from_addr)
        if log_id and log_id != "None":
            _mark_log_delivered(log_id)
        return {"sent": True, "dry_run": False, "queued": False, "error": None}
    except Exception as exc:
        current_app.logger.warning("Failed to send RFI email to %s: %s", to, exc)
        if log_id and log_id != "None":
            _mark_log_delivered(log_id, error=str(exc))
        return {"sent": False, "dry_run": False, "queued": False, "error": str(exc)}


def _graph_access_token() -> str:
    now = time.time()
    cached = _graph_token_cache.get("token")
    expires_at = float(_graph_token_cache.get("expires_at") or 0)
    if cached and now < expires_at - 60:
        return str(cached)

    import httpx

    tenant = (os.environ.get("MS_ENTRA_TENANT_ID") or "").strip()
    url = f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"
    data = {
        "client_id": (os.environ.get("MS_ENTRA_CLIENT_ID") or "").strip(),
        "client_secret": (os.environ.get("MS_ENTRA_CLIENT_SECRET") or "").strip(),
        "scope": "https://graph.microsoft.com/.default",
        "grant_type": "client_credentials",
    }
    with httpx.Client(timeout=30.0) as client:
        response = client.post(url, data=data)
        response.raise_for_status()
        payload = response.json()
    token = str(payload["access_token"])
    _graph_token_cache["token"] = token
    _graph_token_cache["expires_at"] = now + int(payload.get("expires_in") or 3600)
    return token


def _graph_http(method: str, url: str, **kwargs: Any) -> Any:
    """Authenticated Graph HTTP. Raises GraphMailError on 4xx/5xx."""
    import httpx

    token = _graph_access_token()
    headers = dict(kwargs.pop("headers", None) or {})
    headers["Authorization"] = f"Bearer {token}"
    with httpx.Client(timeout=60.0) as client:
        response = client.request(method, url, headers=headers, **kwargs)
    if response.status_code >= 400:
        raise GraphMailError(
            response.status_code,
            f"Graph {method} {response.status_code}: {response.text[:500]}",
        )
    if response.status_code == 204 or not response.content:
        return None
    try:
        return response.json()
    except Exception:
        return {"raw": response.content, "content_type": response.headers.get("content-type")}


def _user_mail_url(mailbox: str, *parts: str) -> str:
    encoded = urllib.parse.quote(mailbox)
    extra = "/".join(urllib.parse.quote(p, safe="") for p in parts if p)
    if extra:
        return f"{_GRAPH_BASE}/users/{encoded}/{extra}"
    return f"{_GRAPH_BASE}/users/{encoded}"


def _addr_from_graph(obj: Any) -> dict[str, str]:
    if not isinstance(obj, dict):
        return {"name": "", "address": ""}
    ea = obj.get("emailAddress") if "emailAddress" in obj else obj
    if not isinstance(ea, dict):
        return {"name": "", "address": ""}
    return {
        "name": str(ea.get("name") or ""),
        "address": str(ea.get("address") or ""),
    }


def _serialize_message_summary(item: dict[str, Any]) -> dict[str, Any]:
    to_list = [_addr_from_graph(x) for x in (item.get("toRecipients") or [])]
    return {
        "id": item.get("id"),
        "subject": item.get("subject") or "(no subject)",
        "from": _addr_from_graph(item.get("from") or {}),
        "to": to_list,
        "received": item.get("receivedDateTime") or item.get("sentDateTime"),
        "is_read": bool(item.get("isRead")),
        "preview": (item.get("bodyPreview") or "")[:240],
        "has_attachments": bool(item.get("hasAttachments")),
    }


def _serialize_attachment_meta(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": item.get("id"),
        "name": item.get("name") or "attachment",
        "size": int(item.get("size") or 0),
        "content_type": item.get("contentType") or "application/octet-stream",
        "is_inline": bool(item.get("isInline")),
    }


def search_mailbox_messages(*, mailbox: str, query: str, top: int = 25) -> dict[str, Any]:
    """Search a mailbox with Graph ``$search`` (KQL). Best-effort; caller handles errors."""
    q = (query or "").strip()
    if not q:
        return {"mailbox": mailbox, "query": q, "items": []}
    n = max(1, min(int(top or 25), 50))
    safe = q.replace('"', " ").strip()
    url = _user_mail_url(mailbox, "messages")
    params = {
        "$search": f'"{safe}"',
        "$top": str(n),
        "$select": _MAIL_LIST_SELECT,
    }
    payload = _graph_http("GET", url, params=params, headers={"ConsistencyLevel": "eventual"}) or {}
    items = payload.get("value") or []
    return {
        "mailbox": mailbox,
        "query": q,
        "items": [_serialize_message_summary(x) for x in items if isinstance(x, dict)],
    }


def list_mailbox_messages(*, mailbox: str, folder: str, top: int = 50) -> dict[str, Any]:
    """List inbox or sent items for ``mailbox`` (must be the signed-in user)."""
    key = (folder or "inbox").strip().lower()
    folder_id = _MAIL_FOLDERS.get(key)
    if folder_id is None:
        raise GraphMailError(400, "folder must be inbox, sent, drafts, or deleted")
    n = max(1, min(int(top or 50), 100))
    url = _user_mail_url(mailbox, "mailFolders", folder_id, "messages")
    params = {
        "$top": str(n),
        "$select": _MAIL_LIST_SELECT,
        "$orderby": "receivedDateTime desc",
    }
    payload = _graph_http("GET", url, params=params) or {}
    items = payload.get("value") or []
    return {
        "folder": key,
        "mailbox": mailbox,
        "items": [_serialize_message_summary(x) for x in items if isinstance(x, dict)],
    }


def get_mailbox_message(*, mailbox: str, message_id: str) -> dict[str, Any]:
    url = _user_mail_url(mailbox, "messages", message_id)
    params = {
        "$select": _MAIL_DETAIL_SELECT,
        "$expand": "attachments($select=id,name,size,contentType,isInline)",
    }
    item = _graph_http("GET", url, params=params) or {}
    body = item.get("body") or {}
    attachments = [
        _serialize_attachment_meta(a)
        for a in (item.get("attachments") or [])
        if isinstance(a, dict)
    ]
    summary = _serialize_message_summary(item)
    summary.update(
        {
            "cc": [_addr_from_graph(x) for x in (item.get("ccRecipients") or [])],
            "body_content": body.get("content") or "",
            "body_type": (body.get("contentType") or "text").lower(),
            "attachments": attachments,
        }
    )
    return summary


def mark_mailbox_message_read(*, mailbox: str, message_id: str, is_read: bool = True) -> dict[str, Any]:
    url = _user_mail_url(mailbox, "messages", message_id)
    _graph_http("PATCH", url, json={"isRead": bool(is_read)})
    return {"ok": True, "is_read": bool(is_read)}


def delete_mailbox_message(*, mailbox: str, message_id: str) -> dict[str, Any]:
    url = _user_mail_url(mailbox, "messages", message_id)
    _graph_http("DELETE", url)
    return {"ok": True}


def download_mailbox_attachment(
    *, mailbox: str, message_id: str, attachment_id: str
) -> tuple[bytes, str, str]:
    url = _user_mail_url(mailbox, "messages", message_id, "attachments", attachment_id)
    item = _graph_http("GET", url) or {}
    raw = item.get("contentBytes")
    if not raw:
        raise GraphMailError(404, "attachment has no file content")
    data = base64.b64decode(raw)
    name = str(item.get("name") or "attachment")
    ctype = str(item.get("contentType") or "application/octet-stream")
    return data, name, ctype


def graph_error_http(exc: GraphMailError) -> tuple[dict[str, object], int]:
    status = int(exc.status_code or 502)
    if status == 400 and "folder must be" in str(exc):
        return {"error": str(exc), "ok": False}, 400
    if status in (401, 403):
        return {
            "ok": False,
            "error": (
                "Microsoft Graph refused mailbox access. Confirm application "
                "Mail.ReadWrite is granted with admin consent, and that an "
                "Exchange application access policy allows this mailbox."
            ),
            "detail": str(exc),
        }, 403
    if status == 404:
        return {
            "ok": False,
            "error": "Mailbox or message was not found in Microsoft 365.",
            "detail": str(exc),
        }, 404
    return {"ok": False, "error": str(exc)}, 502 if status >= 500 else status


def _norm_addr_list(value: str | list[str] | tuple[str, ...] | None) -> list[str]:
    if not value:
        return []
    if isinstance(value, str):
        return [s.strip() for s in value.split(",") if s.strip() and "@" in s]
    return [str(s).strip() for s in value if str(s).strip() and "@" in str(s)]


def _graph_file_attachments(attachments: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for att in attachments or []:
        raw = att.get("content") if isinstance(att, dict) else None
        if raw is None and isinstance(att, dict):
            raw = att.get("data")
        if not isinstance(raw, (bytes, bytearray)):
            continue
        name = str((att.get("name") if isinstance(att, dict) else None) or "file.pdf")[:200]
        ctype = str((att.get("content_type") if isinstance(att, dict) else None) or "application/pdf")
        out.append(
            {
                "@odata.type": "#microsoft.graph.fileAttachment",
                "name": name,
                "contentType": ctype,
                "contentBytes": base64.b64encode(bytes(raw)).decode("ascii"),
            }
        )
    return out


def _send_via_graph(
    *,
    subject: str,
    body: str,
    to: str,
    html_body: str | None = None,
    from_addr: str | None = None,
    reply_to: str | None = None,
    bcc: str | list[str] | None = None,
    cc: str | list[str] | None = None,
    attachments: list[dict[str, Any]] | None = None,
    from_name: str | None = None,
) -> None:
    import httpx

    sender = _resolve_from(from_addr)
    if not sender:
        raise RuntimeError("MAIL_FROM is not set and no from_addr was provided")
    token = _graph_access_token()
    content_type = "HTML" if html_body else "Text"
    content = html_body if html_body else body
    message: dict[str, Any] = {
        "subject": subject,
        "body": {"contentType": content_type, "content": content or ""},
        "toRecipients": [{"emailAddress": {"address": to}}],
    }
    if from_name:
        message["from"] = {"emailAddress": {"address": sender, "name": from_name[:120]}}
    reply = (reply_to or "").strip()
    if reply:
        message["replyTo"] = [{"emailAddress": {"address": reply}}]
    bcc_addrs = _norm_addr_list(bcc)
    if bcc_addrs:
        message["bccRecipients"] = [{"emailAddress": {"address": a}} for a in bcc_addrs]
    cc_addrs = _norm_addr_list(cc)
    if cc_addrs:
        message["ccRecipients"] = [{"emailAddress": {"address": a}} for a in cc_addrs]
    files = _graph_file_attachments(attachments)
    if files:
        message["attachments"] = files
    payload = {"message": message, "saveToSentItems": True}
    encoded = urllib.parse.quote(sender)
    url = f"https://graph.microsoft.com/v1.0/users/{encoded}/sendMail"
    with httpx.Client(timeout=30.0) as client:
        response = client.post(
            url,
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
        )
        if response.status_code >= 400:
            raise RuntimeError(f"Graph sendMail {response.status_code}: {response.text[:500]}")


def _deliver_email(
    *,
    subject: str,
    body: str,
    to: str,
    html_body: str | None = None,
    from_addr: str | None = None,
    reply_to: str | None = None,
    bcc: str | list[str] | None = None,
    cc: str | list[str] | None = None,
    attachments: list[dict[str, Any]] | None = None,
    from_name: str | None = None,
) -> None:
    kwargs = dict(
        subject=subject,
        body=body,
        to=to,
        html_body=html_body,
        from_addr=from_addr,
        reply_to=reply_to,
        bcc=bcc,
        cc=cc,
        attachments=attachments,
        from_name=from_name,
    )
    if _graph_configured():
        _send_via_graph(**kwargs)
        return
    _send_via_smtplib(**kwargs)


def _send_via_smtplib(
    *,
    subject: str,
    body: str,
    to: str,
    html_body: str | None = None,
    from_addr: str | None = None,
    reply_to: str | None = None,
    bcc: str | list[str] | None = None,
    cc: str | list[str] | None = None,
    attachments: list[dict[str, Any]] | None = None,
    from_name: str | None = None,
) -> None:  # pragma: no cover - I/O
    import smtplib
    from email.message import EmailMessage
    from email.utils import formataddr

    host = os.environ.get("MAIL_SERVER", "localhost")
    port = int(os.environ.get("MAIL_PORT") or "587")
    use_tls = (os.environ.get("MAIL_USE_TLS", "true").strip().lower() not in ("0", "false", "no", "off"))
    user = os.environ.get("MAIL_USERNAME") or ""
    pw = os.environ.get("MAIL_PASSWORD") or ""
    sender = _resolve_from(from_addr) or user

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = formataddr(((from_name or "").strip(), sender)) if (from_name or "").strip() else sender
    msg["To"] = to
    cc_addrs = _norm_addr_list(cc)
    if cc_addrs:
        msg["Cc"] = ", ".join(cc_addrs)
    bcc_addrs = _norm_addr_list(bcc)
    if bcc_addrs:
        msg["Bcc"] = ", ".join(bcc_addrs)
    if reply_to:
        msg["Reply-To"] = reply_to
    msg.set_content(body)
    if html_body:
        msg.add_alternative(html_body, subtype="html")
    for att in attachments or []:
        raw = att.get("content") if isinstance(att, dict) else None
        if raw is None and isinstance(att, dict):
            raw = att.get("data")
        if not isinstance(raw, (bytes, bytearray)):
            continue
        name = str((att.get("name") if isinstance(att, dict) else None) or "file.pdf")
        ctype = str((att.get("content_type") if isinstance(att, dict) else None) or "application/pdf")
        maintype, _, subtype = ctype.partition("/")
        msg.add_attachment(
            bytes(raw),
            maintype=maintype or "application",
            subtype=subtype or "octet-stream",
            filename=name,
        )

    with smtplib.SMTP(host, port, timeout=30) as s:
        if use_tls:
            s.starttls()
        if user:
            s.login(user, pw)
        s.send_message(msg)


def send_plain_notification_email(
    *,
    to: str,
    subject: str,
    body: str,
    from_addr: str | None = None,
) -> dict[str, object]:
    """Best-effort synchronous send for system or user-authored mail.

    Omit ``from_addr`` to send as ``MAIL_FROM`` (noreply). Pass the signed-in
    user's email for compose / RFI forwarding.
    """
    return send_html_notification_email(
        to=to, subject=subject, body=body, html_body=None, from_addr=from_addr
    )


def send_html_notification_email(
    *,
    to: str,
    subject: str,
    body: str,
    html_body: str | None,
    from_addr: str | None = None,
    reply_to: str | None = None,
    bcc: str | list[str] | None = None,
    cc: str | list[str] | None = None,
    attachments: list[dict[str, Any]] | None = None,
    from_name: str | None = None,
) -> dict[str, object]:
    """Best-effort synchronous send with optional HTML alternative body."""
    if not to:
        return {"sent": False, "dry_run": False, "error": "missing recipient email"}
    if not _mail_configured(from_addr=from_addr):
        current_app.logger.info("Plain email (mail unset, dry-run): to=%s subj=%r", to, subject)
        return {"sent": False, "dry_run": True, "error": None}

    try:
        _deliver_email(
            subject=subject,
            body=body,
            to=to,
            html_body=html_body,
            from_addr=from_addr,
            reply_to=reply_to,
            bcc=bcc,
            cc=cc,
            attachments=attachments,
            from_name=from_name,
        )
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
    from_addr: str | None = None,
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
        result = send_plain_notification_email(
            to=em, subject=subject, body=body, from_addr=from_addr
        )
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
) -> dict[str, object]:
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
    return send_plain_notification_email(to=to, subject=subject, body="\n".join(lines))


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
