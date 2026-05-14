"""Plan 19 HR tables: onboarding items, policy acknowledgments, training assignments + demo employee seed."""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text
from sqlalchemy.dialects import postgresql

revision: str = "0021_hr_module"
down_revision: Union[str, Sequence[str], None] = "0020_playbook_checklists"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DEMO_USER_ID = "a1700000-0000-4000-8000-000000000001"
DEMO_EMAIL = "hr.demo.employee@usis.local"


def upgrade() -> None:
    op.create_table(
        "hr_onboarding_items",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_hr_onboarding_items_user_id", "hr_onboarding_items", ["user_id"], unique=False)

    op.create_table(
        "hr_policy_acknowledgments",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("policy_version", sa.String(120), nullable=False),
        sa.Column("signed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ip_address", sa.String(64), nullable=True),
        sa.Column("approval_request_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_hr_policy_ack_user_id", "hr_policy_acknowledgments", ["user_id"], unique=False)
    op.create_index("ix_hr_policy_ack_version", "hr_policy_acknowledgments", ["policy_version"], unique=False)

    op.create_table(
        "hr_training_assignments",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("course_key", sa.String(120), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_hr_training_user_id", "hr_training_assignments", ["user_id"], unique=False)
    op.create_index("ix_hr_training_course_key", "hr_training_assignments", ["course_key"], unique=False)

    conn = op.get_bind()
    conn.execute(
        text(
            """
            INSERT INTO users (id, email, first_name, last_name, is_active, is_superuser, created_at, updated_at)
            VALUES (:id, :email, 'Jamie', 'Rivera', true, false, NOW(), NOW())
            ON CONFLICT (email) DO NOTHING
            """
        ),
        {"id": DEMO_USER_ID, "email": DEMO_EMAIL},
    )

    for stmt in (
        """
        INSERT INTO hr_onboarding_items (id, user_id, title, sort_order, completed_at, created_at, updated_at)
        SELECT gen_random_uuid(), u.id, 'Send welcome packet', 1, NOW(), NOW(), NOW()
        FROM users u WHERE u.email = :email
        AND NOT EXISTS (
            SELECT 1 FROM hr_onboarding_items o WHERE o.user_id = u.id AND o.title = 'Send welcome packet'
        )
        """,
        """
        INSERT INTO hr_onboarding_items (id, user_id, title, sort_order, completed_at, created_at, updated_at)
        SELECT gen_random_uuid(), u.id, 'Complete payroll profile', 2, NULL, NOW(), NOW()
        FROM users u WHERE u.email = :email
        AND NOT EXISTS (
            SELECT 1 FROM hr_onboarding_items o WHERE o.user_id = u.id AND o.title = 'Complete payroll profile'
        )
        """,
        """
        INSERT INTO hr_policy_acknowledgments (id, user_id, policy_version, signed_at, ip_address, approval_request_id, created_at, updated_at)
        SELECT gen_random_uuid(), u.id, 'handbook-2025-01', NULL, NULL, NULL, NOW(), NOW()
        FROM users u WHERE u.email = :email
        AND NOT EXISTS (
            SELECT 1 FROM hr_policy_acknowledgments p WHERE p.user_id = u.id AND p.policy_version = 'handbook-2025-01'
        )
        """,
        """
        INSERT INTO hr_training_assignments (id, user_id, course_key, due_at, completed_at, document_id, created_at, updated_at)
        SELECT gen_random_uuid(), u.id, 'harassment-prevention-101', NOW() + interval '14 days', NULL, NULL, NOW(), NOW()
        FROM users u WHERE u.email = :email
        AND NOT EXISTS (
            SELECT 1 FROM hr_training_assignments t WHERE t.user_id = u.id AND t.course_key = 'harassment-prevention-101'
        )
        """,
    ):
        conn.execute(text(stmt), {"email": DEMO_EMAIL})


def downgrade() -> None:
    op.drop_index("ix_hr_training_course_key", table_name="hr_training_assignments")
    op.drop_index("ix_hr_training_user_id", table_name="hr_training_assignments")
    op.drop_table("hr_training_assignments")
    op.drop_index("ix_hr_policy_ack_version", table_name="hr_policy_acknowledgments")
    op.drop_index("ix_hr_policy_ack_user_id", table_name="hr_policy_acknowledgments")
    op.drop_table("hr_policy_acknowledgments")
    op.drop_index("ix_hr_onboarding_items_user_id", table_name="hr_onboarding_items")
    op.drop_table("hr_onboarding_items")
    conn = op.get_bind()
    conn.execute(text("DELETE FROM users WHERE email = :email"), {"email": DEMO_EMAIL})
