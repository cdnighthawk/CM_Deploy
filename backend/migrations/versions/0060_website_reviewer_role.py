"""Seed website_reviewer role (company-wide read-only site review)."""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

revision: str = "0060_website_reviewer_role"
down_revision: Union[str, Sequence[str], None] = "0059_import_github_feedback"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_ROLE_CODE = "website_reviewer"


def upgrade() -> None:
    from app.permissions.defaults import DEFAULTS_BY_ROLE_CODE

    conn = op.get_bind()
    conn.execute(
        text(
            """
            INSERT INTO roles (id, code, name, description, created_at, updated_at)
            VALUES (
                gen_random_uuid(),
                :code,
                'Website Reviewer',
                'Company-wide read-only access for site review; no user admin',
                NOW(),
                NOW()
            )
            ON CONFLICT (code) DO UPDATE
            SET name = EXCLUDED.name,
                description = EXCLUDED.description,
                updated_at = NOW()
            """
        ),
        {"code": _ROLE_CODE},
    )
    perms = DEFAULTS_BY_ROLE_CODE[_ROLE_CODE]
    for module_code, access_level in perms.items():
        conn.execute(
            text(
                """
                INSERT INTO role_module_permissions (role_id, module_code, access_level)
                SELECT r.id, :module_code, :access_level
                FROM roles r
                WHERE r.code = :role_code
                ON CONFLICT (role_id, module_code) DO UPDATE
                SET access_level = EXCLUDED.access_level
                """
            ),
            {
                "role_code": _ROLE_CODE,
                "module_code": module_code,
                "access_level": access_level,
            },
        )


def downgrade() -> None:
    op.execute(text("DELETE FROM user_roles WHERE role_id IN (SELECT id FROM roles WHERE code = 'website_reviewer')"))
    op.execute(
        text(
            "DELETE FROM role_module_permissions WHERE role_id IN (SELECT id FROM roles WHERE code = 'website_reviewer')"
        )
    )
    op.execute(text("DELETE FROM roles WHERE code = 'website_reviewer'"))
