"""Phase 1 (Core): users, roles, companies, contacts, projects, documents,
drawings, drawing_annotations, audit_log.

Revision ID: 0001_phase1_core
Revises:
Create Date: 2026-05-11
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_phase1_core"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# --- enum definitions (created once at upgrade) ------------------------------

company_type = postgresql.ENUM(
    "gc",
    "owner",
    "architect",
    "engineer",
    "subcontractor",
    "vendor",
    "self",
    "other",
    name="company_type",
    create_type=False,
)
project_status = postgresql.ENUM(
    "planning",
    "active",
    "on_hold",
    "complete",
    "archived",
    "cancelled",
    name="project_status",
    create_type=False,
)
project_type = postgresql.ENUM(
    "commercial",
    "government",
    "residential",
    "mixed",
    "other",
    name="project_type",
    create_type=False,
)
document_type = postgresql.ENUM(
    "drawing",
    "rfi",
    "submittal",
    "specification",
    "contract",
    "change_order",
    "invoice",
    "photo",
    "report",
    "ai_review_export",
    "safety_doc",
    "permit",
    "other",
    name="document_type",
    create_type=False,
)
annotation_type = postgresql.ENUM(
    "measurement",
    "user_note",
    "ai_review",
    name="annotation_type",
    create_type=False,
)
annotation_severity = postgresql.ENUM(
    "info",
    "minor",
    "major",
    "critical",
    name="annotation_severity",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()

    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto;")

    company_type.create(bind, checkfirst=True)
    project_status.create(bind, checkfirst=True)
    project_type.create(bind, checkfirst=True)
    document_type.create(bind, checkfirst=True)
    annotation_type.create(bind, checkfirst=True)
    annotation_severity.create(bind, checkfirst=True)

    # --- roles ---------------------------------------------------------------
    op.create_table(
        "roles",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("code", sa.String(50), nullable=False, unique=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # --- users ---------------------------------------------------------------
    op.create_table(
        "users",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=True),
        sa.Column("first_name", sa.String(120), nullable=True),
        sa.Column("last_name", sa.String(120), nullable=True),
        sa.Column("phone", sa.String(50), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_superuser", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # --- user_roles ----------------------------------------------------------
    op.create_table(
        "user_roles",
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "role_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("roles.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )

    # --- companies -----------------------------------------------------------
    op.create_table(
        "companies",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("company_type", company_type, nullable=False),
        sa.Column("trade_specialties", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("tax_id", sa.String(50), nullable=True),
        sa.Column("website", sa.String(255), nullable=True),
        sa.Column("phone", sa.String(50), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("address_line1", sa.String(255), nullable=True),
        sa.Column("address_line2", sa.String(255), nullable=True),
        sa.Column("city", sa.String(120), nullable=True),
        sa.Column("state", sa.String(50), nullable=True),
        sa.Column("postal_code", sa.String(20), nullable=True),
        sa.Column("country", sa.String(2), nullable=True, server_default="US"),
        sa.Column("dbe_certified", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("prevailing_wage", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("portal_access_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("performance_score", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_companies_name", "companies", ["name"])
    op.create_index("ix_companies_company_type", "companies", ["company_type"])

    # --- contacts ------------------------------------------------------------
    op.create_table(
        "contacts",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("first_name", sa.String(120), nullable=True),
        sa.Column("last_name", sa.String(120), nullable=True),
        sa.Column("title", sa.String(120), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("phone", sa.String(50), nullable=True),
        sa.Column("mobile", sa.String(50), nullable=True),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_contacts_company_id", "contacts", ["company_id"])
    op.create_index("ix_contacts_email", "contacts", ["email"])

    # --- projects ------------------------------------------------------------
    op.create_table(
        "projects",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("number", sa.String(50), nullable=True, unique=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", project_status, nullable=False, server_default="planning"),
        sa.Column("project_type", project_type, nullable=False, server_default="commercial"),
        sa.Column(
            "gc_company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "owner_company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "architect_company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("address_line1", sa.String(255), nullable=True),
        sa.Column("address_line2", sa.String(255), nullable=True),
        sa.Column("city", sa.String(120), nullable=True),
        sa.Column("state", sa.String(50), nullable=True),
        sa.Column("postal_code", sa.String(20), nullable=True),
        sa.Column("country", sa.String(2), nullable=True, server_default="US"),
        sa.Column("contract_value", sa.Numeric(15, 2), nullable=True),
        sa.Column("contract_date", sa.Date(), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("substantial_completion_date", sa.Date(), nullable=True),
        sa.Column("closeout_date", sa.Date(), nullable=True),
        sa.Column("retention_percentage", sa.Numeric(5, 2), nullable=True),
        sa.Column("prevailing_wage", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("dbe_required", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("sage_project_id", sa.String(100), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_projects_name", "projects", ["name"])
    op.create_index("ix_projects_number", "projects", ["number"])
    op.create_index("ix_projects_sage_project_id", "projects", ["sage_project_id"])

    # --- documents (polymorphic base) ---------------------------------------
    op.create_table(
        "documents",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("document_type", document_type, nullable=False),
        sa.Column("title", sa.String(500), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("file_url", sa.String(1024), nullable=True),
        sa.Column("thumbnail_url", sa.String(1024), nullable=True),
        sa.Column("original_filename", sa.String(500), nullable=True),
        sa.Column("mime_type", sa.String(120), nullable=True),
        sa.Column("file_size_bytes", sa.Integer(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "parent_document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "uploaded_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("tags", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_documents_project_id", "documents", ["project_id"])
    op.create_index("ix_documents_document_type", "documents", ["document_type"])
    op.create_index("ix_documents_parent_document_id", "documents", ["parent_document_id"])

    # --- drawings (joined-inheritance specialization) -----------------------
    op.create_table(
        "drawings",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("sheet_number", sa.String(50), nullable=True),
        sa.Column("sheet_title", sa.String(500), nullable=True),
        sa.Column("discipline", sa.String(50), nullable=True),
        sa.Column("scale", sa.String(50), nullable=True),
        sa.Column("calibration", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("drawing_set", sa.String(120), nullable=True),
        sa.Column("revision", sa.String(50), nullable=True),
    )
    op.create_index("ix_drawings_sheet_number", "drawings", ["sheet_number"])

    # --- drawing_annotations ------------------------------------------------
    op.create_table(
        "drawing_annotations",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "drawing_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("drawings.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("type", annotation_type, nullable=False),
        sa.Column("data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("severity", annotation_severity, nullable=True),
        sa.Column("provider", sa.String(120), nullable=True),
        sa.Column("model_version", sa.String(120), nullable=True),
        sa.Column("issues", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("raw_response", sa.Text(), nullable=True),
        sa.Column("cost_impact", sa.Numeric(15, 2), nullable=True),
        sa.Column("delay_impact_days", sa.Integer(), nullable=True),
        sa.Column(
            "created_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_drawing_annotations_drawing_id", "drawing_annotations", ["drawing_id"])
    op.create_index("ix_drawing_annotations_type", "drawing_annotations", ["type"])

    # --- audit_log ----------------------------------------------------------
    op.create_table(
        "audit_log",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("entity_type", sa.String(120), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("changes", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.String(500), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_audit_log_user_id", "audit_log", ["user_id"])
    op.create_index("ix_audit_log_entity_type", "audit_log", ["entity_type"])
    op.create_index("ix_audit_log_entity_id", "audit_log", ["entity_id"])
    op.create_index("ix_audit_log_action", "audit_log", ["action"])


def downgrade() -> None:
    op.drop_table("audit_log")
    op.drop_table("drawing_annotations")
    op.drop_table("drawings")
    op.drop_table("documents")
    op.drop_table("projects")
    op.drop_table("contacts")
    op.drop_table("companies")
    op.drop_table("user_roles")
    op.drop_table("users")
    op.drop_table("roles")

    bind = op.get_bind()
    annotation_severity.drop(bind, checkfirst=True)
    annotation_type.drop(bind, checkfirst=True)
    document_type.drop(bind, checkfirst=True)
    project_type.drop(bind, checkfirst=True)
    project_status.drop(bind, checkfirst=True)
    company_type.drop(bind, checkfirst=True)
