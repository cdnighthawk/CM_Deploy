"""Normalize manufacturer product URLs for the material catalog."""
from __future__ import annotations

import re
from urllib.parse import urlparse

MAX_MANUFACTURER_URL = 1024
_TRAILING_URL = re.compile(
    r"(?:\s*\|\s*|\s+)(?P<url>https?://[^\s|]+)\s*$",
    re.IGNORECASE,
)
_PIPE_URL = re.compile(
    r"(?:^|\s*\|\s*)(?P<url>https?://[^\s|]+)\s*(?:\||$)",
    re.IGNORECASE,
)
_BARE_URL = re.compile(r"^(?P<url>https?://[^\s]+)\s*$", re.IGNORECASE)
_SCHEME = re.compile(r"^[a-z][a-z0-9+.-]*:", re.IGNORECASE)


def _strip_url_from_description(desc: str, url: str) -> str | None:
    raw = url.rstrip(".,);")
    if desc.endswith(raw):
        return desc[: -len(raw)].rstrip(" |").strip() or None
    match = _TRAILING_URL.search(desc)
    if match and match.group("url").rstrip(".,);") == raw:
        return desc[: match.start()].rstrip(" |").strip() or None
    idx = desc.lower().find(raw.lower())
    if idx < 0:
        return desc.strip() or None
    before = desc[:idx].rstrip()
    after = desc[idx + len(raw) :].lstrip()
    if before.endswith("|"):
        before = before[:-1].rstrip()
    if after.startswith("|"):
        after = after[1:].lstrip()
    if before and after:
        return f"{before} | {after}"
    return (before or after).strip() or None


def normalize_manufacturer_url(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if (text.startswith('"') and text.endswith('"')) or (text.startswith("'") and text.endswith("'")):
        text = text[1:-1].strip()
    if not text:
        return None
    if not _SCHEME.match(text):
        text = "https://" + text.lstrip("/")
    parsed = urlparse(text)
    if parsed.scheme not in ("http", "https") or not parsed.netloc or parsed.username or parsed.password:
        raise ValueError("manufacturer URL must be an http(s) link")
    return text[:MAX_MANUFACTURER_URL]


def split_description_url(
    description: str | None, url: str | None = None
) -> tuple[str | None, str | None]:
    """Keep description text; store a trailing, piped, or explicit product URL separately."""
    desc = (description or "").strip() or None
    raw = (url or "").strip() or None
    if not raw and desc:
        match = _TRAILING_URL.search(desc) or _PIPE_URL.search(desc) or _BARE_URL.match(desc)
        if match:
            raw = match.group("url").rstrip(".,);")
            desc = _strip_url_from_description(desc, raw)
    elif raw and desc:
        desc = _strip_url_from_description(desc, raw)
    try:
        normalized = normalize_manufacturer_url(raw) if raw else None
    except ValueError:
        normalized = None
    return desc, normalized
