"""Tenant setting helper, locked keys, plan entitlements, feature flags.

Reads go through ``tenant_setting(tenant_id, key, default)``. Existing modules
that already read ``quotes@gousis.com`` etc. should call this helper only when
that module is touched. Missing ``TenantSetting`` row = inherit the code default.
"""
from __future__ import annotations

import os
import threading
import uuid
from typing import Any

from flask import has_request_context, request, session
from sqlalchemy import select

from .extensions import db
from .models.organization import Organization, USIS_ORG_SLUG
from .models.saas import FeatureFlag, TenantEntitlement, TenantSetting
from .tenancy import current_organization_id, include_all_orgs

LOCKED_MESSAGE = "Platform policy — cannot be changed."

LOCKED_KEYS = frozenset(
    {
        "ai.dump_correspondence_to_grok",
        "qb.employee_add",
        "edd.auto_file",
        "hire.ssn_on_user",
        "po.skip_down",
        "punch.auto_push_procore",
    }
)

ALLOWED_FROM_DOMAINS = ("gousis.com",)

MODULE_KEYS = (
    "crm",
    "estimating",
    "rfp",
    "drawings",
    "field",
    "time",
    "hiring",
    "correspondence",
    "local_ai",
    "spec_split",
)

PLAN_KEYS = ("field", "office", "full")

PLAN_DEFAULT_MODULES: dict[str, frozenset[str]] = {
    "field": frozenset({"field", "time"}),
    "office": frozenset(
        {
            "crm",
            "estimating",
            "rfp",
            "drawings",
            "time",
            "hiring",
            "correspondence",
            "local_ai",
            "spec_split",
        }
    ),
    "full": frozenset(MODULE_KEYS),
}

ESTIMATE_STAGE_LABELS = {
    "new_lead": "New Lead",
    "invited": "Invited",
    "estimating": "Estimating",
    "submitted": "Submitted",
    "awarded": "Awarded",
    "lost": "Lost",
    "hold": "Hold",
    "declined": "Declined",
}

DEFAULT_LEGAL_FOOTER = (
    "This document is confidential and intended only for the named recipient. "
    "Prevailing-wage and certified-payroll rules may apply to this project."
)

DEFAULT_NEVER_SPAM_SUBJECTS = ["ITB", "RFI", "submittal", "quote"]

SETTING_DEFAULTS: dict[str, Any] = {
    "company.legal_name": "US Interior Specialties",
    "company.dba": "",
    "company.cslb": "",
    "company.timezone": "America/Los_Angeles",
    "company.logo_document_id": None,
    "company.offices": [],
    "company.letterhead_document_id": None,
    "company.public_hostname": "",
    "security.sso_m365_tenant_id": "",
    "security.mfa_required_roles": ["president", "hr", "ap"],
    "security.session_idle_minutes": 480,
    "security.session_max_minutes": 1440,
    "security.password_reset_hours": 24,
    "mail.rfp.from_address": "quotes@gousis.com",
    "mail.rfp.from_name": "US Interior Specialties",
    "mail.rfp.bcc_self": True,
    "mail.field.from_address": "field@gousis.com",
    "mail.hire.from_address": "hire@gousis.com",
    "public.rfp_token_ttl_hours": 336,
    "public.hire_token_ttl_hours": 168,
    "public.tm_token_ttl_hours": 72,
    "public.legal_footer": DEFAULT_LEGAL_FOOTER,
    "ai.default_provider": "grok",
    "ai.mode.construction_review": True,
    "ai.mode.estimating_review": True,
    "ai.mode.spec_package_review": True,
    "ai.mode.submittal_review": True,
    "ai.mode.bid_feasibility": True,
    "ai.mode.email_classify": True,
    "ai.submittal_rubber_stamp_seconds": 180,
    "ai.email_scan_cap_per_run": 400,
    "ai.dump_correspondence_to_grok": False,
    "ai.local_endpoint": "http://127.0.0.1:8000",
    "ai.tenant_call_cap_daily": None,
    "mail.allow_mailboxes": [],
    "mail.spam_confidence_move": 0.90,
    "mail.never_auto_spam_domains": ["gousis.com"],
    "mail.never_auto_spam_subjects": list(DEFAULT_NEVER_SPAM_SUBJECTS),
    "correspondence.teams_ingest": False,
    "files.spec_split_roles": ["estimator", "pm", "admin"],
    "po.band_0": 0,
    "po.band_pm": 5000,
    "po.band_director": 25000,
    "po.band_president": None,
    "po.skip_down": False,
    "tm.requires_co": True,
    "time.require_cost_code": False,
    "estimate.stage_labels": dict(ESTIMATE_STAGE_LABELS),
    "qb.company_file_name": "",
    "qb.employee_add": False,
    "edd.auto_file": False,
    "field.geofence_mode": "flag",
    "field.signoff_required": True,
    "punch.auto_push_procore": False,
    "hire.w4_edition": "2026",
    "hire.i9_edition": "01/20/25",
    "hire.ssn_on_user": False,
}

