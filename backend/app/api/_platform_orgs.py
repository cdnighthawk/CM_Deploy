"""Platform-only organization provisioning (invite-only SaaS onboarding)."""
from __future__ import annotations

import uuid
from typing import Any

from flask import current_app, request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from ..extensions import db
from ..models import User
from ..models.organization import ORG_ROLE_OWNER, Organization
from ..services.password_reset import issue_set_password_token
from ..tenancy import (
    add_member,
    include_all_orgs,
    organization_public,
    provision_organization,
)
from ._integration_bc import buildingconnected_status_public
from ._perms import CurrentUser, current_user


class PlatformError(Exception):
    def __init__(self, message: str, status: int = 400):
        self.message = message
        self.status = status


def _require_platform(cu: CurrentUser) -> None:
    if cu.user is None or not cu.user.is_superuser:
        raise PlatformError("platform administrator required", 403)


def _jsonify(obj: Any, status: int = 200):
    from flask import jsonify

    return jsonify(obj), status


def _organization_setup_public(org: Organization) -> dict:
    item = organization_public(org)
    item["buildingconnected"] = buildingconnected_status_public(org.id)
    return item


def list_organizations(cu: CurrentUser) -> tuple[Any, int]:
    _require_platform(cu)
    with include_all_orgs():
        rows = db.session.scalars(select(Organization).order_by(Organization.name.asc())).all()
        items = [_organization_setup_public(o) for o in rows]
    return _jsonify(
        {
            "entity": "organizations",
            "items": items,
        }
    )


def create_organization(cu: CurrentUser, data: dict[str, Any]) -> tuple[Any, int]:
    _require_platform(cu)
    if not isinstance(data, dict):
        raise PlatformError("JSON body required")
    name = str(data.get("name") or "").strip()
    if not name:
        raise PlatformError("name is required")
    copy_catalog = data.get("copy_catalog")
    if copy_catalog is None:
        copy_catalog = True
    org = provision_organization(name=name, copy_catalog=bool(copy_catalog))
    db.session.commit()
    return _jsonify({"entity": "organization", "item": _organization_setup_public(org)}, 201)


def invite_organization_admin(cu: CurrentUser, org_id: uuid.UUID, data: dict[str, Any]) -> tuple[Any, int]:
    _require_platform(cu)
    if not isinstance(data, dict):
        raise PlatformError("JSON body required")
    email = str(data.get("email") or "").strip().lower()
    if not email or "@" not in email:
        raise PlatformError("email is required")
    first = str(data.get("first_name") or "").strip()[:120] or None
    last = str(data.get("last_name") or "").strip()[:120] or None
    with include_all_orgs():
        org = db.session.get(Organization, org_id)
        if org is None:
            raise PlatformError("organization not found", 404)
        u = db.session.scalar(select(User).where(User.email == email))
        created = False
        if u is None:
            u = User(
                email=email,
                first_name=first,
                last_name=last,
                is_active=True,
                is_superuser=False,
                password_hash=None,
            )
            db.session.add(u)
            db.session.flush()
            created = True
        add_member(u.id, org.id, ORG_ROLE_OWNER)
        raw = issue_set_password_token(u)
        from ._notifications import send_password_reset_email

        mail = send_password_reset_email(to=u.email, reset_token=raw)
        db.session.commit()
    return _jsonify(
        {
            "entity": "organization_invite",
            "ok": True,
            "user_id": str(u.id),
            "organization_id": str(org.id),
            "created_user": created,
            "email_sent": bool(mail.get("sent")),
            "dry_run": bool(mail.get("dry_run")),
        },
        201,
    )


def register_platform_org_routes(bp) -> None:
    @bp.get("/platform/organizations")
    def platform_list_organizations():
        try:
            return list_organizations(current_user())
        except PlatformError as exc:
            return _jsonify({"error": exc.message}, exc.status)

    @bp.post("/platform/organizations")
    def platform_create_organization():
        try:
            return create_organization(current_user(), request.get_json(silent=True) or {})
        except PlatformError as exc:
            return _jsonify({"error": exc.message}, exc.status)
        except IntegrityError:
            db.session.rollback()
            return _jsonify({"error": "A contractor with that name already exists."}, 409)
        except SQLAlchemyError:
            db.session.rollback()
            current_app.logger.exception("platform create organization failed")
            return _jsonify(
                {"error": "Could not create contractor. Uncheck Copy catalog and retry, or try again."},
                500,
            )

    @bp.post("/platform/organizations/<org_id>/invites")
    def platform_invite(org_id: str):
        try:
            oid = uuid.UUID(str(org_id).strip())
        except (TypeError, ValueError):
            return _jsonify({"error": "invalid organization id"}, 400)
        try:
            return invite_organization_admin(current_user(), oid, request.get_json(silent=True) or {})
        except PlatformError as exc:
            return _jsonify({"error": exc.message}, exc.status)

    @bp.post("/organizations")
    def self_serve_organization():
        if not current_app.config.get("USIS_ALLOW_COMPANY_SELF_SIGNUP"):
            return _jsonify({"error": "company self-signup is disabled"}, 403)
        cu = current_user()
        if cu.user is None:
            return _jsonify({"error": "authentication required"}, 401)
        body = request.get_json(silent=True) or {}
        name = str(body.get("name") or "").strip()
        if not name:
            return _jsonify({"error": "name is required"}, 400)
        org = provision_organization(name=name, copy_catalog=True)
        add_member(cu.user.id, org.id, ORG_ROLE_OWNER)
        db.session.commit()
        from ..tenancy import set_current_organization_id

        set_current_organization_id(org.id)
        return _jsonify({"entity": "organization", "item": organization_public(org)}, 201)
