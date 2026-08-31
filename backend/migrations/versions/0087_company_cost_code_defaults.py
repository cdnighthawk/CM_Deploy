"""Add server defaults on company_cost_codes pk/timestamps.

Revision ID: 0087_co_jcc_def
Revises: 0086_co_jcc
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0087_co_jcc_def"
down_revision: Union[str, Sequence[str], None] = "0086_co_jcc"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "company_cost_codes",
        "id",
        server_default=sa.text("gen_random_uuid()"),
        existing_type=postgresql.UUID(as_uuid=True),
    )
    op.alter_column(
        "company_cost_codes",
        "created_at",
        server_default=sa.text("now()"),
        existing_type=sa.DateTime(timezone=True),
    )
    op.alter_column(
        "company_cost_codes",
        "updated_at",
        server_default=sa.text("now()"),
        existing_type=sa.DateTime(timezone=True),
    )


def downgrade() -> None:
    op.alter_column("company_cost_codes", "id", server_default=None, existing_type=postgresql.UUID(as_uuid=True))
    op.alter_column("company_cost_codes", "created_at", server_default=None, existing_type=sa.DateTime(timezone=True))
    op.alter_column("company_cost_codes", "updated_at", server_default=None, existing_type=sa.DateTime(timezone=True))
