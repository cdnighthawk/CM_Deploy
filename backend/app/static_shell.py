"""Serve the Gulp-built W3CRM static shell from Flask (production / Render)."""
from __future__ import annotations

import os
from pathlib import Path

from flask import Blueprint, abort, make_response, redirect, send_from_directory, session

static_shell_bp = Blueprint("static_shell", __name__)

_RESERVED_PREFIXES = ("/api/", "/auth/", "/healthz")

# Public careers / hiring entry points (no ``.html`` suffix required).
_CAREER_PATH_REDIRECTS: dict[str, str] = {
    "/careers": "/apply.html",
    "/apply": "/apply.html",
    "/Apply": "/apply.html",
    "/jobs": "/apply.html",
    "/hiring": "/apply.html",
    "/hire": "/apply/application.html",
    "/time": "/usis-time-live.html",
    "/time/live": "/usis-time-live.html",
    "/time/me": "/usis-time-me.html",
    "/time/cards": "/usis-time-cards.html",
    "/time/events": "/usis-time-events.html",
    "/time/exceptions": "/usis-time-exceptions.html",
    "/time/payroll": "/usis-time-payroll.html",
    "/time/map": "/usis-time-map.html",
    "/time/settings": "/usis-time-settings.html",
    "/people": "/usis-people-hiring.html",
    "/people/hiring": "/usis-people-hiring.html",
    "/people/directory": "/usis-people-directory.html",
}

# Case-insensitive aliases (marketing links often use ``Apply.html``).
_CASE_INSENSITIVE_HTML_REDIRECTS: dict[str, str] = {
    "/apply.html": "/apply.html",
}

# Duplicate USIS shells → the page staff should actually use.
_PRODUCT_HTML_REDIRECTS: dict[str, str] = {
    "/usis-dashboard.html": "/usis-dashboard-dark.html",
    "/usis-leads.html": "/construction/leads.html",
    "/usis-hr.html": "/usis-hr-dashboard.html",
    "/core-hr.html": "/usis-hr-dashboard.html",
    "/usis-hrms-home.html": "/usis-hr-dashboard.html",
}

# W3CRM leftover templates. Live USIS pages are not in this set.
_DEMO_HTML_PREFIXES: tuple[str, ...] = (
    "ecom-",
    "aikit/",
    "cms/",
    "account/",
    "profile/",
    "essentials/",
)

_DEMO_HTML_EXACT: frozenset[str] = frozenset(
    {
        "index-2.html",
        "blog.html",
        "chat.html",
        "contacts.html",
        "customer.html",
        "customer-profile.html",
        "employee.html",
        "empty-page.html",
        "finance.html",
        "manage-client.html",
        "performance.html",
        "post-details.html",
        "project.html",
        "task.html",
        "task-summary.html",
        "user.html",
        "user-roles.html",
        "add-role.html",
        "edit-profile.html",
        "app-calender.html",
        "app-profile.html",
        "app-profile-2.html",
        "email-inbox.html",
        "email-read.html",
        "email-compose.html",
        "usis-all-pages-index.html",
        "construction/add-quotation.html",
        "construction/attendance.html",
        "construction/contact-us.html",
        "construction/edit-quotation.html",
        "construction/estimate_legacy.html",
        "construction/files.html",
        "construction/finance.html",
        "construction/mom.html",
        "construction/mom-detail.html",
        "construction/overview.html",
        "construction/party.html",
        "construction/quotation.html",
        "construction/reports.html",
        "construction/services.html",
        "construction/task.html",
        "construction/time-sheet.html",
        "construction/timesheet-detail.html",
        "construction/todo.html",
        "construction/todo-detail.html",
        "construction/transaction.html",
    }
)


@static_shell_bp.route("/construction/index.html")
@static_shell_bp.route("/construction", strict_slashes=False)
def redirect_legacy_construction_index():
    """Old W3CRM demo dashboard; real jobs live on the projects list."""
    return redirect("/construction/projects.html", code=302)


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


