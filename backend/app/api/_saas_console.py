"""SaaS Admin v2 remaining routes (slices 3–9). Attached from ``_saas_admin``."""
from __future__ import annotations

import csv
import io
import secrets
import uuid
from datetime import datetime, timezone
from typing import Any

from flask import Response, current_app, request
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from ..extensions import db
from ..models import (
    MobileRefreshToken,
    OrganizationNote,
    OrganizationSeatOverage,
    OrganizationSendDomain,
    PlatformAudit,
    PlatformJob,
    User,
    WorkflowDefinition,
    WorkflowDefinitionStep,
)
from ..models.organization import Organization, OrganizationMember as OrgMember
from ..models.saas import FeatureFlag
from ..tenant_settings import (
    FEATURE_FLAG_CATALOG,
    LOCKED_KEYS,
    LOCKED_MESSAGE,
    MODULE_KEYS,
    PLAN_DEFAULT_MODULES,
    PLAN_KEYS,
    SETTING_DEFAULTS,
    feature_flag_on,
    live_send_domains,
    module_enabled,
    plan_default_modules,
    set_entitlement,
    set_plan_default_modules,
    set_tenant_setting,
    tenant_setting,
    upsert_feature_flag,
    write_platform_audit,
)
from ..tenancy import include_all_orgs
from ._saas_admin import (
    SaasError,
    _audit_public,
    _health_checks,
    _json,
    _parse_uuid,
    _publish_po_bands,
    _put_setting,
    _seat_usage,
    _setting_public,
    _tenant_public,
    admin_bp,
    require_company_admin,
    require_platform_operator,
    settings_bp,
)

