"""Policy acknowledgment scope: active employees only."""
from __future__ import annotations

import uuid

import pytest

from app.extensions import db
from app.models import HrPolicyAcknowledgment, User
from app.permissions.applicant import assign_applicant_role, is_applicant_only_user
from app.services.hr_policy import HIRE_WIZARD_POLICY_VERSIONS


def test_applicant_only_user_id_subquery(flask_app):
    from app.permissions.applicant import applicant_only_user_id_subquery

    with flask_app.app_context():
        email = f"applicant.subq.{uuid.uuid4().hex[:8]}@usis.local"
        u = User(email=email, first_name="Sub", last_name="Query", is_active=True)
        db.session.add(u)
        db.session.flush()
        assign_applicant_role(u)
        db.session.commit()
        uid = u.id

        ids = set(db.session.scalars(applicant_only_user_id_subquery()).all())
        assert uid in ids
        assert is_applicant_only_user(db.session.get(User, uid)) is True

        db.session.delete(u)
        db.session.commit()


def test_hire_wizard_policy_versions_are_not_employee_policies():
    assert "handbook-2025-01" not in HIRE_WIZARD_POLICY_VERSIONS
