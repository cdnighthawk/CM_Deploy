"""SaaS tenant (paying company account). Distinct from directory ``Company`` rows.

This row *is* the Tenant from the SaaS admin ticket. Do not add a parallel
``tenants`` table. Billing fields live here; key/value controls live on
``TenantSetting``.
"""
from __future__ import annotations

import uuid
from typing import List, Optional

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..extensions import db
from .base import TimestampMixin, UUIDPKMixin

TENANT_STATUSES = ("trial", "active", "past_due", "suspended", "closed")
TENANT_PLANS = ("field", "office", "full")

ORG_ROLE_OWNER = "owner"
ORG_ROLE_ADMIN = "admin"
ORG_ROLE_MEMBER = "member"
ORG_ROLES = (ORG_ROLE_OWNER, ORG_ROLE_ADMIN, ORG_ROLE_MEMBER)

USIS_ORG_SLUG = "usis"


class Organization(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(80), unique=True, nullable=False, index=True)
    microsoft_sso_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    entra_tenant_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    allow_join_by_domain: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    storage_prefix: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    legal_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    dba: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    cslb: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    fein_last4: Mapped[Optional[str]] = mapped_column(String(4), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    plan_key: Mapped[str] = mapped_column(String(20), nullable=False, default="full")
    seat_cap_office: Mapped[int] = mapped_column(Integer, nullable=False, default=50)
    seat_cap_field: Mapped[int] = mapped_column(Integer, nullable=False, default=50)
    seat_cap_vendor_token: Mapped[int] = mapped_column(Integer, nullable=False, default=500)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    members: Mapped[List["OrganizationMember"]] = relationship(
        back_populates="organization", cascade="all, delete-orphan"
    )


class OrganizationMember(TimestampMixin, db.Model):
    __tablename__ = "organization_members"
    __table_args__ = (
        UniqueConstraint("user_id", "organization_id", name="uq_organization_members_user_org"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        primary_key=True,
        index=True,
    )
    org_role: Mapped[str] = mapped_column(String(20), nullable=False, default=ORG_ROLE_MEMBER)

    user = relationship("User", foreign_keys=[user_id])
    organization: Mapped["Organization"] = relationship(back_populates="members")
