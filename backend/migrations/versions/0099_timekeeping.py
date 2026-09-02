"""Office timekeeping tables, CA policy seed, punch column extensions.

Revision ID: 0099_timekeep
Revises: 0098_chat_msg
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0099_timekeep"
down_revision: Union[str, Sequence[str], None] = "0098_chat_msg"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_FINISH_CODES = (
    ("09 21 00", "Metal framing / drywall", "drywall", 10),
    ("09 29 00", "Gypsum board", "drywall", 20),
    ("09 91 00", "Painting", "paint", 30),
    ("09 65 00", "Resilient flooring", "flooring", 40),
    ("09 51 00", "Acoustical ceilings", "ceilings", 50),
    ("10 21 00", "Toilet compartments", "div10", 60),
    ("10 51 00", "Lockers", "div10", 70),
    ("10 14 00", "Signage", "div10", 80),
    ("10 44 00", "Fire extinguisher cabinets", "div10", 90),
    ("10 26 00", "Wall protection", "div10", 100),
    ("TRAVEL", "Travel", "other", 200),
    ("SHOP", "Shop", "other", 210),
    ("DUMP", "Dump", "other", 220),
    ("WARRANTY", "Warranty", "other", 230),
    ("EXTRA", "Extra work", "other", 240),
    ("TM", "T&M", "other", 250),
)

_POLICY = (
    '{"timezone":"America/Los_Angeles","week_start":"sunday","ot_daily_hours":8,'
    '"dt_daily_hours":12,"ot_weekly_hours":40,"seventh_day_ot":true,'
    '"meal_after_hours":5,"meal_minutes":30,"second_meal_after_hours":10,'
    '"rest_minutes_per_4h":10,"geofence_default_mode":"flag","require_cost_code":false,'
    '"require_daily_signoff":true,"require_supervisor_approve_before_export":true,'
    '"block_export_with_open_flags":true,"open_punch_flag_after_hours":12,'
    '"web_punch_allowed":true,"breadcrumb_min_interval_sec":180,"track_off_clock":false,'
    '"show_own_cost_on_my_time":false}'
)


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = set(insp.get_table_names())

    if "time_cost_codes" not in tables:
        op.create_table(
            "time_cost_codes",
            sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
            sa.Column("code", sa.String(length=60), nullable=False),
            sa.Column("name", sa.String(length=200), nullable=False),
            sa.Column("trade", sa.String(length=80), nullable=True),
            sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
            sa.Column("is_billable", sa.Boolean(), server_default="true", nullable=False),
            sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
            sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("code", name="uq_time_cost_codes_code"),
        )

    if "project_time_cost_codes" not in tables:
        op.create_table(
            "project_time_cost_codes",
            sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("time_cost_code_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("required", sa.Boolean(), server_default="false", nullable=False),
            sa.Column("favorite", sa.Boolean(), server_default="false", nullable=False),
            sa.Column("is_enabled", sa.Boolean(), server_default="true", nullable=False),
            sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["time_cost_code_id"], ["time_cost_codes.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("project_id", "time_cost_code_id"),
            sa.UniqueConstraint("project_id", "time_cost_code_id", name="uq_project_time_cost_codes"),
        )

    if "employee_time_profiles" not in tables:
        op.create_table(
            "employee_time_profiles",
            sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("classification", sa.String(length=120), nullable=True),
            sa.Column("union_local", sa.String(length=80), nullable=True),
            sa.Column("prevailing_class", sa.String(length=120), nullable=True),
            sa.Column("default_cost_code_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("hourly_rate", sa.Numeric(10, 2), nullable=True),
            sa.Column("ot_rate", sa.Numeric(10, 2), nullable=True),
            sa.Column("dt_rate", sa.Numeric(10, 2), nullable=True),
            sa.Column("burden_rate", sa.Numeric(10, 2), nullable=True),
            sa.Column("hire_date", sa.Date(), nullable=True),
            sa.Column("is_clock_eligible", sa.Boolean(), server_default="true", nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["default_cost_code_id"], ["time_cost_codes.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("user_id", name="uq_employee_time_profiles_user"),
        )
        op.create_index("ix_employee_time_profiles_user_id", "employee_time_profiles", ["user_id"])

    if "project_geofences" not in tables:
        op.create_table(
            "project_geofences",
            sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
            sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("mode", sa.String(length=20), server_default="flag", nullable=False),
            sa.Column("shape", sa.String(length=20), server_default="circle", nullable=False),
            sa.Column("center_lat", sa.Numeric(10, 7), nullable=True),
            sa.Column("center_lon", sa.Numeric(10, 7), nullable=True),
            sa.Column("radius_m", sa.Numeric(10, 2), nullable=True),
            sa.Column("polygon_geojson", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("reminder_mode", sa.String(length=40), server_default="off", nullable=False),
            sa.Column("timezone", sa.String(length=64), nullable=True),
            sa.Column("shift_end_hour", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("project_id", name="uq_project_geofences_project"),
        )
        op.create_index("ix_project_geofences_project_id", "project_geofences", ["project_id"])

    if "time_entries" in tables:
        cols = {c["name"] for c in insp.get_columns("time_entries")}
        add = [
            ("time_cost_code_id", sa.Column("time_cost_code_id", postgresql.UUID(as_uuid=True), nullable=True)),
            ("equipment_id", sa.Column("equipment_id", postgresql.UUID(as_uuid=True), nullable=True)),
            ("entry_type", sa.Column("entry_type", sa.String(length=20), server_default="work", nullable=False)),
            ("source", sa.Column("source", sa.String(length=40), server_default="mobile", nullable=False)),
            ("punched_by_id", sa.Column("punched_by_id", postgresql.UUID(as_uuid=True), nullable=True)),
            ("device_start_at", sa.Column("device_start_at", sa.DateTime(timezone=True), nullable=True)),
            ("device_end_at", sa.Column("device_end_at", sa.DateTime(timezone=True), nullable=True)),
            ("start_lat", sa.Column("start_lat", sa.Numeric(10, 7), nullable=True)),
            ("start_lon", sa.Column("start_lon", sa.Numeric(10, 7), nullable=True)),
            ("start_acc", sa.Column("start_acc", sa.Numeric(8, 2), nullable=True)),
            ("end_lat", sa.Column("end_lat", sa.Numeric(10, 7), nullable=True)),
            ("end_lon", sa.Column("end_lon", sa.Numeric(10, 7), nullable=True)),
            ("end_acc", sa.Column("end_acc", sa.Numeric(8, 2), nullable=True)),
            ("gps_status", sa.Column("gps_status", sa.String(length=20), nullable=True)),
            ("offsite", sa.Column("offsite", sa.Boolean(), server_default="false", nullable=False)),
            ("pending_flags", sa.Column("pending_flags", postgresql.JSONB(astext_type=sa.Text()), nullable=True)),
            ("locked", sa.Column("locked", sa.Boolean(), server_default="false", nullable=False)),
            ("voided", sa.Column("voided", sa.Boolean(), server_default="false", nullable=False)),
            ("void_reason", sa.Column("void_reason", sa.Text(), nullable=True)),
            ("ip_address", sa.Column("ip_address", sa.String(length=64), nullable=True)),
            ("device_label", sa.Column("device_label", sa.String(length=120), nullable=True)),
        ]
        for name, col in add:
            if name not in cols:
                op.add_column("time_entries", col)
        if "time_cost_code_id" not in cols:
            op.create_foreign_key(
                "fk_time_entries_time_cost_code",
                "time_entries",
                "time_cost_codes",
                ["time_cost_code_id"],
                ["id"],
                ondelete="SET NULL",
            )
        if "punched_by_id" not in cols:
            op.create_foreign_key(
                "fk_time_entries_punched_by",
                "time_entries",
                "users",
                ["punched_by_id"],
                ["id"],
                ondelete="SET NULL",
            )

    if "time_punches" in tables:
        pcols = {c["name"] for c in insp.get_columns("time_punches")}
        if "entry_id" in pcols:
            op.alter_column("time_punches", "entry_id", existing_type=postgresql.UUID(as_uuid=True), nullable=True)
        padd = [
            ("user_id", sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True)),
            ("project_id", sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True)),
            ("cost_code_id", sa.Column("cost_code_id", postgresql.UUID(as_uuid=True), nullable=True)),
            ("time_cost_code_id", sa.Column("time_cost_code_id", postgresql.UUID(as_uuid=True), nullable=True)),
            ("source", sa.Column("source", sa.String(length=40), nullable=True)),
            ("performed_by_id", sa.Column("performed_by_id", postgresql.UUID(as_uuid=True), nullable=True)),
            ("payload_json", sa.Column("payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True)),
            ("device_label", sa.Column("device_label", sa.String(length=120), nullable=True)),
            ("reason", sa.Column("reason", sa.Text(), nullable=True)),
        ]
        for name, col in padd:
            if name not in pcols:
                op.add_column("time_punches", col)
        op.create_index("ix_time_punches_user_id", "time_punches", ["user_id"], if_not_exists=True)

    if "time_breadcrumbs" not in tables:
        op.create_table(
            "time_breadcrumbs",
            sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("time_entry_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("lat", sa.Numeric(10, 7), nullable=False),
            sa.Column("lon", sa.Numeric(10, 7), nullable=False),
            sa.Column("acc", sa.Numeric(8, 2), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["time_entry_id"], ["time_entries.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_time_breadcrumbs_user_id", "time_breadcrumbs", ["user_id"])
        op.create_index("ix_time_breadcrumbs_at", "time_breadcrumbs", ["at"])

    if "time_flags" not in tables:
        op.create_table(
            "time_flags",
            sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("time_entry_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("work_date", sa.Date(), nullable=True),
            sa.Column("flag_type", sa.String(length=40), nullable=False),
            sa.Column("status", sa.String(length=20), server_default="open", nullable=False),
            sa.Column("detail", sa.Text(), nullable=True),
            sa.Column("assigned_to", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("resolved_by", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("reason", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["time_entry_id"], ["time_entries.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["assigned_to"], ["users.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["resolved_by"], ["users.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_time_flags_user_id", "time_flags", ["user_id"])
        op.create_index("ix_time_flags_flag_type", "time_flags", ["flag_type"])

    if "timecard_periods" not in tables:
        op.create_table(
            "timecard_periods",
            sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
            sa.Column("period_start", sa.Date(), nullable=False),
            sa.Column("period_end", sa.Date(), nullable=False),
            sa.Column("status", sa.String(length=20), server_default="open", nullable=False),
            sa.Column("exported_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("exported_by", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("export_file_url", sa.String(length=1024), nullable=True),
            sa.Column("workflow_instance_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("policy_json", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
            sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("locked_by", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["exported_by"], ["users.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["locked_by"], ["users.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["workflow_instance_id"], ["workflow_instances.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_timecard_periods_period_start", "timecard_periods", ["period_start"])

    if "timecard_days" not in tables:
        op.create_table(
            "timecard_days",
            sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("work_date", sa.Date(), nullable=False),
            sa.Column("regular_hours", sa.Numeric(8, 2), server_default="0", nullable=False),
            sa.Column("ot_hours", sa.Numeric(8, 2), server_default="0", nullable=False),
            sa.Column("dt_hours", sa.Numeric(8, 2), server_default="0", nullable=False),
            sa.Column("premium_hours", sa.Numeric(8, 2), server_default="0", nullable=False),
            sa.Column("meal_minutes", sa.Numeric(8, 2), server_default="0", nullable=False),
            sa.Column("signed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("signed_ip", sa.String(length=64), nullable=True),
            sa.Column("signature_png_url", sa.Text(), nullable=True),
            sa.Column("employee_attested_accurate", sa.Boolean(), server_default="false", nullable=False),
            sa.Column("injury_reported", sa.Boolean(), server_default="false", nullable=False),
            sa.Column("injury_note", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("user_id", "work_date", name="uq_timecard_days_user_date"),
        )
        op.create_index("ix_timecard_days_user_id", "timecard_days", ["user_id"])
        op.create_index("ix_timecard_days_work_date", "timecard_days", ["work_date"])

    if "timecard_period_employees" not in tables:
        op.create_table(
            "timecard_period_employees",
            sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
            sa.Column("period_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("regular_hours", sa.Numeric(8, 2), server_default="0", nullable=False),
            sa.Column("ot_hours", sa.Numeric(8, 2), server_default="0", nullable=False),
            sa.Column("dt_hours", sa.Numeric(8, 2), server_default="0", nullable=False),
            sa.Column("premium_hours", sa.Numeric(8, 2), server_default="0", nullable=False),
            sa.Column("signed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("signature_png_url", sa.Text(), nullable=True),
            sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("approved_by", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("workflow_status", sa.String(length=40), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["period_id"], ["timecard_periods.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["approved_by"], ["users.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("period_id", "user_id", name="uq_timecard_period_employees"),
        )

    for code, name, trade, sort in _FINISH_CODES:
        op.execute(
            sa.text(
                "INSERT INTO time_cost_codes (code, name, trade, is_active, is_billable, sort_order) "
                "SELECT :code, :name, :trade, true, true, :sort "
                "WHERE NOT EXISTS (SELECT 1 FROM time_cost_codes WHERE code = :code)"
            ).bindparams(code=code, name=name, trade=trade, sort=sort)
        )

    if "hrms_module_settings" in tables:
        op.execute(
            sa.text(
                "INSERT INTO hrms_module_settings (key, value) "
                "SELECT 'timekeeping_policy', CAST(:policy AS jsonb) "
                "WHERE NOT EXISTS (SELECT 1 FROM hrms_module_settings WHERE key = 'timekeeping_policy')"
            ).bindparams(policy=_POLICY)
        )


def downgrade() -> None:
    op.drop_table("timecard_period_employees")
    op.drop_table("timecard_days")
    op.drop_table("timecard_periods")
    op.drop_table("time_flags")
    op.drop_table("time_breadcrumbs")
    op.drop_table("project_geofences")
    op.drop_table("employee_time_profiles")
    op.drop_table("project_time_cost_codes")
    op.drop_table("time_cost_codes")
