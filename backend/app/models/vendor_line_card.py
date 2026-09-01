"""Vendor line card: which CSI sections a company covers and which brands they sell."""
from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..extensions import db
from .base import TimestampMixin, UUIDPKMixin

if TYPE_CHECKING:
    from .company import Company

SUPPLY_ROLES = ("manufacturer", "distributor", "both")
BUY_FROM = ("manufacturer", "distributor")


class CsiBuyChannel(UUIDPKMixin, TimestampMixin, db.Model):
    """How USIS buys a CSI section: direct from the manufacturer, or through a distributor."""

    __tablename__ = "csi_buy_channels"
    __table_args__ = (UniqueConstraint("csi_spec_section", name="uq_csi_buy_channels_section"),)

    csi_spec_section: Mapped[str] = mapped_column(String(6), nullable=False, index=True)
    buy_from: Mapped[str] = mapped_column(String(20), nullable=False)


class VendorLineCard(UUIDPKMixin, TimestampMixin, db.Model):
    """One row per company + CSI section + optional manufacturer brand.

    Empty ``manufacturer`` means the company covers the spec without listing brands.
    Once brands are listed, only those brands are sold for that spec.
    """

    __tablename__ = "vendor_line_cards"
    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "csi_spec_section",
            "manufacturer",
            name="uq_vendor_line_cards_company_csi_mfr",
        ),
    )

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    csi_spec_section: Mapped[str] = mapped_column(String(6), nullable=False, index=True)
    manufacturer: Mapped[str] = mapped_column(String(120), nullable=False, default="", server_default="")

    company: Mapped[Optional["Company"]] = relationship()
