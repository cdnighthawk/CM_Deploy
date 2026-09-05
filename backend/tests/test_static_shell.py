"""Static shell routing (root redirect, apply page still served)."""
from __future__ import annotations

from pathlib import Path

import pytest

from app.static_shell import resolve_static_root


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
