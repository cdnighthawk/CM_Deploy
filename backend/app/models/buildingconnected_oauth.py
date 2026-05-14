"""Persisted APS 3-legged tokens for BuildingConnected sync (one logical integration row)."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..extensions import db
from .base import TimestampMixin


class BuildingConnectedOAuthToken(TimestampMixin, db.Model):
    """Single-tenant store: ``label`` defaults to ``default`` for the server-wide BC connection."""

    __tablename__ = "buildingconnected_oauth_tokens"

    label: Mapped[str] = mapped_column(String(64), primary_key=True, default="default")
    refresh_token_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    access_token: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    access_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
