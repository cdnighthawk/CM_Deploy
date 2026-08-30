"""Company and project safety-document profiles and generated packets."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..extensions import db
from .base import TimestampMixin, UUIDPKMixin

PACKET_STATUSES = ("draft", "published")

SCOPE_FLAGS = (
    "interiors",
    "ladders",
    "scaffolds",
    "aerialLifts",
    "powderActuatedTools",
    "silicaCuttingGrinding",
    "hotWork",
    "electricalTempPower",
    "occupiedBuilding",
    "publicInterface",
    "confinedSpace",
    "excavation",
    "craneOrHoist",
    "steelErection",
    "demolition",
    "leadPaint",
    "asbestosPossible",
)


def default_scope() -> dict[str, bool]:
    out = {key: False for key in SCOPE_FLAGS}
    out["interiors"] = True
    out["ladders"] = True
    return out


def empty_person() -> dict[str, str]:
    return {"name": "", "title": "", "phone": "", "email": ""}


def empty_facility() -> dict[str, str]:
    return {"name": "", "address": "", "phone": "", "directions": ""}


def default_project_payload() -> dict[str, Any]:
    return {
        "projectName": "",
        "projectNumber": "",
        "clientName": "",
        "gcName": "",
        "roleOnSite": "subcontractor",
        "address": {
            "line1": "",
            "line2": "",
            "city": "",
            "state": "CA",
            "zip": "",
            "county": "",
        },
        "accessNotes": "",
        "startDate": "",
        "endDate": "",
        "crewSizeTypical": None,
        "languagesOnSite": ["English", "Spanish"],
        "superintendent": empty_person() | {"title": "Superintendent"},
        "projectManager": empty_person() | {"title": "Project Manager"},
        "competentPersons": {
            "firstAid": empty_person(),
            "lifts": empty_person(),
            "scaffolds": empty_person(),
            "silica": empty_person(),
            "fallProtection": empty_person(),
            "electrical": empty_person(),
        },
        "emergency": {
            "musterPoint": "",
            "secondaryMuster": "",
            "whoCalls911": "",
            "whoCallsCalOsha": "",
            "hospital": empty_facility(),
            "clinic": empty_facility(),
            "fireDept": "",
            "police": "",
            "calOshaDistrictOffice": empty_facility(),
            "cellCoverageReliable": True,
            "radioChannel": "",
            "directionsFor911": "",
        },
        "climate": {
            "outdoorWork": True,
            "indoorWork": True,
            "elevationFt": None,
            "heatRisk": "moderate",
            "coldIceSnow": False,
            "wildfireSmokePossible": False,
            "notes": "",
        },
        "scope": default_scope(),
        "ppeRequired": [
            "Hard hat",
            "Safety glasses",
            "High-visibility vest when exposed to equipment or public traffic",
            "Work boots with defined heel",
        ],
        "chemicals": [],
        "gcRulesStricter": "",
        "notes": "",
    }


class CompanySafetyProfile(UUIDPKMixin, TimestampMixin, db.Model):
    """Singleton company safety identity used to merge IIPP / WVPP / heat / HazCom."""

    __tablename__ = "company_safety_profiles"

    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    template_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    docs: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    docs_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    docs_generated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class ProjectSafetyProfile(UUIDPKMixin, TimestampMixin, db.Model):
    """Site-specific safety JSON for one project (project.schema.json)."""

    __tablename__ = "project_safety_profiles"
    __table_args__ = (UniqueConstraint("project_id", name="uq_project_safety_profiles_project_id"),)

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    project = relationship("Project", foreign_keys=[project_id])


class ProjectSafetyPacket(UUIDPKMixin, TimestampMixin, db.Model):
    """Latest generated project safety packet (HTML + snapshot)."""

    __tablename__ = "project_safety_packets"
    __table_args__ = (UniqueConstraint("project_id", name="uq_project_safety_packets_project_id"),)

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    json_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    html: Mapped[str] = mapped_column(Text, nullable=False, default="")
    docs: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    missing_fields: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    generated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    project = relationship("Project", foreign_keys=[project_id])
