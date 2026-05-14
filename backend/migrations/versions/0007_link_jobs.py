"""Add shared job UID (project_id FK) to lead_estimates and corecon_transactions.

Both tables get a nullable ``project_id UUID`` pointing at ``projects.id``.
Population is intentionally deferred to ``scripts/link_jobs.py`` so the
schema change is fully reversible without losing data.

Revision ID: 0007_link_jobs
Revises: 0006_corecon_transactions
Create Date: 2026-05-11
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007_link_jobs"
down_revision: Union[str, Sequence[str], None] = "0006_corecon_transactions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "lead_estimates",
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_lead_estimates_project_id_projects",
        source_table="lead_estimates",
        referent_table="projects",
        local_cols=["project_id"],
        remote_cols=["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_lead_estimates_project_id",
        "lead_estimates",
        ["project_id"],
    )

    op.add_column(
        "corecon_transactions",
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_corecon_transactions_project_id_projects",
        source_table="corecon_transactions",
        referent_table="projects",
        local_cols=["project_id"],
        remote_cols=["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_corecon_transactions_project_id",
        "corecon_transactions",
        ["project_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_corecon_transactions_project_id", table_name="corecon_transactions")
    op.drop_constraint(
        "fk_corecon_transactions_project_id_projects",
        "corecon_transactions",
        type_="foreignkey",
    )
    op.drop_column("corecon_transactions", "project_id")

    op.drop_index("ix_lead_estimates_project_id", table_name="lead_estimates")
    op.drop_constraint(
        "fk_lead_estimates_project_id_projects",
        "lead_estimates",
        type_="foreignkey",
    )
    op.drop_column("lead_estimates", "project_id")
