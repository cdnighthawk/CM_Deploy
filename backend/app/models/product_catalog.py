"""Manufacturer product data sheets for submittal auto-fill (ASI, Bobrick, etc.)."""
from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ..extensions import db
from .base import TimestampMixin, UUIDPKMixin


class ManufacturerProductData(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "manufacturer_product_data"

    manufacturer: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    model: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    product_name: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    pdf_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    pattern_key: Mapped[Optional[str]] = mapped_column(String(40), nullable=True, index=True)
    technical_data_json: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
