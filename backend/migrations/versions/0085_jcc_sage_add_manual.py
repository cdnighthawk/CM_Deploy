"""Sage Add Manually fields on job cost codes.

Revision ID: 0085_jcc_sage
Revises: 0084_wave2_sage
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0085_jcc_sage"
down_revision: Union[str, Sequence[str], None] = "0084_wave2_sage"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_COLS = (
    ("owner_cost_code_desc", sa.String(length=200)),
    ("default_tax_code", sa.String(length=40)),
    ("division_code", sa.String(length=40)),
    ("division_desc", sa.String(length=200)),
    ("major_code", sa.String(length=40)),
    ("major_desc", sa.String(length=200)),
    ("minor_code", sa.String(length=40)),
    ("minor_desc", sa.String(length=200)),
    ("subminor_code", sa.String(length=40)),
    ("subminor_desc", sa.String(length=200)),
    ("workers_comp_code", sa.String(length=40)),
    ("ap_tax_code", sa.String(length=40)),
    ("ar_tax_code", sa.String(length=40)),
)


def upgrade() -> None:
    for name, col in _COLS:
        op.add_column("rfi_cost_codes", sa.Column(name, col, nullable=True))


def downgrade() -> None:
    for name, _col in reversed(_COLS):
        op.drop_column("rfi_cost_codes", name)
