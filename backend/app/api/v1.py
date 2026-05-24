"""Versioned read+write API for projects, lead_estimates, and Procore-parity RFIs."""
from __future__ import annotations

import json
import os
import uuid
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Mapping

from flask import Blueprint, Response, current_app, jsonify, request
from sqlalchemy import and_, func, literal, or_, select
from sqlalchemy.orm import joinedload
from werkzeug.utils import secure_filename

from ..config import client_debug_log_dev_open
from ..extensions import db
from ..services.object_storage import UploadCategory, delete_stored, save_upload, send_stored_file, stored_exists
from ..models import (
    AuditLog,
    Company,
    DoorHardwareSet,
    DoorHardwareSetItem,
    DoorOpening,
    Drawing,
    Document,
    LeadEstimate,
    MaterialPrice,
    Project,
    Rfi,
    SpecSection,
    Submittal,
    TakeoffLineItem,
    User,
    WageRate,
)
from ..models.hrms_core import HrmsTimesheetEntry
from ..services import door_schedule as door_schedule_svc
from . import _commitment_service as commitment_svc
from . import _admin_users_service as admin_users_svc
from . import _document_render_service as document_render_svc
from . import _pay_application_service as pay_app_svc
from . import _reports_catalog_service as reports_catalog_svc
from . import _power_bi_service as power_bi_svc
from . import _prime_contract_sov_service as prime_sov_svc
from . import _calendar_service as calendar_svc
from . import _project_schedule_service as project_schedule_svc
from . import _rfi_service as rfi_svc
from . import _material_order_service as material_order_svc
from . import _procurement_lookup_service as proc_lookup_svc
from . import _project_members_service as project_members_svc
from . import _project_service as project_svc
from . import _invoice_delivery_service as invoice_delivery_svc
from . import _lead_estimate_queries as lead_q
from . import _serializers as ser
from . import _submittal_service as submittal_svc
from ._perms import can_edit_rfi, current_user, users_for_picker

bp = Blueprint("api_v1", __name__, url_prefix="/api/v1")

# Repo root: backend/app/api/v1.py → parents[3] == USIS_CM
_CLIENT_DEBUG_LOG = Path(__file__).resolve().parents[3] / "debug-ff8612.log"


def _jsonify(obj: Any):
    return jsonify(obj)


def _append_lead_estimate_audit(
    cu,
    lead_id: uuid.UUID,
    action: str,
    *,
    message: str | None = None,
    changes: dict[str, Any] | None = None,
) -> None:
    db.session.add(
        AuditLog(
            user_id=cu.user.id if cu.user else None,
            entity_type="lead_estimate",
            entity_id=lead_id,
            action=action,
            changes=changes,
            message=message,
        )
    )


@bp.post("/__debug/client-log")
def client_debug_log():
    """Append one NDJSON line for in-browser debug (local dev / debug app only)."""
    if not client_debug_log_dev_open():
        return jsonify({"error": "not found"}), 404
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "expected JSON object"}), 400
    if payload.get("sessionId") != "ff8612":
        return jsonify({"ok": True})
    try:
        _CLIENT_DEBUG_LOG.parent.mkdir(parents=True, exist_ok=True)
        with _CLIENT_DEBUG_LOG.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, separators=(",", ":")) + "\n")
    except OSError:
        current_app.logger.exception("client_debug_log write failed")
        return jsonify({"error": "write failed"}), 500
    return jsonify({"ok": True})


@bp.get("/auth/status")
def auth_status():
    """Return whether the browser session is signed in (``session['user_id']``)."""
    from ..integrations.ms_entra_oidc import entra_fully_configured

    cu = current_user()
    ms_on = entra_fully_configured(current_app.config)
    allow_register = bool(current_app.config.get("USIS_ALLOW_SELF_REGISTER"))
    if cu.user is None:
        return _jsonify(
            {
                "authenticated": False,
                "user": None,
                "microsoft_sso_enabled": ms_on,
                "self_register_enabled": allow_register,
            }
        )
    u = cu.user
    from ..permissions.applicant import is_applicant_only_user

    return _jsonify(
        {
            "authenticated": True,
            "microsoft_sso_enabled": ms_on,
            "self_register_enabled": allow_register,
            "applicant_only": is_applicant_only_user(u),
            "role_codes": sorted(cu.role_codes),
            "user": {
                "id": str(u.id),
                "email": u.email,
                "first_name": u.first_name,
                "last_name": u.last_name,
            },
        }
    )


@bp.post("/auth/register")
def auth_register():
    """Create a USIS user account and start a browser session (hire wizard / self-service)."""
    from werkzeug.security import generate_password_hash

    from sqlalchemy import select

    from ..models import User
    from . import _admin_users_service as admin_users_svc

    if not current_app.config.get("USIS_ALLOW_SELF_REGISTER"):
        return _jsonify({"entity": "auth_register", "error": "self-registration is disabled"}), 403

    body = request.get_json(silent=True) or {}
    if not isinstance(body, dict):
        return _jsonify({"entity": "auth_register", "error": "JSON body required"}), 400

    try:
        email = admin_users_svc._normalize_email(str(body.get("email") or ""))
    except admin_users_svc.ApiError as exc:
        return _jsonify({"entity": "auth_register", "error": exc.message}), exc.status

    password = str(body.get("password") or "")
    if len(password) < 8:
        return _jsonify({"entity": "auth_register", "error": "password must be at least 8 characters"}), 400

    existing = db.session.scalar(select(User.id).where(User.email == email))
    if existing is not None:
        return _jsonify({"entity": "auth_register", "error": "an account with this email already exists"}), 409

    fn = str(body.get("first_name") or "").strip()[:120] or None
    ln = str(body.get("last_name") or "").strip()[:120] or None
    phone = str(body.get("phone") or "").strip()[:50] or None

    u = User(
        email=email,
        first_name=fn,
        last_name=ln,
        phone=phone,
        password_hash=generate_password_hash(password),
        is_active=True,
        is_superuser=False,
    )
    db.session.add(u)
    db.session.flush()
    from ..permissions.applicant import assign_applicant_role

    assign_applicant_role(u)
    db.session.commit()

    from flask import session

    session["user_id"] = str(u.id)
    session.permanent = True

    return _jsonify(
        {
            "entity": "auth_register",
            "ok": True,
            "user": {
                "id": str(u.id),
                "email": u.email,
                "first_name": u.first_name,
                "last_name": u.last_name,
            },
        }
    ), 201


@bp.post("/auth/password-reset/request")
def auth_password_reset_request():
    """Email a single-use reset link (always returns success to avoid email enumeration)."""
    from ..services import password_reset as pw_reset

    body = request.get_json(silent=True) or {}
    if not isinstance(body, dict):
        return _jsonify({"entity": "auth_password_reset", "error": "JSON body required"}), 400

    email = str(body.get("email") or "").strip()
    try:
        result = pw_reset.request_password_reset(email)
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("password reset request failed")
        result = {"ok": True, "sent": False, "dry_run": False}

    return _jsonify(
        {
            "entity": "auth_password_reset",
            "ok": True,
            "message": "If an account exists with that email, password reset instructions have been sent.",
            "sent": bool(result.get("sent")),
            "dry_run": bool(result.get("dry_run")),
        }
    )


@bp.post("/auth/password-reset/confirm")
def auth_password_reset_confirm():
    """Set a new password using a token from the reset email."""
    from ..services import password_reset as pw_reset

    body = request.get_json(silent=True) or {}
    if not isinstance(body, dict):
        return _jsonify({"entity": "auth_password_reset", "error": "JSON body required"}), 400

    token = str(body.get("token") or "").strip()
    password = str(body.get("password") or "")
    try:
        pw_reset.confirm_password_reset(token, password)
        db.session.commit()
    except ValueError as exc:
        db.session.rollback()
        return _jsonify({"entity": "auth_password_reset", "error": str(exc)}), 400
    except Exception:
        db.session.rollback()
        current_app.logger.exception("password reset confirm failed")
        return _jsonify({"entity": "auth_password_reset", "error": "could not reset password"}), 500

    return _jsonify({"entity": "auth_password_reset", "ok": True})


@bp.get("/me")
def get_me():
    """Signed-in user's profile (same payload shape as ``GET /admin/users/<id>``)."""
    cu = current_user()
    try:
        item = admin_users_svc.get_me(cu)
        capabilities = admin_users_svc.get_me_capabilities(cu)
    except admin_users_svc.ApiError as exc:
        return _admin_directory_err(exc)
    return _jsonify(
        {
            "item": item,
            "capabilities": capabilities,
            "entity": "session_user",
        }
    )


@bp.get("/me/capabilities")
def get_me_capabilities():
    cu = current_user()
    try:
        capabilities = admin_users_svc.get_me_capabilities(cu)
    except admin_users_svc.ApiError as exc:
        return _admin_directory_err(exc)
    return _jsonify({"capabilities": capabilities, "entity": "session_capabilities"})


@bp.get("/permissions/catalog")
def permissions_catalog():
    return _jsonify(
        {
            "items": admin_users_svc.permissions_catalog(),
            "entity": "permission_modules",
        }
    )


@bp.patch("/me")
def patch_me():
    """Update name, email, phone, or password for the signed-in user only."""
    body = request.get_json(silent=True) or {}
    if not isinstance(body, dict):
        return _jsonify({"error": "JSON body required"}), 400
    try:
        item = admin_users_svc.patch_me(current_user(), body)
    except admin_users_svc.ApiError as exc:
        return _admin_directory_err(exc)
    db.session.commit()
    return _jsonify({"item": item, "entity": "session_user"})


_iso = ser.iso
_lead_estimate_public = ser.lead_estimate_public
_primary_lead_detail_id_by_project_ids = ser.primary_lead_detail_id_by_project_ids
_project_public = ser.project_public


def _client_company_name(client: Any) -> str | None:
    if not isinstance(client, Mapping):
        return None
    comp = client.get("company")
    if isinstance(comp, Mapping):
        n = comp.get("name")
        return str(n).strip() if n else None
    return None


def _client_contact_line(client: Any) -> str | None:
    """Best-effort primary contact string from BC ``client`` JSON."""
    if not isinstance(client, Mapping):
        return None
    for key in ("primaryContact", "contact", "person", "primary_contact"):
        pc = client.get(key)
        if not isinstance(pc, Mapping):
            continue
        fn_raw = pc.get("firstName") or pc.get("first_name")
        ln_raw = pc.get("lastName") or pc.get("last_name")
        fn = str(fn_raw).strip() if fn_raw is not None else ""
        ln = str(ln_raw).strip() if ln_raw is not None else ""
        name = (fn + " " + ln).strip()
        email = pc.get("email") or pc.get("emailAddress")
        email_s = str(email).strip() if email else ""
        if name and email_s:
            return f"{name} · {email_s}"
        if name:
            return name
        if email_s:
            return email_s
    return None


def _company_name_by_id(company_id: uuid.UUID | None) -> str | None:
    if company_id is None:
        return None
    c = db.session.get(Company, company_id)
    return c.name if c else None


def _project_detail_public(p: Project) -> dict[str, Any]:
    """Full project card for Job info tab (active project detail)."""
    lead_nav = _primary_lead_detail_id_by_project_ids([p.id])
    d = _project_public(p, primary_lead_detail_id=lead_nav.get(p.id))
    d.update(
        {
            "description": p.description,
            "address_line1": p.address_line1,
            "address_line2": p.address_line2,
            "postal_code": p.postal_code,
            "country": p.country,
            "contract_value": _num_or_none(p.contract_value),
            "contract_date": _iso(p.contract_date) if p.contract_date else None,
            "start_date": _iso(p.start_date) if p.start_date else None,
            "substantial_completion_date": _iso(p.substantial_completion_date)
            if p.substantial_completion_date
            else None,
            "closeout_date": _iso(p.closeout_date) if p.closeout_date else None,
            "retention_percentage": _num_or_none(p.retention_percentage),
            "prevailing_wage": p.prevailing_wage,
            "dbe_required": p.dbe_required,
            "sage_project_id": p.sage_project_id,
            "textura_project_id": p.textura_project_id,
            "invoice_method": (p.invoice_method or "").strip() or None,
            "invoice_method_label": invoice_delivery_svc.label_for_code(p.invoice_method),
            "invoice_due_date": _iso(p.invoice_due_date) if p.invoice_due_date else None,
            "invoice_recipient_emails": p.invoice_recipient_emails,
            "notes": p.notes,
            "gc_company_name": _company_name_by_id(p.gc_company_id),
            "owner_company_name": _company_name_by_id(p.owner_company_id),
            "architect_company_name": _company_name_by_id(p.architect_company_id),
            "created_at": _iso(p.created_at),
        }
    )
    return d


def _parse_uuid_param(raw: str | None) -> uuid.UUID | None:
    if not raw or not str(raw).strip():
        return None
    try:
        return uuid.UUID(str(raw).strip())
    except ValueError:
        return None


def _drawing_id_from_payload(val: Any) -> uuid.UUID | None:
    """Parse optional drawing revision UUID; empty string clears to None."""
    if val is None:
        return None
    s = str(val).strip()
    if not s:
        return None
    uid = _parse_uuid_param(s)
    if uid is None:
        raise ValueError("invalid drawing_id")
    return uid


def _measurement_data_from_payload(val: Any) -> Any:
    """JSONB-compatible value for takeoff geometry / tool state; None clears."""
    if val is None:
        return None
    if isinstance(val, (dict, list)):
        return val
    if isinstance(val, (str, int, float, bool)):
        return val
    raise ValueError("measurement_data must be JSON-serializable")


def _project_exists(project_id: uuid.UUID) -> bool:
    from ..permissions.project_scope import user_can_access_project

    return user_can_access_project(current_user(), project_id)


def _drawing_public(d: Drawing) -> dict[str, Any]:
    return {
        "id": str(d.id),
        "series_id": str(d.drawing_series_id),
        "sheet_number": d.sheet_number,
        "sheet_title": d.sheet_title,
        "discipline": d.discipline,
        "drawing_set": d.drawing_set,
        "revision": d.revision,
        "version": d.version,
        "file_url": _drawing_resolved_file_url(d),
        "title": d.title,
        "parent_document_id": str(d.parent_document_id) if d.parent_document_id else None,
        "created_at": _iso(d.created_at),
        "updated_at": _iso(d.updated_at),
    }


def _revision_sort_key(d: Drawing) -> tuple:
    """Newest-first ordering for revision lists."""
    ts = d.updated_at or d.created_at
    return (ts, d.version, d.id)


def _group_drawings_into_sheets(rows: list[Drawing]) -> list[dict[str, Any]]:
    by_series: dict[uuid.UUID, list[Drawing]] = defaultdict(list)
    for d in rows:
        by_series[d.drawing_series_id].append(d)

    sheets: list[dict[str, Any]] = []
    for series_id, group in by_series.items():
        ordered_newest = sorted(group, key=_revision_sort_key, reverse=True)
        current = ordered_newest[0]
        cur_pub = _drawing_public(current)
        sheets.append(
            {
                "series_id": str(series_id),
                "sheet_number": current.sheet_number,
                "sheet_title": current.sheet_title or current.title,
                "discipline": current.discipline,
                "drawing_set": current.drawing_set,
                "revision_count": len(group),
                "current_revision": cur_pub,
                "revisions": [_drawing_public(r) for r in ordered_newest],
            }
        )
    sheets.sort(
        key=lambda s: (
            (s.get("sheet_number") or "").lower(),
            (s.get("discipline") or "").lower(),
            s["series_id"],
        )
    )
    return sheets


def _num_or_none(v: Decimal | float | None) -> float | None:
    if v is None:
        return None
    if isinstance(v, Decimal):
        return float(v)
    return float(v)


def _decimal_from_json(val: Any, default: Decimal = Decimal("0")) -> Decimal:
    if val is None:
        return default
    if isinstance(val, bool):
        raise ValueError("invalid number")
    if isinstance(val, int | float):
        return Decimal(str(val))
    if isinstance(val, str):
        s = val.strip()
        if not s:
            return default
        return Decimal(s)
    if isinstance(val, Decimal):
        return val
    raise ValueError("invalid number")


def _compute_extended(quantity: Decimal, unit_cost: Decimal) -> Decimal:
    return (quantity * unit_cost).quantize(Decimal("0.01"))


def _normalize_cost_type(raw: Any) -> str:
    if raw is None or str(raw).strip() == "":
        return "M"
    c = str(raw).strip().upper()[:1]
    if c in ("L", "M", "E", "S", "O"):
        return c
    return "M"


def _takeoff_writes_enabled() -> bool:
    return bool(current_app.config.get("TAKEOFF_API_WRITES_ENABLED"))


def _lead_estimate_is_locked(row: LeadEstimate) -> bool:
    return row.estimate_locked_at is not None


def _takeoff_locked_response():
    return (
        _jsonify(
            {
                "error": "estimate is locked (approved or manually locked); admin unlock required to edit takeoff",
                "error_code": "ESTIMATE_LOCKED",
            }
        ),
        403,
    )


def _require_lead_unlocked_for_takeoff(lead: LeadEstimate | None):
    if lead is not None and _lead_estimate_is_locked(lead):
        return _takeoff_locked_response()
    return None


def _takeoff_line_parent_lead(t: TakeoffLineItem) -> LeadEstimate | None:
    if t.lead_estimate_id:
        return db.session.get(LeadEstimate, t.lead_estimate_id)
    if t.door_opening_id:
        op = db.session.get(DoorOpening, t.door_opening_id)
        if op is not None and op.lead_estimate_id:
            return db.session.get(LeadEstimate, op.lead_estimate_id)
    return None


def _can_unlock_lead_estimate(cu) -> bool:
    return bool(cu.is_dev_admin or cu.has_role("admin", "superuser"))


