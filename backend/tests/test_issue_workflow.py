"""Tracker cards move with GitHub resolution, confirm, assign, and reopen."""
from __future__ import annotations

import uuid

import httpx

from app.api._issue_service import (
    apply_github_workflow,
    assign_issue,
    find_feedback_by_github_number,
)
from app.api._perms import CurrentUser
from app.extensions import db
from app.models import User
from app.models.issue import Issue
from app.services import feedback as feedback_svc
from app.services.github_issue_import import github_source_id, import_github_issues


ISSUE_BODY = """## Something broke

### Reporter
**From:** Sam Lee
**Email:** sam@gousis.com

### Details
The column would not sort.
"""


def _payload(number: int = 9101, **extra):
    item = {
        "number": number,
        "title": "[bug] Workflow sample",
        "body": ISSUE_BODY,
        "state": "open",
        "html_url": f"https://github.com/cdnighthawk/CM_Deploy/issues/{number}",
        "created_at": "2026-08-24T22:00:00Z",
        "closed_at": None,
        "labels": ["bug", "from-hub"],
    }
    item.update(extra)
    return item


def _seed(number: int = 9101) -> Issue:
    import_github_issues([_payload(number)])
    return find_feedback_by_github_number(number)


def _cu(user: User | None = None) -> CurrentUser:
    return CurrentUser(user=user, role_codes=frozenset(), granular=frozenset(), is_dev_admin=True)


def test_resolution_comment_moves_card_to_pending_review(flask_app):
    with flask_app.app_context():
        row = _seed(9101)
        assert row.status == "New"

        def handler(request: httpx.Request) -> httpx.Response:
            if request.method == "GET":
                return httpx.Response(
                    200,
                    json=[{"body": "Resolution: Sorted columns.", "user": {"login": "cdnighthawk"}}],
                )
            return httpx.Response(201, json={"id": 1})

        result = feedback_svc.handle_github_feedback_event(
            event="issue_comment",
            payload={
                "action": "created",
                "comment": {"body": "Resolution: Sorted columns."},
                "issue": _payload(9101),
                "repository": {"full_name": "cdnighthawk/CM_Deploy"},
            },
            config=type(
                "Cfg",
                (),
                {
                    "GITHUB_FEEDBACK_TOKEN": "tok",
                    "GITHUB_FEEDBACK_OWNER": "cdnighthawk",
                    "GITHUB_FEEDBACK_REPO": "CM_Deploy",
                },
            )(),
            send_email=lambda **_kwargs: {"sent": True, "dry_run": False, "error": None},
            confirm_base_url="https://www.usiscm.com/usis-issue-confirm.html",
            secret_key="test-secret-key",
            client=httpx.Client(transport=httpx.MockTransport(handler)),
        )
        assert result["status"] == "sent"
        assert find_feedback_by_github_number(9101).status == "Pending Review"


def test_confirm_close_and_reject_move_card(flask_app):
    with flask_app.app_context():
        _seed(9102)
        apply_github_workflow(9102, "Pending Review", detail="Ready")

        comments = [{"body": "Resolution: Done.", "user": {"login": "cdnighthawk"}}]

        def close_handler(request: httpx.Request) -> httpx.Response:
            if request.method == "GET" and "/comments" in str(request.url):
                return httpx.Response(200, json=comments)
            if request.method == "GET":
                return httpx.Response(200, json=_payload(9102))
            if request.method == "POST":
                return httpx.Response(201, json={"id": 2})
            return httpx.Response(200, json={})

        token = feedback_svc.mint_confirm_token(
            issue_number=9102, email="sam@gousis.com", secret_key="test-secret-key"
        )
        closed = feedback_svc.confirm_issue_from_token(
            token=token,
            action="close",
            config=type(
                "Cfg",
                (),
                {
                    "GITHUB_FEEDBACK_TOKEN": "tok",
                    "GITHUB_FEEDBACK_OWNER": "cdnighthawk",
                    "GITHUB_FEEDBACK_REPO": "CM_Deploy",
                },
            )(),
            secret_key="test-secret-key",
            client=httpx.Client(transport=httpx.MockTransport(close_handler)),
        )
        assert closed["status"] == "closed"
        assert find_feedback_by_github_number(9102).status == "Closed"

        def reject_handler(request: httpx.Request) -> httpx.Response:
            if request.method == "GET" and "/comments" in str(request.url):
                return httpx.Response(200, json=comments)
            if request.method == "GET":
                return httpx.Response(200, json=_payload(9103))
            if request.method == "POST":
                return httpx.Response(201, json={"id": 3})
            return httpx.Response(200, json={})

        _seed(9103)
        apply_github_workflow(9103, "Pending Review", detail="Ready")
        reject_token = feedback_svc.mint_confirm_token(
            issue_number=9103, email="sam@gousis.com", secret_key="test-secret-key"
        )
        rejected = feedback_svc.confirm_issue_from_token(
            token=reject_token,
            action="reject",
            config=type(
                "Cfg",
                (),
                {
                    "GITHUB_FEEDBACK_TOKEN": "tok",
                    "GITHUB_FEEDBACK_OWNER": "cdnighthawk",
                    "GITHUB_FEEDBACK_REPO": "CM_Deploy",
                },
            )(),
            secret_key="test-secret-key",
            client=httpx.Client(transport=httpx.MockTransport(reject_handler)),
        )
        assert rejected["status"] == "rejected"
        assert find_feedback_by_github_number(9103).status == "In Progress"


def test_assign_advances_new_to_in_progress(flask_app):
    with flask_app.app_context():
        row = _seed(9104)
        assignee = User(email="assignee_" + uuid.uuid4().hex[:8] + "@t.com", first_name="A", last_name="S")
        db.session.add(assignee)
        db.session.flush()
        updated = assign_issue(row.id, assignee.id, _cu())
        assert updated["status"] == "In Progress"
        assert updated["assignee_id"] == str(assignee.id)


def test_opened_webhook_creates_new_card(flask_app):
    with flask_app.app_context():
        result = feedback_svc.handle_github_feedback_event(
            event="issues",
            payload={
                "action": "opened",
                "issue": _payload(9105),
                "repository": {"full_name": "cdnighthawk/CM_Deploy"},
            },
            config=type(
                "Cfg",
                (),
                {
                    "GITHUB_FEEDBACK_TOKEN": "tok",
                    "GITHUB_FEEDBACK_OWNER": "cdnighthawk",
                    "GITHUB_FEEDBACK_REPO": "CM_Deploy",
                },
            )(),
            send_email=lambda **_kwargs: {"sent": True},
        )
        assert result["status"] == "tracked"
        created = find_feedback_by_github_number(9105)
        assert created is not None
        assert created.status == "New"
        assert created.source_id == github_source_id(9105)


def test_resolution_does_not_reopen_closed_card(flask_app):
    with flask_app.app_context():
        _seed(9106)
        apply_github_workflow(9106, "Closed", detail="Done")
        apply_github_workflow(9106, "Pending Review", detail="Late comment")
        assert find_feedback_by_github_number(9106).status == "Closed"
