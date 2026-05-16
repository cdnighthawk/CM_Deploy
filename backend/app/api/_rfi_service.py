"""RFI service layer.

Splits the RFI HTTP endpoints in ``v1.py`` from the business logic
(validation, status transitions, audit logging, notification fan-out).
Each function returns plain Python types or raises ``ApiError`` so the
caller can map to an HTTP response.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Iterable, Mapping, Optional

from sqlalchemy import and_, func, or_, select

from ..extensions import db
from ..models import (
    Company,
    Contact,
    CostCode,
    Document,
    Drawing,
    Location,
    Project,
    ProjectStage,
    Rfi,
    RfiAssignee,
    RfiAudit,
    RfiColumnPref,
    RfiConfigurableField,
    RfiCustomFieldDef,
    RfiCustomFieldValue,
    RfiDistribution,
    RfiNotificationLog,
    RfiReply,
    RfiRevision,
    RfiSavedView,
    SpecSection,
    SubJob,
    User,
)
from ._perms import (
    CurrentUser,
    can_act_as_manager,
    can_add_assignee,
    can_close_or_reopen,
    can_create_open_rfi,
    can_create_rfi,
    can_delete_rfi,
    can_edit_rfi,
    can_forward,
    can_mark_official,
    can_reply,
    can_restore_rfi,
    can_shift_ball_in_court,
    can_view_rfi,
    explain_rfi,
)

# ---------------------------------------------------------------------------
# Exceptions + helpers
# ---------------------------------------------------------------------------


class ApiError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message = message
        self.status = status


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


def _parse_uuid(raw: Any) -> Optional[uuid.UUID]:
    if raw in (None, ""):
        return None
    try:
        return uuid.UUID(str(raw).strip())
    except (TypeError, ValueError):
        return None


def _parse_dt(raw: Any) -> Optional[datetime]:
    if raw in (None, ""):
        return None
    if isinstance(raw, datetime):
        return raw if raw.tzinfo else raw.replace(tzinfo=timezone.utc)
    if isinstance(raw, str):
        s = raw.strip()
        if not s:
            return None
        try:
            if s.endswith("Z"):
                s = s[:-1] + "+00:00"
            dt = datetime.fromisoformat(s)
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            pass
        try:
            return datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    return None


def _parse_decimal(raw: Any) -> Optional[Decimal]:
    if raw in (None, ""):
        return None
    if isinstance(raw, bool):
        return None
    try:
        return Decimal(str(raw))
    except (ValueError, ArithmeticError):
        return None


def _parse_int(raw: Any) -> Optional[int]:
    if raw in (None, ""):
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _parse_bool(raw: Any, default: bool = False) -> bool:
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, str):
        return raw.strip().lower() in ("1", "true", "yes", "on", "y", "t")
    if isinstance(raw, (int, float)):
        return bool(raw)
    return default


IMPACT_CHOICES = {"yes", "yes_unknown", "no", "tbd", "na"}
RFI_STATUSES = {"draft", "open", "closed", "closed_draft"}


def _normalize_impact_choice(raw: Any) -> Optional[str]:
    if raw is None:
        return None
    s = str(raw).strip().lower().replace("-", "_").replace(" ", "_")
    if s in IMPACT_CHOICES:
        return s
    if s in ("y", "yes!"):
        return "yes"
    if s in ("n",):
        return "no"
    return None


# ---------------------------------------------------------------------------
# Public serializers
# ---------------------------------------------------------------------------


def _iso(dt: Optional[datetime]) -> Optional[str]:
    return dt.isoformat() if dt else None


def _user_label(u: Optional[User]) -> Optional[dict[str, Any]]:
    if u is None:
        return None
    name = " ".join(p for p in (u.first_name, u.last_name) if p).strip() or u.email
    return {"id": str(u.id), "name": name, "email": u.email}


def _company_label(c: Optional[Company]) -> Optional[dict[str, Any]]:
    if c is None:
        return None
    return {"id": str(c.id), "name": c.name, "company_type": c.company_type}


def _decimal(v: Any) -> Optional[float]:
    if v is None:
        return None
    if isinstance(v, Decimal):
        return float(v)
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _resolve_ball_in_court_label(rfi: Rfi) -> str:
    bic = [a for a in rfi.assignees if a.ball_in_court]
    if bic:
        u = bic[0].user
        if u is not None:
            return _user_label(u)["name"]  # type: ignore[index]
    if rfi.rfi_manager_user_id and rfi.assignees is not None:
        from ..extensions import db as _db

        m = _db.session.get(User, rfi.rfi_manager_user_id)
        if m is not None:
            return _user_label(m)["name"]  # type: ignore[index]
    return rfi.ball_in_court or ""


def rfi_public(rfi: Rfi, *, include_detail: bool = False, cu: Optional[CurrentUser] = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": str(rfi.id),
        "project_id": str(rfi.project_id),
        "number": rfi.number,
        "prefix": rfi.prefix,
        "revision_index": rfi.revision_index,
        "display_number": _format_display_number(rfi),
        "subject": rfi.subject,
        "status": rfi.status,
        "is_private": rfi.is_private,
        "is_deleted": rfi.is_deleted,
        "ball_in_court": _resolve_ball_in_court_label(rfi),
        "due_at": _iso(rfi.due_at),
        "date_initiated_at": _iso(rfi.date_initiated_at),
        "closed_at": _iso(rfi.closed_at),
        "cost_impact_choice": rfi.cost_impact_choice,
        "cost_impact": _decimal(rfi.cost_impact),
        "schedule_impact_choice": rfi.schedule_impact_choice,
        "schedule_impact_days": rfi.schedule_impact_days,
        "reference_text": rfi.reference_text,
        "drawing_number_text": rfi.drawing_number_text,
        "created_at": _iso(rfi.created_at),
        "updated_at": _iso(rfi.updated_at),
        "assignees": [
            {
                "id": str(a.id),
                "user": _user_label(a.user),
                "is_required": a.is_required,
                "ball_in_court": a.ball_in_court,
                "responded_at": _iso(a.responded_at),
            }
            for a in (rfi.assignees or [])
        ],
        "rfi_manager": _user_label(
            db.session.get(User, rfi.rfi_manager_user_id) if rfi.rfi_manager_user_id else None
        ),
        "received_from": _user_label(
            db.session.get(User, rfi.received_from_user_id) if rfi.received_from_user_id else None
        ),
        "responsible_contractor": _company_label(
            db.session.get(Company, rfi.responsible_contractor_company_id)
            if rfi.responsible_contractor_company_id
            else None
        ),
        "created_by": _user_label(
            db.session.get(User, rfi.created_by_user_id) if rfi.created_by_user_id else None
        ),
        "location_id": str(rfi.location_id) if rfi.location_id else None,
        "spec_section_id": str(rfi.spec_section_id) if rfi.spec_section_id else None,
        "cost_code_id": str(rfi.cost_code_id) if rfi.cost_code_id else None,
        "project_stage_id": str(rfi.project_stage_id) if rfi.project_stage_id else None,
        "sub_job_id": str(rfi.sub_job_id) if rfi.sub_job_id else None,
        "drawing_id": str(rfi.drawing_id) if rfi.drawing_id else None,
        "official_response_reply_id": (
            str(rfi.official_response_reply_id) if rfi.official_response_reply_id else None
        ),
    }
    if not include_detail:
        return payload

    # Detail-only fields
    payload.update(
        {
            "question": rfi.question,
            "general_information": rfi.general_information,
            "official_response": rfi.official_response,
            "distribution": [
                {"id": str(d.id), "user": _user_label(d.user)}
                for d in (rfi.distribution or [])
            ],
            "replies": [
                {
                    "id": str(r.id),
                    "author": _user_label(r.author),
                    "body": r.body,
                    "is_official": r.is_official,
                    "is_deleted": r.is_deleted,
                    "created_at": _iso(r.created_at),
                }
                for r in (rfi.replies or [])
                if not r.is_deleted
            ],
            "audit": [
                {
                    "id": str(a.id),
                    "actor": _user_label(a.actor),
                    "action": a.action,
                    "summary": a.summary,
                    "before": a.before_json,
                    "after": a.after_json,
                    "created_at": _iso(a.created_at),
                }
                for a in (rfi.audit_entries or [])
            ],
            "custom_fields": [
                _custom_field_value_public(v) for v in (rfi.custom_values or [])
            ],
            "attachments": _attachments_for(rfi.id),
            "revisions": _revisions_for(rfi.id),
        }
    )
    if cu is not None:
        payload["permissions"] = explain_rfi(cu, rfi)
    return payload


def _format_display_number(rfi: Rfi) -> str:
    prefix = (rfi.prefix or "RFI").strip() or "RFI"
    rev = f"-R{rfi.revision_index}" if (rfi.revision_index or 0) > 0 else ""
    return f"{prefix}-{rfi.number:03d}{rev}"


def _custom_field_value_public(v: RfiCustomFieldValue) -> dict[str, Any]:
    return {
        "id": str(v.id),
        "field_def_id": str(v.field_def_id),
        "key": v.field_def.key if v.field_def else None,
        "label": v.field_def.label if v.field_def else None,
        "field_type": v.field_def.field_type if v.field_def else None,
        "value_text": v.value_text,
        "value_number": _decimal(v.value_number),
        "value_date": _iso(v.value_date),
        "value_bool": v.value_bool,
    }


def _attachments_for(rfi_id: uuid.UUID) -> list[dict[str, Any]]:
    """Return the RFI's attachments.

    Uses raw JSONB containment so we don't depend on polymorphic loading
    (some legacy rows may carry ``document_type='rfi'`` without a matching
    subclass mapper, which would break ``select(Document)``).
    """
    from sqlalchemy import text

    rows = db.session.execute(
        text(
            "SELECT id, title, original_filename, file_url, mime_type, "
            "file_size_bytes, created_at "
            "FROM documents "
            "WHERE tags ? 'rfi_id' AND tags->>'rfi_id' = :rid "
            "ORDER BY created_at ASC"
        ),
        {"rid": str(rfi_id)},
    ).all()
    return [
        {
            "id": str(r[0]),
            "title": r[1],
            "filename": r[2],
            "file_url": r[3],
            "mime_type": r[4],
            "file_size_bytes": r[5],
            "created_at": _iso(r[6]),
        }
        for r in rows
    ]


def _revisions_for(rfi_id: uuid.UUID) -> list[dict[str, Any]]:
    rows = db.session.scalars(
        select(RfiRevision).where(RfiRevision.rfi_id == rfi_id).order_by(RfiRevision.revision_index.asc())
    ).all()
    return [
        {
            "id": str(r.id),
            "revision_index": r.revision_index,
            "actor_user_id": str(r.actor_user_id) if r.actor_user_id else None,
            "reason": r.reason,
            "payload": r.payload_json,
            "created_at": _iso(r.created_at),
        }
        for r in rows
    ]


def reply_public(r: RfiReply) -> dict[str, Any]:
    return {
        "id": str(r.id),
        "rfi_id": str(r.rfi_id),
        "author": _user_label(r.author),
        "body": r.body,
        "is_official": r.is_official,
        "is_deleted": r.is_deleted,
        "created_at": _iso(r.created_at),
    }


# ---------------------------------------------------------------------------
# Lookups
# ---------------------------------------------------------------------------


def lookup_public(row: Any) -> dict[str, Any]:
    out = {"id": str(row.id), "project_id": str(row.project_id)}
    for attr in ("name", "code", "title", "description", "path", "prefix", "sort_order"):
        if hasattr(row, attr):
            out[attr] = getattr(row, attr)
    if hasattr(row, "pdf_url"):
        pu = getattr(row, "pdf_url")
        if pu is not None:
            out["pdf_url"] = pu
    if hasattr(row, "is_active"):
        out["is_active"] = bool(getattr(row, "is_active"))
    return out


def list_lookup(project_id: uuid.UUID, kind: str) -> list[dict[str, Any]]:
    Model = {
        "locations": Location,
        "spec_sections": SpecSection,
        "cost_codes": CostCode,
        "project_stages": ProjectStage,
        "sub_jobs": SubJob,
    }.get(kind)
    if Model is None:
        raise ApiError(f"unknown lookup: {kind}", 400)
    rows = db.session.scalars(
        select(Model).where(Model.project_id == project_id).order_by(getattr(Model, "sort_order", Model.created_at).asc() if hasattr(Model, "sort_order") else Model.created_at.asc())
    ).all()
    return [lookup_public(r) for r in rows]


def create_lookup(project_id: uuid.UUID, kind: str, data: Mapping[str, Any]) -> dict[str, Any]:
    Model = {
        "locations": Location,
        "spec_sections": SpecSection,
        "cost_codes": CostCode,
        "project_stages": ProjectStage,
        "sub_jobs": SubJob,
    }.get(kind)
    if Model is None:
        raise ApiError(f"unknown lookup: {kind}", 400)
    row = Model(project_id=project_id)
    for k, v in data.items():
        if hasattr(row, k):
            setattr(row, k, v)
    if isinstance(row, Location) and not row.path:
        row.path = row.name
    db.session.add(row)
    db.session.commit()
    return lookup_public(row)


def patch_lookup(project_id: uuid.UUID, kind: str, row_id: uuid.UUID, data: Mapping[str, Any]) -> dict[str, Any]:
    Model = {
        "locations": Location,
        "spec_sections": SpecSection,
        "cost_codes": CostCode,
        "project_stages": ProjectStage,
        "sub_jobs": SubJob,
    }.get(kind)
    if Model is None:
        raise ApiError(f"unknown lookup: {kind}", 400)
    allowed = {
        "locations": {"name", "path", "parent_id", "is_active"},
        "spec_sections": {"code", "title", "is_active", "pdf_url"},
        "cost_codes": {"code", "description", "is_active"},
        "project_stages": {"code", "name", "prefix", "sort_order", "is_active"},
        "sub_jobs": {"code", "name", "is_active"},
    }.get(kind, set())
    row = db.session.get(Model, row_id)
    if row is None:
        raise ApiError("lookup row not found", 404)
    if row.project_id != project_id:
        raise ApiError("lookup row not in this project", 404)
    for k, v in data.items():
        if k not in allowed:
            continue
        if not hasattr(row, k):
            continue
        if k == "parent_id":
            row.parent_id = _parse_uuid(str(v)) if v not in (None, "") else None
        elif k == "is_active":
            row.is_active = bool(v)
        elif k == "sort_order":
            row.sort_order = int(v)
        elif k in ("code", "title", "name", "description", "path", "prefix", "pdf_url"):
            s = (str(v).strip() if v is not None else "") or None
            if k == "pdf_url" and s is not None and len(s) > 1024:
                s = s[:1024]
            setattr(row, k, s)
    db.session.commit()
    return lookup_public(row)


# ---------------------------------------------------------------------------
# Permission gates
# ---------------------------------------------------------------------------


def _require_view(cu: CurrentUser, rfi: Rfi) -> None:
    if not can_view_rfi(cu, rfi):
        raise ApiError("not authorized to view this RFI", 403)


def _require_edit(cu: CurrentUser, rfi: Rfi) -> None:
    if not can_edit_rfi(cu, rfi):
        raise ApiError("not authorized to edit this RFI", 403)


# ---------------------------------------------------------------------------
# Audit + notifications
# ---------------------------------------------------------------------------


def _audit(rfi: Rfi, cu: CurrentUser, action: str, summary: str = "", before: Any = None, after: Any = None) -> None:
    db.session.add(
        RfiAudit(
            rfi_id=rfi.id,
            actor_user_id=cu.id,
            action=action,
            summary=summary[:500] if summary else None,
            before_json=_jsonable(before) if before is not None else None,
            after_json=_jsonable(after) if after is not None else None,
        )
    )


def _jsonable(obj: Any) -> Any:
    if obj is None:
        return None
    if isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, (datetime,)):
        return _iso(obj)
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, uuid.UUID):
        return str(obj)
    if isinstance(obj, Mapping):
        return {str(k): _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set, frozenset)):
        return [_jsonable(v) for v in obj]
    return str(obj)


def _notify(rfi: Rfi, event: str, recipients: Iterable[User], cu: CurrentUser) -> None:
    """Phase 3: enqueue email notifications.

    For now (without Celery wired in) this just writes a row to
    ``rfi_notification_log`` so the front-end can show the notification
    history. ``notifications.send_rfi_email`` (added by phase 3) becomes
    the actual sender.
    """
    from ._notifications import enqueue_rfi_email

    for u in recipients:
        if not u or not u.email:
            continue
        log = RfiNotificationLog(
            rfi_id=rfi.id,
            event=event,
            recipient_email=u.email,
            recipient_user_id=u.id,
            subject=f"[RFI {_format_display_number(rfi)}] {rfi.subject}",
            body_preview=(rfi.question or "")[:500],
        )
        db.session.add(log)
        db.session.flush()
        enqueue_rfi_email(log, rfi=rfi, actor=cu)


# ---------------------------------------------------------------------------
# Lookups + helpers used by create/patch
# ---------------------------------------------------------------------------


def _project(project_id: uuid.UUID) -> Project:
    p = db.session.get(Project, project_id)
    if p is None or p.deleted_at is not None:
        raise ApiError("project not found", 404)
    return p


def _resolve_lookup(model: type, project_id: uuid.UUID, raw: Any) -> Optional[uuid.UUID]:
    if raw in (None, ""):
        return None
    uid = _parse_uuid(raw)
    if uid is None:
        return None
    row = db.session.scalar(select(model).where(model.id == uid, model.project_id == project_id))
    if row is None:
        raise ApiError(f"{model.__tablename__} {raw} not found in project", 400)
    return row.id


def _resolve_user(raw: Any) -> Optional[uuid.UUID]:
    uid = _parse_uuid(raw)
    if uid is None:
        return None
    row = db.session.get(User, uid)
    if row is None:
        raise ApiError(f"user {raw} not found", 400)
    return row.id


def _resolve_company(raw: Any) -> Optional[uuid.UUID]:
    uid = _parse_uuid(raw)
    if uid is None:
        return None
    row = db.session.get(Company, uid)
    if row is None:
        raise ApiError(f"company {raw} not found", 400)
    return row.id


def _next_number(project_id: uuid.UUID) -> int:
    m = db.session.scalar(
        select(func.coalesce(func.max(Rfi.number), 0)).where(Rfi.project_id == project_id)
    )
    return int(m or 0) + 1


def _contact_company_id_for_user(user_id: uuid.UUID) -> Optional[uuid.UUID]:
    """Match ``User.email`` to a ``Contact`` row and return that contact's company (Procore-style)."""
    u = db.session.get(User, user_id)
    if u is None or not (u.email or "").strip():
        return None
    email = (u.email or "").strip().lower()
    row = db.session.scalar(
        select(Contact.company_id)
        .where(
            func.lower(func.coalesce(Contact.email, "")) == email,
            Contact.company_id.isnot(None),
        )
        .limit(1)
    )
    return row


