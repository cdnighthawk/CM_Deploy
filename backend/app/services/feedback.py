"""Employee issue reports → GitHub Issues (same intake as USISPdfApp)."""
from __future__ import annotations

import hashlib
import hmac
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable

import httpx

PLACEHOLDER_OWNER = "your-org"
DEFAULT_OWNER = "cdnighthawk"
DEFAULT_REPO = "CM_Deploy"
APP_NAME = "USIS CM"
MAX_TITLE = 200
MAX_DETAILS = 10_000
MAX_NAME = 120
MAX_PAGE = 300
MAX_PAGE_URL = 800
MAX_PAGE_TITLE = 200
MAX_USER_AGENT = 400
MAX_BODY = 50_000
MAX_RESOLUTION = 4_000
NOTIFIED_MARKER = "<!-- usis-reporter-notified -->"
REPORTER_EMAIL_MARKER_RE = re.compile(r"<!--\s*usis-reporter-email:\s*([^ >]+)\s*-->", re.I)
REPORTER_EMAIL_LINE_RE = re.compile(r"(?im)^\*\*Email:\*\*\s*(\S+@\S+)\s*$")
REPORTER_NAME_LINE_RE = re.compile(r"(?im)^\*\*From:\*\*\s*(.+?)\s*$")
RESOLUTION_RE = re.compile(r"(?is)^\s*(?:##\s*)?Resolution:\s*(.+)$")
CLOSER_NOTE = (
    "When closing this issue, add a comment that starts with `Resolution:` "
    "explaining how it was fixed or why it was not. USIS emails that note to the reporter."
)
STATUS_COPY = {
    "completed": {
        "headline": "Your USIS report was fixed",
        "status": "Fixed",
        "fallback": "This was fixed in USIS. The person who closed it did not add extra notes.",
    },
    "not_planned": {
        "headline": "Your USIS report will not be changed",
        "status": "Not fixed",
        "fallback": "This was reviewed and will not be changed at this time. "
        "The person who closed it did not add extra notes.",
    },
    "duplicate": {
        "headline": "Your USIS report was closed as a duplicate",
        "status": "Closed as duplicate",
        "fallback": "This matched an existing report and was closed as a duplicate.",
    },
}

KINDS = {
    "bug": {
        "value": "bug",
        "heading": "Something broke",
        "title_prefix": "[bug] ",
        "github_label": "bug",
        "site_wide": False,
        "extra_labels": [],
    },
    "enhancement": {
        "value": "enhancement",
        "heading": "Recommend a change on this page",
        "title_prefix": "[idea] ",
        "github_label": "enhancement",
        "site_wide": False,
        "extra_labels": [],
    },
    "general": {
        "value": "general",
        "heading": "General recommendation",
        "title_prefix": "[idea] ",
        "github_label": "enhancement",
        "site_wide": True,
        "extra_labels": ["site-wide"],
    },
}


def github_labels_for(kind: dict[str, Any]) -> list[str]:
    labels = [kind["github_label"], *kind.get("extra_labels", []), "from-hub"]
    seen: list[str] = []
    for label in labels:
        if label and label not in seen:
            seen.append(label)
    return seen


def _clean(value: Any, max_len: int) -> str:
    if not isinstance(value, str):
        return ""
    stripped = "".join(ch for ch in value if ord(ch) >= 32 or ch in "\n\t").strip()
    return stripped[:max_len]


def _cfg(config: Any, key: str, default: str = "") -> str:
    if isinstance(config, dict):
        value = config.get(key, default)
    else:
        value = getattr(config, key, default)
    return str(value or default).strip()


def feedback_options(config: Any) -> dict[str, Any]:
    owner = _cfg(config, "GITHUB_FEEDBACK_OWNER", DEFAULT_OWNER) or DEFAULT_OWNER
    repo = _cfg(config, "GITHUB_FEEDBACK_REPO", DEFAULT_REPO) or DEFAULT_REPO
    token = _cfg(config, "GITHUB_FEEDBACK_TOKEN")
    configured = bool(token and owner and repo and owner.lower() != PLACEHOLDER_OWNER)
    return {"owner": owner, "repo": repo, "token": token, "configured": configured}


