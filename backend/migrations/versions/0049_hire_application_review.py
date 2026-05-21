"""HR review workflow fields on hire applications."""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0049_hire_application_review"
down_revision: Union[str, Sequence[str], None] = "0048_password_reset_tokens"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "hr_hire_applications",
        sa.Column(
            "hire_status",
            sa.String(length=32),
            nullable=False,
            server_default="in_progress",
        ),
    )
    op.add_column("hr_hire_applications", sa.Column("review_notes", sa.Text(), nullable=True))
    op.add_column(
        "hr_hire_applications",
        sa.Column("reviewed_by_user_id", sa.UUID(), nullable=True),
    )
    op.add_column(
        "hr_hire_applications",
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "hr_hire_applications",
        sa.Column("submitted_for_review_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_hr_hire_applications_reviewed_by_user_id",
        "hr_hire_applications",
        "users",
        ["reviewed_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_hr_hire_applications_hire_status",
        "hr_hire_applications",
        ["hire_status"],
        unique=False,
    )
    op.execute(
        sa.text(
            """
            UPDATE hr_hire_applications
            SET hire_status = 'submitted',
                submitted_for_review_at = COALESCE(submitted_at, updated_at, created_at)
            WHERE submitted_at IS NOT NULL AND hire_status = 'in_progress'
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE hr_hire_applications
            SET hire_status = 'submitted',
                submitted_for_review_at = COALESCE(w4_signed_at, submitted_at, updated_at, created_at)
            WHERE w4_signed_at IS NOT NULL AND hire_status = 'in_progress'
            """
        )
    )


def downgrade() -> None:
    op.drop_index("ix_hr_hire_applications_hire_status", table_name="hr_hire_applications")
    op.drop_constraint(
        "fk_hr_hire_applications_reviewed_by_user_id",
        "hr_hire_applications",
        type_="foreignkey",
    )
    op.drop_column("hr_hire_applications", "submitted_for_review_at")
    op.drop_column("hr_hire_applications", "reviewed_at")
    op.drop_column("hr_hire_applications", "reviewed_by_user_id")
    op.drop_column("hr_hire_applications", "review_notes")
    op.drop_column("hr_hire_applications", "hire_status")
