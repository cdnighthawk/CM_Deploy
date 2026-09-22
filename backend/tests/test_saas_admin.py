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
    assert 'href="/settings"' in nav
    assert 'href="/admin"' in nav
    assert 'id="usis-platform-admin-nav"' in nav
    assert 'href="/settings/people"' in nav
    for name in ("usis-settings.html", "usis-admin.html", "usis-profile.html"):
        html = (src / name).read_text(encoding="utf-8")
        assert '<base href="/">' in html
        assert 'href="/assets/css/style.css"' in html
        assert 'href="/assets/css/usis-ui.css"' in html
    boot = (src / "assets/js/usis-theme-boot.js").read_text(encoding="utf-8")
    assert 'href = "/assets/css/usis-ui.css' in boot
    css = (src / "assets/css/usis-ui.css").read_text(encoding="utf-8")
    assert ".usis-impersonation-banner" in css
    assert ".usis-console-rail" in css
    assert "--usis-primary: #1e4b8f" in css
    assert "--usis-stamp: #c8102e" in css
    assert "--usis-ai: #6d28d9" in css
    assert "#1f4e5f" not in css
    assert ".btn.usis-ai-review" in css
    settings_js = (src / "assets/js/usis-settings.js").read_text(encoding="utf-8")
    for label in (
        "Overview",
        "People & access",
        "Roles & templates",
        "Projects & defaults",
        "Money & workflows",
        "Mail & senders",
        "Files & public links",
        "Time & field",
        "Hiring",
        "AI",
        "Integrations",
        "Audit",
        "Spend bands",
        "assignment_policy",
        "Creator",
    ):
        assert label in settings_js
    admin_js = (src / "assets/js/usis-admin.js").read_text(encoding="utf-8")
    for label in (
        "Overview",
        "Organizations",
        "Provision",
        "Plans & entitlements",
        "Feature flags",
        "Usage & health",
        "Support",
        "Operators",
        "Policy locks",
    ):
        assert label in admin_js


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
    assert "usis-console-rail" in html
    assert '<base href="/">' in html
    assert 'href="/assets/css/style.css"' in html
    assert "/assets/js/usis-theme-boot.js" in html
    assert 'href="assets/css/style.css"' not in html
    admin_html = (dist / "usis-admin.html").read_text(encoding="utf-8")
    assert admin_html.count("usis-adm-rail") >= 1
    assert '<base href="/">' in admin_html
    assert 'href="/assets/css/style.css"' in admin_html
    profile = dist / "usis-profile.html"
    if profile.is_file():
        profile_html = profile.read_text(encoding="utf-8")
        assert '<base href="/">' in profile_html
        assert 'href="/assets/css/style.css"' in profile_html
        assert "/assets/css/usis-ui.css" in profile_html


def test_settings_overview_and_roles(client, flask_app, no_dev_admin):
    _skip_if_missing(flask_app)
    with flask_app.app_context():
        org = ensure_usis_organization()
        role = _admin_role()
        u = _user("ov_" + uuid.uuid4().hex[:8] + "@t.com")
        add_member(u.id, org.id, ORG_ROLE_ADMIN)
        db.session.add(UserRole(user_id=u.id, role_id=role.id))
        db.session.commit()
        email = u.email
    _login(client, email, "secret123")
    ov = client.get("/api/settings/overview")
    assert ov.status_code == 200, ov.get_data(as_text=True)
    body = ov.get_json() or {}
    assert "seats" in body
    assert "plan_key" in body
    pack = client.get("/api/settings")
    assert pack.status_code == 200
    titles = [t.get("title") for t in (pack.get_json() or {}).get("rail") or []]
    assert titles[0] == "Overview"
    assert "People & access" in titles
    assert len(titles) == 14
    roles = client.get("/api/settings/roles")
    assert roles.status_code == 200
    assert "catalog" in (roles.get_json() or {})


def test_invite_at_seat_cap_409(client, flask_app, no_dev_admin):
    _skip_if_missing(flask_app)
    with flask_app.app_context():
        org = ensure_usis_organization()
        role = _admin_role()
        u = _user("cap_" + uuid.uuid4().hex[:8] + "@t.com")
        add_member(u.id, org.id, ORG_ROLE_ADMIN)
        db.session.add(UserRole(user_id=u.id, role_id=role.id))
        org.seat_cap_office = 1
        db.session.commit()
        email = u.email
    _login(client, email, "secret123")
    r = client.post(
        "/api/settings/users/invite",
        json={"email": "extra_" + uuid.uuid4().hex[:8] + "@t.com", "seat_kind": "office"},
    )
    assert r.status_code == 409, r.get_data(as_text=True)
    assert "seat cap" in ((r.get_json() or {}).get("error") or "").lower()


