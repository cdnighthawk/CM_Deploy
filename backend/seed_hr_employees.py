"""Idempotent HR demo seed: Charles Dossett + Jamie Rivera + hr_* rows.

Run from the backend directory (venv active):

    python seed_hr_employees.py

Requires migrations through 0021 (hr_* tables). Safe to re-run.
"""
from __future__ import annotations

import os
import sys
import uuid
from datetime import datetime, timezone

# Make ``app`` importable when run as a script
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import select

from app import create_app
from app.extensions import db
from app.models import (
    HrOnboardingItem,
    HrPolicyAcknowledgment,
    HrTrainingAssignment,
    User,
)

CHARLES_ID = uuid.UUID("b1700000-0000-4000-8000-000000000001")
CHARLES_EMAIL = "charles.dossett@usis.local"
JAMIE_ID = uuid.UUID("a1700000-0000-4000-8000-000000000001")
JAMIE_EMAIL = "hr.demo.employee@usis.local"


def _upsert_user(uid: uuid.UUID, email: str, first: str, last: str) -> User:
    u = db.session.get(User, uid)
    if u is None:
        u = db.session.scalar(select(User).where(User.email == email))
    if u is None:
        u = User(id=uid, email=email, first_name=first, last_name=last, is_active=True, is_superuser=False)
        db.session.add(u)
    else:
        u.first_name = first
        u.last_name = last
        u.is_active = True
    db.session.flush()
    return u


def _ensure_onboarding(u: User, title: str, sort_order: int, completed: bool) -> None:
    q = select(HrOnboardingItem).where(HrOnboardingItem.user_id == u.id, HrOnboardingItem.title == title)
    row = db.session.scalars(q).first()
    if row is not None:
        return
    db.session.add(
        HrOnboardingItem(
            user_id=u.id,
            title=title,
            sort_order=sort_order,
            completed_at=datetime.now(tz=timezone.utc) if completed else None,
        )
    )


def _ensure_policy(u: User, version: str, signed: bool) -> None:
    q = select(HrPolicyAcknowledgment).where(
        HrPolicyAcknowledgment.user_id == u.id, HrPolicyAcknowledgment.policy_version == version
    )
    row = db.session.scalars(q).first()
    if row is not None:
        return
    db.session.add(
        HrPolicyAcknowledgment(
            user_id=u.id,
            policy_version=version,
            signed_at=datetime.now(tz=timezone.utc) if signed else None,
        )
    )


def _ensure_training(u: User, course_key: str, complete: bool) -> None:
    q = select(HrTrainingAssignment).where(
        HrTrainingAssignment.user_id == u.id, HrTrainingAssignment.course_key == course_key
    )
    row = db.session.scalars(q).first()
    if row is not None:
        return
    db.session.add(
        HrTrainingAssignment(
            user_id=u.id,
            course_key=course_key,
            due_at=None,
            completed_at=datetime.now(tz=timezone.utc) if complete else None,
        )
    )


def main() -> None:
    app = create_app()
    with app.app_context():
        charles = _upsert_user(CHARLES_ID, CHARLES_EMAIL, "Charles", "Dossett")
        _ensure_onboarding(charles, "Complete profile & emergency contacts", 1, False)
        _ensure_onboarding(charles, "Acknowledge employee handbook", 2, False)
        _ensure_policy(charles, "handbook-2025-01", False)
        _ensure_training(charles, "company-orientation-video", False)

        jamie = _upsert_user(JAMIE_ID, JAMIE_EMAIL, "Jamie", "Rivera")
        _ensure_onboarding(jamie, "Send welcome packet", 1, True)
        _ensure_onboarding(jamie, "Complete payroll profile", 2, False)
        _ensure_policy(jamie, "handbook-2025-01", False)
        _ensure_training(jamie, "harassment-prevention-101", False)

        db.session.commit()
        print("OK: HR demo rows ensured for", CHARLES_EMAIL, "and", JAMIE_EMAIL)


if __name__ == "__main__":
    main()
