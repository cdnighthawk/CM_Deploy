"""Lead estimate approval and takeoff lock timestamps.

Revision ID: 0034_lead_estimate_approval_lock
Revises: 0033_material_csi_hd_rename
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0034_lead_estimate_approval_lock"
down_revision: Union[str, Sequence[str], None] = "0033_material_csi_hd_rename"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "lead_estimates",
        sa.Column("estimate_locked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "lead_estimates",
        sa.Column("estimate_approved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "lead_estimates",
        sa.Column(
            "estimate_approved_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_lead_estimates_estimate_locked_at",
        "lead_estimates",
        ["estimate_locked_at"],
    )
    op.create_index(
        "ix_lead_estimates_estimate_approved_at",
        "lead_estimates",
        ["estimate_approved_at"],
    )
    op.create_index(
        "ix_lead_estimates_estimate_approved_by_user_id",
        "lead_estimates",
        ["estimate_approved_by_user_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_lead_estimates_estimate_approved_by_user_id", table_name="lead_estimates")
    op.drop_index("ix_lead_estimates_estimate_approved_at", table_name="lead_estimates")
    op.drop_index("ix_lead_estimates_estimate_locked_at", table_name="lead_estimates")
    op.drop_column("lead_estimates", "estimate_approved_by_user_id")
    op.drop_column("lead_estimates", "estimate_approved_at")
    op.drop_column("lead_estimates", "estimate_locked_at")
