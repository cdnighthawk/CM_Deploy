"""Submittals: Procore-style fields, document link, audit, PDF annotation payload.

Revision ID: 0014_submittal_procore_expand
Revises: 0013_drawing_series
Create Date: 2026-05-12
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0014_submittal_procore_expand"
down_revision: Union[str, Sequence[str], None] = "0013_drawing_series"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_submittal_audit_action_pg = postgresql.ENUM(
    "create",
    "edit",
    "status_change",
    "ball_in_court",
    "attachment_add",
    "attachment_remove",
    "annotation_save",
    "delete",
    name="submittal_audit_action",
    create_type=False,
)


def upgrade() -> None:
    op.execute(
        "CREATE TYPE submittal_audit_action AS ENUM ("
        "'create','edit','status_change','ball_in_court',"
        "'attachment_add','attachment_remove','annotation_save','delete')"
    )

    op.add_column("submittals", sa.Column("responsible_contractor", sa.String(300), nullable=True))
    op.add_column("submittals", sa.Column("submit_by_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("submittals", sa.Column("received_from", sa.String(300), nullable=True))
    op.add_column("submittals", sa.Column("received_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("submittals", sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("submittals", sa.Column("returned_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("submittals", sa.Column("response", sa.Text(), nullable=True))
    op.add_column(
        "submittals",
        sa.Column("approvers", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )

    op.add_column(
        "documents",
        sa.Column("submittal_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index("ix_documents_submittal_id", "documents", ["submittal_id"])
    op.create_foreign_key(
        "fk_documents_submittal_id_submittals",
        "documents",
        "submittals",
        ["submittal_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_table(
        "submittal_audit",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("submittal_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("action", _submittal_audit_action_pg, nullable=False),
        sa.Column("summary", sa.String(500), nullable=True),
        sa.Column("before_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("after_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["submittal_id"], ["submittals.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_submittal_audit_submittal_id", "submittal_audit", ["submittal_id"])

    op.create_table(
        "submittal_pdf_annotations",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("author_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["author_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("document_id", name="uq_submittal_pdf_annotations_document"),
    )
    op.create_index("ix_submittal_pdf_annotations_document_id", "submittal_pdf_annotations", ["document_id"])


def downgrade() -> None:
    op.drop_index("ix_submittal_pdf_annotations_document_id", table_name="submittal_pdf_annotations")
    op.drop_table("submittal_pdf_annotations")

    op.drop_index("ix_submittal_audit_submittal_id", table_name="submittal_audit")
    op.drop_table("submittal_audit")

    op.drop_constraint("fk_documents_submittal_id_submittals", "documents", type_="foreignkey")
    op.drop_index("ix_documents_submittal_id", table_name="documents")
    op.drop_column("documents", "submittal_id")

    op.drop_column("submittals", "approvers")
    op.drop_column("submittals", "response")
    op.drop_column("submittals", "returned_at")
    op.drop_column("submittals", "sent_at")
    op.drop_column("submittals", "received_at")
    op.drop_column("submittals", "received_from")
    op.drop_column("submittals", "submit_by_at")
    op.drop_column("submittals", "responsible_contractor")

    op.execute("DROP TYPE IF EXISTS submittal_audit_action")
