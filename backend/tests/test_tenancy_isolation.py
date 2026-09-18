"""Cross-organization isolation: UUID fetches, catalog copy, login, invites."""
from __future__ import annotations

import uuid
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import OperationalError, ProgrammingError
from werkzeug.security import generate_password_hash

from app.extensions import db
from app.models import Drawing, HrOnboardingItem, Project, Role, User, UserRole
from app.models.material_pricing import MaterialPrice
from app.models.organization import ORG_ROLE_OWNER, Organization, USIS_ORG_SLUG
from app.tenancy import (
    add_member,
    copy_material_catalog,
    ensure_usis_organization,
    include_all_orgs,
    provision_organization,
    storage_key_prefix_for_org,
    stored_key_allowed,
)
from app.services.password_reset import confirm_password_reset, issue_set_password_token

REPO = Path(__file__).resolve().parents[2]
GULP = REPO / "W3CRM-v3.0-13_September_2025" / "gulp"


@pytest.fixture
def no_dev_admin(monkeypatch):
    monkeypatch.setenv("USIS_API_DEV_ALLOW_ANY", "0")


def _skip_if_no_orgs(flask_app) -> None:
    with flask_app.app_context():
        try:
            db.session.execute(text("SELECT 1 FROM organizations LIMIT 1"))
        except (OperationalError, ProgrammingError) as exc:
            pytest.skip(f"organizations schema missing: {exc}")


def test_catalog_copy_uses_insert_select_not_orm_all():
    src = (Path(__file__).resolve().parents[1] / "app" / "tenancy.py").read_text(encoding="utf-8")
    start = src.index("def copy_material_catalog")
    end = src.index("\ndef slugify_org_name")
    body = src[start:end]
    assert "insert(src).from_select" in body
    assert "func.gen_random_uuid()" in body
    assert "null()" in body
    assert ".all()" not in body


def _login(client, email: str, password: str):
    r = client.post("/auth/login", data={"email": email, "password": password}, follow_redirects=False)
    assert r.status_code == 302, r.get_data(as_text=True)
    loc = r.headers.get("Location") or ""
    assert "login_error=" not in loc
    return r


def test_header_and_login_copy_have_org_switcher():
    src_header = GULP / "src" / "elements" / "header-construction.html"
    src_js = GULP / "src" / "assets" / "js" / "usis-auth-links.js"
    src_login = GULP / "src" / "page-login.html"
    assert "usis-org-switcher" in src_header.read_text(encoding="utf-8")
    js = src_js.read_text(encoding="utf-8")
    assert "wireOrgSwitcher" in js
    assert "/api/v1/auth/organization" in js
    login = src_login.read_text(encoding="utf-8")
    assert "USIS employees — Sign in with Microsoft" in login
    assert "Sign in with email and password" in login

    dist_js = GULP / "dist" / "assets" / "js" / "usis-auth-links.js"
    dist_login = GULP / "dist" / "page-login.html"
    dist_dash = GULP / "dist" / "usis-dashboard-dark.html"
    if dist_js.is_file():
        assert "wireOrgSwitcher" in dist_js.read_text(encoding="utf-8")
    if dist_login.is_file():
        html = dist_login.read_text(encoding="utf-8")
        assert "USIS employees — Sign in with Microsoft" in html
    if dist_dash.is_file():
        assert "usis-org-switcher" in dist_dash.read_text(encoding="utf-8")


def test_password_login_sets_organization(client, flask_app, no_dev_admin):
    _skip_if_no_orgs(flask_app)
    email = "iso_login_" + uuid.uuid4().hex[:8] + "@t.com"
    with flask_app.app_context():
        usis = ensure_usis_organization()
        u = User(
            email=email,
            first_name="Iso",
            last_name="Login",
            password_hash=generate_password_hash("iso-login-pw"),
            is_active=True,
        )
        db.session.add(u)
        db.session.flush()
        add_member(u.id, usis.id, ORG_ROLE_OWNER)
        db.session.commit()
        usis_id = str(usis.id)

    _login(client, email, "iso-login-pw")
    st = client.get("/api/v1/auth/status").get_json()
    assert st["authenticated"] is True
    assert st["current_organization_id"] == usis_id
    slugs = [o["slug"] for o in st["organizations"]]
    assert USIS_ORG_SLUG in slugs
    assert st["microsoft_sso_enabled"] is False or "microsoft_sso_enabled" in st


