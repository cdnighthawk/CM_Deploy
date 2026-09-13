"""Field punch list tables for FinishWorks Field.

Revision ID: 0102_field_punch
Revises: 0106_user_office
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0102_field_punch"
down_revision: Union[str, Sequence[str], None] = "0106_user_office"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "punch_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("local_id", sa.String(length=64), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("list", sa.String(length=12), nullable=False, server_default="ours"),
        sa.Column("number", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="open"),
        sa.Column("type", sa.String(length=40), nullable=True),
        sa.Column("priority", sa.String(length=20), nullable=False, server_default="normal"),
        sa.Column("location_text", sa.String(length=255), nullable=True),
        sa.Column("location_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("trade", sa.String(length=80), nullable=True),
        sa.Column("assignee_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("due_on", sa.Date(), nullable=True),
        sa.Column("schedule_impact", sa.String(length=20), nullable=False, server_default="none"),
        sa.Column("schedule_note", sa.String(length=500), nullable=True),
        sa.Column("cost_impact", sa.String(length=20), nullable=False, server_default="none"),
        sa.Column("cost_note", sa.String(length=500), nullable=True),
        sa.Column("drawing_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("revision_id", sa.String(length=80), nullable=True),
        sa.Column("pin_x", sa.Float(), nullable=True),
        sa.Column("pin_y", sa.Float(), nullable=True),
        sa.Column("source", sa.String(length=20), nullable=False, server_default="internal"),
        sa.Column("external_id", sa.String(length=120), nullable=True),
        sa.Column("external_type", sa.String(length=80), nullable=True),
        sa.Column("gc_manager", sa.String(length=200), nullable=True),
        sa.Column("gc_approver", sa.String(length=200), nullable=True),
        sa.Column("notify_on_save", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("last_notified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status_changed_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["assignee_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["drawing_id"], ["drawings.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["location_id"], ["rfi_locations.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["status_changed_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("local_id", name="uq_punch_items_local_id"),
    )
    op.create_index("ix_punch_items_local_id", "punch_items", ["local_id"])
    op.create_index("ix_punch_items_project_id", "punch_items", ["project_id"])
    op.create_index("ix_punch_items_project_list_status", "punch_items", ["project_id", "list", "status"])
    op.create_index("ix_punch_items_project_updated", "punch_items", ["project_id", "updated_at"])

    op.create_table(
        "punch_distributions",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("local_id", sa.String(length=64), nullable=True),
        sa.Column("punch_item_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("contact_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=True),
        sa.Column("role", sa.String(length=80), nullable=True),
        sa.Column("notified_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["contact_id"], ["contacts.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["punch_item_id"], ["punch_items.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("local_id", name="uq_punch_distributions_local_id"),
    )
    op.create_index("ix_punch_distributions_local_id", "punch_distributions", ["local_id"])
    op.create_index("ix_punch_distributions_punch_item_id", "punch_distributions", ["punch_item_id"])

    op.create_table(
        "punch_notify_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("punch_item_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("recipients_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("channel", sa.String(length=20), nullable=False, server_default="email"),
        sa.Column("message_id", sa.String(length=200), nullable=True),
        sa.Column("sent_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(["punch_item_id"], ["punch_items.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["sent_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_punch_notify_logs_punch_item_id", "punch_notify_logs", ["punch_item_id"])

    op.add_column(
        "field_photos",
        sa.Column("punch_item_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_field_photos_punch_item_id",
        "field_photos",
        "punch_items",
        ["punch_item_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_field_photos_punch_item_id", "field_photos", ["punch_item_id"])


def downgrade() -> None:
    op.drop_index("ix_field_photos_punch_item_id", table_name="field_photos")
    op.drop_constraint("fk_field_photos_punch_item_id", "field_photos", type_="foreignkey")
    op.drop_column("field_photos", "punch_item_id")
    op.drop_index("ix_punch_notify_logs_punch_item_id", table_name="punch_notify_logs")
    op.drop_table("punch_notify_logs")
    op.drop_index("ix_punch_distributions_punch_item_id", table_name="punch_distributions")
    op.drop_index("ix_punch_distributions_local_id", table_name="punch_distributions")
    op.drop_table("punch_distributions")
    op.drop_index("ix_punch_items_project_updated", table_name="punch_items")
    op.drop_index("ix_punch_items_project_list_status", table_name="punch_items")
    op.drop_index("ix_punch_items_project_id", table_name="punch_items")
    op.drop_index("ix_punch_items_local_id", table_name="punch_items")
    op.drop_table("punch_items")
