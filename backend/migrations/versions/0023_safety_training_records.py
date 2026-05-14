"""Plan 7: safety_training_records + demo rows for HR employee licenses section (read-only via HR API)."""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text
from sqlalchemy.dialects import postgresql

revision: str = "0023_safety_training_records"
down_revision: Union[str, Sequence[str], None] = "0022_charles_dossett_hr"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

JAMIE_ID = "a1700000-0000-4000-8000-000000000001"
CHARLES_ID = "b1700000-0000-4000-8000-000000000001"
DEMO_RECORD_FORKLIFT = "c1700000-0000-4000-8000-000000000001"
DEMO_RECORD_OSHA = "c1700000-0000-4000-8000-000000000002"


def upgrade() -> None:
    op.create_table(
        "safety_training_records",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("training_type", sa.String(80), nullable=False),
        sa.Column("credential_number", sa.String(120), nullable=True),
        sa.Column("issuing_body", sa.String(255), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_safety_training_records_user_id", "safety_training_records", ["user_id"], unique=False)
    op.create_index("ix_safety_training_records_expires_at", "safety_training_records", ["expires_at"], unique=False)

    conn = op.get_bind()
    conn.execute(
        text(
            """
            INSERT INTO safety_training_records (
                id, user_id, project_id, training_type, credential_number, issuing_body,
                completed_at, expires_at, document_id, notes, created_at, updated_at
            ) VALUES (
                CAST(:id1 AS uuid),
                CAST(:jamie AS uuid),
                NULL,
                'forklift',
                'FL-2024-8891',
                'Authorized evaluator program',
                NOW() - INTERVAL '180 days',
                NOW() + INTERVAL '185 days',
                NULL,
                'Demo: company-wide forklift operator card.',
                NOW(),
                NOW()
            )
            ON CONFLICT (id) DO NOTHING
            """
        ),
        {"id1": DEMO_RECORD_FORKLIFT, "jamie": JAMIE_ID},
    )
    conn.execute(
        text(
            """
            INSERT INTO safety_training_records (
                id, user_id, project_id, training_type, credential_number, issuing_body,
                completed_at, expires_at, document_id, notes, created_at, updated_at
            ) VALUES (
                CAST(:id2 AS uuid),
                CAST(:charles AS uuid),
                NULL,
                'osha_10',
                NULL,
                'OSHA Outreach',
                NOW() - INTERVAL '400 days',
                NOW() + INTERVAL '330 days',
                NULL,
                'Demo: OSHA 10-hour construction.',
                NOW(),
                NOW()
            )
            ON CONFLICT (id) DO NOTHING
            """
        ),
        {"id2": DEMO_RECORD_OSHA, "charles": CHARLES_ID},
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        text("DELETE FROM safety_training_records WHERE id IN (CAST(:id1 AS uuid), CAST(:id2 AS uuid))"),
        {"id1": DEMO_RECORD_FORKLIFT, "id2": DEMO_RECORD_OSHA},
    )
    op.drop_index("ix_safety_training_records_expires_at", table_name="safety_training_records")
    op.drop_index("ix_safety_training_records_user_id", table_name="safety_training_records")
    op.drop_table("safety_training_records")
