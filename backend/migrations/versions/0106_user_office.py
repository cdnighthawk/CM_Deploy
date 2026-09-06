"""Assign each user to a company office for lead distance.

Revision ID: 0106_user_office
Revises: 0105_w1_tools
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0106_user_office"
down_revision: Union[str, Sequence[str], None] = "0105_w1_tools"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("office_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_index("ix_users_office_id", "users", ["office_id"])
    op.create_foreign_key(
        "fk_users_office_id_company_offices",
        "users",
        "company_offices",
        ["office_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_users_office_id_company_offices", "users", type_="foreignkey")
    op.drop_index("ix_users_office_id", table_name="users")
    op.drop_column("users", "office_id")
