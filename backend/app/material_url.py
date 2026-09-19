"""Normalize manufacturer product URLs for the material catalog."""
from __future__ import annotations

import re
from urllib.parse import urlparse

MAX_MANUFACTURER_URL = 1024
_TRAILING_URL = re.compile(
    r"(?:\s*\|\s*|\s+)(?P<url>https?://[^\s]+)\s*$",
    re.IGNORECASE,
)
_BARE_URL = re.compile(r"^(?P<url>https?://[^\s]+)\s*$", re.IGNORECASE)
_SCHEME = re.compile(r"^[a-z][a-z0-9+.-]*:", re.IGNORECASE)


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
    """Keep description text; store a trailing or explicit product URL separately."""
    desc = (description or "").strip() or None
    raw = (url or "").strip() or None
    if not raw and desc:
        match = _TRAILING_URL.search(desc) or _BARE_URL.match(desc)
        if match:
            raw = match.group("url").rstrip(".,);")
            desc = desc[: match.start()].rstrip(" |").strip() or None
    elif raw and desc:
        if desc.endswith(raw):
            desc = desc[: -len(raw)].rstrip(" |").strip() or None
        else:
            match = _TRAILING_URL.search(desc)
            if match and match.group("url").rstrip(".,);") == raw.rstrip(".,);"):
                desc = desc[: match.start()].rstrip(" |").strip() or None
    try:
        normalized = normalize_manufacturer_url(raw) if raw else None
    except ValueError:
        normalized = None
    return desc, normalized
