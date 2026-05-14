"""Add CRM pipeline stage and optional links on lead_estimates."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0015_lead_crm_stage"
down_revision = "0014_submittal_procore_expand"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "lead_estimates",
        sa.Column(
            "crm_stage",
            sa.String(length=80),
            nullable=False,
            server_default="New Lead",
        ),
    )
    op.add_column(
        "lead_estimates",
        sa.Column("primary_estimate_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "lead_estimates",
        sa.Column("primary_rfp_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index("ix_lead_estimates_crm_stage", "lead_estimates", ["crm_stage"], unique=False)


def downgrade():
    op.drop_index("ix_lead_estimates_crm_stage", table_name="lead_estimates")
    op.drop_column("lead_estimates", "primary_rfp_id")
    op.drop_column("lead_estimates", "primary_estimate_id")
    op.drop_column("lead_estimates", "crm_stage")