def _redirect_applicant_from_internal_html(rel: str):
    """Block staff shell HTML for applicant-only sessions."""
    from .permissions.applicant import (
        applicant_only_from_session,
        is_applicant_public_shell_path,
    )

    if not rel.lower().endswith(".html"):
        return None
    if is_applicant_public_shell_path(rel):
        return None
    if not applicant_only_from_session(session.get("user_id")):
        return None
    from .permissions.applicant import APPLICANT_APPLICATION_PATH

    return redirect(APPLICANT_APPLICATION_PATH, code=302)


def _html_rel(rel: str) -> str:
    return (rel or "").replace("\\", "/").lstrip("/").lower()


def _is_demo_shell_html(rel: str) -> bool:
    name = _html_rel(rel)
    if not name.endswith(".html"):
        return False
    if name in _DEMO_HTML_EXACT:
        return True
    return any(name.startswith(prefix) for prefix in _DEMO_HTML_PREFIXES)


def branded_404():
    """USIS 404 page when the static shell exists; otherwise Flask's default."""
    root = resolve_static_root()
    if root is not None and (root / "page-error-404.html").is_file():
        resp = make_response(send_from_directory(root, "page-error-404.html"))
        resp.status_code = 404
        return resp
    abort(404)


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

    product_target = _PRODUCT_HTML_REDIRECTS.get(req_path.lower())
    if product_target:
        return redirect(product_target, code=302)

    if req_path == "/index.html":
        home = root / "usis-dashboard-dark.html"
        if home.is_file():
            return redirect("/usis-dashboard-dark.html", code=302)

    if req_path in ("/construction/index.html", "/construction"):
        return redirect("/construction/projects.html", code=302)

    # Dev-open mode may skip the home page, but never skip the login form.
    # Reviewer/username logins need /page-login.html to stay reachable.
    if req_path == "/":
        raw = (os.environ.get("USIS_API_DEV_ALLOW_ANY") or "").strip().lower()
        if raw not in ("", "0", "false", "no", "off"):
            home = root / "usis-dashboard-dark.html"
            if home.is_file():
                return redirect("/usis-dashboard-dark.html", code=302)

    if req_path == "/":
        login = root / "page-login.html"
        if login.is_file():
            return redirect("/page-login.html", code=302)
        home = root / "usis-dashboard-dark.html"
        if home.is_file():
            return redirect("/usis-dashboard-dark.html", code=302)
        apply = root / "apply.html"
        if apply.is_file():
            return redirect("/apply.html", code=302)
        index = root / "index.html"
        if index.is_file():
            return send_from_directory(root, "index.html")
        return branded_404()

    career_target = _CAREER_PATH_REDIRECTS.get(req_path)
    if career_target:
        return redirect(career_target, code=302)

    case_target = _CASE_INSENSITIVE_HTML_REDIRECTS.get(req_path.lower())
    if case_target and req_path != case_target:
        return redirect(case_target, code=302)

    rel = subpath.lstrip("/")
    candidate = (root / rel).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return branded_404()

    if candidate.is_file():
        if _is_demo_shell_html(rel):
            return branded_404()
        blocked = _redirect_applicant_from_internal_html(rel)
        if blocked is not None:
            return blocked
        return send_from_directory(root, rel)

    if candidate.is_dir():
        index = candidate / "index.html"
        if index.is_file():
            return send_from_directory(candidate, "index.html")

    if not rel.endswith(".html"):
        html_candidate = root / f"{rel}.html"
        if html_candidate.is_file():
            html_rel = f"{rel}.html"
            product_html = _PRODUCT_HTML_REDIRECTS.get("/" + _html_rel(html_rel))
            if product_html:
                return redirect(product_html, code=302)
            if _is_demo_shell_html(html_rel):
                return branded_404()
            blocked = _redirect_applicant_from_internal_html(html_rel)
            if blocked is not None:
                return blocked
            return send_from_directory(root, html_rel)

    return branded_404()


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
