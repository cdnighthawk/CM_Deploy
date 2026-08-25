"""First-class estimates per lead: drawing sets, estimate fields, takeoff FK.

Revision ID: 0057_independent_estimates
Revises: 0056_purge_test_projects
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.dialects import postgresql

from app.services.estimate_backfill import backfill_default_estimates


def _drop_fks_on_column(table: str, column: str) -> None:
    inspector = sa_inspect(op.get_bind())
    for fk in inspector.get_foreign_keys(table):
        if column in (fk.get("constrained_columns") or []):
            name = fk.get("name")
            if name:
                op.drop_constraint(name, table, type_="foreignkey")

revision: str = "0057_independent_estimates"
down_revision: Union[str, Sequence[str], None] = "0056_purge_test_projects"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "drawing_sets",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("lead_estimate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("issued_date", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["lead_estimate_id"], ["lead_estimates.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_drawing_sets_lead_estimate_id", "drawing_sets", ["lead_estimate_id"], unique=False)

    op.add_column("estimates", sa.Column("name", sa.String(length=255), nullable=True))
    op.add_column("estimates", sa.Column("version_label", sa.String(length=64), nullable=True))
    op.add_column("estimates", sa.Column("gc_company_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("estimates", sa.Column("gc_name", sa.String(length=255), nullable=True))
    op.add_column("estimates", sa.Column("drawing_set_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("estimates", sa.Column("fee_percentage", sa.Numeric(7, 4), nullable=True))
    op.add_column("estimates", sa.Column("profit_margin", sa.Numeric(7, 4), nullable=True))
    op.add_column("estimates", sa.Column("rom", sa.Numeric(15, 2), nullable=True))
    op.add_column(
        "estimates",
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column("estimates", sa.Column("estimate_locked_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("estimates", sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("estimates", sa.Column("created_from_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("estimates", sa.Column("created_by_id", postgresql.UUID(as_uuid=True), nullable=True))

    op.create_index("ix_estimates_gc_company_id", "estimates", ["gc_company_id"], unique=False)
    op.create_index("ix_estimates_drawing_set_id", "estimates", ["drawing_set_id"], unique=False)
    op.create_index("ix_estimates_created_from_id", "estimates", ["created_from_id"], unique=False)
    op.create_index("ix_estimates_created_by_id", "estimates", ["created_by_id"], unique=False)
    op.create_index("ix_estimates_estimate_locked_at", "estimates", ["estimate_locked_at"], unique=False)
    op.create_index(
        "uq_estimates_one_current_per_lead",
        "estimates",
        ["lead_estimate_id"],
        unique=True,
        postgresql_where=sa.text("is_current IS true AND lead_estimate_id IS NOT NULL"),
    )

    op.create_foreign_key(
        "estimates_gc_company_id_fkey",
        "estimates",
        "companies",
        ["gc_company_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "estimates_drawing_set_id_fkey",
        "estimates",
        "drawing_sets",
        ["drawing_set_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "estimates_created_from_id_fkey",
        "estimates",
        "estimates",
        ["created_from_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "estimates_created_by_id_fkey",
        "estimates",
        "users",
        ["created_by_id"],
        ["id"],
        ondelete="SET NULL",
    )

    _drop_fks_on_column("estimates", "lead_estimate_id")
    op.create_foreign_key(
        "estimates_lead_estimate_id_fkey",
        "estimates",
        "lead_estimates",
        ["lead_estimate_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.add_column("takeoff_line_items", sa.Column("estimate_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_index("ix_takeoff_line_items_estimate_id", "takeoff_line_items", ["estimate_id"], unique=False)
    op.create_foreign_key(
        "takeoff_line_items_estimate_id_fkey",
        "takeoff_line_items",
        "estimates",
        ["estimate_id"],
        ["id"],
        ondelete="CASCADE",
    )

    backfill_default_estimates(op.get_bind())

    op.execute(
        sa.text(
            """
            UPDATE estimates
            SET name = COALESCE(NULLIF(BTRIM(name), ''), NULLIF(BTRIM(title), ''), 'Original Estimate'),
                fee_percentage = COALESCE(fee_percentage, 0)
            """
        )
    )
    op.alter_column(
        "estimates",
        "name",
        existing_type=sa.String(length=255),
        nullable=False,
        server_default="Original Estimate",
    )
    op.alter_column(
        "estimates",
        "fee_percentage",
        existing_type=sa.Numeric(7, 4),
        nullable=False,
        server_default="0",
    )


def downgrade() -> None:
    op.drop_constraint("takeoff_line_items_estimate_id_fkey", "takeoff_line_items", type_="foreignkey")
    op.drop_index("ix_takeoff_line_items_estimate_id", table_name="takeoff_line_items")
    op.drop_column("takeoff_line_items", "estimate_id")

    _drop_fks_on_column("estimates", "lead_estimate_id")
    op.create_foreign_key(
        "estimates_lead_estimate_id_fkey",
        "estimates",
        "lead_estimates",
        ["lead_estimate_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.drop_constraint("estimates_created_by_id_fkey", "estimates", type_="foreignkey")
    op.drop_constraint("estimates_created_from_id_fkey", "estimates", type_="foreignkey")
    op.drop_constraint("estimates_drawing_set_id_fkey", "estimates", type_="foreignkey")
    op.drop_constraint("estimates_gc_company_id_fkey", "estimates", type_="foreignkey")
    op.drop_index("uq_estimates_one_current_per_lead", table_name="estimates")
    op.drop_index("ix_estimates_estimate_locked_at", table_name="estimates")
    op.drop_index("ix_estimates_created_by_id", table_name="estimates")
    op.drop_index("ix_estimates_created_from_id", table_name="estimates")
    op.drop_index("ix_estimates_drawing_set_id", table_name="estimates")
    op.drop_index("ix_estimates_gc_company_id", table_name="estimates")
    op.drop_column("estimates", "created_by_id")
    op.drop_column("estimates", "created_from_id")
    op.drop_column("estimates", "approved_at")
    op.drop_column("estimates", "estimate_locked_at")
    op.drop_column("estimates", "is_current")
    op.drop_column("estimates", "rom")
    op.drop_column("estimates", "profit_margin")
    op.drop_column("estimates", "fee_percentage")
    op.drop_column("estimates", "drawing_set_id")
    op.drop_column("estimates", "gc_name")
    op.drop_column("estimates", "gc_company_id")
    op.drop_column("estimates", "version_label")
    op.drop_column("estimates", "name")

    op.drop_index("ix_drawing_sets_lead_estimate_id", table_name="drawing_sets")
    op.drop_table("drawing_sets")