def parse_feedback_input(body: dict[str, Any] | None) -> dict[str, Any]:
    data = body if isinstance(body, dict) else {}
    raw_kind = data.get("kind")
    kind_key = raw_kind if raw_kind in KINDS else "bug"
    kind = KINDS[kind_key]
    title = _clean(data.get("title"), MAX_TITLE)
    details = _clean(data.get("details"), MAX_DETAILS)
    reporter_name = _clean(data.get("reporterName"), MAX_NAME)
    page = _clean(data.get("page"), MAX_PAGE)
    page_url = _clean(data.get("pageUrl"), MAX_PAGE_URL)
    page_title = _clean(data.get("pageTitle"), MAX_PAGE_TITLE)
    user_agent = _clean(data.get("userAgent"), MAX_USER_AGENT)
    if kind.get("site_wide"):
        page = ""
        page_url = ""
        page_title = ""

    if not title or not details:
        return {"error": "Add a title and details."}

    if not title.startswith("["):
        title = f"{kind['title_prefix']}{title}"
    if page and not kind.get("site_wide") and " — " not in title:
        short_page = page.rsplit("/", 1)[-1] or page
        title = f"{title} — {short_page}"

    return {
        "kind": kind,
        "title": title[:MAX_TITLE],
        "details": details,
        "reporter_name": reporter_name,
        "page": page,
        "page_url": page_url,
        "page_title": page_title,
        "user_agent": user_agent,
    }


def build_issue_body(
    *,
    kind: dict[str, str],
    details: str,
    reporter_name: str = "",
    reporter_email: str = "",
    page: str = "",
    page_url: str = "",
    page_title: str = "",
    user_agent: str = "",
    created_utc: datetime | None = None,
) -> str:
    when = created_utc or datetime.now(timezone.utc)
    lines = [
        f"## {kind['heading']}",
        "",
        "### Where it happened",
    ]
    if kind.get("site_wide"):
        lines.append("**Page:** Site-wide")
    else:
        lines.append(f"**Page:** {page or '(unknown)'}")
        if page_url:
            lines.append(f"**Page URL:** {page_url}")
        if page_title:
            lines.append(f"**Page title:** {page_title}")
    lines.extend(["", "### Reporter"])
    if reporter_email:
        lines.insert(0, f"<!-- usis-reporter-email: {reporter_email} -->")
        lines.insert(1, "")
    if reporter_name:
        lines.append(f"**From:** {reporter_name}")
    if reporter_email:
        lines.append(f"**Email:** {reporter_email}")
    lines.extend(
        [
            f"**App:** {APP_NAME}",
            f"**Time (UTC):** {when.isoformat()}",
        ]
    )
    if user_agent:
        lines.append(f"**Browser:** {user_agent}")
    lines.extend(["", "### Details", details or "(none)", "", "---", "", CLOSER_NOTE])
    body = "\n".join(lines)
    return body if len(body) <= MAX_BODY else f"{body[:MAX_BODY]}\n…"


@dataclass
class SubmitResult:
    ok: bool
    status: str
    message: str
    issue_number: int = 0


