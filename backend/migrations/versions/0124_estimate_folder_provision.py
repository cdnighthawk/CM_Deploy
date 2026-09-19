"""estimates: folder provision status and path.

Revision ID: 0124_est_folder
Revises: 0123_openings
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0124_est_folder"
down_revision: Union[str, Sequence[str], None] = "0123_openings"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    cols = {c["name"] for c in sa.inspect(bind).get_columns("estimates")}
    if "folder_provision_status" not in cols:
        op.add_column("estimates", sa.Column("folder_provision_status", sa.String(length=32), nullable=True))
        op.create_index(
            "ix_estimates_folder_provision_status",
            "estimates",
            ["folder_provision_status"],
            unique=False,
        )
    if "folder_path" not in cols:
        op.add_column("estimates", sa.Column("folder_path", sa.Text(), nullable=True))
    if "folder_provisioned_at" not in cols:
        op.add_column("estimates", sa.Column("folder_provisioned_at", sa.DateTime(timezone=True), nullable=True))
    if "folder_provision_error" not in cols:
        op.add_column("estimates", sa.Column("folder_provision_error", sa.Text(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    cols = {c["name"] for c in sa.inspect(bind).get_columns("estimates")}
    indexes = {ix["name"] for ix in sa.inspect(bind).get_indexes("estimates")}
    if "ix_estimates_folder_provision_status" in indexes:
        op.drop_index("ix_estimates_folder_provision_status", table_name="estimates")
    if "folder_provision_error" in cols:
        op.drop_column("estimates", "folder_provision_error")
    if "folder_provisioned_at" in cols:
        op.drop_column("estimates", "folder_provisioned_at")
    if "folder_path" in cols:
        op.drop_column("estimates", "folder_path")
    if "folder_provision_status" in cols:
        op.drop_column("estimates", "folder_provision_status")