def _autofill_responsible_contractor(rfi: Rfi, data: Mapping[str, Any], *, partial: bool) -> None:
    if not rfi.received_from_user_id:
        return
    if partial and "responsible_contractor_company_id" in data:
        raw = data.get("responsible_contractor_company_id")
        if raw not in (None, ""):
            return
    elif partial and "received_from_user_id" not in data:
        return
    cid = _contact_company_id_for_user(rfi.received_from_user_id)
    if cid is not None:
        rfi.responsible_contractor_company_id = cid


def _merged_field_requirements(project_id: uuid.UUID) -> dict[str, str]:
    """Global (``project_id`` NULL) rows first, then project-specific overrides."""
    rows = list(
        db.session.scalars(
            select(RfiConfigurableField).where(
                or_(RfiConfigurableField.project_id == project_id, RfiConfigurableField.project_id.is_(None))
            )
        ).all()
    )
    out: dict[str, str] = {}
    for r in rows:
        if r.project_id is None:
            out[r.field_key] = r.requirement
    for r in rows:
        if r.project_id == project_id:
            out[r.field_key] = r.requirement
    return out


def _enforce_configurable_for_open(rfi: Rfi) -> None:
    """When an RFI is ``open``, enforce admin-configured required fields (server-side)."""
    reqs = _merged_field_requirements(rfi.project_id)
    missing: list[str] = []

    def _req(key: str, ok: bool) -> None:
        if reqs.get(key) != "required":
            return
        if not ok:
            missing.append(key)

    _req("subject", bool(rfi.subject and rfi.subject.strip()))
    _req("question", bool(rfi.question and rfi.question.strip()))
    _req("due_date", rfi.due_at is not None)
    _req("assignees", bool(rfi.assignees))
    _req("rfi_manager", rfi.rfi_manager_user_id is not None)
    _req("received_from", rfi.received_from_user_id is not None)
    _req("responsible_contractor", rfi.responsible_contractor_company_id is not None)
    _req("drawing_number", bool(rfi.drawing_number_text and str(rfi.drawing_number_text).strip()))
    _req("location", rfi.location_id is not None)
    _req("spec_section", rfi.spec_section_id is not None)
    _req("cost_code", rfi.cost_code_id is not None)
    _req("project_stage", rfi.project_stage_id is not None)
    _req("sub_job", rfi.sub_job_id is not None)
    _req("distribution", bool(rfi.distribution))
    _req("cost_impact", bool(rfi.cost_impact_choice and str(rfi.cost_impact_choice).strip()))
    _req("schedule_impact", bool(rfi.schedule_impact_choice and str(rfi.schedule_impact_choice).strip()))
    _req("reference", bool(rfi.reference_text and str(rfi.reference_text).strip()))

    if missing:
        raise ApiError("missing configurable required fields for Open: " + ", ".join(sorted(set(missing))), 400)


