"""Multiple owner contracts per project.

Revision ID: 0065_project_contracts
Revises: 0064_saved_list_filters
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0065_project_contracts"
down_revision: Union[str, Sequence[str], None] = "0064_saved_list_filters"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if "project_contracts" not in insp.get_table_names():
        op.create_table(
            "project_contracts",
            sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("contract_number", sa.String(length=80), nullable=True),
            sa.Column("title", sa.String(length=300), nullable=False, server_default="Prime contract"),
            sa.Column("contract_value", sa.Numeric(15, 2), nullable=True),
            sa.Column("contract_date", sa.Date(), nullable=True),
            sa.Column("start_date", sa.Date(), nullable=True),
            sa.Column("substantial_completion_date", sa.Date(), nullable=True),
            sa.Column("closeout_date", sa.Date(), nullable=True),
            sa.Column("retention_percentage", sa.Numeric(5, 2), nullable=True),
            sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_project_contracts_project_id", "project_contracts", ["project_id"], unique=False)
        op.create_index(
            "uq_project_contracts_one_primary",
            "project_contracts",
            ["project_id"],
            unique=True,
            postgresql_where=sa.text("is_primary IS TRUE"),
        )
    op.execute(
        """
        INSERT INTO project_contracts (
            project_id, contract_number, title, contract_value, contract_date,
            start_date, substantial_completion_date, closeout_date, retention_percentage,
            is_primary, sort_order
        )
        SELECT
            id,
            number,
            'Prime contract',
            contract_value,
            contract_date,
            start_date,
            substantial_completion_date,
            closeout_date,
            retention_percentage,
            TRUE,
            0
        FROM projects
        WHERE deleted_at IS NULL
          AND (
            contract_value IS NOT NULL
            OR contract_date IS NOT NULL
            OR start_date IS NOT NULL
            OR substantial_completion_date IS NOT NULL
            OR closeout_date IS NOT NULL
            OR retention_percentage IS NOT NULL
          )
          AND NOT EXISTS (
            SELECT 1 FROM project_contracts c
            WHERE c.project_id = projects.id AND c.is_primary IS TRUE
          )
        """
    )


def downgrade() -> None:
    op.drop_index("uq_project_contracts_one_primary", table_name="project_contracts")
    op.drop_index("ix_project_contracts_project_id", table_name="project_contracts")
    op.drop_table("project_contracts")
