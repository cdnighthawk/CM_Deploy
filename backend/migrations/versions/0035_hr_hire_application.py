"""HR hire wizard intake table (application JSON per user).

Revision ID: 0035_hr_hire_application
Revises: 0034_lead_estimate_approval_lock
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0035_hr_hire_application"
down_revision: Union[str, Sequence[str], None] = "0034_lead_estimate_approval_lock"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "hr_hire_applications",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("application_json", sa.Text(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_hr_hire_applications_user_id", "hr_hire_applications", ["user_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_hr_hire_applications_user_id", table_name="hr_hire_applications")
    op.drop_table("hr_hire_applications")
