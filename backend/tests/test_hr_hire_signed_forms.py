"""Tests for signed hire form document rendering."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.models import User
from app.services.hr_hire_signed_forms import render_signed_i9_html, render_signed_w4_html


def test_render_signed_i9_html_includes_signature(flask_app):
    user = User(
        id=uuid.uuid4(),
        email="applicant@example.com",
        first_name="Jane",
        last_name="Applicant",
    )
    section1 = {
        "first_name": "Jane",
        "last_name": "Applicant",
        "address": "1 Main St",
        "city": "Austin",
        "state": "TX",
        "zip": "78701",
        "date_of_birth": "1990-01-02",
        "ssn": "123-45-6789",
        "citizenship_status": "citizen",
        "document_choice": "list_a",
        "list_a": {
            "title": "U.S. Passport",
            "issuing_authority": "US DOS",
            "number": "P123",
            "expiration": "2030-01-01",
        },
    }
    sig = "data:image/png;base64,iVBORw0KGgo="
    with flask_app.app_context():
        html = render_signed_i9_html(
            user=user,
            section1=section1,
            signature_png=sig,
            signed_at=datetime(2026, 5, 20, 12, 0, tzinfo=timezone.utc),
            typed_full_name="Jane Applicant",
        )
    assert "Form I-9 Section 1" in html
    assert "Jane Applicant" in html
    assert sig in html
    assert "U.S. Passport" in html


def test_render_signed_w4_html_includes_filing_status(flask_app):
    user = User(
        id=uuid.uuid4(),
        email="applicant@example.com",
        first_name="Jane",
        last_name="Applicant",
    )
    w4 = {
        "first_name": "Jane",
        "last_name": "Applicant",
        "address": "1 Main St",
        "city": "Austin",
        "state": "TX",
        "zip": "78701",
        "ssn": "123-45-6789",
        "filing_status": "single",
        "signature_date": "2026-05-20",
    }
    sig = "data:image/png;base64,iVBORw0KGgo="
    with flask_app.app_context():
        html = render_signed_w4_html(
            user=user,
            w4=w4,
            signature_png=sig,
            signed_at=datetime(2026, 5, 20, 12, 0, tzinfo=timezone.utc),
            typed_full_name="Jane Applicant",
        )
    assert "Form W-4" in html
    assert "Single or Married filing separately" in html
    assert sig in html
