"""SaaS admin: tenant settings helper, locked keys, /settings and /admin security."""
from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import OperationalError, ProgrammingError
from werkzeug.security import generate_password_hash

from app.extensions import db
from app.models import Role, User, UserRole
from app.models.organization import ORG_ROLE_ADMIN, ORG_ROLE_MEMBER, USIS_ORG_SLUG
from app.tenant_settings import (
    LOCKED_MESSAGE,
    LockedSettingError,
    list_tenant_settings,
    set_tenant_setting,
    tenant_setting,
)
from app.tenancy import add_member, ensure_usis_organization, provision_organization

REPO = Path(__file__).resolve().parents[2]
GULP = REPO / "W3CRM-v3.0-13_September_2025" / "gulp"


@pytest.fixture
def no_dev_admin(monkeypatch):
    monkeypatch.setenv("USIS_API_DEV_ALLOW_ANY", "0")
    monkeypatch.setenv("USIS_ALLOW_ACTOR_HEADER", "1")


def _skip_if_missing(flask_app) -> None:
    with flask_app.app_context():
        try:
            db.session.execute(text("SELECT 1 FROM tenant_settings LIMIT 1"))
            db.session.execute(text("SELECT is_platform_operator FROM users LIMIT 1"))
        except (OperationalError, ProgrammingError) as exc:
            pytest.skip(f"saas admin schema missing: {exc}")


def _login(client, email: str, password: str):
    r = client.post("/auth/login", data={"email": email, "password": password}, follow_redirects=False)
    assert r.status_code == 302, r.get_data(as_text=True)
    loc = r.headers.get("Location") or ""
    assert "login_error=" not in loc
    return r


def _user(email: str, *, operator=False, superuser=False, password="secret123"):
    u = User(
        email=email,
        first_name="T",
        last_name="User",
        is_active=True,
        is_superuser=superuser,
        is_platform_operator=operator,
        password_hash=generate_password_hash(password),
    )
    db.session.add(u)
    db.session.flush()
    return u


def _admin_role():
    role = db.session.scalar(select(Role).where(Role.code == "admin"))
    if role is None:
        role = Role(code="admin", name="Administrator")
        db.session.add(role)
        db.session.flush()
    return role


def test_src_pages_exist():
    src = GULP / "src"
    assert (src / "usis-settings.html").is_file()
    assert (src / "usis-admin.html").is_file()
    assert (src / "assets/js/usis-settings.js").is_file()
    assert (src / "assets/js/usis-admin.js").is_file()
    nav = (src / "elements/deznav-construction.html").read_text(encoding="utf-8")
    assert "usis-settings.html" in nav
    assert "usis-admin.html" in nav
    assert 'id="usis-platform-admin-nav"' in nav
    css = (src / "assets/css/usis-ui.css").read_text(encoding="utf-8")
    assert ".usis-impersonation-banner" in css


def test_helper_default_then_override(flask_app):
    _skip_if_missing(flask_app)
    with flask_app.app_context():
        org = ensure_usis_organization()
        assert tenant_setting(org.id, "mail.spam_confidence_move") == 0.90
        set_tenant_setting(org.id, "mail.spam_confidence_move", 0.95)
        db.session.commit()
        assert tenant_setting(org.id, "mail.spam_confidence_move") == 0.95
        vals = list_tenant_settings(org.id)
        assert vals["ai.dump_correspondence_to_grok"] is False


def test_locked_key_rejected_at_helper(flask_app):
    _skip_if_missing(flask_app)
    with flask_app.app_context():
        org = ensure_usis_organization()
        with pytest.raises(LockedSettingError) as exc:
            set_tenant_setting(org.id, "ai.dump_correspondence_to_grok", True)
        assert LOCKED_MESSAGE in str(exc.value)
        assert tenant_setting(org.id, "ai.dump_correspondence_to_grok") is False


def test_seed_tenant_exists(flask_app):
    _skip_if_missing(flask_app)
    with flask_app.app_context():
        org = ensure_usis_organization()
        assert org.slug == USIS_ORG_SLUG
        assert org.legal_name or org.name


def test_non_admin_settings_403(client, flask_app, no_dev_admin):
    _skip_if_missing(flask_app)
    with flask_app.app_context():
        org = ensure_usis_organization()
        u = _user("std_" + uuid.uuid4().hex[:8] + "@t.com")
        add_member(u.id, org.id, ORG_ROLE_MEMBER)
        db.session.commit()
        email = u.email
    _login(client, email, "secret123")
    r = client.get("/settings", headers={"Accept": "application/json"})
    assert r.status_code == 403
    r2 = client.get("/api/settings")
    assert r2.status_code == 403


def test_non_operator_admin_403(client, flask_app, no_dev_admin):
    _skip_if_missing(flask_app)
    with flask_app.app_context():
        org = ensure_usis_organization()
        role = _admin_role()
        u = _user("adm_" + uuid.uuid4().hex[:8] + "@t.com")
        add_member(u.id, org.id, ORG_ROLE_ADMIN)
        db.session.add(UserRole(user_id=u.id, role_id=role.id))
        db.session.commit()
        email = u.email
        uid = str(u.id)
    _login(client, email, "secret123")
    r = client.get("/admin", headers={"Accept": "application/json"})
    assert r.status_code == 403
    r2 = client.get("/api/admin/tenants", headers={"X-Usis-User-Id": uid})
    assert r2.status_code == 403


