"""Tool handler implementations — register all tools on import."""
from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import and_, func, or_, select

from ...api import _lead_estimate_queries as lead_q
from ...api import _project_service as project_svc
from ...api import _rfi_service as rfi_svc
from ...api import _serializers as ser
from ...api._perms import CurrentUser, can_create_rfi, can_edit_rfi, can_view_rfi
from ...extensions import db
from ...models import Company, Contact, LeadEstimate, Project, Rfi
from ...permissions.access import has_module_access
from ...permissions.project_scope import project_access_clause
from . import executor as ex
from .registry import ToolDef, _obj, register

_MAX_LIST = 50


def _clamp_limit(raw: Any, default: int = 25) -> int:
    try:
        n = int(raw) if raw is not None else default
    except (TypeError, ValueError):
        n = default
    return max(1, min(n, _MAX_LIST))


def _has_leads_or_estimate_read(cu: CurrentUser) -> bool:
    return has_module_access(cu, "leads", "read") or has_module_access(cu, "estimate", "read")


def _require_leads_or_estimate_write(cu: CurrentUser) -> None:
    if has_module_access(cu, "leads", "write") or has_module_access(cu, "estimate", "write"):
        return
    raise ex.ToolExecutionError("access denied: leads or estimate write required", status=403)


def _resolve_lead(identifier: str) -> LeadEstimate | None:
    raw = (identifier or "").strip()
    if not raw:
        return None
    try:
        uid = uuid.UUID(raw)
        row = db.session.get(LeadEstimate, uid)
        if row is not None:
            return row
    except ValueError:
        pass
    row = db.session.scalar(select(LeadEstimate).where(LeadEstimate.external_id == raw))
    if row is not None:
        return row
    row = db.session.scalar(
        select(LeadEstimate).where(func.lower(LeadEstimate.external_id) == raw.lower())
    )
    return row


def _lead_is_locked(row: LeadEstimate) -> bool:
    return row.estimate_locked_at is not None


def _project_visible(cu: CurrentUser, project_id: uuid.UUID) -> bool:
    filt = and_(Project.id == project_id, Project.deleted_at.is_(None), project_access_clause(cu))
    return db.session.scalar(select(Project.id).where(filt)) is not None


# --- Read handlers ---


def _list_projects(args: dict[str, Any], cu: CurrentUser) -> dict[str, Any]:
    from ...permissions.access import require_module

    require_module(cu, "projects", "read")
    limit = _clamp_limit(args.get("limit"))
    offset = max(0, int(args.get("offset") or 0))
    filt = and_(Project.deleted_at.is_(None), project_access_clause(cu))
    total = db.session.scalar(select(func.count()).select_from(Project).where(filt)) or 0
    q = (
        select(Project)
        .where(filt)
        .order_by(Project.number.asc().nullslast(), Project.name.asc())
        .offset(offset)
        .limit(limit)
    )
    rows = db.session.scalars(q).all()
    pids = [p.id for p in rows]
    lead_nav = ser.primary_lead_detail_id_by_project_ids(pids)
    return {
        "ok": True,
        "entity": "projects",
        "items": [ser.project_public(p, primary_lead_detail_id=lead_nav.get(p.id)) for p in rows],
        "total": int(total),
        "limit": limit,
        "offset": offset,
    }


def _get_project(args: dict[str, Any], cu: CurrentUser) -> dict[str, Any]:
    from ...permissions.access import require_module

    require_module(cu, "projects", "read")
    pid = ex.parse_uuid(args.get("project_id"), "project_id")
    p = db.session.get(Project, pid)
    if p is None or p.deleted_at is not None or not _project_visible(cu, pid):
        return {"ok": False, "error": "project not found", "status": 404}
    lead_nav = ser.primary_lead_detail_id_by_project_ids([p.id])
    return {
        "ok": True,
        "entity": "project",
        "item": ser.project_public(p, primary_lead_detail_id=lead_nav.get(p.id)),
    }


