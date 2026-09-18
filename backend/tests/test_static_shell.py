"""Static shell routing (root redirect, apply page still served)."""
from __future__ import annotations

from pathlib import Path

import pytest

from app.static_shell import resolve_static_root, saas_console_kind


@pytest.fixture
def static_root() -> Path | None:
    return resolve_static_root()


def test_root_redirects_to_login(client, static_root, monkeypatch):
    if static_root is None:
        pytest.skip("gulp/dist not present")
    monkeypatch.setenv("USIS_API_DEV_ALLOW_ANY", "0")
    r = client.get("/")
    assert r.status_code == 302
    assert r.headers.get("Location") == "/page-login.html"


def test_page_login_is_served_even_with_dev_bypass(client, static_root, monkeypatch):
    if static_root is None:
        pytest.skip("gulp/dist not present")
    monkeypatch.setenv("USIS_API_DEV_ALLOW_ANY", "1")
    r = client.get("/page-login.html")
    assert r.status_code == 200
    assert b"usis-login-form" in r.data


def test_careers_path_redirects_to_apply(client, static_root):
    if static_root is None:
        pytest.skip("gulp/dist not present")
    r = client.get("/careers")
    assert r.status_code == 302
    assert r.headers.get("Location") == "/apply.html"


def test_hire_path_redirects_to_application(client, static_root):
    if static_root is None:
        pytest.skip("gulp/dist not present")
    r = client.get("/hire")
    assert r.status_code == 302
    assert r.headers.get("Location") == "/apply/application.html"


def test_apply_html_case_insensitive_redirect(client, static_root):
    if static_root is None:
        pytest.skip("gulp/dist not present")
    r = client.get("/Apply.html")
    assert r.status_code == 302
    assert r.headers.get("Location") == "/apply.html"


def test_construction_index_redirects_to_projects(client, static_root):
    if static_root is None:
        pytest.skip("gulp/dist not present")
    r = client.get("/construction/index.html")
    assert r.status_code == 302
    assert r.headers.get("Location") == "/construction/projects.html"


def test_construction_dir_redirects_to_projects(client, static_root):
    if static_root is None:
        pytest.skip("gulp/dist not present")
    r = client.get("/construction")
    assert r.status_code == 302
    assert r.headers.get("Location") == "/construction/projects.html"


def test_apply_page_served(client, static_root):
    if static_root is None:
        pytest.skip("gulp/dist not present")
    r = client.get("/apply.html")
    assert r.status_code == 200
    assert b"apply" in r.data.lower() or b"career" in r.data.lower()


def test_duplicate_hubs_redirect(client, static_root):
    if static_root is None:
        pytest.skip("gulp/dist not present")
    r = client.get("/usis-dashboard.html")
    assert r.status_code == 302
    assert r.headers.get("Location") == "/usis-dashboard-dark.html"
    r = client.get("/usis-hr.html")
    assert r.status_code == 302
    assert r.headers.get("Location") == "/usis-hr-dashboard.html"
    r = client.get("/usis-leads.html")
    assert r.status_code == 302
    assert r.headers.get("Location") == "/construction/leads.html"


def test_leftover_template_pages_are_branded_404(client, static_root):
    if static_root is None:
        pytest.skip("gulp/dist not present")
    r = client.get("/ecom-product-grid.html")
    assert r.status_code == 404
    assert b"That page is not in USIS CM" in r.data or b"US Interior Specialties" in r.data
    r = client.get("/construction/quotation.html")
    assert r.status_code == 404
    r = client.get("/usis-all-pages-index.html")
    assert r.status_code == 404
    missing = client.get("/this-page-does-not-exist.html")
    assert missing.status_code == 404
    assert b"That page is not in USIS CM" in missing.data or b"US Interior Specialties" in missing.data


def test_live_usis_pages_still_served(client, static_root):
    if static_root is None:
        pytest.skip("gulp/dist not present")
    r = client.get("/page-login.html")
    assert r.status_code == 200
    r = client.get("/construction/projects.html")
    assert r.status_code == 200


def test_saas_console_kind_does_not_steal_profile_or_assets():
    assert saas_console_kind("/admin") == "admin"
    assert saas_console_kind("/admin/organizations") == "admin"
    assert saas_console_kind("/admin/organizations/abc") == "admin"
    assert saas_console_kind("/settings") == "settings"
    assert saas_console_kind("/settings/people") == "settings"
    assert saas_console_kind("/admin/usis-profile.html") is None
    assert saas_console_kind("/admin/assets/css/style.css") is None
    assert saas_console_kind("/settings/assets/css/style.css") is None
    assert saas_console_kind("/usis-profile.html") is None
    assert saas_console_kind("/usis-admin.html") == "admin"
    assert saas_console_kind("/usis-settings.html") == "settings"


def test_admin_profile_collision_redirects_to_profile(client, static_root):
    if static_root is None:
        pytest.skip("gulp/dist not present")
    r = client.get("/admin/usis-profile.html", follow_redirects=False)
    assert r.status_code in (301, 302)
    loc = r.headers.get("Location") or ""
    assert loc.endswith("/usis-profile.html")
    assert "/admin/" not in loc


def test_console_html_uses_root_assets(client, static_root):
    if static_root is None:
        pytest.skip("gulp/dist not present")
    for path in ("/admin", "/admin/organizations", "/settings/people", "/usis-profile.html"):
        r = client.get(path)
        assert r.status_code == 200, path
        html = r.get_data(as_text=True)
        assert '<base href="/">' in html, path
        assert "/assets/css/style.css" in html, path
        assert "/assets/css/usis-ui.css" in html, path
        assert 'href="assets/css/style.css"' not in html, path


def test_admin_prefix_does_not_serve_theme_assets(client, static_root):
    if static_root is None:
        pytest.skip("gulp/dist not present")
    stolen = client.get("/admin/assets/css/style.css")
    assert stolen.status_code == 404
    real = client.get("/assets/css/style.css")
    assert real.status_code == 200
    assert "text/css" in (real.headers.get("Content-Type") or "")
    usis = client.get("/assets/css/usis-ui.css")
    assert usis.status_code == 200
    assert "text/css" in (usis.headers.get("Content-Type") or "")
