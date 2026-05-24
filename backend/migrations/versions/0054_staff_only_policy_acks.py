"""Remove hire-wizard policy rows; policy acknowledgments are for active employees only."""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

revision: str = "0054_staff_only_policy_acks"
down_revision: Union[str, Sequence[str], None] = "0053_hrms_expense_tracker"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_HIRE_WIZARD_POLICY_VERSIONS = (
    "hire-federal-i9-attestation-v1",
    "hire-federal-w4-attestation-v1",
)


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        text(
            """
            DELETE FROM hr_policy_acknowledgments
            WHERE policy_version = ANY(:versions)
            """
        ),
        {"versions": list(_HIRE_WIZARD_POLICY_VERSIONS)},
    )
    conn.execute(
        text(
            """
            DELETE FROM hr_policy_acknowledgments p
            USING users u
            WHERE p.user_id = u.id
              AND u.is_superuser IS NOT TRUE
              AND EXISTS (
                SELECT 1
                FROM user_roles ur
                JOIN roles r ON r.id = ur.role_id
                WHERE ur.user_id = u.id AND r.code = 'applicant'
              )
              AND NOT EXISTS (
                SELECT 1
                FROM user_roles ur2
                JOIN roles r2 ON r2.id = ur2.role_id
                WHERE ur2.user_id = u.id AND r2.code <> 'applicant'
              )
            """
        )
    )


def downgrade() -> None:
    # Applicant/wizard policy rows were incorrect data; do not recreate on downgrade.
    pass
