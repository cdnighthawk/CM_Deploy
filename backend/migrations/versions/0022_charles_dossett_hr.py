"""Seed HR-linked user Charles Dossett (Plan 19 demo extension)."""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

revision: str = "0022_charles_dossett_hr"
down_revision: Union[str, Sequence[str], None] = "0021_hr_module"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

CHARLES_ID = "b1700000-0000-4000-8000-000000000001"
CHARLES_EMAIL = "charles.dossett@usis.local"


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        text(
            """
            INSERT INTO users (id, email, first_name, last_name, is_active, is_superuser, created_at, updated_at)
            VALUES (:id, :email, 'Charles', 'Dossett', true, false, NOW(), NOW())
            ON CONFLICT (email) DO UPDATE SET
                first_name = 'Charles',
                last_name = 'Dossett',
                updated_at = NOW()
            """
        ),
        {"id": CHARLES_ID, "email": CHARLES_EMAIL},
    )

    for stmt in (
        """
        INSERT INTO hr_onboarding_items (id, user_id, title, sort_order, completed_at, created_at, updated_at)
        SELECT gen_random_uuid(), u.id, 'Complete profile & emergency contacts', 1, NULL, NOW(), NOW()
        FROM users u WHERE u.email = :email
        AND NOT EXISTS (
            SELECT 1 FROM hr_onboarding_items o WHERE o.user_id = u.id AND o.title = 'Complete profile & emergency contacts'
        )
        """,
        """
        INSERT INTO hr_onboarding_items (id, user_id, title, sort_order, completed_at, created_at, updated_at)
        SELECT gen_random_uuid(), u.id, 'Acknowledge employee handbook', 2, NULL, NOW(), NOW()
        FROM users u WHERE u.email = :email
        AND NOT EXISTS (
            SELECT 1 FROM hr_onboarding_items o WHERE o.user_id = u.id AND o.title = 'Acknowledge employee handbook'
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
        SELECT gen_random_uuid(), u.id, 'company-orientation-video', NOW() + interval '7 days', NULL, NULL, NOW(), NOW()
        FROM users u WHERE u.email = :email
        AND NOT EXISTS (
            SELECT 1 FROM hr_training_assignments t WHERE t.user_id = u.id AND t.course_key = 'company-orientation-video'
        )
        """,
    ):
        conn.execute(text(stmt), {"email": CHARLES_EMAIL})


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(text("DELETE FROM users WHERE email = :email"), {"email": CHARLES_EMAIL})
