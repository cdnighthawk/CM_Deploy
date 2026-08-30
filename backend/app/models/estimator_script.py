"""Amendable estimator scripts: overall bid-scope pass, then spec-specific runs."""
from __future__ import annotations

import uuid
from typing import Any, List, Optional

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..extensions import db
from .base import TimestampMixin, UUIDPKMixin


class EstimatorScript(UUIDPKMixin, TimestampMixin, db.Model):
    """Named automation script. process_key == script_key on the shared engine."""

    __tablename__ = "estimator_scripts"

    script_key: Mapped[str] = mapped_column(String(80), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    spec_prefixes: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    applies_when: Mapped[str] = mapped_column(String(40), nullable=False, default="always")
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class EstimatorStandardSpec(UUIDPKMixin, TimestampMixin, db.Model):
    """USIS default bid set. Overall pass starts here unless a GC bid package wins."""

    __tablename__ = "estimator_standard_specs"
    __table_args__ = (UniqueConstraint("spec_code", name="uq_estimator_standard_specs_code"),)

    spec_code: Mapped[str] = mapped_column(String(20), nullable=False)
    spec_title: Mapped[str] = mapped_column(String(200), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class EstimateBidScope(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "estimate_bid_scopes"

    estimate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("estimates.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    source: Mapped[str] = mapped_column(String(40), nullable=False, default="standard")
    bid_package_label: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="draft", index=True)

    items: Mapped[List["EstimateBidScopeItem"]] = relationship(
        back_populates="scope",
        cascade="all, delete-orphan",
        order_by="EstimateBidScopeItem.sort_order",
    )


class EstimateBidScopeItem(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "estimate_bid_scope_items"

    scope_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("estimate_bid_scopes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    spec_code: Mapped[str] = mapped_column(String(20), nullable=False)
    spec_title: Mapped[str] = mapped_column(String(200), nullable=False)
    script_key: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    included: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    item_source: Mapped[str] = mapped_column(String(40), nullable=False, default="standard")
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="pending")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    workflow_instance_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workflow_instances.id", ondelete="SET NULL"),
        nullable=True,
    )

    scope: Mapped["EstimateBidScope"] = relationship(back_populates="items")
