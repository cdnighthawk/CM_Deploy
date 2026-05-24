"""Provision standard HR records when a hire wizard applicant becomes staff."""
from __future__ import annotations

import uuid
from datetime import timedelta

from sqlalchemy import select

from ..extensions import db
from ..models import HrOnboardingItem, HrPolicyAcknowledgment, HrTrainingAssignment
from .hire_application_review import utc_now

_STAFF_ONBOARDING: tuple[tuple[str, int], ...] = (
    ("Complete profile & emergency contacts", 10),
    ("Acknowledge employee handbook", 20),
    ("Complete payroll profile", 30),
)
_DEFAULT_POLICY_VERSION = "handbook-2025-01"
_DEFAULT_TRAINING_COURSE = "harassment-prevention-101"


def provision_hired_employee_hr_records(user_id: uuid.UUID) -> None:
    """Create baseline onboarding / policy / training rows so hired staff appear in HR."""
    for title, sort_order in _STAFF_ONBOARDING:
        exists = db.session.scalar(
            select(HrOnboardingItem.id).where(
                HrOnboardingItem.user_id == user_id,
                HrOnboardingItem.title == title,
            )
        )
        if exists is None:
            db.session.add(
                HrOnboardingItem(
                    user_id=user_id,
                    title=title,
                    sort_order=sort_order,
                )
            )

    policy_exists = db.session.scalar(
        select(HrPolicyAcknowledgment.id).where(
            HrPolicyAcknowledgment.user_id == user_id,
            HrPolicyAcknowledgment.policy_version == _DEFAULT_POLICY_VERSION,
        )
    )
    if policy_exists is None:
        db.session.add(
            HrPolicyAcknowledgment(
                user_id=user_id,
                policy_version=_DEFAULT_POLICY_VERSION,
            )
        )

    training_exists = db.session.scalar(
        select(HrTrainingAssignment.id).where(
            HrTrainingAssignment.user_id == user_id,
            HrTrainingAssignment.course_key == _DEFAULT_TRAINING_COURSE,
        )
    )
    if training_exists is None:
        db.session.add(
            HrTrainingAssignment(
                user_id=user_id,
                course_key=_DEFAULT_TRAINING_COURSE,
                due_at=utc_now() + timedelta(days=14),
            )
        )
