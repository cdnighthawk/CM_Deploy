"""Add ``buildingconnected_oauth_tokens`` for APS refresh/access storage.

Revision ID: 0012_bc_oauth
Revises: 0011_rfi_procore_expand
Create Date: 2026-05-12
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0012_bc_oauth"
down_revision: Union[str, Sequence[str], None] = "0011_rfi_procore_expand"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "buildingconnected_oauth_tokens",
        sa.Column("label", sa.String(length=64), nullable=False),
        sa.Column("refresh_token_encrypted", sa.Text(), nullable=False),
        sa.Column("access_token", sa.Text(), nullable=True),
        sa.Column("access_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("label"),
    )


def downgrade() -> None:
    op.drop_table("buildingconnected_oauth_tokens")
