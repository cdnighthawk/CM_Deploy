"""Mobile refresh tokens for Expo clients.

Revision ID: 0040_mobile_refresh_tokens
Revises: 0039_hr_union_document_files
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0040_mobile_refresh_tokens"
down_revision: Union[str, Sequence[str], None] = "0039_hr_union_document_files"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "mobile_refresh_tokens",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("token_hash", sa.String(length=255), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("device_label", sa.String(length=120), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_mobile_refresh_tokens_user_id",
        "mobile_refresh_tokens",
        ["user_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_mobile_refresh_tokens_user_id", table_name="mobile_refresh_tokens")
    op.drop_table("mobile_refresh_tokens")
