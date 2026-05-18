"""Role module permissions: per-role nav/API access levels."""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text

revision: str = "0043_role_module_permissions"
down_revision: Union[str, Sequence[str], None] = "0042_dispatch_material_submittal_lines"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Default levels per role code (see app.permissions.defaults)
_SEED: dict[str, dict[str, str]] = {
    "admin": {c: "admin" for c in (
        "dashboard", "leads", "estimate", "projects", "safety", "crm", "documents",
        "hr", "hrms", "playbooks", "user_admin", "procurement", "reports",
    )},
    "standard": {
        "dashboard": "read", "leads": "write", "estimate": "write", "projects": "write",
        "safety": "write", "crm": "write", "documents": "write", "hr": "read",
        "hrms": "read", "playbooks": "write", "user_admin": "none", "procurement": "write",
        "reports": "read",
    },
    "read_only": {
        "dashboard": "read", "leads": "read", "estimate": "read", "projects": "read",
        "safety": "read", "crm": "read", "documents": "read", "hr": "read",
        "hrms": "read", "playbooks": "read", "user_admin": "none", "procurement": "read",
        "reports": "read",
    },
    "readonly": {
        "dashboard": "read", "leads": "read", "estimate": "read", "projects": "read",
        "safety": "read", "crm": "read", "documents": "read", "hr": "read",
        "hrms": "read", "playbooks": "read", "user_admin": "none", "procurement": "read",
        "reports": "read",
    },
    "hr_admin": {
        "dashboard": "read", "leads": "read", "estimate": "read", "projects": "read",
        "safety": "read", "crm": "none", "documents": "read", "hr": "admin",
        "hrms": "admin", "playbooks": "read", "user_admin": "none", "procurement": "none",
        "reports": "read",
    },
    "hr_manager": {
        "dashboard": "read", "leads": "none", "estimate": "none", "projects": "none",
        "safety": "read", "crm": "none", "documents": "read", "hr": "write",
        "hrms": "write", "playbooks": "read", "user_admin": "none", "procurement": "none",
        "reports": "none",
    },
    "hr_employee": {
        "dashboard": "read", "leads": "none", "estimate": "none", "projects": "none",
        "safety": "read", "crm": "none", "documents": "read", "hr": "read",
        "hrms": "read", "playbooks": "read", "user_admin": "none", "procurement": "none",
        "reports": "none",
    },
    "executive": {
        "dashboard": "read", "leads": "read", "estimate": "read", "projects": "read",
        "safety": "read", "crm": "read", "documents": "read", "hr": "write",
        "hrms": "write", "playbooks": "read", "user_admin": "none", "procurement": "read",
        "reports": "admin",
    },
}


def upgrade() -> None:
    op.create_table(
        "role_module_permissions",
        sa.Column("role_id", sa.UUID(), nullable=False),
        sa.Column("module_code", sa.String(50), nullable=False),
        sa.Column("access_level", sa.String(20), nullable=False, server_default="none"),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("role_id", "module_code"),
    )
    op.create_index(
        "ix_role_module_permissions_role_id",
        "role_module_permissions",
        ["role_id"],
        unique=False,
    )

    conn = op.get_bind()
    for role_code, perms in _SEED.items():
        for module_code, level in perms.items():
            conn.execute(
                text(
                    """
                    INSERT INTO role_module_permissions (role_id, module_code, access_level)
                    SELECT r.id, :module_code, :access_level
                    FROM roles r
                    WHERE r.code = :role_code
                    ON CONFLICT (role_id, module_code) DO NOTHING
                    """
                ),
                {"role_code": role_code, "module_code": module_code, "access_level": level},
            )


def downgrade() -> None:
    op.drop_index("ix_role_module_permissions_role_id", table_name="role_module_permissions")
    op.drop_table("role_module_permissions")