def _apply_payload(rfi: Rfi, data: Mapping[str, Any], *, partial: bool, project_id: uuid.UUID) -> None:
    def _set(field: str, value: Any) -> None:
        setattr(rfi, field, value)

    if not partial or "subject" in data:
        v = data.get("subject")
        if v is None or not str(v).strip():
            if not partial:
                raise ApiError("subject is required", 400)
        else:
            _set("subject", str(v)[:500])

    if not partial or "question" in data:
        v = data.get("question")
        _set("question", str(v) if v is not None else None)

    if not partial or "general_information" in data:
        v = data.get("general_information")
        _set("general_information", str(v) if v is not None else None)

    if not partial or "reference_text" in data:
        v = data.get("reference_text")
        _set("reference_text", str(v)[:500] if v is not None else None)

    if not partial or "is_private" in data:
        _set("is_private", _parse_bool(data.get("is_private"), default=False))

    if not partial or "due_at" in data:
        _set("due_at", _parse_dt(data.get("due_at")))

    if not partial or "cost_impact_choice" in data:
        _set("cost_impact_choice", _normalize_impact_choice(data.get("cost_impact_choice")))
    if not partial or "cost_impact" in data:
        _set("cost_impact", _parse_decimal(data.get("cost_impact")))

    if not partial or "schedule_impact_choice" in data:
        _set("schedule_impact_choice", _normalize_impact_choice(data.get("schedule_impact_choice")))
    if not partial or "schedule_impact_days" in data:
        _set("schedule_impact_days", _parse_int(data.get("schedule_impact_days")))

    if "rfi_manager_user_id" in data:
        _set("rfi_manager_user_id", _resolve_user(data.get("rfi_manager_user_id")))
    if "received_from_user_id" in data:
        _set("received_from_user_id", _resolve_user(data.get("received_from_user_id")))
    if "responsible_contractor_company_id" in data:
        _set(
            "responsible_contractor_company_id",
            _resolve_company(data.get("responsible_contractor_company_id")),
        )

    if "location_id" in data:
        _set("location_id", _resolve_lookup(Location, project_id, data.get("location_id")))
    if "spec_section_id" in data:
        _set("spec_section_id", _resolve_lookup(SpecSection, project_id, data.get("spec_section_id")))
    if "cost_code_id" in data:
        _set("cost_code_id", _resolve_lookup(CostCode, project_id, data.get("cost_code_id")))
    if "project_stage_id" in data:
        _set("project_stage_id", _resolve_lookup(ProjectStage, project_id, data.get("project_stage_id")))
    if "sub_job_id" in data:
        _set("sub_job_id", _resolve_lookup(SubJob, project_id, data.get("sub_job_id")))

    if "drawing_id" in data:
        v = _parse_uuid(data.get("drawing_id"))
        if v is not None and db.session.get(Drawing, v) is None:
            raise ApiError("drawing not found", 400)
        _set("drawing_id", v)
    if "drawing_number_text" in data:
        v = data.get("drawing_number_text")
        _set("drawing_number_text", str(v)[:120] if v is not None else None)

    if "prefix" in data:
        v = data.get("prefix")
        _set("prefix", str(v)[:20].strip() if v else None)


def _set_assignees(rfi: Rfi, raw: Any) -> None:
    if raw is None:
        return
    if not isinstance(raw, (list, tuple)):
        raise ApiError("assignees must be a list", 400)
    existing = {a.user_id: a for a in (rfi.assignees or [])}
    seen: set[uuid.UUID] = set()
    for entry in raw:
        uid_raw = entry.get("user_id") if isinstance(entry, Mapping) else entry
        uid = _resolve_user(uid_raw)
        if uid is None:
            continue
        required = (
            _parse_bool(entry.get("is_required"), default=False)
            if isinstance(entry, Mapping)
            else False
        )
        if uid in existing:
            existing[uid].is_required = required
        else:
            rfi.assignees.append(
                RfiAssignee(rfi_id=rfi.id, user_id=uid, is_required=required, ball_in_court=False)
            )
        seen.add(uid)
    for uid, row in list(existing.items()):
        if uid not in seen:
            rfi.assignees.remove(row)
            db.session.delete(row)


def _set_distribution(rfi: Rfi, raw: Any) -> None:
    if raw is None:
        return
    if not isinstance(raw, (list, tuple)):
        raise ApiError("distribution must be a list", 400)
    existing = {d.user_id: d for d in (rfi.distribution or [])}
    seen: set[uuid.UUID] = set()
    for entry in raw:
        uid_raw = entry.get("user_id") if isinstance(entry, Mapping) else entry
        uid = _resolve_user(uid_raw)
        if uid is None:
            continue
        if uid not in existing:
            rfi.distribution.append(RfiDistribution(rfi_id=rfi.id, user_id=uid))
        seen.add(uid)
    for uid, row in list(existing.items()):
        if uid not in seen:
            rfi.distribution.remove(row)
            db.session.delete(row)


def _initial_ball_in_court(rfi: Rfi) -> None:
    """When ``open``, a single assignee holds ball-in-court (first required, else first listed)."""

    if rfi.status != "open":
        for a in rfi.assignees:
            a.ball_in_court = False
        rfi.ball_in_court = None
        return
    if not rfi.assignees:
        rfi.ball_in_court = None
        return
    primary = next((a for a in rfi.assignees if a.is_required), None)
    if primary is None:
        primary = rfi.assignees[0]
    for a in rfi.assignees:
        a.ball_in_court = a.user_id == primary.user_id
    rfi.ball_in_court = None


def _validate_for_open(rfi: Rfi) -> None:
    """Procore: Number, Subject, Assignees, Due Date, Question are
    required to save in ``Open``."""
    missing: list[str] = []
    if not rfi.number:
        missing.append("number")
    if not (rfi.subject and rfi.subject.strip()):
        missing.append("subject")
    if not rfi.assignees:
        missing.append("assignees")
    if not rfi.due_at:
        missing.append("due_at")
    if not (rfi.question and rfi.question.strip()):
        missing.append("question")
    if missing:
        raise ApiError(
            "missing required fields for Open: " + ", ".join(missing), 400
        )


