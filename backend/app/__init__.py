"""Flask application factory.

Keep this file thin: it wires extensions, configuration, and (later)
blueprints. All model definitions live under ``app.models``.
"""
from __future__ import annotations

import os
import uuid
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, g, jsonify, request
from flask_cors import CORS

from .config import client_debug_log_dev_open
from .extensions import db, migrate

_BACKEND_DIR = Path(__file__).resolve().parent.parent


def _effective_cors_origins(configured: tuple[str, ...] | list[str] | None) -> list[str]:
    """Merge env-configured origins with common local dev browser origins.

    Gulp/BrowserSync often serves on :3001–:3003 while ``CORS_ORIGINS`` in ``.env`` may only
    list :3000 — without a matching ``Access-Control-Allow-Origin`` the browser surfaces a
    generic ``NetworkError`` on ``fetch``. Optional ``CORS_ORIGINS_EXTRA`` (comma-separated)
    adds LAN/Tailscale origins, e.g. ``http://100.x.x.x:3002``.
    """
    out: list[str] = []
    seen: set[str] = set()
    for raw in list(configured or ()):
        o = str(raw).strip().rstrip("/")
        if not o or o in seen:
            continue
        out.append(o)
        seen.add(o)
    for part in (os.environ.get("CORS_ORIGINS_EXTRA") or "").split(","):
        o = part.strip().rstrip("/")
        if o and o not in seen:
            out.append(o)
            seen.add(o)
    if os.environ.get("FLASK_ENV", "").strip().lower() != "development":
        return out
    hosts = ("127.0.0.1", "localhost")
    ports = (
        3000,
        3001,
        3002,
        3003,
        3004,
        3005,
        5173,
        5174,
        4173,
        8080,
        5500,
        5501,
        9630,
        1234,
        4200,
        4321,
    )
    for h in hosts:
        for p in ports:
            o = f"http://{h}:{p}"
            if o not in seen:
                out.append(o)
                seen.add(o)
        return out


