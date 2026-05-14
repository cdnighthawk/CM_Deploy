"""Optional PDF URL per RFI spec section (specs book viewer).

Revision ID: 0028_spec_section_pdf_url
Revises: 0027_prime_contract_sov
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0028_spec_section_pdf_url"
down_revision: Union[str, Sequence[str], None] = "0027_prime_contract_sov"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "rfi_spec_sections",
        sa.Column("pdf_url", sa.String(length=1024), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("rfi_spec_sections", "pdf_url")
