"""Regression: Dashboard flagged-mail links must open that message in Inbox."""
from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
GULP_SRC = REPO / "W3CRM-v3.0-13_September_2025" / "gulp" / "src" / "assets" / "js"


def test_dashboard_flagged_mail_href_includes_message_id():
    src = (GULP_SRC / "usis-dashboard-ops.js").read_text(encoding="utf-8")
    assert 'item.kind === "flagged_mail"' in src
    assert "usis-email.html?id=" in src
    assert "encodeURIComponent(id)" in src
    assert "https://to-do.office.com/tasks" in src


def test_inbox_opens_message_from_query_id():
    src = (GULP_SRC / "usis-email.js").read_text(encoding="utf-8")
    assert "function requestedMessageId" in src
    assert 'q.get("id")' in src
    assert "openMessage(deepId)" in src
    assert "function openMessage(id, rowBtn)" in src
