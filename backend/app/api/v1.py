"""Versioned read+write API for projects, lead_estimates, and Procore-parity RFIs."""
from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Mapping

from flask import Blueprint, Response, current_app, jsonify, request, send_file
from sqlalchemy import and_, func, literal, or_, select
from werkzeug.utils import secure_filename

from ..extensions import db
from ..models import (
    Company,
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
from . import _commitment_service as commitment_svc
from . import _admin_users_service as admin_users_svc
from . import _document_render_service as document_render_svc
from . import _pay_application_service as pay_app_svc
from . import _power_bi_service as power_bi_svc
from . import _prime_contract_sov_service as prime_sov_svc
from . import _project_schedule_service as project_schedule_svc
from . import _rfi_service as rfi_svc
from . import _submittal_service as submittal_svc
from ._perms import can_edit_rfi, current_user, users_for_picker

bp = Blueprint("api_v1", __name__, url_prefix="/api/v1")


def _jsonify(obj: Any):
    return jsonify(obj)


@bp.get("/auth/status")
def auth_status():
    """Return whether the browser session is signed in (``session['user_id']``)."""
    from ..integrations.ms_entra_oidc import entra_fully_configured

    cu = current_user()
    ms_on = entra_fully_configured(current_app.config)
    if cu.user is None:
        return _jsonify({"authenticated": False, "user": None, "microsoft_sso_enabled": ms_on})
    u = cu.user
    return _jsonify(
        {
            "authenticated": True,
            "microsoft_sso_enabled": ms_on,
            "user": {
                "id": str(u.id),
                "email": u.email,
                "first_name": u.first_name,
                "last_name": u.last_name,
            },
        }
    )


@bp.get("/me")
def get_me():
    """Signed-in user's profile (same payload shape as ``GET /admin/users/<id>``)."""
    try:
        item = admin_users_svc.get_me(current_user())
    except admin_users_svc.ApiError as exc:
        return _admin_directory_err(exc)
    return _jsonify({"item": item, "entity": "session_user"})


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


def _iso(dt: datetime | date | None) -> str | None:
    if dt is None:
        return None
    if isinstance(dt, datetime):
        return dt.isoformat()
    return dt.isoformat()


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


def _location_bits(loc: Any) -> tuple[str | None, str | None]:
    if not isinstance(loc, Mapping):
        return None, None
    c = loc.get("city")
    s = loc.get("state")
    return (str(c).strip() if c else None, str(s).strip() if s else None)


def _lead_estimate_public(row: LeadEstimate) -> dict[str, Any]:
    city, state = _location_bits(row.location)
    return {
        "id": str(row.id),
        "external_id": row.external_id,
        "project_id": str(row.project_id) if row.project_id else None,
        "name": row.name,
        "number": row.number,
        "trade_name": row.trade_name,
        "submission_state": row.submission_state,
        "source": row.source,
        "workflow_bucket": row.workflow_bucket,
        "due_at": _iso(row.due_at),
        "bc_updated_at": _iso(row.bc_updated_at),
        "company_name": _client_company_name(row.client),
        "city": city,
        "state": state,
        "crm_stage": row.crm_stage,
        "win_probability": _num_or_none(row.win_probability),
        "primary_estimate_id": str(row.primary_estimate_id) if row.primary_estimate_id else None,
        "primary_rfp_id": str(row.primary_rfp_id) if row.primary_rfp_id else None,
    }


def _primary_lead_detail_id_by_project_ids(project_ids: list[uuid.UUID]) -> dict[uuid.UUID, str]:
    """One BC lead id per project (newest ``bc_updated_at``) for deep-links to ``lead-detail``."""
    if not project_ids:
        return {}
    q = (
        select(LeadEstimate)
        .where(LeadEstimate.project_id.in_(project_ids))
        .order_by(
            LeadEstimate.project_id.asc(),
            LeadEstimate.bc_updated_at.desc().nullslast(),
            LeadEstimate.id.asc(),
        )
    )
    rows = list(db.session.scalars(q).all())
    out: dict[uuid.UUID, str] = {}
    for le in rows:
        pid = le.project_id
        if pid is None or pid in out:
            continue
        ext = (le.external_id or "").strip()
        out[pid] = ext if ext else str(le.id)
    return out


def _project_public(p: Project, *, primary_lead_detail_id: str | None = None) -> dict[str, Any]:
    city = p.city.strip() if p.city else None
    state = p.state.strip() if p.state else None
    d: dict[str, Any] = {
        "id": str(p.id),
        "number": p.number,
        "name": p.name,
        "city": city,
        "state": state,
        "status": p.status,
        "project_type": p.project_type,
        "updated_at": _iso(p.updated_at),
    }
    if primary_lead_detail_id:
        d["primary_lead_detail_id"] = primary_lead_detail_id
    return d


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
    row = db.session.scalar(
        select(Project.id).where(Project.id == project_id, Project.deleted_at.is_(None))
    )
    return row is not None


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
        "file_url": d.file_url,
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
    lines = db.session.scalars(
        select(TakeoffLineItem)
        .where(TakeoffLineItem.lead_estimate_id == row.id)
        .order_by(TakeoffLineItem.sort_order.asc(), TakeoffLineItem.created_at.asc())
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
    t.extended_total = _compute_extended(t.quantity, t.unit_cost)


def _rfi_public(r: Rfi) -> dict[str, Any]:
    """Compatibility wrapper used by other code paths (drawings tab uses it).

    The full Procore-parity payload comes from ``rfi_svc.rfi_public``."""
    return rfi_svc.rfi_public(r)


def _submission_state_norm_sql():
    """Lowercase, trim, strip ``_`` / ``-`` so BC camelCase (e.g. ``willBid``) matches ``will_bid``."""
    co = func.trim(func.coalesce(LeadEstimate.submission_state, literal("")))
    return func.replace(func.replace(func.lower(co), "_", ""), "-", "")


def _submission_state_norm_param(submission_state: str) -> str:
    return (submission_state or "").strip().lower().replace("_", "").replace("-", "")


def _lead_estimates_ui_filter(submission_state: str) -> Any:
    """Filter by submission pipeline.

    - ``undecided`` (alone): null/blank/undecided, not archived (Leads).
    - Otherwise: one or more comma-separated states (e.g. ``will_submit,submitted``); each is
      matched case-insensitively with ``_`` / ``-`` ignored (BC exports ``WILL_SUBMIT``, etc.).
      If ``undecided`` appears in a comma-separated list, blank/null submission_state still matches
      (same as the single-token ``undecided`` case).
    """
    st_in = (submission_state or "").strip()
    if not st_in:
        raise ValueError("submission_state cannot be empty")
    not_archived = or_(LeadEstimate.is_archived.is_(False), LeadEstimate.is_archived.is_(None))
    norm_sql = _submission_state_norm_sql()

    parts = [p.strip() for p in st_in.split(",") if p.strip()]
    norms = [_submission_state_norm_param(p) for p in parts]

    if len(norms) == 1 and norms[0] == "undecided":
        empty_or_ws = func.trim(func.coalesce(LeadEstimate.submission_state, literal(""))) == literal("")
        state_ok = or_(empty_or_ws, norm_sql == literal("undecided"))
        return and_(state_ok, not_archived)

    # Multi-state OR: treat ``undecided`` like the single-token branch (blank/null counts as undecided).
    empty_or_ws = func.trim(func.coalesce(LeadEstimate.submission_state, literal(""))) == literal("")
    clauses: list[Any] = []
    for n in norms:
        if not n:
            continue
        if n == "undecided":
            clauses.append(or_(empty_or_ws, norm_sql == literal("undecided")))
        else:
            clauses.append(norm_sql == literal(n))
    if not clauses:
        raise ValueError("submission_state has no valid tokens")
    state_ok = or_(*clauses) if len(clauses) > 1 else clauses[0]
    return and_(state_ok, not_archived)


def _lead_estimates_health_count_filter() -> Any:
    """Same row set as the Leads page default (undecided / no decision yet, not archived)."""
    return _lead_estimates_ui_filter("undecided")


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
        filt = _lead_estimates_ui_filter(submission_state)
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
    try:
        limit = max(1, min(int(request.args.get("limit", 500)), 2000))
        offset = max(0, int(request.args.get("offset", 0)))
    except ValueError:
        return _jsonify({"error": "invalid limit or offset"}), 400

    filt = Project.deleted_at.is_(None)
    total = db.session.scalar(select(func.count()).select_from(Project).where(filt)) or 0
    q = select(Project).where(filt).order_by(Project.number.asc().nullslast(), Project.name.asc()).offset(offset).limit(limit)
    rows = db.session.scalars(q).all()
    pids = [p.id for p in rows]
    lead_nav = _primary_lead_detail_id_by_project_ids(pids)
    return _jsonify(
        {
            "items": [_project_public(p, primary_lead_detail_id=lead_nav.get(p.id)) for p in rows],
            "total": total,
            "limit": limit,
            "offset": offset,
            "entity": "projects",
        }
    )


@bp.get("/projects/<project_id>")
def get_project(project_id: str):
    """Single project by UUID (Job info tab)."""
    pid = _parse_uuid_param(project_id)
    if not pid:
        return _jsonify({"error": "invalid project id"}), 400
    p = db.session.get(Project, pid)
    if p is None or p.deleted_at is not None:
        return _jsonify({"error": "project not found"}), 404
    return _jsonify({"item": _project_detail_public(p), "entity": "project"})


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


def _drawing_upload_dir() -> Path:
    raw = current_app.config.get("DRAWING_UPLOAD_FOLDER")
    if raw:
        return Path(str(raw)).expanduser().resolve()
    return Path(current_app.instance_path).resolve() / "drawing_uploads"


def _spec_section_upload_dir() -> Path:
    raw = current_app.config.get("SPEC_SECTION_UPLOAD_FOLDER")
    if raw:
        return Path(str(raw)).expanduser().resolve()
    return Path(current_app.instance_path).resolve() / "spec_section_uploads"


def _rfi_attachment_upload_dir() -> Path:
    raw = current_app.config.get("RFI_ATTACHMENT_UPLOAD_FOLDER")
    if raw:
        return Path(str(raw)).expanduser().resolve()
    return Path(current_app.instance_path).resolve() / "rfi_attachment_uploads"


@bp.get("/drawings/<drawing_id>/file")
def get_drawing_pdf_file(drawing_id: str):
    """Stream an uploaded drawing PDF (same-origin for PDF.js)."""
    did = _parse_uuid_param(drawing_id)
    if not did:
        return _jsonify({"error": "invalid drawing id"}), 400
    row = db.session.get(Drawing, did)
    if row is None:
        return _jsonify({"error": "drawing not found"}), 404
    path = _drawing_upload_dir() / f"{did}.pdf"
    if not path.is_file():
        return _jsonify({"error": "file not found on server"}), 404
    dl = (row.original_filename or "drawing.pdf").replace('"', "")
    if not dl.lower().endswith(".pdf"):
        dl = dl + ".pdf"
    return send_file(path, mimetype="application/pdf", as_attachment=False, download_name=dl[:200])


@bp.post("/projects/<project_id>/drawings")
def upload_project_drawing(project_id: str):
    """Multipart upload: field ``file`` (PDF) plus optional form fields for metadata."""
    pid = _parse_uuid_param(project_id)
    if not pid:
        return _jsonify({"error": "invalid project id"}), 400
    if not _project_exists(pid):
        return _jsonify({"error": "project not found"}), 404
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

    sheet_number = (request.form.get("sheet_number") or "").strip()[:50] or None
    sheet_title = (request.form.get("sheet_title") or "").strip()[:500] or None
    discipline = (request.form.get("discipline") or "").strip()[:50] or None
    drawing_set = (request.form.get("drawing_set") or "").strip()[:120] or None
    revision = (request.form.get("revision") or "").strip()[:50] or "0"

    title = sheet_title or raw_name.rsplit(".", 1)[0][:500]

    d = Drawing(
        project_id=pid,
        title=title,
        sheet_number=sheet_number,
        sheet_title=sheet_title or title,
        discipline=discipline,
        drawing_set=drawing_set,
        revision=revision,
        mime_type="application/pdf",
        original_filename=raw_name[:500],
    )
    db.session.add(d)
    db.session.flush()

    dest_dir = _drawing_upload_dir()
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / f"{d.id}.pdf"
    try:
        f.save(str(dest_path))
    except OSError as exc:
        db.session.rollback()
        return _jsonify({"error": f"could not save file: {exc}"}), 500

    try:
        sz = dest_path.stat().st_size
    except OSError:
        sz = None
    if sz == 0:
        try:
            dest_path.unlink(missing_ok=True)
        except OSError:
            pass
        db.session.rollback()
        return _jsonify({"error": "empty upload"}), 400
    if sz is not None and sz > max_bytes:
        try:
            dest_path.unlink(missing_ok=True)
        except OSError:
            pass
        db.session.rollback()
        return _jsonify({"error": "file too large (max 50MB)"}), 400

    d.file_url = f"/api/v1/drawings/{d.id}/file"
    d.file_size_bytes = int(sz) if sz is not None else None
    db.session.commit()
    return _jsonify({"item": _drawing_public(d), "entity": "drawing"}), 201


@bp.get("/spec-sections/<spec_section_id>/file")
def get_spec_section_pdf_file(spec_section_id: str):
    """Stream an uploaded spec-section PDF (same-origin for embedded viewers)."""
    sid = _parse_uuid_param(spec_section_id)
    if not sid:
        return _jsonify({"error": "invalid spec section id"}), 400
    row = db.session.get(SpecSection, sid)
    if row is None:
        return _jsonify({"error": "spec section not found"}), 404
    path = _spec_section_upload_dir() / f"{sid}.pdf"
    if not path.is_file():
        return _jsonify({"error": "file not found on server"}), 404
    base = secure_filename(f"{row.code} {row.title}".strip()) or "spec"
    dl = (base + ".pdf")[:200].replace('"', "")
    return send_file(path, mimetype="application/pdf", as_attachment=False, download_name=dl)


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

    dest_dir = _rfi_attachment_upload_dir()
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / f"{doc.id}{ext}"
    try:
        f.save(str(dest_path))
    except OSError as exc:
        db.session.rollback()
        return _jsonify({"error": f"could not save file: {exc}"}), 500
    try:
        sz = dest_path.stat().st_size
    except OSError:
        sz = None
    if sz == 0:
        try:
            dest_path.unlink(missing_ok=True)
        except OSError:
            pass
        db.session.rollback()
        return _jsonify({"error": "empty upload"}), 400
    if sz is not None and sz > max_bytes:
        try:
            dest_path.unlink(missing_ok=True)
        except OSError:
            pass
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
    path = _rfi_attachment_upload_dir() / f"{did}{ext}"
    if not path.is_file():
        return _jsonify({"error": "file not found on server"}), 404
    dl = (row.original_filename or "attachment").replace('"', "")[:200]
    mt = row.mime_type or "application/octet-stream"
    return send_file(path, mimetype=mt, as_attachment=False, download_name=dl)


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

    dest_dir = _spec_section_upload_dir()
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / f"{row.id}.pdf"
    try:
        f.save(str(dest_path))
    except OSError as exc:
        return _jsonify({"error": f"could not save file: {exc}"}), 500

    try:
        sz = dest_path.stat().st_size
    except OSError:
        sz = None
    if sz == 0:
        try:
            dest_path.unlink(missing_ok=True)
        except OSError:
            pass
        return _jsonify({"error": "empty upload"}), 400
    if sz is not None and sz > max_bytes:
        try:
            dest_path.unlink(missing_ok=True)
        except OSError:
            pass
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
        "description": m.description,
        "cost": _num_or_none(m.cost),
        "labor_per": _num_or_none(m.labor_per),
        "unit_of_measure": m.unit_of_measure,
        "currency": m.currency,
    }


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


@bp.post("/lead-estimates/<identifier>/award")
def award_lead_estimate(identifier: str):
    """Create or attach a ``Project``, mark CRM stage Awarded, propagate ``project_id`` to takeoff lines."""
    row = _resolve_lead(identifier)
    if row is None:
        return _jsonify({"error": "lead estimate not found"}), 404
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
    like = f"%{q}%"
    items: list[dict[str, Any]] = []
    for p in db.session.scalars(
        select(Project)
        .where(Project.deleted_at.is_(None), Project.name.ilike(like))
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
        return _jsonify({"error": "takeoff writes disabled (set TAKEOFF_API_WRITES_ENABLED=1)"}), 403
    lead = _resolve_lead(identifier)
    if lead is None:
        return _jsonify({"error": "lead estimate not found"}), 404
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
        return _jsonify({"error": "takeoff writes disabled (set TAKEOFF_API_WRITES_ENABLED=1)"}), 403
    lid = _parse_uuid_param(line_id)
    if not lid:
        return _jsonify({"error": "invalid line id"}), 400
    t = db.session.get(TakeoffLineItem, lid)
    if t is None:
        return _jsonify({"error": "takeoff line not found"}), 404
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
        return _jsonify({"error": "takeoff writes disabled (set TAKEOFF_API_WRITES_ENABLED=1)"}), 403
    lid = _parse_uuid_param(line_id)
    if not lid:
        return _jsonify({"error": "invalid line id"}), 400
    t = db.session.get(TakeoffLineItem, lid)
    if t is None:
        return _jsonify({"error": "takeoff line not found"}), 404
    db.session.delete(t)
    db.session.commit()
    return _jsonify({"ok": True})


@bp.get("/cost-suggestions/material")
def cost_suggestions_material():
    q = (request.args.get("q") or "").strip()
    if len(q) < 2:
        return _jsonify({"items": [], "entity": "material_prices", "hint": "pass q= with at least 2 characters"})
    like = f"%{q}%"
    stmt = (
        select(MaterialPrice)
        .where(
            or_(
                MaterialPrice.item.ilike(like),
                MaterialPrice.manufacturer.ilike(like),
                MaterialPrice.description.ilike(like),
            )
        )
        .limit(25)
    )
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
from .extra_plan_routes import register_extra_routes  # noqa: E402

register_extra_routes(bp)
_hr_dashboard.register_hr_routes(bp)
from . import _playbooks as _playbooks_mod  # noqa: E402

_playbooks_mod.register_playbook_routes(bp)
_integration_bc.register_buildingconnected_routes(bp)