# ---------------------------------------------------------------------------
# Create / Read / Update / Delete
# ---------------------------------------------------------------------------


@dataclass
class ListFilters:
    status: Optional[list[str]] = None
    assignee: Optional[uuid.UUID] = None
    manager: Optional[uuid.UUID] = None
    in_recycle_bin: bool = False
    q: Optional[str] = None
    sort: str = "number_asc"
    limit: int = 200
    offset: int = 0


def list_rfis(project_id: uuid.UUID, filters: ListFilters, cu: CurrentUser) -> dict[str, Any]:
    _project(project_id)
    q = select(Rfi).where(Rfi.project_id == project_id)
    if filters.in_recycle_bin:
        q = q.where(Rfi.is_deleted.is_(True))
    else:
        q = q.where(Rfi.is_deleted.is_(False))
    if filters.status:
        q = q.where(Rfi.status.in_(filters.status))
    if filters.assignee:
        q = q.join(RfiAssignee, RfiAssignee.rfi_id == Rfi.id).where(
            RfiAssignee.user_id == filters.assignee
        )
    if filters.manager:
        q = q.where(Rfi.rfi_manager_user_id == filters.manager)
    if filters.q:
        like = f"%{filters.q.strip().lower()}%"
        q = q.where(
            or_(
                func.lower(Rfi.subject).like(like),
                func.lower(func.coalesce(Rfi.question, "")).like(like),
                func.lower(func.coalesce(Rfi.reference_text, "")).like(like),
            )
        )

    sort_map = {
        "number_asc": Rfi.number.asc(),
        "number_desc": Rfi.number.desc(),
        "due_asc": Rfi.due_at.asc().nullslast(),
        "due_desc": Rfi.due_at.desc().nullslast(),
        "updated_desc": Rfi.updated_at.desc(),
        "created_desc": Rfi.created_at.desc(),
        "subject_asc": Rfi.subject.asc(),
    }
    q = q.order_by(sort_map.get(filters.sort, Rfi.number.asc()))
    total = db.session.scalar(select(func.count()).select_from(q.subquery())) or 0
    q = q.offset(max(0, filters.offset)).limit(max(1, min(filters.limit, 1000)))
    rows = db.session.scalars(q).all()
    items = [rfi_public(r) for r in rows if can_view_rfi(cu, r)]
    return {
        "items": items,
        "total": total,
        "limit": filters.limit,
        "offset": filters.offset,
        "entity": "rfis",
    }


def get_rfi(rfi_id: uuid.UUID, cu: CurrentUser) -> dict[str, Any]:
    r = db.session.get(Rfi, rfi_id)
    if r is None:
        raise ApiError("RFI not found", 404)
    _require_view(cu, r)
    return {"item": rfi_public(r, include_detail=True, cu=cu), "entity": "rfi"}


def create_rfi(project_id: uuid.UUID, data: Mapping[str, Any], cu: CurrentUser) -> dict[str, Any]:
    project = _project(project_id)
    if not can_create_rfi(cu):
        raise ApiError("not authorized to create RFIs", 403)

    target_status_raw = (data.get("status") or "draft").strip().lower()
    if target_status_raw not in RFI_STATUSES:
        raise ApiError("invalid status", 400)
    if target_status_raw == "open" and not can_create_open_rfi(cu):
        target_status_raw = "draft"

    number_in = data.get("number")
    number = _parse_int(number_in) if number_in not in (None, "") else _next_number(project_id)
    if number is None:
        raise ApiError("invalid number", 400)
    if db.session.scalar(
        select(Rfi.id).where(Rfi.project_id == project_id, Rfi.number == number, Rfi.revision_index == 0)
    ):
        raise ApiError(f"RFI {number} already exists for this project", 409)

    rfi = Rfi(
        project_id=project_id,
        number=number,
        revision_index=0,
        status="draft",
        subject="",
        created_by_user_id=cu.id,
    )
    _apply_payload(rfi, data, partial=False, project_id=project_id)
    db.session.add(rfi)
    db.session.flush()

    _set_assignees(rfi, data.get("assignees"))
    _set_distribution(rfi, data.get("distribution"))

    if not rfi.rfi_manager_user_id and rfi.created_by_user_id:
        rfi.rfi_manager_user_id = rfi.created_by_user_id

    _autofill_responsible_contractor(rfi, data, partial=False)

    if target_status_raw == "open":
        rfi.status = "open"
        rfi.date_initiated_at = _utcnow()
        _enforce_configurable_for_open(rfi)
        _validate_for_open(rfi)
    _initial_ball_in_court(rfi)

    _audit(rfi, cu, "create", summary=f"Created RFI {_format_display_number(rfi)} as {rfi.status}")
    db.session.commit()

    recipients = _notification_targets(rfi, "created")
    _notify(rfi, "created", recipients, cu)
    db.session.commit()

    return {"item": rfi_public(rfi, include_detail=True, cu=cu), "entity": "rfi"}


def patch_rfi(rfi_id: uuid.UUID, data: Mapping[str, Any], cu: CurrentUser) -> dict[str, Any]:
    rfi = db.session.get(Rfi, rfi_id)
    if rfi is None:
        raise ApiError("RFI not found", 404)
    _require_edit(cu, rfi)

    before = rfi_public(rfi, include_detail=False)
    prev_status = rfi.status
    status_in = data.get("status")
    if status_in is not None:
        new_st = str(status_in).strip().lower()
        if new_st not in RFI_STATUSES:
            raise ApiError("invalid status", 400)
        if new_st != prev_status:
            if prev_status == "draft" and new_st == "open":
                if not can_create_open_rfi(cu):
                    raise ApiError("not authorized to move RFI to Open", 403)
            elif new_st == "closed" or new_st == "closed_draft":
                raise ApiError("use POST /rfis/<id>/close to close an RFI", 400)
            elif prev_status == "open" and new_st == "draft":
                raise ApiError("cannot revert Open RFI to Draft", 400)
            else:
                raise ApiError("unsupported status transition", 400)

    _apply_payload(rfi, data, partial=True, project_id=rfi.project_id)
    if "assignees" in data:
        _set_assignees(rfi, data.get("assignees"))
    if "distribution" in data:
        _set_distribution(rfi, data.get("distribution"))

    _autofill_responsible_contractor(rfi, data, partial=True)

    if status_in is not None:
        new_st = str(status_in).strip().lower()
        if new_st != prev_status and prev_status == "draft" and new_st == "open":
            rfi.status = "open"
            rfi.date_initiated_at = rfi.date_initiated_at or _utcnow()
            _enforce_configurable_for_open(rfi)
            _validate_for_open(rfi)
            _initial_ball_in_court(rfi)
            recipients = _notification_targets(rfi, "created")
            _notify(rfi, "created", recipients, cu)

    if rfi.status == "open":
        _enforce_configurable_for_open(rfi)

    _audit(rfi, cu, "edit", summary="Edited RFI", before=before, after=rfi_public(rfi))
    db.session.commit()
    return {"item": rfi_public(rfi, include_detail=True, cu=cu), "entity": "rfi"}


def delete_rfi(rfi_id: uuid.UUID, cu: CurrentUser) -> dict[str, Any]:
    rfi = db.session.get(Rfi, rfi_id)
    if rfi is None:
        raise ApiError("RFI not found", 404)
    if not can_delete_rfi(cu, rfi):
        raise ApiError("not authorized", 403)
    rfi.is_deleted = True
    rfi.deleted_at = _utcnow()
    _audit(rfi, cu, "delete", summary="Moved RFI to Recycle Bin")
    db.session.commit()
    return {"ok": True}


def restore_rfi(rfi_id: uuid.UUID, cu: CurrentUser) -> dict[str, Any]:
    rfi = db.session.get(Rfi, rfi_id)
    if rfi is None:
        raise ApiError("RFI not found", 404)
    if not can_restore_rfi(cu, rfi):
        raise ApiError("not authorized", 403)
    rfi.is_deleted = False
    rfi.deleted_at = None
    _audit(rfi, cu, "restore", summary="Restored from Recycle Bin")
    db.session.commit()
    return {"item": rfi_public(rfi, include_detail=True, cu=cu), "entity": "rfi"}


# ---------------------------------------------------------------------------
# Workflow: replies, official response, ball-in-court, close/reopen, forward
# ---------------------------------------------------------------------------


def add_reply(rfi_id: uuid.UUID, body: str, cu: CurrentUser) -> dict[str, Any]:
    rfi = db.session.get(Rfi, rfi_id)
    if rfi is None:
        raise ApiError("RFI not found", 404)
    if not can_reply(cu, rfi):
        raise ApiError("not authorized to reply", 403)
    body = (body or "").strip()
    if not body:
        raise ApiError("reply body is required", 400)

    reply = RfiReply(rfi_id=rfi.id, author_user_id=cu.id, body=body, is_official=False)
    db.session.add(reply)
    db.session.flush()

    # Mark the assignee as responded; shift ball-in-court back to manager.
    now = _utcnow()
    for a in rfi.assignees:
        if a.user_id == cu.id:
            a.responded_at = now
        a.ball_in_court = False
    rfi.ball_in_court = None  # manager holds it now

    _audit(rfi, cu, "reply_add", summary="Replied to RFI", after={"reply_id": str(reply.id)})

    recipients = _notification_targets(rfi, "reply")
    _notify(rfi, "reply", recipients, cu)

    db.session.commit()
    return {"item": reply_public(reply), "entity": "rfi_reply"}