def _list_rfis(args: dict[str, Any], cu: CurrentUser) -> dict[str, Any]:
    from ...permissions.access import require_module

    require_module(cu, "projects", "read")
    pid = ex.parse_uuid(args.get("project_id"), "project_id")
    if not _project_visible(cu, pid):
        return {"ok": False, "error": "project not found", "status": 404}
    filters = rfi_svc.ListFilters(
        limit=_clamp_limit(args.get("limit")),
        offset=max(0, int(args.get("offset") or 0)),
        q=(str(args.get("q")).strip() if args.get("q") else None),
    )
    data = rfi_svc.list_rfis(pid, filters, cu)
    return {"ok": True, **data}


def _get_rfi(args: dict[str, Any], cu: CurrentUser) -> dict[str, Any]:
    from ...permissions.access import require_module

    require_module(cu, "projects", "read")
    rid = ex.parse_uuid(args.get("rfi_id"), "rfi_id")
    try:
        data = rfi_svc.get_rfi(rid, cu)
    except rfi_svc.ApiError as exc:
        return {"ok": False, "error": exc.message, "status": exc.status}
    return {"ok": True, **data}


def _list_lead_estimates(args: dict[str, Any], cu: CurrentUser) -> dict[str, Any]:
    if not _has_leads_or_estimate_read(cu):
        raise ex.ToolExecutionError("access denied: leads or estimate read required", status=403)
    submission_state = str(args.get("submission_state") or "undecided").strip()
    try:
        filt = lead_q.lead_estimates_ui_filter(submission_state)
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}
    limit = _clamp_limit(args.get("limit"))
    offset = max(0, int(args.get("offset") or 0))
    total = db.session.scalar(select(func.count()).select_from(LeadEstimate).where(filt)) or 0
    rows = db.session.scalars(
        select(LeadEstimate)
        .where(filt)
        .order_by(LeadEstimate.bc_updated_at.desc().nullslast(), LeadEstimate.name.asc())
        .offset(offset)
        .limit(limit)
    ).all()
    return {
        "ok": True,
        "entity": "lead_estimates",
        "items": [ser.lead_estimate_public(r) for r in rows],
        "total": int(total),
        "limit": limit,
        "offset": offset,
    }


def _get_lead_estimate(args: dict[str, Any], cu: CurrentUser) -> dict[str, Any]:
    if not _has_leads_or_estimate_read(cu):
        raise ex.ToolExecutionError("access denied: leads or estimate read required", status=403)
    ident = str(args.get("lead_estimate_id") or args.get("id") or "").strip()
    row = _resolve_lead(ident)
    if row is None:
        return {"ok": False, "error": "lead estimate not found", "status": 404}
    return {"ok": True, "entity": "lead_estimate", "item": ser.lead_estimate_public(row)}


def _list_companies(args: dict[str, Any], cu: CurrentUser) -> dict[str, Any]:
    from ...permissions.access import require_module

    require_module(cu, "crm", "read")
    limit = _clamp_limit(args.get("limit"))
    offset = max(0, int(args.get("offset") or 0))
    q = str(args.get("q") or "").strip().lower()
    filt = Company.deleted_at.is_(None)
    if q:
        filt = and_(filt, func.lower(Company.name).contains(q))
    total = db.session.scalar(select(func.count()).select_from(Company).where(filt)) or 0
    rows = db.session.scalars(
        select(Company).where(filt).order_by(Company.name.asc()).offset(offset).limit(limit)
    ).all()
    return {
        "ok": True,
        "entity": "companies",
        "items": [ser.company_public(c) for c in rows],
        "total": int(total),
        "limit": limit,
        "offset": offset,
    }


def _get_company(args: dict[str, Any], cu: CurrentUser) -> dict[str, Any]:
    from ...permissions.access import require_module

    require_module(cu, "crm", "read")
    cid = ex.parse_uuid(args.get("company_id"), "company_id")
    c = db.session.get(Company, cid)
    if c is None or c.deleted_at is not None:
        return {"ok": False, "error": "company not found", "status": 404}
    return {"ok": True, "entity": "company", "item": ser.company_public(c)}