def _resolve_lead(identifier: str) -> LeadEstimate | None:
    """Resolve by UUID PK, ``external_id`` (BC CSV ``id``), case-insensitive id, or ``raw_row.id``."""
    raw = (identifier or "").strip()
    if not raw:
        return None
    uid = _parse_uuid_param(raw)
    if uid:
        row = db.session.get(LeadEstimate, uid)
        if row is not None:
            return row
    row = db.session.scalar(select(LeadEstimate).where(LeadEstimate.external_id == raw))
    if row is not None:
        return row
    row = db.session.scalar(
        select(LeadEstimate).where(func.lower(LeadEstimate.external_id) == raw.lower())
    )
    if row is not None:
        return row
    # Some imports only preserve BC Mongo id inside raw_row JSON
    try:
        row = db.session.scalar(
            select(LeadEstimate).where(LeadEstimate.raw_row.contains({"id": raw}))
        )
    except Exception:
        row = None
    if row is not None:
        return row
    try:
        row = db.session.scalar(
            select(LeadEstimate).where(LeadEstimate.raw_row["id"].as_string() == raw)
        )
    except Exception:
        row = None
    return row


def _takeoff_line_public(t: TakeoffLineItem) -> dict[str, Any]:
    mat_cat = None
    if t.material_pricing_id is not None:
        mp = t.material_price
        if mp is not None:
            mat_cat = {"id": str(mp.id), "manufacturer": mp.manufacturer, "item": mp.item}
    return {
        "id": str(t.id),
        "lead_estimate_id": str(t.lead_estimate_id) if t.lead_estimate_id else None,
        "project_id": str(t.project_id) if t.project_id else None,
        "section": t.section,
        "sort_order": t.sort_order,
        "description": t.description,
        "quantity": float(t.quantity),
        "unit": t.unit,
        "unit_cost": float(t.unit_cost),
        "extended_total": float(t.extended_total),
        "cost_type": t.cost_type,
        "job_cost_code": t.job_cost_code,
        "job_cost_code_description": t.job_cost_code_description,
        "notes": t.notes,
        "status": t.status,
        "version": t.version,
        "drawing_id": str(t.drawing_id) if t.drawing_id else None,
        "measurement_data": t.measurement_data,
        "takeoff_location": t.takeoff_location,
        "material_pricing_id": str(t.material_pricing_id) if t.material_pricing_id else None,
        "material_catalog": mat_cat,
        "door_opening_id": str(t.door_opening_id) if t.door_opening_id else None,
        "line_role": t.line_role,
        "created_at": _iso(t.created_at),
        "updated_at": _iso(t.updated_at),
    }


def _lead_estimate_detail(row: LeadEstimate) -> dict[str, Any]:
    out = dict(_lead_estimate_public(row))
    out.update(
        {
            "default_currency": row.default_currency,
            "rom": _num_or_none(row.rom),
            "final_value": _num_or_none(row.final_value),
            "profit_margin": _num_or_none(row.profit_margin),
            "fee_percentage": _num_or_none(row.fee_percentage),
            "win_probability": _num_or_none(row.win_probability),
            "project_size": _num_or_none(row.project_size),
            "estimating_hours": _num_or_none(row.estimating_hours),
            "is_archived": row.is_archived,
            "bc_created_at": _iso(row.bc_created_at),
            "expected_start_at": _iso(row.expected_start_at),
            "expected_finish_at": _iso(row.expected_finish_at),
            # --- Building Connected job / opportunity detail (for lead Job info UI) ---
            "location": row.location if isinstance(row.location, (dict, list)) else None,
            "architect": row.architect,
            "engineer": row.engineer,
            "property_owner": row.property_owner,
            "property_tenant": row.property_tenant,
            "project_information": row.project_information,
            "trade_specific_instructions": row.trade_specific_instructions,
            "request_type": row.request_type,
            "market_sector": row.market_sector,
            "priority": row.priority,
            "invited_at": _iso(row.invited_at),
            "job_walk_at": _iso(row.job_walk_at),
            "contract_start_at": _iso(row.contract_start_at),
            "rfis_due_at": _iso(row.rfis_due_at),
            "follow_up_at": _iso(row.follow_up_at),
            "is_nda_required": row.is_nda_required,
            "is_sealed_bidding": row.is_sealed_bidding,
            "project_is_public": row.project_is_public,
            "contract_duration": row.contract_duration,
            "average_crew_size": row.average_crew_size,
            "client": row.client if isinstance(row.client, (dict, list)) else None,
            "client_contact": _client_contact_line(row.client),
            "members": row.members if isinstance(row.members, (dict, list)) else None,
            "additional_info": row.additional_info if isinstance(row.additional_info, (dict, list)) else None,
            "custom_tags": row.custom_tags if isinstance(row.custom_tags, (dict, list)) else None,
            "decline_reasons": row.decline_reasons if isinstance(row.decline_reasons, (dict, list)) else None,
            "outcome": row.outcome if isinstance(row.outcome, (dict, list)) else None,
            "owning_office_id": row.owning_office_id,
            "is_parent": row.is_parent,
        }
    )
    if row.estimate_approved_by_user_id:
        u = db.session.get(User, row.estimate_approved_by_user_id)
        out["estimate_approved_by_email"] = u.email if u is not None else None
    else:
        out["estimate_approved_by_email"] = None
    lines = db.session.scalars(
        select(TakeoffLineItem)
        .where(TakeoffLineItem.lead_estimate_id == row.id)
        .order_by(TakeoffLineItem.sort_order.asc(), TakeoffLineItem.created_at.asc())
        .options(joinedload(TakeoffLineItem.material_price))
    ).all()
    out["takeoff_lines"] = [_takeoff_line_public(x) for x in lines]
    out["takeoff_line_count"] = len(lines)
    return out


def _next_sort_order(lead_estimate_id: uuid.UUID) -> int:
    m = db.session.scalar(
        select(func.coalesce(func.max(TakeoffLineItem.sort_order), -1)).where(
            TakeoffLineItem.lead_estimate_id == lead_estimate_id
        )
    )
    return int(m if m is not None else -1) + 1


def _apply_takeoff_material_pricing_fk(t: TakeoffLineItem, raw: Any) -> None:
    if raw is None or raw == "":
        t.material_pricing_id = None
        return
    mid = _parse_uuid_param(str(raw).strip())
    if not mid:
        raise ValueError("invalid material_pricing_id")
    if db.session.get(MaterialPrice, mid) is None:
        raise ValueError("material catalog row not found")
    t.material_pricing_id = mid


def _apply_takeoff_payload(t: TakeoffLineItem, data: Mapping[str, Any], *, partial: bool) -> None:
    if partial:
        if "section" in data:
            v = data["section"]
            t.section = (str(v).strip()[:120] or None) if v is not None else None
        if "sort_order" in data and data["sort_order"] is not None:
            t.sort_order = int(data["sort_order"])
        if "description" in data and data["description"] is not None:
            t.description = str(data["description"])[:500]
        if "quantity" in data:
            t.quantity = _decimal_from_json(data["quantity"], Decimal("0"))
        if "unit" in data and data["unit"] is not None:
            t.unit = str(data["unit"]).strip()[:50] or "EA"
        if "unit_cost" in data:
            t.unit_cost = _decimal_from_json(data["unit_cost"], Decimal("0"))
        if "cost_type" in data:
            t.cost_type = _normalize_cost_type(data["cost_type"])
        if "job_cost_code" in data:
            v = data["job_cost_code"]
            t.job_cost_code = (str(v).strip()[:60] or None) if v is not None else None
        if "job_cost_code_description" in data:
            v = data["job_cost_code_description"]
            t.job_cost_code_description = (str(v).strip()[:500] or None) if v is not None else None
        if "notes" in data:
            v = data["notes"]
            t.notes = str(v) if v is not None else None
        if "status" in data:
            v = data["status"]
            t.status = (str(v).strip()[:40] or None) if v is not None else None
        if "version" in data and data["version"] is not None:
            t.version = int(data["version"])
        if "drawing_id" in data:
            t.drawing_id = _drawing_id_from_payload(data["drawing_id"])
        if "measurement_data" in data:
            t.measurement_data = _measurement_data_from_payload(data["measurement_data"])
        if "takeoff_location" in data:
            v = data["takeoff_location"]
            t.takeoff_location = (str(v).strip()[:500] or None) if v is not None else None
        if "material_pricing_id" in data:
            _apply_takeoff_material_pricing_fk(t, data["material_pricing_id"])
    else:
        v = data.get("section")
        t.section = (str(v).strip()[:120] or None) if v is not None else None
        if data.get("sort_order") is not None:
            t.sort_order = int(data["sort_order"])
        t.description = str(data.get("description") or "")[:500]
        t.quantity = _decimal_from_json(data.get("quantity"), Decimal("0"))
        t.unit = str(data.get("unit") or "EA").strip()[:50] or "EA"
        t.unit_cost = _decimal_from_json(data.get("unit_cost"), Decimal("0"))
        t.cost_type = _normalize_cost_type(data.get("cost_type"))
        v = data.get("job_cost_code")
        t.job_cost_code = (str(v).strip()[:60] or None) if v is not None else None
        v = data.get("job_cost_code_description")
        t.job_cost_code_description = (str(v).strip()[:500] or None) if v is not None else None
        v = data.get("notes")
        t.notes = str(v) if v is not None else None
        v = data.get("status")
        t.status = (str(v).strip()[:40] or None) if v is not None else None
        if data.get("version") is not None:
            t.version = int(data["version"])
        t.drawing_id = _drawing_id_from_payload(data.get("drawing_id"))
        if "measurement_data" in data:
            t.measurement_data = _measurement_data_from_payload(data["measurement_data"])
        v = data.get("takeoff_location")
        t.takeoff_location = (str(v).strip()[:500] or None) if v is not None else None
        if "material_pricing_id" in data:
            _apply_takeoff_material_pricing_fk(t, data.get("material_pricing_id"))
    t.extended_total = _compute_extended(t.quantity, t.unit_cost)


def _rfi_public(r: Rfi) -> dict[str, Any]:
    """Compatibility wrapper used by other code paths (drawings tab uses it).

    The full Procore-parity payload comes from ``rfi_svc.rfi_public``."""
    return rfi_svc.rfi_public(r)


def _lead_estimates_health_count_filter() -> Any:
    """Same row set as the Leads page default (undecided / no decision yet, not archived)."""
    return lead_q.lead_estimates_ui_filter("undecided")


@bp.get("/lead-estimates")
def list_lead_estimates():
    """Paged list of ``lead_estimates`` (default: Leads = undecided / no state, not archived)."""
    try:
        limit = max(1, min(int(request.args.get("limit", 200)), 1000))
        offset = max(0, int(request.args.get("offset", 0)))
    except ValueError:
        return _jsonify({"error": "invalid limit or offset"}), 400

    submission_state = (request.args.get("submission_state") or "undecided").strip()
    if not submission_state:
        return _jsonify({"error": "submission_state cannot be empty"}), 400

    source = (request.args.get("source") or "").strip() or None
    crm_stage = (request.args.get("crm_stage") or "").strip() or None
    due_before_raw = (request.args.get("due_before") or "").strip() or None
    due_after_raw = (request.args.get("due_after") or "").strip() or None

    try:
        filt = lead_q.lead_estimates_ui_filter(submission_state)
    except ValueError as exc:
        return _jsonify({"error": str(exc)}), 400
    if source:
        filt = and_(filt, LeadEstimate.source == source)
    if crm_stage:
        filt = and_(filt, LeadEstimate.crm_stage == crm_stage)
    if due_before_raw:
        try:
            due_before = datetime.fromisoformat(due_before_raw.replace("Z", "+00:00"))
        except ValueError:
            return _jsonify({"error": "invalid due_before (use ISO-8601)"}), 400
        filt = and_(filt, LeadEstimate.due_at.is_not(None), LeadEstimate.due_at <= due_before)
    if due_after_raw:
        try:
            due_after = datetime.fromisoformat(due_after_raw.replace("Z", "+00:00"))
        except ValueError:
            return _jsonify({"error": "invalid due_after (use ISO-8601)"}), 400
        filt = and_(filt, LeadEstimate.due_at.is_not(None), LeadEstimate.due_at >= due_after)

    stmt = select(func.count()).select_from(LeadEstimate).where(filt)
    total = db.session.scalar(stmt) or 0

    q = select(LeadEstimate).where(filt)
    q = q.order_by(LeadEstimate.bc_updated_at.desc().nullslast(), LeadEstimate.name.asc())
    q = q.offset(offset).limit(limit)
    rows = db.session.scalars(q).all()

    return _jsonify(
        {
            "items": [_lead_estimate_public(r) for r in rows],
            "total": total,
            "limit": limit,
            "offset": offset,
            "entity": "lead_estimates",
        }
    )


