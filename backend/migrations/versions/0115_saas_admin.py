"""SaaS admin: tenant billing fields, settings, flags, audit, impersonation.

Revision ID: 0115_saas_admin
Revises: 0114_mat_supplier
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0115_saas_admin"
down_revision: Union[str, Sequence[str], None] = "0114_mat_supplier"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.add_column("users", sa.Column("is_platform_operator", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.execute("UPDATE users SET is_platform_operator = TRUE WHERE is_superuser = TRUE")

    op.add_column("organizations", sa.Column("legal_name", sa.String(length=255), nullable=True))
    op.add_column("organizations", sa.Column("dba", sa.String(length=255), nullable=True))
    op.add_column("organizations", sa.Column("cslb", sa.String(length=40), nullable=True))
    op.add_column("organizations", sa.Column("fein_last4", sa.String(length=4), nullable=True))
    op.add_column(
        "organizations",
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
    )
    op.add_column(
        "organizations",
        sa.Column("plan_key", sa.String(length=20), nullable=False, server_default="full"),
    )
    op.add_column(
        "organizations",
        sa.Column("seat_cap_office", sa.Integer(), nullable=False, server_default="50"),
    )
    op.add_column(
        "organizations",
        sa.Column("seat_cap_field", sa.Integer(), nullable=False, server_default="50"),
    )
    op.add_column(
        "organizations",
        sa.Column("seat_cap_vendor_token", sa.Integer(), nullable=False, server_default="500"),
    )
    op.add_column("organizations", sa.Column("notes", sa.Text(), nullable=True))
    op.execute("UPDATE organizations SET legal_name = name WHERE legal_name IS NULL")

    op.create_table(
        "tenant_entitlements",
        sa.Column("id", _UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("organization_id", _UUID, nullable=False),
        sa.Column("module_key", sa.String(length=80), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "module_key", name="uq_tenant_entitlements_org_module"),
    )
    op.create_index("ix_tenant_entitlements_organization_id", "tenant_entitlements", ["organization_id"])

    op.create_table(
        "feature_flags",
        sa.Column("id", _UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("key", sa.String(length=120), nullable=False),
        sa.Column("default_on", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("organization_id", _UUID, nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_feature_flags_key", "feature_flags", ["key"])
    op.create_index("ix_feature_flags_organization_id", "feature_flags", ["organization_id"])
    op.create_index(
        "uq_feature_flags_platform_key",
        "feature_flags",
        ["key"],
        unique=True,
        postgresql_where=sa.text("organization_id IS NULL"),
    )
    op.create_index(
        "uq_feature_flags_tenant_key",
        "feature_flags",
        ["key", "organization_id"],
        unique=True,
        postgresql_where=sa.text("organization_id IS NOT NULL"),
    )

    op.create_table(
        "tenant_settings",
        sa.Column("organization_id", _UUID, nullable=False),
        sa.Column("key", sa.String(length=120), nullable=False),
        sa.Column("value_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("updated_by_user_id", _UUID, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("organization_id", "key", name="uq_tenant_settings_org_key"),
    )

    op.create_table(
        "impersonation_sessions",
        sa.Column("id", _UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("operator_user_id", _UUID, nullable=False),
        sa.Column("organization_id", _UUID, nullable=False),
        sa.Column("target_user_id", _UUID, nullable=True),
        sa.Column("reason", sa.String(length=500), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("banner_ack", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.ForeignKeyConstraint(["operator_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_impersonation_sessions_operator_user_id", "impersonation_sessions", ["operator_user_id"])
    op.create_index("ix_impersonation_sessions_organization_id", "impersonation_sessions", ["organization_id"])

    op.create_table(
        "platform_audit",
        sa.Column("id", _UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("actor_user_id", _UUID, nullable=True),
        sa.Column("organization_id", _UUID, nullable=True),
        sa.Column("impersonation_id", _UUID, nullable=True),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("before_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("after_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("user_agent", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["impersonation_id"], ["impersonation_sessions.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_platform_audit_actor_user_id", "platform_audit", ["actor_user_id"])
    op.create_index("ix_platform_audit_organization_id", "platform_audit", ["organization_id"])
    op.create_index("ix_platform_audit_impersonation_id", "platform_audit", ["impersonation_id"])
    op.create_index("ix_platform_audit_action", "platform_audit", ["action"])


def downgrade() -> None:
    op.drop_table("platform_audit")
    op.drop_table("impersonation_sessions")
    op.drop_table("tenant_settings")
    op.drop_index("uq_feature_flags_tenant_key", table_name="feature_flags")
    op.drop_index("uq_feature_flags_platform_key", table_name="feature_flags")
    op.drop_table("feature_flags")
    op.drop_table("tenant_entitlements")
    op.drop_column("organizations", "notes")
    op.drop_column("organizations", "seat_cap_vendor_token")
    op.drop_column("organizations", "seat_cap_field")
    op.drop_column("organizations", "seat_cap_office")
    op.drop_column("organizations", "plan_key")
    op.drop_column("organizations", "status")
    op.drop_column("organizations", "fein_last4")
    op.drop_column("organizations", "cslb")
    op.drop_column("organizations", "dba")
    op.drop_column("organizations", "legal_name")
    op.drop_column("users", "is_platform_operator")
