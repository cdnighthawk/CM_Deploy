"""Takeoff lines may be project-scoped without a lead_estimate row."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0016_takeoff_project_scope"
down_revision = "0015_lead_crm_stage"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        "takeoff_line_items",
        "lead_estimate_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=True,
    )
    op.create_check_constraint(
        "ck_takeoff_line_items_scope",
        "takeoff_line_items",
        "lead_estimate_id IS NOT NULL OR project_id IS NOT NULL",
    )


def downgrade():
    op.drop_constraint("ck_takeoff_line_items_scope", "takeoff_line_items", type_="check")
    op.alter_column(
        "takeoff_line_items",
        "lead_estimate_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=False,
    )