@bp.get("/projects")
def list_projects():
    """Active directory jobs (``projects``), excluding soft-deleted rows."""
    from ..permissions.project_scope import project_access_clause, project_scope_label

    try:
        limit = max(1, min(int(request.args.get("limit", 500)), 2000))
        offset = max(0, int(request.args.get("offset", 0)))
    except ValueError:
        return _jsonify({"error": "invalid limit or offset"}), 400

    cu = current_user()
    filt = and_(Project.deleted_at.is_(None), project_access_clause(cu))
    total = db.session.scalar(select(func.count()).select_from(Project).where(filt)) or 0
    q = select(Project).where(filt).order_by(Project.number.asc().nullslast(), Project.name.asc()).offset(offset).limit(limit)
    rows = db.session.scalars(q).all()
    pids = [p.id for p in rows]
    lead_nav = _primary_lead_detail_id_by_project_ids(pids)
    payload: dict[str, Any] = {
        "items": [_project_public(p, primary_lead_detail_id=lead_nav.get(p.id)) for p in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
        "entity": "projects",
    }
    payload["project_scope"] = project_scope_label(cu)
    return _jsonify(payload)


@bp.get("/projects/<project_id>")
def get_project(project_id: str):
    """Single project by UUID (Job info tab)."""
    pid = _parse_uuid_param(project_id)
    if not pid:
        return _jsonify({"error": "invalid project id"}), 400
    if not _project_exists(pid):
        return _jsonify({"error": "project not found"}), 404
    p = db.session.get(Project, pid)
    if p is None or p.deleted_at is not None:
        return _jsonify({"error": "project not found"}), 404
    return _jsonify({"item": _project_detail_public(p), "entity": "project"})


@bp.patch("/projects/<project_id>")
def patch_project(project_id: str):
    """Update project Job info fields (requires projects write access)."""
    pid = _parse_uuid_param(project_id)
    if not pid:
        return _jsonify({"error": "invalid project id"}), 400
    if not _project_exists(pid):
        return _jsonify({"error": "project not found"}), 404
    body = request.get_json(silent=True) or {}
    try:
        item = project_svc.patch_project(pid, body)
    except project_svc.ApiError as exc:
        return _jsonify({"error": exc.message}), exc.status
    if item is None:
        return _jsonify({"error": "project not found"}), 404
    db.session.commit()
    return _jsonify({"item": item, "entity": "project"})


@bp.get("/invoice-delivery-methods")
def list_invoice_delivery_methods():
    items = invoice_delivery_svc.list_methods()
    return _jsonify({"items": items, "entity": "invoice_delivery_methods"})


@bp.post("/invoice-delivery-methods")
def create_invoice_delivery_method():
    body = request.get_json(silent=True) or {}
    try:
        item = invoice_delivery_svc.create_method(body)
    except invoice_delivery_svc.ApiError as exc:
        return _jsonify({"error": exc.message}), exc.status
    db.session.commit()
    return _jsonify({"item": item, "entity": "invoice_delivery_method"}), 201


@bp.get("/calendar-events")
def list_calendar_events():
    """Categorized calendar feed (procurement, schedule, RFIs, submittals, milestones)."""
    from ._perms import current_user

    cu = current_user()
    pid_raw = request.args.get("project_id")
    pid = _parse_uuid_param(pid_raw) if pid_raw else None
    if pid_raw and not pid:
        return _jsonify({"error": "invalid project_id"}), 400
    categories = calendar_svc._resolve_categories(
        request.args.get("categories"),
        request.args.get("preset"),
    )
    range_start = calendar_svc._parse_date_param(request.args.get("start"))
    range_end = calendar_svc._parse_date_param(request.args.get("end"))
    project_statuses = calendar_svc._parse_project_statuses(request.args.get("project_status"))
    payload = calendar_svc.list_calendar_events(
        cu,
        project_id=pid,
        categories=categories,
        range_start=range_start,
        range_end=range_end,
        project_statuses=project_statuses,
    )
    return _jsonify(payload)


@bp.get("/projects/<project_id>/schedule-items")
def list_project_schedule_items(project_id: str):
    """Installation / work windows for Job costing calendar (multi line per project)."""
    pid = _parse_uuid_param(project_id)
    if not pid:
        return _jsonify({"error": "invalid project id"}), 400
    if not _project_exists(pid):
        return _jsonify({"error": "project not found"}), 404
    items = project_schedule_svc.list_schedule_items(pid)
    return _jsonify({"items": items, "entity": "project_schedule_items"})


@bp.post("/projects/<project_id>/schedule-items")
def create_project_schedule_item(project_id: str):
    pid = _parse_uuid_param(project_id)
    if not pid:
        return _jsonify({"error": "invalid project id"}), 400
    if not _project_exists(pid):
        return _jsonify({"error": "project not found"}), 404
    body = request.get_json(silent=True) or {}
    if not isinstance(body, dict):
        return _jsonify({"error": "JSON body required"}), 400
    try:
        item = project_schedule_svc.create_schedule_item(pid, body)
    except ValueError as e:
        return _jsonify({"error": str(e)}), 400
    db.session.commit()
    return _jsonify({"item": item, "entity": "project_schedule_item"}), 201


@bp.patch("/projects/<project_id>/schedule-items/<item_id>")
def patch_project_schedule_item(project_id: str, item_id: str):
    pid = _parse_uuid_param(project_id)
    iid = _parse_uuid_param(item_id)
    if not pid or not iid:
        return _jsonify({"error": "invalid id"}), 400
    if not _project_exists(pid):
        return _jsonify({"error": "project not found"}), 404
    body = request.get_json(silent=True) or {}
    if not isinstance(body, dict):
        return _jsonify({"error": "JSON body required"}), 400
    try:
        item = project_schedule_svc.patch_schedule_item(pid, iid, body)
    except ValueError as e:
        return _jsonify({"error": str(e)}), 400
    if item is None:
        return _jsonify({"error": "schedule item not found"}), 404
    db.session.commit()
    return _jsonify({"item": item, "entity": "project_schedule_item"})


@bp.delete("/projects/<project_id>/schedule-items/<item_id>")
def delete_project_schedule_item(project_id: str, item_id: str):
    pid = _parse_uuid_param(project_id)
    iid = _parse_uuid_param(item_id)
    if not pid or not iid:
        return _jsonify({"error": "invalid id"}), 400
    if not _project_exists(pid):
        return _jsonify({"error": "project not found"}), 404
    ok = project_schedule_svc.delete_schedule_item(pid, iid)
    if not ok:
        return _jsonify({"error": "schedule item not found"}), 404
    db.session.commit()
    return _jsonify({"ok": True})


@bp.get("/projects/<project_id>/drawings")
def list_project_drawings(project_id: str):
    """Drawing log: one entry per sheet (``series_id``) with nested ``revisions`` (newest first)."""
    pid = _parse_uuid_param(project_id)
    if not pid:
        return _jsonify({"error": "invalid project id"}), 400
    if not _project_exists(pid):
        return _jsonify({"error": "project not found"}), 404

    q_raw = (request.args.get("q") or "").strip().lower()
    discipline_f = (request.args.get("discipline") or "").strip().lower()
    set_f = (request.args.get("drawing_set") or "").strip().lower()
    try:
        limit = max(1, min(int(request.args.get("limit") or 500), 2000))
    except ValueError:
        limit = 500
    try:
        offset = max(0, int(request.args.get("offset") or 0))
    except ValueError:
        offset = 0

    q = select(Drawing).where(Drawing.project_id == pid)
    q = q.order_by(Drawing.sheet_number.asc().nullslast(), Drawing.updated_at.desc())
    rows = list(db.session.scalars(q).all())

    sheets = _group_drawings_into_sheets(rows)
    if discipline_f:
        sheets = [
            s
            for s in sheets
            if discipline_f in (s.get("discipline") or "").lower()
        ]
    if set_f:
        sheets = [
            s
            for s in sheets
            if set_f in (s.get("drawing_set") or "").lower()
        ]
    if q_raw:

        def _sheet_matches(s: dict[str, Any]) -> bool:
            blob = " ".join(
                str(x).lower()
                for x in (
                    s.get("sheet_number"),
                    s.get("sheet_title"),
                    s.get("discipline"),
                    s.get("drawing_set"),
                    s.get("series_id"),
                    s.get("current_revision", {}).get("revision"),
                )
            )
            return q_raw in blob

        sheets = [s for s in sheets if _sheet_matches(s)]

    total = len(sheets)
    page = sheets[offset : offset + limit]

    return _jsonify(
        {
            "items": page,
            "total": total,
            "limit": limit,
            "offset": offset,
            "entity": "drawing_sheets",
        }
    )


@bp.get("/drawings/<drawing_id>/revisions")
def list_drawing_revisions(drawing_id: str):
    """All revisions in the same series as ``drawing_id`` (any revision id), newest first."""
    did = _parse_uuid_param(drawing_id)
    if not did:
        return _jsonify({"error": "invalid drawing id"}), 400
    row = db.session.get(Drawing, did)
    if row is None:
        return _jsonify({"error": "drawing not found"}), 404
    series_id = row.drawing_series_id
    q = select(Drawing).where(Drawing.drawing_series_id == series_id)
    group = list(db.session.scalars(q).all())
    ordered = sorted(group, key=_revision_sort_key, reverse=True)
    return _jsonify(
        {
            "entity": "drawing_revisions",
            "series_id": str(series_id),
            "project_id": str(row.project_id) if row.project_id else None,
            "revisions": [_drawing_public(r) for r in ordered],
        }
    )


def _drawing_object_name(drawing_id: uuid.UUID) -> str:
    return f"{drawing_id}.pdf"


def _drawing_resolved_file_url(d: Drawing) -> str | None:
    """DB ``file_url`` or, when missing, the standard upload path if a PDF exists on disk."""
    raw = d.file_url
    if raw is not None and str(raw).strip():
        return str(raw).strip()
    if stored_exists(UploadCategory.DRAWINGS, _drawing_object_name(d.id)):
        return f"/api/v1/drawings/{d.id}/file"
    return None


@bp.get("/drawings/<drawing_id>/file")
def get_drawing_pdf_file(drawing_id: str):
    """Stream an uploaded drawing PDF (same-origin for PDF.js)."""
    did = _parse_uuid_param(drawing_id)
    if not did:
        return _jsonify({"error": "invalid drawing id"}), 400
    row = db.session.get(Drawing, did)
    if row is None:
        return _jsonify({"error": "drawing not found"}), 404
    name = _drawing_object_name(did)
    dl = (row.original_filename or "drawing.pdf").replace('"', "")
    if not dl.lower().endswith(".pdf"):
        dl = dl + ".pdf"
    resp = send_stored_file(
        UploadCategory.DRAWINGS,
        name,
        mimetype="application/pdf",
        download_name=dl[:200],
    )
    if resp is None:
        return _jsonify({"error": "file not found on server"}), 404
    return resp


@bp.post("/projects/<project_id>/drawings")
def upload_project_drawing(project_id: str):
    """Multipart upload: field ``file`` (PDF). Multi-page PDFs split into one sheet per page by default."""
    from ..services.drawing_upload import DrawingUploadError, upload_project_drawing_pdf

    pid = _parse_uuid_param(project_id)
    if not pid:
        return _jsonify({"error": "invalid project id"}), 400
    if not _project_exists(pid):
        return _jsonify({"error": "project not found"}), 404
    f = request.files.get("file")
    if f is None or not getattr(f, "filename", None):
        return _jsonify({"error": "missing file field (multipart form-data)"}), 400
    max_bytes = 52_428_800  # 50 MiB
    cl = request.content_length
    if cl is not None and cl > max_bytes:
        return _jsonify({"error": "file too large (max 50MB)"}), 400

    sheet_number = (request.form.get("sheet_number") or "").strip()[:50] or None
    sheet_title = (request.form.get("sheet_title") or "").strip()[:500] or None
    discipline = (request.form.get("discipline") or "").strip()[:50] or None
    drawing_set = (request.form.get("drawing_set") or "").strip()[:120] or None
    revision = (request.form.get("revision") or "").strip()[:50] or "0"
    split_raw = request.form.get("split_pages")
    split_pages = split_raw is None or str(split_raw).strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )

    try:
        result = upload_project_drawing_pdf(
            project_id=pid,
            file_storage=f,
            sheet_number=sheet_number,
            sheet_title=sheet_title,
            discipline=discipline,
            drawing_set=drawing_set,
            revision=revision,
            split_pages=split_pages,
            max_bytes=max_bytes,
            drawing_public_fn=_drawing_public,
        )
    except DrawingUploadError as exc:
        db.session.rollback()
        return _jsonify({"error": exc.message}), exc.status
    except Exception as exc:
        db.session.rollback()
        current_app.logger.exception("drawing upload failed for project %s", project_id)
        detail = str(exc).strip() or exc.__class__.__name__
        if "pypdf" in detail.lower() or "No module named" in detail:
            detail = "PDF processing is unavailable on the server (missing pypdf). Contact your administrator."
        return _jsonify({"error": "drawing upload failed", "detail": detail}), 500

    db.session.commit()
    if result.get("split"):
        return _jsonify(result), 201
    return _jsonify({"item": result["item"], "entity": "drawing"}), 201


@bp.post("/drawings/<drawing_id>/delete")
def delete_drawing(drawing_id: str):
    """Delete one revision or the entire sheet series (all revisions).

    JSON body: ``{ "scope": "revision" | "series", "confirm": true }``.
    Uses POST so callers with projects *write* (not only admin) may remove drawings.
    """
    from ..services.drawing_delete import delete_drawing_revision, delete_drawing_series

    did = _parse_uuid_param(drawing_id)
    if not did:
        return _jsonify({"error": "invalid drawing id"}), 400
    body = request.get_json(silent=True) or {}
    if not isinstance(body, dict):
        return _jsonify({"error": "JSON body required"}), 400
    if not body.get("confirm"):
        return _jsonify({"error": "confirm must be true"}), 400
    scope = str(body.get("scope") or "revision").strip().lower()
    if scope not in ("revision", "series"):
        return _jsonify({"error": "scope must be revision or series"}), 400

    row = db.session.get(Drawing, did)
    if row is None:
        return _jsonify({"error": "drawing not found"}), 404

    if scope == "series":
        deleted = delete_drawing_series(row.drawing_series_id, project_id=row.project_id)
        if deleted == 0:
            return _jsonify({"error": "drawing not found"}), 404
        db.session.commit()
        return _jsonify(
            {
                "ok": True,
                "scope": "series",
                "deleted": deleted,
                "series_id": str(row.drawing_series_id),
            }
        )

    ok = delete_drawing_revision(did)
    if not ok:
        return _jsonify({"error": "drawing not found"}), 404
    db.session.commit()
    return _jsonify({"ok": True, "scope": "revision", "deleted": 1, "drawing_id": str(did)})


@bp.get("/spec-sections/<spec_section_id>/file")
def get_spec_section_pdf_file(spec_section_id: str):
    """Stream an uploaded spec-section PDF (same-origin for embedded viewers)."""
    sid = _parse_uuid_param(spec_section_id)
    if not sid:
        return _jsonify({"error": "invalid spec section id"}), 400
    row = db.session.get(SpecSection, sid)
    if row is None:
        return _jsonify({"error": "spec section not found"}), 404
    name = f"{sid}.pdf"
    base = secure_filename(f"{row.code} {row.title}".strip()) or "spec"
    dl = (base + ".pdf")[:200].replace('"', "")
    resp = send_stored_file(
        UploadCategory.SPEC_SECTIONS,
        name,
        mimetype="application/pdf",
        download_name=dl,
    )
    if resp is None:
        return _jsonify({"error": "file not found on server"}), 404
    return resp


def _rfi_list_filters_from_request() -> rfi_svc.ListFilters:
    status_raw = (request.args.get("status") or "").strip()
    statuses = [s.strip() for s in status_raw.split(",") if s.strip()] if status_raw else None
    return rfi_svc.ListFilters(
        status=statuses,
        assignee=_parse_uuid_param(request.args.get("assignee")),
        manager=_parse_uuid_param(request.args.get("manager")),
        in_recycle_bin=str(request.args.get("in_recycle_bin") or "").strip().lower()
        in ("1", "true", "yes", "on"),
        q=(request.args.get("q") or "").strip() or None,
        sort=(request.args.get("sort") or "number_asc").strip(),
        limit=max(1, min(int(request.args.get("limit") or 200), 1000)),
        offset=max(0, int(request.args.get("offset") or 0)),
    )


def _rfi_err(exc: rfi_svc.ApiError):
    return _jsonify({"error": exc.message}), exc.status


@bp.get("/projects/<project_id>/rfis")
def list_project_rfis(project_id: str):
    pid = _parse_uuid_param(project_id)
    if not pid:
        return _jsonify({"error": "invalid project id"}), 400
    if not _project_exists(pid):
        return _jsonify({"error": "project not found"}), 404
    try:
        return _jsonify(rfi_svc.list_rfis(pid, _rfi_list_filters_from_request(), current_user()))
    except rfi_svc.ApiError as exc:
        return _rfi_err(exc)


@bp.post("/projects/<project_id>/rfis")
def create_project_rfi(project_id: str):
    pid = _parse_uuid_param(project_id)
    if not pid:
        return _jsonify({"error": "invalid project id"}), 400
    data = request.get_json(silent=True) or {}
    try:
        return _jsonify(rfi_svc.create_rfi(pid, data, current_user())), 201
    except rfi_svc.ApiError as exc:
        return _rfi_err(exc)


@bp.get("/rfis/<rfi_id>")
def get_rfi(rfi_id: str):
    rid = _parse_uuid_param(rfi_id)
    if not rid:
        return _jsonify({"error": "invalid rfi id"}), 400
    try:
        return _jsonify(rfi_svc.get_rfi(rid, current_user()))
    except rfi_svc.ApiError as exc:
        return _rfi_err(exc)


@bp.patch("/rfis/<rfi_id>")
def patch_rfi(rfi_id: str):
    rid = _parse_uuid_param(rfi_id)
    if not rid:
        return _jsonify({"error": "invalid rfi id"}), 400
    data = request.get_json(silent=True) or {}
    try:
        return _jsonify(rfi_svc.patch_rfi(rid, data, current_user()))
    except rfi_svc.ApiError as exc:
        return _rfi_err(exc)


@bp.delete("/rfis/<rfi_id>")
def delete_rfi(rfi_id: str):
    rid = _parse_uuid_param(rfi_id)
    if not rid:
        return _jsonify({"error": "invalid rfi id"}), 400
    try:
        return _jsonify(rfi_svc.delete_rfi(rid, current_user()))
    except rfi_svc.ApiError as exc:
        return _rfi_err(exc)


@bp.post("/rfis/<rfi_id>/restore")
def restore_rfi(rfi_id: str):
    rid = _parse_uuid_param(rfi_id)
    if not rid:
        return _jsonify({"error": "invalid rfi id"}), 400
    try:
        return _jsonify(rfi_svc.restore_rfi(rid, current_user()))
    except rfi_svc.ApiError as exc:
        return _rfi_err(exc)


# ---------------------------------------------------------------------------
# Workflow endpoints (replies, official response, close/reopen, ball-in-court,
# assignees, distribution, forward)
# ---------------------------------------------------------------------------


@bp.post("/rfis/<rfi_id>/replies")
def add_rfi_reply(rfi_id: str):
    rid = _parse_uuid_param(rfi_id)
    if not rid:
        return _jsonify({"error": "invalid rfi id"}), 400
    data = request.get_json(silent=True) or {}
    try:
        return _jsonify(rfi_svc.add_reply(rid, data.get("body") or "", current_user())), 201
    except rfi_svc.ApiError as exc:
        return _rfi_err(exc)


@bp.delete("/rfis/<rfi_id>/replies/<reply_id>")
def delete_rfi_reply(rfi_id: str, reply_id: str):
    rid = _parse_uuid_param(rfi_id)
    pid = _parse_uuid_param(reply_id)
    if not rid or not pid:
        return _jsonify({"error": "invalid id"}), 400
    try:
        return _jsonify(rfi_svc.delete_reply(rid, pid, current_user()))
    except rfi_svc.ApiError as exc:
        return _rfi_err(exc)


@bp.post("/rfis/<rfi_id>/official-response")
def set_rfi_official_response(rfi_id: str):
    rid = _parse_uuid_param(rfi_id)
    if not rid:
        return _jsonify({"error": "invalid rfi id"}), 400
    data = request.get_json(silent=True) or {}
    rpid = _parse_uuid_param(data.get("reply_id"))
    if not rpid:
        return _jsonify({"error": "reply_id is required"}), 400
    try:
        return _jsonify(rfi_svc.set_official_response(rid, rpid, current_user()))
    except rfi_svc.ApiError as exc:
        return _rfi_err(exc)


@bp.post("/rfis/<rfi_id>/close")
def close_rfi(rfi_id: str):
    rid = _parse_uuid_param(rfi_id)
    if not rid:
        return _jsonify({"error": "invalid rfi id"}), 400
    try:
        return _jsonify(rfi_svc.close_rfi(rid, current_user()))
    except rfi_svc.ApiError as exc:
        return _rfi_err(exc)


@bp.post("/rfis/<rfi_id>/reopen")
def reopen_rfi(rfi_id: str):
    rid = _parse_uuid_param(rfi_id)
    if not rid:
        return _jsonify({"error": "invalid rfi id"}), 400
    try:
        return _jsonify(rfi_svc.reopen_rfi(rid, current_user()))
    except rfi_svc.ApiError as exc:
        return _rfi_err(exc)


@bp.post("/rfis/<rfi_id>/ball-in-court")
def shift_ball_in_court(rfi_id: str):
    rid = _parse_uuid_param(rfi_id)
    if not rid:
        return _jsonify({"error": "invalid rfi id"}), 400
    data = request.get_json(silent=True) or {}
    target = _parse_uuid_param(data.get("user_id")) if data.get("user_id") else None
    try:
        return _jsonify(rfi_svc.shift_ball_in_court(rid, target, current_user()))
    except rfi_svc.ApiError as exc:
        return _rfi_err(exc)


@bp.post("/rfis/<rfi_id>/assignees")
def add_rfi_assignee(rfi_id: str):
    rid = _parse_uuid_param(rfi_id)
    if not rid:
        return _jsonify({"error": "invalid rfi id"}), 400
    data = request.get_json(silent=True) or {}
    uid = _parse_uuid_param(data.get("user_id"))
    if not uid:
        return _jsonify({"error": "user_id is required"}), 400
    try:
        return _jsonify(
            rfi_svc.add_assignee(
                rid,
                uid,
                is_required=bool(data.get("is_required")),
                cu=current_user(),
            )
        )
    except rfi_svc.ApiError as exc:
        return _rfi_err(exc)


@bp.delete("/rfis/<rfi_id>/assignees/<user_id>")
def remove_rfi_assignee(rfi_id: str, user_id: str):
    rid = _parse_uuid_param(rfi_id)
    uid = _parse_uuid_param(user_id)
    if not rid or not uid:
        return _jsonify({"error": "invalid id"}), 400
    try:
        return _jsonify(rfi_svc.remove_assignee(rid, uid, current_user()))
    except rfi_svc.ApiError as exc:
        return _rfi_err(exc)


