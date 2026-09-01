"""RFP drawing B2 snapshot keys and zip status.

Revision ID: 0093_rfp_b2
Revises: 0092_rfp_body
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0093_rfp_b2"
down_revision: Union[str, Sequence[str], None] = "0092_rfp_body"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("rfp_drawings", sa.Column("b2_bucket", sa.String(length=120), nullable=True))
    op.add_column("rfp_drawings", sa.Column("b2_key", sa.String(length=700), nullable=True))
    op.add_column("rfp_drawings", sa.Column("sha256", sa.String(length=64), nullable=True))
    op.add_column("rfp_drawings", sa.Column("bytes", sa.Integer(), nullable=True))
    op.add_column("rfp_drawings", sa.Column("content_type", sa.String(length=120), nullable=True))
    op.add_column("rfp_drawings", sa.Column("original_filename", sa.String(length=500), nullable=True))
    op.add_column("rfp_drawings", sa.Column("send_batch", sa.String(length=64), nullable=True))
    op.create_index("ix_rfp_drawings_send_batch", "rfp_drawings", ["send_batch"])

    op.add_column("rfps", sa.Column("last_send_batch", sa.String(length=64), nullable=True))
    op.add_column("rfps", sa.Column("files_zip_status", sa.String(length=20), nullable=True))
    op.add_column("rfps", sa.Column("files_zip_key", sa.String(length=700), nullable=True))
    op.add_column("rfps", sa.Column("files_zip_bytes", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("rfps", "files_zip_bytes")
    op.drop_column("rfps", "files_zip_key")
    op.drop_column("rfps", "files_zip_status")
    op.drop_column("rfps", "last_send_batch")

    op.drop_index("ix_rfp_drawings_send_batch", table_name="rfp_drawings")
    op.drop_column("rfp_drawings", "send_batch")
    op.drop_column("rfp_drawings", "original_filename")
    op.drop_column("rfp_drawings", "content_type")
    op.drop_column("rfp_drawings", "bytes")
    op.drop_column("rfp_drawings", "sha256")
    op.drop_column("rfp_drawings", "b2_key")
    op.drop_column("rfp_drawings", "b2_bucket")
