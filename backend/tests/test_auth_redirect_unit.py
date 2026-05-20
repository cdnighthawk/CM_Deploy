"""Unit tests for shell redirect resolution (no database)."""
from __future__ import annotations

from unittest.mock import patch


def test_resolve_shell_redirect_relative_next(flask_app):
    with flask_app.app_context():
        from app.auth_session import _resolve_shell_redirect

        flask_app.config["CORS_ORIGINS"] = ("http://127.0.0.1:3000",)

        with flask_app.test_request_context(
            "/auth/login",
            headers={"Referer": "http://127.0.0.1:3000/page-login.html?next=usis-hr-hire.html"},
        ):
            assert (
                _resolve_shell_redirect("usis-hr-hire.html")
                == "http://127.0.0.1:3000/usis-hr-hire.html"
            )

        with flask_app.test_request_context(
            "/auth/login",
            headers={"Referer": "http://127.0.0.1:3000/page-login.html"},
        ):
            assert (
                _resolve_shell_redirect("/apply.html") == "http://127.0.0.1:3000/apply.html"
            )


def test_login_redirect_target_for_applicant_session(flask_app):
    with flask_app.app_context():
        from app.auth_session import _login_redirect_target

        flask_app.config["CORS_ORIGINS"] = ("http://127.0.0.1:3000",)
        with flask_app.test_request_context(
            "/auth/login",
            headers={"Referer": "http://127.0.0.1:3000/page-login.html"},
        ):
            with patch("app.permissions.applicant.applicant_only_from_session", return_value=True):
                assert _login_redirect_target(None) == "http://127.0.0.1:3000/apply/application.html"