@bp.post("/rfis/<rfi_id>/forward-for-review")
def forward_rfi(rfi_id: str):
    rid = _parse_uuid_param(rfi_id)
    if not rid:
        return _jsonify({"error": "invalid rfi id"}), 400
    data = request.get_json(silent=True) or {}
    uid = _parse_uuid_param(data.get("user_id"))
    if not uid:
        return _jsonify({"error": "user_id is required"}), 400
    try:
        return _jsonify(
            rfi_svc.forward_for_review(rid, uid, (data.get("message") or "").strip() or None, current_user())
        )
    except rfi_svc.ApiError as exc:
        return _rfi_err(exc)


@bp.post("/rfis/<rfi_id>/distribution")
def add_rfi_distribution(rfi_id: str):
    rid = _parse_uuid_param(rfi_id)
    if not rid:
        return _jsonify({"error": "invalid rfi id"}), 400
    data = request.get_json(silent=True) or {}
    uid = _parse_uuid_param(data.get("user_id"))
    if not uid:
        return _jsonify({"error": "user_id is required"}), 400
    try:
        return _jsonify(rfi_svc.add_distribution(rid, uid, current_user()))
    except rfi_svc.ApiError as exc:
        return _rfi_err(exc)


@bp.delete("/rfis/<rfi_id>/distribution/<user_id>")
def remove_rfi_distribution(rfi_id: str, user_id: str):
    rid = _parse_uuid_param(rfi_id)
    uid = _parse_uuid_param(user_id)
    if not rid or not uid:
        return _jsonify({"error": "invalid id"}), 400
    try:
        return _jsonify(rfi_svc.remove_distribution(rid, uid, current_user()))
    except rfi_svc.ApiError as exc:
        return _rfi_err(exc)


# ---------------------------------------------------------------------------
# Attachments + email + bulk + export + saved views + column prefs
# ---------------------------------------------------------------------------


@bp.post("/rfis/<rfi_id>/attachments")
def add_rfi_attachment(rfi_id: str):
    rid = _parse_uuid_param(rfi_id)
    if not rid:
        return _jsonify({"error": "invalid rfi id"}), 400
    data = request.get_json(silent=True) or {}
    try:
        return _jsonify(rfi_svc.add_attachment(rid, data, current_user())), 201
    except rfi_svc.ApiError as exc:
        return _rfi_err(exc)


@bp.delete("/rfis/<rfi_id>/attachments/<document_id>")
def remove_rfi_attachment(rfi_id: str, document_id: str):
    rid = _parse_uuid_param(rfi_id)
    did = _parse_uuid_param(document_id)
    if not rid or not did:
        return _jsonify({"error": "invalid id"}), 400
    try:
        return _jsonify(rfi_svc.remove_attachment(rid, did, current_user()))
    except rfi_svc.ApiError as exc:
        return _rfi_err(exc)


_RFI_UPLOAD_EXT = frozenset({".pdf", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".txt", ".csv"})


@bp.post("/rfis/<rfi_id>/attachments/upload")
def upload_rfi_attachment_multipart(rfi_id: str):
    """Multipart ``file`` upload; returns ``file_url`` suitable for the RFI detail view."""
    rid = _parse_uuid_param(rfi_id)
    if not rid:
        return _jsonify({"error": "invalid rfi id"}), 400
    rfi = db.session.get(Rfi, rid)
    if rfi is None:
        return _jsonify({"error": "RFI not found"}), 404
    if not can_edit_rfi(current_user(), rfi):
        return _jsonify({"error": "not authorized"}), 403
    f = request.files.get("file")
    if f is None or not getattr(f, "filename", None):
        return _jsonify({"error": "missing file field (multipart form-data)"}), 400
    raw_name = secure_filename(f.filename) or "upload.bin"
    ext = Path(raw_name).suffix.lower() or ".bin"
    if ext not in _RFI_UPLOAD_EXT:
        return _jsonify({"error": f"unsupported file type ({ext}); allowed: {', '.join(sorted(_RFI_UPLOAD_EXT))}"}), 400
    max_bytes = 52_428_800
    cl = request.content_length
    if cl is not None and cl > max_bytes:
        return _jsonify({"error": "file too large (max 50MB)"}), 400

    doc = Document(
        project_id=rfi.project_id,
        document_type="other",
        title=raw_name[:500],
        original_filename=raw_name[:500],
        mime_type=(f.mimetype or "").strip()[:120] or None,
        uploaded_by_user_id=current_user().id,
        tags={"rfi_id": str(rfi.id), "entity": "rfi", "suffix": ext},
    )
    db.session.add(doc)
    db.session.flush()

    obj_name = f"{doc.id}{ext}"
    try:
        sz = save_upload(UploadCategory.RFI_ATTACHMENTS, obj_name, f)
    except OSError as exc:
        db.session.rollback()
        return _jsonify({"error": f"could not save file: {exc}"}), 500
    except Exception as exc:
        db.session.rollback()
        return _jsonify({"error": f"could not save file: {exc}"}), 500
    if sz == 0:
        delete_stored(UploadCategory.RFI_ATTACHMENTS, obj_name)
        db.session.rollback()
        return _jsonify({"error": "empty upload"}), 400
    if sz > max_bytes:
        delete_stored(UploadCategory.RFI_ATTACHMENTS, obj_name)
        db.session.rollback()
        return _jsonify({"error": "file too large (max 50MB)"}), 400

    doc.file_url = f"/api/v1/rfi-attachments/{doc.id}/file"
    doc.file_size_bytes = int(sz) if sz is not None else None
    db.session.commit()
    return _jsonify(
        {
            "item": {
                "id": str(doc.id),
                "title": doc.title,
                "file_url": doc.file_url,
                "filename": doc.original_filename,
                "mime_type": doc.mime_type,
                "file_size_bytes": doc.file_size_bytes,
            },
            "entity": "rfi_attachment",
        }
    ), 201


@bp.get("/rfi-attachments/<document_id>/file")
def get_rfi_attachment_file(document_id: str):
    did = _parse_uuid_param(document_id)
    if not did:
        return _jsonify({"error": "invalid document id"}), 400
    row = db.session.get(Document, did)
    if row is None:
        return _jsonify({"error": "not found"}), 404
    tags = row.tags or {}
    if str(tags.get("rfi_id") or "") == "" or tags.get("entity") != "rfi":
        return _jsonify({"error": "not found"}), 404
    ext = str(tags.get("suffix") or ".bin")
    name = f"{did}{ext}"
    dl = (row.original_filename or "attachment").replace('"', "")[:200]
    mt = row.mime_type or "application/octet-stream"
    resp = send_stored_file(
        UploadCategory.RFI_ATTACHMENTS,
        name,
        mimetype=mt,
        download_name=dl,
    )
    if resp is None:
        return _jsonify({"error": "file not found on server"}), 404
    return resp


@bp.post("/rfis/<rfi_id>/email")
def email_rfi(rfi_id: str):
    rid = _parse_uuid_param(rfi_id)
    if not rid:
        return _jsonify({"error": "invalid rfi id"}), 400
    data = request.get_json(silent=True) or {}
    try:
        return _jsonify(rfi_svc.forward_by_email(rid, data, current_user()))
    except rfi_svc.ApiError as exc:
        return _rfi_err(exc)


@bp.post("/messages/email")
def compose_email():
    """Outbound mail from ``email-compose.html`` (requires signed-in user)."""
    cu = current_user()
    if cu.user is None:
        return _jsonify({"error": "sign in required"}), 401
    data = request.get_json(silent=True) or {}
    to = (data.get("to") or "").strip()
    if not to:
        return _jsonify({"error": "'to' is required"}), 400
    subject = (data.get("subject") or "").strip() or "(no subject)"
    body = (data.get("message") or data.get("body") or "").strip()
    cc = (data.get("cc") or "").strip() or None
    from ._notifications import send_compose_email

    result = send_compose_email(to=to, subject=subject[:500], body=body, cc=cc)
    if not result.get("ok"):
        return _jsonify(result), 400
    return _jsonify(result)


@bp.post("/rfis/bulk")
def bulk_rfi_action():
    data = request.get_json(silent=True) or {}
    try:
        return _jsonify(rfi_svc.bulk_action(data, current_user()))
    except rfi_svc.ApiError as exc:
        return _rfi_err(exc)


@bp.get("/projects/<project_id>/rfis/export")
def export_project_rfis(project_id: str):
    pid = _parse_uuid_param(project_id)
    if not pid:
        return _jsonify({"error": "invalid project id"}), 400
    fmt = (request.args.get("format") or "csv").strip().lower()
    try:
        if fmt == "csv":
            csv_text = rfi_svc.export_rfis_csv(pid, _rfi_list_filters_from_request(), current_user())
            return Response(
                csv_text,
                mimetype="text/csv",
                headers={"Content-Disposition": f"attachment; filename=rfis_{project_id}.csv"},
            )
        if fmt == "json":
            return _jsonify(rfi_svc.list_rfis(pid, _rfi_list_filters_from_request(), current_user()))
        return _jsonify({"error": f"unsupported format: {fmt}"}), 400
    except rfi_svc.ApiError as exc:
        return _rfi_err(exc)


# Saved views ---------------------------------------------------------------


@bp.get("/rfi-saved-views")
def list_rfi_saved_views():
    pid = _parse_uuid_param(request.args.get("project_id"))
    try:
        return _jsonify(rfi_svc.list_saved_views(pid, current_user()))
    except rfi_svc.ApiError as exc:
        return _rfi_err(exc)


@bp.post("/rfi-saved-views")
def create_rfi_saved_view():
    data = request.get_json(silent=True) or {}
    try:
        return _jsonify(rfi_svc.create_saved_view(data, current_user())), 201
    except rfi_svc.ApiError as exc:
        return _rfi_err(exc)


@bp.patch("/rfi-saved-views/<view_id>")
def update_rfi_saved_view(view_id: str):
    vid = _parse_uuid_param(view_id)
    if not vid:
        return _jsonify({"error": "invalid id"}), 400
    data = request.get_json(silent=True) or {}
    try:
        return _jsonify(rfi_svc.update_saved_view(vid, data, current_user()))
    except rfi_svc.ApiError as exc:
        return _rfi_err(exc)


@bp.delete("/rfi-saved-views/<view_id>")
def delete_rfi_saved_view(view_id: str):
    vid = _parse_uuid_param(view_id)
    if not vid:
        return _jsonify({"error": "invalid id"}), 400
    try:
        return _jsonify(rfi_svc.delete_saved_view(vid, current_user()))
    except rfi_svc.ApiError as exc:
        return _rfi_err(exc)


# Column prefs --------------------------------------------------------------


@bp.get("/rfi-column-prefs/<scope_key>")
def get_rfi_column_prefs(scope_key: str):
    try:
        return _jsonify(rfi_svc.get_column_prefs(scope_key, current_user()))
    except rfi_svc.ApiError as exc:
        return _rfi_err(exc)


@bp.put("/rfi-column-prefs/<scope_key>")
def put_rfi_column_prefs(scope_key: str):
    data = request.get_json(silent=True) or {}
    try:
        return _jsonify(rfi_svc.put_column_prefs(scope_key, data, current_user()))
    except rfi_svc.ApiError as exc:
        return _rfi_err(exc)


# Lookups (Locations, Spec Sections, Cost Codes, Project Stages, Sub Jobs) --


@bp.get("/projects/<project_id>/rfi-lookups/<kind>")
def list_rfi_lookups(project_id: str, kind: str):
    pid = _parse_uuid_param(project_id)
    if not pid:
        return _jsonify({"error": "invalid project id"}), 400
    try:
        return _jsonify({"items": rfi_svc.list_lookup(pid, kind), "entity": kind})
    except rfi_svc.ApiError as exc:
        return _rfi_err(exc)


@bp.post("/projects/<project_id>/rfi-lookups/<kind>")
def create_rfi_lookup(project_id: str, kind: str):
    pid = _parse_uuid_param(project_id)
    if not pid:
        return _jsonify({"error": "invalid project id"}), 400
    data = request.get_json(silent=True) or {}
    try:
        return _jsonify({"item": rfi_svc.create_lookup(pid, kind, data), "entity": kind}), 201
    except rfi_svc.ApiError as exc:
        return _rfi_err(exc)


@bp.patch("/projects/<project_id>/rfi-lookups/<kind>/<row_id>")
def patch_rfi_lookup(project_id: str, kind: str, row_id: str):
    pid = _parse_uuid_param(project_id)
    rid = _parse_uuid_param(row_id)
    if not pid or not rid:
        return _jsonify({"error": "invalid id"}), 400
    if not _project_exists(pid):
        return _jsonify({"error": "project not found"}), 404
    data = request.get_json(silent=True) or {}
    if not isinstance(data, Mapping):
        return _jsonify({"error": "expected JSON object body"}), 400
    try:
        return _jsonify({"item": rfi_svc.patch_lookup(pid, kind, rid, data), "entity": kind})
    except rfi_svc.ApiError as exc:
        return _rfi_err(exc)


@bp.post("/projects/<project_id>/rfi-lookups/spec_sections/<row_id>/file")
def upload_spec_section_pdf(project_id: str, row_id: str):
    """Multipart upload: field ``file`` (PDF); sets ``pdf_url`` to the API file route."""
    pid = _parse_uuid_param(project_id)
    rid = _parse_uuid_param(row_id)
    if not pid or not rid:
        return _jsonify({"error": "invalid id"}), 400
    if not _project_exists(pid):
        return _jsonify({"error": "project not found"}), 404
    row = db.session.get(SpecSection, rid)
    if row is None or row.project_id != pid:
        return _jsonify({"error": "spec section not found"}), 404
    f = request.files.get("file")
    if f is None or not getattr(f, "filename", None):
        return _jsonify({"error": "missing file field (multipart form-data)"}), 400
    raw_name = secure_filename(f.filename) or "upload.pdf"
    if not raw_name.lower().endswith(".pdf"):
        return _jsonify({"error": "only PDF uploads are supported"}), 400
    max_bytes = 52_428_800  # 50 MiB
    cl = request.content_length
    if cl is not None and cl > max_bytes:
        return _jsonify({"error": "file too large (max 50MB)"}), 400

    obj_name = f"{row.id}.pdf"
    try:
        sz = save_upload(UploadCategory.SPEC_SECTIONS, obj_name, f)
    except OSError as exc:
        return _jsonify({"error": f"could not save file: {exc}"}), 500
    except Exception as exc:
        return _jsonify({"error": f"could not save file: {exc}"}), 500

    if sz == 0:
        delete_stored(UploadCategory.SPEC_SECTIONS, obj_name)
        return _jsonify({"error": "empty upload"}), 400
    if sz > max_bytes:
        delete_stored(UploadCategory.SPEC_SECTIONS, obj_name)
        return _jsonify({"error": "file too large (max 50MB)"}), 400

    row.pdf_url = f"/api/v1/spec-sections/{row.id}/file"
    db.session.commit()
    return _jsonify({"item": rfi_svc.lookup_public(row), "entity": "spec_sections"}), 201


# Custom fields + configurable fields (Phase 5) ------------------------------


@bp.get("/rfi-custom-field-defs")
def list_rfi_custom_field_defs():
    company_id = _parse_uuid_param(request.args.get("company_id"))
    return _jsonify(rfi_svc.list_custom_field_defs(company_id))


@bp.post("/rfi-custom-field-defs")
def create_rfi_custom_field_def():
    data = request.get_json(silent=True) or {}
    try:
        result = rfi_svc.create_custom_field_def(data, current_user())
        return _jsonify(result), 201
    except rfi_svc.ApiError as exc:
        return _rfi_err(exc)


@bp.patch("/rfi-custom-field-defs/<def_id>")
def patch_rfi_custom_field_def(def_id: str):
    did = _parse_uuid_param(def_id)
    if not did:
        return _jsonify({"error": "invalid id"}), 400
    data = request.get_json(silent=True) or {}
    try:
        return _jsonify(rfi_svc.patch_custom_field_def(did, data, current_user()))
    except rfi_svc.ApiError as exc:
        return _rfi_err(exc)


@bp.delete("/rfi-custom-field-defs/<def_id>")
def delete_rfi_custom_field_def(def_id: str):
    did = _parse_uuid_param(def_id)
    if not did:
        return _jsonify({"error": "invalid id"}), 400
    try:
        return _jsonify(rfi_svc.delete_custom_field_def(did, current_user()))
    except rfi_svc.ApiError as exc:
        return _rfi_err(exc)


@bp.post("/rfis/<rfi_id>/custom-fields")
def upsert_rfi_custom_field_value(rfi_id: str):
    rid = _parse_uuid_param(rfi_id)
    if not rid:
        return _jsonify({"error": "invalid rfi id"}), 400
    data = request.get_json(silent=True) or {}
    try:
        return _jsonify(rfi_svc.upsert_custom_field_value(rid, data, current_user()))
    except rfi_svc.ApiError as exc:
        return _rfi_err(exc)


@bp.get("/rfi-configurable-fields")
def list_rfi_configurable_fields():
    project_id = _parse_uuid_param(request.args.get("project_id"))
    return _jsonify(rfi_svc.list_configurable_fields(project_id))


@bp.put("/rfi-configurable-fields")
def upsert_rfi_configurable_field():
    data = request.get_json(silent=True) or {}
    try:
        return _jsonify(rfi_svc.upsert_configurable_field(data, current_user()))
    except rfi_svc.ApiError as exc:
        return _rfi_err(exc)


# Revisions + cross-tool create (Phase 5) -----------------------------------


@bp.post("/rfis/<rfi_id>/revise")
def revise_rfi(rfi_id: str):
    rid = _parse_uuid_param(rfi_id)
    if not rid:
        return _jsonify({"error": "invalid rfi id"}), 400
    data = request.get_json(silent=True) or {}
    try:
        return _jsonify(rfi_svc.revise_rfi(rid, (data.get("reason") or "").strip() or None, current_user()))
    except rfi_svc.ApiError as exc:
        return _rfi_err(exc)


