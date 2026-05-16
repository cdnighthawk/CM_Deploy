"""Application configuration.

All values are sourced from environment variables (loaded from .env in
``create_app``). Add new groups here rather than scattering ``os.environ``
calls across the codebase.
"""
from __future__ import annotations

import os
from datetime import timedelta


def _normalize_database_url(url: str) -> str:
    """Render/Heroku often provide ``postgres://``; SQLAlchemy needs ``postgresql+psycopg://``."""
    u = (url or "").strip()
    if not u:
        return u
    if u.startswith("postgres://"):
        return "postgresql+psycopg://" + u[len("postgres://") :]
    if u.startswith("postgresql://") and not u.startswith("postgresql+psycopg://"):
        return "postgresql+psycopg://" + u[len("postgresql://") :]
    return u


def _env_database_url() -> str:
    return _normalize_database_url(
        os.environ.get(
            "DATABASE_URL",
            "postgresql+psycopg://usis_app:CHANGE_ME_APP_PASSWORD@localhost:5432/usis_cm",
        )
    )


def _render_external_url() -> str:
    return (os.environ.get("RENDER_EXTERNAL_URL") or "").strip().rstrip("/")


def _default_post_login_redirect() -> str:
    explicit = (os.environ.get("USIS_POST_LOGIN_REDIRECT") or "").strip()
    if explicit:
        return explicit
    render_base = _render_external_url()
    if render_base:
        return f"{render_base}/usis-dashboard.html"
    return "http://127.0.0.1:3000/usis-dashboard.html"


def _default_cors_origins() -> tuple[str, ...]:
    explicit = (os.environ.get("CORS_ORIGINS") or "").strip()
    if explicit:
        return tuple(o.strip() for o in explicit.split(",") if o.strip())
    render_base = _render_external_url()
    if render_base:
        return (render_base,)
    return tuple(
        o.strip()
        for o in (
            "http://127.0.0.1:3000,http://localhost:3000,"
            "http://127.0.0.1:3001,http://localhost:3001,"
            "http://127.0.0.1:3002,http://localhost:3002,"
            "http://127.0.0.1:3003,http://localhost:3003,"
            "http://127.0.0.1:5000,http://localhost:5000,"
            "http://127.0.0.1:5500,http://localhost:5500"
        ).split(",")
        if o.strip()
    )


