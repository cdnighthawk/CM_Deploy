"""Unit tests for hire path helpers (no database)."""
from __future__ import annotations

from datetime import datetime, timezone

from app.models import HrHireApplication
from app.services.hire_application_review import (
    HIRE_STATUS_OFFER_EXTENDED,
    HIRE_STATUS_SUBMITTED,
    allowed_hr_status_transition,
    can_hr_manual_hire,
)
from app.services.hire_path import (
    applicant_may_complete_i9_w4,
    applicant_may_upload_union,
)


def _row(**kwargs) -> HrHireApplication:
    row = HrHireApplication(user_id=kwargs.pop("user_id", None))
    for key, val in kwargs.items():
        setattr(row, key, val)
    return row


def test_union_path_allows_i9_after_application_submitted():
    row = _row(
        hire_path="union_dispatch",
        submitted_at=datetime.now(timezone.utc),
    )
    assert applicant_may_complete_i9_w4(row) is True


def test_standard_path_blocks_i9_until_offer_accepted():
    row = _row(
        hire_path="standard",
        submitted_at=datetime.now(timezone.utc),
        hire_status=HIRE_STATUS_SUBMITTED,
    )
    assert applicant_may_complete_i9_w4(row) is False
    row.offer_accepted_at = datetime.now(timezone.utc)
    assert applicant_may_complete_i9_w4(row) is True


def test_union_upload_only_for_union_dispatch_after_w4():
    row = _row(hire_path="standard", w4_signed_at=datetime.now(timezone.utc))
    assert applicant_may_upload_union(row) is False
    row.hire_path = "union_dispatch"
    assert applicant_may_upload_union(row) is True


def test_hr_offer_status_transitions():
    assert allowed_hr_status_transition(HIRE_STATUS_SUBMITTED, HIRE_STATUS_OFFER_EXTENDED) is True
    assert allowed_hr_status_transition(HIRE_STATUS_OFFER_EXTENDED, HIRE_STATUS_OFFER_EXTENDED) is False


def test_can_hr_manual_hire_standard_false():
    row = _row(hire_path="standard", hire_status=HIRE_STATUS_SUBMITTED)
    assert can_hr_manual_hire(row) is False


def test_can_hr_manual_hire_union_true():
    row = _row(hire_path="union_dispatch", hire_status=HIRE_STATUS_SUBMITTED)
    assert can_hr_manual_hire(row) is True


def test_can_hr_manual_hire_unset_path_false():
    row = _row(hire_path=None, hire_status=HIRE_STATUS_SUBMITTED)
    assert can_hr_manual_hire(row) is False


def test_can_hr_send_offer_unset_path_true():
    from app.services.hire_application_review import can_hr_send_offer

    row = _row(hire_path=None, hire_status=HIRE_STATUS_SUBMITTED)
    assert can_hr_send_offer(row) is True


def test_can_hr_send_offer_union_false():
    from app.services.hire_application_review import can_hr_send_offer

    row = _row(hire_path="union_dispatch", hire_status=HIRE_STATUS_SUBMITTED)
    assert can_hr_send_offer(row) is False