@bp.post("/rfis/<rfi_id>/create-change-event")
def create_change_event_from_rfi(rfi_id: str):
    rid = _parse_uuid_param(rfi_id)
    if not rid:
        return _jsonify({"error": "invalid rfi id"}), 400
    data = request.get_json(silent=True) or {}
    try:
        return _jsonify(rfi_svc.create_change_event(rid, data, current_user())), 201
    except rfi_svc.ApiError as exc:
        return _rfi_err(exc)


@bp.post("/rfis/<rfi_id>/create-pco")
def create_pco_from_rfi(rfi_id: str):
    rid = _parse_uuid_param(rfi_id)
    if not rid:
        return _jsonify({"error": "invalid rfi id"}), 400
    data = request.get_json(silent=True) or {}
    try:
        return _jsonify(rfi_svc.create_pco(rid, data, current_user())), 201
    except rfi_svc.ApiError as exc:
        return _rfi_err(exc)


@bp.post("/rfis/<rfi_id>/create-instruction")
def create_instruction_from_rfi(rfi_id: str):
    rid = _parse_uuid_param(rfi_id)
    if not rid:
        return _jsonify({"error": "invalid rfi id"}), 400
    data = request.get_json(silent=True) or {}
    try:
        return _jsonify(rfi_svc.create_instruction(rid, data, current_user())), 201
    except rfi_svc.ApiError as exc:
        return _rfi_err(exc)


# AI Draft Agent (Phase 6) --------------------------------------------------


@bp.post("/rfis/draft-assist")
def rfi_draft_assist():
    data = request.get_json(silent=True) or {}
    try:
        return _jsonify(rfi_svc.draft_assist(data, current_user()))
    except rfi_svc.ApiError as exc:
        return _rfi_err(exc)


# User picker (Assignees / RFI Manager / Distribution / Received From) ------


@bp.get("/rfi-users")
def list_rfi_users():
    q = (request.args.get("q") or "").strip().lower()
    limit = max(1, min(int(request.args.get("limit") or 50), 200))
    users = users_for_picker()
    if q:
        users = [
            u
            for u in users
            if (u.email and q in u.email.lower())
            or (u.first_name and q in u.first_name.lower())
            or (u.last_name and q in u.last_name.lower())
        ]
    out = []
    for u in users[:limit]:
        name = " ".join(p for p in (u.first_name, u.last_name) if p).strip() or u.email
        out.append({"id": str(u.id), "name": name, "email": u.email})
    return _jsonify({"items": out, "entity": "users"})


def _admin_directory_err(exc: admin_users_svc.ApiError):
    return _jsonify({"error": exc.message}), exc.status


@bp.get("/admin/roles")
def admin_list_roles():
    try:
        items = admin_users_svc.list_roles(current_user())
        return _jsonify({"items": items, "entity": "roles"})
    except admin_users_svc.ApiError as exc:
        return _admin_directory_err(exc)


@bp.get("/admin/roles/<role_id>")
def admin_get_role(role_id: str):
    rid = _parse_uuid_param(role_id)
    if not rid:
        return _jsonify({"error": "invalid role id"}), 400
    try:
        item = admin_users_svc.get_role(current_user(), rid)
    except admin_users_svc.ApiError as exc:
        return _admin_directory_err(exc)
    if item is None:
        return _jsonify({"error": "role not found"}), 404
    return _jsonify({"item": item, "entity": "role"})


@bp.post("/admin/roles")
def admin_create_role():
    body = request.get_json(silent=True) or {}
    if not isinstance(body, dict):
        return _jsonify({"error": "JSON body required"}), 400
    try:
        item = admin_users_svc.create_role(current_user(), body)
    except admin_users_svc.ApiError as exc:
        return _admin_directory_err(exc)
    db.session.commit()
    return _jsonify({"item": item, "entity": "role"}), 201


@bp.patch("/admin/roles/<role_id>")
def admin_patch_role(role_id: str):
    rid = _parse_uuid_param(role_id)
    if not rid:
        return _jsonify({"error": "invalid role id"}), 400
    body = request.get_json(silent=True) or {}
    if not isinstance(body, dict):
        return _jsonify({"error": "JSON body required"}), 400
    try:
        item = admin_users_svc.patch_role(current_user(), rid, body)
    except admin_users_svc.ApiError as exc:
        return _admin_directory_err(exc)
    if item is None:
        return _jsonify({"error": "role not found"}), 404
    db.session.commit()
    return _jsonify({"item": item, "entity": "role"})


@bp.get("/admin/users")
def admin_list_users():
    q = (request.args.get("q") or "").strip() or None
    try:
        limit = max(1, min(int(request.args.get("limit") or 100), 500))
        offset = max(0, int(request.args.get("offset") or 0))
    except ValueError:
        return _jsonify({"error": "invalid limit or offset"}), 400
    try:
        items, total = admin_users_svc.list_users(
            current_user(), q=q, limit=limit, offset=offset
        )
        return _jsonify(
            {
                "items": items,
                "total": total,
                "limit": limit,
                "offset": offset,
                "entity": "directory_users",
            }
        )
    except admin_users_svc.ApiError as exc:
        return _admin_directory_err(exc)


@bp.get("/admin/users/<user_id>")
def admin_get_user(user_id: str):
    uid = _parse_uuid_param(user_id)
    if not uid:
        return _jsonify({"error": "invalid user id"}), 400
    try:
        item = admin_users_svc.get_user(current_user(), uid)
    except admin_users_svc.ApiError as exc:
        return _admin_directory_err(exc)
    if item is None:
        return _jsonify({"error": "user not found"}), 404
    return _jsonify({"item": item, "entity": "directory_user"})


@bp.post("/admin/users")
def admin_create_user():
    body = request.get_json(silent=True) or {}
    if not isinstance(body, dict):
        return _jsonify({"error": "JSON body required"}), 400
    try:
        item = admin_users_svc.create_user(current_user(), body)
    except admin_users_svc.ApiError as exc:
        return _admin_directory_err(exc)
    db.session.commit()
    return _jsonify({"item": item, "entity": "directory_user"}), 201


@bp.get("/admin/purge-test-users")
def admin_preview_purge_test_users():
    include_hr = (request.args.get("include_hr_demos") or "").strip().lower() in (
        "1",
        "true",
        "yes",
    )
    try:
        sample = max(0, min(int(request.args.get("sample") or 20), 100))
    except ValueError:
        return _jsonify({"error": "invalid sample"}), 400
    try:
        result = admin_users_svc.preview_purge_test_users(
            current_user(),
            include_hr_demos=include_hr,
            sample=sample,
        )
    except admin_users_svc.ApiError as exc:
        return _admin_directory_err(exc)
    return _jsonify(result)


@bp.post("/admin/purge-test-users")
def admin_purge_test_users():
    body = request.get_json(silent=True) or {}
    if not isinstance(body, dict):
        return _jsonify({"error": "JSON body required"}), 400
    include_hr = bool(body.get("include_hr_demos"))
    confirm = bool(body.get("confirm"))
    try:
        result = admin_users_svc.purge_test_users(
            current_user(),
            include_hr_demos=include_hr,
            confirm=confirm,
        )
    except admin_users_svc.ApiError as exc:
        return _admin_directory_err(exc)
    db.session.commit()
    return _jsonify(result)


@bp.patch("/admin/users/<user_id>")
def admin_patch_user(user_id: str):
    uid = _parse_uuid_param(user_id)
    if not uid:
        return _jsonify({"error": "invalid user id"}), 400
    body = request.get_json(silent=True) or {}
    if not isinstance(body, dict):
        return _jsonify({"error": "JSON body required"}), 400
    try:
        item = admin_users_svc.patch_user(current_user(), uid, body)
    except admin_users_svc.ApiError as exc:
        return _admin_directory_err(exc)
    if item is None:
        return _jsonify({"error": "user not found"}), 404
    db.session.commit()
    return _jsonify({"item": item, "entity": "directory_user"})


def _project_membership_err(exc: project_members_svc.ApiError):
    return _jsonify({"error": exc.message}), exc.status


@bp.get("/admin/users/<user_id>/project-memberships")
def admin_get_user_project_memberships(user_id: str):
    uid = _parse_uuid_param(user_id)
    if not uid:
        return _jsonify({"error": "invalid user id"}), 400
    try:
        body = project_members_svc.list_user_project_memberships(current_user(), uid)
    except project_members_svc.ApiError as exc:
        return _project_membership_err(exc)
    if body is None:
        return _jsonify({"error": "user not found"}), 404
    return _jsonify({**body, "entity": "user_project_memberships"})


@bp.put("/admin/users/<user_id>/project-memberships")
def admin_put_user_project_memberships(user_id: str):
    uid = _parse_uuid_param(user_id)
    if not uid:
        return _jsonify({"error": "invalid user id"}), 400
    body = request.get_json(silent=True) or {}
    if not isinstance(body, dict):
        return _jsonify({"error": "JSON body required"}), 400
    try:
        result = project_members_svc.set_user_project_memberships(current_user(), uid, body)
    except project_members_svc.ApiError as exc:
        return _project_membership_err(exc)
    if result is None:
        return _jsonify({"error": "user not found"}), 404
    db.session.commit()
    return _jsonify({**result, "entity": "user_project_memberships"})


@bp.get("/projects/<project_id>/members")
def get_project_members(project_id: str):
    pid = _parse_uuid_param(project_id)
    if not pid:
        return _jsonify({"error": "invalid project id"}), 400
    try:
        body = project_members_svc.list_project_members(current_user(), pid)
    except project_members_svc.ApiError as exc:
        return _project_membership_err(exc)
    if body is None:
        return _jsonify({"error": "project not found"}), 404
    return _jsonify({**body, "entity": "project_members"})


@bp.put("/projects/<project_id>/members")
def put_project_members(project_id: str):
    pid = _parse_uuid_param(project_id)
    if not pid:
        return _jsonify({"error": "invalid project id"}), 400
    body = request.get_json(silent=True) or {}
    if not isinstance(body, dict):
        return _jsonify({"error": "JSON body required"}), 400
    try:
        result = project_members_svc.set_project_members(current_user(), pid, body)
    except project_members_svc.ApiError as exc:
        return _project_membership_err(exc)
    if result is None:
        return _jsonify({"error": "project not found"}), 404
    db.session.commit()
    return _jsonify({**result, "entity": "project_members"})


@bp.get("/rfi-companies")
def list_rfi_companies():
    q = (request.args.get("q") or "").strip().lower()
    limit = max(1, min(int(request.args.get("limit") or 50), 200))
    stmt = select(Company).where(Company.deleted_at.is_(None)).order_by(Company.name.asc()).limit(500)
    rows = db.session.scalars(stmt).all()
    if q:
        rows = [c for c in rows if q in (c.name or "").lower()]
    return _jsonify(
        {
            "items": [
                {"id": str(c.id), "name": c.name, "company_type": c.company_type}
                for c in rows[:limit]
            ],
            "entity": "companies",
        }
    )


def _submittal_err(exc: submittal_svc.ApiError):
    return _jsonify({"error": exc.message}), exc.status


@bp.get("/projects/<project_id>/submittals")
def list_project_submittals(project_id: str):
    pid = _parse_uuid_param(project_id)
    if not pid:
        return _jsonify({"error": "invalid project id"}), 400
    if not _project_exists(pid):
        return _jsonify({"error": "project not found"}), 404
    return _jsonify(submittal_svc.list_submittals(pid))


@bp.get("/projects/<project_id>/submittals/<submittal_id>")
def get_project_submittal(project_id: str, submittal_id: str):
    pid = _parse_uuid_param(project_id)
    sid = _parse_uuid_param(submittal_id)
    if not pid or not sid:
        return _jsonify({"error": "invalid id"}), 400
    if not _project_exists(pid):
        return _jsonify({"error": "project not found"}), 404
    try:
        body = submittal_svc.get_submittal_detail(sid, current_user())
    except submittal_svc.ApiError as exc:
        return _submittal_err(exc)
    if str(body["item"]["project_id"]) != str(pid):
        return _jsonify({"error": "submittal not found"}), 404
    return _jsonify(body)


@bp.post("/projects/<project_id>/submittals")
def create_project_submittal(project_id: str):
    pid = _parse_uuid_param(project_id)
    if not pid:
        return _jsonify({"error": "invalid project id"}), 400
    if not _project_exists(pid):
        return _jsonify({"error": "project not found"}), 404
    data = request.get_json(silent=True) or {}
    try:
        return _jsonify(submittal_svc.create_submittal(pid, data, current_user())), 201
    except submittal_svc.ApiError as exc:
        return _submittal_err(exc)


@bp.patch("/projects/<project_id>/submittals/<submittal_id>")
def patch_project_submittal(project_id: str, submittal_id: str):
    pid = _parse_uuid_param(project_id)
    sid = _parse_uuid_param(submittal_id)
    if not pid or not sid:
        return _jsonify({"error": "invalid id"}), 400
    if not _project_exists(pid):
        return _jsonify({"error": "project not found"}), 404
    data = request.get_json(silent=True) or {}
    try:
        body = submittal_svc.patch_submittal(sid, data, current_user())
    except submittal_svc.ApiError as exc:
        return _submittal_err(exc)
    if str(body["item"]["project_id"]) != str(pid):
        return _jsonify({"error": "submittal not found"}), 404
    return _jsonify(body)


@bp.post("/projects/<project_id>/submittals/<submittal_id>/attachments")
def post_submittal_attachment(project_id: str, submittal_id: str):
    pid = _parse_uuid_param(project_id)
    sid = _parse_uuid_param(submittal_id)
    if not pid or not sid:
        return _jsonify({"error": "invalid id"}), 400
    if not _project_exists(pid):
        return _jsonify({"error": "project not found"}), 404
    s = db.session.get(Submittal, sid)
    if s is None or s.project_id != pid:
        return _jsonify({"error": "submittal not found"}), 404
    data = request.get_json(silent=True) or {}
    try:
        body = submittal_svc.add_submittal_attachment(sid, data, current_user())
    except submittal_svc.ApiError as exc:
        return _submittal_err(exc)
    return _jsonify(body), 201


@bp.get("/documents/<document_id>/submittal-annotations")
def get_submittal_document_annotations(document_id: str):
    did = _parse_uuid_param(document_id)
    if not did:
        return _jsonify({"error": "invalid document id"}), 400
    try:
        return _jsonify(submittal_svc.get_document_annotations(did, current_user()))
    except submittal_svc.ApiError as exc:
        return _submittal_err(exc)


@bp.put("/documents/<document_id>/submittal-annotations")
def put_submittal_document_annotations(document_id: str):
    did = _parse_uuid_param(document_id)
    if not did:
        return _jsonify({"error": "invalid document id"}), 400
    data = request.get_json(silent=True) or {}
    try:
        return _jsonify(submittal_svc.put_document_annotations(did, data, current_user()))
    except submittal_svc.ApiError as exc:
        return _submittal_err(exc)


def _commitment_err(exc: rfi_svc.ApiError):
    return _jsonify({"error": exc.message}), exc.status


def _proc_lookup_err(exc: rfi_svc.ApiError):
    return _jsonify({"error": exc.message}), exc.status


@bp.get("/procurement/po-types")
def list_procurement_po_types():
    try:
        return _jsonify(proc_lookup_svc.list_po_types(current_user()))
    except rfi_svc.ApiError as exc:
        return _proc_lookup_err(exc)


@bp.get("/companies/<company_id>/procurement-profile")
def get_company_procurement_profile(company_id: str):
    cid = _parse_uuid_param(company_id)
    if not cid:
        return _jsonify({"error": "invalid company id"}), 400
    try:
        return _jsonify(proc_lookup_svc.get_company_procurement_profile(cid, current_user()))
    except rfi_svc.ApiError as exc:
        return _proc_lookup_err(exc)


@bp.get("/projects/<project_id>/directory/companies")
def list_project_directory_companies(project_id: str):
    pid = _parse_uuid_param(project_id)
    if not pid:
        return _jsonify({"error": "invalid project id"}), 400
    if not _project_exists(pid):
        return _jsonify({"error": "project not found"}), 404
    q = (request.args.get("q") or "").strip()
    try:
        limit = int(request.args.get("limit") or 20)
    except ValueError:
        return _jsonify({"error": "invalid limit"}), 400
    try:
        return _jsonify(proc_lookup_svc.list_directory_companies(pid, current_user(), q=q, limit=limit))
    except rfi_svc.ApiError as exc:
        return _proc_lookup_err(exc)


@bp.post("/projects/<project_id>/directory/companies")
def add_project_directory_company(project_id: str):
    pid = _parse_uuid_param(project_id)
    if not pid:
        return _jsonify({"error": "invalid project id"}), 400
    if not _project_exists(pid):
        return _jsonify({"error": "project not found"}), 404
    data = request.get_json(silent=True) or {}
    cid = _parse_uuid_param(str(data.get("company_id") or ""))
    if not cid:
        return _jsonify({"error": "company_id required"}), 400
    try:
        return _jsonify(proc_lookup_svc.add_directory_company(pid, cid, current_user())), 201
    except rfi_svc.ApiError as exc:
        return _proc_lookup_err(exc)


@bp.get("/projects/<project_id>/rfi-lookups/tax_codes")
def list_project_tax_codes(project_id: str):
    pid = _parse_uuid_param(project_id)
    if not pid:
        return _jsonify({"error": "invalid project id"}), 400
    if not _project_exists(pid):
        return _jsonify({"error": "project not found"}), 404
    try:
        return _jsonify(proc_lookup_svc.list_tax_codes(pid, current_user()))
    except rfi_svc.ApiError as exc:
        return _proc_lookup_err(exc)


@bp.get("/projects/<project_id>/procurement/defaults")
def get_project_procurement_defaults(project_id: str):
    pid = _parse_uuid_param(project_id)
    if not pid:
        return _jsonify({"error": "invalid project id"}), 400
    project = db.session.get(Project, pid)
    if project is None or project.deleted_at is not None:
        return _jsonify({"error": "project not found"}), 404
    return _jsonify(
        {
            "item": {
                "ship_to_address": proc_lookup_svc.format_project_address(project),
                "issue_date": date.today().isoformat(),
            },
            "entity": "procurement_defaults",
        }
    )


