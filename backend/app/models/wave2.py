"""Sage CM Wave 2 documents: field, procurement extras, directory, QC."""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import Boolean, Date, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from ..extensions import db
from .base import TimestampMixin, UUIDPKMixin


class Transmittal(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "transmittals"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    number: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    subject: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="draft")
    transmittal_type: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    from_company_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="SET NULL"), nullable=True
    )
    to_company_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="SET NULL"), nullable=True
    )
    issue_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    due_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    items: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)


class PunchlistItem(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "punchlist_items"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    number: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="open")
    location: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    responsible_company_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="SET NULL"), nullable=True
    )
    inspection_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    completed_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    punch_type: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    priority: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    trade: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    reference: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    schedule_impact: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    cost_impact: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    manager_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    final_approver_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    distribution_user_ids: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    attachments: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)


class WorkOrder(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "work_orders"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    number: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    subject: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="open")
    work_order_type: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    issued_to_company_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="SET NULL"), nullable=True
    )
    issue_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    items: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2), nullable=True)


class AnticipatedCost(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "anticipated_costs"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    number: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    subject: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="open")
    cost_code_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rfi_cost_codes.id", ondelete="SET NULL"), nullable=True
    )
    amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2), nullable=True)
    accounted_for: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class PurchaseOrderChangeOrder(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "purchase_order_change_orders"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    commitment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("commitments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    number: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    subject: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="draft")
    status_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    items: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2), nullable=True)
    applied: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    amount_applied: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2), nullable=True)
    line_snapshot: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)


class SubInvoice(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "sub_invoices"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    commitment_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("commitments.id", ondelete="SET NULL"), nullable=True
    )
    number: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    subject: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="draft")
    approved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    invoice_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    period_start: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    period_end: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2), nullable=True)
    retainage: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2), nullable=True)
    retainage_pct: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2), nullable=True)
    this_period: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2), nullable=True)
    previous_to_date: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2), nullable=True)
    amount_due: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    lines: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)


class Meeting(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "meetings"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    number: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    subject: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="scheduled")
    meeting_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    meeting_type: Mapped[Optional[str]] = mapped_column(String(40), nullable=True, default="other")
    start_time: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    end_time: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    location: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    facilitator_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    minutes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    attendees: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    items: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)


class SafetyIncident(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "safety_incidents"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    number: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    subject: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="open")
    incident_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    severity: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    location: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    injuries: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)


class CompanyInsurancePolicy(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "company_insurance_policies"

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    policy_type: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    carrier: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    policy_number: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    expires_on: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    coverage_limit: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class CompanyLicense(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "company_licenses"

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    license_type: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    license_number: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    jurisdiction: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    expires_on: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class IssueCompany(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "issue_companies"
    __table_args__ = (UniqueConstraint("issue_id", "company_id", name="uq_issue_companies_issue_company"),)

    issue_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tracker_issues.id", ondelete="CASCADE"), nullable=False, index=True
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)


class WorkflowAmountRule(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "workflow_amount_rules"

    transaction_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    min_amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False, default=Decimal("0"))
    approver_role: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class QcChecklist(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "qc_checklists"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    number: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    subject: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="open")
    review_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    items: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
