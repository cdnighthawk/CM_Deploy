"""Project — the central scoping entity for almost every downstream module."""
from __future__ import annotations

import uuid
from datetime import date
from typing import Optional

from sqlalchemy import Boolean, Date, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import ENUM, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..extensions import db
from .base import SoftDeleteMixin, TimestampMixin, UUIDPKMixin

project_status_enum = ENUM(
    "planning",
    "active",
    "on_hold",
    "complete",
    "archived",
    "cancelled",
    name="project_status",
    create_type=True,
)

project_type_enum = ENUM(
    "commercial",
    "government",
    "residential",
    "mixed",
    "other",
    name="project_type",
    create_type=True,
)


class Project(UUIDPKMixin, TimestampMixin, SoftDeleteMixin, db.Model):
    __tablename__ = "projects"

    number: Mapped[Optional[str]] = mapped_column(String(50), unique=True, nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(project_status_enum, nullable=False, default="planning")
    project_type: Mapped[str] = mapped_column(
        project_type_enum, nullable=False, default="commercial"
    )

    gc_company_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="SET NULL"), nullable=True
    )
    owner_company_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="SET NULL"), nullable=True
    )
    architect_company_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="SET NULL"), nullable=True
    )

    address_line1: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    address_line2: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    city: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    state: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    postal_code: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    country: Mapped[Optional[str]] = mapped_column(String(2), nullable=True, default="US")

    contract_value: Mapped[Optional[float]] = mapped_column(Numeric(15, 2), nullable=True)
    contract_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    start_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    substantial_completion_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    closeout_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    retention_percentage: Mapped[Optional[float]] = mapped_column(Numeric(5, 2), nullable=True)

    prevailing_wage: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    dbe_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    sage_project_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    textura_project_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, unique=True, index=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    gc_company = relationship("Company", foreign_keys=[gc_company_id])
    owner_company = relationship("Company", foreign_keys=[owner_company_id])
    architect_company = relationship("Company", foreign_keys=[architect_company_id])

    rfis = relationship("Rfi", back_populates="project", cascade="all, delete-orphan")
    submittals = relationship("Submittal", back_populates="project", cascade="all, delete-orphan")
    commitments = relationship("Commitment", back_populates="project", cascade="all, delete-orphan")
    pay_applications = relationship("PayApplication", back_populates="project", cascade="all, delete-orphan")
    prime_contract_sov_lines = relationship(
        "PrimeContractSovLine",
        back_populates="project",
        cascade="all, delete-orphan",
        order_by="PrimeContractSovLine.sort_order",
    )
    schedule_items = relationship(
        "ProjectScheduleItem",
        back_populates="project",
        cascade="all, delete-orphan",
        order_by="ProjectScheduleItem.sort_order, ProjectScheduleItem.start_date",
    )
