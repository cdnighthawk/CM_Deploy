"""Unit tests for hired employee HR provisioning."""
from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

from app.services.hr_hired_employee import provision_hired_employee_hr_records


def test_provision_hired_employee_creates_missing_rows():
    uid = uuid.uuid4()
    scalars = iter([None, None, None, None, None, None])

    def fake_scalar(_stmt):
        return next(scalars, None)

    session = MagicMock()
    session.scalar.side_effect = fake_scalar
    added: list = []
    session.add.side_effect = added.append

    with patch("app.services.hr_hired_employee.db.session", session):
        provision_hired_employee_hr_records(uid)

    assert len(added) == 5
