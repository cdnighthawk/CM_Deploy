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
