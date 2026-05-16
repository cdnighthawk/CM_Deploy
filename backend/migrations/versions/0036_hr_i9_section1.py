"""I-9 Section 1 encrypted storage and e-sign columns on hr_hire_applications.

Revision ID: 0036_hr_i9_section1
Revises: 0035_hr_hire_application
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0036_hr_i9_section1"
down_revision: Union[str, Sequence[str], None] = "0035_hr_hire_application"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("hr_hire_applications", sa.Column("i9_section1_json_encrypted", sa.Text(), nullable=True))
    op.add_column(
        "hr_hire_applications",
        sa.Column("i9_section1_completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column("hr_hire_applications", sa.Column("i9_signature_png", sa.Text(), nullable=True))
    op.add_column("hr_hire_applications", sa.Column("i9_signed_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("hr_hire_applications", "i9_signed_at")
    op.drop_column("hr_hire_applications", "i9_signature_png")
    op.drop_column("hr_hire_applications", "i9_section1_completed_at")
    op.drop_column("hr_hire_applications", "i9_section1_json_encrypted")
