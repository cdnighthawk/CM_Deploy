"""Persist the stored object name for spec-section PDFs.

Revision ID: 0126_spec_storage
Revises: 0125_ingest_evt
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0126_spec_storage"
down_revision: Union[str, Sequence[str], None] = "0125_ingest_evt"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    cols = {c["name"] for c in sa.inspect(bind).get_columns("rfi_spec_sections")}
    if "storage_object" not in cols:
        op.add_column(
            "rfi_spec_sections",
            sa.Column("storage_object", sa.String(length=500), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    cols = {c["name"] for c in sa.inspect(bind).get_columns("rfi_spec_sections")}
    if "storage_object" in cols:
        op.drop_column("rfi_spec_sections", "storage_object")