@bp.get("/projects/<project_id>/commitments")
def list_project_commitments(project_id: str):
    pid = _parse_uuid_param(project_id)
    if not pid:
        return _jsonify({"error": "invalid project id"}), 400
    if not _project_exists(pid):
        return _jsonify({"error": "project not found"}), 404
    try:
        return _jsonify(commitment_svc.list_commitments(pid, current_user()))
    except rfi_svc.ApiError as exc:
        return _commitment_err(exc)


@bp.get("/projects/<project_id>/commitments/<commitment_id>")
def get_project_commitment(project_id: str, commitment_id: str):
    pid = _parse_uuid_param(project_id)
    cid = _parse_uuid_param(commitment_id)
    if not pid or not cid:
        return _jsonify({"error": "invalid id"}), 400
    if not _project_exists(pid):
        return _jsonify({"error": "project not found"}), 404
    try:
        return _jsonify(commitment_svc.get_commitment_detail(pid, cid, current_user()))
    except rfi_svc.ApiError as exc:
        return _commitment_err(exc)


@bp.post("/projects/<project_id>/commitments")
def create_project_commitment(project_id: str):
    pid = _parse_uuid_param(project_id)
    if not pid:
        return _jsonify({"error": "invalid project id"}), 400
    if not _project_exists(pid):
        return _jsonify({"error": "project not found"}), 404
    data = request.get_json(silent=True) or {}
    try:
        body = commitment_svc.create_commitment(pid, data, current_user())
        return _jsonify(body), 201
    except rfi_svc.ApiError as exc:
        return _commitment_err(exc)


@bp.patch("/projects/<project_id>/commitments/<commitment_id>")
def patch_project_commitment(project_id: str, commitment_id: str):
    pid = _parse_uuid_param(project_id)
    cid = _parse_uuid_param(commitment_id)
    if not pid or not cid:
        return _jsonify({"error": "invalid id"}), 400
    if not _project_exists(pid):
        return _jsonify({"error": "project not found"}), 404
    data = request.get_json(silent=True) or {}
    try:
        return _jsonify(commitment_svc.patch_commitment(pid, cid, data, current_user()))
    except rfi_svc.ApiError as exc:
        return _commitment_err(exc)


@bp.delete("/projects/<project_id>/commitments/<commitment_id>")
def delete_project_commitment(project_id: str, commitment_id: str):
    pid = _parse_uuid_param(project_id)
    cid = _parse_uuid_param(commitment_id)
    if not pid or not cid:
        return _jsonify({"error": "invalid id"}), 400
    if not _project_exists(pid):
        return _jsonify({"error": "project not found"}), 404
    try:
        commitment_svc.delete_commitment(pid, cid, current_user())
        return "", 204
    except rfi_svc.ApiError as exc:
        return _commitment_err(exc)


@bp.get("/projects/<project_id>/commitments/<commitment_id>/line-items")
def list_commitment_line_items(project_id: str, commitment_id: str):
    pid = _parse_uuid_param(project_id)
    cid = _parse_uuid_param(commitment_id)
    if not pid or not cid:
        return _jsonify({"error": "invalid id"}), 400
    if not _project_exists(pid):
        return _jsonify({"error": "project not found"}), 404
    try:
        return _jsonify(commitment_svc.list_line_items(pid, cid, current_user()))
    except rfi_svc.ApiError as exc:
        return _commitment_err(exc)


@bp.post("/projects/<project_id>/commitments/<commitment_id>/line-items")
def create_commitment_line_item(project_id: str, commitment_id: str):
    pid = _parse_uuid_param(project_id)
    cid = _parse_uuid_param(commitment_id)
    if not pid or not cid:
        return _jsonify({"error": "invalid id"}), 400
    if not _project_exists(pid):
        return _jsonify({"error": "project not found"}), 404
    data = request.get_json(silent=True) or {}
    try:
        item = commitment_svc.create_line_item(pid, cid, data, current_user())
        return _jsonify({"item": item}), 201
    except rfi_svc.ApiError as exc:
        return _commitment_err(exc)


@bp.patch("/projects/<project_id>/commitments/<commitment_id>/line-items/<line_id>")
def patch_commitment_line_item(project_id: str, commitment_id: str, line_id: str):
    pid = _parse_uuid_param(project_id)
    cid = _parse_uuid_param(commitment_id)
    lid = _parse_uuid_param(line_id)
    if not pid or not cid or not lid:
        return _jsonify({"error": "invalid id"}), 400
    if not _project_exists(pid):
        return _jsonify({"error": "project not found"}), 404
    data = request.get_json(silent=True) or {}
    try:
        return _jsonify({"item": commitment_svc.patch_line_item(pid, cid, lid, data, current_user())})
    except rfi_svc.ApiError as exc:
        return _commitment_err(exc)


@bp.delete("/projects/<project_id>/commitments/<commitment_id>/line-items/<line_id>")
def delete_commitment_line_item(project_id: str, commitment_id: str, line_id: str):
    pid = _parse_uuid_param(project_id)
    cid = _parse_uuid_param(commitment_id)
    lid = _parse_uuid_param(line_id)
    if not pid or not cid or not lid:
        return _jsonify({"error": "invalid id"}), 400
    if not _project_exists(pid):
        return _jsonify({"error": "project not found"}), 404
    try:
        commitment_svc.delete_line_item(pid, cid, lid, current_user())
        return "", 204
    except rfi_svc.ApiError as exc:
        return _commitment_err(exc)


@bp.get("/projects/<project_id>/commitments/<commitment_id>/bill-allocations")
def list_commitment_bill_allocations(project_id: str, commitment_id: str):
    pid = _parse_uuid_param(project_id)
    cid = _parse_uuid_param(commitment_id)
    if not pid or not cid:
        return _jsonify({"error": "invalid id"}), 400
    if not _project_exists(pid):
        return _jsonify({"error": "project not found"}), 404
    try:
        return _jsonify(commitment_svc.list_bill_allocations(pid, cid, current_user()))
    except rfi_svc.ApiError as exc:
        return _commitment_err(exc)


@bp.post("/projects/<project_id>/commitments/<commitment_id>/bill-allocations")
def create_commitment_bill_allocation(project_id: str, commitment_id: str):
    pid = _parse_uuid_param(project_id)
    cid = _parse_uuid_param(commitment_id)
    if not pid or not cid:
        return _jsonify({"error": "invalid id"}), 400
    if not _project_exists(pid):
        return _jsonify({"error": "project not found"}), 404
    data = request.get_json(silent=True) or {}
    try:
        item = commitment_svc.create_bill_allocation(pid, cid, data, current_user())
        return _jsonify({"item": item}), 201
    except rfi_svc.ApiError as exc:
        return _commitment_err(exc)


@bp.delete("/projects/<project_id>/commitments/<commitment_id>/bill-allocations/<bill_id>")
def delete_commitment_bill_allocation(project_id: str, commitment_id: str, bill_id: str):
    pid = _parse_uuid_param(project_id)
    cid = _parse_uuid_param(commitment_id)
    bid = _parse_uuid_param(bill_id)
    if not pid or not cid or not bid:
        return _jsonify({"error": "invalid id"}), 400
    if not _project_exists(pid):
        return _jsonify({"error": "project not found"}), 404
    try:
        commitment_svc.delete_bill_allocation(pid, cid, bid, current_user())
        return "", 204
    except rfi_svc.ApiError as exc:
        return _commitment_err(exc)


def _material_order_err(exc: rfi_svc.ApiError):
    return _jsonify({"error": exc.message}), exc.status


@bp.get("/projects/<project_id>/material-orders")
def list_project_material_orders(project_id: str):
    pid = _parse_uuid_param(project_id)
    if not pid:
        return _jsonify({"error": "invalid project id"}), 400
    if not _project_exists(pid):
        return _jsonify({"error": "project not found"}), 404
    try:
        return _jsonify(material_order_svc.list_material_orders(pid, current_user()))
    except rfi_svc.ApiError as exc:
        return _material_order_err(exc)


@bp.post("/projects/<project_id>/material-orders")
def create_project_material_order(project_id: str):
    pid = _parse_uuid_param(project_id)
    if not pid:
        return _jsonify({"error": "invalid project id"}), 400
    if not _project_exists(pid):
        return _jsonify({"error": "project not found"}), 404
    data = request.get_json(silent=True) or {}
    try:
        body = material_order_svc.create_material_order(pid, data, current_user())
        return _jsonify(body), 201
    except rfi_svc.ApiError as exc:
        return _material_order_err(exc)


@bp.patch("/projects/<project_id>/material-orders/<order_id>")
def patch_project_material_order(project_id: str, order_id: str):
    pid = _parse_uuid_param(project_id)
    oid = _parse_uuid_param(order_id)
    if not pid or not oid:
        return _jsonify({"error": "invalid id"}), 400
    if not _project_exists(pid):
        return _jsonify({"error": "project not found"}), 404
    data = request.get_json(silent=True) or {}
    try:
        return _jsonify(material_order_svc.patch_material_order(pid, oid, data, current_user()))
    except rfi_svc.ApiError as exc:
        return _material_order_err(exc)


@bp.delete("/projects/<project_id>/material-orders/<order_id>")
def delete_project_material_order(project_id: str, order_id: str):
    pid = _parse_uuid_param(project_id)
    oid = _parse_uuid_param(order_id)
    if not pid or not oid:
        return _jsonify({"error": "invalid id"}), 400
    if not _project_exists(pid):
        return _jsonify({"error": "project not found"}), 404
    try:
        material_order_svc.delete_material_order(pid, oid, current_user())
        return "", 204
    except rfi_svc.ApiError as exc:
        return _material_order_err(exc)


@bp.get("/manufacturer-product-data")
def list_manufacturer_product_data():
    q = (request.args.get("q") or "").strip() or None
    mfr = (request.args.get("manufacturer") or "").strip() or None
    return _jsonify(submittal_svc.lookup_product_catalog(q, mfr))


def _document_render_err(exc: rfi_svc.ApiError):
    return _jsonify({"error": exc.message}), exc.status


@bp.get("/projects/<project_id>/commitments/<commitment_id>/render/purchase-order")
def render_commitment_purchase_order_html(project_id: str, commitment_id: str):
    pid = _parse_uuid_param(project_id)
    cid = _parse_uuid_param(commitment_id)
    if not pid or not cid:
        return _jsonify({"error": "invalid id"}), 400
    if not _project_exists(pid):
        return _jsonify({"error": "project not found"}), 404
    try:
        html = document_render_svc.render_purchase_order_html(pid, cid, current_user())
        return Response(html, mimetype="text/html; charset=utf-8")
    except rfi_svc.ApiError as exc:
        return _document_render_err(exc)


@bp.get("/projects/<project_id>/render/client-proposal")
def render_project_client_proposal_html(project_id: str):
    pid = _parse_uuid_param(project_id)
    if not pid:
        return _jsonify({"error": "invalid project id"}), 400
    if not _project_exists(pid):
        return _jsonify({"error": "project not found"}), 404
    scope_raw = (request.args.get("scope_commitment_id") or "").strip()
    scope_cid = _parse_uuid_param(scope_raw) if scope_raw else None
    try:
        html = document_render_svc.render_client_proposal_html(
            pid, current_user(), scope_commitment_id=scope_cid
        )
        return Response(html, mimetype="text/html; charset=utf-8")
    except rfi_svc.ApiError as exc:
        return _document_render_err(exc)


@bp.get("/reports/catalog")
def get_reports_catalog():
    return _jsonify(reports_catalog_svc.reports_catalog_public())


@bp.get("/lead-estimates/<identifier>/render/estimate-summary")
def render_lead_estimate_summary_html(identifier: str):
    row = _resolve_lead(identifier)
    if row is None:
        return _jsonify({"error": "lead estimate not found"}), 404
    try:
        limit = int(request.args.get("line_limit", 500))
    except ValueError:
        return _jsonify({"error": "invalid line_limit"}), 400
    limit = max(0, min(limit, 5000))
    try:
        html = document_render_svc.render_estimate_summary_html(
            row, current_user(), line_limit=limit
        )
        return Response(html, mimetype="text/html; charset=utf-8")
    except rfi_svc.ApiError as exc:
        return _document_render_err(exc)


@bp.get("/lead-estimates/<identifier>/render/quote-report")
def render_lead_quote_report_html(identifier: str):
    row = _resolve_lead(identifier)
    if row is None:
        return _jsonify({"error": "lead estimate not found"}), 404
    try:
        limit = int(request.args.get("line_limit", 500))
    except ValueError:
        return _jsonify({"error": "invalid line_limit"}), 400
    limit = max(0, min(limit, 5000))
    columns = request.args.get("columns")
    try:
        html = document_render_svc.render_quote_report_html(
            row, current_user(), columns_raw=columns, line_limit=limit
        )
        return Response(html, mimetype="text/html; charset=utf-8")
    except rfi_svc.ApiError as exc:
        return _document_render_err(exc)


@bp.get("/lead-estimates/<identifier>/render/door-schedule-html")
def render_lead_door_schedule_report_html(identifier: str):
    row = _resolve_lead(identifier)
    if row is None:
        return _jsonify({"error": "lead estimate not found"}), 404
    try:
        html = document_render_svc.render_door_schedule_report_html(row, current_user())
        return Response(html, mimetype="text/html; charset=utf-8")
    except rfi_svc.ApiError as exc:
        return _document_render_err(exc)


def _pay_app_err(exc: rfi_svc.ApiError):
    return _jsonify({"error": exc.message}), exc.status


def _prime_sov_err(exc: rfi_svc.ApiError):
    return _jsonify({"error": exc.message}), exc.status


@bp.get("/projects/<project_id>/prime-contract/sov")
def get_project_prime_contract_sov(project_id: str):
    pid = _parse_uuid_param(project_id)
    if not pid:
        return _jsonify({"error": "invalid project id"}), 400
    if not _project_exists(pid):
        return _jsonify({"error": "project not found"}), 404
    try:
        return _jsonify(prime_sov_svc.get_prime_contract_sov(pid, current_user()))
    except rfi_svc.ApiError as exc:
        return _prime_sov_err(exc)


@bp.put("/projects/<project_id>/prime-contract/sov")
def put_project_prime_contract_sov(project_id: str):
    pid = _parse_uuid_param(project_id)
    if not pid:
        return _jsonify({"error": "invalid project id"}), 400
    if not _project_exists(pid):
        return _jsonify({"error": "project not found"}), 404
    data = request.get_json(silent=True) or {}
    try:
        return _jsonify(prime_sov_svc.put_prime_contract_sov(pid, current_user(), data))
    except rfi_svc.ApiError as exc:
        return _prime_sov_err(exc)


@bp.get("/powerbi/embed-config")
def get_powerbi_embed_config():
    """Return Power BI embed settings for ``reports.html`` (requires POWERBI_* env when embedding)."""
    try:
        return _jsonify(power_bi_svc.get_embed_config(current_user()))
    except rfi_svc.ApiError as exc:
        return _jsonify({"error": exc.message, "entity": "powerbi_embed"}), exc.status


@bp.get("/projects/<project_id>/pay-applications")
def list_project_pay_applications(project_id: str):
    pid = _parse_uuid_param(project_id)
    if not pid:
        return _jsonify({"error": "invalid project id"}), 400
    if not _project_exists(pid):
        return _jsonify({"error": "project not found"}), 404
    try:
        return _jsonify(pay_app_svc.list_pay_applications(pid, current_user()))
    except rfi_svc.ApiError as exc:
        return _pay_app_err(exc)


@bp.post("/projects/<project_id>/pay-applications")
def create_project_pay_application(project_id: str):
    pid = _parse_uuid_param(project_id)
    if not pid:
        return _jsonify({"error": "invalid project id"}), 400
    if not _project_exists(pid):
        return _jsonify({"error": "project not found"}), 404
    data = request.get_json(silent=True) or {}
    try:
        body = pay_app_svc.create_pay_application(pid, current_user(), data)
        return _jsonify(body), 201
    except rfi_svc.ApiError as exc:
        return _pay_app_err(exc)


@bp.get("/projects/<project_id>/pay-applications/<pay_application_id>")
def get_project_pay_application(project_id: str, pay_application_id: str):
    pid = _parse_uuid_param(project_id)
    aid = _parse_uuid_param(pay_application_id)
    if not pid or not aid:
        return _jsonify({"error": "invalid id"}), 400
    if not _project_exists(pid):
        return _jsonify({"error": "project not found"}), 404
    try:
        return _jsonify(pay_app_svc.get_pay_application_detail(pid, aid, current_user()))
    except rfi_svc.ApiError as exc:
        return _pay_app_err(exc)


@bp.patch("/projects/<project_id>/pay-applications/<pay_application_id>")
def patch_project_pay_application(project_id: str, pay_application_id: str):
    pid = _parse_uuid_param(project_id)
    aid = _parse_uuid_param(pay_application_id)
    if not pid or not aid:
        return _jsonify({"error": "invalid id"}), 400
    if not _project_exists(pid):
        return _jsonify({"error": "project not found"}), 404
    data = request.get_json(silent=True) or {}
    try:
        return _jsonify(pay_app_svc.patch_pay_application(pid, aid, current_user(), data))
    except rfi_svc.ApiError as exc:
        return _pay_app_err(exc)


@bp.delete("/projects/<project_id>/pay-applications/<pay_application_id>")
def delete_project_pay_application(project_id: str, pay_application_id: str):
    pid = _parse_uuid_param(project_id)
    aid = _parse_uuid_param(pay_application_id)
    if not pid or not aid:
        return _jsonify({"error": "invalid id"}), 400
    if not _project_exists(pid):
        return _jsonify({"error": "project not found"}), 404
    try:
        pay_app_svc.delete_pay_application(pid, aid, current_user())
        return "", 204
    except rfi_svc.ApiError as exc:
        return _pay_app_err(exc)


