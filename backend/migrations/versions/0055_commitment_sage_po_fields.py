"""Sage CM PO header/line fields, project directory, PO types.

Revision ID: 0055_commitment_sage_po
Revises: 0054_staff_only_policy_acks
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0055_commitment_sage_po"
down_revision: Union[str, Sequence[str], None] = "0054_staff_only_policy_acks"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

commitment_resource_enum = postgresql.ENUM(
    "material",
    "labor",
    "equipment",
    "subcontractor",
    "other",
    name="commitment_resource",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    commitment_resource_enum.create(bind, checkfirst=True)

    op.create_table(
        "procurement_po_types",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("code", sa.String(40), nullable=False, unique=True),
        sa.Column("label", sa.String(120), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_procurement_po_types_sort", "procurement_po_types", ["sort_order"], unique=False)

    op.create_table(
        "project_directory_companies",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("project_id", "company_id", name="uq_project_directory_company"),
    )
    op.create_index(
        "ix_project_directory_companies_project_id",
        "project_directory_companies",
        ["project_id"],
        unique=False,
    )

    op.add_column("commitments", sa.Column("issue_date", sa.Date(), nullable=True))
    op.add_column("commitments", sa.Column("po_type", sa.String(40), nullable=True))
    op.add_column("commitments", sa.Column("reminder_date", sa.Date(), nullable=True))
    op.add_column("commitments", sa.Column("vendor_contact_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("commitments", sa.Column("vendor_address_snapshot", sa.Text(), nullable=True))
    op.add_column("commitments", sa.Column("issued_by_user_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("commitments", sa.Column("authorized_by_user_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("commitments", sa.Column("issued_by_address_snapshot", sa.Text(), nullable=True))
    op.add_column("commitments", sa.Column("ship_to_address", sa.Text(), nullable=True))
    op.add_column("commitments", sa.Column("default_delivery_date", sa.Date(), nullable=True))
    op.add_column("commitments", sa.Column("default_cost_code_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("commitments", sa.Column("default_tax_code", sa.String(40), nullable=True))
    op.add_column(
        "commitments",
        sa.Column("default_resource", commitment_resource_enum, nullable=True),
    )
    op.create_foreign_key(
        "fk_commitments_vendor_contact_id",
        "commitments",
        "contacts",
        ["vendor_contact_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_commitments_issued_by_user_id",
        "commitments",
        "users",
        ["issued_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_commitments_authorized_by_user_id",
        "commitments",
        "users",
        ["authorized_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_commitments_default_cost_code_id",
        "commitments",
        "rfi_cost_codes",
        ["default_cost_code_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.add_column("commitment_line_items", sa.Column("item_number", sa.String(40), nullable=True))
    op.add_column(
        "commitment_line_items",
        sa.Column("resource", commitment_resource_enum, nullable=True),
    )
    op.add_column("commitment_line_items", sa.Column("delivery_date", sa.Date(), nullable=True))

    # Seed default PO types
    op.execute(
        sa.text(
            """
            INSERT INTO procurement_po_types (code, label, sort_order) VALUES
            ('material', 'Material', 10),
            ('subcontract', 'Subcontract', 20),
            ('equipment', 'Equipment', 30),
            ('other', 'Other', 40)
            ON CONFLICT (code) DO NOTHING
            """
        )
    )

    # Seed project directory from existing commitments and project GC
    op.execute(
        sa.text(
            """
            INSERT INTO project_directory_companies (project_id, company_id)
            SELECT DISTINCT c.project_id, c.vendor_company_id
            FROM commitments c
            ON CONFLICT (project_id, company_id) DO NOTHING
            """
        )
    )
    op.execute(
        sa.text(
            """
            INSERT INTO project_directory_companies (project_id, company_id)
            SELECT p.id, p.gc_company_id
            FROM projects p
            WHERE p.gc_company_id IS NOT NULL
            ON CONFLICT (project_id, company_id) DO NOTHING
            """
        )
    )


def downgrade() -> None:
    op.drop_column("commitment_line_items", "delivery_date")
    op.drop_column("commitment_line_items", "resource")
    op.drop_column("commitment_line_items", "item_number")

    op.drop_constraint("fk_commitments_default_cost_code_id", "commitments", type_="foreignkey")
    op.drop_constraint("fk_commitments_authorized_by_user_id", "commitments", type_="foreignkey")
    op.drop_constraint("fk_commitments_issued_by_user_id", "commitments", type_="foreignkey")
    op.drop_constraint("fk_commitments_vendor_contact_id", "commitments", type_="foreignkey")
    op.drop_column("commitments", "default_resource")
    op.drop_column("commitments", "default_tax_code")
    op.drop_column("commitments", "default_cost_code_id")
    op.drop_column("commitments", "default_delivery_date")
    op.drop_column("commitments", "ship_to_address")
    op.drop_column("commitments", "issued_by_address_snapshot")
    op.drop_column("commitments", "authorized_by_user_id")
    op.drop_column("commitments", "issued_by_user_id")
    op.drop_column("commitments", "vendor_address_snapshot")
    op.drop_column("commitments", "vendor_contact_id")
    op.drop_column("commitments", "reminder_date")
    op.drop_column("commitments", "po_type")
    op.drop_column("commitments", "issue_date")

    op.drop_index("ix_project_directory_companies_project_id", table_name="project_directory_companies")
    op.drop_table("project_directory_companies")
    op.drop_index("ix_procurement_po_types_sort", table_name="procurement_po_types")
    op.drop_table("procurement_po_types")

    bind = op.get_bind()
    commitment_resource_enum.drop(bind, checkfirst=True)