class Config:
    SECRET_KEY: str = os.environ.get("SECRET_KEY", "dev-insecure-change-me")

    # After successful ``POST /auth/login``, redirect browser here (Gulp / static shell).
    USIS_POST_LOGIN_REDIRECT: str = _default_post_login_redirect()

    # Optional override for the marketing logo on ``/auth/login`` (defaults to GoUSIS header asset).
    USIS_PUBLIC_LOGO_URL: str | None = (os.environ.get("USIS_PUBLIC_LOGO_URL") or "").strip() or None

    # Allow ``POST /api/v1/auth/register`` for hire / self-service account creation.
    _self_reg_raw = (os.environ.get("USIS_ALLOW_SELF_REGISTER") or "").strip().lower()
    if _self_reg_raw in ("0", "false", "no", "off"):
        USIS_ALLOW_SELF_REGISTER: bool = False
    elif _self_reg_raw in ("1", "true", "yes", "on"):
        USIS_ALLOW_SELF_REGISTER: bool = True
    else:
        USIS_ALLOW_SELF_REGISTER: bool = os.environ.get("FLASK_ENV", "").strip().lower() == "development"

    _perm_days_raw = (os.environ.get("PERMANENT_SESSION_DAYS") or "14").strip()
    try:
        _perm_days = max(1, min(int(_perm_days_raw), 365))
    except ValueError:
        _perm_days = 14
    PERMANENT_SESSION_LIFETIME = timedelta(days=_perm_days)

    # Comma-separated browser origins allowed to call ``/api/*`` (W3CRM / Live Server / etc.).
    CORS_ORIGINS: tuple[str, ...] = _default_cors_origins()

    SQLALCHEMY_DATABASE_URI: str = _env_database_url()

    # Gulp ``dist`` folder for production static shell (Render sets this in render.yaml).
    USIS_STATIC_ROOT: str | None = (os.environ.get("USIS_STATIC_ROOT") or "").strip() or None
    SQLALCHEMY_TRACK_MODIFICATIONS: bool = False
    SQLALCHEMY_ENGINE_OPTIONS: dict = {
        "pool_pre_ping": True,
    }

    JSON_SORT_KEYS: bool = False

    # Optional path to a BuildingConnected ``bc_projects`` CSV; used for startup import when enabled.
    BC_PROJECTS_CSV: str | None = (os.environ.get("BC_PROJECTS_CSV") or "").strip() or None

    # If true and ``BC_PROJECTS_CSV`` points to a file: upsert that CSV on every app startup (not only when the table is empty).
    _merge_csv_raw = (os.environ.get("BC_PROJECTS_CSV_MERGE_ON_STARTUP") or "").strip().lower()
    if _merge_csv_raw in ("1", "true", "yes", "on"):
        BC_PROJECTS_CSV_MERGE_ON_STARTUP: bool = True
    else:
        BC_PROJECTS_CSV_MERGE_ON_STARTUP: bool = False

    # When enabled: upsert three canonical demo ``lead_estimates`` rows on every app startup
    # (keyed by ``usis-seed-demo-*`` ``external_id``). Defaults on in ``FLASK_ENV=development``.
    _auto_seed_raw = (os.environ.get("AUTO_SEED_DEMO_LEADS_IF_EMPTY") or "").strip().lower()
    if _auto_seed_raw in ("0", "false", "no", "off"):
        AUTO_SEED_DEMO_LEADS_IF_EMPTY: bool = False
    elif _auto_seed_raw in ("1", "true", "yes", "on"):
        AUTO_SEED_DEMO_LEADS_IF_EMPTY: bool = True
    else:
        AUTO_SEED_DEMO_LEADS_IF_EMPTY: bool = os.environ.get("FLASK_ENV", "").strip().lower() == "development"

    # Mutating takeoff/estimate line APIs (POST/PATCH/DELETE). Off by default outside development.
    _tw_raw = (os.environ.get("TAKEOFF_API_WRITES_ENABLED") or "").strip().lower()
    if _tw_raw in ("1", "true", "yes", "on"):
        TAKEOFF_API_WRITES_ENABLED: bool = True
    elif _tw_raw in ("0", "false", "no", "off"):
        TAKEOFF_API_WRITES_ENABLED: bool = False
    else:
        TAKEOFF_API_WRITES_ENABLED: bool = os.environ.get("FLASK_ENV", "").strip().lower() == "development"

    # --- Autodesk / BuildingConnected (APS 3-legged OAuth + BC REST) ---
    AUTODESK_CLIENT_ID: str | None = (os.environ.get("AUTODESK_CLIENT_ID") or "").strip() or None
    AUTODESK_CLIENT_SECRET: str | None = (os.environ.get("AUTODESK_CLIENT_SECRET") or "").strip() or None
    AUTODESK_OAUTH_REDIRECT_URI: str | None = (os.environ.get("AUTODESK_OAUTH_REDIRECT_URI") or "").strip() or None
    # Space-separated APS scopes (e.g. ``data:read``). Must match the app registration.
    AUTODESK_OAUTH_SCOPES: str = (os.environ.get("AUTODESK_OAUTH_SCOPES") or "data:read").strip() or "data:read"
    BUILDINGCONNECTED_API_BASE: str = (
        (os.environ.get("BUILDINGCONNECTED_API_BASE") or "").strip()
        or "https://developer.api.autodesk.com/construction/buildingconnected/v2"
    )
    _bc_sync_raw = (os.environ.get("BUILDINGCONNECTED_SYNC_ENABLED") or "").strip().lower()
    if _bc_sync_raw in ("1", "true", "yes", "on"):
        BUILDINGCONNECTED_SYNC_ENABLED: bool = True
    elif _bc_sync_raw in ("0", "false", "no", "off"):
        BUILDINGCONNECTED_SYNC_ENABLED: bool = False
    else:
        BUILDINGCONNECTED_SYNC_ENABLED: bool = os.environ.get("FLASK_ENV", "").strip().lower() == "development"
    _bc_closed_raw = (os.environ.get("BUILDINGCONNECTED_INCLUDE_CLOSED") or "").strip().lower()
    if _bc_closed_raw in ("0", "false", "no", "off"):
        BUILDINGCONNECTED_INCLUDE_CLOSED: bool = False
    else:
        BUILDINGCONNECTED_INCLUDE_CLOSED: bool = True
    # Optional 32+ byte secret for Fernet; defaults to a SHA256-derived key from SECRET_KEY.
    TOKEN_ENCRYPTION_KEY: str | None = (os.environ.get("TOKEN_ENCRYPTION_KEY") or "").strip() or None

    # Letterhead for Jinja2 print documents (``app/templates/documents/``).
    DOCUMENT_PRINT_COMPANY_NAME: str | None = (os.environ.get("DOCUMENT_PRINT_COMPANY_NAME") or "").strip() or None

    # Drawing PDFs uploaded via ``POST /api/v1/projects/<id>/drawings`` (defaults under Flask ``instance/``).
    DRAWING_UPLOAD_FOLDER: str | None = (os.environ.get("DRAWING_UPLOAD_FOLDER") or "").strip() or None
    # Spec section PDFs (``POST .../rfi-lookups/spec_sections/<id>/file``); defaults under ``instance/``.
    SPEC_SECTION_UPLOAD_FOLDER: str | None = (os.environ.get("SPEC_SECTION_UPLOAD_FOLDER") or "").strip() or None
    # RFI attachment binaries (``POST /api/v1/rfis/<id>/attachments/upload``).
    RFI_ATTACHMENT_UPLOAD_FOLDER: str | None = (os.environ.get("RFI_ATTACHMENT_UPLOAD_FOLDER") or "").strip() or None
    # I-9 supporting document photos (hire wizard); defaults under Flask ``instance/``.
    HR_I9_DOCUMENT_UPLOAD_FOLDER: str | None = (
        os.environ.get("HR_I9_DOCUMENT_UPLOAD_FOLDER") or ""
    ).strip() or None
    # W-4 supporting document photos (hire wizard); defaults under Flask ``instance/``.
    HR_W4_DOCUMENT_UPLOAD_FOLDER: str | None = (
        os.environ.get("HR_W4_DOCUMENT_UPLOAD_FOLDER") or ""
    ).strip() or None
    # Union card / dispatch photos (hire wizard); defaults under Flask ``instance/``.
    HR_UNION_DOCUMENT_UPLOAD_FOLDER: str | None = (
        os.environ.get("HR_UNION_DOCUMENT_UPLOAD_FOLDER") or ""
    ).strip() or None

    # --- Microsoft Entra ID (Azure AD) SSO for ``/auth/microsoft/*`` ---
    # Register a single-page / web app in Entra, add redirect URI = MS_ENTRA_REDIRECT_URI
    # (e.g. ``http://127.0.0.1:5000/auth/microsoft/callback``). Token ``tid`` must match tenant when not common.
    MS_ENTRA_TENANT_ID: str | None = (os.environ.get("MS_ENTRA_TENANT_ID") or "").strip() or None
    MS_ENTRA_CLIENT_ID: str | None = (os.environ.get("MS_ENTRA_CLIENT_ID") or "").strip() or None
    MS_ENTRA_CLIENT_SECRET: str | None = (os.environ.get("MS_ENTRA_CLIENT_SECRET") or "").strip() or None
    MS_ENTRA_REDIRECT_URI: str | None = (os.environ.get("MS_ENTRA_REDIRECT_URI") or "").strip() or None
    MS_ENTRA_SCOPES: str = (
        (os.environ.get("MS_ENTRA_SCOPES") or "").strip() or "openid profile email offline_access"
    )
    _ms_jit_raw = (os.environ.get("MS_ENTRA_ALLOW_JIT_USER") or "").strip().lower()
    if _ms_jit_raw in ("1", "true", "yes", "on"):
        MS_ENTRA_ALLOW_JIT_USER: bool = True
    elif _ms_jit_raw in ("0", "false", "no", "off"):
        MS_ENTRA_ALLOW_JIT_USER: bool = False
    else:
        MS_ENTRA_ALLOW_JIT_USER: bool = False
    MS_ENTRA_ALLOWED_EMAIL_DOMAINS: tuple[str, ...] = tuple(
        d.strip().lower().lstrip("@")
        for d in (os.environ.get("MS_ENTRA_ALLOWED_EMAIL_DOMAINS") or "").split(",")
        if d.strip()
    )


def client_debug_log_dev_open() -> bool:
    """True when anonymous ``POST /api/v1/__debug/client-log`` is allowed (local dev only).

    ``FLASK_ENV=development`` is the explicit signal; ``FLASK_DEBUG`` / ``app.debug`` cover
    typical ``flask run`` defaults when ``FLASK_ENV`` is unset. Production should keep
    ``debug=False`` and avoid ``FLASK_DEBUG=1`` so this stays off.
    """
    if os.environ.get("FLASK_ENV", "").strip().lower() == "development":
        return True
    if (os.environ.get("FLASK_DEBUG") or "").strip().lower() in ("1", "true", "yes", "on"):
        return True
    try:
        from flask import current_app, has_app_context

        return bool(has_app_context() and current_app.debug)
    except RuntimeError:
        return False