def delete_reply(rfi_id: uuid.UUID, reply_id: uuid.UUID, cu: CurrentUser) -> dict[str, Any]:
    rfi = db.session.get(Rfi, rfi_id)
    if rfi is None:
        raise ApiError("RFI not found", 404)
    reply = db.session.get(RfiReply, reply_id)
    if reply is None or reply.rfi_id != rfi.id:
        raise ApiError("reply not found", 404)
    if not can_act_as_manager(cu, rfi) and reply.author_user_id != cu.id:
        raise ApiError("not authorized", 403)
    reply.is_deleted = True
    _audit(rfi, cu, "reply_delete", summary="Deleted reply", before={"reply_id": str(reply.id)})
    db.session.commit()
    return {"ok": True}


def set_official_response(rfi_id: uuid.UUID, reply_id: uuid.UUID, cu: CurrentUser) -> dict[str, Any]:
    rfi = db.session.get(Rfi, rfi_id)
    if rfi is None:
        raise ApiError("RFI not found", 404)
    if not can_mark_official(cu, rfi):
        raise ApiError("not authorized", 403)
    reply = db.session.get(RfiReply, reply_id)
    if reply is None or reply.rfi_id != rfi.id or reply.is_deleted:
        raise ApiError("reply not found", 404)

    for r in rfi.replies:
        r.is_official = r.id == reply.id
    rfi.official_response_reply_id = reply.id
    rfi.official_response = reply.body

    _audit(
        rfi,
        cu,
        "official_response_set",
        summary="Marked Official Response",
        after={"reply_id": str(reply.id)},
    )
    recipients = _notification_targets(rfi, "official_response")
    _notify(rfi, "official_response", recipients, cu)

    db.session.commit()
    return {"item": rfi_public(rfi, include_detail=True, cu=cu), "entity": "rfi"}


def close_rfi(rfi_id: uuid.UUID, cu: CurrentUser) -> dict[str, Any]:
    rfi = db.session.get(Rfi, rfi_id)
    if rfi is None:
        raise ApiError("RFI not found", 404)
    if not can_close_or_reopen(cu, rfi):
        raise ApiError("not authorized", 403)
    if rfi.status in ("closed", "closed_draft"):
        return {"item": rfi_public(rfi, include_detail=True, cu=cu), "entity": "rfi"}
    new_status = "closed_draft" if rfi.status == "draft" else "closed"
    before_status = rfi.status
    rfi.status = new_status
    rfi.closed_at = _utcnow()
    for a in rfi.assignees:
        a.ball_in_court = False
    _audit(
        rfi,
        cu,
        "close",
        summary=f"Closed RFI ({before_status} -> {new_status})",
        before={"status": before_status},
        after={"status": new_status},
    )
    recipients = _notification_targets(rfi, "closed")
    _notify(rfi, "closed", recipients, cu)
    db.session.commit()
    return {"item": rfi_public(rfi, include_detail=True, cu=cu), "entity": "rfi"}


def reopen_rfi(rfi_id: uuid.UUID, cu: CurrentUser) -> dict[str, Any]:
    rfi = db.session.get(Rfi, rfi_id)
    if rfi is None:
        raise ApiError("RFI not found", 404)
    if not can_close_or_reopen(cu, rfi):
        raise ApiError("not authorized", 403)
    if rfi.status not in ("closed", "closed_draft"):
        return {"item": rfi_public(rfi, include_detail=True, cu=cu), "entity": "rfi"}
    new_status = "draft" if rfi.status == "closed_draft" else "open"
    before_status = rfi.status
    rfi.status = new_status
    rfi.closed_at = None
    _initial_ball_in_court(rfi)
    _audit(
        rfi,
        cu,
        "reopen",
        summary=f"Reopened RFI ({before_status} -> {new_status})",
        before={"status": before_status},
        after={"status": new_status},
    )
    db.session.commit()
    return {"item": rfi_public(rfi, include_detail=True, cu=cu), "entity": "rfi"}


def shift_ball_in_court(
    rfi_id: uuid.UUID, target_user_id: Optional[uuid.UUID], cu: CurrentUser
) -> dict[str, Any]:
    rfi = db.session.get(Rfi, rfi_id)
    if rfi is None:
        raise ApiError("RFI not found", 404)
    if not can_shift_ball_in_court(cu, rfi):
        raise ApiError("not authorized", 403)

    if target_user_id is None:
        # Shift to RFI Manager
        for a in rfi.assignees:
            a.ball_in_court = False
        _audit(rfi, cu, "ball_in_court", summary="Shifted Ball in Court to RFI Manager")
    else:
        match = next((a for a in rfi.assignees if a.user_id == target_user_id), None)
        if match is None:
            match = RfiAssignee(rfi_id=rfi.id, user_id=target_user_id, ball_in_court=True)
            rfi.assignees.append(match)
        for a in rfi.assignees:
            a.ball_in_court = a.user_id == target_user_id
        _audit(
            rfi,
            cu,
            "ball_in_court",
            summary="Shifted Ball in Court",
            after={"user_id": str(target_user_id)},
        )
    db.session.commit()
    return {"item": rfi_public(rfi, include_detail=True, cu=cu), "entity": "rfi"}


def add_assignee(
    rfi_id: uuid.UUID, user_id: uuid.UUID, *, is_required: bool, cu: CurrentUser
) -> dict[str, Any]:
    rfi = db.session.get(Rfi, rfi_id)
    if rfi is None:
        raise ApiError("RFI not found", 404)
    if not can_add_assignee(cu, rfi):
        raise ApiError("not authorized", 403)
    if any(a.user_id == user_id for a in rfi.assignees):
        return {"item": rfi_public(rfi, include_detail=True, cu=cu), "entity": "rfi"}
    if db.session.get(User, user_id) is None:
        raise ApiError("user not found", 400)
    rfi.assignees.append(
        RfiAssignee(rfi_id=rfi.id, user_id=user_id, is_required=is_required, ball_in_court=False)
    )
    _audit(rfi, cu, "assignee_add", summary="Added assignee", after={"user_id": str(user_id)})
    db.session.commit()
    return {"item": rfi_public(rfi, include_detail=True, cu=cu), "entity": "rfi"}


def remove_assignee(rfi_id: uuid.UUID, user_id: uuid.UUID, cu: CurrentUser) -> dict[str, Any]:
    rfi = db.session.get(Rfi, rfi_id)
    if rfi is None:
        raise ApiError("RFI not found", 404)
    if not can_act_as_manager(cu, rfi):
        raise ApiError("not authorized", 403)
    match = next((a for a in rfi.assignees if a.user_id == user_id), None)
    if match is None:
        return {"item": rfi_public(rfi, include_detail=True, cu=cu), "entity": "rfi"}
    rfi.assignees.remove(match)
    db.session.delete(match)
    _audit(rfi, cu, "assignee_remove", summary="Removed assignee", before={"user_id": str(user_id)})
    db.session.commit()
    return {"item": rfi_public(rfi, include_detail=True, cu=cu), "entity": "rfi"}


def forward_for_review(
    rfi_id: uuid.UUID, user_id: uuid.UUID, message: Optional[str], cu: CurrentUser
) -> dict[str, Any]:
    rfi = db.session.get(Rfi, rfi_id)
    if rfi is None:
        raise ApiError("RFI not found", 404)
    if not can_forward(cu, rfi):
        raise ApiError("not authorized", 403)
    if db.session.get(User, user_id) is None:
        raise ApiError("user not found", 400)
    match = next((a for a in rfi.assignees if a.user_id == user_id), None)
    if match is None:
        match = RfiAssignee(rfi_id=rfi.id, user_id=user_id, is_required=False, ball_in_court=True)
        rfi.assignees.append(match)
    else:
        match.ball_in_court = True
    for a in rfi.assignees:
        if a.user_id != user_id:
            a.ball_in_court = False
    _audit(
        rfi,
        cu,
        "forward",
        summary="Forwarded for review",
        after={"user_id": str(user_id), "message": message or ""},
    )
    recipients_query = select(User).where(User.id == user_id)
    recipients = list(db.session.scalars(recipients_query).all())
    _notify(rfi, "forward", recipients, cu)
    db.session.commit()
    return {"item": rfi_public(rfi, include_detail=True, cu=cu), "entity": "rfi"}


def add_distribution(rfi_id: uuid.UUID, user_id: uuid.UUID, cu: CurrentUser) -> dict[str, Any]:
    rfi = db.session.get(Rfi, rfi_id)
    if rfi is None:
        raise ApiError("RFI not found", 404)
    if not can_act_as_manager(cu, rfi):
        raise ApiError("not authorized", 403)
    if any(d.user_id == user_id for d in rfi.distribution):
        return {"item": rfi_public(rfi, include_detail=True, cu=cu), "entity": "rfi"}
    if db.session.get(User, user_id) is None:
        raise ApiError("user not found", 400)
    rfi.distribution.append(RfiDistribution(rfi_id=rfi.id, user_id=user_id))
    _audit(rfi, cu, "distribution_add", summary="Added to distribution list", after={"user_id": str(user_id)})
    db.session.commit()
    return {"item": rfi_public(rfi, include_detail=True, cu=cu), "entity": "rfi"}


