"""SaaS admin v2: send domains, notes, overage, jobs, plan defaults.

Revision ID: 0116_saas_admin_v2
Revises: 0115_saas_admin
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0116_saas_admin_v2"
down_revision: Union[str, Sequence[str], None] = "0115_saas_admin"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.create_table(
        "organization_send_domains",
        sa.Column("id", _UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", _UUID, sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("domain", sa.String(255), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("requested_by_user_id", _UUID, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("reviewed_by_user_id", _UUID, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("organization_id", "domain", name="uq_organization_send_domains_org_domain"),
    )
    op.create_index("ix_organization_send_domains_organization_id", "organization_send_domains", ["organization_id"])

    op.create_table(
        "organization_notes",
        sa.Column("id", _UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", _UUID, sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("actor_user_id", _UUID, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_organization_notes_organization_id", "organization_notes", ["organization_id"])

    op.create_table(
        "organization_seat_overages",
        sa.Column("id", _UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", _UUID, sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("seat_kind", sa.String(20), nullable=False, server_default="office"),
        sa.Column("reason", sa.String(500), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by_user_id", _UUID, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_organization_seat_overages_organization_id", "organization_seat_overages", ["organization_id"])

    op.create_table(
        "platform_jobs",
        sa.Column("id", _UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", _UUID, sa.ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("job_type", sa.String(40), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="queued"),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", _UUID, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("payload_json", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_platform_jobs_organization_id", "platform_jobs", ["organization_id"])

    op.create_table(
        "plan_defaults",
        sa.Column("id", _UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("plan_key", sa.String(20), nullable=False),
        sa.Column("module_key", sa.String(80), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("plan_key", "module_key", name="uq_plan_defaults_plan_module"),
    )


def downgrade() -> None:
    op.drop_table("plan_defaults")
    op.drop_index("ix_platform_jobs_organization_id", table_name="platform_jobs")
    op.drop_table("platform_jobs")
    op.drop_index("ix_organization_seat_overages_organization_id", table_name="organization_seat_overages")
    op.drop_table("organization_seat_overages")
    op.drop_index("ix_organization_notes_organization_id", table_name="organization_notes")
    op.drop_table("organization_notes")
    op.drop_index("ix_organization_send_domains_organization_id", table_name="organization_send_domains")
    op.drop_table("organization_send_domains")
