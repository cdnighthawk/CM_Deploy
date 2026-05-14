"""Pay applications (AIA G702–aligned) + schedule-of-values lines.

Revision ID: 0026_pay_applications
Revises: 0025_commitments
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0026_pay_applications"
down_revision: Union[str, Sequence[str], None] = "0025_commitments"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

pay_application_status = postgresql.ENUM(
    "draft",
    "submitted",
    "certified",
    "paid",
    name="pay_application_status",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    pay_application_status.create(bind, checkfirst=True)

    op.create_table(
        "pay_applications",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("application_number", sa.Integer(), nullable=False),
        sa.Column("period_to", sa.Date(), nullable=True),
        sa.Column("status", pay_application_status, nullable=False, server_default="draft"),
        sa.Column("original_contract_sum", sa.Numeric(15, 2), nullable=True),
        sa.Column("net_change_by_change_orders", sa.Numeric(15, 2), nullable=False, server_default="0"),
        sa.Column("contract_sum_to_date", sa.Numeric(15, 2), nullable=True),
        sa.Column("total_completed_and_stored_to_date", sa.Numeric(15, 2), nullable=True),
        sa.Column("retainage_total", sa.Numeric(15, 2), nullable=True),
        sa.Column("total_earned_less_retainage", sa.Numeric(15, 2), nullable=True),
        sa.Column("less_previous_certificates", sa.Numeric(15, 2), nullable=True),
        sa.Column("current_payment_due", sa.Numeric(15, 2), nullable=True),
        sa.Column("balance_to_finish_including_retainage", sa.Numeric(15, 2), nullable=True),
        sa.Column("architect_certified_amount", sa.Numeric(15, 2), nullable=True),
        sa.Column("architect_certified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_pay_applications_project_id", "pay_applications", ["project_id"], unique=False)
    op.create_index(
        "uq_pay_applications_project_app_no",
        "pay_applications",
        ["project_id", "application_number"],
        unique=True,
    )

    op.create_table(
        "pay_application_lines",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("pay_application_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("parent_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("phase_code", sa.String(40), nullable=True),
        sa.Column("description", sa.String(500), nullable=False, server_default=""),
        sa.Column("scheduled_value", sa.Numeric(15, 2), nullable=False, server_default="0"),
        sa.Column("net_change_co", sa.Numeric(15, 2), nullable=False, server_default="0"),
        sa.Column("work_from_previous", sa.Numeric(15, 2), nullable=False, server_default="0"),
        sa.Column("work_this_period", sa.Numeric(15, 2), nullable=False, server_default="0"),
        sa.Column("materials_stored", sa.Numeric(15, 2), nullable=False, server_default="0"),
        sa.Column("retention_to_date", sa.Numeric(15, 2), nullable=False, server_default="0"),
        sa.Column("balance_to_complete", sa.Numeric(15, 2), nullable=False, server_default="0"),
        sa.Column("balance_due", sa.Numeric(15, 2), nullable=False, server_default="0"),
        sa.Column("percent_complete", sa.Numeric(5, 2), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["pay_application_id"], ["pay_applications.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parent_id"], ["pay_application_lines.id"], ondelete="SET NULL"),
    )
    op.create_index(
        "ix_pay_application_lines_pay_application_id",
        "pay_application_lines",
        ["pay_application_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_pay_application_lines_pay_application_id", table_name="pay_application_lines")
    op.drop_table("pay_application_lines")
    op.drop_index("uq_pay_applications_project_app_no", table_name="pay_applications")
    op.drop_index("ix_pay_applications_project_id", table_name="pay_applications")
    op.drop_table("pay_applications")
    pay_application_status.drop(op.get_bind(), checkfirst=True)
