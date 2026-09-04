"""Procore-parity fields on punchlist items.

Revision ID: 0101_punch_procore
Revises: 0099_timekeep
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0101_punch_procore"
down_revision: Union[str, Sequence[str], None] = "0099_timekeep"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("punchlist_items", sa.Column("description", sa.Text(), nullable=True))
    op.add_column("punchlist_items", sa.Column("punch_type", sa.String(length=80), nullable=True))
    op.add_column("punchlist_items", sa.Column("priority", sa.String(length=40), nullable=True))
    op.add_column("punchlist_items", sa.Column("trade", sa.String(length=120), nullable=True))
    op.add_column("punchlist_items", sa.Column("reference", sa.String(length=500), nullable=True))
    op.add_column("punchlist_items", sa.Column("schedule_impact", sa.String(length=40), nullable=True))
    op.add_column("punchlist_items", sa.Column("cost_impact", sa.String(length=40), nullable=True))
    op.add_column(
        "punchlist_items",
        sa.Column(
            "manager_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "punchlist_items",
        sa.Column(
            "final_approver_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "punchlist_items",
        sa.Column("distribution_user_ids", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
    )
    op.add_column(
        "punchlist_items",
        sa.Column("attachments", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
    )


def downgrade() -> None:
    op.drop_column("punchlist_items", "attachments")
    op.drop_column("punchlist_items", "distribution_user_ids")
    op.drop_column("punchlist_items", "final_approver_user_id")
    op.drop_column("punchlist_items", "manager_user_id")
    op.drop_column("punchlist_items", "cost_impact")
    op.drop_column("punchlist_items", "schedule_impact")
    op.drop_column("punchlist_items", "reference")
    op.drop_column("punchlist_items", "trade")
    op.drop_column("punchlist_items", "priority")
    op.drop_column("punchlist_items", "punch_type")
    op.drop_column("punchlist_items", "description")
