"""Hire wizard path selection (union dispatch vs standard job-offer flow)."""

from __future__ import annotations

from ..models import HrHireApplication

HIRE_PATH_UNION_DISPATCH = "union_dispatch"
HIRE_PATH_STANDARD = "standard"
HIRE_PATHS = frozenset({HIRE_PATH_UNION_DISPATCH, HIRE_PATH_STANDARD})


def normalize_hire_path(raw: str | None) -> str | None:
    s = (raw or "").strip().lower()
    return s if s in HIRE_PATHS else None


def applicant_may_complete_i9_w4(hire_row: HrHireApplication | None) -> bool:
    if hire_row is None or not hire_row.hire_path:
        return False
    if hire_row.hire_path == HIRE_PATH_UNION_DISPATCH:
        return hire_row.submitted_at is not None
    if hire_row.hire_path == HIRE_PATH_STANDARD:
        return hire_row.offer_accepted_at is not None
    return False


def applicant_may_upload_union(hire_row: HrHireApplication | None) -> bool:
    if hire_row is None or hire_row.hire_path != HIRE_PATH_UNION_DISPATCH:
        return False
    return hire_row.w4_signed_at is not None


def is_standard_path(hire_row: HrHireApplication | None) -> bool:
    return hire_row is not None and hire_row.hire_path == HIRE_PATH_STANDARD


def is_union_dispatch_path(hire_row: HrHireApplication | None) -> bool:
    return hire_row is not None and hire_row.hire_path == HIRE_PATH_UNION_DISPATCH
