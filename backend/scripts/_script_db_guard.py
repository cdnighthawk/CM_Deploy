"""Guard destructive script runs against accidental production deletes."""
from __future__ import annotations

import os
import sys
from urllib.parse import urlparse

_PRODUCTION_HOST_MARKERS = (
    "render.com",
    "onrender.com",
)


def database_url() -> str:
    return (
        os.environ.get("DATABASE_URL")
        or os.environ.get("SQLALCHEMY_DATABASE_URI")
        or ""
    ).strip()


def is_production_database(url: str | None = None) -> bool:
    raw = (url if url is not None else database_url()).strip()
    if not raw:
        return False
    host = (urlparse(raw).hostname or "").lower()
    return any(marker in host for marker in _PRODUCTION_HOST_MARKERS)


def require_safe_execute(
    *,
    execute: bool,
    production_ack: bool,
    script_name: str,
) -> None:
    """Abort --execute when DATABASE_URL looks like Render production without ack flag."""
    if not execute:
        return
    url = database_url()
    if not is_production_database(url):
        return
    if production_ack:
        return
    host = urlparse(url).hostname or "(unknown host)"
    print(
        f"Refusing --execute: DATABASE_URL host looks like production ({host}).\n"
        f"Run from Render Shell with production DATABASE_URL, or pass\n"
        f"  --i-know-this-is-production\n"
        f"if you intentionally mean to delete rows on that database.",
        file=sys.stderr,
    )
    raise SystemExit(2)


def warn_if_production_preview() -> None:
    """Print a notice when dry-running against a production-looking database."""
    if is_production_database():
        host = urlparse(database_url()).hostname or "render"
        print(f"Note: DATABASE_URL host is production-like ({host}); dry-run only.\n")