def _list_contacts(args: dict[str, Any], cu: CurrentUser) -> dict[str, Any]:
    from ...permissions.access import require_module

    require_module(cu, "crm", "read")
    limit = _clamp_limit(args.get("limit"))
    offset = max(0, int(args.get("offset") or 0))
    filt = True
    clauses = []
    if args.get("company_id"):
        cid = ex.parse_uuid(args.get("company_id"), "company_id")
        clauses.append(Contact.company_id == cid)
    q = str(args.get("q") or "").strip().lower()
    if q:
        clauses.append(
            or_(
                func.lower(func.coalesce(Contact.first_name, "")).contains(q),
                func.lower(func.coalesce(Contact.last_name, "")).contains(q),
                func.lower(func.coalesce(Contact.email, "")).contains(q),
            )
        )
    if clauses:
        filt = and_(*clauses)
    total = db.session.scalar(select(func.count()).select_from(Contact).where(filt)) or 0
    rows = db.session.scalars(
        select(Contact).where(filt).order_by(Contact.last_name.asc().nullslast()).offset(offset).limit(limit)
    ).all()
    return {
        "ok": True,
        "entity": "contacts",
        "items": [ser.contact_public(c) for c in rows],
        "total": int(total),
        "limit": limit,
        "offset": offset,
    }


def _get_contact(args: dict[str, Any], cu: CurrentUser) -> dict[str, Any]:
    from ...permissions.access import require_module

    require_module(cu, "crm", "read")
    cid = ex.parse_uuid(args.get("contact_id"), "contact_id")
    c = db.session.get(Contact, cid)
    if c is None:
        return {"ok": False, "error": "contact not found", "status": 404}
    return {"ok": True, "entity": "contact", "item": ser.contact_public(c)}


# --- Write handlers ---

_PROJECT_PATCH_KEYS = frozenset(
    {
        "name",
        "number",
        "description",
        "notes",
        "status",
        "project_type",
        "address_line1",
        "address_line2",
        "city",
        "state",
        "postal_code",
        "country",
        "contract_value",
        "contract_date",
        "start_date",
        "substantial_completion_date",
        "closeout_date",
    }
)

_LEAD_PATCH_KEYS = frozenset({"crm_stage", "win_probability", "due_at"})

_RFI_CREATE_KEYS = frozenset(
    {
        "subject",
        "question",
        "status",
        "number",
        "due_at",
        "cost_impact_choice",
        "schedule_impact_choice",
        "reference_text",
        "assignees",
        "distribution",
    }
)

_RFI_PATCH_KEYS = frozenset(
    {
        "subject",
        "question",
        "due_at",
        "cost_impact_choice",
        "schedule_impact_choice",
        "reference_text",
        "status",
        "assignees",
        "distribution",
    }
)


def _filter_keys(data: dict[str, Any], allowed: frozenset[str]) -> dict[str, Any]:
    extra = set(data.keys()) - allowed
    if extra:
        raise ex.ToolExecutionError(f"unsupported fields: {', '.join(sorted(extra))}")
    return {k: data[k] for k in data if k in allowed}


def _update_project(args: dict[str, Any], cu: CurrentUser) -> dict[str, Any]:
    from ...permissions.access import require_module

    require_module(cu, "projects", "write")
    pid = ex.parse_uuid(args.get("project_id"), "project_id")
    if not _project_visible(cu, pid):
        return {"ok": False, "error": "project not found", "status": 404}
    fields = args.get("fields")
    if not isinstance(fields, dict):
        raise ex.ToolExecutionError("fields object is required")
    payload = _filter_keys(fields, _PROJECT_PATCH_KEYS)
    try:
        result = project_svc.patch_project(pid, payload)
    except project_svc.ApiError as exc:
        return {"ok": False, "error": exc.message, "status": exc.status}
    if result is None:
        return {"ok": False, "error": "project not found", "status": 404}
    db.session.commit()
    p = db.session.get(Project, pid)
    lead_nav = ser.primary_lead_detail_id_by_project_ids([pid])
    return {
        "ok": True,
        "entity": "project",
        "item": ser.project_public(p, primary_lead_detail_id=lead_nav.get(pid)) if p else result,
    }


