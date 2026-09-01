"""RFP quote mailbox: send audit, inbound Graph ids, bidder links.

Revision ID: 0090_rfp_quote
Revises: 0089_user_act
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0090_rfp_quote"
down_revision: Union[str, Sequence[str], None] = "0089_user_act"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("rfps", sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("rfps", sa.Column("mail_tag", sa.String(length=16), nullable=True))
    op.create_index("ix_rfps_mail_tag", "rfps", ["mail_tag"], unique=True)

    op.add_column(
        "rfp_vendor_quotes",
        sa.Column("vendor_company_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "rfp_vendor_quotes",
        sa.Column("vendor_contact_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column("rfp_vendor_quotes", sa.Column("invited_email", sa.String(length=255), nullable=True))
    op.add_column("rfp_vendor_quotes", sa.Column("invite_token", sa.String(length=64), nullable=True))
    op.add_column("rfp_vendor_quotes", sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("rfp_vendor_quotes", sa.Column("sent_from_mailbox", sa.String(length=255), nullable=True))
    op.add_column(
        "rfp_vendor_quotes",
        sa.Column("source", sa.String(length=20), nullable=False, server_default="invited"),
    )
    op.add_column(
        "rfp_vendor_quotes",
        sa.Column("graph_inbound_message_id", sa.String(length=256), nullable=True),
    )
    op.add_column("rfp_vendor_quotes", sa.Column("from_email", sa.String(length=255), nullable=True))
    op.add_column("rfp_vendor_quotes", sa.Column("from_name", sa.String(length=255), nullable=True))
    op.add_column("rfp_vendor_quotes", sa.Column("subject", sa.String(length=500), nullable=True))
    op.add_column("rfp_vendor_quotes", sa.Column("received_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("rfp_vendor_quotes", sa.Column("mailbox", sa.String(length=255), nullable=True))
    op.add_column(
        "rfp_vendor_quotes",
        sa.Column("attachments", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.create_index("ix_rfp_vendor_quotes_vendor_company_id", "rfp_vendor_quotes", ["vendor_company_id"])
    op.create_index("ix_rfp_vendor_quotes_vendor_contact_id", "rfp_vendor_quotes", ["vendor_contact_id"])
    op.create_index("ix_rfp_vendor_quotes_invited_email", "rfp_vendor_quotes", ["invited_email"])
    op.create_index("ix_rfp_vendor_quotes_invite_token", "rfp_vendor_quotes", ["invite_token"], unique=True)
    op.create_index(
        "ix_rfp_vendor_quotes_graph_inbound_message_id",
        "rfp_vendor_quotes",
        ["graph_inbound_message_id"],
        unique=True,
    )
    op.create_foreign_key(
        "fk_rfp_vendor_quotes_vendor_company_id",
        "rfp_vendor_quotes",
        "companies",
        ["vendor_company_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_rfp_vendor_quotes_vendor_contact_id",
        "rfp_vendor_quotes",
        "contacts",
        ["vendor_contact_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_rfp_vendor_quotes_vendor_contact_id", "rfp_vendor_quotes", type_="foreignkey")
    op.drop_constraint("fk_rfp_vendor_quotes_vendor_company_id", "rfp_vendor_quotes", type_="foreignkey")
    op.drop_index("ix_rfp_vendor_quotes_graph_inbound_message_id", table_name="rfp_vendor_quotes")
    op.drop_index("ix_rfp_vendor_quotes_invite_token", table_name="rfp_vendor_quotes")
    op.drop_index("ix_rfp_vendor_quotes_invited_email", table_name="rfp_vendor_quotes")
    op.drop_index("ix_rfp_vendor_quotes_vendor_contact_id", table_name="rfp_vendor_quotes")
    op.drop_index("ix_rfp_vendor_quotes_vendor_company_id", table_name="rfp_vendor_quotes")
    op.drop_column("rfp_vendor_quotes", "attachments")
    op.drop_column("rfp_vendor_quotes", "mailbox")
    op.drop_column("rfp_vendor_quotes", "received_at")
    op.drop_column("rfp_vendor_quotes", "subject")
    op.drop_column("rfp_vendor_quotes", "from_name")
    op.drop_column("rfp_vendor_quotes", "from_email")
    op.drop_column("rfp_vendor_quotes", "graph_inbound_message_id")
    op.drop_column("rfp_vendor_quotes", "source")
    op.drop_column("rfp_vendor_quotes", "sent_from_mailbox")
    op.drop_column("rfp_vendor_quotes", "sent_at")
    op.drop_column("rfp_vendor_quotes", "invite_token")
    op.drop_column("rfp_vendor_quotes", "invited_email")
    op.drop_column("rfp_vendor_quotes", "vendor_contact_id")
    op.drop_column("rfp_vendor_quotes", "vendor_company_id")
    op.drop_index("ix_rfps_mail_tag", table_name="rfps")
    op.drop_column("rfps", "mail_tag")
    op.drop_column("rfps", "sent_at")