def submit_github_issue(
    *,
    title: str,
    body: str,
    labels: list[str],
    config: Any,
    client: httpx.Client | None = None,
) -> SubmitResult:
    options = feedback_options(config)
    if not options["configured"]:
        return SubmitResult(
            ok=False,
            status="not_configured",
            message="Reporting isn't configured yet. Ask an admin to set GITHUB_FEEDBACK_TOKEN.",
        )

    url = f"https://api.github.com/repos/{options['owner']}/{options['repo']}/issues"
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {options['token']}",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "USISCM",
    }
    attempts = [labels, [label for label in labels if label != "from-hub"], []]
    last_status = 0
    owns_client = client is None
    http = client or httpx.Client(timeout=15.0)
    try:
        for attempt in attempts:
            response = http.post(url, headers=headers, json={"title": title, "body": body, "labels": attempt})
            last_status = response.status_code
            if response.is_success:
                number = 0
                try:
                    number = int((response.json() or {}).get("number") or 0)
                except (TypeError, ValueError):
                    number = 0
                return SubmitResult(
                    ok=True,
                    status="created",
                    message="Report sent. We'll email you when it's resolved.",
                    issue_number=number,
                )
            if response.status_code != 422:
                break
    except httpx.HTTPError:
        return SubmitResult(ok=False, status="failed", message="Couldn't send the report. Try again later.")
    finally:
        if owns_client:
            http.close()

    return SubmitResult(
        ok=False,
        status="failed",
        message=f"Couldn't send the report (HTTP {last_status}). Try again later.",
    )


def _looks_like_email(value: str) -> bool:
    text = (value or "").strip().strip("<>")
    return bool(text) and "@" in text and " " not in text and "." in text.split("@")[-1]


def parse_reporter_email(body: str | None) -> str:
    text = body or ""
    marker = REPORTER_EMAIL_MARKER_RE.search(text)
    if marker and _looks_like_email(marker.group(1)):
        return marker.group(1).strip().strip("<>")
    line = REPORTER_EMAIL_LINE_RE.search(text)
    if line and _looks_like_email(line.group(1)):
        return line.group(1).strip().strip("<>")
    return ""


def parse_reporter_name(body: str | None) -> str:
    match = REPORTER_NAME_LINE_RE.search(body or "")
    return (match.group(1).strip() if match else "")[:MAX_NAME]


def issue_already_notified(comments: list[dict[str, Any]] | None, body: str | None = None) -> bool:
    if NOTIFIED_MARKER in (body or ""):
        return True
    for comment in comments or []:
        if NOTIFIED_MARKER in str(comment.get("body") or ""):
            return True
    return False


def extract_resolution(comments: list[dict[str, Any]] | None, state_reason: str | None) -> dict[str, str]:
    copy = STATUS_COPY.get((state_reason or "").strip().lower()) or {
        "headline": "Update on your USIS report",
        "status": "Closed",
        "fallback": "This issue was closed. The person who closed it did not add extra notes.",
    }
    resolution = ""
    for comment in reversed(comments or []):
        body = str(comment.get("body") or "")
        if NOTIFIED_MARKER in body:
            continue
        match = RESOLUTION_RE.match(body)
        if match:
            resolution = match.group(1).strip()
            break
    if not resolution:
        for comment in reversed(comments or []):
            body = str(comment.get("body") or "").strip()
            if not body or NOTIFIED_MARKER in body:
                continue
            user = comment.get("user") if isinstance(comment.get("user"), dict) else {}
            login = str(user.get("login") or "")
            if login.endswith("[bot]") or login == "github-actions[bot]":
                continue
            resolution = body
            break
    resolution = resolution[:MAX_RESOLUTION] if resolution else copy["fallback"]
    return {
        "headline": copy["headline"],
        "status": copy["status"],
        "resolution": resolution,
    }


def build_status_email(
    *,
    title: str,
    reporter_name: str,
    status: str,
    resolution: str,
    issue_number: int,
    issue_url: str = "",
) -> dict[str, str]:
    who = reporter_name or "there"
    clean_title = (title or "your report").strip() or "your report"
    lines = [
        f"Hi {who},",
        "",
        f"You reported: {clean_title}",
        "",
        f"Status: {status}",
        "",
        resolution,
        "",
    ]
    if issue_number:
        lines.append(f"This was issue #{issue_number}.")
    if issue_url:
        lines.append(issue_url)
    lines.extend(["", "— USIS"])
    return {
        "subject": f"{status}: {clean_title}"[:200],
        "body": "\n".join(lines),
    }


