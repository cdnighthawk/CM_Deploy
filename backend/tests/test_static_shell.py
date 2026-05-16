"""Static shell routing (root redirect, apply page still served)."""
from __future__ import annotations

from pathlib import Path

import pytest

from app.static_shell import resolve_static_root


@pytest.fixture
def static_root() -> Path | None:
    return resolve_static_root()


def test_root_redirects_to_dark_dashboard(client, static_root):
    if static_root is None:
        pytest.skip("gulp/dist not present")
    r = client.get("/")
    assert r.status_code == 302
    assert r.headers.get("Location") == "/usis-dashboard-dark.html"


def test_apply_page_served(client, static_root):
    if static_root is None:
        pytest.skip("gulp/dist not present")
    r = client.get("/apply.html")
    assert r.status_code == 200
    assert b"apply" in r.data.lower() or b"career" in r.data.lower()
