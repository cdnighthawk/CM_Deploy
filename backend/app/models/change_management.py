"""Owner CPR/CO and subcontract change orders (Sage CM Wave 1)."""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, Date, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..extensions import db
from .base import TimestampMixin, UUIDPKMixin

if TYPE_CHECKING:
    from .auth import User
    from .commitment import Commitment
    from .company import Company
    from .project import Project
    from .project_contract import ProjectContract
    from .rfi_lookups import CostCode

CHANGE_STATUSES = ("draft", "pending_submission", "pending", "not_approved", "approved")
CPR_STATUSES = (
    "draft",
    "submitted",
    "under_review",
    "accepted",
    "rejected",
    "converted",
    "void",
    "pending_submission",
    "pending",
    "not_approved",
    "approved",
)
PRIME_CO_STATUSES = ("draft", "submitted", "approved", "void", "pending_submission", "pending", "not_approved")
SCO_STATUSES = ("draft", "issued", "approved", "void", "pending_submission", "pending", "not_approved")


class ChangeProposalRequest(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "change_proposal_requests"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    prime_contract_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("project_contracts.id", ondelete="SET NULL"), nullable=True
    )
    number: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    subject: Mapped[str] = mapped_column(String(500), nullable=False, default="", server_default="")
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="draft", server_default="draft")
    status_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    issue_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    response_due_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    impacted_company_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="SET NULL"), nullable=True
    )
    origin: Mapped[Optional[str]] = mapped_column(String(40), nullable=True, default="other", server_default="other")
    source_tm_ticket_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    source_rfi_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rfis.id", ondelete="SET NULL"), nullable=True
    )
    schedule_impact_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    project: Mapped["Project"] = relationship("Project")
    impacted_company: Mapped[Optional["Company"]] = relationship("Company", foreign_keys=[impacted_company_id])
    items: Mapped[List["ChangeProposalRequestItem"]] = relationship(
        back_populates="cpr", cascade="all, delete-orphan", order_by="ChangeProposalRequestItem.sort_order"
    )


class ChangeProposalRequestItem(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "change_proposal_request_items"

    cpr_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("change_proposal_requests.id", ondelete="CASCADE"), nullable=False, index=True
    )
    cost_code_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rfi_cost_codes.id", ondelete="SET NULL"), nullable=True
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    description: Mapped[str] = mapped_column(String(500), nullable=False, default="", server_default="")
    quantity: Mapped[Decimal] = mapped_column(Numeric(15, 4), nullable=False, default=Decimal("0"))
    unit: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(15, 4), nullable=False, default=Decimal("0"))
    line_total: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False, default=Decimal("0"))
    resource: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)

    cpr: Mapped["ChangeProposalRequest"] = relationship("ChangeProposalRequest", back_populates="items")
    cost_code: Mapped[Optional["CostCode"]] = relationship("CostCode")


class OwnerChangeOrder(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "owner_change_orders"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    prime_contract_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("project_contracts.id", ondelete="SET NULL"), nullable=True
    )
    cpr_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("change_proposal_requests.id", ondelete="SET NULL"), nullable=True
    )
    number: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    subject: Mapped[str] = mapped_column(String(500), nullable=False, default="", server_default="")
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="draft", server_default="draft")
    status_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    issue_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    schedule_impact_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    approved_revises_contract: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    contract_value_applied: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2), nullable=True)
    source_tm_ticket_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    gc_company_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="SET NULL"), nullable=True
    )
    created_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    project: Mapped["Project"] = relationship("Project")
    prime_contract: Mapped[Optional["ProjectContract"]] = relationship("ProjectContract")
    items: Mapped[List["OwnerChangeOrderItem"]] = relationship(
        back_populates="change_order",
        cascade="all, delete-orphan",
        order_by="OwnerChangeOrderItem.sort_order",
    )


class OwnerChangeOrderItem(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "owner_change_order_items"

    change_order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("owner_change_orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    cost_code_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rfi_cost_codes.id", ondelete="SET NULL"), nullable=True
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    description: Mapped[str] = mapped_column(String(500), nullable=False, default="", server_default="")
    quantity: Mapped[Decimal] = mapped_column(Numeric(15, 4), nullable=False, default=Decimal("0"))
    unit: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(15, 4), nullable=False, default=Decimal("0"))
    line_total: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False, default=Decimal("0"))
    resource: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)

    change_order: Mapped["OwnerChangeOrder"] = relationship("OwnerChangeOrder", back_populates="items")
    cost_code: Mapped[Optional["CostCode"]] = relationship("CostCode")


class SubcontractChangeOrder(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "subcontract_change_orders"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    commitment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("commitments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    number: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    subject: Mapped[str] = mapped_column(String(500), nullable=False, default="", server_default="")
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="draft", server_default="draft")
    status_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    issue_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    value_applied: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2), nullable=True)
    created_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    project: Mapped["Project"] = relationship("Project")
    commitment: Mapped["Commitment"] = relationship("Commitment")
    items: Mapped[List["SubcontractChangeOrderItem"]] = relationship(
        back_populates="sco", cascade="all, delete-orphan", order_by="SubcontractChangeOrderItem.sort_order"
    )


class SubcontractChangeOrderItem(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "subcontract_change_order_items"

    sco_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("subcontract_change_orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    cost_code_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rfi_cost_codes.id", ondelete="SET NULL"), nullable=True
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    description: Mapped[str] = mapped_column(String(500), nullable=False, default="", server_default="")
    quantity: Mapped[Decimal] = mapped_column(Numeric(15, 4), nullable=False, default=Decimal("0"))
    unit: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(15, 4), nullable=False, default=Decimal("0"))
    line_total: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False, default=Decimal("0"))
    resource: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)

    sco: Mapped["SubcontractChangeOrder"] = relationship("SubcontractChangeOrder", back_populates="items")
    cost_code: Mapped[Optional["CostCode"]] = relationship("CostCode")
