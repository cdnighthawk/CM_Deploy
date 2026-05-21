"""Static shell routing (root redirect, apply page still served)."""
from __future__ import annotations

from pathlib import Path

import pytest

from app.static_shell import resolve_static_root


@pytest.fixture
def static_root() -> Path | None:
    return resolve_static_root()


def test_root_redirects_to_dashboard(client, static_root):
    if static_root is None:
        pytest.skip("gulp/dist not present")
    r = client.get("/")
    assert r.status_code == 302
    assert r.headers.get("Location") == "/usis-dashboard-dark.html"


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


def test_apply_page_served(client, static_root):
    if static_root is None:
        pytest.skip("gulp/dist not present")
    r = client.get("/apply.html")
    assert r.status_code == 200
    assert b"apply" in r.data.lower() or b"career" in r.data.lower()
