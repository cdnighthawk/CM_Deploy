"""Unit tests for hire application letter email content (no database)."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest


@pytest.fixture
def letter_context(flask_app):
    with flask_app.app_context():
        user = SimpleNamespace(
            email="applicant@example.com",
            first_name="Jane",
            last_name="Applicant",
        )
        hire_row = SimpleNamespace(
            application_json='{"position_applying_for": "Foreman"}',
            review_notes="Thank you for interviewing with us.",
            reviewed_at=None,
            offer_position=None,
            offer_start_date=None,
        )
        yield user, hire_row


def test_send_rejection_letter_email_builds_html(letter_context):
    from app.api._notifications import send_application_rejection_letter_email

    user, hire_row = letter_context
    with patch("app.api._notifications.send_html_notification_email") as send:
        send.return_value = {"sent": True, "dry_run": False, "error": None}
        result = send_application_rejection_letter_email(user=user, hire_row=hire_row)

    assert result["sent"] is True
    kwargs = send.call_args.kwargs
    assert "Foreman" in kwargs["body"]
    assert "interviewing" in kwargs["body"]
    assert kwargs["html_body"] is not None
    assert "interviewing" in kwargs["html_body"]


def test_send_approval_letter_email_builds_html(letter_context):
    from app.api._notifications import send_application_approval_letter_email

    user, hire_row = letter_context
    hire_row.offer_position = "Foreman"
    with patch("app.api._notifications.send_html_notification_email") as send:
        send.return_value = {"sent": True, "dry_run": False, "error": None}
        result = send_application_approval_letter_email(user=user, hire_row=hire_row)

    assert result["sent"] is True
    kwargs = send.call_args.kwargs
    assert "approved" in kwargs["body"].lower()
    assert "page-login.html" in kwargs["body"]
    assert kwargs["html_body"] is not None
