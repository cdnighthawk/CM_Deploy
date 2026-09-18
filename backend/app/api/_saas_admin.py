"""SaaS admin APIs: /api/settings (tenant) and /api/admin (platform).

Slice 0 mapping (do not invent a parallel tree):
- Tenant → ``Organization`` (``backend.app.models.organization.Organization``)
- Company Admin → Role ``admin`` / module ``user_admin`` / org_role ``owner``|``admin``
- Platform operator → ``User.is_platform_operator`` (seeded from superusers / PLATFORM_OPERATOR_EMAIL)
- ``quotes@gousis.com`` → ``config.QUOTES_MAILBOX`` and ``TenantSetting`` key ``mail.rfp.from_address``
- Workflow definitions → ``WorkflowDefinition`` / ``WorkflowDefinitionStep``
- Hire settings → ``HireCompanySetting`` plus ``hire.*`` keys here
- Time policy → ``HrmsModuleSetting`` key ``timekeeping_policy`` plus ``time.require_cost_code``
- Audit → ``PlatformAudit`` (cross-tenant). Existing ``AuditLog`` stays tenant-scoped.
- People directory → ``User`` / ``UserRole`` / ``Role`` / ``RoleModulePermission`` (old page ``usis-user-directory.html``)
- v2 consoles: ``/settings/*`` 14-item rail, ``/admin/*`` 10-item rail. No second Tenant table.
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Any

from flask import Blueprint, current_app, g, jsonify, request, session
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from sqlalchemy.orm import selectinload

from ..extensions import db
from ..models import MobileRefreshToken, User, WorkflowDefinition
from ..models.organization import ORG_ROLE_ADMIN, ORG_ROLE_OWNER, Organization, OrganizationMember as OrgMember
from ..models.saas import FeatureFlag, ImpersonationSession, PlatformAudit
from ..tenant_settings import (
    FEATURE_FLAG_CATALOG,
    LOCKED_KEYS,
    LOCKED_MESSAGE,
    MODULE_KEYS,
    PLAN_DEFAULT_MODULES,
    PLAN_KEYS,
    PLATFORM_ONLY_KEYS,
    SETTING_DEFAULTS,
    LockedSettingError,
    feature_flag_on,
    list_tenant_settings,
    module_enabled,
    set_entitlement,
    set_tenant_setting,
    tenant_setting,
    upsert_feature_flag,
    write_platform_audit,
)
from ..tenancy import (
    current_organization_id,
    include_all_orgs,
    provision_organization,
    set_current_organization_id,
)
from ._perms import CurrentUser, can_manage_directory_users, current_user

settings_bp = Blueprint("api_settings", __name__, url_prefix="/api/settings")
admin_bp = Blueprint("api_admin_saas", __name__, url_prefix="/api/admin")

SETTINGS_RAIL = (
    {
        "id": "overview",
        "path": "/settings",
        "title": "Overview",
        "description": "Seats, plan, and recent changes for this company",
        "icon": "home",
        "keys": [],
    },
    {
        "id": "company",
        "path": "/settings/company",
        "title": "Company",
        "description": "Legal name, offices, timezone, logo",
        "icon": "briefcase",
        "keys": [
            "company.legal_name",
            "company.dba",
            "company.cslb",
            "company.timezone",
            "company.logo_document_id",
            "company.offices",
            "company.letterhead_document_id",
            "company.public_hostname",
        ],
    },
    {
        "id": "people",
        "path": "/settings/people",
        "title": "People & access",
        "description": "Company directory, invites, and seats",
        "icon": "users",
        "keys": [
            "security.sso_m365_tenant_id",
            "security.mfa_required_roles",
            "security.session_idle_minutes",
            "security.session_max_minutes",
            "security.password_reset_hours",
        ],
        "aliases": ["users", "security"],
    },
    {
        "id": "roles",
        "path": "/settings/roles",
        "title": "Roles & templates",
        "description": "Permission templates: tool × level",
        "icon": "shield",
        "keys": [],
    },
    {
        "id": "projects",
        "path": "/settings/projects",
        "title": "Projects & defaults",
        "description": "New-project defaults and estimate stage labels",
        "icon": "folder",
        "keys": ["estimate.stage_labels"],
    },
    {
        "id": "money",
        "path": "/settings/money",
        "title": "Money & workflows",
        "description": "PO bands and published workflow steps",
        "icon": "dollar-sign",
        "keys": ["po.band_0", "po.band_pm", "po.band_director", "po.band_president", "po.skip_down", "tm.requires_co"],
        "aliases": ["workflows"],
    },
    {
        "id": "mail",
        "path": "/settings/mail",
        "title": "Mail & senders",
        "description": "From addresses, spam, and never-auto lists",
        "icon": "send",
        "keys": [
            "mail.rfp.from_address",
            "mail.rfp.from_name",
            "mail.rfp.bcc_self",
            "mail.field.from_address",
            "mail.hire.from_address",
            "mail.allow_mailboxes",
            "mail.spam_confidence_move",
            "mail.never_auto_spam_domains",
            "mail.never_auto_spam_subjects",
        ],
        "aliases": ["senders"],
    },
    {
        "id": "correspondence",
        "path": "/settings/correspondence",
        "title": "Correspondence",
        "description": "Allow-listed mailboxes and Teams ingest",
        "icon": "archive",
        "keys": ["correspondence.teams_ingest"],
    },
    {
        "id": "files",
        "path": "/settings/files",
        "title": "Files & public links",
        "description": "Public token TTL and legal footer",
        "icon": "file",
        "keys": [
            "public.rfp_token_ttl_hours",
            "public.hire_token_ttl_hours",
            "public.tm_token_ttl_hours",
            "public.legal_footer",
            "files.spec_split_roles",
        ],
    },
    {
        "id": "time-field",
        "path": "/settings/time-field",
        "title": "Time & field",
        "description": "Cost codes, geofence, sign-off, devices",
        "icon": "clock",
        "keys": [
            "time.require_cost_code",
            "field.geofence_mode",
            "field.signoff_required",
            "punch.auto_push_procore",
        ],
    },
    {
        "id": "hiring",
        "path": "/settings/hiring",
        "title": "Hiring",
        "description": "W-4 and I-9 editions (not the hire register)",
        "icon": "user-plus",
        "keys": ["hire.w4_edition", "hire.i9_edition", "hire.ssn_on_user", "qb.employee_add", "edd.auto_file"],
    },
    {
        "id": "ai",
        "path": "/settings/ai",
        "title": "AI",
        "description": "Review modes, rubber-stamp, scan cap",
        "icon": "cpu",
        "keys": [
            "ai.default_provider",
            "ai.mode.construction_review",
            "ai.mode.estimating_review",
            "ai.mode.spec_package_review",
            "ai.mode.submittal_review",
            "ai.mode.bid_feasibility",
            "ai.mode.email_classify",
            "ai.submittal_rubber_stamp_seconds",
            "ai.email_scan_cap_per_run",
            "ai.dump_correspondence_to_grok",
        ],
    },
    {
        "id": "integrations",
        "path": "/settings/integrations",
        "title": "Integrations",
        "description": "SMTP, B2, QuickBooks, and Local AI status",
        "icon": "link",
        "keys": ["qb.company_file_name"],
    },
    {
        "id": "audit",
        "path": "/settings/audit",
        "title": "Audit",
        "description": "Setting changes for this company",
        "icon": "list",
        "keys": [],
    },
)

ADMIN_RAIL = (
    {
        "id": "overview",
        "path": "/admin",
        "title": "Overview",
        "description": "Platform health, seats, and recent audit",
    },
    {
        "id": "organizations",
        "path": "/admin/organizations",
        "title": "Organizations",
        "description": "Every subscriber company",
        "aliases": ["tenants"],
    },
    {"id": "provision", "path": "/admin/provision", "title": "Provision", "description": "Create an Organization"},
    {
        "id": "plans",
        "path": "/admin/plans",
        "title": "Plans & entitlements",
        "description": "Default module sets for field / office / full",
    },
    {
        "id": "flags",
        "path": "/admin/flags",
        "title": "Feature flags",
        "description": "Platform defaults and per-org overrides",
    },
    {
        "id": "usage",
        "path": "/admin/usage",
        "title": "Usage & health",
        "description": "SMTP, B2, Scout, Celery",
        "aliases": ["health"],
    },
    {"id": "support", "path": "/admin/support", "title": "Support", "description": "Find an org and impersonate"},
    {"id": "operators", "path": "/admin/operators", "title": "Operators", "description": "Platform operator accounts"},
    {"id": "audit", "path": "/admin/audit", "title": "Audit", "description": "Cross-org privileged log"},
    {
        "id": "policy",
        "path": "/admin/policy",
        "title": "Policy locks",
        "description": "Keys the API will never set true",
    },
)

# v1 name kept so existing callers still import the topic list.
SETTING_TOPICS = SETTINGS_RAIL

AUDITOR_ROLE_CODES = frozenset({"auditor", "read_only", "readonly"})
AUDITOR_NO_ADMIN_MODULES = frozenset({"hr", "hrms", "ap", "procurement", "user_admin"})


class SaasError(Exception):
    def __init__(self, message: str, status: int = 400):
        self.message = message
        self.status = status


def _json(obj: Any, status: int = 200):
    return jsonify(obj), status


def _impersonation_grants_admin() -> bool:
    return getattr(g, "impersonation_id", None) is not None


def _org_role(cu: CurrentUser) -> str | None:
    oid = current_organization_id()
    if cu.user is None or oid is None:
        return None
    with include_all_orgs():
        row = db.session.get(OrgMember, (cu.user.id, oid))
    return row.org_role if row is not None else None


def require_company_admin(cu: CurrentUser) -> uuid.UUID:
    if cu.user is None and not cu.is_dev_admin:
        raise SaasError("Company Admin required", 403)
    oid = current_organization_id()
    if oid is None:
        raise SaasError("no current tenant", 403)
    if cu.is_dev_admin or _impersonation_grants_admin():
        return oid
    if can_manage_directory_users(cu):
        return oid
    role = _org_role(cu)
    if role in (ORG_ROLE_OWNER, ORG_ROLE_ADMIN):
        return oid
    raise SaasError("Company Admin required", 403)


def require_platform_operator(cu: CurrentUser) -> User:
    if cu.is_dev_admin and cu.user is None:
        raise SaasError("platform operator required", 403)
    op_id = None
    if session:
        raw = session.get("impersonation_operator_id")
        if raw:
            try:
                op_id = uuid.UUID(str(raw))
            except (TypeError, ValueError):
                op_id = None
    user = cu.user
    if op_id is not None:
        with include_all_orgs():
            user = db.session.get(User, op_id) or user
    if user is None or not bool(getattr(user, "is_platform_operator", False)):
        raise SaasError("platform operator required", 403)
    return user


def _parse_uuid(raw: Any) -> uuid.UUID | None:
    if raw is None:
        return None
    try:
        return uuid.UUID(str(raw).strip())
    except (TypeError, ValueError):
        return None


def _setting_public(key: str, value: Any) -> dict[str, Any]:
    return {
        "key": key,
        "value": value,
        "locked": key in LOCKED_KEYS,
        "platform_only": key in PLATFORM_ONLY_KEYS,
        "default": SETTING_DEFAULTS.get(key),
    }


def _tenant_public(org: Organization, *, extra: bool = False) -> dict[str, Any]:
    item: dict[str, Any] = {
        "id": str(org.id),
        "slug": org.slug,
        "name": org.name,
        "legal_name": org.legal_name or org.name,
        "dba": org.dba,
        "cslb": org.cslb,
        "status": org.status or "active",
        "plan_key": org.plan_key or "full",
        "seat_cap_office": org.seat_cap_office,
        "seat_cap_field": org.seat_cap_field,
        "seat_cap_vendor_token": org.seat_cap_vendor_token,
        "created_at": org.created_at.isoformat() if org.created_at else None,
        "notes": org.notes if extra else None,
    }
    if extra:
        item["fein_last4"] = org.fein_last4
        item["storage_prefix"] = org.storage_prefix
        item["microsoft_sso_enabled"] = bool(org.microsoft_sso_enabled)
        entitlements = {}
        for key in MODULE_KEYS:
            entitlements[key] = module_enabled(org.id, key)
        item["entitlements"] = entitlements
        flags = {}
        for key in FEATURE_FLAG_CATALOG:
            flags[key] = feature_flag_on(key, org.id)
        item["flags"] = flags
        item["seats"] = _seat_usage(org)
    return item


def _seat_usage(org: Organization) -> dict[str, Any]:
    with include_all_orgs():
        office_used = db.session.scalar(
            select(func.count()).select_from(OrgMember).where(OrgMember.organization_id == org.id)
        ) or 0
        member_ids = select(OrgMember.user_id).where(OrgMember.organization_id == org.id)
        field_used = db.session.scalar(
            select(func.count()).select_from(MobileRefreshToken).where(
                MobileRefreshToken.user_id.in_(member_ids),
                MobileRefreshToken.revoked_at.is_(None),
            )
        ) or 0
        last = db.session.scalar(
            select(func.max(User.last_seen_at)).where(User.id.in_(member_ids))
        )
    return {
        "office_used": int(office_used),
        "office_cap": org.seat_cap_office,
        "field_used": int(field_used),
        "field_cap": org.seat_cap_field,
        "last_activity": last.isoformat() if last else None,
    }


def _optional_metric(fn):
    try:
        return fn()
    except Exception:
        db.session.rollback()
        return None


def _assert_seat_available(org: Organization, seat_kind: str) -> None:
    usage = _seat_usage(org)
    kind = (seat_kind or "office").strip().lower()
    if kind == "field":
        cap = org.seat_cap_field
        used = usage["field_used"]
        label = "Field device"
    else:
        cap = org.seat_cap_office
        used = usage["office_used"]
        label = "Office"
    if cap is not None and int(used) >= int(cap):
        raise SaasError(
            f"{label} seat cap reached ({used} / {cap}). Ask USIS to raise the cap or grant a temporary overage.",
            409,
        )


def _enrich_directory_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ids = []
    for it in items:
        uid = _parse_uuid(it.get("id"))
        if uid is not None:
            ids.append(uid)
    counts: dict[uuid.UUID, int] = {}
    if ids:
        rows = db.session.execute(
            select(MobileRefreshToken.user_id, func.count())
            .where(
                MobileRefreshToken.user_id.in_(ids),
                MobileRefreshToken.revoked_at.is_(None),
            )
            .group_by(MobileRefreshToken.user_id)
        ).all()
        counts = {uid: int(n) for uid, n in rows}
    for it in items:
        uid = _parse_uuid(it.get("id"))
        n = counts.get(uid, 0) if uid else 0
        it["devices"] = n
        it["seat_kind"] = "field" if n else "office"
        it["status"] = "active" if it.get("is_active") else "inactive"
    return items


def _health_checks() -> dict[str, dict[str, Any]]:
    checks: dict[str, dict[str, Any]] = {}
    try:
        from ..ai import config as ai_config

        checks["ai"] = {
            "status": "ok" if ai_config.is_configured() else "warn",
            "detail": "xAI configured" if ai_config.is_configured() else "xAI not configured",
        }
    except Exception as exc:
        checks["ai"] = {"status": "fail", "detail": str(exc)[:200]}
    try:
        from ._notifications import _mail_configured

        checks["smtp"] = {
            "status": "ok" if _mail_configured() else "warn",
            "detail": "mail configured" if _mail_configured() else "mail not configured",
        }
    except Exception as exc:
        checks["smtp"] = {"status": "fail", "detail": str(exc)[:200]}
    try:
        from ..services.object_storage import b2_enabled

        on = bool(b2_enabled())
        checks["b2"] = {"status": "ok" if on else "warn", "detail": "B2 configured" if on else "B2 not configured"}
    except Exception:
        b2_on = bool(
            (current_app.config.get("B2_APPLICATION_KEY_ID") or "")
            and (current_app.config.get("B2_APPLICATION_KEY") or "")
            and (current_app.config.get("B2_BUCKET_NAME") or "")
        )
        checks["b2"] = {"status": "ok" if b2_on else "warn", "detail": "B2 env" if b2_on else "B2 not configured"}
    broker = (os.environ.get("CELERY_BROKER_URL") or current_app.config.get("CELERY_BROKER_URL") or "").strip()
    checks["celery"] = {
        "status": "ok" if broker else "warn",
        "detail": "broker set" if broker else "no Celery broker",
    }
    with include_all_orgs():
        n = db.session.scalar(select(func.count()).select_from(Organization)) or 0
    checks["tenants"] = {"status": "ok", "detail": f"{int(n)} tenants"}
    return checks


def _settings_kpis(oid: uuid.UUID) -> dict[str, Any]:
    out: dict[str, Any] = {}

    def open_rfps():
        from ..models import Rfp

        closed = ("awarded", "closed", "cancelled", "canceled", "void")
        return int(
            db.session.scalar(
                select(func.count()).select_from(Rfp).where(func.lower(Rfp.status).notin_(closed))
            )
            or 0
        )

    def hires_in_flight():
        from ..models.hiring import HirePacket

        done = ("closed", "void")
        return int(
            db.session.scalar(
                select(func.count()).select_from(HirePacket).where(HirePacket.stage.notin_(done))
            )
            or 0
        )

    def clocked_in():
        from ..models.field_ops import TimeEntry

        return int(
            db.session.scalar(
                select(func.count())
                .select_from(TimeEntry)
                .where(TimeEntry.ended_at.is_(None), TimeEntry.voided.is_(False), TimeEntry.status != "closed")
            )
            or 0
        )

    val = _optional_metric(open_rfps)
    if val is not None:
        out["open_rfps"] = val
    val = _optional_metric(hires_in_flight)
    if val is not None:
        out["hires_in_flight"] = val
    val = _optional_metric(clocked_in)
    if val is not None:
        out["clocked_in"] = val
    return out


def _apply_company_fields(org: Organization, key: str, value: Any) -> None:
    if key == "company.legal_name":
        org.legal_name = str(value or "")[:255] or org.name
        if org.slug == "usis" or not org.name:
            org.name = org.legal_name
    elif key == "company.dba":
        org.dba = str(value or "")[:255] or None
    elif key == "company.cslb":
        org.cslb = str(value or "")[:40] or None


def _sync_time_policy_cost_code(value: Any) -> None:
    try:
        from ._time_policy import load_time_policy, save_time_policy

        save_time_policy({**load_time_policy(), "require_cost_code": bool(value)})
    except Exception:
        current_app.logger.exception("could not sync time.require_cost_code onto timekeeping policy")


def _publish_po_bands(tenant_id: uuid.UUID) -> None:
    """Write PO bands onto the next published purchase_order definition; never mutate in-flight."""
    from datetime import datetime, timezone

    from ..models import WorkflowDefinitionStep

    bands = {
        "band_0": tenant_setting(tenant_id, "po.band_0", 0),
        "band_pm": tenant_setting(tenant_id, "po.band_pm", 5000),
        "band_director": tenant_setting(tenant_id, "po.band_director", 25000),
        "band_president": tenant_setting(tenant_id, "po.band_president", None),
        "skip_down": False,
    }
    with include_all_orgs():
        current = db.session.scalar(
            select(WorkflowDefinition)
            .where(
                WorkflowDefinition.process_key == "purchase_order",
                WorkflowDefinition.organization_id == tenant_id,
                WorkflowDefinition.is_published.is_(True),
            )
            .order_by(WorkflowDefinition.version.desc())
            .limit(1)
        )
        if current is None:
            return
        nxt = WorkflowDefinition(
            process_key="purchase_order",
            version=int(current.version) + 1,
            name=current.name,
            project_id=current.project_id,
            organization_id=tenant_id,
            is_published=True,
            published_at=datetime.now(timezone.utc),
            notes="PO bands from Settings",
            created_by_user_id=current.created_by_user_id,
        )
        db.session.add(nxt)
        db.session.flush()
        for step in current.steps:
            auto = dict(step.automation or {}) if isinstance(step.automation, dict) else {}
            auto["po_bands"] = bands
            db.session.add(
                WorkflowDefinitionStep(
                    definition_id=nxt.id,
                    organization_id=tenant_id,
                    step_key=step.step_key,
                    label=step.label,
                    sort_order=step.sort_order,
                    queue_key=step.queue_key,
                    required_actions=step.required_actions,
                    on_approve_status=step.on_approve_status,
                    entry_condition=step.entry_condition,
                    skippable=step.skippable,
                    automation=auto,
                )
            )


def _put_setting(tenant_id: uuid.UUID, key: str, value: Any, actor_id: uuid.UUID | None) -> dict[str, Any]:
    if key in PLATFORM_ONLY_KEYS:
        raise SaasError("This setting is platform-only", 403)
    if key not in SETTING_DEFAULTS and key not in LOCKED_KEYS:
        raise SaasError("unknown setting key", 400)
    before = tenant_setting(tenant_id, key, SETTING_DEFAULTS.get(key))
    try:
        stored = set_tenant_setting(tenant_id, key, value, actor_user_id=actor_id)
    except LockedSettingError as exc:
        raise SaasError(exc.message, 403) from exc
    except ValueError as exc:
        raise SaasError(str(exc), 400) from exc
    with include_all_orgs():
        org = db.session.get(Organization, tenant_id)
        if org is not None:
            _apply_company_fields(org, key, stored)
    if key == "time.require_cost_code":
        _sync_time_policy_cost_code(stored)
    if key.startswith("po.band_") or key == "po.skip_down":
        try:
            _publish_po_bands(tenant_id)
        except Exception:
            current_app.logger.exception("could not publish PO band snapshot")
    write_platform_audit(
        action="setting.set",
        actor_user_id=actor_id,
        organization_id=tenant_id,
        before=before,
        after=stored,
    )
    db.session.commit()
    return _setting_public(key, stored)


def register_saas_routes() -> tuple[Blueprint, Blueprint]:
    return settings_bp, admin_bp


@settings_bp.get("")
def settings_index():
    try:
        cu = current_user()
        oid = require_company_admin(cu)
    except SaasError as exc:
        return _json({"error": exc.message}, exc.status)
    values = list_tenant_settings(oid)
    return _json(
        {
            "entity": "settings",
            "tenant_id": str(oid),
            "rail": SETTINGS_RAIL,
            "topics": SETTINGS_RAIL,
            "items": [_setting_public(k, values.get(k)) for k in SETTING_DEFAULTS if k not in PLATFORM_ONLY_KEYS],
            "locked_keys": sorted(LOCKED_KEYS),
        }
    )


@settings_bp.get("/overview")
def settings_overview():
    try:
        cu = current_user()
        oid = require_company_admin(cu)
    except SaasError as exc:
        return _json({"error": exc.message}, exc.status)
    with include_all_orgs():
        org = db.session.get(Organization, oid)
    if org is None:
        return _json({"error": "tenant not found"}, 404)
    seats = _seat_usage(org)
    modules = {key: module_enabled(oid, key) for key in MODULE_KEYS}
    recent = db.session.scalars(
        select(PlatformAudit)
        .where(PlatformAudit.organization_id == oid)
        .order_by(PlatformAudit.created_at.desc())
        .limit(10)
    ).all()
    return _json(
        {
            "entity": "settings_overview",
            "tenant_id": str(oid),
            "legal_name": org.legal_name or org.name,
            "plan_key": org.plan_key or "full",
            "status": org.status or "active",
            "seats": seats,
            "modules": modules,
            "kpis": _settings_kpis(oid),
            "recent_changes": [_audit_public(r) for r in recent],
            "can": {"invite": True, "new_project": True, "audit": True},
        }
    )


@settings_bp.get("/roles")
def settings_roles():
    from . import _admin_users_service as admin_users_svc
    from ..permissions.applicant import APPLICANT_ROLE_CODE
    from ..permissions.modules import ALL_LEVELS, catalog_public

    try:
        cu = current_user()
        require_company_admin(cu)
        items = [
            row
            for row in admin_users_svc.list_roles(cu)
            if (row.get("code") or "") != APPLICANT_ROLE_CODE
        ]
    except SaasError as exc:
        return _json({"error": exc.message}, exc.status)
    except admin_users_svc.ApiError as exc:
        return _json({"error": exc.message}, exc.status)
    return _json(
        {
            "entity": "roles",
            "items": items,
            "catalog": catalog_public(),
            "levels": list(ALL_LEVELS),
        }
    )


@settings_bp.put("/roles/<template_id>")
def settings_role_put(template_id: str):
    from . import _admin_users_service as admin_users_svc

    rid = _parse_uuid(template_id)
    if rid is None:
        return _json({"error": "invalid role id"}, 400)
    try:
        cu = current_user()
        oid = require_company_admin(cu)
        body = request.get_json(silent=True) or {}
        if not isinstance(body, dict):
            return _json({"error": "JSON body required"}, 400)
        existing = admin_users_svc.get_role(cu, rid)
        if existing is None:
            return _json({"error": "role not found"}, 404)
        code = (existing.get("code") or "").strip().lower()
        perms = body.get("permissions")
        if isinstance(perms, dict) and code in AUDITOR_ROLE_CODES:
            for mk in AUDITOR_NO_ADMIN_MODULES:
                if str(perms.get(mk) or "").strip().lower() == "admin":
                    raise SaasError("Auditor is read-only and cannot be given Admin on Hiring or Money.", 403)
            for mk, level in perms.items():
                if str(level).strip().lower() == "admin":
                    raise SaasError("Auditor is read-only everywhere.", 403)
        item = admin_users_svc.patch_role(cu, rid, body)
        write_platform_audit(
            action="role.update",
            actor_user_id=cu.id,
            organization_id=oid,
            before=existing.get("permissions"),
            after=(item or {}).get("permissions"),
        )
        db.session.commit()
    except SaasError as exc:
        db.session.rollback()
        return _json({"error": exc.message}, exc.status)
    except admin_users_svc.ApiError as exc:
        db.session.rollback()
        return _json({"error": exc.message}, exc.status)
    return _json({"entity": "role", "item": item})


@settings_bp.put("/<path:key>")
def settings_put(key: str):
    try:
        cu = current_user()
        oid = require_company_admin(cu)
    except SaasError as exc:
        return _json({"error": exc.message}, exc.status)
    body = request.get_json(silent=True) or {}
    if not isinstance(body, dict) or "value" not in body:
        return _json({"error": "JSON body with value is required"}, 400)
    try:
        item = _put_setting(oid, key, body.get("value"), cu.id)
    except SaasError as exc:
        db.session.rollback()
        return _json({"error": exc.message}, exc.status)
    return _json({"entity": "setting", "item": item})


@settings_bp.get("/users")
def settings_users():
    from . import _admin_users_service as admin_users_svc

    try:
        cu = current_user()
        require_company_admin(cu)
        items, total = admin_users_svc.list_users(cu, q=request.args.get("q"), limit=200, offset=0)
        items = _enrich_directory_items(items)
    except SaasError as exc:
        return _json({"error": exc.message}, exc.status)
    except admin_users_svc.ApiError as exc:
        return _json({"error": exc.message}, exc.status)
    return _json({"entity": "users", "items": items, "total": total})


@settings_bp.post("/users/invite")
def settings_invite():
    from . import _admin_users_service as admin_users_svc
    from ..services.password_reset import issue_set_password_token
    from ._notifications import send_password_reset_email

    try:
        cu = current_user()
        oid = require_company_admin(cu)
        data = request.get_json(silent=True) or {}
        if not isinstance(data, dict):
            data = {}
        else:
            data = dict(data)
        if data.get("role_id") and not data.get("role_ids"):
            data["role_ids"] = [data.get("role_id")]
        seat_kind = str(data.get("seat_kind") or "office").strip().lower()
        if seat_kind not in ("office", "field"):
            seat_kind = "office"
        with include_all_orgs():
            org = db.session.get(Organization, oid)
        if org is None:
            raise SaasError("no current tenant", 403)
        _assert_seat_available(org, seat_kind)
        item = admin_users_svc.create_user(cu, data)
        uid = _parse_uuid(item.get("id"))
        email_sent = False
        dry_run = False
        if uid is not None:
            u = db.session.get(User, uid)
            if u is not None and (u.email or "").strip():
                raw = issue_set_password_token(u)
                mail = send_password_reset_email(to=u.email, reset_token=raw)
                email_sent = bool(mail.get("sent"))
                dry_run = bool(mail.get("dry_run"))
        write_platform_audit(
            action="user.invite",
            actor_user_id=cu.id,
            organization_id=oid,
            after={"user_id": item.get("id"), "email": item.get("email")},
        )
        db.session.commit()
    except SaasError as exc:
        db.session.rollback()
        return _json({"error": exc.message}, exc.status)
    except admin_users_svc.ApiError as exc:
        db.session.rollback()
        return _json({"error": exc.message}, exc.status)
    return _json({"entity": "user_invite", "item": item, "email_sent": email_sent, "dry_run": dry_run}, 201)


@settings_bp.post("/users/<user_id>/roles")
def settings_user_roles(user_id: str):
    from . import _admin_users_service as admin_users_svc

    uid = _parse_uuid(user_id)
    if uid is None:
        return _json({"error": "invalid user id"}, 400)
    try:
        cu = current_user()
        oid = require_company_admin(cu)
        body = request.get_json(silent=True) or {}
        role_ids = body.get("role_ids") if isinstance(body, dict) else None
        if body.get("role_id") and not role_ids:
            role_ids = [body.get("role_id")]
        item = admin_users_svc.patch_user(cu, uid, {"role_ids": role_ids or []})
        if item is None:
            return _json({"error": "user not found"}, 404)
        write_platform_audit(
            action="user.roles",
            actor_user_id=cu.id,
            organization_id=oid,
            after={"user_id": str(uid), "role_ids": [r.get("id") for r in (item.get("roles") or [])]},
        )
        db.session.commit()
    except SaasError as exc:
        db.session.rollback()
        return _json({"error": exc.message}, exc.status)
    except admin_users_svc.ApiError as exc:
        db.session.rollback()
        return _json({"error": exc.message}, exc.status)
    return _json({"entity": "user", "item": item})


@settings_bp.post("/users/<user_id>/deactivate")
def settings_deactivate(user_id: str):
    from . import _admin_users_service as admin_users_svc

    uid = _parse_uuid(user_id)
    if uid is None:
        return _json({"error": "invalid user id"}, 400)
    try:
        cu = current_user()
        oid = require_company_admin(cu)
        item = admin_users_svc.patch_user(cu, uid, {"is_active": False})
        if item is None:
            return _json({"error": "user not found"}, 404)
        write_platform_audit(
            action="user.deactivate",
            actor_user_id=cu.id,
            organization_id=oid,
            after={"user_id": str(uid)},
        )
        db.session.commit()
    except SaasError as exc:
        db.session.rollback()
        return _json({"error": exc.message}, exc.status)
    except admin_users_svc.ApiError as exc:
        db.session.rollback()
        return _json({"error": exc.message}, exc.status)
    return _json({"entity": "user", "item": item})


@settings_bp.post("/users/<user_id>/reset-password")
def settings_reset_password(user_id: str):
    from . import _admin_users_service as admin_users_svc
    from ..services.password_reset import issue_set_password_token
    from ._notifications import send_password_reset_email

    uid = _parse_uuid(user_id)
    if uid is None:
        return _json({"error": "invalid user id"}, 400)
    try:
        cu = current_user()
        oid = require_company_admin(cu)
        item = admin_users_svc.get_user(cu, uid)
        if item is None:
            return _json({"error": "user not found"}, 404)
        u = db.session.get(User, uid)
        if u is None or not (u.email or "").strip():
            return _json({"error": "user has no email"}, 400)
        raw = issue_set_password_token(u)
        mail = send_password_reset_email(to=u.email, reset_token=raw)
        write_platform_audit(
            action="user.reset_password",
            actor_user_id=cu.id,
            organization_id=oid,
            after={"user_id": str(uid)},
        )
        db.session.commit()
    except SaasError as exc:
        db.session.rollback()
        return _json({"error": exc.message}, exc.status)
    except admin_users_svc.ApiError as exc:
        db.session.rollback()
        return _json({"error": exc.message}, exc.status)
    return _json(
        {
            "entity": "user_reset",
            "ok": True,
            "email_sent": bool(mail.get("sent")),
            "dry_run": bool(mail.get("dry_run")),
        }
    )


@settings_bp.get("/workflows")
def settings_workflows():
    try:
        cu = current_user()
        oid = require_company_admin(cu)
    except SaasError as exc:
        return _json({"error": exc.message}, exc.status)
    keys = ("purchase_order", "submittal_qc", "new_hire", "tm_ticket")
    items = []
    for process_key in keys:
        row = db.session.scalar(
            select(WorkflowDefinition)
            .options(selectinload(WorkflowDefinition.steps))
            .where(
                WorkflowDefinition.process_key == process_key,
                WorkflowDefinition.is_published.is_(True),
            )
            .order_by(WorkflowDefinition.version.desc())
            .limit(1)
        )
        if row is None:
            items.append({"process_key": process_key, "version": None, "steps": []})
            continue
        items.append(
            {
                "id": str(row.id),
                "process_key": row.process_key,
                "version": row.version,
                "name": row.name,
                "steps": [
                    {
                        "id": str(s.id),
                        "step_key": s.step_key,
                        "label": s.label,
                        "sort_order": s.sort_order,
                        "queue_key": s.queue_key,
                    }
                    for s in (row.steps or [])
                ],
            }
        )
    return _json({"entity": "workflows", "tenant_id": str(oid), "items": items})


@settings_bp.put("/workflows/<process_key>/steps")
def settings_workflow_steps(process_key: str):
    """Edit labels/sort_order and publish a new version (does not mutate in-flight instances)."""
    from ..models import WorkflowDefinitionStep

    try:
        cu = current_user()
        oid = require_company_admin(cu)
    except SaasError as exc:
        return _json({"error": exc.message}, exc.status)
    body = request.get_json(silent=True) or {}
    steps_in = body.get("steps") if isinstance(body, dict) else None
    if not isinstance(steps_in, list):
        return _json({"error": "steps array required"}, 400)
    current = db.session.scalar(
        select(WorkflowDefinition)
        .where(
            WorkflowDefinition.process_key == process_key,
            WorkflowDefinition.is_published.is_(True),
        )
        .order_by(WorkflowDefinition.version.desc())
        .limit(1)
    )
    if current is None:
        return _json({"error": "no published definition"}, 404)
    by_key = {s.step_key: s for s in current.steps}
    nxt = WorkflowDefinition(
        process_key=process_key,
        version=int(current.version) + 1,
        name=current.name,
        project_id=current.project_id,
        is_published=True,
        published_at=datetime.now(timezone.utc),
        notes="Edited from Settings",
        created_by_user_id=cu.id,
    )
    db.session.add(nxt)
    db.session.flush()
    for i, spec in enumerate(steps_in):
        if not isinstance(spec, dict):
            continue
        sk = str(spec.get("step_key") or "")
        src = by_key.get(sk)
        if src is None:
            continue
        db.session.add(
            WorkflowDefinitionStep(
                definition_id=nxt.id,
                step_key=src.step_key,
                label=str(spec.get("label") or src.label)[:200],
                sort_order=int(spec.get("sort_order") if spec.get("sort_order") is not None else i),
                queue_key=str(spec.get("queue_key") or src.queue_key or "") or src.queue_key,
                required_actions=src.required_actions,
                on_approve_status=src.on_approve_status,
                entry_condition=src.entry_condition,
                skippable=src.skippable,
                automation=src.automation,
            )
        )
    write_platform_audit(
        action="workflow.publish",
        actor_user_id=cu.id,
        organization_id=oid,
        after={"process_key": process_key, "version": nxt.version},
    )
    db.session.commit()
    return _json({"entity": "workflow", "process_key": process_key, "version": nxt.version})


@settings_bp.get("/audit")
def settings_audit():
    try:
        cu = current_user()
        oid = require_company_admin(cu)
    except SaasError as exc:
        return _json({"error": exc.message}, exc.status)
    rows = db.session.scalars(
        select(PlatformAudit)
        .where(PlatformAudit.organization_id == oid)
        .order_by(PlatformAudit.created_at.desc())
        .limit(200)
    ).all()
    return _json({"entity": "audit", "items": [_audit_public(r) for r in rows]})


def _audit_public(row: PlatformAudit) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "actor_user_id": str(row.actor_user_id) if row.actor_user_id else None,
        "tenant_id": str(row.organization_id) if row.organization_id else None,
        "action": row.action,
        "reason": row.reason,
        "before": row.before_json,
        "after": row.after_json,
        "ip": row.ip_address,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


@admin_bp.get("/overview")
def admin_overview():
    try:
        require_platform_operator(current_user())
    except SaasError as exc:
        return _json({"error": exc.message}, exc.status)
    with include_all_orgs():
        orgs = db.session.scalars(select(Organization)).all()
        open_imp = (
            db.session.scalar(
                select(func.count())
                .select_from(ImpersonationSession)
                .where(ImpersonationSession.ended_at.is_(None))
            )
            or 0
        )
        audit_rows = db.session.scalars(
            select(PlatformAudit).order_by(PlatformAudit.created_at.desc()).limit(20)
        ).all()
    by_status: dict[str, int] = {s: 0 for s in ("trial", "active", "past_due", "suspended", "closed")}
    office_used = office_cap = field_used = field_cap = 0
    for org in orgs:
        st = org.status or "active"
        by_status[st] = by_status.get(st, 0) + 1
        seats = _seat_usage(org)
        office_used += seats["office_used"]
        office_cap += int(org.seat_cap_office or 0)
        field_used += seats["field_used"]
        field_cap += int(org.seat_cap_field or 0)
    return _json(
        {
            "entity": "admin_overview",
            "rail": ADMIN_RAIL,
            "organizations_by_status": by_status,
            "organization_count": len(orgs),
            "seats": {
                "office_used": office_used,
                "office_cap": office_cap,
                "field_used": field_used,
                "field_cap": field_cap,
            },
            "ai_calls_today": None,
            "health": _health_checks(),
            "open_impersonations": int(open_imp),
            "audit": [_audit_public(r) for r in audit_rows],
        }
    )


@admin_bp.get("/plans")
def admin_plans():
    try:
        require_platform_operator(current_user())
    except SaasError as exc:
        return _json({"error": exc.message}, exc.status)
    items = []
    for key in PLAN_KEYS:
        items.append(
            {
                "plan_key": key,
                "modules": sorted(PLAN_DEFAULT_MODULES.get(key) or ()),
            }
        )
    return _json({"entity": "plans", "items": items, "all_modules": list(MODULE_KEYS)})


@admin_bp.get("/policy-locks")
@admin_bp.get("/policy")
def admin_policy_locks():
    try:
        require_platform_operator(current_user())
    except SaasError as exc:
        return _json({"error": exc.message}, exc.status)
    items = [{"key": k, "message": LOCKED_MESSAGE, "locked_value": False} for k in sorted(LOCKED_KEYS)]
    return _json({"entity": "policy_locks", "items": items})


@admin_bp.get("/organizations")
def admin_organizations():
    return admin_tenants()


@admin_bp.post("/organizations")
def admin_create_organization():
    return admin_create_tenant()


@admin_bp.get("/organizations/<tenant_id>")
def admin_get_organization(tenant_id: str):
    return admin_get_tenant(tenant_id)


@admin_bp.patch("/organizations/<tenant_id>")
def admin_patch_organization(tenant_id: str):
    return admin_patch_tenant(tenant_id)


@admin_bp.post("/organizations/<tenant_id>/impersonate")
def admin_impersonate_organization(tenant_id: str):
    return admin_impersonate(tenant_id)


@admin_bp.get("/tenants")
def admin_tenants():
    try:
        require_platform_operator(current_user())
    except SaasError as exc:
        return _json({"error": exc.message}, exc.status)
    with include_all_orgs():
        rows = db.session.scalars(select(Organization).order_by(Organization.name.asc())).all()
        items = []
        for org in rows:
            item = _tenant_public(org)
            item["seats"] = _seat_usage(org)
            items.append(item)
    return _json({"entity": "tenants", "items": items, "total": len(items)})


@admin_bp.post("/tenants")
def admin_create_tenant():
    try:
        op = require_platform_operator(current_user())
    except SaasError as exc:
        return _json({"error": exc.message}, exc.status)
    data = request.get_json(silent=True) or {}
    name = str(data.get("name") or data.get("legal_name") or "").strip()
    if not name:
        return _json({"error": "name is required"}, 400)
    try:
        org = provision_organization(name=name, copy_catalog=bool(data.get("copy_catalog")))
        if data.get("plan_key") in ("field", "office", "full"):
            org.plan_key = data["plan_key"]
        write_platform_audit(
            action="tenant.create",
            actor_user_id=op.id,
            organization_id=org.id,
            after={"name": org.name, "slug": org.slug},
        )
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return _json({"error": "A tenant with that name already exists."}, 409)
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception("create tenant failed")
        return _json({"error": "Could not create tenant"}, 500)
    return _json({"entity": "tenant", "item": _tenant_public(org, extra=True)}, 201)


@admin_bp.get("/tenants/<tenant_id>")
def admin_get_tenant(tenant_id: str):
    try:
        require_platform_operator(current_user())
    except SaasError as exc:
        return _json({"error": exc.message}, exc.status)
    tid = _parse_uuid(tenant_id)
    if tid is None:
        return _json({"error": "invalid tenant id"}, 400)
    with include_all_orgs():
        org = db.session.get(Organization, tid)
    if org is None:
        return _json({"error": "tenant not found"}, 404)
    return _json({"entity": "tenant", "item": _tenant_public(org, extra=True)})


@admin_bp.patch("/tenants/<tenant_id>")
def admin_patch_tenant(tenant_id: str):
    try:
        op = require_platform_operator(current_user())
    except SaasError as exc:
        return _json({"error": exc.message}, exc.status)
    tid = _parse_uuid(tenant_id)
    if tid is None:
        return _json({"error": "invalid tenant id"}, 400)
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return _json({"error": "JSON body required"}, 400)
    reason = str(data.get("reason") or "").strip()
    with include_all_orgs():
        org = db.session.get(Organization, tid)
        if org is None:
            return _json({"error": "tenant not found"}, 404)
        before = _tenant_public(org, extra=True)
        if "status" in data:
            st = str(data.get("status") or "").strip()
            if st not in ("trial", "active", "past_due", "suspended", "closed"):
                return _json({"error": "invalid status"}, 400)
            if st in ("suspended", "closed") and len(reason) < 12:
                return _json({"error": "reason is required (min 12 characters)"}, 400)
            org.status = st
        if "plan_key" in data:
            pk = str(data.get("plan_key") or "").strip()
            if pk not in ("field", "office", "full"):
                return _json({"error": "invalid plan_key"}, 400)
            org.plan_key = pk
        if "notes" in data:
            org.notes = str(data.get("notes") or "")[:4000] or None
        for cap in ("seat_cap_office", "seat_cap_field", "seat_cap_vendor_token"):
            if cap in data:
                if len(reason) < 12:
                    return _json({"error": "reason is required (min 12 characters)"}, 400)
                try:
                    setattr(org, cap, max(0, int(data[cap])))
                except (TypeError, ValueError):
                    return _json({"error": f"invalid {cap}"}, 400)
        if "legal_name" in data:
            org.legal_name = str(data.get("legal_name") or "")[:255] or org.name
        if "entitlements" in data and isinstance(data["entitlements"], dict):
            for mk, on in data["entitlements"].items():
                if mk in MODULE_KEYS:
                    set_entitlement(org.id, mk, bool(on))
        write_platform_audit(
            action="tenant.update",
            actor_user_id=op.id,
            organization_id=org.id,
            reason=reason or None,
            before=before,
            after=_tenant_public(org, extra=True),
        )
        db.session.commit()
    return _json({"entity": "tenant", "item": _tenant_public(org, extra=True)})


@admin_bp.post("/tenants/<tenant_id>/impersonate")
def admin_impersonate(tenant_id: str):
    try:
        op = require_platform_operator(current_user())
    except SaasError as exc:
        return _json({"error": exc.message}, exc.status)
    tid = _parse_uuid(tenant_id)
    if tid is None:
        return _json({"error": "invalid tenant id"}, 400)
    data = request.get_json(silent=True) or {}
    reason = str(data.get("reason") or "").strip()
    if len(reason) < 12:
        return _json({"error": "reason is required (min 12 characters)"}, 400)
    target_id = _parse_uuid(data.get("target_user_id"))
    with include_all_orgs():
        org = db.session.get(Organization, tid)
        if org is None:
            return _json({"error": "tenant not found"}, 404)
        if target_id is not None:
            target = db.session.get(User, target_id)
            if target is None:
                return _json({"error": "target user not found"}, 404)
        row = ImpersonationSession(
            operator_user_id=op.id,
            organization_id=org.id,
            target_user_id=target_id,
            reason=reason,
            banner_ack=True,
        )
        db.session.add(row)
        db.session.flush()
        write_platform_audit(
            action="impersonate.start",
            actor_user_id=op.id,
            organization_id=org.id,
            reason=reason,
            after={"impersonation_id": str(row.id), "target_user_id": str(target_id) if target_id else None},
        )
        db.session.commit()
    session["impersonation_id"] = str(row.id)
    session["impersonation_operator_id"] = str(op.id)
    set_current_organization_id(org.id)
    if target_id is not None:
        session["impersonation_saved_user_id"] = str(op.id)
        session["user_id"] = str(target_id)
    return _json(
        {
            "entity": "impersonation",
            "banner": True,
            "item": {
                "id": str(row.id),
                "tenant_id": str(org.id),
                "tenant_name": org.legal_name or org.name,
            },
        }
    )


@admin_bp.post("/impersonate/end")
def admin_impersonate_end():
    raw = session.get("impersonation_id")
    sid = _parse_uuid(raw)
    if sid is None:
        return _json({"error": "no impersonation session"}, 400)
    with include_all_orgs():
        row = db.session.get(ImpersonationSession, sid)
        if row is None:
            session.pop("impersonation_id", None)
            return _json({"error": "session not found"}, 404)
        row.ended_at = datetime.now(timezone.utc)
        write_platform_audit(
            action="impersonate.end",
            actor_user_id=row.operator_user_id,
            organization_id=row.organization_id,
            after={"impersonation_id": str(row.id)},
        )
        db.session.commit()
    saved = session.pop("impersonation_saved_user_id", None)
    if saved:
        session["user_id"] = saved
    session.pop("impersonation_id", None)
    session.pop("impersonation_operator_id", None)
    set_current_organization_id(None)
    return _json({"entity": "impersonation", "ended": True, "banner": False})


@admin_bp.get("/impersonate/status")
def admin_impersonate_status():
    raw = session.get("impersonation_id")
    sid = _parse_uuid(raw)
    if sid is None:
        return _json({"active": False, "banner": False})
    with include_all_orgs():
        row = db.session.get(ImpersonationSession, sid)
        if row is None or row.ended_at is not None:
            return _json({"active": False, "banner": False})
        org = db.session.get(Organization, row.organization_id)
    name = (org.legal_name or org.name) if org is not None else "tenant"
    return _json(
        {
            "active": True,
            "banner": True,
            "tenant_id": str(row.organization_id),
            "tenant_name": name,
            "reason": row.reason,
        }
    )


@admin_bp.get("/flags")
def admin_flags():
    try:
        require_platform_operator(current_user())
    except SaasError as exc:
        return _json({"error": exc.message}, exc.status)
    tid = _parse_uuid(request.args.get("tenant_id"))
    items = []
    for key, meta in FEATURE_FLAG_CATALOG.items():
        items.append(
            {
                "key": key,
                "description": meta.get("description"),
                "catalog_default": bool(meta.get("default_on")),
                "value": feature_flag_on(key, tid),
            }
        )
    with include_all_orgs():
        extras = db.session.scalars(select(FeatureFlag).where(FeatureFlag.organization_id.is_(None))).all()
    known = {i["key"] for i in items}
    for row in extras:
        if row.key in known:
            continue
        items.append(
            {
                "key": row.key,
                "description": row.description,
                "catalog_default": bool(row.default_on),
                "value": bool(row.default_on),
            }
        )
    return _json({"entity": "flags", "items": items, "tenant_id": str(tid) if tid else None})


@admin_bp.put("/flags/<path:key>")
def admin_put_flag(key: str):
    try:
        op = require_platform_operator(current_user())
    except SaasError as exc:
        return _json({"error": exc.message}, exc.status)
    body = request.get_json(silent=True) or {}
    if not isinstance(body, dict) or "value" not in body:
        return _json({"error": "JSON body with value is required"}, 400)
    reason = str(body.get("reason") or "").strip()
    tid = _parse_uuid(body.get("tenant_id"))
    before = feature_flag_on(key, tid)
    row = upsert_feature_flag(key, value=bool(body.get("value")), tenant_id=tid)
    write_platform_audit(
        action="flag.set",
        actor_user_id=op.id,
        organization_id=tid,
        reason=reason or None,
        before=before,
        after=bool(row.default_on),
    )
    db.session.commit()
    return _json({"entity": "flag", "item": {"key": key, "value": bool(row.default_on), "tenant_id": str(tid) if tid else None}})


@admin_bp.get("/health")
@admin_bp.get("/usage")
def admin_health():
    try:
        require_platform_operator(current_user())
    except SaasError as exc:
        return _json({"error": exc.message}, exc.status)
    return _json({"entity": "health", "items": _health_checks()})


@admin_bp.get("/audit")
def admin_audit():
    try:
        require_platform_operator(current_user())
    except SaasError as exc:
        return _json({"error": exc.message}, exc.status)
    stmt = select(PlatformAudit).order_by(PlatformAudit.created_at.desc()).limit(300)
    tid = _parse_uuid(request.args.get("tenant_id"))
    if tid is not None:
        stmt = stmt.where(PlatformAudit.organization_id == tid)
    with include_all_orgs():
        rows = db.session.scalars(stmt).all()
    return _json({"entity": "audit", "items": [_audit_public(r) for r in rows]})


@admin_bp.post("/tenants/<tenant_id>/export")
def admin_tenant_export(tenant_id: str):
    try:
        op = require_platform_operator(current_user())
    except SaasError as exc:
        return _json({"error": exc.message}, exc.status)
    tid = _parse_uuid(tenant_id)
    if tid is None:
        return _json({"error": "invalid tenant id"}, 400)
    write_platform_audit(
        action="tenant.export",
        actor_user_id=op.id,
        organization_id=tid,
        after={"queued": True},
    )
    db.session.commit()
    return _json({"entity": "tenant_export", "queued": True, "stub": True})
