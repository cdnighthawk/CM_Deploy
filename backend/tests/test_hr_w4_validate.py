"""Unit tests for W-4 validation."""
from __future__ import annotations

from app.services.hr_w4_validate import validate_w4


def _sample_w4(**overrides):
    base = {
        "first_name": "Jamie",
        "last_name": "Rivera",
        "middle_initial": "",
        "address": "100 Test St",
        "city": "Denver",
        "state": "CO",
        "zip": "80202",
        "ssn": "123-45-6789",
        "filing_status": "single",
        "multiple_jobs": False,
        "higher_withholding": False,
        "dependents_amount": "",
        "other_income": "",
        "deductions": "",
        "extra_withholding": "",
        "exempt_claim": False,
    }
    base.update(overrides)
    return base


def test_validate_w4_ok():
    data, errors = validate_w4(_sample_w4())
    assert errors == []
    assert data is not None
    assert data["filing_status"] == "single"


def test_validate_w4_exempt_conflict():
    data, errors = validate_w4(
        _sample_w4(exempt_claim=True, dependents_amount="100", multiple_jobs=True)
    )
    assert data is None
    assert any("Exempt" in e for e in errors)
