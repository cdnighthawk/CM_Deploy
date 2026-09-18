"""Request-scoped organization (SaaS tenant) context and query isolation."""
from __future__ import annotations

import uuid
from contextlib import contextmanager
from typing import Any, Iterator, Optional

from flask import g, has_app_context, has_request_context, session
from sqlalchemy import event, inspect as sa_inspect, select
from sqlalchemy.orm import ORMExecuteState, Session, with_loader_criteria

from .extensions import db
from .models.base import TenantMixin
from .models.organization import (
    ORG_ROLE_MEMBER,
    ORG_ROLE_OWNER,
    Organization,
    OrganizationMember,
    USIS_ORG_SLUG,
)

SESSION_ORG_KEY = "organization_id"
INCLUDE_ALL_ORGS = "include_all_orgs"
G_ORG_KEY = "organization_id"
G_SKIP_FILTER = "_tenancy_skip_filter"

_LISTENERS_READY = False


def _parse_uuid(raw: Any) -> uuid.UUID | None:
    if raw is None:
        return None
    try:
        return uuid.UUID(str(raw).strip())
    except (TypeError, ValueError):
        return None


def skip_tenant_filter() -> bool:
    if has_request_context() and getattr(g, G_SKIP_FILTER, False):
        return True
    return False


@contextmanager
def include_all_orgs() -> Iterator[None]:
    """Disable auto tenant filters (platform org CRUD, migrations, backfill)."""
    if has_request_context():
        prev = getattr(g, G_SKIP_FILTER, False)
        setattr(g, G_SKIP_FILTER, True)
        try:
            yield
        finally:
            setattr(g, G_SKIP_FILTER, prev)
        return
    yield


def current_organization_id() -> uuid.UUID | None:
    if has_request_context():
        raw = getattr(g, G_ORG_KEY, None)
        parsed = _parse_uuid(raw)
        if parsed is not None:
            return parsed
    return None


def set_current_organization_id(org_id: uuid.UUID | None) -> None:
    if has_request_context():
        g.organization_id = org_id
    if has_request_context() and org_id is not None:
        session[SESSION_ORG_KEY] = str(org_id)
    elif has_request_context() and org_id is None:
        session.pop(SESSION_ORG_KEY, None)


def bind_request_organization(org_id: uuid.UUID | None) -> None:
    """Set this request's tenant without changing the login session (public tokens)."""
    if has_request_context() and org_id is not None:
        g.organization_id = org_id


def organization_public(org: Organization) -> dict[str, Any]:
    return {
        "id": str(org.id),
        "name": org.name,
        "slug": org.slug,
        "microsoft_sso_enabled": bool(org.microsoft_sso_enabled),
    }


def memberships_for_user(user_id: uuid.UUID) -> list[OrganizationMember]:
    with include_all_orgs():
        return list(
            db.session.scalars(
                select(OrganizationMember)
                .where(OrganizationMember.user_id == user_id)
                .order_by(OrganizationMember.created_at.asc())
            ).all()
        )


def organizations_for_user(user_id: uuid.UUID) -> list[Organization]:
    rows = memberships_for_user(user_id)
    out: list[Organization] = []
    with include_all_orgs():
        for row in rows:
            org = db.session.get(Organization, row.organization_id)
            if org is not None:
                out.append(org)
    return out


def user_is_member(user_id: uuid.UUID, org_id: uuid.UUID) -> bool:
    with include_all_orgs():
        row = db.session.get(OrganizationMember, (user_id, org_id))
        return row is not None


def ensure_usis_organization() -> Organization:
    """Idempotent USIS tenant used as org #1 and as the test/dev default."""
    from sqlalchemy.exc import SQLAlchemyError

    with include_all_orgs():
        try:
            org = db.session.scalar(select(Organization).where(Organization.slug == USIS_ORG_SLUG))
            if org is not None:
                return org
            org = Organization(
                name="US Interior Specialties",
                slug=USIS_ORG_SLUG,
                microsoft_sso_enabled=True,
                storage_prefix="",
            )
            db.session.add(org)
            db.session.flush()
            return org
        except SQLAlchemyError:
            db.session.rollback()
            raise


