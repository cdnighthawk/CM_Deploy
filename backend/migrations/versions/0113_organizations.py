"""Organizations (SaaS tenants) and organization_id on tenant-owned tables.

Revision ID: 0113_orgs
Revises: 0112_mat_labor
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0113_orgs"
down_revision: Union[str, Sequence[str], None] = "0112_mat_labor"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_UUID = postgresql.UUID(as_uuid=True)

_GLOBAL_TABLES = frozenset(
    {
        "alembic_version",
        "organizations",
        "organization_members",
        "users",
        "roles",
        "role_module_permissions",
        "manufacturer_product_data",
        "wage_rates",
        "invoice_delivery_methods",
        "procurement_po_types",
        "sales_tax_rates",
        "password_reset_tokens",
        "mobile_refresh_tokens",
        "drawings",
        "spatial_ref_sys",
        "geography_columns",
        "geometry_columns",
    }
)

_COMPOSITE_PK = {
    "user_roles": ["user_id", "organization_id", "role_id"],
    "hire_company_settings": ["organization_id", "key"],
    "textura_credentials": ["organization_id", "label"],
    "buildingconnected_oauth_tokens": ["organization_id", "label"],
}

_NEW_UNIQUES = [
    ("material_pricing", "uq_material_pricing_org_manufacturer_item", ["organization_id", "manufacturer", "item"]),
    ("company_cost_codes", "uq_company_cost_codes_org_code", ["organization_id", "code"]),
    ("projects", "uq_projects_org_number", ["organization_id", "number"]),
    ("lead_estimates", "uq_lead_estimates_org_external_id", ["organization_id", "external_id"]),
    ("hrms_module_settings", "uq_hrms_module_settings_org_key", ["organization_id", "key"]),
    ("hrms_leave_types", "uq_hrms_leave_types_org_code", ["organization_id", "code"]),
    ("estimator_scripts", "uq_estimator_scripts_org_script_key", ["organization_id", "script_key"]),
    ("estimator_standard_specs", "uq_estimator_standard_specs_org_code", ["organization_id", "spec_code"]),
    ("user_roles", "uq_user_roles_user_org_role", ["user_id", "organization_id", "role_id"]),
]


def _tenant_tables(bind) -> list[str]:
    insp = sa.inspect(bind)
    names = []
    for name in insp.get_table_names():
        if name in _GLOBAL_TABLES:
            continue
        cols = {c["name"] for c in insp.get_columns(name)}
        if "organization_id" in cols:
            continue
        names.append(name)
    return sorted(names)


def _drop_unique_on_columns(bind, table: str, columns: set[str]) -> None:
    insp = sa.inspect(bind)
    if table not in insp.get_table_names():
        return
    for uq in insp.get_unique_constraints(table):
        uq_cols = set(uq.get("column_names") or ())
        if uq_cols == columns or (len(columns) == 1 and columns <= uq_cols and "organization_id" not in uq_cols):
            name = uq.get("name")
            if name:
                op.drop_constraint(name, table, type_="unique")
    for ix in insp.get_indexes(table):
        if not ix.get("unique"):
            continue
        ix_cols = set(ix.get("column_names") or ())
        if ix_cols == columns:
            name = ix.get("name")
            if name:
                op.drop_index(name, table_name=table)


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("id", _UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column("microsoft_sso_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("entra_tenant_id", sa.String(length=64), nullable=True),
        sa.Column("allow_join_by_domain", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("storage_prefix", sa.String(length=120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_organizations"),
        sa.UniqueConstraint("slug", name="uq_organizations_slug"),
    )
    op.create_index("ix_organizations_slug", "organizations", ["slug"])

    op.create_table(
        "organization_members",
        sa.Column("user_id", _UUID, nullable=False),
        sa.Column("organization_id", _UUID, nullable=False),
        sa.Column("org_role", sa.String(length=20), nullable=False, server_default="member"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE", name="fk_organization_members_user_id_users"),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            ondelete="CASCADE",
            name="fk_organization_members_organization_id_organizations",
        ),
        sa.PrimaryKeyConstraint("user_id", "organization_id", name="pk_organization_members"),
        sa.UniqueConstraint("user_id", "organization_id", name="uq_organization_members_user_org"),
    )
    op.create_index("ix_organization_members_organization_id", "organization_members", ["organization_id"])

    op.execute(
        sa.text(
            """
            INSERT INTO organizations (name, slug, microsoft_sso_enabled, storage_prefix)
            VALUES ('US Interior Specialties', 'usis', true, '')
            """
        )
    )

    bind = op.get_bind()
    tables = _tenant_tables(bind)

    for table in tables:
        op.add_column(table, sa.Column("organization_id", _UUID, nullable=True))

    op.execute(
        sa.text(
            """
            DO $$
            DECLARE r RECORD;
            DECLARE usis uuid;
            BEGIN
                SELECT id INTO usis FROM organizations WHERE slug = 'usis' LIMIT 1;
                FOR r IN
                    SELECT table_name
                    FROM information_schema.columns
                    WHERE table_schema = current_schema()
                      AND column_name = 'organization_id'
                      AND table_name <> 'organization_members'
                LOOP
                    EXECUTE format(
                        'UPDATE %I SET organization_id = $1 WHERE organization_id IS NULL',
                        r.table_name
                    ) USING usis;
                END LOOP;
            END $$;
            """
        )
    )

    insp = sa.inspect(bind)
    for table in tables:
        if table in _COMPOSITE_PK:
            pk = insp.get_pk_constraint(table)
            pk_name = pk.get("name") if pk else None
            if pk_name:
                op.drop_constraint(pk_name, table, type_="primary")
        op.alter_column(table, "organization_id", nullable=False)
        op.create_index(f"ix_{table}_organization_id", table, ["organization_id"])
        op.create_foreign_key(
            f"fk_{table}_organization_id_organizations",
            table,
            "organizations",
            ["organization_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        if table in _COMPOSITE_PK:
            op.create_primary_key(f"pk_{table}", table, _COMPOSITE_PK[table])

    op.execute(
        sa.text(
            """
            INSERT INTO organization_members (user_id, organization_id, org_role)
            SELECT u.id, o.id, CASE WHEN u.is_superuser THEN 'owner' ELSE 'member' END
            FROM users u
            CROSS JOIN organizations o
            WHERE o.slug = 'usis'
            ON CONFLICT DO NOTHING
            """
        )
    )

    bind = op.get_bind()
    _drop_unique_on_columns(bind, "material_pricing", {"manufacturer", "item"})
    _drop_unique_on_columns(bind, "company_cost_codes", {"code"})
    _drop_unique_on_columns(bind, "projects", {"number"})
    _drop_unique_on_columns(bind, "lead_estimates", {"external_id"})
    _drop_unique_on_columns(bind, "hrms_module_settings", {"key"})
    _drop_unique_on_columns(bind, "hrms_leave_types", {"code"})
    _drop_unique_on_columns(bind, "estimator_scripts", {"script_key"})
    _drop_unique_on_columns(bind, "estimator_standard_specs", {"spec_code"})

    insp = sa.inspect(bind)
    existing_tables = set(insp.get_table_names())
    for table, name, cols in _NEW_UNIQUES:
        if table not in existing_tables:
            continue
        table_cols = {c["name"] for c in insp.get_columns(table)}
        if not set(cols) <= table_cols:
            continue
        already = {uq.get("name") for uq in insp.get_unique_constraints(table)}
        if name in already:
            continue
        op.create_unique_constraint(name, table, cols)


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    for table in list(insp.get_table_names()):
        cols = {c["name"] for c in insp.get_columns(table)}
        if "organization_id" not in cols or table in ("organizations", "organization_members"):
            continue
        fks = insp.get_foreign_keys(table)
        for fk in fks:
            if fk.get("constrained_columns") == ["organization_id"]:
                if fk.get("name"):
                    op.drop_constraint(fk["name"], table, type_="foreignkey")
        for ix in insp.get_indexes(table):
            if ix.get("column_names") == ["organization_id"] and ix.get("name"):
                op.drop_index(ix["name"], table_name=table)
        op.drop_column(table, "organization_id")
    op.drop_table("organization_members")
    op.drop_table("organizations")
