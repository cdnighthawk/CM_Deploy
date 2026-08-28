"""Vendor AP invoices, attachments, events, and ap module permissions."""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0061_vendor_invoices"
down_revision: Union[str, Sequence[str], None] = "0060_website_reviewer_role"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "vendor_invoices",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="received"),
        sa.Column("source", sa.String(length=16), nullable=False, server_default="manual"),
        sa.Column("graph_message_id", sa.String(length=512), nullable=True),
        sa.Column("mailbox", sa.String(length=255), nullable=True),
        sa.Column("from_email", sa.String(length=255), nullable=True),
        sa.Column("from_name", sa.String(length=255), nullable=True),
        sa.Column("subject", sa.String(length=500), nullable=True),
        sa.Column("body_preview", sa.Text(), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("vendor_company_id", sa.UUID(), nullable=True),
        sa.Column("project_id", sa.UUID(), nullable=True),
        sa.Column("commitment_id", sa.UUID(), nullable=True),
        sa.Column("invoice_number", sa.String(length=80), nullable=True),
        sa.Column("invoice_date", sa.Date(), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="USD"),
        sa.Column("po_number", sa.String(length=80), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("parse_meta", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("routed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("routed_by_user_id", sa.UUID(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("submitted_by_user_id", sa.UUID(), nullable=True),
        sa.Column("approver_user_id", sa.UUID(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paid_by_user_id", sa.UUID(), nullable=True),
        sa.Column("payment_ref", sa.String(length=120), nullable=True),
        sa.ForeignKeyConstraint(["vendor_company_id"], ["companies.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["commitment_id"], ["commitments.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["routed_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["submitted_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["approver_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["paid_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("graph_message_id"),
    )
    op.create_index("ix_vendor_invoices_status", "vendor_invoices", ["status"])
    op.create_index("ix_vendor_invoices_from_email", "vendor_invoices", ["from_email"])
    op.create_index("ix_vendor_invoices_received_at", "vendor_invoices", ["received_at"])
    op.create_index("ix_vendor_invoices_vendor_company_id", "vendor_invoices", ["vendor_company_id"])
    op.create_index("ix_vendor_invoices_project_id", "vendor_invoices", ["project_id"])
    op.create_index("ix_vendor_invoices_commitment_id", "vendor_invoices", ["commitment_id"])
    op.create_index("ix_vendor_invoices_invoice_number", "vendor_invoices", ["invoice_number"])

    op.create_table(
        "vendor_invoice_files",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("invoice_id", sa.UUID(), nullable=False),
        sa.Column("document_id", sa.UUID(), nullable=False),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("original_filename", sa.String(length=500), nullable=True),
        sa.Column("content_type", sa.String(length=120), nullable=True),
        sa.ForeignKeyConstraint(["invoice_id"], ["vendor_invoices.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("invoice_id", "document_id", name="uq_vendor_invoice_files_invoice_document"),
    )
    op.create_index("ix_vendor_invoice_files_invoice_id", "vendor_invoice_files", ["invoice_id"])
    op.create_index("ix_vendor_invoice_files_document_id", "vendor_invoice_files", ["document_id"])

    op.create_table(
        "vendor_invoice_events",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("invoice_id", sa.UUID(), nullable=False),
        sa.Column("actor_user_id", sa.UUID(), nullable=True),
        sa.Column("action", sa.String(length=40), nullable=False),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["invoice_id"], ["vendor_invoices.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_vendor_invoice_events_invoice_id", "vendor_invoice_events", ["invoice_id"])
    op.create_index("ix_vendor_invoice_events_action", "vendor_invoice_events", ["action"])

    from app.permissions.defaults import DEFAULTS_BY_ROLE_CODE

    conn = op.get_bind()
    for role_code, perms in DEFAULTS_BY_ROLE_CODE.items():
        level = perms.get("ap", "none")
        conn.execute(
            sa.text(
                """
                INSERT INTO role_module_permissions (role_id, module_code, access_level)
                SELECT r.id, 'ap', :access_level
                FROM roles r
                WHERE r.code = :role_code
                ON CONFLICT (role_id, module_code) DO UPDATE
                SET access_level = EXCLUDED.access_level
                """
            ),
            {"role_code": role_code, "access_level": level},
        )


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM role_module_permissions WHERE module_code = 'ap'"))
    op.drop_index("ix_vendor_invoice_events_action", table_name="vendor_invoice_events")
    op.drop_index("ix_vendor_invoice_events_invoice_id", table_name="vendor_invoice_events")
    op.drop_table("vendor_invoice_events")
    op.drop_index("ix_vendor_invoice_files_document_id", table_name="vendor_invoice_files")
    op.drop_index("ix_vendor_invoice_files_invoice_id", table_name="vendor_invoice_files")
    op.drop_table("vendor_invoice_files")
    op.drop_index("ix_vendor_invoices_invoice_number", table_name="vendor_invoices")
    op.drop_index("ix_vendor_invoices_commitment_id", table_name="vendor_invoices")
    op.drop_index("ix_vendor_invoices_project_id", table_name="vendor_invoices")
    op.drop_index("ix_vendor_invoices_vendor_company_id", table_name="vendor_invoices")
    op.drop_index("ix_vendor_invoices_received_at", table_name="vendor_invoices")
    op.drop_index("ix_vendor_invoices_from_email", table_name="vendor_invoices")
    op.drop_index("ix_vendor_invoices_status", table_name="vendor_invoices")
    op.drop_table("vendor_invoices")
