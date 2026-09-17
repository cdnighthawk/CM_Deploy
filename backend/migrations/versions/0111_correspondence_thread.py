"""Add thread_id so filed mail can stay grouped by conversation.

Revision ID: 0111_corr_thread
Revises: 0110_mat_csi
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0111_corr_thread"
down_revision: Union[str, Sequence[str], None] = "0110_mat_csi"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "correspondence_items",
        sa.Column("thread_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index("ix_correspondence_items_thread_id", "correspondence_items", ["thread_id"])


def downgrade() -> None:
    op.drop_index("ix_correspondence_items_thread_id", table_name="correspondence_items")
    op.drop_column("correspondence_items", "thread_id")
