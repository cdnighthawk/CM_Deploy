"""Browser session login (email + password) for the USIS app shell."""
from __future__ import annotations

import secrets
import uuid
from urllib.parse import quote, urlparse

from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    request,
    session,
    url_for,
)
from sqlalchemy import select
from werkzeug.security import check_password_hash

from .extensions import db
from .models import User

auth_bp = Blueprint("auth", __name__)


def _post_login_redirect() -> str:
    return (
        current_app.config.get("USIS_POST_LOGIN_REDIRECT")
        or "http://127.0.0.1:3000/usis-dashboard.html"
    ).strip()


def _allowed_shell_origins() -> set[str]:
    """Origins where the static W3CRM shell is served (same list as ``CORS_ORIGINS``)."""
    origins = current_app.config.get("CORS_ORIGINS") or ()
    out: set[str] = set()
    for o in origins:
        s = str(o).strip().rstrip("/").lower()
        if s:
            out.add(s)
    return out


def _safe_shell_redirect(raw: str | None) -> str | None:
    """Return ``raw`` if ``scheme://host[:port]`` is in ``CORS_ORIGINS`` (open-redirect safe)."""
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    try:
        p = urlparse(s)
    except ValueError:
        return None
    if p.scheme not in ("http", "https"):
        return None
    if not p.netloc:
        return None
    origin = f"{p.scheme}://{p.netloc}".lower().rstrip("/")
    if origin in _allowed_shell_origins():
        return s
    return None


def _login_redirect_target(explicit_next: str | None) -> str:
    return _safe_shell_redirect(explicit_next) or _post_login_redirect()


def _shell_template_login_base_url() -> str:
    """``…/page-login.html`` on an allowed shell origin (W3CRM template).

    Prefer ``Referer`` so the host matches the tab the user was on (``localhost`` vs ``127.0.0.1``).
    """
    ref = (request.headers.get("Referer") or "").strip()
    if ref:
        try:
            p = urlparse(ref)
        except ValueError:
            p = None
        if p and p.scheme in ("http", "https") and p.netloc:
            origin = f"{p.scheme}://{p.netloc}".lower().rstrip("/")
            if origin in _allowed_shell_origins():
                return f"{origin}/page-login.html"
    post = _post_login_redirect()
    try:
        p = urlparse(post)
    except ValueError:
        p = None
    if p and p.scheme in ("http", "https") and p.netloc:
        origin = f"{p.scheme}://{p.netloc}".lower().rstrip("/")
        if origin in _allowed_shell_origins():
            return f"{origin}/page-login.html"
    first = next(iter(sorted(_allowed_shell_origins())), None)
    if first:
        return f"{first}/page-login.html"
    return "http://127.0.0.1:3000/page-login.html"


def _redirect_to_shell_login(*, next_after_login: str | None, ms_error: str | None = None) -> str:
    base = _shell_template_login_base_url()
    parts: list[tuple[str, str]] = []
    nxt = (next_after_login or "").strip()
    if nxt:
        parts.append(("next", nxt))
    err = (ms_error or "").strip()
    if err:
        parts.append(("ms_error", err))
    if not parts:
        return base
    sep = "&" if "?" in base else "?"
    q = "&".join(f"{quote(k, safe='')}={quote(v, safe='')}" for k, v in parts)
    return f"{base}{sep}{q}"


def _parse_session_user_id() -> uuid.UUID | None:
    raw = session.get("user_id")
    if raw is None:
        return None
    try:
        return uuid.UUID(str(raw).strip())
    except (ValueError, TypeError, AttributeError):
        return None


