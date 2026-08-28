"""Assign a user on installation windows and track reminder send date.

Revision ID: 0066_schedule_item_assignee
Revises: 0065_pay_app_collection_status
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0066_schedule_item_assignee"
down_revision: Union[str, Sequence[str], None] = "0065_pay_app_collection_status"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    cols = {c["name"] for c in insp.get_columns("project_schedule_items")}
    fks = {fk["name"] for fk in insp.get_foreign_keys("project_schedule_items")}
    indexes = {idx["name"] for idx in insp.get_indexes("project_schedule_items")}
    if "assignee_user_id" not in cols:
        op.add_column(
            "project_schedule_items",
            sa.Column("assignee_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        )
    if "reminder_sent_on" not in cols:
        op.add_column(
            "project_schedule_items",
            sa.Column("reminder_sent_on", sa.Date(), nullable=True),
        )
    if "fk_project_schedule_items_assignee_user_id" not in fks:
        op.create_foreign_key(
            "fk_project_schedule_items_assignee_user_id",
            "project_schedule_items",
            "users",
            ["assignee_user_id"],
            ["id"],
            ondelete="SET NULL",
        )
    if "ix_project_schedule_items_assignee_user_id" not in indexes:
        op.create_index(
            "ix_project_schedule_items_assignee_user_id",
            "project_schedule_items",
            ["assignee_user_id"],
        )


def downgrade() -> None:
    op.drop_index("ix_project_schedule_items_assignee_user_id", table_name="project_schedule_items")
    op.drop_constraint(
        "fk_project_schedule_items_assignee_user_id",
        "project_schedule_items",
        type_="foreignkey",
    )
    op.drop_column("project_schedule_items", "reminder_sent_on")
    op.drop_column("project_schedule_items", "assignee_user_id")
