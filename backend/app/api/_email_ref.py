"""Visible USIS-REF footer so project mail can be filed after subject edits."""
from __future__ import annotations

import os
import re
import uuid
from typing import Any

REF_LABEL = "USIS-REF"
_UUID_RE = r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
_REF_RE = re.compile(
    rf"{re.escape(REF_LABEL)}\s+project=({_UUID_RE})\s+thread=({_UUID_RE})",
    re.IGNORECASE,
)
_HAS_REF_RE = re.compile(rf"{re.escape(REF_LABEL)}\s+project=", re.IGNORECASE)


def _as_uuid(raw: Any) -> uuid.UUID | None:
    if raw is None:
        return None
    if isinstance(raw, uuid.UUID):
        return raw
    text = str(raw).strip()
    if not text:
        return None
    try:
        return uuid.UUID(text)
    except ValueError:
        return None


def ensure_thread_id(thread_id: Any | None) -> uuid.UUID:
    parsed = _as_uuid(thread_id)
    return parsed if parsed is not None else uuid.uuid4()


def format_ref_block(project_id: uuid.UUID | str, thread_id: uuid.UUID | str) -> str:
    pid = _as_uuid(project_id)
    tid = _as_uuid(thread_id)
    if pid is None or tid is None:
        return ""
    return f"-----\n{REF_LABEL} project={pid} thread={tid}"


def _html_ref_block(block: str) -> str:
    escaped = block.replace("\n", "<br>\n")
    return f'<p style="margin-top:1.5em;color:#666;font-size:12px;">{escaped}</p>'


def append_ref(
    body: str | None,
    html_body: str | None,
    project_id: Any | None,
    thread_id: Any | None = None,
) -> tuple[str, str | None, uuid.UUID | None]:
    """Append the footer to text/HTML. Skip if a USIS-REF line is already present."""
    pid = _as_uuid(project_id)
    text = body or ""
    html = html_body
    if pid is None:
        return text, html, _as_uuid(thread_id)
    if _HAS_REF_RE.search(text) or (html and _HAS_REF_RE.search(html)):
        parsed = parse_ref((html or "") + "\n" + text)
        return text, html, (parsed[1] if parsed else ensure_thread_id(thread_id))
    tid = ensure_thread_id(thread_id)
    block = format_ref_block(pid, tid)
    if not block:
        return text, html, tid
    text = f"{text.rstrip()}\n\n{block}\n" if text.strip() else f"{block}\n"
    if html is not None:
        html = f"{html.rstrip()}\n{_html_ref_block(block)}\n"
    return text, html, tid


def parse_ref(text: str | None) -> tuple[uuid.UUID, uuid.UUID] | None:
    """Return the last USIS-REF pair in ``text`` (quoted originals sit at the bottom)."""
    if not text:
        return None
    matches = list(_REF_RE.finditer(text))
    if not matches:
        return None
    last = matches[-1]
    try:
        return uuid.UUID(last.group(1)), uuid.UUID(last.group(2))
    except ValueError:
        return None


def correspondence_archive_mailbox() -> str | None:
    raw = ""
    try:
        from flask import current_app, has_app_context

        if has_app_context():
            raw = str(current_app.config.get("CORRESPONDENCE_MAILBOXES") or "").strip()
    except Exception:
        raw = ""
    if not raw:
        raw = (os.environ.get("CORRESPONDENCE_MAILBOXES") or "").strip()
    for part in raw.split(","):
        addr = part.strip()
        if "@" in addr:
            return addr
    return None
