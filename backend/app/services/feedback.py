"""Employee issue reports → GitHub Issues (same intake as USISPdfApp)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

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
    lines.extend(["", "### Details", details or "(none)"])
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
                return SubmitResult(ok=True, status="created", message="Report sent.", issue_number=number)
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
