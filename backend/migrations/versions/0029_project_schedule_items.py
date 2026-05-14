"""Project installation / work window lines (construction schedule).

Revision ID: 0029_project_schedule_items
Revises: 0028_spec_section_pdf_url
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0029_project_schedule_items"
down_revision: Union[str, Sequence[str], None] = "0028_spec_section_pdf_url"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "project_schedule_items",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("crew_label", sa.String(length=200), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "ix_project_schedule_items_project_id",
        "project_schedule_items",
        ["project_id"],
    )
    op.create_index(
        "ix_project_schedule_items_start_date",
        "project_schedule_items",
        ["start_date"],
    )
    op.create_index(
        "ix_project_schedule_items_end_date",
        "project_schedule_items",
        ["end_date"],
    )


def downgrade() -> None:
    op.drop_index("ix_project_schedule_items_end_date", table_name="project_schedule_items")
    op.drop_index("ix_project_schedule_items_start_date", table_name="project_schedule_items")
    op.drop_index("ix_project_schedule_items_project_id", table_name="project_schedule_items")
    op.drop_table("project_schedule_items")