def default_organization_id() -> uuid.UUID | None:
    """USIS org when the request has no tenant yet (dev-open tests, first boot)."""
    try:
        return ensure_usis_organization().id
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass
        return None


def bind_organization_for_user(user_id: uuid.UUID, *, preferred: uuid.UUID | None = None) -> uuid.UUID | None:
    """Pick a current org for this user. None if they must choose among several."""
    orgs = organizations_for_user(user_id)
    if preferred is not None:
        if any(o.id == preferred for o in orgs):
            set_current_organization_id(preferred)
            return preferred
    if len(orgs) == 1:
        set_current_organization_id(orgs[0].id)
        return orgs[0].id
    if len(orgs) == 0:
        usis = ensure_usis_organization()
        db.session.add(
            OrganizationMember(
                user_id=user_id,
                organization_id=usis.id,
                org_role=ORG_ROLE_MEMBER,
            )
        )
        db.session.flush()
        set_current_organization_id(usis.id)
        return usis.id
    session_pref = None
    if has_request_context():
        session_pref = _parse_uuid(session.get(SESSION_ORG_KEY))
    if session_pref is not None and any(o.id == session_pref for o in orgs):
        set_current_organization_id(session_pref)
        return session_pref
    set_current_organization_id(None)
    return None


def entra_organization() -> Organization | None:
    with include_all_orgs():
        return db.session.scalar(
            select(Organization).where(
                Organization.microsoft_sso_enabled.is_(True),
                Organization.slug == USIS_ORG_SLUG,
            )
        ) or db.session.scalar(
            select(Organization).where(Organization.microsoft_sso_enabled.is_(True)).limit(1)
        )


def add_member(user_id: uuid.UUID, org_id: uuid.UUID, org_role: str = ORG_ROLE_MEMBER) -> OrganizationMember:
    with include_all_orgs():
        existing = db.session.get(OrganizationMember, (user_id, org_id))
        if existing is not None:
            return existing
        row = OrganizationMember(user_id=user_id, organization_id=org_id, org_role=org_role)
        db.session.add(row)
        db.session.flush()
        return row


def _target_org_id_for_insert() -> uuid.UUID | None:
    oid = current_organization_id()
    if oid is not None:
        return oid
    return default_organization_id()


def _is_tenant_instance(target: Any) -> bool:
    mapper = sa_inspect(target, raiseerr=False)
    if mapper is None:
        return False
    return "organization_id" in mapper.mapper.columns


@event.listens_for(Session, "do_orm_execute")
def _filter_tenant_selects(execute_state: ORMExecuteState) -> None:
    if not execute_state.is_select:
        return
    if execute_state.execution_options.get(INCLUDE_ALL_ORGS):
        return
    if skip_tenant_filter():
        return
    org_id = current_organization_id()
    if org_id is None:
        # Signed-in users who have not picked a company must not see a mix of tenants.
        logged_in = False
        if has_request_context():
            cu = getattr(g, "current_user", None)
            if cu is not None and getattr(cu, "user", None) is not None:
                logged_in = True
            elif session.get("user_id"):
                logged_in = True
        if not logged_in:
            return
        org_id = uuid.UUID("00000000-0000-0000-0000-000000000000")
    execute_state.statement = execute_state.statement.options(
        with_loader_criteria(
            TenantMixin,
            lambda cls: cls.organization_id == org_id,
            include_aliases=True,
        )
    )


@event.listens_for(Session, "before_flush")
def _stamp_tenant_on_insert(session: Session, flush_context, instances) -> None:  # noqa: ARG001
    if skip_tenant_filter():
        return
    org_id = _target_org_id_for_insert()
    if org_id is None:
        return
    for obj in session.new:
        if not _is_tenant_instance(obj):
            continue
        if getattr(obj, "organization_id", None) is None:
            obj.organization_id = org_id


def init_tenancy(app) -> None:
    """Register request hook so session/JWT org is on ``g`` before API work."""

    @app.before_request
    def _load_organization_context() -> None:
        if not has_request_context():
            return
        raw = session.get(SESSION_ORG_KEY) if session else None
        parsed = _parse_uuid(raw)
        if parsed is not None:
            g.organization_id = parsed