CORE_PROCESS_KEYS = ("purchase_order", "submittal_qc", "new_hire", "tm_ticket")
EXTRA_PROCESS_KEYS = ("rfp_award", "change_order")
ASSIGNMENT_POLICIES = ("queue", "role", "creator", "unassigned")
MONEY_KEYS = ("po.band_0", "po.band_pm", "po.band_director", "po.band_president", "tm.requires_co")
PLAN_STAFF_PATHS: tuple[tuple[str, str], ...] = (
    ("/construction/leads", "crm"),
    ("/construction/lead-", "crm"),
    ("/usis-crm", "crm"),
    ("/api/v1/lead-estimates", "crm"),
    ("/api/v1/companies", "crm"),
    ("/api/v1/contacts", "crm"),
    ("/construction/estimate", "estimating"),
    ("/api/v1/estimates", "estimating"),
    ("/api/v1/estimate-queue", "estimating"),
    ("/usis-rfp", "rfp"),
    ("/api/v1/rfps", "rfp"),
    ("/api/v1/rfp", "rfp"),
    ("/construction/drawing", "drawings"),
    ("/api/v1/drawings", "drawings"),
    ("/api/field", "field"),
    ("/api/v1/time-clock", "field"),
    ("/time/", "time"),
    ("/usis-time", "time"),
    ("/api/time", "time"),
    ("/people/hiring", "hiring"),
    ("/usis-people-hiring", "hiring"),
    ("/api/hires", "hiring"),
    ("/usis-correspondence", "correspondence"),
    ("/usis-ingest", "correspondence"),
    ("/api/correspondence", "correspondence"),
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _reason(body: dict[str, Any] | None = None, *, min_len: int = 12) -> str:
    raw = str((body or {}).get("reason") or "").strip()
    if len(raw) < min_len:
        raise SaasError("reason is required (min 12 characters)", 400)
    return raw


def _assignment_of(step: WorkflowDefinitionStep) -> str:
    auto = step.automation if isinstance(step.automation, dict) else {}
    val = str(auto.get("assignment_policy") or "queue").strip().lower()
    return val if val in ASSIGNMENT_POLICIES else "queue"


def _published_definition(process_key: str, tenant_id: uuid.UUID | None = None) -> WorkflowDefinition | None:
    with include_all_orgs():
        stmt = (
            select(WorkflowDefinition)
            .options(selectinload(WorkflowDefinition.steps))
            .where(
                WorkflowDefinition.process_key == process_key,
                WorkflowDefinition.is_published.is_(True),
            )
            .order_by(WorkflowDefinition.version.desc())
        )
        if tenant_id is not None:
            scoped = db.session.scalars(stmt.where(WorkflowDefinition.organization_id == tenant_id)).first()
            if scoped is not None:
                return scoped
        return db.session.scalars(stmt).first()


def _workflow_item(process_key: str, row: WorkflowDefinition | None) -> dict[str, Any]:
    if row is None:
        return {"process_key": process_key, "version": None, "name": process_key, "steps": []}
    return {
        "id": str(row.id),
        "process_key": process_key,
        "version": row.version,
        "name": row.name,
        "steps": [
            {
                "id": str(s.id),
                "step_key": s.step_key,
                "label": s.label,
                "sort_order": s.sort_order,
                "queue_key": s.queue_key,
                "assignment_policy": _assignment_of(s),
            }
            for s in (row.steps or [])
        ],
    }


def _overage_live(org_id: uuid.UUID, seat_kind: str) -> OrganizationSeatOverage | None:
    now = _utcnow()
    with include_all_orgs():
        return db.session.scalars(
            select(OrganizationSeatOverage)
            .where(
                OrganizationSeatOverage.organization_id == org_id,
                OrganizationSeatOverage.seat_kind == seat_kind,
                OrganizationSeatOverage.expires_at > now,
            )
            .order_by(OrganizationSeatOverage.expires_at.desc())
        ).first()


def _queue_job(
    *,
    org_id: uuid.UUID,
    job_type: str,
    actor_id: uuid.UUID | None,
    reason: str,
    payload: dict[str, Any] | None = None,
) -> PlatformJob:
    row = PlatformJob(
        organization_id=org_id,
        job_type=job_type,
        status="queued",
        reason=reason,
        created_by_user_id=actor_id,
        payload_json=payload or {},
    )
    db.session.add(row)
    db.session.flush()
    return row


def _org_or_404(tenant_id: str) -> Organization:
    tid = _parse_uuid(tenant_id)
    if tid is None:
        raise SaasError("invalid tenant id", 400)
    with include_all_orgs():
        org = db.session.get(Organization, tid)
    if org is None:
        raise SaasError("tenant not found", 404)
    return org


def plan_module_for_path(path: str) -> str | None:
    p = path or ""
    if p.startswith("/api/public/") or p.startswith("/public/"):
        return None
    if "/spec-scan" in p or p.endswith("/spec-book/import") or "/spec-trade-map" in p:
        return "spec_split"
    for prefix, module in PLAN_STAFF_PATHS:
        if p.startswith(prefix):
            return module
    return None


# ---- contractor: money / workflows extras ---------------------------------


@settings_bp.post("/money")
def settings_money_save():
    try:
        cu = current_user_admin()
        oid = require_company_admin(cu, write=True)
    except SaasError as exc:
        return _json({"error": exc.message}, exc.status)
    body = request.get_json(silent=True) or {}
    if not isinstance(body, dict):
        return _json({"error": "JSON body required"}, 400)
    if "po.skip_down" in body:
        return _json({"error": LOCKED_MESSAGE, "key": "po.skip_down"}, 403)
    items = []
    try:
        for key in MONEY_KEYS:
            if key not in body:
                continue
            items.append(_put_setting(oid, key, body.get(key), cu.id, commit=False, publish_po=False))
        _publish_po_bands(oid)
        db.session.commit()
    except SaasError as exc:
        db.session.rollback()
        return _json({"error": exc.message}, exc.status)
    except Exception:
        db.session.rollback()
        current_app.logger.exception("money save failed")
        return _json({"error": "Could not save spend bands"}, 500)
    return _json({"entity": "money", "items": items})


def current_user_admin():
    from ._perms import current_user

    return current_user()


@settings_bp.get("/tokens")
def settings_tokens():
    try:
        cu = current_user_admin()
        oid = require_company_admin(cu)
    except SaasError as exc:
        return _json({"error": exc.message}, exc.status)
    items: list[dict[str, Any]] = []
    try:
        from ..models import Rfp

        rows = db.session.scalars(select(Rfp).order_by(Rfp.created_at.desc()).limit(200)).all()
        for r in rows:
            items.append(
                {
                    "id": f"rfp:{r.id}",
                    "kind": "rfp",
                    "type": "rfp",
                    "project_id": str(r.project_id) if r.project_id else None,
                    "title": r.title,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                    "expires_at": None,
                    "revoked": not bool(r.public_token),
                }
            )
    except Exception:
        db.session.rollback()
    try:
        from ..models.hiring import HirePacket

        rows = db.session.scalars(
            select(HirePacket).where(HirePacket.public_token_hash.is_not(None)).order_by(HirePacket.created_at.desc()).limit(200)
        ).all()
        for r in rows:
            items.append(
                {
                    "id": f"hire:{r.id}",
                    "kind": "hire",
                    "type": "hire",
                    "project_id": None,
                    "title": getattr(r, "job_title", None) or "Hire packet",
                    "created_at": r.created_at.isoformat() if getattr(r, "created_at", None) else None,
                    "expires_at": None,
                    "revoked": False,
                }
            )
    except Exception:
        db.session.rollback()
    try:
        from ..models import Submittal

        rows = db.session.scalars(
            select(Submittal).where(Submittal.public_token.is_not(None)).order_by(Submittal.created_at.desc()).limit(100)
        ).all()
        for r in rows:
            items.append(
                {
                    "id": f"submittal:{r.id}",
                    "kind": "submittal",
                    "type": "submittal",
                    "project_id": str(r.project_id) if getattr(r, "project_id", None) else None,
                    "title": getattr(r, "title", None) or "Submittal",
                    "created_at": r.created_at.isoformat() if getattr(r, "created_at", None) else None,
                    "expires_at": r.public_token_expires_at.isoformat() if getattr(r, "public_token_expires_at", None) else None,
                    "revoked": False,
                }
            )
    except Exception:
        db.session.rollback()
    return _json({"entity": "tokens", "tenant_id": str(oid), "items": items})


@settings_bp.post("/tokens/<token_id>/revoke")
def settings_token_revoke(token_id: str):
    try:
        cu = current_user_admin()
        oid = require_company_admin(cu, write=True)
    except SaasError as exc:
        return _json({"error": exc.message}, exc.status)
    kind, _, raw = (token_id or "").partition(":")
    uid = _parse_uuid(raw)
    if uid is None:
        return _json({"error": "invalid token id"}, 400)
    try:
        if kind == "rfp":
            from ..models import Rfp

            row = db.session.get(Rfp, uid)
            if row is None:
                return _json({"error": "token not found"}, 404)
            row.public_token = secrets.token_urlsafe(32)[:64]
        elif kind == "hire":
            from ..models.hiring import HirePacket

            row = db.session.get(HirePacket, uid)
            if row is None:
                return _json({"error": "token not found"}, 404)
            row.public_token_hash = None
        elif kind == "submittal":
            from ..models import Submittal

            row = db.session.get(Submittal, uid)
            if row is None:
                return _json({"error": "token not found"}, 404)
            row.public_token = None
            row.public_token_expires_at = None
        else:
            return _json({"error": "unknown token type"}, 400)
        write_platform_audit(
            action="token.revoke",
            actor_user_id=cu.id,
            organization_id=oid,
            after={"token_id": token_id},
        )
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("token revoke failed")
        return _json({"error": "Could not revoke token"}, 500)
    return _json({"entity": "token", "revoked": True, "id": token_id})


@settings_bp.post("/mail/test")
def settings_mail_test():
    try:
        cu = current_user_admin()
        oid = require_company_admin(cu, write=True)
    except SaasError as exc:
        return _json({"error": exc.message}, exc.status)
    to = (cu.email or "").strip()
    if not to or "@" not in to:
        return _json({"error": "Signed-in user has no email"}, 400)
    from ._notifications import send_plain_notification_email

    mail = send_plain_notification_email(
        to=to,
        subject="USIS mail test",
        body="This is a Settings → Mail test send. It is addressed only to the signed-in Company Admin.",
        from_addr=str(tenant_setting(oid, "mail.rfp.from_address") or "quotes@gousis.com"),
    )
    write_platform_audit(
        action="mail.test",
        actor_user_id=cu.id,
        organization_id=oid,
        after={"to": to, "queued": mail.get("queued"), "dry_run": mail.get("dry_run")},
    )
    db.session.commit()
    return _json({"entity": "mail_test", "to": to, **mail})


@settings_bp.get("/mail/preview")
def settings_mail_preview():
    try:
        require_company_admin(current_user_admin())
    except SaasError as exc:
        return _json({"error": exc.message}, exc.status)
    html = (
        "<div style='font-family:Segoe UI,Arial,sans-serif;max-width:640px'>"
        "<p>Hello Vendor,</p>"
        "<p>Please submit your quote for <strong>Sample RFP — Drywall Package</strong> (due 2026-10-01).</p>"
        "<p>Portal: <a href='#'>/public/rfp/…demo</a></p>"
        "<p style='color:#666;font-size:12px'>Dummy preview. Existing RFP Jinja2 template is used on live send.</p>"
        "</div>"
    )
    return _json({"entity": "mail_preview", "html": html, "subject": "[RFP DEMO] Sample RFP — Drywall Package"})


@settings_bp.post("/mail/domains")
def settings_mail_domain_request():
    try:
        cu = current_user_admin()
        oid = require_company_admin(cu, write=True)
    except SaasError as exc:
        return _json({"error": exc.message}, exc.status)
    body = request.get_json(silent=True) or {}
    domain = str(body.get("domain") or "").strip().lower().lstrip("@")
    if "." not in domain or " " in domain:
        return _json({"error": "valid domain required"}, 400)
    with include_all_orgs():
        row = db.session.scalar(
            select(OrganizationSendDomain).where(
                OrganizationSendDomain.organization_id == oid,
                OrganizationSendDomain.domain == domain,
            )
        )
        if row is None:
            row = OrganizationSendDomain(
                organization_id=oid,
                domain=domain,
                status="pending",
                requested_by_user_id=cu.id,
            )
            db.session.add(row)
        elif row.status == "revoked":
            row.status = "pending"
            row.requested_by_user_id = cu.id
        write_platform_audit(
            action="send_domain.request",
            actor_user_id=cu.id,
            organization_id=oid,
            after={"domain": domain, "status": row.status},
        )
        db.session.commit()
    return _json({"entity": "send_domain", "item": {"domain": row.domain, "status": row.status}}, 201)


@settings_bp.get("/mail/domains")
def settings_mail_domains():
    try:
        cu = current_user_admin()
        oid = require_company_admin(cu)
    except SaasError as exc:
        return _json({"error": exc.message}, exc.status)
    with include_all_orgs():
        rows = db.session.scalars(
            select(OrganizationSendDomain)
            .where(OrganizationSendDomain.organization_id == oid)
            .order_by(OrganizationSendDomain.domain)
        ).all()
    items = [{"id": str(r.id), "domain": r.domain, "status": r.status} for r in rows]
    return _json(
        {
            "entity": "send_domains",
            "approved": list(live_send_domains(oid)),
            "items": items,
        }
    )


@settings_bp.get("/devices")
def settings_devices():
    try:
        cu = current_user_admin()
        oid = require_company_admin(cu)
    except SaasError as exc:
        return _json({"error": exc.message}, exc.status)
    member_ids = select(OrgMember.user_id).where(OrgMember.organization_id == oid)
    rows = db.session.scalars(
        select(MobileRefreshToken)
        .where(
            MobileRefreshToken.user_id.in_(member_ids),
            MobileRefreshToken.revoked_at.is_(None),
        )
        .order_by(MobileRefreshToken.created_at.desc())
        .limit(300)
    ).all()
    users = {u.id: u for u in db.session.scalars(select(User).where(User.id.in_([r.user_id for r in rows]))).all()}
    items = []
    for r in rows:
        u = users.get(r.user_id)
        items.append(
            {
                "id": str(r.id),
                "name": r.device_label or "Field device",
                "user_email": u.email if u else None,
                "last_seen": r.created_at.isoformat() if r.created_at else None,
                "app_version": None,
            }
        )
    return _json({"entity": "devices", "items": items})


@settings_bp.post("/devices/<device_id>/revoke")
def settings_device_revoke(device_id: str):
    try:
        cu = current_user_admin()
        oid = require_company_admin(cu, write=True)
    except SaasError as exc:
        return _json({"error": exc.message}, exc.status)
    did = _parse_uuid(device_id)
    if did is None:
        return _json({"error": "invalid device id"}, 400)
    member_ids = select(OrgMember.user_id).where(OrgMember.organization_id == oid)
    row = db.session.scalar(
        select(MobileRefreshToken).where(
            MobileRefreshToken.id == did,
            MobileRefreshToken.user_id.in_(member_ids),
        )
    )
    if row is None:
        return _json({"error": "device not found"}, 404)
    row.revoked_at = _utcnow()
    write_platform_audit(
        action="device.revoke",
        actor_user_id=cu.id,
        organization_id=oid,
        after={"device_id": str(row.id)},
    )
    db.session.commit()
    return _json({"entity": "device", "revoked": True})


@settings_bp.get("/integrations")
def settings_integrations():
    try:
        require_company_admin(current_user_admin())
    except SaasError as exc:
        return _json({"error": exc.message}, exc.status)
    items = _health_checks()
    try:
        from ..ai import local as local_ai

        st = local_ai.status_public() if hasattr(local_ai, "status_public") else None
        if isinstance(st, dict):
            items["local_llama"] = {"status": st.get("status") or "warn", "detail": st.get("detail") or ""}
    except Exception:
        try:
            import httpx

            from flask import current_app as app

            url = (app.config.get("AI_LOCAL_ENDPOINT") or tenant_setting(None, "ai.local_endpoint") or "").rstrip("/")
            if url:
                with httpx.Client(timeout=2.0) as client:
                    r = client.get(url + "/health")
                items["local_llama"] = {"status": "ok" if r.status_code < 400 else "fail", "detail": f"HTTP {r.status_code}"}
            else:
                items["local_llama"] = {"status": "warn", "detail": "no local endpoint"}
        except Exception as exc:
            items["local_llama"] = {"status": "fail", "detail": str(exc)[:160]}
    items.setdefault("grok", items.get("ai") or {"status": "warn", "detail": "see ai"})
    items.setdefault("m365", {"status": "warn", "detail": "manage in Correspondence"})
    items.setdefault("teams", {"status": "warn", "detail": "off until connector is healthy"})
    items.setdefault("qbwc", {"status": "warn", "detail": tenant_setting(None, "qb.company_file_name") or "set company file"})
    return _json({"entity": "integrations", "items": items})


@settings_bp.get("/audit.csv")
def settings_audit_csv():
    try:
        cu = current_user_admin()
        oid = require_company_admin(cu)
    except SaasError as exc:
        return _json({"error": exc.message}, exc.status)
    rows = db.session.scalars(
        select(PlatformAudit)
        .where(PlatformAudit.organization_id == oid)
        .order_by(PlatformAudit.created_at.desc())
        .limit(1000)
    ).all()
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["when", "action", "reason", "actor_user_id"])
    for r in rows:
        w.writerow([r.created_at.isoformat() if r.created_at else "", r.action, r.reason or "", r.actor_user_id or ""])
    return Response(buf.getvalue(), mimetype="text/csv", headers={"Content-Disposition": "attachment; filename=settings-audit.csv"})


