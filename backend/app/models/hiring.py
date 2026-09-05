"""New-hire packet tables (People → Hiring).

PII (SSN, DOB, bank routing/account) lives here encrypted — never on ``User``
or ``EmployeeTimeProfile``. Link to ``User`` after HR review; do not clone a
second employee directory.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any, Optional

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from ..extensions import db
from .base import TimestampMixin, UUIDPKMixin

HIRE_STAGES = (
    "draft",
    "invite_sent",
    "employee_in_progress",
    "employee_signed",
    "hr_review",
    "i9_section2",
    "ready_for_payroll",
    "payroll_setup",
    "closed",
    "void",
)

I9_ATTESTATIONS = (
    "us_citizen",
    "noncitizen_national",
    "lawful_permanent_resident",
    "alien_authorized_to_work",
)

I9_LISTS = ("A", "B", "C")


class FormTemplate(UUIDPKMixin, TimestampMixin, db.Model):
    """Official (or USIS working-copy) blank + field map. In-flight packets freeze ids."""

    __tablename__ = "form_templates"
    __table_args__ = (UniqueConstraint("key", "edition", name="uq_form_templates_key_edition"),)

    key: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    edition: Mapped[str] = mapped_column(String(80), nullable=False)
    effective_from: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    pdf_blank_path: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    field_map: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    is_frozen_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    uses_official_blank: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    title: Mapped[Optional[str]] = mapped_column(String(240), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class HireCompanySetting(db.Model):
    """Key/value hire settings. Secret values (FEIN, EDD) are Fernet ciphertext."""

    __tablename__ = "hire_company_settings"

    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_secret: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class HirePacket(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "hire_packets"

    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    public_token_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, unique=True, index=True)
    token_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    hire_type: Mapped[str] = mapped_column(String(20), nullable=False, default="new")
    stage: Mapped[str] = mapped_column(String(40), nullable=False, default="draft", index=True)
    workflow_instance_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workflow_instances.id", ondelete="SET NULL"), nullable=True
    )
    start_of_work_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True, index=True)
    job_title: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    employment_class: Mapped[str] = mapped_column(String(40), nullable=False, default="hourly_nonexempt")
    union_status: Mapped[str] = mapped_column(String(20), nullable=False, default="nonunion")
    union_local_name: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    wage_order: Mapped[str] = mapped_column(String(8), nullable=False, default="16")
    work_state: Mapped[str] = mapped_column(String(2), nullable=False, default="CA")
    drives_for_work: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    requires_e_verify: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    show_rate_on_packet: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    pay_rate_display: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    pay_frequency: Mapped[str] = mapped_column(String(20), nullable=False, default="weekly")
    primary_project_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="SET NULL"), nullable=True
    )
    offer_letter_file_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="SET NULL"), nullable=True
    )
    form_pack_version_id: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    form_template_ids: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    workflow_definition_version: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    invite_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    invited_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    employee_signed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    locked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    voided_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    void_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    send_back_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    wizard_step: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    pay_by_check: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    i9_section2_scheduled_at: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    de34_filed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    de34_confirmation: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    qb_created_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    qb_list_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    owner_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    person: Mapped[Optional["HirePerson"]] = relationship(
        back_populates="packet", uselist=False, cascade="all, delete-orphan"
    )
    i9: Mapped[Optional["HireI9"]] = relationship(
        back_populates="packet", uselist=False, cascade="all, delete-orphan"
    )
    direct_deposit: Mapped[Optional["HireDirectDeposit"]] = relationship(
        back_populates="packet", uselist=False, cascade="all, delete-orphan"
    )
    tax_elections: Mapped[list["HireTaxElection"]] = relationship(
        back_populates="packet", cascade="all, delete-orphan"
    )
    emergency_contacts: Mapped[list["HireEmergencyContact"]] = relationship(
        back_populates="packet", cascade="all, delete-orphan", order_by="HireEmergencyContact.sort_order"
    )
    notice_acks: Mapped[list["HireNoticeAck"]] = relationship(
        back_populates="packet", cascade="all, delete-orphan"
    )
    signatures: Mapped[list["HireSignature"]] = relationship(
        back_populates="packet", cascade="all, delete-orphan"
    )
    artifacts: Mapped[list["HireArtifact"]] = relationship(
        back_populates="packet", cascade="all, delete-orphan"
    )


class HirePerson(UUIDPKMixin, TimestampMixin, db.Model):
    """1:1 identity on the packet. Encrypted SSN + DOB."""

    __tablename__ = "hire_people"
    __table_args__ = (UniqueConstraint("packet_id", name="uq_hire_people_packet"),)

    packet_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("hire_packets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    legal_first: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    legal_middle: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    legal_last: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    legal_suffix: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    preferred_name: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    dob_ciphertext: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ssn_ciphertext: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ssn_last4: Mapped[Optional[str]] = mapped_column(String(4), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    mobile: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    address1: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    address2: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    city: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    state: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    zip: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    county: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    mailing_same_as_residential: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    mailing_address1: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    mailing_city: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    mailing_state: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    mailing_zip: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    dl_number: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    dl_state: Mapped[Optional[str]] = mapped_column(String(2), nullable=True)
    last_company: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    referred_by: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    packet: Mapped["HirePacket"] = relationship(back_populates="person")


class HireTaxElection(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "hire_tax_elections"
    __table_args__ = (UniqueConstraint("packet_id", "form_key", "version", name="uq_hire_tax_elections_form_ver"),)

    packet_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("hire_packets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    form_key: Mapped[str] = mapped_column(String(20), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    template_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("form_templates.id", ondelete="SET NULL"), nullable=True
    )
    fields: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    signed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    pdf_artifact_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("hire_artifacts.id", ondelete="SET NULL"), nullable=True
    )

    packet: Mapped["HirePacket"] = relationship(back_populates="tax_elections")


class HireI9(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "hire_i9s"
    __table_args__ = (UniqueConstraint("packet_id", name="uq_hire_i9s_packet"),)

    packet_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("hire_packets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    attestation: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    uscis_a_number: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    i94_number: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    foreign_passport_number: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    foreign_passport_country: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    work_until: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    section1_signed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    first_day_of_employment: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    additional_information: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    examiner_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    examiner_title: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    examiner_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    employer_business_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    employer_address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    section2_signed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    section2_late: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    document_list_mode: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)

    packet: Mapped["HirePacket"] = relationship(back_populates="i9")
    documents: Mapped[list["HireI9Document"]] = relationship(
        back_populates="i9", cascade="all, delete-orphan"
    )


class HireI9Document(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "hire_i9_documents"

    i9_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("hire_i9s.id", ondelete="CASCADE"), nullable=False, index=True
    )
    list_kind: Mapped[str] = mapped_column(String(1), nullable=False)
    document_title: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    issuing_authority: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    document_number: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    expiration: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    expiration_na: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    copy_storage_name: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    original_filename: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    mime_type: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    preset_key: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)

    i9: Mapped["HireI9"] = relationship(back_populates="documents")


class HireDirectDeposit(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "hire_direct_deposits"
    __table_args__ = (UniqueConstraint("packet_id", name="uq_hire_direct_deposits_packet"),)

    packet_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("hire_packets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    bank_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    routing_ciphertext: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    account_ciphertext: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    account_last4: Mapped[Optional[str]] = mapped_column(String(4), nullable=True)
    account_type: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    account_holder_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    signed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    voided_check_storage_name: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    voided_check_filename: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    packet: Mapped["HirePacket"] = relationship(back_populates="direct_deposit")


class HireEmergencyContact(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "hire_emergency_contacts"

    packet_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("hire_packets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    relation: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    packet: Mapped["HirePacket"] = relationship(back_populates="emergency_contacts")


class HireNoticeAck(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "hire_notice_acks"
    __table_args__ = (UniqueConstraint("packet_id", "notice_key", name="uq_hire_notice_acks_key"),)

    packet_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("hire_packets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    notice_key: Mapped[str] = mapped_column(String(80), nullable=False)
    template_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("form_templates.id", ondelete="SET NULL"), nullable=True
    )
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    packet: Mapped["HirePacket"] = relationship(back_populates="notice_acks")


class HireSignature(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "hire_signatures"

    packet_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("hire_packets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    artifact_key: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    typed_legal_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    signature_png: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    signed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    timezone_display: Mapped[str] = mapped_column(String(64), nullable=False, default="America/Los_Angeles")
    source_ip: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    form_template_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("form_templates.id", ondelete="SET NULL"), nullable=True
    )
    pdf_sha256: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    certification_checked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    packet: Mapped["HirePacket"] = relationship(back_populates="signatures")


class HireArtifact(UUIDPKMixin, TimestampMixin, db.Model):
    """Stored draft/signed PDFs and payroll exports under hr/hires/<packet_id>/."""

    __tablename__ = "hire_artifacts"

    packet_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("hire_packets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    artifact_key: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    is_draft: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sha256: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    storage_name: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    original_filename: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    mime_type: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    file_size_bytes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    packet: Mapped["HirePacket"] = relationship(back_populates="artifacts")