def test_entra_login_lands_on_usis_org(client, flask_app, no_dev_admin, monkeypatch):
    _skip_if_no_orgs(flask_app)
    email = "iso_ms_" + uuid.uuid4().hex[:8] + "@t.com"
    with flask_app.app_context():
        usis = ensure_usis_organization()
        usis.microsoft_sso_enabled = True
        u = User(
            email=email,
            first_name="M",
            last_name="S",
            password_hash=generate_password_hash("pw"),
            is_active=True,
        )
        db.session.add(u)
        db.session.commit()
        usis_id = str(usis.id)

    monkeypatch.setenv("MS_ENTRA_TENANT_ID", "11111111-1111-1111-1111-111111111111")
    monkeypatch.setenv("MS_ENTRA_CLIENT_ID", "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    monkeypatch.setenv("MS_ENTRA_CLIENT_SECRET", "secret-value")
    monkeypatch.setenv("MS_ENTRA_REDIRECT_URI", "http://127.0.0.1:5000/auth/microsoft/callback")
    cfg = client.application.config
    cfg["MS_ENTRA_TENANT_ID"] = "11111111-1111-1111-1111-111111111111"
    cfg["MS_ENTRA_CLIENT_ID"] = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    cfg["MS_ENTRA_CLIENT_SECRET"] = "secret-value"
    cfg["MS_ENTRA_REDIRECT_URI"] = "http://127.0.0.1:5000/auth/microsoft/callback"

    with client.session_transaction() as sess:
        sess["ms_entra_oauth_state"] = "st-iso"
        sess["ms_entra_oauth_next"] = "http://127.0.0.1:3000/usis-dashboard-dark.html"

    with patch("app.integrations.ms_entra_oidc.exchange_code_for_tokens", return_value={"id_token": "x"}):
        with patch("app.integrations.ms_entra_oidc.verify_id_token", return_value={"email": email}):
            with patch("app.integrations.ms_entra_oidc.claims_email", return_value=email):
                r = client.get("/auth/microsoft/callback?code=cc&state=st-iso", follow_redirects=False)
    assert r.status_code == 302
    st = client.get("/api/v1/auth/status").get_json()
    assert st["authenticated"] is True
    assert st["current_organization_id"] == usis_id


def test_applicant_register_does_not_create_org(client, flask_app, no_dev_admin, monkeypatch):
    _skip_if_no_orgs(flask_app)
    monkeypatch.setitem(client.application.config, "USIS_ALLOW_SELF_REGISTER", True)
    email = "iso_hire_" + uuid.uuid4().hex[:8] + "@t.com"
    before = 0
    with flask_app.app_context():
        before = db.session.scalar(select(func.count()).select_from(Organization)) or 0
    r = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "hire-test-pw", "first_name": "Pat", "last_name": "Applicant"},
    )
    assert r.status_code == 201, r.get_data(as_text=True)
    st = client.get("/api/v1/auth/status").get_json()
    assert st["authenticated"] is True
    slugs = [o["slug"] for o in st["organizations"]]
    assert slugs == [USIS_ORG_SLUG]
    with flask_app.app_context():
        after = db.session.scalar(select(func.count()).select_from(Organization)) or 0
    assert after == before