def _update_lead_estimate(args: dict[str, Any], cu: CurrentUser) -> dict[str, Any]:
    _require_leads_or_estimate_write(cu)
    ident = str(args.get("lead_estimate_id") or "").strip()
    row = _resolve_lead(ident)
    if row is None:
        return {"ok": False, "error": "lead estimate not found", "status": 404}
    if _lead_is_locked(row):
        return {
            "ok": False,
            "error": "estimate is locked; unlock required before editing",
            "status": 403,
        }
    fields = args.get("fields")
    if not isinstance(fields, dict):
        raise ex.ToolExecutionError("fields object is required")
    payload = _filter_keys(fields, _LEAD_PATCH_KEYS)
    if "crm_stage" in payload and payload["crm_stage"] is not None:
        s = str(payload["crm_stage"]).strip()[:80]
        if s:
            row.crm_stage = s
    if "win_probability" in payload:
        wp = payload["win_probability"]
        if wp is None:
            row.win_probability = None
        else:
            row.win_probability = Decimal(str(wp)).quantize(Decimal("0.0001"))
    if "due_at" in payload:
        row.due_at = rfi_svc._parse_dt(payload.get("due_at"))
    db.session.commit()
    return {"ok": True, "entity": "lead_estimate", "item": ser.lead_estimate_public(row)}


def _create_rfi(args: dict[str, Any], cu: CurrentUser) -> dict[str, Any]:
    from ...permissions.access import require_module

    require_module(cu, "projects", "write")
    if not can_create_rfi(cu):
        return {"ok": False, "error": "not authorized to create RFIs", "status": 403}
    pid = ex.parse_uuid(args.get("project_id"), "project_id")
    if not _project_visible(cu, pid):
        return {"ok": False, "error": "project not found", "status": 404}
    payload = _filter_keys({k: v for k, v in args.items() if k != "project_id"}, _RFI_CREATE_KEYS)
    try:
        data = rfi_svc.create_rfi(pid, payload, cu)
    except rfi_svc.ApiError as exc:
        return {"ok": False, "error": exc.message, "status": exc.status}
    return {"ok": True, **data}


def _update_rfi(args: dict[str, Any], cu: CurrentUser) -> dict[str, Any]:
    from ...permissions.access import require_module

    require_module(cu, "projects", "write")
    rid = ex.parse_uuid(args.get("rfi_id"), "rfi_id")
    rfi = db.session.get(Rfi, rid)
    if rfi is None:
        return {"ok": False, "error": "RFI not found", "status": 404}
    if not can_edit_rfi(cu, rfi):
        return {"ok": False, "error": "not authorized to edit this RFI", "status": 403}
    fields = args.get("fields")
    if not isinstance(fields, dict):
        raise ex.ToolExecutionError("fields object is required")
    payload = _filter_keys(fields, _RFI_PATCH_KEYS)
    try:
        data = rfi_svc.patch_rfi(rid, payload, cu)
    except rfi_svc.ApiError as exc:
        return {"ok": False, "error": exc.message, "status": exc.status}
    return {"ok": True, **data}


