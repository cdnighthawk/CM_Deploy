"""Estimate spec-package scan tables + RFP source_spec_scan_id.

Revision ID: 0093_est_spec
Revises: 0092_rfp_body
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0093_est_spec"
down_revision: Union[str, Sequence[str], None] = "0092_rfp_body"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "spec_trade_map",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("csi_prefix", sa.String(length=20), nullable=False),
        sa.Column("trade_label", sa.String(length=200), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("default_in_scope", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("csi_prefix", name="uq_spec_trade_map_csi_prefix"),
    )

    op.create_table(
        "estimate_spec_scans",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("estimate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(length=40), server_default="detecting", nullable=False),
        sa.Column("provider", sa.String(length=40), server_default="llama4-scout", nullable=False),
        sa.Column("model_version", sa.String(length=80), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("error_text", sa.Text(), nullable=True),
        sa.Column("raw_response", sa.Text(), nullable=True),
        sa.Column("progress_text", sa.String(length=200), nullable=True),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["estimate_id"], ["estimates.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_estimate_spec_scans_estimate_id", "estimate_spec_scans", ["estimate_id"])
    op.create_index("ix_estimate_spec_scans_project_id", "estimate_spec_scans", ["project_id"])
    op.create_index("ix_estimate_spec_scans_created_by_id", "estimate_spec_scans", ["created_by_id"])

    op.create_table(
        "estimate_spec_sections",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("scan_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("csi_code", sa.String(length=20), nullable=False),
        sa.Column("title", sa.String(length=300), server_default="", nullable=False),
        sa.Column("in_scope", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("out_of_trade", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("shop_alternates", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=True),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("page_start", sa.Integer(), nullable=True),
        sa.Column("page_end", sa.Integer(), nullable=True),
        sa.Column("page_label", sa.String(length=80), nullable=True),
        sa.Column("estimator_notes", sa.Text(), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confirmed_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(["confirmed_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["scan_id"], ["estimate_spec_scans.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_estimate_spec_sections_scan_id", "estimate_spec_sections", ["scan_id"])
    op.create_index("ix_estimate_spec_sections_document_id", "estimate_spec_sections", ["document_id"])

    op.create_table(
        "estimate_spec_mentions",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("section_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("mention_role", sa.String(length=40), nullable=False),
        sa.Column("manufacturer", sa.String(length=200), server_default="", nullable=False),
        sa.Column("product_line", sa.String(length=200), nullable=True),
        sa.Column("model_no", sa.String(length=120), nullable=True),
        sa.Column("finish_note", sa.String(length=300), nullable=True),
        sa.Column("or_equal", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("substitution_note", sa.Text(), nullable=True),
        sa.Column("page_cite", sa.String(length=80), server_default="", nullable=False),
        sa.Column("excerpt", sa.Text(), nullable=True),
        sa.Column("material_pricing_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("configurator_key", sa.String(length=80), nullable=True),
        sa.Column("match_status", sa.String(length=40), server_default="unmatched", nullable=False),
        sa.Column("confirmed", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("product_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(["material_pricing_id"], ["material_pricing.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["section_id"], ["estimate_spec_sections.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_estimate_spec_mentions_section_id", "estimate_spec_mentions", ["section_id"])
    op.create_index("ix_estimate_spec_mentions_material_pricing_id", "estimate_spec_mentions", ["material_pricing_id"])

    op.create_table(
        "estimate_spec_vendors",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("scan_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("suggested_reason", sa.String(length=40), server_default="manual", nullable=False),
        sa.Column("selected", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("rfp_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("sections", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["rfp_id"], ["rfps.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["scan_id"], ["estimate_spec_scans.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_estimate_spec_vendors_scan_id", "estimate_spec_vendors", ["scan_id"])
    op.create_index("ix_estimate_spec_vendors_company_id", "estimate_spec_vendors", ["company_id"])
    op.create_index("ix_estimate_spec_vendors_rfp_id", "estimate_spec_vendors", ["rfp_id"])

    op.add_column("rfps", sa.Column("source_spec_scan_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_index("ix_rfps_source_spec_scan_id", "rfps", ["source_spec_scan_id"])
    op.create_foreign_key(
        "fk_rfps_source_spec_scan_id",
        "rfps",
        "estimate_spec_scans",
        ["source_spec_scan_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_rfps_source_spec_scan_id", "rfps", type_="foreignkey")
    op.drop_index("ix_rfps_source_spec_scan_id", table_name="rfps")
    op.drop_column("rfps", "source_spec_scan_id")
    op.drop_index("ix_estimate_spec_vendors_rfp_id", table_name="estimate_spec_vendors")
    op.drop_index("ix_estimate_spec_vendors_company_id", table_name="estimate_spec_vendors")
    op.drop_index("ix_estimate_spec_vendors_scan_id", table_name="estimate_spec_vendors")
    op.drop_table("estimate_spec_vendors")
    op.drop_index("ix_estimate_spec_mentions_material_pricing_id", table_name="estimate_spec_mentions")
    op.drop_index("ix_estimate_spec_mentions_section_id", table_name="estimate_spec_mentions")
    op.drop_table("estimate_spec_mentions")
    op.drop_index("ix_estimate_spec_sections_document_id", table_name="estimate_spec_sections")
    op.drop_index("ix_estimate_spec_sections_scan_id", table_name="estimate_spec_sections")
    op.drop_table("estimate_spec_sections")
    op.drop_index("ix_estimate_spec_scans_created_by_id", table_name="estimate_spec_scans")
    op.drop_index("ix_estimate_spec_scans_project_id", table_name="estimate_spec_scans")
    op.drop_index("ix_estimate_spec_scans_estimate_id", table_name="estimate_spec_scans")
    op.drop_table("estimate_spec_scans")
    op.drop_table("spec_trade_map")