def test_company_self_signup_disabled(client, flask_app, no_dev_admin):
    _skip_if_no_orgs(flask_app)
    email = "iso_self_" + uuid.uuid4().hex[:8] + "@t.com"
    with flask_app.app_context():
        usis = ensure_usis_organization()
        u = User(
            email=email,
            password_hash=generate_password_hash("self-signup-pw"),
            is_active=True,
        )
        db.session.add(u)
        db.session.flush()
        add_member(u.id, usis.id)
        db.session.commit()
    _login(client, email, "self-signup-pw")
    r = client.post("/api/v1/organizations", json={"name": "Should Fail Inc"})
    assert r.status_code == 403


def test_acme_cannot_read_usis_rows_by_uuid(client, flask_app, no_dev_admin):
    _skip_if_no_orgs(flask_app)
    token = uuid.uuid4().hex[:8]
    with flask_app.app_context():
        usis = ensure_usis_organization()
        usis_user = User(
            email=f"iso_usis_{token}@t.com",
            first_name="Usis",
            last_name="Staff",
            password_hash=generate_password_hash("usis-pw"),
            is_active=True,
        )
        db.session.add(usis_user)
        db.session.flush()
        add_member(usis_user.id, usis.id)
        proj = Project(name=f"ISO-USIS-{token}", organization_id=usis.id)
        db.session.add(proj)
        db.session.flush()
        sku = MaterialPrice(
            organization_id=usis.id,
            manufacturer=f"IsoMfg{token}",
            item=f"sku-{token}",
            category="Hardware",
            cost=Decimal("99.2500"),
            labor_per=Decimal("1"),
        )
        db.session.add(sku)
        drawing = Drawing(
            project_id=proj.id,
            document_type="drawing",
            sheet_number="A-ISO",
            sheet_title="Isolation sheet",
            original_filename="iso.pdf",
            organization_id=usis.id,
        )
        db.session.add(drawing)
        db.session.add(
            HrOnboardingItem(
                user_id=usis_user.id,
                title="USIS packet",
                sort_order=1,
                organization_id=usis.id,
            )
        )
        acme = provision_organization(name=f"Acme Iso {token}", copy_catalog=False)
        acme_user = User(
            email=f"iso_acme_{token}@t.com",
            first_name="Acme",
            last_name="Admin",
            password_hash=generate_password_hash("acme-pw"),
            is_active=True,
            is_superuser=True,
        )
        db.session.add(acme_user)
        db.session.flush()
        add_member(acme_user.id, acme.id, ORG_ROLE_OWNER)
        role = db.session.scalar(select(Role).where(Role.code == "admin"))
        if role is not None:
            db.session.add(UserRole(user_id=acme_user.id, role_id=role.id, organization_id=acme.id))
        db.session.commit()
        ids = {
            "project": str(proj.id),
            "material": str(sku.id),
            "drawing": str(drawing.id),
            "employee": str(usis_user.id),
            "acme": str(acme.id),
            "usis": str(usis.id),
        }

    _login(client, f"iso_acme_{token}@t.com", "acme-pw")
    st = client.get("/api/v1/auth/status").get_json()
    assert st["current_organization_id"] == ids["acme"]

    p = client.get(f"/api/v1/projects/{ids['project']}")
    assert p.status_code == 404

    m = client.get(f"/api/v1/material-prices/{ids['material']}")
    assert m.status_code == 404

    d = client.get(f"/api/v1/projects/{ids['project']}/drawings")
    assert d.status_code == 404

    df = client.get(f"/api/v1/drawings/{ids['drawing']}/file")
    assert df.status_code in (403, 404)

    emp = client.get(f"/api/v1/hr/employees/{ids['employee']}")
    assert emp.status_code == 404

    listed = client.get("/api/v1/material-prices")
    assert listed.status_code == 200
    items = listed.get_json().get("items") or []
    for row in items:
        assert row.get("id") != ids["material"]
        cost = row.get("cost")
        if cost is not None:
            assert Decimal(str(cost)) != Decimal("99.2500") or row.get("manufacturer") != f"IsoMfg{token}"