PLATFORM_ONLY_KEYS = frozenset({"ai.local_endpoint", "ai.tenant_call_cap_daily"})

FEATURE_FLAG_CATALOG: dict[str, dict[str, Any]] = {
    "rfp.b2_files_page": {"default_on": False, "description": "RFP B2 files page"},
    "ai.local_model": {"default_on": True, "description": "Local AI selectable in ChatBot"},
}

_CACHE: dict[tuple[str, str], Any] = {}
_CACHE_LOCK = threading.Lock()


class LockedSettingError(Exception):
    def __init__(self, key: str, message: str = LOCKED_MESSAGE):
        self.key = key
        self.message = message
        super().__init__(message)


def _cache_key(tenant_id: uuid.UUID | None, key: str) -> tuple[str, str]:
    return (str(tenant_id) if tenant_id else "*", key)


def bust_setting_cache(tenant_id: uuid.UUID | None = None, key: str | None = None) -> None:
    with _CACHE_LOCK:
        if tenant_id is None and key is None:
            _CACHE.clear()
            return
        drop = []
        tid = str(tenant_id) if tenant_id else None
        for ck in _CACHE:
            if tid is not None and ck[0] != tid:
                continue
            if key is not None and ck[1] != key:
                continue
            drop.append(ck)
        for ck in drop:
            _CACHE.pop(ck, None)


def tenant_setting(tenant_id: uuid.UUID | None, key: str, default: Any = None) -> Any:
    """Resolve a setting: stored row → code default → caller default."""
    if default is None and key in SETTING_DEFAULTS:
        default = SETTING_DEFAULTS[key]
    if tenant_id is None:
        return default
    ck = _cache_key(tenant_id, key)
    with _CACHE_LOCK:
        if ck in _CACHE:
            return _CACHE[ck]
    row = None
    with include_all_orgs():
        row = db.session.get(TenantSetting, (tenant_id, key))
    value = row.value_json if row is not None else default
    if key in LOCKED_KEYS:
        value = False
    with _CACHE_LOCK:
        _CACHE[ck] = value
    return value


def current_tenant_setting(key: str, default: Any = None) -> Any:
    return tenant_setting(current_organization_id(), key, default)


def from_address_allowed(address: str) -> bool:
    addr = (address or "").strip().lower()
    if "@" not in addr:
        return False
    domain = addr.rsplit("@", 1)[-1]
    return any(domain == d or domain.endswith("." + d) for d in ALLOWED_FROM_DOMAINS)


def set_tenant_setting(
    tenant_id: uuid.UUID,
    key: str,
    value: Any,
    *,
    actor_user_id: uuid.UUID | None = None,
    allow_locked: bool = False,
) -> Any:
    if key in LOCKED_KEYS and not allow_locked:
        raise LockedSettingError(key)
    if key in ("mail.rfp.from_address", "mail.field.from_address", "mail.hire.from_address"):
        if value and not from_address_allowed(str(value)):
            raise ValueError("From address must use an allow-listed company domain.")
    if key == "ai.dump_correspondence_to_grok" and value:
        raise LockedSettingError(key)
    with include_all_orgs():
        row = db.session.get(TenantSetting, (tenant_id, key))
        if row is None:
            row = TenantSetting(
                organization_id=tenant_id,
                key=key,
                value_json=value,
                updated_by_user_id=actor_user_id,
            )
            db.session.add(row)
        else:
            row.value_json = value
            row.updated_by_user_id = actor_user_id
        db.session.flush()
    bust_setting_cache(tenant_id, key)
    return value


def list_tenant_settings(tenant_id: uuid.UUID) -> dict[str, Any]:
    out = dict(SETTING_DEFAULTS)
    with include_all_orgs():
        rows = db.session.scalars(
            select(TenantSetting).where(TenantSetting.organization_id == tenant_id)
        ).all()
    for row in rows:
        out[row.key] = row.value_json
    for locked in LOCKED_KEYS:
        out[locked] = False
    return out


def module_enabled(tenant_id: uuid.UUID | None, module_key: str) -> bool:
    if tenant_id is None:
        return True
    with include_all_orgs():
        row = db.session.scalar(
            select(TenantEntitlement).where(
                TenantEntitlement.organization_id == tenant_id,
                TenantEntitlement.module_key == module_key,
            )
        )
        if row is not None:
            return bool(row.enabled)
        org = db.session.get(Organization, tenant_id)
    plan = (org.plan_key if org is not None else None) or "full"
    allowed = PLAN_DEFAULT_MODULES.get(plan, PLAN_DEFAULT_MODULES["full"])
    return module_key in allowed


