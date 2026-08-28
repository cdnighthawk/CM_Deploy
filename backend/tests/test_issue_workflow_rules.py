"""Status transition rules for the Issues board (no database)."""
from app.api._issue_service import workflow_allows
from app.services.feedback import (
    CONFIRMED_MARKER,
    NOTIFIED_MARKER,
    inferred_tracker_status,
    refresh_tracker_from_github,
)


def test_resolution_advances_open_cards_but_not_closed():
    assert workflow_allows("New", "Pending Review") is True
    assert workflow_allows("In Progress", "Pending Review") is True
    assert workflow_allows("Closed", "Pending Review") is False


def test_confirm_and_reject():
    assert workflow_allows("Pending Review", "Closed") is True
    assert workflow_allows("Pending Review", "In Progress") is True
    assert workflow_allows("Closed", "In Progress") is True


def test_opened_does_not_reset_later_status():
    assert workflow_allows("New", "New") is False
    assert workflow_allows("In Progress", "New") is False
    assert workflow_allows("Pending Review", "New") is False
    assert workflow_allows("Closed", "New") is False


def test_infer_new_without_activity():
    status, _detail = inferred_tracker_status({"number": 1, "body": "", "state": "open"}, [])
    assert status == "New"


def test_infer_in_progress_from_work_comment_or_assignee():
    status, _detail = inferred_tracker_status(
        {"number": 1, "body": "", "state": "open"},
        [{"body": "Looking into this.", "user": {"login": "cdnighthawk"}}],
    )
    assert status == "In Progress"
    assigned, _detail = inferred_tracker_status(
        {"number": 2, "body": "", "state": "open", "assignees": [{"login": "cdnighthawk"}]},
        [],
    )
    assert assigned == "In Progress"


def test_infer_pending_review_and_closed():
    pending, _detail = inferred_tracker_status(
        {"number": 1, "body": "", "state": "open"},
        [{"body": "Resolution: Fixed the sort.", "user": {"login": "cdnighthawk"}}],
    )
    assert pending == "Pending Review"
    closed, _detail = inferred_tracker_status(
        {"number": 2, "body": "", "state": "closed"},
        [{"body": f"{CONFIRMED_MARKER}\nReporter confirmed."}],
    )
    assert closed == "Closed"
    notified, _detail = inferred_tracker_status(
        {"number": 3, "body": "", "state": "open"},
        [
            {"body": "Resolution: Fixed.", "user": {"login": "cdnighthawk"}},
            {"body": f"{NOTIFIED_MARKER}\nEmailed"},
        ],
    )
    assert notified == "Pending Review"


def test_refresh_skips_without_github_token():
    result = refresh_tracker_from_github(type("Cfg", (), {})())
    assert result["status"] == "skipped"
    assert result["reason"] == "not_configured"
