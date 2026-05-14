"""Add ``drawing_series_id`` to group drawing revisions (Procore-style sheet).

Revision ID: 0013_drawing_series
Revises: 0012_bc_oauth
Create Date: 2026-05-12
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0013_drawing_series"
down_revision: Union[str, Sequence[str], None] = "0012_bc_oauth"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "drawings",
        sa.Column("drawing_series_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.execute(sa.text("UPDATE drawings SET drawing_series_id = id WHERE drawing_series_id IS NULL"))
    op.alter_column("drawings", "drawing_series_id", nullable=False)
    op.create_index("ix_drawings_drawing_series_id", "drawings", ["drawing_series_id"])


def downgrade() -> None:
    op.drop_index("ix_drawings_drawing_series_id", table_name="drawings")
    op.drop_column("drawings", "drawing_series_id")
