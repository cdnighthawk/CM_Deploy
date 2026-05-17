"""HR dispatch revisions, project material orders, submittal line items, product catalog.

Revision ID: 0042_dispatch_material_submittal_lines
Revises: 0041_textura_external_ids
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0042_dispatch_material_submittal_lines"
down_revision: Union[str, Sequence[str], None] = "0041_textura_external_ids"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "hr_employee_dispatches",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("effective_date", sa.Date(), nullable=True),
        sa.Column("supersedes_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("pay_scale_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("hourly_rate_snapshot", sa.Numeric(12, 4), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("union_document_file_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["pay_scale_id"], ["hr_employee_pay_scales.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["supersedes_id"], ["hr_employee_dispatches.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["union_document_file_id"], ["hr_hire_union_document_files.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "project_id", "revision", name="uq_hr_dispatch_user_project_rev"),
    )
    op.create_index("ix_hr_employee_dispatches_user_id", "hr_employee_dispatches", ["user_id"])
    op.create_index("ix_hr_employee_dispatches_project_id", "hr_employee_dispatches", ["project_id"])

    op.create_table(
        "manufacturer_product_data",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("manufacturer", sa.String(length=200), nullable=False),
        sa.Column("model", sa.String(length=200), nullable=False),
        sa.Column("product_name", sa.String(length=500), nullable=True),
        sa.Column("pdf_url", sa.String(length=1024), nullable=True),
        sa.Column("pattern_key", sa.String(length=40), nullable=True),
        sa.Column("technical_data_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_manufacturer_product_data_manufacturer", "manufacturer_product_data", ["manufacturer"])
    op.create_index("ix_manufacturer_product_data_model", "manufacturer_product_data", ["model"])
    op.create_index("ix_manufacturer_product_data_pattern_key", "manufacturer_product_data", ["pattern_key"])

    op.create_table(
        "project_material_orders",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("commitment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("vendor_company_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("vendor_name", sa.String(length=300), nullable=False, server_default=""),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("order_date", sa.Date(), nullable=True),
        sa.Column("lead_time_days", sa.Integer(), nullable=True),
        sa.Column("schedule_anchor_date", sa.Date(), nullable=True),
        sa.Column("expected_delivery_date", sa.Date(), nullable=True),
        sa.Column("shipping_company", sa.String(length=200), nullable=True),
        sa.Column("tracking_number", sa.String(length=120), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="draft"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["commitment_id"], ["commitments.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["vendor_company_id"], ["companies.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_project_material_orders_project_id", "project_material_orders", ["project_id"])
    op.create_index("ix_project_material_orders_commitment_id", "project_material_orders", ["commitment_id"])
    op.create_index("ix_project_material_orders_status", "project_material_orders", ["status"])

    op.create_table(
        "submittal_line_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("submittal_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("spec_section_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("spec_section_code", sa.String(length=40), nullable=True),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("manufacturer", sa.String(length=200), nullable=True),
        sa.Column("model", sa.String(length=200), nullable=True),
        sa.Column("catalog_product_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("pdf_url", sa.String(length=1024), nullable=True),
        sa.ForeignKeyConstraint(["catalog_product_id"], ["manufacturer_product_data.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["spec_section_id"], ["rfi_spec_sections.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["submittal_id"], ["submittals.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_submittal_line_items_submittal_id", "submittal_line_items", ["submittal_id"])

    op.execute(
        sa.text(
            """
            INSERT INTO manufacturer_product_data (id, manufacturer, model, product_name, pdf_url, pattern_key, technical_data_json)
            VALUES
            (gen_random_uuid(), 'ASI', 'GENERIC', 'ASI product data template', NULL, 'asi',
             '{"source":"preset","notes":"Auto-fill technical manual references for ASI hardware submittals."}'::jsonb),
            (gen_random_uuid(), 'Bobrick', 'GENERIC', 'Bobrick technical data', NULL, 'bobrick',
             '{"source":"preset","notes":"Auto-fill Bobrick TM references for product data submittals."}'::jsonb)
            """
        )
    )


def downgrade() -> None:
    op.drop_index("ix_submittal_line_items_submittal_id", table_name="submittal_line_items")
    op.drop_table("submittal_line_items")
    op.drop_index("ix_project_material_orders_status", table_name="project_material_orders")
    op.drop_index("ix_project_material_orders_commitment_id", table_name="project_material_orders")
    op.drop_index("ix_project_material_orders_project_id", table_name="project_material_orders")
    op.drop_table("project_material_orders")
    op.drop_index("ix_manufacturer_product_data_pattern_key", table_name="manufacturer_product_data")
    op.drop_index("ix_manufacturer_product_data_model", table_name="manufacturer_product_data")
    op.drop_index("ix_manufacturer_product_data_manufacturer", table_name="manufacturer_product_data")
    op.drop_table("manufacturer_product_data")
    op.drop_index("ix_hr_employee_dispatches_project_id", table_name="hr_employee_dispatches")
    op.drop_index("ix_hr_employee_dispatches_user_id", table_name="hr_employee_dispatches")
    op.drop_table("hr_employee_dispatches")