# ---- platform --------------------------------------------------------------


@admin_bp.put("/plans/<plan_key>")
def admin_put_plan(plan_key: str):
    try:
        op = require_platform_operator(current_user_admin())
    except SaasError as exc:
        return _json({"error": exc.message}, exc.status)
    body = request.get_json(silent=True) or {}
    modules = body.get("modules")
    if not isinstance(modules, list):
        return _json({"error": "modules array required"}, 400)
    try:
        saved = set_plan_default_modules(plan_key, modules)
    except ValueError as exc:
        return _json({"error": str(exc)}, 400)
    write_platform_audit(
        action="plan.update",
        actor_user_id=op.id,
        after={"plan_key": plan_key, "modules": sorted(saved)},
    )
    db.session.commit()
    return _json({"entity": "plan", "plan_key": plan_key, "modules": sorted(saved)})


@admin_bp.get("/operators")
def admin_operators():
    try:
        require_platform_operator(current_user_admin())
    except SaasError as exc:
        return _json({"error": exc.message}, exc.status)
    with include_all_orgs():
        rows = db.session.scalars(select(User).where(User.is_platform_operator.is_(True)).order_by(User.email)).all()
    items = [
        {
            "id": str(u.id),
            "email": u.email,
            "name": " ".join(p for p in (u.first_name, u.last_name) if p).strip() or u.email,
            "is_active": bool(u.is_active),
        }
        for u in rows
    ]
    return _json({"entity": "operators", "items": items})


