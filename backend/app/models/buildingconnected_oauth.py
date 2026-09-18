"""Persisted APS 3-legged tokens for BuildingConnected sync (one logical integration row)."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from ..extensions import db
from .base import TimestampMixin, TenantMixin


class BuildingConnectedOAuthToken(TimestampMixin, TenantMixin, db.Model):
    """Per-organization store: ``label`` defaults to ``default``."""

    __tablename__ = "buildingconnected_oauth_tokens"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        primary_key=True,
    )
    label: Mapped[str] = mapped_column(String(64), primary_key=True, default="default")
    refresh_token_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    access_token: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    access_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