def test_tenant_a_cannot_put_tenant_b(client, flask_app, no_dev_admin):
    _skip_if_missing(flask_app)
    with flask_app.app_context():
        usis = ensure_usis_organization()
        other = provision_organization(name="Other Co " + uuid.uuid4().hex[:6])
        role = _admin_role()
        a = _user("a_" + uuid.uuid4().hex[:8] + "@t.com")
        add_member(a.id, usis.id, ORG_ROLE_ADMIN)
        db.session.add(UserRole(user_id=a.id, role_id=role.id))
        db.session.commit()
        email = a.email
        other_id = str(other.id)
    _login(client, email, "secret123")
    r = client.put(
        "/api/settings/company.legal_name",
        json={"value": "Hijack", "tenant_id": other_id},
    )
    assert r.status_code in (200, 400, 403)
    if r.status_code == 200:
        with flask_app.app_context():
            assert tenant_setting(uuid.UUID(other_id), "company.legal_name", None) not in ("Hijack",)


def test_locked_setting_put_403(client, flask_app, no_dev_admin):
    _skip_if_missing(flask_app)
    with flask_app.app_context():
        org = ensure_usis_organization()
        role = _admin_role()
        u = _user("lk_" + uuid.uuid4().hex[:8] + "@t.com")
        add_member(u.id, org.id, ORG_ROLE_ADMIN)
        db.session.add(UserRole(user_id=u.id, role_id=role.id))
        db.session.commit()
        email = u.email
    _login(client, email, "secret123")
    r = client.put("/api/settings/ai.dump_correspondence_to_grok", json={"value": True})
    assert r.status_code == 403
    assert LOCKED_MESSAGE in (r.get_json() or {}).get("error", "")


def test_impersonate_requires_reason_and_audits(client, flask_app, no_dev_admin):
    _skip_if_missing(flask_app)
    from app.models.saas import PlatformAudit

    with flask_app.app_context():
        org = ensure_usis_organization()
        op = _user("op_" + uuid.uuid4().hex[:8] + "@t.com", operator=True, superuser=True)
        add_member(op.id, org.id, ORG_ROLE_ADMIN)
        db.session.commit()
        email = op.email
        oid = str(org.id)
    _login(client, email, "secret123")
    bad = client.post("/api/admin/tenants/" + oid + "/impersonate", json={})
    assert bad.status_code == 400
    ok = client.post(
        "/api/admin/tenants/" + oid + "/impersonate",
        json={"reason": "investigating a billing ticket"},
    )
    assert ok.status_code == 200
    body = ok.get_json()
    assert body.get("banner") is True
    with flask_app.app_context():
        row = db.session.scalar(
            select(PlatformAudit)
            .where(PlatformAudit.action == "impersonate.start")
            .order_by(PlatformAudit.created_at.desc())
        )
        assert row is not None
        assert "billing ticket" in (row.reason or "")
    ended = client.post("/api/admin/impersonate/end")
    assert ended.status_code == 200


def test_company_admin_can_save_setting(client, flask_app, no_dev_admin):
    _skip_if_missing(flask_app)
    with flask_app.app_context():
        org = ensure_usis_organization()
        role = _admin_role()
        u = _user("ca_" + uuid.uuid4().hex[:8] + "@t.com")
        add_member(u.id, org.id, ORG_ROLE_ADMIN)
        db.session.add(UserRole(user_id=u.id, role_id=role.id))
        db.session.commit()
        email = u.email
        oid = org.id
    _login(client, email, "secret123")
    r = client.put("/api/settings/mail.spam_confidence_move", json={"value": 0.91})
    assert r.status_code == 200, r.get_data(as_text=True)
    r2 = client.put("/api/settings/mail.rfp.from_address", json={"value": "quotes@gousis.com"})
    assert r2.status_code == 200
    bad_from = client.put("/api/settings/mail.rfp.from_address", json={"value": "me@gmail.com"})
    assert bad_from.status_code == 400
    with flask_app.app_context():
        assert tenant_setting(oid, "mail.spam_confidence_move") == 0.91


def test_operator_lists_seed_tenant(client, flask_app, no_dev_admin):
    _skip_if_missing(flask_app)
    with flask_app.app_context():
        org = ensure_usis_organization()
        op = _user("pop_" + uuid.uuid4().hex[:8] + "@t.com", operator=True)
        add_member(op.id, org.id, ORG_ROLE_MEMBER)
        db.session.commit()
        email = op.email
    _login(client, email, "secret123")
    r = client.get("/api/admin/tenants")
    assert r.status_code == 200, r.get_data(as_text=True)
    slugs = [i.get("slug") for i in (r.get_json() or {}).get("items") or []]
    assert USIS_ORG_SLUG in slugs
    flag = client.put("/api/admin/flags/rfp.b2_files_page", json={"value": True, "reason": "enable files page"})
    assert flag.status_code == 200


def test_dist_mirrors_when_present():
    dist = GULP / "dist"
    src = GULP / "src"
    if not (dist / "usis-settings.html").is_file():
        pytest.skip("dist settings page not built")
    assert (dist / "assets/js/usis-settings.js").read_bytes() == (src / "assets/js/usis-settings.js").read_bytes()
    assert (dist / "assets/js/usis-admin.js").read_bytes() == (src / "assets/js/usis-admin.js").read_bytes()
    html = (dist / "usis-settings.html").read_text(encoding="utf-8")
    assert "usis-settings.js" in html
    assert "usis-ui.css" in html