def test_user_directory_redirects_to_people(client, flask_app, no_dev_admin):
    _skip_if_missing(flask_app)
    r = client.get("/usis-user-directory.html", follow_redirects=False)
    assert r.status_code in (301, 302)
    loc = r.headers.get("Location") or ""
    assert loc.endswith("/settings/people") or "/settings/people" in loc


def test_admin_overview_operator_only(client, flask_app, no_dev_admin):
    _skip_if_missing(flask_app)
    with flask_app.app_context():
        org = ensure_usis_organization()
        op = _user("aov_" + uuid.uuid4().hex[:8] + "@t.com", operator=True)
        add_member(op.id, org.id, ORG_ROLE_ADMIN)
        db.session.commit()
        email = op.email
    _login(client, email, "secret123")
    r = client.get("/api/admin/overview")
    assert r.status_code == 200, r.get_data(as_text=True)
    body = r.get_json() or {}
    assert "organizations_by_status" in body
    plans = client.get("/api/admin/plans")
    assert plans.status_code == 200
    locks = client.get("/api/admin/policy")
    assert locks.status_code == 200
    orgs = client.get("/api/admin/organizations")
    assert orgs.status_code == 200


def test_last_platform_operator_cannot_be_deleted(client, flask_app, no_dev_admin):
    _skip_if_missing(flask_app)
    with flask_app.app_context():
        org = ensure_usis_organization()
        ops = db.session.scalars(select(User).where(User.is_platform_operator.is_(True))).all()
        for u in ops[1:]:
            u.is_platform_operator = False
        if not ops:
            op = _user("onlyop_" + uuid.uuid4().hex[:8] + "@t.com", operator=True)
            add_member(op.id, org.id, ORG_ROLE_ADMIN)
            email = op.email
            uid = str(op.id)
        else:
            email = ops[0].email
            uid = str(ops[0].id)
            if not ops[0].password_hash:
                from werkzeug.security import generate_password_hash

                ops[0].password_hash = generate_password_hash("secret123")
        db.session.commit()
    _login(client, email, "secret123")
    r = client.delete("/api/admin/operators/" + uid)
    assert r.status_code == 400
    assert "last" in ((r.get_json() or {}).get("error") or "").lower()


def test_publish_po_bands_does_not_change_inflight_version(client, flask_app, no_dev_admin):
    _skip_if_missing(flask_app)
    with flask_app.app_context():
        try:
            db.session.execute(text("SELECT 1 FROM workflow_definitions LIMIT 1"))
            db.session.execute(text("SELECT 1 FROM workflow_instances LIMIT 1"))
        except (OperationalError, ProgrammingError) as exc:
            pytest.skip(f"workflow schema missing: {exc}")
        from app.api._workflow_service import PROCESS_PURCHASE_ORDER, ensure_default_definition, start_instance
        from app.models import WorkflowInstance
        from app.tenancy import set_current_organization_id

        org = ensure_usis_organization()
        role = _admin_role()
        u = _user("po_" + uuid.uuid4().hex[:8] + "@t.com")
        add_member(u.id, org.id, ORG_ROLE_ADMIN)
        db.session.add(UserRole(user_id=u.id, role_id=role.id))
        set_current_organization_id(org.id)
        definition = ensure_default_definition(process_key=PROCESS_PURCHASE_ORDER)
        frozen = int(definition.version)
        inst = start_instance(
            process_key=PROCESS_PURCHASE_ORDER,
            subject_type="test_po",
            subject_id=uuid.uuid4(),
        )
        inst_id = inst.id
        db.session.commit()
        email = u.email
    _login(client, email, "secret123")
    r = client.post(
        "/api/settings/money",
        json={"po.band_pm": 6000, "po.band_0": 0, "po.band_director": 25000, "tm.requires_co": True},
    )
    assert r.status_code == 200, r.get_data(as_text=True)
    skip = client.put("/api/settings/po.skip_down", json={"value": True})
    assert skip.status_code == 403
    with flask_app.app_context():
        from app.models import WorkflowInstance

        row = db.session.get(WorkflowInstance, inst_id)
        assert row is not None
        assert int(row.definition_version) == frozen


def test_src_money_and_admin_v2_labels():
    src = GULP / "src"
    settings_js = (src / "assets/js/usis-settings.js").read_text(encoding="utf-8")
    assert "Spend bands" in settings_js
    assert "Workflow pack" in settings_js
    admin_js = (src / "assets/js/usis-admin.js").read_text(encoding="utf-8")
    assert "usis-adm-tabs" in admin_js
    assert "/api/admin/operators" in admin_js
    assert "not metered yet" in admin_js
    assert "Force end" in admin_js

