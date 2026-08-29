"""Store Online Plan Service project-detail payload on Golden State leads.

Revision ID: 0072_gs_planroom_detail
Revises: 0071_gs_planroom_project_url
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0072_gs_planroom_detail"
down_revision: Union[str, Sequence[str], None] = "0071_gs_planroom_project_url"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    cols = {c["name"] for c in insp.get_columns("golden_state_planroom_leads")}
    if "detail" not in cols:
        op.add_column(
            "golden_state_planroom_leads",
            sa.Column("detail", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        )
    if "details_fetched_at" not in cols:
        op.add_column(
            "golden_state_planroom_leads",
            sa.Column("details_fetched_at", sa.DateTime(timezone=True), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    cols = {c["name"] for c in insp.get_columns("golden_state_planroom_leads")}
    if "details_fetched_at" in cols:
        op.drop_column("golden_state_planroom_leads", "details_fetched_at")
    if "detail" in cols:
        op.drop_column("golden_state_planroom_leads", "detail")
