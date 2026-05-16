"""Textura TPM integration: external IDs, credentials, sync logs.

Revision ID: 0041_textura_external_ids
Revises: 0040_mobile_refresh_tokens
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0041_textura_external_ids"
down_revision: Union[str, Sequence[str], None] = "0040_mobile_refresh_tokens"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("projects", sa.Column("textura_project_id", sa.String(length=64), nullable=True))
    op.create_index("ix_projects_textura_project_id", "projects", ["textura_project_id"], unique=True)

    op.add_column("pay_applications", sa.Column("textura_invoice_id", sa.String(length=128), nullable=True))
    op.create_index(
        "ix_pay_applications_project_textura_invoice",
        "pay_applications",
        ["project_id", "textura_invoice_id"],
        unique=True,
    )

    op.add_column("commitments", sa.Column("textura_contract_id", sa.String(length=64), nullable=True))
    op.create_index("ix_commitments_textura_contract_id", "commitments", ["textura_contract_id"])

    op.add_column("companies", sa.Column("textura_vendor_id", sa.String(length=64), nullable=True))
    op.create_index("ix_companies_textura_vendor_id", "companies", ["textura_vendor_id"])

    op.create_table(
        "textura_credentials",
        sa.Column("label", sa.String(length=64), nullable=False),
        sa.Column("username", sa.String(length=255), nullable=False),
        sa.Column("password_encrypted", sa.Text(), nullable=False),
        sa.Column("api_base", sa.String(length=512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("label"),
    )

    op.create_table(
        "textura_sync_logs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("direction", sa.String(length=16), nullable=False, server_default="export"),
        sa.Column("entity_type", sa.String(length=32), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="running"),
        sa.Column("loaded", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("skipped", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("errors", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_details", sa.JSON(), nullable=True),
        sa.Column("tpm_job_id", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_textura_sync_logs_started_at", "textura_sync_logs", ["started_at"])


def downgrade() -> None:
    op.drop_index("ix_textura_sync_logs_started_at", table_name="textura_sync_logs")
    op.drop_table("textura_sync_logs")
    op.drop_table("textura_credentials")
    op.drop_index("ix_companies_textura_vendor_id", table_name="companies")
    op.drop_column("companies", "textura_vendor_id")
    op.drop_index("ix_commitments_textura_contract_id", table_name="commitments")
    op.drop_column("commitments", "textura_contract_id")
    op.drop_index("ix_pay_applications_project_textura_invoice", table_name="pay_applications")
    op.drop_column("pay_applications", "textura_invoice_id")
    op.drop_index("ix_projects_textura_project_id", table_name="projects")
    op.drop_column("projects", "textura_project_id")
