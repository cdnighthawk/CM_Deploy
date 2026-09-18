"""Contractor setup page, script, and superuser-only Admin nav exist."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
GULP = REPO / "W3CRM-v3.0-13_September_2025" / "gulp"
SRC = GULP / "src"
DIST = GULP / "dist"

SRC_PAGE = SRC / "usis-platform-contractors.html"
SRC_JS = SRC / "assets/js/usis-platform-contractors.js"
SRC_NAV = SRC / "elements/deznav-construction.html"
SRC_INDEX = SRC / "usis-all-pages-index.html"

DIST_PAGE = DIST / "usis-platform-contractors.html"
DIST_JS = DIST / "assets/js/usis-platform-contractors.js"
DIST_INDEX = DIST / "usis-all-pages-index.html"


def test_src_page_and_script_exist():
    html = SRC_PAGE.read_text(encoding="utf-8")
    js = SRC_JS.read_text(encoding="utf-8")
    assert "usis-platform-contractors.js" in html
    assert "Add contractor" in html
    assert "Copy catalog without USIS prices" in html
    assert "Connect BuildingConnected" in html
    settings_src = SRC / "usis-company-settings.html"
    assert "Connect BuildingConnected" in settings_src.read_text(encoding="utf-8")
    assert "/api/v1/integrations/buildingconnected/status" in (SRC / "assets/js/usis-company-settings.js").read_text(encoding="utf-8")
    assert "BuildingConnected" in html
    assert "Platform administrator required" in html
    assert "/api/v1/platform/organizations" in js
    assert "/api/v1/platform/organizations/" in js
    assert "/invites" in js
    assert "copy_catalog" in js
    assert "is_superuser" in js
    assert 'credentials = opts.credentials || "include"' in js
    assert "Set-password email sent" in js
    assert "email dry-run" in js
    assert "Uncheck Copy catalog" in js
    assert "/api/v1/integrations/buildingconnected/oauth/start" in js
    assert "organization_id=" in js
    assert "usis-bc-oauth" in js


def test_src_nav_uses_platform_module_not_user_admin():
    nav = SRC_NAV.read_text(encoding="utf-8")
    match = re.search(
        r'<li data-usis-module="([^"]+)">\s*<a href="usis-platform-contractors.html"',
        nav,
    )
    assert match is not None
    assert match.group(1) == "platform"
    index = SRC_INDEX.read_text(encoding="utf-8")
    assert "usis-platform-contractors.html" in index
    assert "USIS Contractors" in index


def test_dist_mirrors_page_script_and_nav():
    if not DIST.is_dir():
        pytest.skip("gulp/dist not present")
    assert DIST_PAGE.is_file()
    assert DIST_JS.is_file()
    assert SRC_JS.read_bytes() == DIST_JS.read_bytes()
    html = DIST_PAGE.read_text(encoding="utf-8")
    assert "usis-platform-contractors.js" in html
    assert "Add contractor" in html
    assert 'data-usis-module="platform"' in html
    assert 'href="usis-platform-contractors.html"' in html
    settings = (DIST / "usis-company-settings.html").read_text(encoding="utf-8")
    projects = (DIST / "construction/projects.html").read_text(encoding="utf-8")
    assert 'data-usis-module="platform"' in settings
    assert 'href="usis-platform-contractors.html"' in settings
    assert "Connect BuildingConnected" in settings
    assert 'data-usis-module="platform"' in projects
    assert 'href="usis-platform-contractors.html"' in projects
    index = DIST_INDEX.read_text(encoding="utf-8")
    assert "usis-platform-contractors.html" in index
    assert "USIS Contractors" in index
