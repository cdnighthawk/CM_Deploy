"""HR review workflow for hire wizard applications."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from ..models import HrHireApplication
from ..services.object_storage import UploadCategory, delete_stored

HIRE_STATUS_IN_PROGRESS = "in_progress"
HIRE_STATUS_SUBMITTED = "submitted"
HIRE_STATUS_UNDER_REVIEW = "under_review"
HIRE_STATUS_HIRED = "hired"
HIRE_STATUS_REJECTED = "rejected"

HIRE_STATUSES = frozenset(
    {
        HIRE_STATUS_IN_PROGRESS,
        HIRE_STATUS_SUBMITTED,
        HIRE_STATUS_UNDER_REVIEW,
        HIRE_STATUS_HIRED,
        HIRE_STATUS_REJECTED,
    }
)

TERMINAL_HIRE_STATUSES = frozenset({HIRE_STATUS_HIRED, HIRE_STATUS_REJECTED})

HR_REVIEWABLE_STATUSES = frozenset({HIRE_STATUS_SUBMITTED, HIRE_STATUS_UNDER_REVIEW})


class HireReviewError(Exception):
    def __init__(self, message: str, status: int = 400):
        self.message = message
        self.status = status


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def applicant_wizard_mutable(hire_row: HrHireApplication | None) -> bool:
    if hire_row is None:
        return True
    return hire_row.hire_status not in TERMINAL_HIRE_STATUSES


def mark_submitted_for_review(hire_row: HrHireApplication, *, when: datetime | None = None) -> None:
    """Move application into HR queue when applicant submits or completes wizard."""
    now = when or utc_now()
    if hire_row.hire_status in TERMINAL_HIRE_STATUSES:
        return
    if hire_row.hire_status == HIRE_STATUS_IN_PROGRESS:
        hire_row.hire_status = HIRE_STATUS_SUBMITTED
    if hire_row.submitted_for_review_at is None:
        hire_row.submitted_for_review_at = now


def parse_application_payload(hire_row: HrHireApplication | None) -> dict[str, Any] | None:
    if hire_row is None or not hire_row.application_json:
        return None
    try:
        data = json.loads(hire_row.application_json)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        return None


def application_position(hire_row: HrHireApplication | None) -> str | None:
    payload = parse_application_payload(hire_row)
    if not payload:
        return None
    pos = payload.get("position_applying_for") or payload.get("position")
    if pos is None:
        return None
    s = str(pos).strip()
    return s or None


def wizard_progress_percent(hire_row: HrHireApplication | None) -> int:
    if hire_row is None:
        return 0
    steps = 0
    done = 0
    if hire_row.submitted_at is not None:
        done += 1
    steps += 1
    if hire_row.i9_signed_at is not None:
        done += 1
    steps += 1
    if hire_row.w4_signed_at is not None:
        done += 1
    steps += 1
    union_complete = bool(hire_row.union_document_files)
    if union_complete:
        done += 1
    steps += 1
    return int(round(100 * done / steps)) if steps else 0


def serialize_hire_status(hire_row: HrHireApplication | None) -> dict[str, Any]:
    if hire_row is None:
        return {
            "hire_status": HIRE_STATUS_IN_PROGRESS,
            "review_notes": None,
            "reviewed_at": None,
            "reviewed_by_user_id": None,
            "submitted_for_review_at": None,
            "progress_percent": 0,
            "wizard_locked": False,
        }
    return {
        "hire_status": hire_row.hire_status or HIRE_STATUS_IN_PROGRESS,
        "review_notes": hire_row.review_notes,
        "reviewed_at": hire_row.reviewed_at.isoformat() if hire_row.reviewed_at else None,
        "reviewed_by_user_id": str(hire_row.reviewed_by_user_id) if hire_row.reviewed_by_user_id else None,
        "submitted_for_review_at": (
            hire_row.submitted_for_review_at.isoformat() if hire_row.submitted_for_review_at else None
        ),
        "progress_percent": wizard_progress_percent(hire_row),
        "wizard_locked": hire_row.hire_status in TERMINAL_HIRE_STATUSES,
    }


def allowed_hr_status_transition(current: str, new: str) -> bool:
    if new not in HIRE_STATUSES or new == HIRE_STATUS_IN_PROGRESS:
        return False
    if new == HIRE_STATUS_UNDER_REVIEW:
        return current in HR_REVIEWABLE_STATUSES
    if new in TERMINAL_HIRE_STATUSES:
        return current in HR_REVIEWABLE_STATUSES
    return False


def purge_hire_application_files(hire_row: HrHireApplication) -> None:
    """Remove uploaded hire wizard files from object storage."""
    for row in hire_row.i9_document_files or ():
        delete_stored(UploadCategory.HR_I9, f"{row.id}{row.file_ext}")
    for row in hire_row.w4_document_files or ():
        delete_stored(UploadCategory.HR_W4, f"{row.id}{row.file_ext}")
    for row in hire_row.union_document_files or ():
        delete_stored(UploadCategory.HR_UNION, f"{row.id}{row.file_ext}")
