"""Encrypted Textura TPM API credentials (single-tenant default row)."""
from __future__ import annotations

from typing import Optional

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..extensions import db
from .base import TimestampMixin


class TexturaCredential(TimestampMixin, db.Model):
    __tablename__ = "textura_credentials"

    label: Mapped[str] = mapped_column(String(64), primary_key=True, default="default")
    username: Mapped[str] = mapped_column(String(255), nullable=False)
    password_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    api_base: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
