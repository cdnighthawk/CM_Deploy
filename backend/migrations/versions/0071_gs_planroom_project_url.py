"""Store per-project Online Plan Service URLs on Golden State leads.

Revision ID: 0071_gs_planroom_project_url
Revises: 0070_golden_state_planroom_leads
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0071_gs_planroom_project_url"
down_revision: Union[str, Sequence[str], None] = "0070_golden_state_planroom_leads"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    cols = {c["name"] for c in insp.get_columns("golden_state_planroom_leads")}
    if "project_url" not in cols:
        op.add_column(
            "golden_state_planroom_leads",
            sa.Column("project_url", sa.String(length=500), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    cols = {c["name"] for c in insp.get_columns("golden_state_planroom_leads")}
    if "project_url" in cols:
        op.drop_column("golden_state_planroom_leads", "project_url")
