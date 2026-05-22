"""Pytest fixtures for Flask app + HTTP client."""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("TAKEOFF_API_WRITES_ENABLED", "true")
os.environ.setdefault("FLASK_ENV", "development")
# Most tests call the API without a browser session; opt in to legacy dev-open mode.
os.environ.setdefault("USIS_API_DEV_ALLOW_ANY", "1")


@pytest.fixture
def flask_app():
    """Named ``flask_app`` (not ``app``) so a globally installed ``pytest-flask`` plugin
    does not try to wrap our factory and break collection."""
    from app import create_app

    return create_app()


@pytest.fixture
def client(flask_app):
    return flask_app.test_client()


@pytest.fixture
def hr_sample_employee(flask_app):
    """Non-demo user with HR rows for employee summary / dashboard tests."""
    from datetime import datetime, timezone

    from sqlalchemy import select

    from app.extensions import db
    from app.models import (
        HrEmployeePayScale,
        HrOnboardingItem,
        HrPolicyAcknowledgment,
        HrTrainingAssignment,
        SafetyTrainingRecord,
        User,
    )

    email = "hr.sample.employee@example.com"
    with flask_app.app_context():
        u = db.session.scalar(select(User).where(User.email == email))
        if u is None:
            u = User(
                email=email,
                first_name="Sample",
                last_name="Employee",
                is_active=True,
                is_superuser=False,
            )
            db.session.add(u)
            db.session.flush()
            now = datetime.now(tz=timezone.utc)
            db.session.add(
                HrOnboardingItem(
                    user_id=u.id,
                    title="Welcome packet",
                    sort_order=1,
                    completed_at=now,
                )
            )
            db.session.add(
                HrOnboardingItem(
                    user_id=u.id,
                    title="Payroll profile",
                    sort_order=2,
                )
            )
            db.session.add(
                HrPolicyAcknowledgment(
                    user_id=u.id,
                    policy_version="handbook-2025-01",
                )
            )
            db.session.add(
                HrTrainingAssignment(
                    user_id=u.id,
                    course_key="company-orientation-video",
                )
            )
            db.session.add(
                SafetyTrainingRecord(
                    user_id=u.id,
                    training_type="forklift",
                    credential_number="FL-TEST-001",
                    completed_at=now,
                )
            )
            db.session.add(
                HrEmployeePayScale(
                    user_id=u.id,
                    label="Field journeyman (standard)",
                    pay_basis="hourly",
                    hourly_rate="45.0000",
                    sort_order=1,
                )
            )
            db.session.commit()
        yield {"user_id": str(u.id), "email": email}


@pytest.fixture
def hr_wizard_user(flask_app):
    """User id for ``/hr/me/hire-wizard`` header-auth tests (not a demo seed user)."""
    from sqlalchemy import select

    from app.extensions import db
    from app.models import User

    email = "hr.wizard.employee@example.com"
    with flask_app.app_context():
        u = db.session.scalar(select(User).where(User.email == email))
        if u is None:
            u = User(
                email=email,
                first_name="Wizard",
                last_name="Tester",
                is_active=True,
                is_superuser=False,
            )
            db.session.add(u)
            db.session.commit()
        yield {"user_id": str(u.id), "email": email}


@pytest.fixture
def staff_user_for_hr_tests(flask_app):
    """Active staff user (non-applicant) for negative HR application tests."""
    from sqlalchemy import select

    from app.extensions import db
    from app.models import Role, User, UserRole

    email = "hr.staff.negative@example.com"
    with flask_app.app_context():
        u = db.session.scalar(select(User).where(User.email == email))
        if u is None:
            u = User(
                email=email,
                first_name="Staff",
                last_name="Negative",
                is_active=True,
                is_superuser=False,
            )
            db.session.add(u)
            db.session.flush()
            role = db.session.scalar(select(Role).where(Role.code == "read_only"))
            if role is not None:
                db.session.add(UserRole(user_id=u.id, role_id=role.id))
            db.session.commit()
        yield {"user_id": str(u.id), "email": email}
