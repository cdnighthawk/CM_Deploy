"""Top header Issues control sits next to Open AI assistant on staff shells."""
from __future__ import annotations

from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
GULP = REPO / "W3CRM-v3.0-13_September_2025/gulp"
SRC_HEADER = GULP / "src" / "elements" / "header-construction.html"
DIST = GULP / "dist"
SUCCESS_PAGES = (
    DIST / "usis-dashboard-dark.html",
    DIST / "construction" / "projects.html",
    DIST / "construction" / "estimate.html",
)
CHAT_MARK = 'class="nav-link border-0 bg-transparent px-2 py-1 btn-chatbox"'
ISSUES_HREF = 'href="construction/issues.html"'
ISSUES_I18N = 'data-i18n="Issues"'
REPORT_MARK = "data-usis-report-problem"


def _assert_header_issues(html: str, path: Path) -> None:
    header_idx = html.find('<ul class="navbar-nav header-right">')
    assert header_idx != -1, f"{path} missing header-right"
    chat_idx = html.find(CHAT_MARK, header_idx)
    issues_idx = html.find(ISSUES_HREF, header_idx)
    assert chat_idx != -1, f"{path} missing Open AI assistant control"
    assert issues_idx != -1, f"{path} missing Issues href in header"
    between = html[min(issues_idx, chat_idx) : max(issues_idx, chat_idx)]
    assert between.count("<li") <= 2, f"{path} Issues is not adjacent to Open AI assistant"
    snippet = html[issues_idx - 220 : issues_idx + 280]
    assert 'data-usis-module="user_admin"' not in snippet
    assert 'data-usis-module="projects"' in snippet
    assert ISSUES_I18N in html
    assert REPORT_MARK in html
    assert "usis-report-problem-btn" in html


def test_shared_construction_header_has_issues_next_to_assistant():
    html = SRC_HEADER.read_text(encoding="utf-8")
    _assert_header_issues(html, SRC_HEADER)


@pytest.mark.parametrize("path", SUCCESS_PAGES, ids=["home", "projects", "estimate"])
def test_staff_shells_show_header_issues_next_to_assistant(path: Path):
    if not DIST.is_dir():
        pytest.skip("gulp/dist not present")
    if not path.is_file():
        pytest.skip(f"{path} not present")
    html = path.read_text(encoding="utf-8")
    _assert_header_issues(html, path)
    # Sidebar Issues from PR #48 stays in place.
    assert html.count(ISSUES_HREF) >= 2
    assert '<span class="nav-text" data-i18n="Issues">Issues</span>' in html