def _material_price_public(m: MaterialPrice) -> dict[str, Any]:
    return {
        "id": str(m.id),
        "manufacturer": m.manufacturer,
        "item": m.item,
        "category": m.category,
        "csi_spec_section": m.csi_spec_section,
        "description": m.description,
        "mounting_type": m.mounting_type,
        "cost": _num_or_none(m.cost),
        "labor_per": _num_or_none(m.labor_per),
        "unit_of_measure": m.unit_of_measure,
        "currency": m.currency,
    }


def _material_prices_query(q: str, manufacturer: str, csi_spec_section: str | None = None):
    from ..csi_spec import normalize_csi_spec_section

    stmt = select(MaterialPrice)
    if manufacturer:
        stmt = stmt.where(MaterialPrice.manufacturer.ilike(f"%{manufacturer}%"))
    if csi_spec_section:
        norm = normalize_csi_spec_section(csi_spec_section)
        if norm:
            stmt = stmt.where(MaterialPrice.csi_spec_section == norm)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            or_(
                MaterialPrice.item.ilike(like),
                MaterialPrice.manufacturer.ilike(like),
                MaterialPrice.description.ilike(like),
                MaterialPrice.category.ilike(like),
            )
        )
    return stmt.order_by(MaterialPrice.manufacturer.asc(), MaterialPrice.item.asc())


def _wage_rate_public(w: WageRate) -> dict[str, Any]:
    return {
        "id": str(w.id),
        "state": w.state,
        "sub_area": w.sub_area,
        "year": w.year,
        "trade": w.trade,
        "basic_hourly_rate": _num_or_none(w.basic_hourly_rate),
        "health_welfare": _num_or_none(w.health_welfare),
        "pension": _num_or_none(w.pension),
        "vacation_holiday": _num_or_none(w.vacation_holiday),
        "other_payments": _num_or_none(w.other_payments),
        "training": _num_or_none(w.training),
        "notes": w.notes,
        "is_assumed": w.is_assumed,
    }


def _wage_total_loaded(w: WageRate) -> float:
    total = Decimal("0")
    for col in (
        w.basic_hourly_rate,
        w.health_welfare,
        w.pension,
        w.vacation_holiday,
        w.other_payments,
        w.training,
    ):
        if col is not None:
            total += col
    return float(total.quantize(Decimal("0.0001")))


@bp.get("/lead-estimates/<identifier>")
def get_lead_estimate(identifier: str):
    """Single lead estimate by UUID primary key or BuildingConnected ``external_id``."""
    row = _resolve_lead(identifier)
    if row is None:
        return _jsonify({"error": "lead estimate not found"}), 404
    return _jsonify({"item": _lead_estimate_detail(row), "entity": "lead_estimate"})


@bp.patch("/lead-estimates/<identifier>")
def patch_lead_estimate(identifier: str):
    """Update CRM fields (``crm_stage``, ``win_probability``, ``due_at``)."""
    row = _resolve_lead(identifier)
    if row is None:
        return _jsonify({"error": "lead estimate not found"}), 404
    data = request.get_json(silent=True)
    if not isinstance(data, Mapping):
        return _jsonify({"error": "expected JSON object body"}), 400
    if "crm_stage" in data and data["crm_stage"] is not None:
        s = str(data["crm_stage"]).strip()[:80]
        if s:
            row.crm_stage = s
    if "win_probability" in data:
        wp = data["win_probability"]
        if wp is None:
            row.win_probability = None
        else:
            row.win_probability = _decimal_from_json(wp, Decimal("0")).quantize(Decimal("0.0001"))
    if "due_at" in data:
        row.due_at = rfi_svc._parse_dt(data.get("due_at"))
    db.session.commit()
    return _jsonify({"item": _lead_estimate_detail(row), "entity": "lead_estimate"})


@bp.post("/lead-estimates/<identifier>/approve-estimate")
def approve_lead_estimate_for_takeoff(identifier: str):
    """Record formal approval, lock takeoff & door-schedule edits. Requires takeoff writes enabled."""
    if not _takeoff_writes_enabled():
        return _jsonify({"error": "takeoff writes disabled (set TAKEOFF_API_WRITES_ENABLED=1)", "error_code": "TAKEOFF_WRITES_DISABLED"}), 403
    row = _resolve_lead(identifier)
    if row is None:
        return _jsonify({"error": "lead estimate not found"}), 404
    if row.estimate_approved_at is not None:
        return _jsonify({"error": "estimate already approved"}), 400
    if _lead_estimate_is_locked(row):
        return _jsonify({"error": "estimate is locked; unlock before approving"}), 400
    cu = current_user()
    now = datetime.now(timezone.utc)
    row.estimate_approved_at = now
    row.estimate_approved_by_user_id = cu.user.id if cu.user else None
    row.estimate_locked_at = now
    _append_lead_estimate_audit(
        cu,
        row.id,
        "estimate_approved",
        changes={"estimate_approved_at": _iso(now), "estimate_locked_at": _iso(now)},
    )
    db.session.commit()
    return _jsonify({"item": _lead_estimate_detail(row), "entity": "lead_estimate"})


@bp.post("/lead-estimates/<identifier>/lock-estimate")
def lock_lead_estimate_for_takeoff(identifier: str):
    """Lock takeoff without recording approval (e.g. freeze draft for bid day)."""
    if not _takeoff_writes_enabled():
        return _jsonify({"error": "takeoff writes disabled (set TAKEOFF_API_WRITES_ENABLED=1)", "error_code": "TAKEOFF_WRITES_DISABLED"}), 403
    row = _resolve_lead(identifier)
    if row is None:
        return _jsonify({"error": "lead estimate not found"}), 404
    if _lead_estimate_is_locked(row):
        return _jsonify({"error": "estimate already locked"}), 400
    cu = current_user()
    lock_at = datetime.now(timezone.utc)
    row.estimate_locked_at = lock_at
    _append_lead_estimate_audit(
        cu,
        row.id,
        "estimate_locked",
        changes={"estimate_locked_at": _iso(lock_at)},
    )
    db.session.commit()
    return _jsonify({"item": _lead_estimate_detail(row), "entity": "lead_estimate"})


@bp.post("/lead-estimates/<identifier>/unlock-estimate")
def unlock_lead_estimate_for_takeoff(identifier: str):
    """Clear takeoff lock. Admin / superuser only (or dev-unrestricted)."""
    row = _resolve_lead(identifier)
    if row is None:
        return _jsonify({"error": "lead estimate not found"}), 404
    cu = current_user()
    if not _can_unlock_lead_estimate(cu):
        return _jsonify({"error": "admin or superuser role required to unlock estimates", "error_code": "UNLOCK_FORBIDDEN"}), 403
    if not _lead_estimate_is_locked(row):
        return _jsonify({"error": "estimate is not locked"}), 400
    prev_iso = _iso(row.estimate_locked_at)
    row.estimate_locked_at = None
    _append_lead_estimate_audit(
        cu,
        row.id,
        "estimate_unlocked",
        changes={"previous_locked_at": prev_iso},
    )
    db.session.commit()
    return _jsonify({"item": _lead_estimate_detail(row), "entity": "lead_estimate"})


@bp.get("/lead-estimates/<identifier>/audit-trail")
def get_lead_estimate_audit_trail(identifier: str):
    """Last audit rows for estimate lock/approve (admin / superuser)."""
    cu = current_user()
    if not _can_unlock_lead_estimate(cu):
        return _jsonify({"error": "admin or superuser role required", "error_code": "UNLOCK_FORBIDDEN"}), 403
    row = _resolve_lead(identifier)
    if row is None:
        return _jsonify({"error": "lead estimate not found"}), 404
    rows = db.session.scalars(
        select(AuditLog)
        .where(AuditLog.entity_type == "lead_estimate", AuditLog.entity_id == row.id)
        .order_by(AuditLog.created_at.desc())
        .limit(100)
    ).all()
    items = [
        {
            "id": str(a.id),
            "action": a.action,
            "message": a.message,
            "changes": a.changes,
            "user_id": str(a.user_id) if a.user_id else None,
            "created_at": _iso(a.created_at),
        }
        for a in rows
    ]
    return _jsonify({"items": items, "entity": "lead_estimate_audit"})


@bp.post("/lead-estimates/<identifier>/award")
def award_lead_estimate(identifier: str):
    """Create or attach a ``Project``, mark CRM stage Awarded, propagate ``project_id`` to takeoff lines."""
    row = _resolve_lead(identifier)
    if row is None:
        return _jsonify({"error": "lead estimate not found"}), 404
    if _lead_estimate_is_locked(row):
        return (
            _jsonify({"error": "estimate is locked; unlock before awarding / linking project", "error_code": "ESTIMATE_LOCKED"}),
            403,
        )
    data = request.get_json(silent=True)
    if not isinstance(data, Mapping):
        data = {}
    pid = _parse_uuid_param(str(data.get("project_id") or "").strip())
    if pid:
        if not _project_exists(pid):
            return _jsonify({"error": "project not found"}), 404
        row.project_id = pid
    elif row.project_id and not data.get("create_new_project"):
        pass
    else:
        name_raw = data.get("project_name") or row.name or row.number or "Awarded project"
        name = str(name_raw).strip()[:255] or "Awarded project"
        proj = Project(name=name, status="active", project_type="commercial")
        db.session.add(proj)
        db.session.flush()
        row.project_id = proj.id
    row.crm_stage = "Awarded"
    for line in row.takeoff_lines:
        line.project_id = row.project_id
    for opening in row.door_openings:
        opening.project_id = row.project_id
    db.session.commit()
    return _jsonify({"item": _lead_estimate_detail(row), "entity": "lead_estimate"})


@bp.post("/lead-estimates/<identifier>/ai-feasibility")
def lead_ai_feasibility(identifier: str):
    """Placeholder for bid feasibility AI (Plan 12)."""
    row = _resolve_lead(identifier)
    if row is None:
        return _jsonify({"error": "lead estimate not found"}), 404
    return (
        _jsonify(
            {
                "status": "accepted",
                "mode": "bid_feasibility_review",
                "lead_estimate_id": str(row.id),
                "message": "Stub — wire to /api/v1/ai/* when available.",
            }
        ),
        202,
    )


@bp.get("/search")
def global_search():
    """Lightweight global search for projects and lead estimates (Plan 1 command palette)."""
    q = (request.args.get("q") or "").strip()
    if len(q) < 2:
        return _jsonify({"items": [], "entity": "search", "hint": "pass q= with at least 2 characters"})
    from ..permissions.project_scope import project_access_clause

    like = f"%{q}%"
    items: list[dict[str, Any]] = []
    cu = current_user()
    for p in db.session.scalars(
        select(Project)
        .where(
            Project.deleted_at.is_(None),
            Project.name.ilike(like),
            project_access_clause(cu),
        )
        .order_by(Project.name.asc())
        .limit(15)
    ).all():
        items.append(
            {
                "type": "project",
                "label": p.name,
                "id": str(p.id),
                "href": f"construction/project-detail.html?project_id={p.id}",
            }
        )
    for le in db.session.scalars(
        select(LeadEstimate)
        .where(
            or_(
                LeadEstimate.name.ilike(like),
                LeadEstimate.number.ilike(like),
                LeadEstimate.external_id.ilike(like),
            )
        )
        .order_by(LeadEstimate.bc_updated_at.desc().nullslast())
        .limit(15)
    ).all():
        ext = (le.external_id or "").strip() or str(le.id)
        label = le.name or le.number or ext
        items.append(
            {
                "type": "lead",
                "label": str(label),
                "id": str(le.id),
                "href": f"construction/lead-detail.html?id={ext}",
            }
        )
    return _jsonify({"items": items, "entity": "search"})


@bp.get("/lead-estimates/<identifier>/takeoff-lines")
def list_takeoff_lines(identifier: str):
    lead = _resolve_lead(identifier)
    if lead is None:
        return _jsonify({"error": "lead estimate not found"}), 404
    lines = db.session.scalars(
        select(TakeoffLineItem)
        .where(TakeoffLineItem.lead_estimate_id == lead.id)
        .order_by(TakeoffLineItem.sort_order.asc(), TakeoffLineItem.created_at.asc())
        .options(joinedload(TakeoffLineItem.material_price))
    ).all()
    return _jsonify(
        {
            "items": [_takeoff_line_public(x) for x in lines],
            "entity": "takeoff_line_items",
            "lead_estimate_id": str(lead.id),
        }
    )


@bp.post("/lead-estimates/<identifier>/takeoff-lines")
def create_takeoff_line(identifier: str):
    if not _takeoff_writes_enabled():
        return _jsonify({"error": "takeoff writes disabled (set TAKEOFF_API_WRITES_ENABLED=1)", "error_code": "TAKEOFF_WRITES_DISABLED"}), 403
    lead = _resolve_lead(identifier)
    if lead is None:
        return _jsonify({"error": "lead estimate not found"}), 404
    blocked = _require_lead_unlocked_for_takeoff(lead)
    if blocked:
        return blocked
    data = request.get_json(silent=True)
    if not isinstance(data, Mapping):
        data = {}
    try:
        t = TakeoffLineItem(
            lead_estimate_id=lead.id,
            project_id=lead.project_id,
            sort_order=int(data["sort_order"]) if data.get("sort_order") is not None else _next_sort_order(lead.id),
        )
        _apply_takeoff_payload(t, data, partial=False)
    except (ValueError, TypeError) as exc:
        return _jsonify({"error": str(exc)}), 400
    db.session.add(t)
    db.session.commit()
    return _jsonify({"item": _takeoff_line_public(t), "entity": "takeoff_line_item"}), 201


@bp.patch("/takeoff-lines/<line_id>")
def patch_takeoff_line(line_id: str):
    if not _takeoff_writes_enabled():
        return _jsonify({"error": "takeoff writes disabled (set TAKEOFF_API_WRITES_ENABLED=1)", "error_code": "TAKEOFF_WRITES_DISABLED"}), 403
    lid = _parse_uuid_param(line_id)
    if not lid:
        return _jsonify({"error": "invalid line id"}), 400
    t = db.session.get(TakeoffLineItem, lid)
    if t is None:
        return _jsonify({"error": "takeoff line not found"}), 404
    lead = _takeoff_line_parent_lead(t)
    blocked = _require_lead_unlocked_for_takeoff(lead)
    if blocked:
        return blocked
    data = request.get_json(silent=True)
    if not isinstance(data, Mapping):
        return _jsonify({"error": "expected JSON object body"}), 400
    try:
        _apply_takeoff_payload(t, data, partial=True)
    except (ValueError, TypeError) as exc:
        return _jsonify({"error": str(exc)}), 400
    db.session.commit()
    return _jsonify({"item": _takeoff_line_public(t), "entity": "takeoff_line_item"})


@bp.delete("/takeoff-lines/<line_id>")
def delete_takeoff_line(line_id: str):
    if not _takeoff_writes_enabled():
        return _jsonify({"error": "takeoff writes disabled (set TAKEOFF_API_WRITES_ENABLED=1)", "error_code": "TAKEOFF_WRITES_DISABLED"}), 403
    lid = _parse_uuid_param(line_id)
    if not lid:
        return _jsonify({"error": "invalid line id"}), 400
    t = db.session.get(TakeoffLineItem, lid)
    if t is None:
        return _jsonify({"error": "takeoff line not found"}), 404
    lead = _takeoff_line_parent_lead(t)
    blocked = _require_lead_unlocked_for_takeoff(lead)
    if blocked:
        return blocked
    db.session.delete(t)
    db.session.commit()
    return _jsonify({"ok": True})


def _door_opening_detail(opening: DoorOpening) -> dict[str, Any]:
    base = door_schedule_svc.door_opening_public(opening, include_lines=False)
    lines = db.session.scalars(
        select(TakeoffLineItem)
        .where(TakeoffLineItem.door_opening_id == opening.id)
        .order_by(TakeoffLineItem.sort_order.asc(), TakeoffLineItem.created_at.asc())
        .options(joinedload(TakeoffLineItem.material_price))
    ).all()
    base["takeoff_lines"] = [_takeoff_line_public(x) for x in lines]
    base["takeoff_line_count"] = len(lines)
    return base


@bp.get("/door-hardware-sets")
def list_door_hardware_sets():
    rows = db.session.scalars(
        select(DoorHardwareSet)
        .options(joinedload(DoorHardwareSet.items))
        .order_by(DoorHardwareSet.code.asc())
    ).unique().all()
    return _jsonify(
        {
            "items": [door_schedule_svc.hardware_set_public(hs) for hs in rows],
            "entity": "door_hardware_sets",
        }
    )


@bp.get("/door-hardware-sets/<code>")
def get_door_hardware_set(code: str):
    hs = door_schedule_svc.get_hardware_set_by_code(code)
    if hs is None:
        return _jsonify({"error": "hardware set not found"}), 404
    return _jsonify({"item": door_schedule_svc.hardware_set_public(hs), "entity": "door_hardware_sets"})


@bp.post("/door-hardware-sets")
def create_door_hardware_set():
    if not _takeoff_writes_enabled():
        return _jsonify({"error": "takeoff writes disabled (set TAKEOFF_API_WRITES_ENABLED=1)", "error_code": "TAKEOFF_WRITES_DISABLED"}), 403
    data = request.get_json(silent=True)
    if not isinstance(data, Mapping):
        return _jsonify({"error": "expected JSON object body"}), 400
    try:
        hs = door_schedule_svc.create_hardware_set(
            str(data.get("code") or ""),
            str(data.get("name") or ""),
            data.get("description"),
        )
    except ValueError as exc:
        return _jsonify({"error": str(exc)}), 400
    db.session.commit()
    return _jsonify({"item": door_schedule_svc.hardware_set_public(hs), "entity": "door_hardware_sets"}), 201


