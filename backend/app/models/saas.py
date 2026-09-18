"""SaaS admin tables: entitlements, flags, tenant settings, platform audit, impersonation.

Tenant billing unit is ``Organization`` (see ``organization.py``). Do not add a
second Tenant table.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from ..extensions import db
from .base import TimestampMixin, UUIDPKMixin


class TenantEntitlement(UUIDPKMixin, TimestampMixin, db.Model):
    """Per-tenant module on/off. Missing row = inherit plan default."""

    __tablename__ = "tenant_entitlements"
    __table_args__ = (
        UniqueConstraint("organization_id", "module_key", name="uq_tenant_entitlements_org_module"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    module_key: Mapped[str] = mapped_column(String(80), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class FeatureFlag(UUIDPKMixin, TimestampMixin, db.Model):
    """Platform default (organization_id NULL) or tenant override."""

    __tablename__ = "feature_flags"

    key: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    default_on: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    organization_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )


class TenantSetting(TimestampMixin, db.Model):
    """Dotted key/value settings per organization. Do not invent 50 columns."""

    __tablename__ = "tenant_settings"
    __table_args__ = (
        UniqueConstraint("organization_id", "key", name="uq_tenant_settings_org_key"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        primary_key=True,
    )
    key: Mapped[str] = mapped_column(String(120), primary_key=True)
    value_json: Mapped[Any] = mapped_column(JSONB, nullable=True)
    updated_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )


class PlatformAudit(UUIDPKMixin, db.Model):
    """Cross-tenant privileged audit (settings, flags, impersonate, seats)."""

    __tablename__ = "platform_audit"

    actor_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    organization_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    impersonation_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("impersonation_sessions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    action: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    before_json: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    after_json: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class ImpersonationSession(UUIDPKMixin, db.Model):
    """Audited operator view of a tenant. Reason required (min 12 chars)."""

    __tablename__ = "impersonation_sessions"

    operator_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    target_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    banner_ack: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
