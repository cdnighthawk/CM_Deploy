"""Hire packets, form templates, and encrypted PII tables.

Revision ID: 0103_hiring
Revises: 0102_field_punch
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0103_hiring"
down_revision: Union[str, Sequence[str], None] = "0102_field_punch"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = set(insp.get_table_names())

    if "form_templates" not in tables:
        op.create_table(
            "form_templates",
            sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("key", sa.String(80), nullable=False),
            sa.Column("edition", sa.String(80), nullable=False),
            sa.Column("effective_from", sa.Date(), nullable=True),
            sa.Column("pdf_blank_path", sa.String(1024), nullable=True),
            sa.Column("field_map", postgresql.JSONB(), nullable=True),
            sa.Column("is_frozen_default", sa.Boolean(), server_default="false", nullable=False),
            sa.Column("uses_official_blank", sa.Boolean(), server_default="false", nullable=False),
            sa.Column("title", sa.String(240), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("key", "edition", name="uq_form_templates_key_edition"),
        )
        op.create_index("ix_form_templates_key", "form_templates", ["key"])

    if "hire_company_settings" not in tables:
        op.create_table(
            "hire_company_settings",
            sa.Column("key", sa.String(80), nullable=False),
            sa.Column("value_text", sa.Text(), nullable=True),
            sa.Column("is_secret", sa.Boolean(), server_default="false", nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.PrimaryKeyConstraint("key"),
        )

    if "hire_packets" not in tables:
        op.create_table(
            "hire_packets",
            sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("public_token_hash", sa.String(64), nullable=True),
            sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("hire_type", sa.String(20), nullable=False, server_default="new"),
            sa.Column("stage", sa.String(40), nullable=False, server_default="draft"),
            sa.Column("workflow_instance_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("start_of_work_date", sa.Date(), nullable=True),
            sa.Column("job_title", sa.String(200), nullable=True),
            sa.Column("employment_class", sa.String(40), nullable=False, server_default="hourly_nonexempt"),
            sa.Column("union_status", sa.String(20), nullable=False, server_default="nonunion"),
            sa.Column("union_local_name", sa.String(120), nullable=True),
            sa.Column("wage_order", sa.String(8), nullable=False, server_default="16"),
            sa.Column("work_state", sa.String(2), nullable=False, server_default="CA"),
            sa.Column("drives_for_work", sa.Boolean(), server_default="false", nullable=False),
            sa.Column("requires_e_verify", sa.Boolean(), server_default="false", nullable=False),
            sa.Column("show_rate_on_packet", sa.Boolean(), server_default="false", nullable=False),
            sa.Column("pay_rate_display", sa.String(80), nullable=True),
            sa.Column("pay_frequency", sa.String(20), nullable=False, server_default="weekly"),
            sa.Column("primary_project_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("offer_letter_file_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("form_pack_version_id", sa.String(80), nullable=True),
            sa.Column("form_template_ids", postgresql.JSONB(), nullable=True),
            sa.Column("workflow_definition_version", sa.Integer(), nullable=True),
            sa.Column("invite_email", sa.String(255), nullable=True),
            sa.Column("invited_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("employee_signed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("voided_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("void_reason", sa.Text(), nullable=True),
            sa.Column("send_back_note", sa.Text(), nullable=True),
            sa.Column("wizard_step", sa.Integer(), server_default="1", nullable=False),
            sa.Column("pay_by_check", sa.Boolean(), server_default="false", nullable=False),
            sa.Column("i9_section2_scheduled_at", sa.Date(), nullable=True),
            sa.Column("de34_filed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("de34_confirmation", sa.String(80), nullable=True),
            sa.Column("qb_created_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("qb_list_id", sa.String(64), nullable=True),
            sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("owner_user_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["workflow_instance_id"], ["workflow_instances.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["primary_project_id"], ["projects.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["offer_letter_file_id"], ["documents.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_hire_packets_stage", "hire_packets", ["stage"])
        op.create_index("ix_hire_packets_start", "hire_packets", ["start_of_work_date"])
        op.create_index("ix_hire_packets_user_id", "hire_packets", ["user_id"])
        op.create_index("ix_hire_packets_invite_email", "hire_packets", ["invite_email"])
        op.create_index("ix_hire_packets_token_hash", "hire_packets", ["public_token_hash"], unique=True)

    def _child(name, cols, fks=None, uniques=None, indexes=None):
        if name in tables:
            return
        args = [
            sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            *cols,
            sa.PrimaryKeyConstraint("id"),
        ]
        for fk in fks or []:
            args.append(sa.ForeignKeyConstraint(*fk[:2], ondelete=fk[2] if len(fk) > 2 else "CASCADE"))
        for uq in uniques or []:
            args.append(sa.UniqueConstraint(*uq[0], name=uq[1]))
        op.create_table(name, *args)
        for ix in indexes or []:
            op.create_index(ix[0], name, ix[1], unique=ix[2] if len(ix) > 2 else False)

    _child(
        "hire_people",
        [
            sa.Column("packet_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("legal_first", sa.String(120), nullable=True),
            sa.Column("legal_middle", sa.String(120), nullable=True),
            sa.Column("legal_last", sa.String(120), nullable=True),
            sa.Column("legal_suffix", sa.String(40), nullable=True),
            sa.Column("preferred_name", sa.String(120), nullable=True),
            sa.Column("dob_ciphertext", sa.Text(), nullable=True),
            sa.Column("ssn_ciphertext", sa.Text(), nullable=True),
            sa.Column("ssn_last4", sa.String(4), nullable=True),
            sa.Column("email", sa.String(255), nullable=True),
            sa.Column("mobile", sa.String(50), nullable=True),
            sa.Column("address1", sa.String(255), nullable=True),
            sa.Column("address2", sa.String(255), nullable=True),
            sa.Column("city", sa.String(120), nullable=True),
            sa.Column("state", sa.String(50), nullable=True),
            sa.Column("zip", sa.String(20), nullable=True),
            sa.Column("county", sa.String(80), nullable=True),
            sa.Column("mailing_same_as_residential", sa.Boolean(), server_default="true", nullable=False),
            sa.Column("mailing_address1", sa.String(255), nullable=True),
            sa.Column("mailing_city", sa.String(120), nullable=True),
            sa.Column("mailing_state", sa.String(50), nullable=True),
            sa.Column("mailing_zip", sa.String(20), nullable=True),
            sa.Column("dl_number", sa.String(40), nullable=True),
            sa.Column("dl_state", sa.String(2), nullable=True),
            sa.Column("last_company", sa.String(200), nullable=True),
            sa.Column("referred_by", sa.String(200), nullable=True),
        ],
        fks=[(["packet_id"], ["hire_packets.id"], "CASCADE")],
        uniques=[(["packet_id"], "uq_hire_people_packet")],
        indexes=[("ix_hire_people_packet_id", ["packet_id"])],
    )

    _child(
        "hire_artifacts",
        [
            sa.Column("packet_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("artifact_key", sa.String(40), nullable=False),
            sa.Column("is_draft", sa.Boolean(), server_default="true", nullable=False),
            sa.Column("sha256", sa.String(64), nullable=True),
            sa.Column("storage_name", sa.String(500), nullable=True),
            sa.Column("original_filename", sa.String(500), nullable=True),
            sa.Column("mime_type", sa.String(120), nullable=True),
            sa.Column("file_size_bytes", sa.Integer(), nullable=True),
        ],
        fks=[(["packet_id"], ["hire_packets.id"], "CASCADE")],
        indexes=[
            ("ix_hire_artifacts_packet_id", ["packet_id"]),
            ("ix_hire_artifacts_key", ["artifact_key"]),
        ],
    )

    _child(
        "hire_tax_elections",
        [
            sa.Column("packet_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("form_key", sa.String(20), nullable=False),
            sa.Column("version", sa.Integer(), server_default="1", nullable=False),
            sa.Column("template_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("fields", postgresql.JSONB(), nullable=True),
            sa.Column("signed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("pdf_artifact_id", postgresql.UUID(as_uuid=True), nullable=True),
        ],
        fks=[
            (["packet_id"], ["hire_packets.id"], "CASCADE"),
            (["template_id"], ["form_templates.id"], "SET NULL"),
            (["pdf_artifact_id"], ["hire_artifacts.id"], "SET NULL"),
        ],
        uniques=[(["packet_id", "form_key", "version"], "uq_hire_tax_elections_form_ver")],
        indexes=[("ix_hire_tax_elections_packet_id", ["packet_id"])],
    )

    _child(
        "hire_i9s",
        [
            sa.Column("packet_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("attestation", sa.String(40), nullable=True),
            sa.Column("uscis_a_number", sa.String(40), nullable=True),
            sa.Column("i94_number", sa.String(40), nullable=True),
            sa.Column("foreign_passport_number", sa.String(40), nullable=True),
            sa.Column("foreign_passport_country", sa.String(80), nullable=True),
            sa.Column("work_until", sa.Date(), nullable=True),
            sa.Column("section1_signed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("first_day_of_employment", sa.Date(), nullable=True),
            sa.Column("additional_information", sa.Text(), nullable=True),
            sa.Column("examiner_user_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("examiner_title", sa.String(120), nullable=True),
            sa.Column("examiner_name", sa.String(200), nullable=True),
            sa.Column("employer_business_name", sa.String(200), nullable=True),
            sa.Column("employer_address", sa.Text(), nullable=True),
            sa.Column("section2_signed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("section2_late", sa.Boolean(), server_default="false", nullable=False),
            sa.Column("document_list_mode", sa.String(8), nullable=True),
        ],
        fks=[
            (["packet_id"], ["hire_packets.id"], "CASCADE"),
            (["examiner_user_id"], ["users.id"], "SET NULL"),
        ],
        uniques=[(["packet_id"], "uq_hire_i9s_packet")],
        indexes=[("ix_hire_i9s_packet_id", ["packet_id"])],
    )

    _child(
        "hire_i9_documents",
        [
            sa.Column("i9_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("list_kind", sa.String(1), nullable=False),
            sa.Column("document_title", sa.String(200), nullable=True),
            sa.Column("issuing_authority", sa.String(200), nullable=True),
            sa.Column("document_number", sa.String(80), nullable=True),
            sa.Column("expiration", sa.Date(), nullable=True),
            sa.Column("expiration_na", sa.Boolean(), server_default="false", nullable=False),
            sa.Column("copy_storage_name", sa.String(500), nullable=True),
            sa.Column("original_filename", sa.String(500), nullable=True),
            sa.Column("mime_type", sa.String(120), nullable=True),
            sa.Column("preset_key", sa.String(80), nullable=True),
        ],
        fks=[(["i9_id"], ["hire_i9s.id"], "CASCADE")],
        indexes=[("ix_hire_i9_documents_i9_id", ["i9_id"])],
    )

    _child(
        "hire_direct_deposits",
        [
            sa.Column("packet_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("bank_name", sa.String(200), nullable=True),
            sa.Column("routing_ciphertext", sa.Text(), nullable=True),
            sa.Column("account_ciphertext", sa.Text(), nullable=True),
            sa.Column("account_last4", sa.String(4), nullable=True),
            sa.Column("account_type", sa.String(20), nullable=True),
            sa.Column("account_holder_name", sa.String(200), nullable=True),
            sa.Column("signed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("voided_check_storage_name", sa.String(500), nullable=True),
            sa.Column("voided_check_filename", sa.String(500), nullable=True),
        ],
        fks=[(["packet_id"], ["hire_packets.id"], "CASCADE")],
        uniques=[(["packet_id"], "uq_hire_direct_deposits_packet")],
        indexes=[("ix_hire_direct_deposits_packet_id", ["packet_id"])],
    )

    _child(
        "hire_emergency_contacts",
        [
            sa.Column("packet_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("sort_order", sa.Integer(), server_default="1", nullable=False),
            sa.Column("name", sa.String(200), nullable=True),
            sa.Column("relation", sa.String(80), nullable=True),
            sa.Column("phone", sa.String(50), nullable=True),
        ],
        fks=[(["packet_id"], ["hire_packets.id"], "CASCADE")],
        indexes=[("ix_hire_emergency_contacts_packet_id", ["packet_id"])],
    )

    _child(
        "hire_notice_acks",
        [
            sa.Column("packet_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("notice_key", sa.String(80), nullable=False),
            sa.Column("template_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        ],
        fks=[
            (["packet_id"], ["hire_packets.id"], "CASCADE"),
            (["template_id"], ["form_templates.id"], "SET NULL"),
        ],
        uniques=[(["packet_id", "notice_key"], "uq_hire_notice_acks_key")],
        indexes=[("ix_hire_notice_acks_packet_id", ["packet_id"])],
    )

    _child(
        "hire_signatures",
        [
            sa.Column("packet_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("artifact_key", sa.String(40), nullable=False),
            sa.Column("typed_legal_name", sa.String(200), nullable=True),
            sa.Column("signature_png", sa.Text(), nullable=True),
            sa.Column("signed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("timezone_display", sa.String(64), server_default="America/Los_Angeles", nullable=False),
            sa.Column("source_ip", sa.String(45), nullable=True),
            sa.Column("user_agent", sa.String(500), nullable=True),
            sa.Column("form_template_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("pdf_sha256", sa.String(64), nullable=True),
            sa.Column("certification_checked", sa.Boolean(), server_default="false", nullable=False),
        ],
        fks=[
            (["packet_id"], ["hire_packets.id"], "CASCADE"),
            (["form_template_id"], ["form_templates.id"], "SET NULL"),
        ],
        indexes=[
            ("ix_hire_signatures_packet_id", ["packet_id"]),
            ("ix_hire_signatures_artifact_key", ["artifact_key"]),
        ],
    )

    op.execute(
        sa.text(
            """
            INSERT INTO roles (id, code, name, description)
            SELECT gen_random_uuid(), 'payroll_admin', 'Payroll Administrator', 'Payroll setup for new hires'
            WHERE NOT EXISTS (SELECT 1 FROM roles WHERE code = 'payroll_admin')
            """
        )
    )


def downgrade() -> None:
    for name in (
        "hire_signatures",
        "hire_notice_acks",
        "hire_emergency_contacts",
        "hire_direct_deposits",
        "hire_i9_documents",
        "hire_i9s",
        "hire_tax_elections",
        "hire_artifacts",
        "hire_people",
        "hire_packets",
        "hire_company_settings",
        "form_templates",
    ):
        op.drop_table(name)
