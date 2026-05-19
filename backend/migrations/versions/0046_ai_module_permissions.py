"""Seed ``ai`` module permissions for existing roles."""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

revision: str = "0046_ai_module_permissions"
down_revision: Union[str, Sequence[str], None] = "0045_cm_roles_and_project_members"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from app.permissions.defaults import DEFAULTS_BY_ROLE_CODE

    conn = op.get_bind()
    for role_code, perms in DEFAULTS_BY_ROLE_CODE.items():
        level = perms.get("ai", "none")
        conn.execute(
            text(
                """
                INSERT INTO role_module_permissions (role_id, module_code, access_level)
                SELECT r.id, 'ai', :access_level
                FROM roles r
                WHERE r.code = :role_code
                ON CONFLICT (role_id, module_code) DO UPDATE
                SET access_level = EXCLUDED.access_level
                """
            ),
            {"role_code": role_code, "access_level": level},
        )


def downgrade() -> None:
    op.execute(
        text("DELETE FROM role_module_permissions WHERE module_code = 'ai'")
    )