@admin_bp.post("/operators")
def admin_add_operator():
    try:
        op = require_platform_operator(current_user_admin())
    except SaasError as exc:
        return _json({"error": exc.message}, exc.status)
    body = request.get_json(silent=True) or {}
    email = str(body.get("email") or "").strip().lower()
    uid = _parse_uuid(body.get("user_id"))
    with include_all_orgs():
        user = db.session.get(User, uid) if uid else None
        if user is None and email:
            user = db.session.scalar(select(User).where(func.lower(User.email) == email))
        if user is None:
            return _json({"error": "user not found"}, 404)
        user.is_platform_operator = True
        write_platform_audit(
            action="operator.add",
            actor_user_id=op.id,
            after={"user_id": str(user.id), "email": user.email},
        )
        db.session.commit()
    return _json({"entity": "operator", "item": {"id": str(user.id), "email": user.email}})


@admin_bp.delete("/operators/<user_id>")
def admin_remove_operator(user_id: str):
    try:
        op = require_platform_operator(current_user_admin())
    except SaasError as exc:
        return _json({"error": exc.message}, exc.status)
    uid = _parse_uuid(user_id)
    if uid is None:
        return _json({"error": "invalid user id"}, 400)
    with include_all_orgs():
        remaining = db.session.scalar(
            select(func.count()).select_from(User).where(User.is_platform_operator.is_(True), User.is_active.is_(True))
        ) or 0
        user = db.session.get(User, uid)
        if user is None or not user.is_platform_operator:
            return _json({"error": "operator not found"}, 404)
        if int(remaining) <= 1:
            return _json({"error": "Cannot remove the last platform operator."}, 400)
        user.is_platform_operator = False
        write_platform_audit(
            action="operator.remove",
            actor_user_id=op.id,
            after={"user_id": str(user.id)},
        )
        db.session.commit()
    return _json({"entity": "operator", "removed": True})