def remove_distribution(rfi_id: uuid.UUID, user_id: uuid.UUID, cu: CurrentUser) -> dict[str, Any]:
    rfi = db.session.get(Rfi, rfi_id)
    if rfi is None:
        raise ApiError("RFI not found", 404)
    if not can_act_as_manager(cu, rfi):
        raise ApiError("not authorized", 403)
    match = next((d for d in rfi.distribution if d.user_id == user_id), None)
    if match is None:
        return {"item": rfi_public(rfi, include_detail=True, cu=cu), "entity": "rfi"}
    rfi.distribution.remove(match)
    db.session.delete(match)
    _audit(rfi, cu, "distribution_remove", summary="Removed from distribution list", before={"user_id": str(user_id)})
    db.session.commit()
    return {"item": rfi_public(rfi, include_detail=True, cu=cu), "entity": "rfi"}


# ---------------------------------------------------------------------------
# Attachments + email forwarding
# ---------------------------------------------------------------------------


def add_attachment(rfi_id: uuid.UUID, data: Mapping[str, Any], cu: CurrentUser) -> dict[str, Any]:
    rfi = db.session.get(Rfi, rfi_id)
    if rfi is None:
        raise ApiError("RFI not found", 404)
    _require_view(cu, rfi)
    file_url = (data.get("file_url") or "").strip()
    title = (data.get("title") or "").strip() or None
    if not file_url:
        raise ApiError("file_url is required (use the upload endpoint to obtain one)", 400)
    # Use the ``other`` polymorphic identity so SQLAlchemy can hydrate it
    # back to a plain ``Document`` (there is no ``Document`` subclass with
    # ``polymorphic_identity='rfi'``). RFI-ness is captured by
    # ``tags['rfi_id']`` instead.
    doc = Document(
        project_id=rfi.project_id,
        document_type="other",
        title=title or file_url.rsplit("/", 1)[-1][:500],
        file_url=file_url[:1024],
        original_filename=(data.get("filename") or title or "").strip()[:500] or None,
        mime_type=(data.get("mime_type") or "").strip()[:120] or None,
        file_size_bytes=_parse_int(data.get("file_size_bytes")),
        uploaded_by_user_id=cu.id,
        tags={"rfi_id": str(rfi.id), "entity": "rfi"},
    )
    db.session.add(doc)
    db.session.flush()
    _audit(rfi, cu, "attachment_add", summary=f"Attached {doc.title or doc.file_url}", after={"document_id": str(doc.id)})
    db.session.commit()
    return {"item": {
        "id": str(doc.id),
        "title": doc.title,
        "file_url": doc.file_url,
        "filename": doc.original_filename,
        "mime_type": doc.mime_type,
        "file_size_bytes": doc.file_size_bytes,
        "created_at": _iso(doc.created_at),
    }, "entity": "rfi_attachment"}


def remove_attachment(rfi_id: uuid.UUID, document_id: uuid.UUID, cu: CurrentUser) -> dict[str, Any]:
    rfi = db.session.get(Rfi, rfi_id)
    if rfi is None:
        raise ApiError("RFI not found", 404)
    if not can_act_as_manager(cu, rfi):
        raise ApiError("not authorized", 403)
    from sqlalchemy import text

    row = db.session.execute(
        text("SELECT id FROM documents WHERE id = :id AND tags->>'rfi_id' = :rid"),
        {"id": str(document_id), "rid": str(rfi.id)},
    ).first()
    if row is None:
        raise ApiError("attachment not found", 404)
    doc = db.session.get(Document, document_id)
    if doc is not None and isinstance(doc.tags, dict):
        suf = doc.tags.get("suffix")
        if suf and doc.file_url and "/rfi-attachments/" in (doc.file_url or ""):
            from ..services.object_storage import UploadCategory, delete_stored

            delete_stored(UploadCategory.RFI_ATTACHMENTS, f"{document_id}{suf}")
    db.session.execute(text("DELETE FROM documents WHERE id = :id"), {"id": str(document_id)})
    _audit(rfi, cu, "attachment_remove", summary="Removed attachment", before={"document_id": str(document_id)})
    db.session.commit()
    return {"ok": True}


def forward_by_email(rfi_id: uuid.UUID, data: Mapping[str, Any], cu: CurrentUser) -> dict[str, Any]:
    rfi = db.session.get(Rfi, rfi_id)
    if rfi is None:
        raise ApiError("RFI not found", 404)
    if not can_view_rfi(cu, rfi):
        raise ApiError("not authorized", 403)
    to_raw = data.get("to") or []
    if isinstance(to_raw, str):
        to_raw = [s.strip() for s in to_raw.split(",") if s.strip()]
    if not isinstance(to_raw, list) or not to_raw:
        raise ApiError("'to' must be a non-empty list of email addresses", 400)
    cc_raw = data.get("cc") or []
    if isinstance(cc_raw, str):
        cc_raw = [s.strip() for s in cc_raw.split(",") if s.strip()]
    subject = (data.get("subject") or f"[RFI {_format_display_number(rfi)}] {rfi.subject}").strip()[:500]
    body = (data.get("message") or rfi.question or "").strip()

    from ._notifications import enqueue_email

    emails = [str(e).strip() for e in (to_raw + cc_raw) if str(e or "").strip()]
    sent = 0
    dry_run = False
    queued = False
    errors: list[str] = []
    for em in emails:
        log = RfiNotificationLog(
            rfi_id=rfi.id,
            event="forward_email",
            recipient_email=em[:255],
            subject=subject,
            body_preview=body[:500],
        )
        db.session.add(log)
        db.session.flush()
        result = enqueue_email(log, subject=subject, body=body, to=em)
        if result.get("dry_run"):
            dry_run = True
        if result.get("queued"):
            queued = True
        if result.get("sent"):
            sent += 1
        elif result.get("error"):
            errors.append(f"{em}: {result['error']}")
        elif result.get("dry_run"):
            sent += 1
    _audit(rfi, cu, "email_sent", summary=f"Emailed RFI to {len(emails)} recipient(s)")
    db.session.commit()
    return {
        "ok": True,
        "sent": sent,
        "recipients": len(emails),
        "dry_run": dry_run,
        "queued": queued,
        "errors": errors,
    }


# ---------------------------------------------------------------------------
# Saved views + column prefs
# ---------------------------------------------------------------------------


def list_saved_views(project_id: Optional[uuid.UUID], cu: CurrentUser) -> dict[str, Any]:
    q = select(RfiSavedView)
    if project_id is not None:
        q = q.where(or_(RfiSavedView.project_id == project_id, RfiSavedView.project_id.is_(None)))
    if cu.id is not None:
        q = q.where(
            or_(
                RfiSavedView.scope == "company",
                and_(RfiSavedView.scope == "user", RfiSavedView.owner_user_id == cu.id),
                and_(RfiSavedView.scope == "project", RfiSavedView.project_id == project_id),
            )
        )
    else:
        q = q.where(RfiSavedView.scope == "company")
    rows = db.session.scalars(q.order_by(RfiSavedView.name.asc())).all()
    return {"items": [_saved_view_public(r) for r in rows], "entity": "rfi_saved_views"}


def _saved_view_public(v: RfiSavedView) -> dict[str, Any]:
    return {
        "id": str(v.id),
        "name": v.name,
        "scope": v.scope,
        "owner_user_id": str(v.owner_user_id) if v.owner_user_id else None,
        "project_id": str(v.project_id) if v.project_id else None,
        "company_id": str(v.company_id) if v.company_id else None,
        "filters": v.filters,
        "sort": v.sort,
        "columns": v.columns,
        "is_default": v.is_default,
    }


def create_saved_view(data: Mapping[str, Any], cu: CurrentUser) -> dict[str, Any]:
    name = (data.get("name") or "").strip()
    if not name:
        raise ApiError("name is required", 400)
    scope = (data.get("scope") or "user").strip()
    if scope not in ("user", "project", "company"):
        raise ApiError("scope must be one of user/project/company", 400)
    v = RfiSavedView(
        name=name[:200],
        scope=scope,
        owner_user_id=cu.id if scope == "user" else None,
        project_id=_parse_uuid(data.get("project_id")) if scope != "company" else None,
        company_id=_parse_uuid(data.get("company_id")) if scope == "company" else None,
        filters=data.get("filters") or None,
        sort=data.get("sort") or None,
        columns=data.get("columns") or None,
        is_default=_parse_bool(data.get("is_default")),
    )
    db.session.add(v)
    db.session.commit()
    return {"item": _saved_view_public(v), "entity": "rfi_saved_view"}


def update_saved_view(view_id: uuid.UUID, data: Mapping[str, Any], cu: CurrentUser) -> dict[str, Any]:
    v = db.session.get(RfiSavedView, view_id)
    if v is None:
        raise ApiError("saved view not found", 404)
    if "name" in data and data["name"]:
        v.name = str(data["name"]).strip()[:200]
    for k in ("filters", "sort", "columns"):
        if k in data:
            setattr(v, k, data[k])
    if "is_default" in data:
        v.is_default = _parse_bool(data["is_default"])
    db.session.commit()
    return {"item": _saved_view_public(v), "entity": "rfi_saved_view"}


