"""Import existing GitHub hub reports into the internal issues tracker."""
from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from sqlalchemy import select

from ..extensions import db
from ..models import Project, User
from ..models.issue import Issue, IssueEvent

GITHUB_SOURCE_NS = uuid.UUID("a3c8e1d0-5f21-4b7a-9c44-0e6d2a1b8f10")
BUNDLE_PATH = Path(__file__).resolve().parent.parent / "data" / "github_feedback_issues.json"
_DETAILS_RE = re.compile(r"### Details\s*(.*?)(?:\n---|\Z)", re.S | re.I)
_PAGE_RE = re.compile(r"\*\*Page:\*\*\s*(.+)", re.I)
_PAGE_URL_RE = re.compile(r"\*\*Page URL:\*\*\s*(\S+)", re.I)
_EMAIL_RE = re.compile(r"\*\*Email:\*\*\s*(\S+)", re.I)
_FROM_RE = re.compile(r"\*\*From:\*\*\s*(.+)", re.I)


def github_source_id(number: int) -> uuid.UUID:
    return uuid.uuid5(GITHUB_SOURCE_NS, f"github:{int(number)}")


def _parse_dt(raw: str | None) -> datetime | None:
    if not raw:
        return None
    text = raw.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        value = datetime.fromisoformat(text)
    except ValueError:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _first_match(pattern: re.Pattern[str], text: str) -> str:
    match = pattern.search(text or "")
    return (match.group(1) if match else "").strip()


def description_from_github(item: dict[str, Any]) -> str:
    body = item.get("body") or ""
    details = _first_match(_DETAILS_RE, body) or body.strip()
    details = details.strip()
    page = _first_match(_PAGE_RE, body)
    page_url = _first_match(_PAGE_URL_RE, body)
    reporter = _first_match(_FROM_RE, body)
    email = _first_match(_EMAIL_RE, body)
    lines = [details] if details else []
    if page and page.lower() != "site-wide":
        lines.append(f"Page: {page}")
    if page_url:
        lines.append(f"Page URL: {page_url}")
    if reporter:
        lines.append(f"Reported by: {reporter}")
    if email:
        lines.append(f"Email: {email}")
    html_url = (item.get("html_url") or "").strip()
    number = item.get("number")
    if html_url:
        lines.append(f"GitHub: {html_url}")
    elif number:
        lines.append(f"GitHub #{int(number)}")
    return "\n".join(lines).strip()


def _project_id_from_item(item: dict[str, Any]) -> uuid.UUID | None:
    body = item.get("body") or ""
    page_url = _first_match(_PAGE_URL_RE, body)
    if not page_url:
        return None
    qs = parse_qs(urlparse(page_url).query)
    raw = (qs.get("id") or qs.get("project_id") or qs.get("projectId") or [""])[0]
    try:
        pid = uuid.UUID(str(raw))
    except (TypeError, ValueError):
        return None
    if db.session.get(Project, pid) is None:
        return None
    return pid


def _user_id_from_item(item: dict[str, Any]) -> uuid.UUID | None:
    from sqlalchemy import func

    email = _first_match(_EMAIL_RE, item.get("body") or "").lower()
    if not email or "@" not in email:
        return None
    user = db.session.scalar(select(User).where(func.lower(User.email) == email))
    return user.id if user else None


def _severity(item: dict[str, Any]) -> str:
    labels = {str(name).lower() for name in (item.get("labels") or [])}
    title = str(item.get("title") or "").lower()
    if "bug" in labels or title.startswith("[bug]"):
        return "Major"
    return "Minor"


def _status(item: dict[str, Any]) -> str:
    return "Closed" if str(item.get("state") or "").lower() == "closed" else "New"


def _sheet_number(item: dict[str, Any]) -> str | None:
    page = _first_match(_PAGE_RE, item.get("body") or "")
    if not page or page.lower() == "site-wide":
        return None
    name = page.rsplit("/", 1)[-1]
    return name[:50] or None


def upsert_github_issue(item: dict[str, Any]) -> str:
    number = int(item["number"])
    source_id = github_source_id(number)
    existing = db.session.scalar(
        select(Issue).where(Issue.source_type == "feedback", Issue.source_id == source_id)
    )
    title = (item.get("title") or f"GitHub #{number}").strip()[:500]
    description = description_from_github(item)
    status = _status(item)
    resolved_at = _parse_dt(item.get("closed_at")) if status == "Closed" else None
    created_at = _parse_dt(item.get("created_at"))
    if existing:
        existing.title = title
        existing.description = description
        existing.severity = _severity(item)
        existing.status = status
        existing.resolved_at = resolved_at
        existing.project_id = _project_id_from_item(item) or existing.project_id
        existing.sheet_number = _sheet_number(item) or existing.sheet_number
        existing.linked_change_order_id = f"github:{number}"
        return "updated"

    issue = Issue(
        project_id=_project_id_from_item(item),
        source_type="feedback",
        source_id=source_id,
        severity=_severity(item),
        status=status,
        trade="General",
        title=title,
        description=description or None,
        created_by_id=_user_id_from_item(item),
        sheet_number=_sheet_number(item),
        linked_change_order_id=f"github:{number}",
        resolved_at=resolved_at,
    )
    if created_at is not None:
        issue.created_at = created_at
        issue.updated_at = created_at
    db.session.add(issue)
    db.session.flush()
    db.session.add(
        IssueEvent(
            issue_id=issue.id,
            action="imported",
            detail=f"Imported from GitHub #{number}",
            payload={"github_number": number, "html_url": item.get("html_url")},
        )
    )
    return "created"


def import_github_issues(items: list[dict[str, Any]]) -> dict[str, int]:
    created = updated = skipped = 0
    for item in items:
        if not item or item.get("pull_request") or not item.get("number"):
            skipped += 1
            continue
        result = upsert_github_issue(item)
        if result == "created":
            created += 1
        else:
            updated += 1
    db.session.commit()
    return {"created": created, "updated": updated, "skipped": skipped, "total": len(items)}


def load_bundled_github_issues() -> list[dict[str, Any]]:
    payload = json.loads(BUNDLE_PATH.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("github_feedback_issues.json must be a list")
    return [row for row in payload if isinstance(row, dict)]


def import_bundled_github_issues() -> dict[str, int]:
    return import_github_issues(load_bundled_github_issues())
