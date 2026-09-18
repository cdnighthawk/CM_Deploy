"""Encrypted Textura TPM API credentials (single-tenant default row)."""
from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from ..extensions import db
from .base import TimestampMixin, TenantMixin


class TexturaCredential(TimestampMixin, TenantMixin, db.Model):
    __tablename__ = "textura_credentials"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        primary_key=True,
    )
    label: Mapped[str] = mapped_column(String(64), primary_key=True, default="default")
    username: Mapped[str] = mapped_column(String(255), nullable=False)
    password_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    api_base: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
