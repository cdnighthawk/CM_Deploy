"""CM role catalog, module permissions seed, and project_members assignments."""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text

revision: str = "0045_cm_roles_and_project_members"
down_revision: Union[str, Sequence[str], None] = "0044_project_invoice_fields"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_MODULE_CODES = (
    "dashboard",
    "leads",
    "estimate",
    "projects",
    "safety",
    "crm",
    "documents",
    "hr",
    "hrms",
    "playbooks",
    "user_admin",
    "procurement",
    "reports",
)

_CM_ROLES: list[tuple[str, str, str]] = [
    ("admin", "Admin", "Full system access; all projects"),
    ("executive", "Executive", "Company-wide read; reports admin; all projects"),
    ("project_manager", "Project Manager", "Assigned projects; full project tools"),
    ("superintendent", "Superintendent", "Assigned projects; field leadership"),
    ("project_engineer", "Project Engineer", "Assigned projects; technical docs and RFIs"),
    ("estimator", "Estimator", "Assigned projects; leads and estimating"),
    ("project_accountant", "Project Accountant", "Assigned projects; procurement and reports"),
    ("safety_manager", "Safety Manager", "Assigned projects; safety admin"),
    ("office_coordinator", "Office Coordinator", "Assigned projects; CRM and documents"),
    ("field_readonly", "Field (read-only)", "Assigned projects; read-only access"),
]

_CM_PERMISSIONS: dict[str, dict[str, str]] = {
    "admin": {c: "admin" for c in _MODULE_CODES},
    "executive": {
        "dashboard": "read",
        "leads": "read",
        "estimate": "read",
        "projects": "read",
        "safety": "read",
        "crm": "read",
        "documents": "read",
        "hr": "write",
        "hrms": "write",
        "playbooks": "read",
        "user_admin": "none",
        "procurement": "read",
        "reports": "admin",
    },
    "project_manager": {
        "dashboard": "read",
        "leads": "read",
        "estimate": "read",
        "projects": "write",
        "safety": "write",
        "crm": "read",
        "documents": "write",
        "hr": "read",
        "hrms": "read",
        "playbooks": "write",
        "user_admin": "none",
        "procurement": "write",
        "reports": "read",
    },
    "superintendent": {
        "dashboard": "read",
        "leads": "none",
        "estimate": "none",
        "projects": "write",
        "safety": "write",
        "crm": "none",
        "documents": "write",
        "hr": "read",
        "hrms": "read",
        "playbooks": "write",
        "user_admin": "none",
        "procurement": "read",
        "reports": "read",
    },
    "project_engineer": {
        "dashboard": "read",
        "leads": "none",
        "estimate": "read",
        "projects": "write",
        "safety": "read",
        "crm": "none",
        "documents": "write",
        "hr": "read",
        "hrms": "read",
        "playbooks": "read",
        "user_admin": "none",
        "procurement": "read",
        "reports": "read",
    },
    "estimator": {
        "dashboard": "read",
        "leads": "write",
        "estimate": "write",
        "projects": "read",
        "safety": "none",
        "crm": "write",
        "documents": "read",
        "hr": "none",
        "hrms": "none",
        "playbooks": "none",
        "user_admin": "none",
        "procurement": "none",
        "reports": "read",
    },
    "project_accountant": {
        "dashboard": "read",
        "leads": "none",
        "estimate": "none",
        "projects": "read",
        "safety": "none",
        "crm": "none",
        "documents": "read",
        "hr": "none",
        "hrms": "read",
        "playbooks": "none",
        "user_admin": "none",
        "procurement": "write",
        "reports": "write",
    },
    "safety_manager": {
        "dashboard": "read",
        "leads": "none",
        "estimate": "none",
        "projects": "read",
        "safety": "admin",
        "crm": "none",
        "documents": "read",
        "hr": "read",
        "hrms": "read",
        "playbooks": "read",
        "user_admin": "none",
        "procurement": "none",
        "reports": "read",
    },
    "office_coordinator": {
        "dashboard": "read",
        "leads": "read",
        "estimate": "none",
        "projects": "read",
        "safety": "read",
        "crm": "write",
        "documents": "write",
        "hr": "none",
        "hrms": "none",
        "playbooks": "read",
        "user_admin": "none",
        "procurement": "none",
        "reports": "none",
    },
    "field_readonly": {
        "dashboard": "read",
        "leads": "none",
        "estimate": "none",
        "projects": "read",
        "safety": "read",
        "crm": "none",
        "documents": "read",
        "hr": "none",
        "hrms": "none",
        "playbooks": "read",
        "user_admin": "none",
        "procurement": "none",
        "reports": "none",
    },
}


def upgrade() -> None:
    op.create_table(
        "project_members",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("member_role", sa.String(50), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("created_by_id", sa.UUID(), nullable=True),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "project_id"),
        sa.UniqueConstraint("user_id", "project_id", name="uq_project_members_user_project"),
    )
    op.create_index("ix_project_members_project_id", "project_members", ["project_id"], unique=False)
    op.create_index("ix_project_members_user_id", "project_members", ["user_id"], unique=False)

    conn = op.get_bind()
    for code, name, description in _CM_ROLES:
        conn.execute(
            text(
                """
                INSERT INTO roles (id, code, name, description, created_at, updated_at)
                SELECT gen_random_uuid(),
                       CAST(:code AS VARCHAR(50)),
                       CAST(:name AS VARCHAR(120)),
                       CAST(:description AS VARCHAR(500)),
                       now(), now()
                WHERE NOT EXISTS (
                    SELECT 1 FROM roles WHERE code = CAST(:code AS VARCHAR(50))
                )
                """
            ),
            {"code": code, "name": name, "description": description},
        )

    for role_code, perms in _CM_PERMISSIONS.items():
        for module_code, level in perms.items():
            conn.execute(
                text(
                    """
                    INSERT INTO role_module_permissions (role_id, module_code, access_level)
                    SELECT r.id,
                           CAST(:module_code AS VARCHAR(50)),
                           CAST(:access_level AS VARCHAR(20))
                    FROM roles r
                    WHERE r.code = CAST(:role_code AS VARCHAR(50))
                    ON CONFLICT (role_id, module_code) DO UPDATE
                    SET access_level = EXCLUDED.access_level
                    """
                ),
                {"role_code": role_code, "module_code": module_code, "access_level": level},
            )

    conn.execute(
        text(
            """
            UPDATE user_roles ur
            SET role_id = pm.id
            FROM roles std, roles pm
            WHERE ur.role_id = std.id
              AND std.code = 'standard'
              AND pm.code = 'project_manager'
            """
        )
    )
    conn.execute(
        text(
            """
            UPDATE user_roles ur
            SET role_id = fr.id
            FROM roles ro, roles fr
            WHERE ur.role_id = ro.id
              AND ro.code IN ('read_only', 'readonly')
              AND fr.code = 'field_readonly'
            """
        )
    )


def downgrade() -> None:
    op.drop_index("ix_project_members_user_id", table_name="project_members")
    op.drop_index("ix_project_members_project_id", table_name="project_members")
    op.drop_table("project_members")