def verify_github_signature(*, secret: str, payload: bytes, signature_header: str) -> bool:
    if not secret or not signature_header:
        return False
    digest = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    expected = f"sha256={digest}"
    return hmac.compare_digest(expected, signature_header.strip())


def _github_headers(token: str) -> dict[str, str]:
    return {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "USISCM",
    }


def fetch_issue_comments(
    *,
    owner: str,
    repo: str,
    issue_number: int,
    token: str,
    client: httpx.Client | None = None,
) -> list[dict[str, Any]]:
    if not token or not issue_number:
        return []
    url = (
        f"https://api.github.com/repos/{owner}/{repo}/issues/{int(issue_number)}/comments"
        "?per_page=100"
    )
    owns_client = client is None
    http = client or httpx.Client(timeout=15.0)
    try:
        response = http.get(url, headers=_github_headers(token))
        if not response.is_success:
            return []
        payload = response.json()
        return payload if isinstance(payload, list) else []
    except httpx.HTTPError:
        return []
    finally:
        if owns_client:
            http.close()


def mark_issue_notified(
    *,
    owner: str,
    repo: str,
    issue_number: int,
    token: str,
    client: httpx.Client | None = None,
) -> bool:
    if not token or not issue_number:
        return False
    url = f"https://api.github.com/repos/{owner}/{repo}/issues/{int(issue_number)}/comments"
    owns_client = client is None
    http = client or httpx.Client(timeout=15.0)
    try:
        response = http.post(
            url,
            headers=_github_headers(token),
            json={"body": f"{NOTIFIED_MARKER}\nEmailed the reporter about this close."},
        )
        return response.is_success
    except httpx.HTTPError:
        return False
    finally:
        if owns_client:
            http.close()


def notify_reporter_for_closed_issue(
    *,
    payload: dict[str, Any],
    config: Any,
    send_email: Callable[..., dict[str, Any]],
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    action = str(payload.get("action") or "")
    if action != "closed":
        return {"ok": True, "status": "ignored", "reason": action or "not_closed"}

    issue = payload.get("issue") if isinstance(payload.get("issue"), dict) else {}
    if issue.get("pull_request"):
        return {"ok": True, "status": "ignored", "reason": "pull_request"}

    options = feedback_options(config)
    repo_info = payload.get("repository") if isinstance(payload.get("repository"), dict) else {}
    full_name = str(repo_info.get("full_name") or "")
    expected = f"{options['owner']}/{options['repo']}"
    if full_name and full_name.lower() != expected.lower():
        return {"ok": True, "status": "ignored", "reason": "wrong_repo"}

    body = str(issue.get("body") or "")
    email = parse_reporter_email(body)
    if not email:
        return {"ok": True, "status": "skipped", "reason": "no_reporter_email"}

    number = int(issue.get("number") or 0)
    comments = fetch_issue_comments(
        owner=options["owner"],
        repo=options["repo"],
        issue_number=number,
        token=options["token"],
        client=client,
    )
    if issue_already_notified(comments, body):
        return {"ok": True, "status": "already_notified", "reason": "marker"}

    extracted = extract_resolution(comments, issue.get("state_reason"))
    message = build_status_email(
        title=str(issue.get("title") or ""),
        reporter_name=parse_reporter_name(body),
        status=extracted["status"],
        resolution=extracted["resolution"],
        issue_number=number,
        issue_url=str(issue.get("html_url") or ""),
    )
    result = send_email(to=email, subject=message["subject"], body=message["body"]) or {}
    if result.get("error") and not result.get("dry_run"):
        return {"ok": False, "status": "failed", "reason": str(result.get("error"))}

    mark_issue_notified(
        owner=options["owner"],
        repo=options["repo"],
        issue_number=number,
        token=options["token"],
        client=client,
    )
    status = "dry_run" if result.get("dry_run") else "sent"
    return {"ok": True, "status": status, "reason": email}
