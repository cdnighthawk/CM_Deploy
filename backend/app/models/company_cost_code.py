"""Firm-wide master cost codes. Project job codes are copies seeded from takeoff."""
from __future__ import annotations

from typing import Optional

from sqlalchemy import Boolean, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from ..extensions import db
from .base import TimestampMixin, UUIDPKMixin


class CompanyCostCode(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "company_cost_codes"
    __table_args__ = (UniqueConstraint("code", name="uq_company_cost_codes_code"),)

    code: Mapped[str] = mapped_column(String(60), nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    order_number: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    units: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    owner_cost_code: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    owner_cost_code_desc: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    default_tax_code: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    division_code: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    division_desc: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    major_code: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    major_desc: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    minor_code: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    minor_desc: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    subminor_code: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    subminor_desc: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    workers_comp_code: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    ap_tax_code: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    ar_tax_code: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
