"""PO order-by tracking: lead time, schedule link, supplier confirm, receipt replay.

Revision ID: 0088_order_trk
Revises: 0087_co_jcc_def
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0088_order_trk"
down_revision: Union[str, Sequence[str], None] = "0087_co_jcc_def"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("commitments", sa.Column("lead_time_days", sa.Integer(), nullable=True))
    op.add_column("commitments", sa.Column("schedule_item_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("commitments", sa.Column("order_by_date", sa.Date(), nullable=True))
    op.add_column(
        "commitments",
        sa.Column("supplier_confirm_status", sa.String(length=20), nullable=False, server_default="none"),
    )
    op.add_column("commitments", sa.Column("supplier_confirm_sent_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("commitments", sa.Column("supplier_confirm_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("commitments", sa.Column("last_notified_order_by_date", sa.Date(), nullable=True))
    op.create_index("ix_commitments_schedule_item_id", "commitments", ["schedule_item_id"])
    op.create_index("ix_commitments_order_by_date", "commitments", ["order_by_date"])
    op.create_foreign_key(
        "fk_commitments_schedule_item_id",
        "commitments",
        "project_schedule_items",
        ["schedule_item_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.add_column("purchase_order_receipts", sa.Column("client_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("purchase_order_receipts", sa.Column("condition", sa.String(length=40), nullable=True))
    op.add_column("purchase_order_receipts", sa.Column("photo_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.create_unique_constraint("uq_purchase_order_receipts_client_id", "purchase_order_receipts", ["client_id"])


def downgrade() -> None:
    op.drop_constraint("uq_purchase_order_receipts_client_id", "purchase_order_receipts", type_="unique")
    op.drop_column("purchase_order_receipts", "photo_ids")
    op.drop_column("purchase_order_receipts", "condition")
    op.drop_column("purchase_order_receipts", "client_id")

    op.drop_constraint("fk_commitments_schedule_item_id", "commitments", type_="foreignkey")
    op.drop_index("ix_commitments_order_by_date", table_name="commitments")
    op.drop_index("ix_commitments_schedule_item_id", table_name="commitments")
    op.drop_column("commitments", "last_notified_order_by_date")
    op.drop_column("commitments", "supplier_confirm_at")
    op.drop_column("commitments", "supplier_confirm_sent_at")
    op.drop_column("commitments", "supplier_confirm_status")
    op.drop_column("commitments", "order_by_date")
    op.drop_column("commitments", "schedule_item_id")
    op.drop_column("commitments", "lead_time_days")
