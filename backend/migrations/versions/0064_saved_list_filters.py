"""Personal saved list-query presets for the Leads filter drawer.

Revision ID: 0064_saved_list_filters
Revises: 0063_submittal_qc
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0064_saved_list_filters"
down_revision: Union[str, Sequence[str], None] = "0063_submittal_qc"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "saved_list_filters",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("table_key", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("query_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "table_key", "name", name="uq_saved_list_filters_user_table_name"),
    )
    op.create_index("ix_saved_list_filters_user_id", "saved_list_filters", ["user_id"], unique=False)
    op.create_index("ix_saved_list_filters_table_key", "saved_list_filters", ["table_key"], unique=False)
    op.create_index(
        "uq_saved_list_filters_one_default",
        "saved_list_filters",
        ["user_id", "table_key"],
        unique=True,
        postgresql_where=sa.text("is_default IS TRUE"),
    )


def downgrade() -> None:
    op.drop_index("uq_saved_list_filters_one_default", table_name="saved_list_filters")
    op.drop_index("ix_saved_list_filters_table_key", table_name="saved_list_filters")
    op.drop_index("ix_saved_list_filters_user_id", table_name="saved_list_filters")
    op.drop_table("saved_list_filters")
