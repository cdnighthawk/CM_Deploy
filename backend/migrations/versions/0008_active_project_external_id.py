"""Link every corecon_transactions row to the active-project / lead_estimate key.

Adds ``active_project_external_id`` (matches ``lead_estimates.external_id`` for
CORECON-sourced rows from ``active project.csv``) and back-fills it from
``project_corecon_id`` / ``project_number``.

Revision ID: 0008_active_project_external_id
Revises: 0007_link_jobs
Create Date: 2026-05-11
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0008_active_project_external_id"
down_revision: Union[str, Sequence[str], None] = "0007_link_jobs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "corecon_transactions",
        sa.Column("active_project_external_id", sa.String(64), nullable=True),
    )
    op.create_index(
        "ix_corecon_transactions_active_project_external_id",
        "corecon_transactions",
        ["active_project_external_id"],
    )

    op.execute(
        sa.text(
            """
            UPDATE corecon_transactions
               SET active_project_external_id = CASE
                     WHEN project_corecon_id IS NOT NULL
                         THEN 'corecon-project-' || project_corecon_id::text
                     WHEN project_number IS NOT NULL AND trim(project_number) <> ''
                         THEN 'corecon-project-noid-' || trim(project_number)
                     ELSE NULL
                   END
             WHERE active_project_external_id IS NULL;
            """
        )
    )


def downgrade() -> None:
    op.drop_index(
        "ix_corecon_transactions_active_project_external_id",
        table_name="corecon_transactions",
    )
    op.drop_column("corecon_transactions", "active_project_external_id")
