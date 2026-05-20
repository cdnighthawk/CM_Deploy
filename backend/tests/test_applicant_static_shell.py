"""Static shell blocks applicants from staff HTML pages."""
from __future__ import annotations

from unittest.mock import patch

from app.permissions.applicant import APPLICANT_APPLICATION_PATH
from app.static_shell import _redirect_applicant_from_internal_html


def test_redirect_applicant_from_internal_html_blocks_dashboard(flask_app):
    with flask_app.test_request_context("/usis-dashboard-dark.html"):
        with patch("app.permissions.applicant.applicant_only_from_session", return_value=True):
            resp = _redirect_applicant_from_internal_html("usis-dashboard-dark.html")
    assert resp is not None
    assert resp.status_code == 302
    assert resp.headers.get("Location") == APPLICANT_APPLICATION_PATH


def test_redirect_applicant_allows_apply_application(flask_app):
    with flask_app.test_request_context("/apply/application.html"):
        with patch("app.permissions.applicant.applicant_only_from_session", return_value=True):
            resp = _redirect_applicant_from_internal_html("apply/application.html")
    assert resp is None


def test_redirect_applicant_allows_hire_wizard_redirect_page(flask_app):
    with flask_app.test_request_context("/usis-hr-hire.html"):
        with patch("app.permissions.applicant.applicant_only_from_session", return_value=True):
            resp = _redirect_applicant_from_internal_html("usis-hr-hire.html")
    assert resp is None


def test_redirect_staff_user_allows_dashboard(flask_app):
    with flask_app.test_request_context("/usis-dashboard-dark.html"):
        with patch("app.permissions.applicant.applicant_only_from_session", return_value=False):
            resp = _redirect_applicant_from_internal_html("usis-dashboard-dark.html")
    assert resp is None
