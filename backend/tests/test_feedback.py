"""Employee report-a-problem intake now saves to the internal issues tracker."""
from __future__ import annotations

import uuid
from types import SimpleNamespace

import httpx
import pytest

from app.extensions import db
from app.models import User
from app.models.issue import Issue
from app.services import feedback as feedback_svc


@pytest.fixture
def no_dev_admin(monkeypatch):
    monkeypatch.setenv("USIS_API_DEV_ALLOW_ANY", "0")


def test_parse_includes_page_in_title_and_fields():
    parsed = feedback_svc.parse_feedback_input(
        {
            "kind": "bug",
            "title": "Table will not sort",
            "details": "Clicking the header does nothing.",
            "page": "/construction/leads.html",
            "pageUrl": "https://usis-cm.onrender.com/construction/leads.html?q=west",
            "pageTitle": "Leads",
        }
    )
    assert "error" not in parsed
    assert parsed["page"] == "/construction/leads.html"
    assert parsed["page_url"].endswith("leads.html?q=west")
    assert parsed["title"].endswith(" — leads.html")
    body = feedback_svc.build_issue_body(
        kind=parsed["kind"],
        details=parsed["details"],
        reporter_email="sam@gousis.com",
        page=parsed["page"],
        page_url=parsed["page_url"],
        page_title=parsed["page_title"],
    )
    assert "**Page:** /construction/leads.html" in body
    assert "**Page URL:** https://usis-cm.onrender.com/construction/leads.html?q=west" in body
    assert "**Page title:** Leads" in body
    assert "<!-- usis-reporter-email: sam@gousis.com -->" in body
    assert "Resolution:" in body


def test_parse_general_omits_page_and_uses_sitewide_body():
    parsed = feedback_svc.parse_feedback_input(
        {
            "kind": "general",
            "title": "Add a dark mode toggle back",
            "details": "The header feels too sparse after the cleanup.",
            "page": "/construction/leads.html",
            "pageUrl": "https://usis-cm.onrender.com/construction/leads.html",
            "pageTitle": "Leads",
        }
    )
    assert "error" not in parsed
    assert parsed["kind"]["value"] == "general"
    assert parsed["page"] == ""
    assert parsed["page_url"] == ""
    assert parsed["page_title"] == ""
    assert parsed["title"] == "[idea] Add a dark mode toggle back"
    assert " — " not in parsed["title"]
    assert feedback_svc.github_labels_for(parsed["kind"]) == ["enhancement", "site-wide", "from-hub"]
    body = feedback_svc.build_issue_body(
        kind=parsed["kind"],
        details=parsed["details"],
        page=parsed["page"],
        page_url=parsed["page_url"],
        page_title=parsed["page_title"],
    )
    assert "**Page:** Site-wide" in body
    assert "leads.html" not in body
    assert "**Page URL:**" not in body


def test_feedback_requires_session(client, no_dev_admin):
    r = client.post("/api/v1/feedback", json={"title": "x", "details": "y" * 5})
    assert r.status_code == 401


def _staff_headers(flask_app, email_prefix: str = "fb") -> dict[str, str]:
    with flask_app.app_context():
        user = User(
            email=f"{email_prefix}_{uuid.uuid4().hex[:8]}@t.com",
            first_name="Sam",
            last_name="Lee",
            is_active=True,
        )
        db.session.add(user)
        db.session.commit()
        return {"X-Usis-User-Id": str(user.id)}


def test_feedback_requires_title_and_details(client, flask_app, no_dev_admin):
    r = client.post(
        "/api/v1/feedback",
        json={"title": "", "details": ""},
        headers=_staff_headers(flask_app, "need"),
    )
    assert r.status_code == 400


def test_feedback_saves_to_internal_tracker(client, flask_app, no_dev_admin):
    hdr = _staff_headers(flask_app, "bug")
    r = client.post(
        "/api/v1/feedback",
        json={
            "kind": "bug",
            "title": "Save failed",
            "details": "The save button stays disabled.",
            "page": "/usis-dashboard-dark.html",
            "pageUrl": "https://www.usiscm.com/usis-dashboard-dark.html",
            "pageTitle": "Dashboard",
        },
        headers=hdr,
    )
    assert r.status_code == 201, r.get_data(as_text=True)
    body = r.get_json()
    assert body["issueId"]
    assert "Issues page" in body["message"]
    with flask_app.app_context():
        row = db.session.get(Issue, uuid.UUID(body["issueId"]))
        assert row is not None
        assert row.source_type == "feedback"
        assert row.severity == "Major"
        assert "The save button stays disabled." in (row.description or "")
        assert "usis-dashboard-dark.html" in (row.description or "")


def test_feedback_general_stays_sitewide(client, flask_app, no_dev_admin):
    hdr = _staff_headers(flask_app, "idea")
    r = client.post(
        "/api/v1/feedback",
        json={
            "kind": "general",
            "title": "Need a company-wide search",
            "details": "I want to find a contact from any screen.",
            "page": "/construction/leads.html",
            "pageUrl": "https://www.usiscm.com/construction/leads.html",
        },
        headers=hdr,
    )
    assert r.status_code == 201, r.get_data(as_text=True)
    issue_id = r.get_json()["issueId"]
    with flask_app.app_context():
        row = db.session.get(Issue, uuid.UUID(issue_id))
        assert row is not None
        assert row.source_type == "feedback"
        assert row.severity == "Minor"
        assert row.title == "[idea] Need a company-wide search"
        assert "leads.html" not in (row.description or "")


def test_submit_skips_github_when_token_missing():
    result = feedback_svc.submit_github_issue(
        title="[bug] x",
        body="body",
        labels=["bug"],
        config=SimpleNamespace(GITHUB_FEEDBACK_TOKEN="", GITHUB_FEEDBACK_OWNER="cdnighthawk", GITHUB_FEEDBACK_REPO="CM_Deploy"),
        client=httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(500))),
    )
    assert result.status == "not_configured"