def test_catalog_copy_strips_usis_cost(flask_app):
    _skip_if_no_orgs(flask_app)
    token = uuid.uuid4().hex[:8]
    with flask_app.app_context():
        src_org = provision_organization(name=f"Copy Src {token}", copy_catalog=False)
        dest = provision_organization(name=f"Copy Dest {token}", copy_catalog=False)
        src = MaterialPrice(
            organization_id=src_org.id,
            manufacturer=f"CopyMfg{token}",
            item=f"copy-{token}",
            category="Hardware",
            cost=Decimal("42.5000"),
            labor_per=Decimal("2"),
            labor_units_per_hour=Decimal("4"),
            description="keep-desc",
        )
        db.session.add(src)
        db.session.flush()
        n = copy_material_catalog(src_org.id, dest.id)
        assert n == 1
        db.session.commit()
        dest_id = dest.id
        with include_all_orgs():
            copied = db.session.scalar(
                select(MaterialPrice).where(
                    MaterialPrice.organization_id == dest_id,
                    MaterialPrice.manufacturer == f"CopyMfg{token}",
                    MaterialPrice.item == f"copy-{token}",
                )
            )
        assert copied is not None
        assert copied.cost is None
        assert copied.description == "keep-desc"
        assert copied.labor_per == Decimal("2")


def test_invite_set_password_without_entra(client, flask_app, no_dev_admin):
    _skip_if_no_orgs(flask_app)
    token = uuid.uuid4().hex[:8]
    email = f"iso_invite_{token}@t.com"
    with flask_app.app_context():
        org = provision_organization(name=f"Invite Co {token}", copy_catalog=False)
        u = User(email=email, first_name="Inv", last_name="Itee", is_active=True, password_hash=None)
        db.session.add(u)
        db.session.flush()
        add_member(u.id, org.id, ORG_ROLE_OWNER)
        raw = issue_set_password_token(u)
        org_id = str(org.id)
        db.session.commit()
        confirm_password_reset(raw, "invite-set-pw")
        db.session.commit()

    _login(client, email, "invite-set-pw")
    st = client.get("/api/v1/auth/status").get_json()
    assert st["authenticated"] is True
    assert st["current_organization_id"] == org_id


def test_platform_create_org_and_invite(client, flask_app, no_dev_admin):
    _skip_if_no_orgs(flask_app)
    token = uuid.uuid4().hex[:8]
    admin_email = f"iso_plat_{token}@t.com"
    invite_email = f"iso_plat_invite_{token}@t.com"
    with flask_app.app_context():
        usis = ensure_usis_organization()
        admin = User(
            email=admin_email,
            password_hash=generate_password_hash("plat-pw"),
            is_active=True,
            is_superuser=True,
        )
        db.session.add(admin)
        db.session.flush()
        add_member(admin.id, usis.id, ORG_ROLE_OWNER)
        db.session.commit()

    _login(client, admin_email, "plat-pw")
    created = client.post(
        "/api/v1/platform/organizations",
        json={"name": f"Platform Co {token}", "copy_catalog": True},
    )
    assert created.status_code == 201, created.get_data(as_text=True)
    created_item = created.get_json()["item"]
    org_id = created_item["id"]
    with flask_app.app_context():
        with include_all_orgs():
            copied = db.session.scalar(
                select(func.count())
                .select_from(MaterialPrice)
                .where(MaterialPrice.organization_id == uuid.UUID(org_id))
            )
        assert copied == 0
    assert created_item.get("buildingconnected", {}).get("connected") is False
    invited = client.post(
        f"/api/v1/platform/organizations/{org_id}/invites",
        json={"email": invite_email, "first_name": "Pat"},
    )
    assert invited.status_code == 201, invited.get_data(as_text=True)
    body = invited.get_json()
    assert body["ok"] is True
    assert body["created_user"] is True

    listed = client.get("/api/v1/platform/organizations")
    assert listed.status_code == 200
    match = next(o for o in listed.get_json()["items"] if o["id"] == org_id)
    assert match["buildingconnected"]["connected"] is False
    assert "/integrations/buildingconnected/oauth/start" in match["buildingconnected"]["oauth_start_url"]

    non_admin = f"iso_notplat_{token}@t.com"
    with flask_app.app_context():
        u = User(email=non_admin, password_hash=generate_password_hash("nope-pw"), is_active=True)
        db.session.add(u)
        db.session.flush()
        add_member(u.id, uuid.UUID(org_id), ORG_ROLE_OWNER)
        db.session.commit()
    client.get("/auth/logout")
    _login(client, non_admin, "nope-pw")
    denied = client.post("/api/v1/platform/organizations", json={"name": "Nope"})
    assert denied.status_code == 403


