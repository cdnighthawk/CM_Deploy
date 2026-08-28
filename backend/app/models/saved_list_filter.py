"""Personal named list-query presets (Leads drawer first; table_key is forward-compatible)."""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..extensions import db
from .auth import User
from .base import TimestampMixin, UUIDPKMixin


class SavedListFilter(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "saved_list_filters"
    __table_args__ = (
        UniqueConstraint("user_id", "table_key", "name", name="uq_saved_list_filters_user_table_name"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    table_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    query_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    user: Mapped[User] = relationship("User", foreign_keys=[user_id])
