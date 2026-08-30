"""CPU drawing hygiene: label_status + sheet_function.

Revision ID: 0080_dwg_hyg
Revises: 0079_est_scripts
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0080_dwg_hyg"
down_revision: Union[str, Sequence[str], None] = "0079_est_scripts"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("drawings", sa.Column("label_status", sa.String(20), nullable=True))
    op.add_column("drawings", sa.Column("sheet_function", sa.String(40), nullable=True))
    op.add_column("drawings", sa.Column("hygiene", postgresql.JSONB(), nullable=True))
    op.create_index("ix_drawings_sheet_function", "drawings", ["sheet_function"])


def downgrade() -> None:
    op.drop_index("ix_drawings_sheet_function", table_name="drawings")
    op.drop_column("drawings", "hygiene")
    op.drop_column("drawings", "sheet_function")
    op.drop_column("drawings", "label_status")