def test_org_switcher_api(client, flask_app, no_dev_admin):
    _skip_if_no_orgs(flask_app)
    token = uuid.uuid4().hex[:8]
    email = f"iso_switch_{token}@t.com"
    with flask_app.app_context():
        usis = ensure_usis_organization()
        acme = provision_organization(name=f"Switch Co {token}", copy_catalog=False)
        u = User(email=email, password_hash=generate_password_hash("switch-pw"), is_active=True)
        db.session.add(u)
        db.session.flush()
        add_member(u.id, usis.id)
        add_member(u.id, acme.id)
        db.session.commit()
        ids = {"usis": str(usis.id), "acme": str(acme.id)}

    _login(client, email, "switch-pw")
    st = client.get("/api/v1/auth/status").get_json()
    org_ids = {o["id"] for o in st["organizations"]}
    assert ids["usis"] in org_ids and ids["acme"] in org_ids
    r = client.post("/api/v1/auth/organization", json={"organization_id": ids["acme"]})
    assert r.status_code == 200, r.get_data(as_text=True)
    assert r.get_json()["current_organization_id"] == ids["acme"]
    st2 = client.get("/api/v1/auth/status").get_json()
    assert st2["current_organization_id"] == ids["acme"]
    bogus = client.post("/api/v1/auth/organization", json={"organization_id": str(uuid.uuid4())})
    assert bogus.status_code == 403


def test_storage_prefix_isolates_non_usis_keys(flask_app):
    _skip_if_no_orgs(flask_app)
    with flask_app.app_context():
        flask_app.config["B2_PREFIX"] = "prod/usis-cm"
        usis = ensure_usis_organization()
        acme = provision_organization(name="Storage Co " + uuid.uuid4().hex[:6], copy_catalog=False)
        db.session.commit()
        assert storage_key_prefix_for_org(usis) == "prod/usis-cm"
        other = storage_key_prefix_for_org(acme)
        assert str(acme.id) in other
        assert other.startswith("prod/usis-cm/")
        from flask import g

        with flask_app.test_request_context("/"):
            g.organization_id = acme.id
            assert stored_key_allowed(f"prod/usis-cm/{acme.id}/drawings/a.pdf") is True
            assert stored_key_allowed("prod/usis-cm/drawings/legacy.pdf") is False
            g.organization_id = usis.id
            assert stored_key_allowed("prod/usis-cm/drawings/legacy.pdf") is True
            assert stored_key_allowed(f"prod/usis-cm/{acme.id}/drawings/a.pdf") is False


def test_mobile_jwt_carries_organization(client, flask_app, no_dev_admin):
    _skip_if_no_orgs(flask_app)
    email = "iso_mob_" + uuid.uuid4().hex[:8] + "@t.com"
    with flask_app.app_context():
        usis = ensure_usis_organization()
        u = User(email=email, password_hash=generate_password_hash("mob-pw"), is_active=True)
        db.session.add(u)
        db.session.flush()
        add_member(u.id, usis.id)
        db.session.commit()
        usis_id = str(usis.id)

    r = client.post("/api/v1/auth/mobile/login", json={"email": email, "password": "mob-pw"})
    assert r.status_code == 200, r.get_data(as_text=True)
    token = r.get_json()["access_token"]
    import jwt

    payload = jwt.decode(token, client.application.config["SECRET_KEY"], algorithms=["HS256"])
    assert payload.get("org") == usis_id