@admin_bp.post("/organizations/<tenant_id>/suspend")
def admin_org_suspend(tenant_id: str):
    return _set_org_status(tenant_id, "suspended")


@admin_bp.post("/organizations/<tenant_id>/reactivate")
def admin_org_reactivate(tenant_id: str):
    return _set_org_status(tenant_id, "active")


@admin_bp.post("/organizations/<tenant_id>/close")
def admin_org_close(tenant_id: str):
    body = request.get_json(silent=True) or {}
    if str(body.get("confirm") or body.get("type") or "").strip().upper() != "CLOSE":
        return _json({"error": "type CLOSE is required"}, 400)
    return _set_org_status(tenant_id, "closed")


def _set_org_status(tenant_id: str, status: str):
    try:
        op = require_platform_operator(current_user_admin())
        body = request.get_json(silent=True) or {}
        reason = _reason(body) if status in ("suspended", "closed") else str(body.get("reason") or "reactivated from admin")
        org = _org_or_404(tenant_id)
        before = org.status
        org.status = status
        write_platform_audit(
            action=f"tenant.{status}",
            actor_user_id=op.id,
            organization_id=org.id,
            reason=reason,
            before=before,
            after=status,
        )
        db.session.commit()
    except SaasError as exc:
        db.session.rollback()
        return _json({"error": exc.message}, exc.status)
    return _json({"entity": "tenant", "item": _tenant_public(org, extra=True)})