def _apply_production_middleware(app: Flask) -> None:
    """Trust Render reverse proxy and secure session cookies in production."""
    if os.environ.get("FLASK_ENV", "").strip().lower() != "production":
        return
    from werkzeug.middleware.proxy_fix import ProxyFix

    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
    app.config["SESSION_COOKIE_SECURE"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"


def _should_autoload_bc_csv() -> bool:
    raw = (os.environ.get("AUTO_IMPORT_BC_CSV_IF_EMPTY") or "").strip().lower()
    if raw in ("0", "false", "no", "off"):
        return False
    if raw in ("1", "true", "yes", "on"):
        return True
    return os.environ.get("FLASK_ENV", "").strip().lower() == "development"


def create_app(config_object: str | None = None) -> Flask:
    load_dotenv(_BACKEND_DIR / ".env", override=True)

    app = Flask(__name__, instance_relative_config=False)

    app.config.from_object(config_object or "app.config.Config")

    db.init_app(app)
    migrate.init_app(app, db, directory=os.path.join(os.path.dirname(__file__), "..", "migrations"))

    origins = _effective_cors_origins(app.config.get("CORS_ORIGINS"))
    if origins:
        CORS(
            app,
            resources={r"/api/*": {"origins": origins}},
            supports_credentials=True,
        )

    from . import models  # noqa: F401  (register mappers with SQLAlchemy)

    from .auth_session import auth_bp

    app.register_blueprint(auth_bp)
    app.permanent_session_lifetime = app.config.get("PERMANENT_SESSION_LIFETIME", timedelta(days=14))

    from .api import v1_bp
    from .hrms import hrms_bp
    from .public_portal import public_bp

    app.register_blueprint(v1_bp)
    app.register_blueprint(public_bp)
    app.register_blueprint(hrms_bp)

    @app.before_request
    def _require_session_for_api_v1() -> None:
        """All ``/api/v1`` routes require a real signed-in user unless dev-open is enabled."""
        path = request.path.rstrip("/")
        if not path.startswith("/api/v1"):
            return None
        # CORS preflight has no session; must not return 401 or the browser blocks the real request.
        if request.method == "OPTIONS":
            return None
        if path in ("/api/v1/auth/status", "/api/v1/auth/register"):
            return None
        # Cursor debug: client logs to workspace NDJSON (dev only; see POST handler in api.v1).
        if path == "/api/v1/__debug/client-log" and client_debug_log_dev_open():
            return None
        from .api._perms import allow_dev_anonymous_access, current_user

        cu = current_user()
        if cu.user is not None:
            return None
        if allow_dev_anonymous_access():
            return None
        return jsonify({"error": "authentication required"}), 401

    @app.before_request
    def _attach_request_id() -> None:
        rid = (request.headers.get("X-Request-Id") or "").strip() or str(uuid.uuid4())
        g.request_id = rid

    @app.after_request
    def _echo_request_id(response):
        rid = getattr(g, "request_id", None)
        if rid:
            response.headers["X-Request-Id"] = str(rid)
        return response

    @app.get("/healthz")
    def healthz():
        out: dict = {"status": "ok", "request_id": getattr(g, "request_id", None)}
        # Cheap DB sanity check for operators / browser debugging (no secrets).
        try:
            from sqlalchemy import func, select

            from .api.v1 import _lead_estimates_health_count_filter
            from .models.lead_estimate import LeadEstimate

            n = (
                db.session.scalar(
                    select(func.count()).select_from(LeadEstimate).where(_lead_estimates_health_count_filter())
                )
                or 0
            )
            out["lead_estimates_count"] = int(n)
        except Exception:
            out["lead_estimates_count"] = None
        return out

    from .static_shell import register_static_shell

    register_static_shell(app)
    _apply_production_middleware(app)

    if os.environ.get("USIS_BOOTSTRAP_LEADS_ON_STARTUP", "true").strip().lower() in (
        "0",
        "false",
        "no",
        "off",
    ):
        return app

    with app.app_context():
        try:
            from pathlib import Path

            from sqlalchemy import func, select
            from sqlalchemy.exc import IntegrityError, SQLAlchemyError

            from .models.lead_estimate import LeadEstimate

            try:
                n = db.session.scalar(select(func.count()).select_from(LeadEstimate)) or 0
            except SQLAlchemyError as exc:
                app.logger.warning("lead_estimates bootstrap skipped (database unavailable?): %s", exc)
            else:
                csv_path = app.config.get("BC_PROJECTS_CSV")
                csv_exists = bool(csv_path and Path(csv_path).is_file())
                app.logger.info(
                    "lead_estimates bootstrap: count=%s BC_PROJECTS_CSV=%s (file exists=%s) merge_on_startup=%s",
                    n,
                    csv_path or "(unset)",
                    csv_exists,
                    bool(app.config.get("BC_PROJECTS_CSV_MERGE_ON_STARTUP")),
                )

                if csv_path and csv_exists and app.config.get("BC_PROJECTS_CSV_MERGE_ON_STARTUP"):
                    try:
                        from .lead_estimate_csv_load import load_lead_estimates_csv

                        loaded, skipped, errors = load_lead_estimates_csv(
                            db.session, csv_path, mode="upsert", batch_size=1000
                        )
                        app.logger.info(
                            "Merged BuildingConnected CSV on startup: loaded=%s skipped=%s errors=%s file=%s",
                            loaded,
                            skipped,
                            errors,
                            csv_path,
                        )
                        n = db.session.scalar(select(func.count()).select_from(LeadEstimate)) or 0
                    except Exception as exc:
                        app.logger.warning("BuildingConnected CSV merge-on-startup failed: %s", exc)

                if n == 0 and csv_path and Path(csv_path).is_file() and _should_autoload_bc_csv():
                    try:
                        from .lead_estimate_csv_load import load_lead_estimates_csv

                        loaded, skipped, errors = load_lead_estimates_csv(
                            db.session, csv_path, mode="upsert", batch_size=1000
                        )
                        app.logger.info(
                            "Imported BuildingConnected CSV on startup: loaded=%s skipped=%s errors=%s file=%s",
                            loaded,
                            skipped,
                            errors,
                            csv_path,
                        )
                        n = db.session.scalar(select(func.count()).select_from(LeadEstimate)) or 0
                    except Exception as exc:
                        app.logger.warning("BuildingConnected CSV autoload failed: %s", exc)

                try:
                    from .demo_lead_estimates import purge_demo_lead_estimates, upsert_demo_lead_estimates

                    if app.config.get("AUTO_SEED_DEMO_LEADS_IF_EMPTY"):
                        written = upsert_demo_lead_estimates(db.session, force=False)
                        if written:
                            db.session.commit()
                            app.logger.info("Upserted %s demo lead_estimates row(s).", written)
                    else:
                        removed = purge_demo_lead_estimates(db.session)
                        if removed:
                            db.session.commit()
                            app.logger.info("Removed %s template demo lead_estimates row(s).", removed)
                except IntegrityError:
                    db.session.rollback()
                except Exception as exc:
                    db.session.rollback()
                    app.logger.warning("Demo lead_estimates maintenance failed: %s", exc)
        except Exception:
            app.logger.exception("Unexpected error during lead_estimates bootstrap")

    return app
