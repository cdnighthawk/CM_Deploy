"""Automation JSON on workflow steps + first-pass process seeds.

Revision ID: 0078_ai_wf
Revises: 0077_corr_po
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0078_ai_wf"
down_revision: Union[str, Sequence[str], None] = "0077_corr_po"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("workflow_definition_steps", sa.Column("automation", postgresql.JSONB(), nullable=True))
    op.add_column("workflow_instance_steps", sa.Column("automation", postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("workflow_instance_steps", "automation")
    op.drop_column("workflow_definition_steps", "automation")
