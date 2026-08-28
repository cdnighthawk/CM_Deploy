"""Import existing GitHub hub reports into tracker_issues."""
from __future__ import annotations

from app.extensions import db
from app.models.issue import Issue
from app.services.github_issue_import import (
    description_from_github,
    github_source_id,
    import_bundled_github_issues,
    import_github_issues,
    load_bundled_github_issues,
)


def test_description_extracts_details_and_keeps_github_link():
    text = description_from_github(
        {
            "number": 3,
            "html_url": "https://github.com/cdnighthawk/CM_Deploy/issues/3",
            "body": (
                "## Something broke\n\n"
                "### Where it happened\n"
                "**Page:** /construction/projects.html\n"
                "**Page URL:** https://www.usiscm.com/construction/projects.html\n\n"
                "### Reporter\n"
                "**From:** Marcos Ibarra\n"
                "**Email:** mibarra@gousis.com\n\n"
                "### Details\n"
                "I don't have access to the Projects section.\n"
            ),
        }
    )
    assert text.startswith("I don't have access to the Projects section.")
    assert "Page: /construction/projects.html" in text
    assert "Reported by: Marcos Ibarra" in text
    assert "GitHub: https://github.com/cdnighthawk/CM_Deploy/issues/3" in text


def test_bundled_snapshot_has_all_hub_reports():
    items = load_bundled_github_issues()
    assert {item["number"] for item in items} == set(range(1, 17))


def test_import_github_issue_is_idempotent(flask_app):
    payload = [
        {
            "number": 9001,
            "title": "[bug] Imported sample — leads.html",
            "body": (
                "## Something broke\n\n"
                "### Where it happened\n"
                "**Page:** /construction/leads.html\n"
                "**Page URL:** https://www.usiscm.com/construction/leads.html\n\n"
                "### Reporter\n"
                "**From:** Test User\n"
                "**Email:** nobody@example.com\n\n"
                "### Details\n"
                "The column would not sort.\n\n"
                "---\n\nLeave a comment"
            ),
            "state": "open",
            "html_url": "https://github.com/cdnighthawk/CM_Deploy/issues/9001",
            "created_at": "2026-08-24T22:00:00Z",
            "closed_at": None,
            "labels": ["bug", "from-hub"],
        }
    ]
    with flask_app.app_context():
        first = import_github_issues(payload)
        second = import_github_issues(payload)
        row = (
            db.session.query(Issue)
            .filter_by(source_type="feedback", source_id=github_source_id(9001))
            .one()
        )
        assert first["created"] == 1
        assert second["created"] == 0
        assert second["updated"] == 1
        assert row.title.startswith("[bug] Imported sample")
        assert row.severity == "Major"
        assert row.status == "New"
        assert "The column would not sort." in (row.description or "")
        assert row.linked_change_order_id == "github:9001"


def test_bundled_github_snapshot_imports(flask_app):
    with flask_app.app_context():
        summary = import_bundled_github_issues()
        assert summary["created"] + summary["updated"] >= 16
        calendar = (
            db.session.query(Issue)
            .filter_by(source_type="feedback", source_id=github_source_id(14))
            .one()
        )
        assert "assign someone in the calendar" in (calendar.description or "").lower()
        closed = (
            db.session.query(Issue)
            .filter_by(source_type="feedback", source_id=github_source_id(10))
            .one()
        )
        assert closed.status == "Closed"
        bilingual = (
            db.session.query(Issue)
            .filter_by(source_type="feedback", source_id=github_source_id(2))
            .one()
        )
        assert "spanish" in (bilingual.description or "").lower()
