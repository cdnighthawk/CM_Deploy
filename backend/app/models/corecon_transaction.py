"""Corecon ERP transaction-details export.

One row per transaction line item. Seven different ``TransactionSource``
values feed this table (Bill, Bill No PO, CO, PO, Prime Contract,
Prime Invoice, Prime Invoice Retainage); the source is preserved on each
row and is part of the natural key.

The natural / upsert key is
``(transaction_source, transaction_corecon_id, transaction_item_corecon_id)``.

All ``*_corecon_id`` columns are Corecon's own integer IDs (NOT FKs to our
own tables). Dates ending in ``_utc`` are timezone-aware UTC; dates ending
in ``_org_local`` are naive wall-clock as the user saw them. .NET's
``01/01/0001 00:00:00`` sentinel is mapped to NULL by the loader.

``active_project_external_id`` matches ``LeadEstimate.external_id`` for rows
imported from ``active project.csv`` (see ``app.corecon_ids``).
"""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..extensions import db
from .base import TimestampMixin, UUIDPKMixin


class CoreconTransaction(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "corecon_transactions"
    __table_args__ = (
        UniqueConstraint(
            "transaction_source",
            "transaction_corecon_id",
            "transaction_item_corecon_id",
            name="uq_corecon_transactions_source_txn_item",
        ),
    )

    # --- our meta ---------------------------------------------------------
    project_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Shared job UID. Many corecon_transactions rows point at one project.",
    )
    project = relationship("Project", foreign_keys=[project_id])

    active_project_external_id: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
        index=True,
        comment="Same as lead_estimates.external_id for CORECON active-project rows.",
    )

    source_file: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    raw_row: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)

    # --- Corecon "row" header (this Id column is always blank in samples)
    corecon_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, comment="CSV Id")

    transaction_item_source: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    transaction_source: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    transaction_category_level_1: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    transaction_category_level_2: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    transaction_category_level_3: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)

    # --- Project (Corecon) -----------------------------------------------
    project_corecon_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    project_number: Mapped[Optional[str]] = mapped_column(String(60), nullable=True, index=True)
    project_title: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    project_pm_contact_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    project_bid_contact_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    project_sales_contact_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    project_est_start_date_utc: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    project_est_finish_date_utc: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    prime_contract_est_finish_date_incl_co_days_utc: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    project_est_start_date_org_local: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=False), nullable=True
    )
    project_est_finish_date_org_local: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=False), nullable=True
    )
    prime_contract_est_finish_date_incl_co_days_org_local: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=False), nullable=True
    )

    # --- Prime Contract --------------------------------------------------
    prime_contract_corecon_id: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, index=True
    )
    prime_contract_number: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    prime_contract_subject: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    prime_contract_billing_type: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    prime_contract_billing_type_value: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    prime_contract_issue_date_utc: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    prime_contract_issue_date_org_local: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=False), nullable=True
    )
    prime_contract_approval_date_utc: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    prime_contract_approval_date_org_local: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=False), nullable=True
    )
    owner_company_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    owner_contact: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    prime_company_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    prime_contact: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    prime_contract_status: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    prime_contract_est_start_date_utc: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    prime_contract_est_finish_date_utc: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    prime_contract_est_start_date_org_local: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=False), nullable=True
    )
    prime_contract_est_finish_date_org_local: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=False), nullable=True
    )
    prime_contract_change_order_impact_days: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True
    )

    # --- Change Order ----------------------------------------------------
    co_corecon_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    co_number: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    co_subject: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    co_issue_date_utc: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    co_issue_date_org_local: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=False), nullable=True
    )
    co_status_date_utc: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    co_status_date_org_local: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=False), nullable=True
    )

    # --- Work Order ------------------------------------------------------
    work_order_corecon_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    work_order_number: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    work_order_subject: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    work_order_issue_date_utc: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    work_order_issue_date_org_local: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=False), nullable=True
    )
    work_order_status_date_utc: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    work_order_status_date_org_local: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=False), nullable=True
    )

    # --- Job Cost Code ---------------------------------------------------
    job_cost_code_corecon_id: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, index=True
    )
    job_cost_code_order_number: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    job_cost_code: Mapped[Optional[str]] = mapped_column(String(60), nullable=True, index=True)
    job_cost_code_description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    job_cost_code_quantity: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(15, 4), nullable=True
    )
    job_cost_code_unit: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    job_cost_code_internal_division: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    job_cost_code_internal_division_desc: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    job_cost_code_internal_major: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    job_cost_code_internal_major_desc: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    job_cost_code_internal_minor: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    job_cost_code_internal_minor_desc: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    job_cost_code_internal_sub_minor: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    job_cost_code_internal_sub_minor_desc: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    owner_cost_code: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    owner_cost_code_description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # --- Transaction header ---------------------------------------------
    transaction_corecon_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    transaction_number: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    transaction_subject: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    transaction_type: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    transaction_status: Mapped[Optional[str]] = mapped_column(String(60), nullable=True, index=True)
    transaction_date_utc: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    transaction_date_org_local: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=False), nullable=True
    )
    transaction_company_corecon_id: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, index=True
    )
    transaction_company_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    transaction_company_code: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    transaction_contact_corecon_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    transaction_contact: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    transaction_export_status: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    transaction_export_id: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    transaction_export_date_utc: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    transaction_export_date_org_local: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=False), nullable=True
    )
    transaction_payment_amount: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(15, 2), nullable=True
    )

    # --- Transaction Item (line) -----------------------------------------
    transaction_item_corecon_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    transaction_item_order_number: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    transaction_item_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    transaction_item_quantity: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(15, 4), nullable=True
    )
    transaction_item_unit: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    transaction_item_unit_price: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(15, 4), nullable=True
    )
    transaction_item_unit_price_2: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(15, 4), nullable=True
    )
    transaction_item_gross_total: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(15, 2), nullable=True
    )
    transaction_item_subtotal: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(15, 2), nullable=True
    )
    transaction_item_subtotal_2: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(15, 2), nullable=True
    )
    transaction_item_tax_id: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    transaction_item_tax_total: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(15, 2), nullable=True
    )
    transaction_item_total: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(15, 2), nullable=True
    )
    transaction_item_invoiced_total: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(15, 2), nullable=True
    )
    transaction_invoiced_date_utc: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    transaction_invoiced_date_org_local: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=False), nullable=True
    )
    transaction_item_resource_type: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    transaction_item_billable_status: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    transaction_start_date_utc: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    transaction_start_date_org_local: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=False), nullable=True
    )
    transaction_finish_date_utc: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    transaction_finish_date_org_local: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=False), nullable=True
    )
    transaction_project_multiplier: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(15, 6), nullable=True
    )
    transaction_org_multiplier: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(15, 6), nullable=True
    )
    transaction_item_created_utc: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    transaction_item_modified_utc: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
