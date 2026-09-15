"""Lead detail breadcrumb must parent through Leads, not Active projects."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SRC_JS = REPO / "W3CRM-v3.0-13_September_2025/gulp/src/assets/js/usis-project-context.js"
DIST_JS = REPO / "W3CRM-v3.0-13_September_2025/gulp/dist/assets/js/usis-project-context.js"
DIST = REPO / "W3CRM-v3.0-13_September_2025/gulp/dist"
HARNESS = Path(__file__).resolve().parent / "js/lead_detail_breadcrumb_harness.js"


def test_src_and_dist_project_context_stay_in_sync():
    assert SRC_JS.is_file()
    assert DIST_JS.is_file()
    assert SRC_JS.read_text(encoding="utf-8") == DIST_JS.read_text(encoding="utf-8")


def test_project_context_js_special_cases_lead_detail_list_trail():
    text = SRC_JS.read_text(encoding="utf-8")
    assert "construction/leads.html" in text
    assert 'label: "Leads"' in text
    assert "lead-detail.html" in text
    assert "leadDetailOrigin" in text


def test_leads_list_and_projects_pass_origin_query():
    leads_src = REPO / "W3CRM-v3.0-13_September_2025/gulp/src/construction/leads.html"
    projects_src = REPO / "W3CRM-v3.0-13_September_2025/gulp/src/construction/projects.html"
    assert "&from=leads" in leads_src.read_text(encoding="utf-8")
    assert "&from=projects" in projects_src.read_text(encoding="utf-8")
    if not DIST.is_dir():
        pytest.skip("gulp/dist not present")
    assert "&from=leads" in (DIST / "construction/leads.html").read_text(encoding="utf-8")
    assert "&from=projects" in (DIST / "construction/projects.html").read_text(encoding="utf-8")


def test_lead_detail_page_keeps_back_to_leads():
    if not DIST.is_dir():
        pytest.skip("gulp/dist not present")
    html = (DIST / "construction/lead-detail.html").read_text(encoding="utf-8")
    assert "Back to Leads" in html
    assert 'href="construction/leads.html"' in html
    assert "usis-project-context.js?v=20260915a" in html


def test_breadcrumb_builder_routes_lead_detail_through_leads():
    node = shutil.which("node")
    if not node:
        pytest.skip("node not available")
    result = subprocess.run(
        [node, str(HARNESS), str(DIST_JS)],
        check=False,
        capture_output=True,
        text=True,
        cwd=str(REPO),
    )
    if result.returncode != 0:
        pytest.fail(
            "node breadcrumb harness failed:\n"
            + (result.stdout or "")
            + (result.stderr or "")
        )
    assert "ok" in (result.stdout or "")
