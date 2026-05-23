from __future__ import annotations

from types import SimpleNamespace

from app.services.hire_application_mappings import (
    map_application_to_i9_prefill,
    map_application_to_w4_prefill,
    merge_application_into_i9_draft,
    normalize_ssn,
)


def _user():
    return SimpleNamespace(
        first_name="Jamie",
        last_name="Rivera",
        email="jamie@example.com",
        phone="555-0100",
    )


def test_normalize_ssn_formats_digits():
    assert normalize_ssn("123456789") == "123-45-6789"
    assert normalize_ssn("123-45-6789") == "123-45-6789"
    assert normalize_ssn("bad") is None


def test_map_application_to_i9_prefill():
    app = {
        "address_line1": "100 Main",
        "address_line2": "Apt 2",
        "city": "Denver",
        "state": "CO",
        "postal_code": "80202",
        "date_of_birth": "01/15/1990",
        "ssn": "123-45-6789",
        "middle_initial": "Q",
        "citizenship_status": "citizen",
    }
    out = map_application_to_i9_prefill(_user(), app)
    assert out["first_name"] == "Jamie"
    assert out["apt"] == "Apt 2"
    assert out["date_of_birth"] == "1990-01-15"
    assert out["ssn"] == "123-45-6789"
    assert out["citizenship_status"] == "citizen"
    assert out["email"] == "jamie@example.com"


def test_map_application_to_w4_prefill():
    app = {
        "address_line1": "100 Main",
        "city": "Denver",
        "state": "CO",
        "postal_code": "80202",
        "ssn": "123456789",
        "middle_initial": "Q",
        "filing_status": "single",
        "dependents_amount": "500",
        "other_income": "1000",
        "deductions": "200",
    }
    out = map_application_to_w4_prefill(_user(), app)
    assert out["filing_status"] == "single"
    assert out["dependents_amount"] == "500"
    assert out["ssn"] == "123-45-6789"


def test_merge_application_into_i9_draft_preserves_documents():
    draft = {
        "first_name": "Old",
        "document_choice": "list_a",
        "list_a": {"document_type": "us_passport", "title": "U.S. Passport", "number": "X1"},
    }
    merged = merge_application_into_i9_draft(
        draft,
        user=_user(),
        app={"address_line1": "200 Oak", "ssn": "123-45-6789", "citizenship_status": "citizen"},
    )
    assert merged["address"] == "200 Oak"
    assert merged["first_name"] == "Jamie"
    assert merged["list_a"]["number"] == "X1"