def storage_key_prefix_for_org(org: Organization | None) -> str:
    """B2 key prefix after env ``B2_PREFIX``. USIS omits extra segment (legacy keys)."""
    env_prefix = ""
    try:
        from flask import current_app

        env_prefix = (current_app.config.get("B2_PREFIX") or "").strip().strip("/")
    except Exception:
        env_prefix = ""
    if org is None:
        return env_prefix
    extra = (org.storage_prefix or "").strip().strip("/")
    if org.slug == USIS_ORG_SLUG or extra == "":
        if org.slug == USIS_ORG_SLUG:
            return env_prefix
    segment = extra or str(org.id)
    parts = [p for p in (env_prefix, segment) if p]
    return "/".join(parts)


def current_storage_prefix() -> str:
    org_id = current_organization_id()
    org = None
    if org_id is not None:
        with include_all_orgs():
            org = db.session.get(Organization, org_id)
    return storage_key_prefix_for_org(org)


def stored_key_allowed(object_key: str) -> bool:
    """True when this object key is in the current org's prefix space."""
    key = (object_key or "").replace("\\", "/").lstrip("/")
    org_id = current_organization_id()
    if org_id is None:
        return True
    with include_all_orgs():
        org = db.session.get(Organization, org_id)
    if org is None:
        return False
    prefix = storage_key_prefix_for_org(org).strip("/")
    if org.slug == USIS_ORG_SLUG:
        others = db.session.scalars(
            select(Organization.id).where(Organization.slug != USIS_ORG_SLUG)
        ).all()
        for oid in others:
            other_prefix = "/".join(p for p in (prefix, str(oid)) if p)
            if other_prefix and (key == other_prefix or key.startswith(other_prefix + "/")):
                return False
        return True
    if not prefix:
        return False
    return key == prefix or key.startswith(prefix + "/")


def copy_material_catalog(source_org_id: uuid.UUID, dest_org_id: uuid.UUID) -> int:
    """Copy SKU/CSI/labor units into dest; strip USIS ``cost``."""
    from .models.material_pricing import MaterialPrice

    count = 0
    with include_all_orgs():
        rows = db.session.scalars(
            select(MaterialPrice).where(MaterialPrice.organization_id == source_org_id)
        ).all()
        for src in rows:
            db.session.add(
                MaterialPrice(
                    organization_id=dest_org_id,
                    manufacturer=src.manufacturer,
                    item=src.item,
                    category=src.category,
                    csi_spec_section=src.csi_spec_section,
                    description=src.description,
                    mounting_type=src.mounting_type,
                    cost=None,
                    labor_per=src.labor_per,
                    labor_units_per_hour=src.labor_units_per_hour,
                    labor_rate_unit=src.labor_rate_unit,
                    size_width_in=src.size_width_in,
                    size_height_in=src.size_height_in,
                    currency=src.currency,
                    unit_of_measure=src.unit_of_measure,
                )
            )
            count += 1
        db.session.flush()
    return count


def slugify_org_name(name: str) -> str:
    import re

    base = re.sub(r"[^a-z0-9]+", "-", (name or "").strip().lower()).strip("-") or "org"
    slug = base[:80]
    with include_all_orgs():
        n = 1
        candidate = slug
        while db.session.scalar(select(Organization.id).where(Organization.slug == candidate)):
            n += 1
            suffix = f"-{n}"
            candidate = (slug[: 80 - len(suffix)] + suffix)
        return candidate


def provision_organization(*, name: str, copy_catalog: bool = True) -> Organization:
    from .models.company import Company

    usis = ensure_usis_organization()
    with include_all_orgs():
        org = Organization(
            name=(name or "").strip()[:255] or "New company",
            slug=slugify_org_name(name),
            microsoft_sso_enabled=False,
            storage_prefix=None,
        )
        db.session.add(org)
        db.session.flush()
        db.session.add(
            Company(
                organization_id=org.id,
                name=org.name,
                company_type="self",
                country="US",
            )
        )
        if copy_catalog:
            copy_material_catalog(usis.id, org.id)
        db.session.flush()
        return org