def delete_saved_view(view_id: uuid.UUID, cu: CurrentUser) -> dict[str, Any]:
    v = db.session.get(RfiSavedView, view_id)
    if v is None:
        return {"ok": True}
    db.session.delete(v)
    db.session.commit()
    return {"ok": True}


def get_column_prefs(scope_key: str, cu: CurrentUser) -> dict[str, Any]:
    if cu.id is None:
        return {"item": None, "entity": "rfi_column_pref"}
    row = db.session.scalar(
        select(RfiColumnPref).where(
            RfiColumnPref.user_id == cu.id, RfiColumnPref.scope_key == scope_key
        )
    )
    if row is None:
        return {"item": None, "entity": "rfi_column_pref"}
    return {
        "item": {
            "scope_key": row.scope_key,
            "columns": row.columns,
            "row_height": row.row_height,
        },
        "entity": "rfi_column_pref",
    }


def put_column_prefs(scope_key: str, data: Mapping[str, Any], cu: CurrentUser) -> dict[str, Any]:
    if cu.id is None:
        raise ApiError("authentication required", 401)
    row = db.session.scalar(
        select(RfiColumnPref).where(
            RfiColumnPref.user_id == cu.id, RfiColumnPref.scope_key == scope_key
        )
    )
    if row is None:
        row = RfiColumnPref(user_id=cu.id, scope_key=scope_key)
        db.session.add(row)
    row.columns = data.get("columns") or None
    row.row_height = (data.get("row_height") or "")[:20] or None
    db.session.commit()
    return {
        "item": {
            "scope_key": row.scope_key,
            "columns": row.columns,
            "row_height": row.row_height,
        },
        "entity": "rfi_column_pref",
    }


# ---------------------------------------------------------------------------
# Bulk + export
# ---------------------------------------------------------------------------


def bulk_action(data: Mapping[str, Any], cu: CurrentUser) -> dict[str, Any]:
    ids = data.get("rfi_ids") or []
    if not isinstance(ids, list) or not ids:
        raise ApiError("rfi_ids must be a non-empty list", 400)
    op = (data.get("op") or "").strip().lower()
    payload = data.get("payload") or {}
    affected = 0
    for raw in ids:
        rid = _parse_uuid(raw)
        if rid is None:
            continue
        rfi = db.session.get(Rfi, rid)
        if rfi is None:
            continue
        if op == "patch":
            if not can_edit_rfi(cu, rfi):
                continue
            _apply_payload(rfi, payload, partial=True, project_id=rfi.project_id)
            _audit(rfi, cu, "edit", summary="Bulk edit")
        elif op == "delete":
            if not can_delete_rfi(cu, rfi):
                continue
            rfi.is_deleted = True
            rfi.deleted_at = _utcnow()
            _audit(rfi, cu, "delete", summary="Bulk delete")
        elif op == "restore":
            if not can_restore_rfi(cu, rfi):
                continue
            rfi.is_deleted = False
            rfi.deleted_at = None
            _audit(rfi, cu, "restore", summary="Bulk restore")
        elif op == "close":
            if not can_close_or_reopen(cu, rfi):
                continue
            new_status = "closed_draft" if rfi.status == "draft" else "closed"
            rfi.status = new_status
            rfi.closed_at = _utcnow()
            _audit(rfi, cu, "close", summary="Bulk close")
        else:
            raise ApiError(f"unknown bulk op: {op}", 400)
        affected += 1
    db.session.commit()
    return {"ok": True, "affected": affected}


def export_rfis_csv(project_id: uuid.UUID, filters: ListFilters, cu: CurrentUser) -> str:
    payload = list_rfis(project_id, filters, cu)
    cols = [
        ("display_number", "#"),
        ("subject", "Subject"),
        ("status", "Status"),
        ("ball_in_court", "Ball in Court"),
        ("due_at", "Due Date"),
        ("date_initiated_at", "Date Initiated"),
        ("closed_at", "Closed Date"),
        ("cost_impact_choice", "Cost Impact"),
        ("cost_impact", "Cost Impact $"),
        ("schedule_impact_choice", "Schedule Impact"),
        ("schedule_impact_days", "Schedule Impact Days"),
        ("reference_text", "Reference"),
        ("is_private", "Private"),
    ]
    import csv
    import io

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow([label for _, label in cols])
    for item in payload["items"]:
        row = []
        for key, _ in cols:
            v = item.get(key)
            if v is None:
                v = ""
            row.append(str(v))
        w.writerow(row)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Revisions, custom fields, configurable fields (Phase 5)
# ---------------------------------------------------------------------------


def revise_rfi(rfi_id: uuid.UUID, reason: Optional[str], cu: CurrentUser) -> dict[str, Any]:
    rfi = db.session.get(Rfi, rfi_id)
    if rfi is None:
        raise ApiError("RFI not found", 404)
    if not can_act_as_manager(cu, rfi):
        raise ApiError("not authorized", 403)
    if rfi.status not in ("closed", "closed_draft"):
        raise ApiError("only closed RFIs can be revised", 400)

    snapshot = rfi_public(rfi, include_detail=True)
    rev = RfiRevision(
        rfi_id=rfi.id,
        revision_index=rfi.revision_index + 1,
        actor_user_id=cu.id,
        reason=reason,
        payload_json=snapshot,
    )
    db.session.add(rev)

    rfi.revision_index += 1
    rfi.status = "open"
    rfi.closed_at = None
    for a in rfi.assignees:
        a.ball_in_court = True

    _audit(rfi, cu, "revision", summary=f"Revised RFI to R{rfi.revision_index}", after={"reason": reason})
    db.session.commit()
    return {"item": rfi_public(rfi, include_detail=True, cu=cu), "entity": "rfi"}


def _custom_field_def_public(r: RfiCustomFieldDef) -> dict[str, Any]:
    return {
        "id": str(r.id),
        "company_id": str(r.company_id) if r.company_id else None,
        "key": r.key,
        "label": r.label,
        "field_type": r.field_type,
        "sort_order": r.sort_order,
        "is_active": r.is_active,
    }


def list_custom_field_defs(company_id: Optional[uuid.UUID]) -> dict[str, Any]:
    q = select(RfiCustomFieldDef).where(RfiCustomFieldDef.is_active.is_(True))
    if company_id is not None:
        q = q.where(or_(RfiCustomFieldDef.company_id == company_id, RfiCustomFieldDef.company_id.is_(None)))
    rows = db.session.scalars(q.order_by(RfiCustomFieldDef.sort_order.asc(), RfiCustomFieldDef.label.asc())).all()
    return {
        "items": [_custom_field_def_public(r) for r in rows],
        "entity": "rfi_custom_field_defs",
    }


_ALLOWED_CUSTOM_FIELD_TYPES = {"plain_text", "number", "date", "checkbox"}
_CUSTOM_FIELD_TYPE_ALIASES = {
    "text": "plain_text",
    "string": "plain_text",
    "plaintext": "plain_text",
    "bool": "checkbox",
    "boolean": "checkbox",
}


def create_custom_field_def(data: Mapping[str, Any], cu: CurrentUser) -> dict[str, Any]:
    label = (data.get("label") or data.get("name") or "").strip()
    if not label:
        raise ApiError("label is required", 400)
    key = (data.get("key") or data.get("name") or label).strip().lower().replace(" ", "_")[:80]
    if not key:
        raise ApiError("key is required", 400)
    field_type = (data.get("field_type") or "plain_text").strip().lower()
    field_type = _CUSTOM_FIELD_TYPE_ALIASES.get(field_type, field_type)
    if field_type not in _ALLOWED_CUSTOM_FIELD_TYPES:
        raise ApiError(
            f"field_type must be one of {sorted(_ALLOWED_CUSTOM_FIELD_TYPES)}", 400
        )
    company_id = _parse_uuid(data.get("company_id"))
    existing = db.session.scalar(
        select(RfiCustomFieldDef).where(
            RfiCustomFieldDef.key == key,
            RfiCustomFieldDef.is_active.is_(True),
            RfiCustomFieldDef.company_id.is_(company_id) if company_id is None else (RfiCustomFieldDef.company_id == company_id),
        )
    )
    if existing is not None:
        raise ApiError("custom field with that key already exists", 409)
    row = RfiCustomFieldDef(
        company_id=company_id,
        key=key,
        label=label[:200],
        field_type=field_type,
        sort_order=_parse_int(data.get("sort_order")) or 0,
        is_active=True,
    )
    db.session.add(row)
    db.session.commit()
    return {"item": _custom_field_def_public(row), "entity": "rfi_custom_field_def"}


def patch_custom_field_def(def_id: uuid.UUID, data: Mapping[str, Any], cu: CurrentUser) -> dict[str, Any]:
    row = db.session.get(RfiCustomFieldDef, def_id)
    if row is None:
        raise ApiError("custom field def not found", 404)
    if "label" in data:
        row.label = (data.get("label") or "").strip()[:200] or row.label
    if "sort_order" in data:
        row.sort_order = _parse_int(data.get("sort_order")) or 0
    if "is_active" in data:
        row.is_active = _parse_bool(data.get("is_active")) or False
    if "field_type" in data:
        ft = (data.get("field_type") or "").strip().lower()
        ft = _CUSTOM_FIELD_TYPE_ALIASES.get(ft, ft)
        if ft and ft in _ALLOWED_CUSTOM_FIELD_TYPES:
            row.field_type = ft
    db.session.commit()
    return {"item": _custom_field_def_public(row), "entity": "rfi_custom_field_def"}


