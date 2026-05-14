"""Companies (GCs, owners, architects, subs, vendors, USIS itself) and their contacts."""
from __future__ import annotations

import uuid
from typing import List, Optional

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import ENUM, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..extensions import db
from .base import SoftDeleteMixin, TimestampMixin, UUIDPKMixin

company_type_enum = ENUM(
    "gc",
    "owner",
    "architect",
    "engineer",
    "subcontractor",
    "vendor",
    "self",
    "other",
    name="company_type",
    create_type=True,
)


class Company(UUIDPKMixin, TimestampMixin, SoftDeleteMixin, db.Model):
    __tablename__ = "companies"

    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    company_type: Mapped[str] = mapped_column(company_type_enum, nullable=False, index=True)
    trade_specialties: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    tax_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    website: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    address_line1: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    address_line2: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    city: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    state: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    postal_code: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    country: Mapped[Optional[str]] = mapped_column(String(2), nullable=True, default="US")
    dbe_certified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    prevailing_wage: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    portal_access_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    performance_score: Mapped[Optional[int]] = mapped_column(nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    contacts: Mapped[List["Contact"]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )


class Contact(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "contacts"

    company_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    first_name: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    last_name: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    title: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    mobile: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    company: Mapped[Optional["Company"]] = relationship(back_populates="contacts")
