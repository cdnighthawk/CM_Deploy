"""Prime contract schedule-of-values lines (project-scoped master SOV).

Revision ID: 0027_prime_contract_sov
Revises: 0026_pay_applications
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0027_prime_contract_sov"
down_revision: Union[str, Sequence[str], None] = "0026_pay_applications"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "prime_contract_sov_lines",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("parent_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("phase_code", sa.String(length=40), nullable=True),
        sa.Column("description", sa.String(length=500), nullable=False, server_default=""),
        sa.Column("scheduled_value", sa.Numeric(15, 2), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parent_id"], ["prime_contract_sov_lines.id"], ondelete="SET NULL"),
    )
    op.create_index(
        "ix_prime_contract_sov_lines_project_id",
        "prime_contract_sov_lines",
        ["project_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_prime_contract_sov_lines_project_id", table_name="prime_contract_sov_lines")
    op.drop_table("prime_contract_sov_lines")
