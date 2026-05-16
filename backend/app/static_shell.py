"""Serve the Gulp-built W3CRM static shell from Flask (production / Render)."""
from __future__ import annotations

import os
from pathlib import Path

from flask import Blueprint, abort, redirect, send_from_directory

static_shell_bp = Blueprint("static_shell", __name__)

_RESERVED_PREFIXES = ("/api/", "/auth/", "/healthz")


def resolve_static_root() -> Path | None:
    """Return absolute path to ``gulp/dist`` or None if missing."""
    raw = (os.environ.get("USIS_STATIC_ROOT") or "").strip()
    if raw:
        root = Path(raw).expanduser().resolve()
    else:
        backend_dir = Path(__file__).resolve().parent.parent
        root = (backend_dir.parent / "W3CRM-v3.0-13_September_2025" / "gulp" / "dist").resolve()
    if root.is_dir():
        return root
    return None


def _is_reserved(path: str) -> bool:
    p = path if path.startswith("/") else f"/{path}"
    if p == "/healthz":
        return True
    return any(p.startswith(prefix) for prefix in _RESERVED_PREFIXES)


@static_shell_bp.route("/", defaults={"subpath": ""})
@static_shell_bp.route("/<path:subpath>")
def serve_static(subpath: str):
    """Serve built HTML/assets; API/auth routes are registered on the app first."""
    req_path = ("/" + subpath.lstrip("/")).rstrip("/") or "/"
    if _is_reserved(req_path):
        abort(404)

    root = resolve_static_root()
    if root is None:
        abort(
            503,
            "Static UI not found. Set USIS_STATIC_ROOT or run gulp build "
            "(W3CRM-v3.0-13_September_2025/gulp/dist).",
        )

    if req_path == "/":
        home = root / "usis-dashboard-dark.html"
        if home.is_file():
            return redirect("/usis-dashboard-dark.html", code=302)
        login = root / "page-login.html"
        if login.is_file():
            return redirect("/page-login.html", code=302)
        index = root / "index.html"
        if index.is_file():
            return send_from_directory(root, "index.html")
        abort(404)

    rel = subpath.lstrip("/")
    candidate = (root / rel).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        abort(404)

    if candidate.is_file():
        return send_from_directory(root, rel)

    if candidate.is_dir():
        index = candidate / "index.html"
        if index.is_file():
            return send_from_directory(candidate, "index.html")

    if not rel.endswith(".html"):
        html_candidate = root / f"{rel}.html"
        if html_candidate.is_file():
            return send_from_directory(root, f"{rel}.html")

    abort(404)


def register_static_shell(app) -> None:
    """Mount static routes only when a dist folder exists or USIS_STATIC_ROOT is set."""
    root = resolve_static_root()
    force = bool((os.environ.get("USIS_STATIC_ROOT") or "").strip())
    if root is None and not force:
        app.logger.warning(
            "Static shell disabled: gulp/dist not found at %s",
            (Path(__file__).resolve().parent.parent.parent / "W3CRM-v3.0-13_September_2025" / "gulp" / "dist"),
        )
        return
    if root is None:
        app.logger.error("USIS_STATIC_ROOT is set but path is not a directory")
        return
    app.register_blueprint(static_shell_bp)
    app.logger.info("Serving W3CRM static shell from %s", root)