def set_entitlement(tenant_id: uuid.UUID, module_key: str, enabled: bool) -> None:
    if module_key not in MODULE_KEYS:
        raise ValueError(f"unknown module_key: {module_key}")
    with include_all_orgs():
        row = db.session.scalar(
            select(TenantEntitlement).where(
                TenantEntitlement.organization_id == tenant_id,
                TenantEntitlement.module_key == module_key,
            )
        )
        if row is None:
            db.session.add(
                TenantEntitlement(
                    organization_id=tenant_id,
                    module_key=module_key,
                    enabled=bool(enabled),
                )
            )
        else:
            row.enabled = bool(enabled)
        db.session.flush()


def feature_flag_on(key: str, tenant_id: uuid.UUID | None = None) -> bool:
    catalog = FEATURE_FLAG_CATALOG.get(key, {"default_on": False})
    platform_default = bool(catalog.get("default_on"))
    with include_all_orgs():
        plat = db.session.scalar(
            select(FeatureFlag).where(
                FeatureFlag.key == key,
                FeatureFlag.organization_id.is_(None),
            )
        )
        if plat is not None:
            platform_default = bool(plat.default_on)
        if tenant_id is not None:
            override = db.session.scalar(
                select(FeatureFlag).where(
                    FeatureFlag.key == key,
                    FeatureFlag.organization_id == tenant_id,
                )
            )
            if override is not None:
                return bool(override.default_on)
    return platform_default


def upsert_feature_flag(
    key: str,
    *,
    value: bool,
    tenant_id: uuid.UUID | None = None,
    description: str | None = None,
) -> FeatureFlag:
    with include_all_orgs():
        stmt = select(FeatureFlag).where(FeatureFlag.key == key)
        if tenant_id is None:
            stmt = stmt.where(FeatureFlag.organization_id.is_(None))
        else:
            stmt = stmt.where(FeatureFlag.organization_id == tenant_id)
        row = db.session.scalar(stmt)
        if row is None:
            row = FeatureFlag(
                key=key,
                default_on=bool(value),
                description=description or FEATURE_FLAG_CATALOG.get(key, {}).get("description"),
                organization_id=tenant_id,
            )
            db.session.add(row)
        else:
            row.default_on = bool(value)
            if description:
                row.description = description
        db.session.flush()
        return row


def seed_usis_tenant_fields(org: Organization) -> None:
    """Fill SaaS columns on the seed USIS organization without overwriting edits."""
    if not (org.legal_name or "").strip():
        org.legal_name = org.name or "US Interior Specialties"
    if not (org.status or "").strip():
        org.status = "active"
    if not (org.plan_key or "").strip():
        org.plan_key = "full"
    if org.seat_cap_office is None:
        org.seat_cap_office = 50
    if org.seat_cap_field is None:
        org.seat_cap_field = 50
    if org.seat_cap_vendor_token is None:
        org.seat_cap_vendor_token = 500


def ensure_platform_operators() -> None:
    """Seed ``is_platform_operator`` from env or existing superusers."""
    from .models import User

    email = (os.environ.get("PLATFORM_OPERATOR_EMAIL") or "").strip().lower()
    with include_all_orgs():
        if email:
            u = db.session.scalar(select(User).where(User.email == email))
            if u is not None and not u.is_platform_operator:
                u.is_platform_operator = True
                db.session.flush()
                return
        any_op = db.session.scalar(select(User.id).where(User.is_platform_operator.is_(True)).limit(1))
        if any_op is not None:
            return
        for u in db.session.scalars(select(User).where(User.is_superuser.is_(True))).all():
            u.is_platform_operator = True
        db.session.flush()


def impersonation_session_id() -> uuid.UUID | None:
    if not has_request_context():
        return None
    raw = session.get("impersonation_id")
    if not raw:
        return None
    try:
        return uuid.UUID(str(raw))
    except (TypeError, ValueError):
        return None


def request_audit_meta() -> tuple[str | None, str | None]:
    if not has_request_context():
        return None, None
    ip = (request.headers.get("X-Forwarded-For") or request.remote_addr or "")[:45] or None
    ua = (request.headers.get("User-Agent") or "")[:500] or None
    return ip, ua


def write_platform_audit(
    *,
    action: str,
    actor_user_id: uuid.UUID | None,
    organization_id: uuid.UUID | None = None,
    reason: str | None = None,
    before: Any = None,
    after: Any = None,
) -> None:
    from .models.saas import PlatformAudit

    ip, ua = request_audit_meta()
    row = PlatformAudit(
        actor_user_id=actor_user_id,
        organization_id=organization_id,
        impersonation_id=impersonation_session_id(),
        action=action,
        reason=reason,
        before_json=before,
        after_json=after,
        ip_address=ip,
        user_agent=ua,
    )
    db.session.add(row)
    db.session.flush()
