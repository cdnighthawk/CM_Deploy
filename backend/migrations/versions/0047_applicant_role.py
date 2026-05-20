"""Seed job-applicant role (hire wizard only; no staff CM modules)."""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

revision: str = "0047_applicant_role"
down_revision: Union[str, Sequence[str], None] = "0046_ai_module_permissions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from app.permissions.defaults import DEFAULTS_BY_ROLE_CODE

    conn = op.get_bind()
    conn.execute(
        text(
            """
            INSERT INTO roles (id, code, name, created_at, updated_at)
            VALUES (gen_random_uuid(), 'applicant', 'Job applicant', NOW(), NOW())
            ON CONFLICT (code) DO UPDATE SET name = EXCLUDED.name
            """
        )
    )
    perms = DEFAULTS_BY_ROLE_CODE["applicant"]
    for module_code, access_level in perms.items():
        conn.execute(
            text(
                """
                INSERT INTO role_module_permissions (role_id, module_code, access_level)
                SELECT r.id, :module_code, :access_level
                FROM roles r
                WHERE r.code = 'applicant'
                ON CONFLICT (role_id, module_code) DO UPDATE
                SET access_level = EXCLUDED.access_level
                """
            ),
            {"module_code": module_code, "access_level": access_level},
        )

    # Self-registered users with no role: treat as applicants going forward.
    conn.execute(
        text(
            """
            INSERT INTO user_roles (user_id, role_id)
            SELECT u.id, r.id
            FROM users u
            CROSS JOIN roles r
            WHERE r.code = 'applicant'
              AND NOT EXISTS (SELECT 1 FROM user_roles ur WHERE ur.user_id = u.id)
            """
        )
    )


def downgrade() -> None:
    op.execute(text("DELETE FROM user_roles WHERE role_id IN (SELECT id FROM roles WHERE code = 'applicant')"))
    op.execute(text("DELETE FROM role_module_permissions WHERE role_id IN (SELECT id FROM roles WHERE code = 'applicant')"))
    op.execute(text("DELETE FROM roles WHERE code = 'applicant'"))