def _register_all() -> None:
    register(
        ToolDef(
            name="list_projects",
            description="List construction projects the user can access.",
            parameters=_obj(
                {
                    "limit": {"type": "integer", "description": "Max rows (default 25, max 50)."},
                    "offset": {"type": "integer", "description": "Pagination offset."},
                }
            ),
            handler=_list_projects,
            modules=("projects",),
        )
    )
    register(
        ToolDef(
            name="get_project",
            description="Get one project by UUID.",
            parameters=_obj({"project_id": {"type": "string", "description": "Project UUID."}}, required=["project_id"]),
            handler=_get_project,
            modules=("projects",),
        )
    )
    register(
        ToolDef(
            name="list_rfis",
            description="List RFIs for a project.",
            parameters=_obj(
                {
                    "project_id": {"type": "string"},
                    "limit": {"type": "integer"},
                    "offset": {"type": "integer"},
                    "q": {"type": "string", "description": "Search subject/question."},
                },
                required=["project_id"],
            ),
            handler=_list_rfis,
            modules=("projects",),
        )
    )
    register(
        ToolDef(
            name="get_rfi",
            description="Get one RFI by UUID with detail.",
            parameters=_obj({"rfi_id": {"type": "string"}}, required=["rfi_id"]),
            handler=_get_rfi,
            modules=("projects",),
        )
    )
    register(
        ToolDef(
            name="list_lead_estimates",
            description="List lead estimates (bids/leads). Default submission_state=undecided.",
            parameters=_obj(
                {
                    "submission_state": {
                        "type": "string",
                        "description": "e.g. undecided, will_submit, submitted",
                    },
                    "limit": {"type": "integer"},
                    "offset": {"type": "integer"},
                }
            ),
            handler=_list_lead_estimates,
            modules=("leads", "estimate"),
        )
    )
    register(
        ToolDef(
            name="get_lead_estimate",
            description="Get one lead estimate by UUID or external_id.",
            parameters=_obj({"lead_estimate_id": {"type": "string"}}, required=["lead_estimate_id"]),
            handler=_get_lead_estimate,
            modules=("leads", "estimate"),
        )
    )
    register(
        ToolDef(
            name="list_companies",
            description="List CRM companies.",
            parameters=_obj({"limit": {"type": "integer"}, "offset": {"type": "integer"}, "q": {"type": "string"}}),
            handler=_list_companies,
            modules=("crm",),
        )
    )
    register(
        ToolDef(
            name="get_company",
            description="Get one company by UUID.",
            parameters=_obj({"company_id": {"type": "string"}}, required=["company_id"]),
            handler=_get_company,
            modules=("crm",),
        )
    )
    register(
        ToolDef(
            name="list_contacts",
            description="List CRM contacts, optionally filtered by company.",
            parameters=_obj(
                {
                    "company_id": {"type": "string"},
                    "limit": {"type": "integer"},
                    "offset": {"type": "integer"},
                    "q": {"type": "string"},
                }
            ),
            handler=_list_contacts,
            modules=("crm",),
        )
    )
    register(
        ToolDef(
            name="get_contact",
            description="Get one contact by UUID.",
            parameters=_obj({"contact_id": {"type": "string"}}, required=["contact_id"]),
            handler=_get_contact,
            modules=("crm",),
        )
    )
    register(
        ToolDef(
            name="update_project",
            description="Update allowlisted project fields.",
            parameters=_obj(
                {
                    "project_id": {"type": "string"},
                    "fields": {
                        "type": "object",
                        "description": "Allowed: name, number, description, notes, status, project_type, address fields, dates, contract_value.",
                    },
                },
                required=["project_id", "fields"],
            ),
            handler=_update_project,
            modules=("projects",),
        )
    )
    register(
        ToolDef(
            name="update_lead_estimate",
            description="Update CRM fields on a lead estimate (crm_stage, win_probability, due_at).",
            parameters=_obj(
                {
                    "lead_estimate_id": {"type": "string"},
                    "fields": {"type": "object"},
                },
                required=["lead_estimate_id", "fields"],
            ),
            handler=_update_lead_estimate,
            modules=("leads", "estimate"),
        )
    )
    register(
        ToolDef(
            name="create_rfi",
            description="Create an RFI on a project (draft or open per permissions).",
            parameters=_obj(
                {
                    "project_id": {"type": "string"},
                    "subject": {"type": "string"},
                    "question": {"type": "string"},
                    "status": {"type": "string"},
                    "number": {"type": "integer"},
                    "due_at": {"type": "string"},
                },
                required=["project_id"],
            ),
            handler=_create_rfi,
            modules=("projects",),
        )
    )
    register(
        ToolDef(
            name="update_rfi",
            description="Patch allowlisted RFI fields.",
            parameters=_obj(
                {
                    "rfi_id": {"type": "string"},
                    "fields": {"type": "object"},
                },
                required=["rfi_id", "fields"],
            ),
            handler=_update_rfi,
            modules=("projects",),
        )
    )


_register_all()