@bp.patch("/door-hardware-sets/<code>")
def patch_door_hardware_set(code: str):
    if not _takeoff_writes_enabled():
        return _jsonify({"error": "takeoff writes disabled (set TAKEOFF_API_WRITES_ENABLED=1)", "error_code": "TAKEOFF_WRITES_DISABLED"}), 403
    hs = door_schedule_svc.get_hardware_set_by_code(code)
    if hs is None:
        return _jsonify({"error": "hardware set not found"}), 404
    data = request.get_json(silent=True)
    if not isinstance(data, Mapping):
        return _jsonify({"error": "expected JSON object body"}), 400
    door_schedule_svc.update_hardware_set(
        hs,
        name=data.get("name") if "name" in data else None,
        description=data.get("description") if "description" in data else None,
    )
    db.session.commit()
    return _jsonify({"item": door_schedule_svc.hardware_set_public(hs), "entity": "door_hardware_sets"})


@bp.post("/door-hardware-sets/<code>/items")
def create_door_hardware_set_item(code: str):
    if not _takeoff_writes_enabled():
        return _jsonify({"error": "takeoff writes disabled (set TAKEOFF_API_WRITES_ENABLED=1)", "error_code": "TAKEOFF_WRITES_DISABLED"}), 403
    hs = door_schedule_svc.get_hardware_set_by_code(code)
    if hs is None:
        return _jsonify({"error": "hardware set not found"}), 404
    data = request.get_json(silent=True)
    if not isinstance(data, Mapping):
        return _jsonify({"error": "expected JSON object body"}), 400
    try:
        item = door_schedule_svc.add_hardware_set_item(hs, data)
    except ValueError as exc:
        return _jsonify({"error": str(exc)}), 400
    db.session.commit()
    hs = door_schedule_svc.get_hardware_set_by_code(code)
    return _jsonify(
        {"item": door_schedule_svc.hardware_set_public(hs), "entity": "door_hardware_sets"}
    ), 201


@bp.patch("/door-hardware-set-items/<item_id>")
def patch_door_hardware_set_item(item_id: str):
    if not _takeoff_writes_enabled():
        return _jsonify({"error": "takeoff writes disabled (set TAKEOFF_API_WRITES_ENABLED=1)", "error_code": "TAKEOFF_WRITES_DISABLED"}), 403
    iid = _parse_uuid_param(item_id)
    if not iid:
        return _jsonify({"error": "invalid item id"}), 400
    item = db.session.get(DoorHardwareSetItem, iid)
    if item is None:
        return _jsonify({"error": "hardware set item not found"}), 404
    data = request.get_json(silent=True)
    if not isinstance(data, Mapping):
        return _jsonify({"error": "expected JSON object body"}), 400
    try:
        door_schedule_svc.update_hardware_set_item(item, data)
    except ValueError as exc:
        return _jsonify({"error": str(exc)}), 400
    db.session.commit()
    hs = door_schedule_svc.get_hardware_set_by_id(item.hardware_set_id)
    return _jsonify(
        {"item": door_schedule_svc.hardware_set_public(hs), "entity": "door_hardware_sets"}
    )


@bp.delete("/door-hardware-set-items/<item_id>")
def delete_door_hardware_set_item(item_id: str):
    if not _takeoff_writes_enabled():
        return _jsonify({"error": "takeoff writes disabled (set TAKEOFF_API_WRITES_ENABLED=1)", "error_code": "TAKEOFF_WRITES_DISABLED"}), 403
    iid = _parse_uuid_param(item_id)
    if not iid:
        return _jsonify({"error": "invalid item id"}), 400
    item = db.session.get(DoorHardwareSetItem, iid)
    if item is None:
        return _jsonify({"error": "hardware set item not found"}), 404
    hs_id = item.hardware_set_id
    door_schedule_svc.delete_hardware_set_item(item)
    db.session.commit()
    hs = door_schedule_svc.get_hardware_set_by_id(hs_id)
    return _jsonify(
        {"item": door_schedule_svc.hardware_set_public(hs), "entity": "door_hardware_sets"}
    )


@bp.get("/lead-estimates/<identifier>/door-schedule")
def get_door_schedule(identifier: str):
    row = _resolve_lead(identifier)
    if row is None:
        return _jsonify({"error": "lead estimate not found"}), 404
    openings = db.session.scalars(
        select(DoorOpening)
        .where(DoorOpening.lead_estimate_id == row.id)
        .order_by(DoorOpening.sort_order.asc(), DoorOpening.created_at.asc())
    ).all()
    items = [_door_opening_detail(op) for op in openings]
    grand = sum(float(x.get("extended_total") or 0) for x in items)
    return _jsonify(
        {
            "lead_estimate_id": str(row.id),
            "external_id": row.external_id,
            "project_id": str(row.project_id) if row.project_id else None,
            "openings": items,
            "opening_count": len(items),
            "grand_total": grand,
            "entity": "door_schedule",
        }
    )


@bp.post("/lead-estimates/<identifier>/door-schedule/import")
def import_door_schedule(identifier: str):
    if not _takeoff_writes_enabled():
        return _jsonify({"error": "takeoff writes disabled (set TAKEOFF_API_WRITES_ENABLED=1)", "error_code": "TAKEOFF_WRITES_DISABLED"}), 403
    row = _resolve_lead(identifier)
    if row is None:
        return _jsonify({"error": "lead estimate not found"}), 404
    blocked = _require_lead_unlocked_for_takeoff(row)
    if blocked:
        return blocked
    data = request.get_json(silent=True)
    if not isinstance(data, Mapping):
        return _jsonify({"error": "expected JSON object body"}), 400
    rows_in = data.get("rows")
    if not isinstance(rows_in, list):
        return _jsonify({"error": "rows must be an array"}), 400
    column_map = data.get("column_map")
    if not isinstance(column_map, Mapping):
        return _jsonify({"error": "column_map must be an object"}), 400
    mode = str(data.get("mode") or "merge").strip().lower()
    try:
        summary = door_schedule_svc.import_door_schedule(
            row, rows_in, column_map, mode=mode
        )
    except ValueError as exc:
        return _jsonify({"error": str(exc)}), 400
    db.session.commit()
    openings = db.session.scalars(
        select(DoorOpening)
        .where(DoorOpening.lead_estimate_id == row.id)
        .order_by(DoorOpening.sort_order.asc(), DoorOpening.created_at.asc())
    ).all()
    summary["openings"] = [_door_opening_detail(op) for op in openings]
    return _jsonify(summary), 201


@bp.post("/lead-estimates/<identifier>/door-openings")
def create_door_opening(identifier: str):
    if not _takeoff_writes_enabled():
        return _jsonify({"error": "takeoff writes disabled (set TAKEOFF_API_WRITES_ENABLED=1)", "error_code": "TAKEOFF_WRITES_DISABLED"}), 403
    row = _resolve_lead(identifier)
    if row is None:
        return _jsonify({"error": "lead estimate not found"}), 404
    blocked = _require_lead_unlocked_for_takeoff(row)
    if blocked:
        return blocked
    data = request.get_json(silent=True) or {}
    if not isinstance(data, Mapping):
        return _jsonify({"error": "expected JSON object body"}), 400
    mark = str(data.get("mark") or "").strip()[:60]
    if not mark:
        n = db.session.scalar(
            select(func.count()).select_from(DoorOpening).where(
                DoorOpening.lead_estimate_id == row.id
            )
        ) or 0
        mark = f"NEW-{int(n) + 1}"
    sort_ix = db.session.scalar(
        select(func.coalesce(func.max(DoorOpening.sort_order), -1)).where(
            DoorOpening.lead_estimate_id == row.id
        )
    )
    op = DoorOpening(
        lead_estimate_id=row.id,
        project_id=row.project_id,
        mark=mark,
        room=door_schedule_svc._str_field(data.get("room"), 255),
        sort_order=int(sort_ix if sort_ix is not None else -1) + 1,
    )
    db.session.add(op)
    db.session.flush()
    door_schedule_svc.rebuild_opening_lines(op, preserve_priced=False)
    db.session.commit()
    return _jsonify({"item": _door_opening_detail(op), "entity": "door_opening"}), 201


@bp.patch("/door-openings/<opening_id>")
def patch_door_opening(opening_id: str):
    if not _takeoff_writes_enabled():
        return _jsonify({"error": "takeoff writes disabled (set TAKEOFF_API_WRITES_ENABLED=1)", "error_code": "TAKEOFF_WRITES_DISABLED"}), 403
    oid = _parse_uuid_param(opening_id)
    if not oid:
        return _jsonify({"error": "invalid opening id"}), 400
    op = db.session.get(DoorOpening, oid)
    if op is None:
        return _jsonify({"error": "door opening not found"}), 404
    if op.lead_estimate_id:
        lead = db.session.get(LeadEstimate, op.lead_estimate_id)
        blocked = _require_lead_unlocked_for_takeoff(lead)
        if blocked:
            return blocked
    data = request.get_json(silent=True)
    if not isinstance(data, Mapping):
        return _jsonify({"error": "expected JSON object body"}), 400
    for field, max_len in (        ("mark", 60),
        ("room", 255),
        ("width", 40),
        ("height", 40),
        ("door_type", 120),
        ("frame_type", 120),
        ("hardware_set_code", 60),
        ("fire_rating", 60),
        ("handing", 60),
    ):
        if field in data:
            val = door_schedule_svc._str_field(data.get(field), max_len) or ""
            if field == "hardware_set_code":
                val = door_schedule_svc.normalize_hardware_set_code(val) or ""
            setattr(op, field, val)
    if "remarks" in data:
        v = data.get("remarks")
        op.remarks = str(v) if v is not None else None
    if data.get("rebuild_lines") in (True, "true", 1, "1"):
        door_schedule_svc.rebuild_opening_lines(op, preserve_priced=True)
    db.session.commit()
    return _jsonify({"item": _door_opening_detail(op), "entity": "door_opening"})


@bp.post("/door-openings/<opening_id>/expand-hardware")
def expand_door_opening_hardware(opening_id: str):
    if not _takeoff_writes_enabled():
        return _jsonify({"error": "takeoff writes disabled (set TAKEOFF_API_WRITES_ENABLED=1)", "error_code": "TAKEOFF_WRITES_DISABLED"}), 403
    oid = _parse_uuid_param(opening_id)
    if not oid:
        return _jsonify({"error": "invalid opening id"}), 400
    op = db.session.get(DoorOpening, oid)
    if op is None:
        return _jsonify({"error": "door opening not found"}), 404
    if op.lead_estimate_id:
        lead = db.session.get(LeadEstimate, op.lead_estimate_id)
        blocked = _require_lead_unlocked_for_takeoff(lead)
        if blocked:
            return blocked
    created = door_schedule_svc.expand_hardware_for_opening(op)
    db.session.commit()
    return _jsonify(
        {
            "item": _door_opening_detail(op),
            "hardware_lines_added": len(created),
            "entity": "door_opening",
        }
    )


def _dashboard_period_bounds(period: str) -> tuple[date, date]:
    today = date.today()
    if period == "day":
        return today, today
    if period == "week":
        return today - timedelta(days=6), today
    if period == "year":
        return date(today.year, 1, 1), today
    return date(today.year, today.month, 1), today


@bp.get("/dashboard/hours-by-project")
def dashboard_hours_by_project():
    """Sum ``hrms_timesheet_entries.hours_worked`` by project for dashboard chart."""
    period = (request.args.get("period") or "month").strip().lower()
    if period not in ("day", "week", "month", "year"):
        return _jsonify({"error": "invalid period; use day, week, month, or year"}), 400
    start, end = _dashboard_period_bounds(period)
    try:
        limit = int(request.args.get("limit") or 15)
    except ValueError:
        limit = 15
    limit = max(1, min(limit, 30))

    from ..permissions.project_scope import project_access_clause

    cu = current_user()
    stmt = (
        select(
            Project.id,
            Project.name,
            func.coalesce(func.sum(HrmsTimesheetEntry.hours_worked), 0).label("hours"),
        )
        .select_from(HrmsTimesheetEntry)
        .join(Project, Project.id == HrmsTimesheetEntry.project_id)
        .where(
            HrmsTimesheetEntry.work_date >= start,
            HrmsTimesheetEntry.work_date <= end,
            project_access_clause(cu),
        )
        .group_by(Project.id, Project.name)
        .having(func.sum(HrmsTimesheetEntry.hours_worked) > 0)
        .order_by(func.sum(HrmsTimesheetEntry.hours_worked).desc())
        .limit(limit)
    )
    rows = db.session.execute(stmt).all()
    projects: list[dict[str, Any]] = []
    total_hours = Decimal("0")
    for pid, pname, hours in rows:
        h = Decimal(str(hours or 0))
        total_hours += h
        projects.append(
            {
                "project_id": str(pid),
                "project_name": (pname or "Unnamed project").strip(),
                "hours": float(h.quantize(Decimal("0.01"))),
            }
        )
    n = len(projects)
    avg = float((total_hours / n).quantize(Decimal("0.01"))) if n else 0.0
    return _jsonify(
        {
            "entity": "dashboard_hours_by_project",
            "period": period,
            "period_start": start.isoformat(),
            "period_end": end.isoformat(),
            "projects": projects,
            "summary": {
                "total_hours": float(total_hours.quantize(Decimal("0.01"))),
                "project_count": n,
                "avg_hours_per_project": avg,
                "top_project_name": projects[0]["project_name"] if projects else None,
            },
        }
    )


@bp.get("/material-prices")
def list_material_prices():
    """Company material catalog (``material_pricing``) for pickers; optional ``q`` / ``manufacturer``."""
    try:
        limit = int(request.args.get("limit") or 250)
    except ValueError:
        limit = 250
    try:
        offset = int(request.args.get("offset") or 0)
    except ValueError:
        offset = 0
    limit = max(1, min(limit, 500))
    offset = max(0, offset)
    q = (request.args.get("q") or "").strip()
    manufacturer = (request.args.get("manufacturer") or "").strip()
    csi = (request.args.get("csi_spec_section") or "").strip() or None
    base = _material_prices_query(q, manufacturer, csi)
    total = db.session.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = db.session.scalars(base.offset(offset).limit(limit)).all()
    return _jsonify(
        {
            "items": [_material_price_public(m) for m in rows],
            "entity": "material_prices",
            "total": int(total),
            "limit": limit,
            "offset": offset,
        }
    )


@bp.get("/material-prices/manufacturers")
def list_material_price_manufacturers():
    """Distinct manufacturers for catalog filters."""
    q = (request.args.get("q") or "").strip()
    stmt = select(MaterialPrice.manufacturer).distinct().order_by(MaterialPrice.manufacturer.asc())
    if q:
        stmt = stmt.where(MaterialPrice.manufacturer.ilike(f"%{q}%"))
    try:
        limit = int(request.args.get("limit") or 200)
    except ValueError:
        limit = 200
    limit = max(1, min(limit, 500))
    names = [r for r in db.session.scalars(stmt.limit(limit)).all() if r]
    return _jsonify({"items": names, "entity": "material_manufacturers"})


@bp.get("/cost-suggestions/material")
def cost_suggestions_material():
    from ..csi_spec import normalize_csi_spec_section

    q = (request.args.get("q") or "").strip()
    if len(q) < 2:
        return _jsonify({"items": [], "entity": "material_prices", "hint": "pass q= with at least 2 characters"})
    like = f"%{q}%"
    stmt = select(MaterialPrice).where(
        or_(
            MaterialPrice.item.ilike(like),
            MaterialPrice.manufacturer.ilike(like),
            MaterialPrice.description.ilike(like),
        )
    )
    csi = (request.args.get("csi_spec_section") or "").strip() or None
    if csi:
        norm = normalize_csi_spec_section(csi)
        if norm:
            stmt = stmt.where(MaterialPrice.csi_spec_section == norm)
    stmt = stmt.limit(25)
    rows = db.session.scalars(stmt).all()
    return _jsonify({"items": [_material_price_public(m) for m in rows], "entity": "material_prices"})


@bp.get("/cost-suggestions/wage")
def cost_suggestions_wage():
    state = (request.args.get("state") or "").strip()
    trade = (request.args.get("trade") or "").strip()
    if not state or not trade:
        return _jsonify({"error": "state and trade query params are required"}), 400
    try:
        year = int(request.args.get("year") or datetime.now().year)
    except ValueError:
        return _jsonify({"error": "invalid year"}), 400
    sub_area = (request.args.get("sub_area") or "").strip()
    stmt = select(WageRate).where(WageRate.state == state, WageRate.year == year, WageRate.trade == trade)
    if sub_area != "":
        stmt = stmt.where(WageRate.sub_area == sub_area)
    w = db.session.scalars(stmt.limit(1)).first()
    if w is None:
        stmt2 = (
            select(WageRate)
            .where(WageRate.state == state, WageRate.year == year, WageRate.trade.ilike(f"%{trade}%"))
            .limit(5)
        )
        alt = db.session.scalars(stmt2).all()
        return _jsonify(
            {
                "item": None,
                "total_loaded_hourly": None,
                "entity": "wage_rate",
                "near_matches": [_wage_rate_public(x) for x in alt],
            }
        )
    return _jsonify(
        {
            "item": _wage_rate_public(w),
            "total_loaded_hourly": _wage_total_loaded(w),
            "entity": "wage_rate",
        }
    )


from . import _hr_dashboard  # noqa: E402
from . import _integration_bc  # noqa: E402
from . import _integration_textura  # noqa: E402
from .extra_plan_routes import register_extra_routes  # noqa: E402

register_extra_routes(bp)
_hr_dashboard.register_hr_routes(bp)
from . import _hr_hire_wizard  # noqa: E402

_hr_hire_wizard.register_hr_hire_wizard_routes(bp)
from . import _hr_job_offer  # noqa: E402

_hr_job_offer.register_hr_job_offer_routes(bp)
from . import _hr_applications  # noqa: E402

_hr_applications.register_hr_application_routes(bp)
from . import _hr_signed_forms  # noqa: E402

_hr_signed_forms.register_hr_signed_form_routes(bp)
from . import _playbooks as _playbooks_mod  # noqa: E402

_playbooks_mod.register_playbook_routes(bp)
_integration_bc.register_buildingconnected_routes(bp)
_integration_textura.register_textura_routes(bp)
from . import _auth_mobile  # noqa: E402

_auth_mobile.register_mobile_auth_routes(bp)
