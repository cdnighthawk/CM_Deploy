"""Serve the Gulp-built W3CRM static shell from Flask (production / Render)."""
from __future__ import annotations

import os
from pathlib import Path

from flask import Blueprint, abort, make_response, redirect, request, send_from_directory, session

static_shell_bp = Blueprint("static_shell", __name__)

_RESERVED_PREFIXES = ("/api/", "/auth/", "/healthz", "/public/")

# Public careers / hiring entry points (no ``.html`` suffix required).
_CAREER_PATH_REDIRECTS: dict[str, str] = {
    "/login": "/page-login.html",
    "/careers": "/apply.html",
    "/apply": "/apply.html",
    "/Apply": "/apply.html",
    "/jobs": "/apply.html",
    "/hiring": "/apply.html",
    "/hire": "/apply/application.html",
    "/ingest": "/construction/ingest.html",
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
    "/people/packet": "/usis-people-hire-detail.html",
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
        "usis-messenger.html",
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


def resolve_landing_root() -> Path | None:
    """Marketing homepage at ``docs/worxcm_landing`` (served on worxcm.com)."""
    raw = (os.environ.get("USIS_LANDING_ROOT") or "").strip()
    if raw:
        root = Path(raw).expanduser().resolve()
    else:
        repo = Path(__file__).resolve().parent.parent.parent
        root = (repo / "docs" / "worxcm_landing").resolve()
    if root.is_dir() and (root / "index.html").is_file():
        return root
    return None


def _is_worxcm_host() -> bool:
    host = (request.host or "").split(":")[0].strip().lower()
    return host == "worxcm.com" or host.endswith(".worxcm.com")


def _serve_worxcm_landing(req_path: str):
    """Homepage and ``/img/*`` for the public product domain. Else None."""
    landing = resolve_landing_root()
    if landing is None or not _is_worxcm_host():
        return None
    if req_path in ("/", "/index.html"):
        return send_from_directory(landing, "index.html")
    if not req_path.startswith("/img/"):
        return None
    rel = req_path.lstrip("/").replace("\\", "/")
    if not rel or ".." in rel.split("/"):
        return branded_404()
    candidate = (landing / rel).resolve()
    try:
        candidate.relative_to(landing.resolve())
    except ValueError:
        return branded_404()
    if candidate.is_file():
        return send_from_directory(landing, rel)
    return branded_404()


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


def saas_console_kind(path: str) -> str | None:
    """Return ``settings`` or ``admin`` for SaaS console URLs; else None.

    ``/admin/organizations`` is the platform console. ``/admin/usis-profile.html``
    and ``/admin/assets/...`` are not — W3CRM already used those relative URLs.
    """
    p = (path or "").split("?", 1)[0].rstrip("/") or "/"
    if p == "/usis-admin.html" or p.endswith("/usis-admin.html"):
        return "admin"
    if p == "/usis-settings.html" or p.endswith("/usis-settings.html"):
        return "settings"
    for prefix, kind in (("/admin", "admin"), ("/settings", "settings")):
        if p == prefix:
            return kind
        if p.startswith(prefix + "/"):
            first = p[len(prefix) + 1 :].split("/", 1)[0]
            if not first or first == "assets" or "." in first:
                return None
            return kind
    return None


def _redirect_html_stolen_by_console(req_path: str, root: Path):
    """``/admin/usis-profile.html`` is My profile, not the platform console."""
    for prefix in ("/admin/", "/settings/"):
        if not req_path.startswith(prefix) or not req_path.endswith(".html"):
            continue
        leaf = req_path.rsplit("/", 1)[-1]
        if not leaf or _is_demo_shell_html(leaf):
            continue
        if (root / leaf).is_file():
            return redirect("/" + leaf, code=302)
    return None


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

    marketing = _serve_worxcm_landing(req_path)
    if marketing is not None:
        return marketing

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
    if req_path in ("/usis-user-directory.html", "/usis-user-directory"):
        return redirect("/settings/people", code=302)
    if req_path == "/settings/users":
        return redirect("/settings/people", code=302)
    if req_path == "/admin/tenants":
        return redirect("/admin/organizations", code=302)
    if req_path.startswith("/admin/tenants/"):
        return redirect("/admin/organizations/" + req_path[len("/admin/tenants/") :], code=302)
    if req_path == "/admin/health":
        return redirect("/admin/usage", code=302)
    stolen = _redirect_html_stolen_by_console(req_path, root)
    if stolen is not None:
        return stolen
    kind = saas_console_kind(req_path)
    if kind == "settings":
        settings_page = root / "usis-settings.html"
        if settings_page.is_file():
            return send_from_directory(root, "usis-settings.html")
    if kind == "admin":
        admin_page = root / "usis-admin.html"
        if admin_page.is_file():
            return send_from_directory(root, "usis-admin.html")

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