@auth_bp.route("/auth/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        uid = _parse_session_user_id()
        if uid is not None:
            u = db.session.get(User, uid)
            if u is not None and u.is_active:
                nxt = request.args.get("next") or ""
                return redirect(_login_redirect_target(nxt))
            session.pop("user_id", None)
        nxt = (request.args.get("next") or "").strip() or None
        return redirect(_redirect_to_shell_login(next_after_login=nxt))

    email = (request.form.get("email") or "").strip().lower()
    password = request.form.get("password") or ""
    remember = request.form.get("remember")
    form_next = (request.form.get("next") or "").strip() or None
    if not email or not password:
        flash("Email and password are required.", "danger")
        if form_next and _safe_shell_redirect(form_next):
            return redirect(url_for("auth.login", next=form_next))
        return redirect(url_for("auth.login"))

    u = db.session.scalar(select(User).where(User.email == email, User.is_active.is_(True)))
    if u is None or not u.password_hash or not check_password_hash(u.password_hash, password):
        flash("Invalid email or password.", "danger")
        if form_next and _safe_shell_redirect(form_next):
            return redirect(url_for("auth.login", next=form_next))
        return redirect(url_for("auth.login"))

    session["user_id"] = str(u.id)
    session.permanent = bool(remember)
    return redirect(_login_redirect_target(form_next))


@auth_bp.get("/auth/logout")
def logout():
    session.pop("user_id", None)
    flash("You have been signed out.", "info")
    nxt = (request.args.get("next") or "").strip() or None
    shell = _safe_shell_redirect(nxt)
    if shell:
        return redirect(shell)
    return redirect(url_for("auth.login"))


MS_ENTRA_STATE_KEY = "ms_entra_oauth_state"
MS_ENTRA_NEXT_KEY = "ms_entra_oauth_next"


@auth_bp.get("/auth/microsoft/start")
def microsoft_sso_start():
    from .integrations import ms_entra_oidc as mso

    cfg = current_app.config
    if not mso.entra_fully_configured(cfg):
        return redirect(_redirect_to_shell_login(next_after_login=None, ms_error="not_configured"))
    tenant = (cfg.get("MS_ENTRA_TENANT_ID") or "").strip()
    client_id = (cfg.get("MS_ENTRA_CLIENT_ID") or "").strip()
    redirect_uri = (cfg.get("MS_ENTRA_REDIRECT_URI") or "").strip()
    state = secrets.token_urlsafe(32)
    session[MS_ENTRA_STATE_KEY] = state
    nxt = (request.args.get("next") or "").strip() or None
    session[MS_ENTRA_NEXT_KEY] = _safe_shell_redirect(nxt)
    scopes = (cfg.get("MS_ENTRA_SCOPES") or "openid profile email offline_access").strip()
    url = mso.build_authorize_url(
        tenant=tenant,
        client_id=client_id,
        redirect_uri=redirect_uri,
        state=state,
        scopes=scopes,
    )
    return redirect(url)


@auth_bp.get("/auth/microsoft/callback")
def microsoft_sso_callback():
    from datetime import datetime, timezone

    from .integrations import ms_entra_oidc as mso

    cfg = current_app.config
    if not mso.entra_fully_configured(cfg):
        return redirect(_redirect_to_shell_login(next_after_login=None, ms_error="not_configured"))

    err = (request.args.get("error") or "").strip()
    if err:
        next_url = session.pop(MS_ENTRA_NEXT_KEY, None)
        session.pop(MS_ENTRA_STATE_KEY, None)
        desc = (request.args.get("error_description") or "").strip()
        current_app.logger.info("Microsoft SSO error from IdP: %s %s", err, desc[:300])
        return redirect(_redirect_to_shell_login(next_after_login=next_url, ms_error="cancelled"))

    state = (request.args.get("state") or "").strip()
    code = (request.args.get("code") or "").strip()
    expected = session.pop(MS_ENTRA_STATE_KEY, None)
    next_url = session.pop(MS_ENTRA_NEXT_KEY, None)
    if not state or not code or not expected or state != expected:
        return redirect(_redirect_to_shell_login(next_after_login=next_url, ms_error="invalid_state"))

    tenant = (cfg.get("MS_ENTRA_TENANT_ID") or "").strip()
    client_id = (cfg.get("MS_ENTRA_CLIENT_ID") or "").strip()
    secret = (cfg.get("MS_ENTRA_CLIENT_SECRET") or "").strip()
    redirect_uri = (cfg.get("MS_ENTRA_REDIRECT_URI") or "").strip()
    try:
        tok = mso.exchange_code_for_tokens(
            tenant=tenant,
            client_id=client_id,
            client_secret=secret,
            redirect_uri=redirect_uri,
            code=code,
        )
        idt = (tok.get("id_token") or "").strip()
        if not idt:
            raise RuntimeError("missing id_token")
        payload = mso.verify_id_token(id_token=idt, client_id=client_id, tenant_id=tenant)
    except Exception as exc:
        current_app.logger.warning("Microsoft SSO token exchange failed: %s", exc)
        return redirect(_redirect_to_shell_login(next_after_login=next_url, ms_error="token"))

    email = mso.claims_email(payload)
    if not email:
        return redirect(_redirect_to_shell_login(next_after_login=next_url, ms_error="no_email"))

    domains = cfg.get("MS_ENTRA_ALLOWED_EMAIL_DOMAINS") or ()
    if domains:
        dom = email.rsplit("@", 1)[-1].lower() if "@" in email else ""
        allowed = {str(d).lower() for d in domains}
        if dom not in allowed:
            return redirect(_redirect_to_shell_login(next_after_login=next_url, ms_error="domain_denied"))

    u = db.session.scalar(select(User).where(User.email == email))
    jit = bool(cfg.get("MS_ENTRA_ALLOW_JIT_USER"))
    if u is None:
        if not jit:
            return redirect(_redirect_to_shell_login(next_after_login=next_url, ms_error="not_registered"))
        u = User(email=email, password_hash=None, is_active=True, is_superuser=False)
        given = (payload.get("given_name") or "").strip()
        family = (payload.get("family_name") or "").strip()
        if not given and not family:
            full = (payload.get("name") or "").strip()
            if full:
                parts = full.split(None, 1)
                given = parts[0]
                family = parts[1] if len(parts) > 1 else ""
        u.first_name = given or None
        u.last_name = family or None
        db.session.add(u)
        db.session.commit()
    if not u.is_active:
        return redirect(_redirect_to_shell_login(next_after_login=next_url, ms_error="inactive"))

    u.last_login_at = datetime.now(timezone.utc)
    db.session.add(u)
    db.session.commit()
    session["user_id"] = str(u.id)
    session.permanent = True
    return redirect(_login_redirect_target(next_url))