@admin_bp.post("/organizations/<tenant_id>/export")
def admin_org_export(tenant_id: str):
    try:
        op = require_platform_operator(current_user_admin())
        org = _org_or_404(tenant_id)
        reason = str((request.get_json(silent=True) or {}).get("reason") or "queue export").strip()
        job = _queue_job(org_id=org.id, job_type="export", actor_id=op.id, reason=reason)
        write_platform_audit(action="tenant.export", actor_user_id=op.id, organization_id=org.id, after={"job_id": str(job.id)})
        db.session.commit()
    except SaasError as exc:
        db.session.rollback()
        return _json({"error": exc.message}, exc.status)
    return _json({"entity": "tenant_export", "queued": True, "job_id": str(job.id)})


@admin_bp.post("/organizations/<tenant_id>/wipe")
def admin_org_wipe(tenant_id: str):
    try:
        op = require_platform_operator(current_user_admin())
        body = request.get_json(silent=True) or {}
        reason = _reason(body)
        org = _org_or_404(tenant_id)
        job = _queue_job(org_id=org.id, job_type="wipe", actor_id=op.id, reason=reason)
        write_platform_audit(action="tenant.wipe", actor_user_id=op.id, organization_id=org.id, reason=reason, after={"job_id": str(job.id)})
        db.session.commit()
    except SaasError as exc:
        db.session.rollback()
        return _json({"error": exc.message}, exc.status)
    return _json({"entity": "tenant_wipe", "queued": True, "job_id": str(job.id)})


@admin_bp.post("/organizations/<tenant_id>/notes")
def admin_org_note(tenant_id: str):
    try:
        op = require_platform_operator(current_user_admin())
        org = _org_or_404(tenant_id)
        body = request.get_json(silent=True) or {}
        text = str(body.get("body") or body.get("note") or "").strip()
        if len(text) < 2:
            return _json({"error": "note body required"}, 400)
        row = OrganizationNote(organization_id=org.id, actor_user_id=op.id, body=text[:8000])
        db.session.add(row)
        write_platform_audit(action="tenant.note", actor_user_id=op.id, organization_id=org.id)
        db.session.commit()
    except SaasError as exc:
        db.session.rollback()
        return _json({"error": exc.message}, exc.status)
    return _json({"entity": "note", "item": {"id": str(row.id), "body": row.body, "created_at": row.created_at.isoformat()}}, 201)