def delete_custom_field_def(def_id: uuid.UUID, cu: CurrentUser) -> dict[str, Any]:
    row = db.session.get(RfiCustomFieldDef, def_id)
    if row is None:
        raise ApiError("custom field def not found", 404)
    # Hard-delete when no values reference it; otherwise soft-delete so
    # historical RFI custom values still render.
    in_use = db.session.scalar(
        select(RfiCustomFieldValue.id).where(RfiCustomFieldValue.field_def_id == row.id).limit(1)
    )
    if in_use is None:
        db.session.delete(row)
    else:
        row.is_active = False
    db.session.commit()
    return {"ok": True}


def upsert_custom_field_value(rfi_id: uuid.UUID, data: Mapping[str, Any], cu: CurrentUser) -> dict[str, Any]:
    rfi = db.session.get(Rfi, rfi_id)
    if rfi is None:
        raise ApiError("RFI not found", 404)
    _require_edit(cu, rfi)
    def_id = _parse_uuid(data.get("field_def_id"))
    if def_id is None:
        raise ApiError("field_def_id is required", 400)
    fdef = db.session.get(RfiCustomFieldDef, def_id)
    if fdef is None:
        raise ApiError("custom field def not found", 400)
    val = db.session.scalar(
        select(RfiCustomFieldValue).where(
            RfiCustomFieldValue.rfi_id == rfi.id,
            RfiCustomFieldValue.field_def_id == fdef.id,
        )
    )
    if val is None:
        val = RfiCustomFieldValue(rfi_id=rfi.id, field_def_id=fdef.id)
        db.session.add(val)
    val.value_text = data.get("value_text")
    val.value_number = _parse_decimal(data.get("value_number"))
    val.value_date = _parse_dt(data.get("value_date"))
    val.value_bool = (
        _parse_bool(data.get("value_bool")) if data.get("value_bool") is not None else None
    )
    db.session.commit()
    return {"item": _custom_field_value_public(val), "entity": "rfi_custom_field_value"}


def list_configurable_fields(project_id: Optional[uuid.UUID]) -> dict[str, Any]:
    q = select(RfiConfigurableField)
    if project_id is not None:
        q = q.where(or_(RfiConfigurableField.project_id == project_id, RfiConfigurableField.project_id.is_(None)))
    rows = db.session.scalars(q).all()
    return {
        "items": [
            {
                "id": str(r.id),
                "project_id": str(r.project_id) if r.project_id else None,
                "field_key": r.field_key,
                "requirement": r.requirement,
            }
            for r in rows
        ],
        "entity": "rfi_configurable_fields",
    }


def upsert_configurable_field(data: Mapping[str, Any], cu: CurrentUser) -> dict[str, Any]:
    project_id = _parse_uuid(data.get("project_id"))
    field_key = (data.get("field_key") or "").strip()
    requirement = (data.get("requirement") or "optional").strip()
    if not field_key:
        raise ApiError("field_key is required", 400)
    if requirement not in ("required", "optional", "hidden"):
        raise ApiError("requirement must be required/optional/hidden", 400)
    q = select(RfiConfigurableField).where(RfiConfigurableField.field_key == field_key)
    if project_id is not None:
        q = q.where(RfiConfigurableField.project_id == project_id)
    else:
        q = q.where(RfiConfigurableField.project_id.is_(None))
    row = db.session.scalar(q)
    if row is None:
        row = RfiConfigurableField(project_id=project_id, field_key=field_key, requirement=requirement)
        db.session.add(row)
    else:
        row.requirement = requirement
    db.session.commit()
    return {
        "item": {
            "id": str(row.id),
            "project_id": str(row.project_id) if row.project_id else None,
            "field_key": row.field_key,
            "requirement": row.requirement,
        },
        "entity": "rfi_configurable_field",
    }


# ---------------------------------------------------------------------------
# Cross-tool creation stubs (Phase 5)
# ---------------------------------------------------------------------------


def create_change_event(rfi_id: uuid.UUID, data: Mapping[str, Any], cu: CurrentUser) -> dict[str, Any]:
    rfi = db.session.get(Rfi, rfi_id)
    if rfi is None:
        raise ApiError("RFI not found", 404)
    if not can_view_rfi(cu, rfi):
        raise ApiError("not authorized", 403)
    payload = {
        "rfi_id": str(rfi.id),
        "rfi_number": _format_display_number(rfi),
        "title": data.get("title") or rfi.subject,
        "description": data.get("description") or rfi.question,
        "cost_impact": _decimal(rfi.cost_impact),
        "schedule_impact_days": rfi.schedule_impact_days,
        "_related_kind": "change_event",
    }
    _audit(rfi, cu, "edit", summary="Created Change Event (stub)", after=payload)
    db.session.commit()
    return {"item": payload, "entity": "change_event_stub"}


def create_pco(rfi_id: uuid.UUID, data: Mapping[str, Any], cu: CurrentUser) -> dict[str, Any]:
    rfi = db.session.get(Rfi, rfi_id)
    if rfi is None:
        raise ApiError("RFI not found", 404)
    if not can_view_rfi(cu, rfi):
        raise ApiError("not authorized", 403)
    payload = {
        "rfi_id": str(rfi.id),
        "title": data.get("title") or rfi.subject,
        "description": data.get("description") or rfi.question,
        "amount": _decimal(rfi.cost_impact),
        "_related_kind": "pco",
    }
    _audit(rfi, cu, "edit", summary="Created Potential Change Order (stub)", after=payload)
    db.session.commit()
    return {"item": payload, "entity": "pco_stub"}


def create_instruction(rfi_id: uuid.UUID, data: Mapping[str, Any], cu: CurrentUser) -> dict[str, Any]:
    rfi = db.session.get(Rfi, rfi_id)
    if rfi is None:
        raise ApiError("RFI not found", 404)
    if not can_view_rfi(cu, rfi):
        raise ApiError("not authorized", 403)
    payload = {
        "rfi_id": str(rfi.id),
        "title": data.get("title") or rfi.subject,
        "instruction": data.get("instruction") or rfi.official_response or rfi.question,
        "_related_kind": "instruction",
    }
    _audit(rfi, cu, "edit", summary="Created Instruction (stub)", after=payload)
    db.session.commit()
    return {"item": payload, "entity": "instruction_stub"}


# ---------------------------------------------------------------------------
# AI Draft Agent (Phase 6)
# ---------------------------------------------------------------------------


def draft_assist(data: Mapping[str, Any], cu: CurrentUser) -> dict[str, Any]:
    """Draft RFI Agent (Procore parity, 2025-09 GA).

    Without an LLM key configured we return a deterministic
    rule-based draft so the front-end can render the same payload shape.
    To plug in a real model, set ``USIS_RFI_AI_PROVIDER`` to e.g.
    ``openai`` and configure ``USIS_RFI_AI_MODEL`` /
    ``USIS_RFI_AI_API_KEY``.
    """
    import os

    free_text = str(data.get("text") or "").strip()
    project_id = _parse_uuid(data.get("project_id"))
    drawing_id = _parse_uuid(data.get("drawing_id"))
    if not free_text:
        raise ApiError("text is required", 400)

    provider = (os.environ.get("USIS_RFI_AI_PROVIDER") or "").strip().lower()
    if provider == "openai":
        try:
            from ._ai_openai import draft_with_openai

            return draft_with_openai(free_text, project_id=project_id, drawing_id=drawing_id)
        except Exception as exc:  # pragma: no cover — fall through
            from flask import current_app

            current_app.logger.warning("OpenAI draft assist failed: %s", exc)

    # Rule-based fallback.
    first_line = free_text.splitlines()[0].strip()
    subject = (first_line[:140] or "Field condition needs clarification") + (
        "" if first_line.endswith("?") else ""
    )
    question = free_text
    cost_impact = "tbd" if "cost" in free_text.lower() or "$" in free_text else "tbd"
    schedule_impact = "tbd"
    return {
        "item": {
            "subject": subject[:500],
            "question": question,
            "cost_impact_choice": cost_impact,
            "schedule_impact_choice": schedule_impact,
            "provider": "rule_based",
        },
        "entity": "rfi_draft_assist",
    }


# ---------------------------------------------------------------------------
# Notification fan-out
# ---------------------------------------------------------------------------


def _notification_targets(rfi: Rfi, event: str) -> list[User]:
    out: list[User] = []
    seen: set[uuid.UUID] = set()
    # Assignees
    for a in rfi.assignees:
        if a.user_id and a.user_id not in seen:
            u = a.user
            if u and u.email:
                out.append(u)
                seen.add(a.user_id)
    # Distribution list
    for d in rfi.distribution:
        if d.user_id and d.user_id not in seen:
            u = d.user
            if u and u.email:
                out.append(u)
                seen.add(d.user_id)
    # Manager + Creator
    for uid in (rfi.rfi_manager_user_id, rfi.created_by_user_id):
        if uid and uid not in seen:
            u = db.session.get(User, uid)
            if u and u.email:
                out.append(u)
                seen.add(uid)
    return out
