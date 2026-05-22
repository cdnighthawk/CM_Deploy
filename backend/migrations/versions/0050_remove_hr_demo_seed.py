"""Remove Plan 19 HR demo seed users and their cascaded HR/safety rows."""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

revision: str = "0050_remove_hr_demo_seed"
down_revision: Union[str, Sequence[str], None] = "0049_hire_application_review"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        text(
            """
            DELETE FROM users
            WHERE email IN ('hr.demo.employee@usis.local', 'charles.dossett@usis.local')
               OR id IN (
                 'a1700000-0000-4000-8000-000000000001'::uuid,
                 'b1700000-0000-4000-8000-000000000001'::uuid
               )
            """
        )
    )


def downgrade() -> None:
    # Demo seed was for development only; do not re-insert on downgrade.
    pass