@admin_bp.get("/organizations/<tenant_id>/notes")
def admin_org_notes(tenant_id: str):
    try:
        require_platform_operator(current_user_admin())
        org = _org_or_404(tenant_id)
    except SaasError as exc:
        return _json({"error": exc.message}, exc.status)
    with include_all_orgs():
        rows = db.session.scalars(
            select(OrganizationNote)
            .where(OrganizationNote.organization_id == org.id)
            .order_by(OrganizationNote.created_at.desc())
            .limit(100)
        ).all()
    return _json(
        {
            "entity": "notes",
            "items": [
                {
                    "id": str(r.id),
                    "body": r.body,
                    "actor_user_id": str(r.actor_user_id) if r.actor_user_id else None,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
                for r in rows
            ],
        }
    )


@admin_bp.post("/organizations/<tenant_id>/overage")
def admin_org_overage(tenant_id: str):
    try:
        op = require_platform_operator(current_user_admin())
        org = _org_or_404(tenant_id)
        body = request.get_json(silent=True) or {}
        reason = _reason(body)
        kind = str(body.get("seat_kind") or "office").strip().lower()
        if kind not in ("office", "field"):
            kind = "office"
        expires_raw = str(body.get("expires_at") or "").strip()
        try:
            expires = datetime.fromisoformat(expires_raw.replace("Z", "+00:00"))
        except ValueError:
            return _json({"error": "expires_at ISO datetime required"}, 400)
        row = OrganizationSeatOverage(
            organization_id=org.id,
            seat_kind=kind,
            reason=reason,
            expires_at=expires,
            created_by_user_id=op.id,
        )
        db.session.add(row)
        write_platform_audit(
            action="tenant.overage",
            actor_user_id=op.id,
            organization_id=org.id,
            reason=reason,
            after={"seat_kind": kind, "expires_at": expires.isoformat()},
        )
        db.session.commit()
    except SaasError as exc:
        db.session.rollback()
        return _json({"error": exc.message}, exc.status)
    return _json({"entity": "overage", "item": {"id": str(row.id), "seat_kind": kind, "expires_at": expires.isoformat()}}, 201)


@admin_bp.post("/organizations/<tenant_id>/send-domains")
def admin_org_send_domain(tenant_id: str):
    try:
        op = require_platform_operator(current_user_admin())
        org = _org_or_404(tenant_id)
        body = request.get_json(silent=True) or {}
        domain = str(body.get("domain") or "").strip().lower().lstrip("@")
        status = str(body.get("status") or "live").strip().lower()
        if status not in ("pending", "live", "revoked"):
            return _json({"error": "invalid status"}, 400)
        if "." not in domain:
            return _json({"error": "valid domain required"}, 400)
        with include_all_orgs():
            row = db.session.scalar(
                select(OrganizationSendDomain).where(
                    OrganizationSendDomain.organization_id == org.id,
                    OrganizationSendDomain.domain == domain,
                )
            )
            if row is None:
                row = OrganizationSendDomain(organization_id=org.id, domain=domain, status=status)
                db.session.add(row)
            row.status = status
            row.reviewed_by_user_id = op.id
            row.reviewed_at = _utcnow()
        write_platform_audit(
            action="send_domain.set",
            actor_user_id=op.id,
            organization_id=org.id,
            after={"domain": domain, "status": status},
        )
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return _json({"error": "domain already exists"}, 409)
    except SaasError as exc:
        db.session.rollback()
        return _json({"error": exc.message}, exc.status)
    return _json({"entity": "send_domain", "item": {"domain": domain, "status": status}})


@admin_bp.get("/flags/matrix")
def admin_flags_matrix():
    try:
        require_platform_operator(current_user_admin())
    except SaasError as exc:
        return _json({"error": exc.message}, exc.status)
    keys = list(FEATURE_FLAG_CATALOG.keys())
    with include_all_orgs():
        orgs = db.session.scalars(select(Organization).order_by(Organization.name)).all()
        extras = db.session.scalars(select(FeatureFlag).where(FeatureFlag.organization_id.is_(None))).all()
    for row in extras:
        if row.key not in keys:
            keys.append(row.key)
    defaults = {k: feature_flag_on(k, None) for k in keys}
    cells = []
    for org in orgs:
        row = {"tenant_id": str(org.id), "slug": org.slug, "name": org.legal_name or org.name, "flags": {}}
        for k in keys:
            row["flags"][k] = feature_flag_on(k, org.id)
        cells.append(row)
    return _json({"entity": "flags_matrix", "keys": keys, "defaults": defaults, "organizations": cells})


@admin_bp.get("/impersonate/sessions")
def admin_impersonate_sessions():
    try:
        require_platform_operator(current_user_admin())
    except SaasError as exc:
        return _json({"error": exc.message}, exc.status)
    from ..models.saas import ImpersonationSession

    with include_all_orgs():
        rows = db.session.scalars(
            select(ImpersonationSession).where(ImpersonationSession.ended_at.is_(None)).order_by(ImpersonationSession.started_at.desc())
        ).all()
        orgs = {o.id: o for o in db.session.scalars(select(Organization)).all()}
        users = {u.id: u for u in db.session.scalars(select(User).where(User.id.in_([r.operator_user_id for r in rows] + [r.target_user_id for r in rows if r.target_user_id]))).all()}
    items = []
    for r in rows:
        org = orgs.get(r.organization_id)
        op = users.get(r.operator_user_id)
        tgt = users.get(r.target_user_id) if r.target_user_id else None
        items.append(
            {
                "id": str(r.id),
                "tenant_id": str(r.organization_id),
                "tenant_name": (org.legal_name or org.name) if org else None,
                "operator_email": op.email if op else None,
                "target_email": tgt.email if tgt else None,
                "reason": r.reason,
                "started_at": r.started_at.isoformat() if r.started_at else None,
            }
        )
    return _json({"entity": "impersonation_sessions", "items": items})


@admin_bp.post("/impersonate/<session_id>/end")
def admin_force_end_impersonation(session_id: str):
    try:
        op = require_platform_operator(current_user_admin())
    except SaasError as exc:
        return _json({"error": exc.message}, exc.status)
    sid = _parse_uuid(session_id)
    if sid is None:
        return _json({"error": "invalid session id"}, 400)
    from ..models.saas import ImpersonationSession

    with include_all_orgs():
        row = db.session.get(ImpersonationSession, sid)
        if row is None:
            return _json({"error": "session not found"}, 404)
        row.ended_at = _utcnow()
        write_platform_audit(
            action="impersonate.force_end",
            actor_user_id=op.id,
            organization_id=row.organization_id,
            after={"impersonation_id": str(row.id)},
        )
        db.session.commit()
    return _json({"entity": "impersonation", "ended": True})


@admin_bp.get("/usage/meters")
def admin_usage_meters():
    try:
        require_platform_operator(current_user_admin())
    except SaasError as exc:
        return _json({"error": exc.message}, exc.status)
    meters = {
        "storage_gb": {"value": None, "label": "not metered yet"},
        "b2_egress": {"value": None, "label": "not metered yet"},
        "ai_calls_7d": {"value": None, "label": "not metered yet"},
        "ai_calls_30d": {"value": None, "label": "not metered yet"},
        "email_sends": {"value": None, "label": "not metered yet"},
        "public_token_hits": {"value": None, "label": "not metered yet"},
    }
    return _json({"entity": "usage_meters", "items": meters, "health": _health_checks()})


@admin_bp.get("/audit.csv")
def admin_audit_csv():
    try:
        require_platform_operator(current_user_admin())
    except SaasError as exc:
        return _json({"error": exc.message}, exc.status)
    stmt = select(PlatformAudit).order_by(PlatformAudit.created_at.desc()).limit(2000)
    tid = _parse_uuid(request.args.get("tenant_id"))
    if tid is not None:
        stmt = stmt.where(PlatformAudit.organization_id == tid)
    with include_all_orgs():
        rows = db.session.scalars(stmt).all()
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["when", "action", "tenant_id", "reason", "actor_user_id"])
    for r in rows:
        w.writerow(
            [
                r.created_at.isoformat() if r.created_at else "",
                r.action,
                r.organization_id or "",
                r.reason or "",
                r.actor_user_id or "",
            ]
        )
    return Response(buf.getvalue(), mimetype="text/csv", headers={"Content-Disposition": "attachment; filename=platform-audit.csv"})
