"""Estimate detail breadcrumb must parent through Estimate, not Active projects."""
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


def test_project_context_js_special_cases_estimate_detail_list_trail():
    text = SRC_JS.read_text(encoding="utf-8")
    assert "construction/estimate.html" in text
    assert 'label: "Estimate"' in text
    assert "estimate-detail.html" in text
    assert "isEstimateDetailPage" in text


def test_estimate_board_and_projects_pass_origin_query():
    board_src = REPO / "W3CRM-v3.0-13_September_2025/gulp/src/assets/js/usis-estimate-board.js"
    job_src = REPO / "W3CRM-v3.0-13_September_2025/gulp/src/assets/js/project-detail-job.js"
    api_src = REPO / "W3CRM-v3.0-13_September_2025/gulp/src/assets/js/usis-estimate-api.js"
    assert "&from=estimate" in board_src.read_text(encoding="utf-8")
    assert "&from=projects" in job_src.read_text(encoding="utf-8")
    assert "&from=estimate" in api_src.read_text(encoding="utf-8")
    if not DIST.is_dir():
        pytest.skip("gulp/dist not present")
    assert "&from=estimate" in (DIST / "assets/js/usis-estimate-board.js").read_text(
        encoding="utf-8"
    )
    assert "&from=projects\">Open estimate" in (DIST / "assets/js/project-detail-job.js").read_text(
        encoding="utf-8"
    )


def test_estimate_detail_page_keeps_back_to_estimates():
    if not DIST.is_dir():
        pytest.skip("gulp/dist not present")
    html = (DIST / "construction/estimate-detail.html").read_text(encoding="utf-8")
    assert "Back to Estimates" in html
    assert 'href="construction/estimate.html"' in html
    assert "usis-project-context.js?v=20260915b" in html


def test_breadcrumb_builder_routes_estimate_detail_through_estimate():
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
