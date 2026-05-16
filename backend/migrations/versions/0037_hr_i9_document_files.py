"""I-9 supporting document photo files linked to hire applications.

Revision ID: 0037_hr_i9_document_files
Revises: 0036_hr_i9_section1
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0037_hr_i9_document_files"
down_revision: Union[str, Sequence[str], None] = "0036_hr_i9_section1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "hr_hire_i9_document_files",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("hire_application_id", sa.UUID(), nullable=False),
        sa.Column("slot", sa.String(length=16), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("original_filename", sa.String(length=500), nullable=False),
        sa.Column("mime_type", sa.String(length=120), nullable=True),
        sa.Column("file_ext", sa.String(length=16), nullable=False),
        sa.Column("file_size_bytes", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["hire_application_id"], ["hr_hire_applications.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_hr_hire_i9_document_files_hire_application_id",
        "hr_hire_i9_document_files",
        ["hire_application_id"],
    )
    op.create_index(
        "ix_hr_hire_i9_document_files_slot",
        "hr_hire_i9_document_files",
        ["hire_application_id", "slot"],
    )


def downgrade() -> None:
    op.drop_index("ix_hr_hire_i9_document_files_slot", table_name="hr_hire_i9_document_files")
    op.drop_index("ix_hr_hire_i9_document_files_hire_application_id", table_name="hr_hire_i9_document_files")
    op.drop_table("hr_hire_i9_document_files")
