"""Allow username-only logins (nullable email).

Revision ID: 0097_user_uname
Revises: 0096_rfp_award
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0097_user_uname"
down_revision: Union[str, Sequence[str], None] = "0096_rfp_award"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("username", sa.String(length=80), nullable=True))
    op.create_index("ix_users_username", "users", ["username"], unique=True)
    op.alter_column(
        "users",
        "email",
        existing_type=sa.String(length=255),
        nullable=True,
    )
    op.create_check_constraint(
        "ck_users_email_or_username",
        "users",
        "email IS NOT NULL OR username IS NOT NULL",
    )


def downgrade() -> None:
    op.drop_constraint("ck_users_email_or_username", "users", type_="check")
    op.alter_column(
        "users",
        "email",
        existing_type=sa.String(length=255),
        nullable=False,
    )
    op.drop_index("ix_users_username", table_name="users")
    op.drop_column("users", "username")
