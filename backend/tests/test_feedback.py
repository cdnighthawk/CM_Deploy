"""Employee report-a-problem intake, including the page the user was on."""
from __future__ import annotations

from types import SimpleNamespace

import httpx
import pytest

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
        page=parsed["page"],
        page_url=parsed["page_url"],
        page_title=parsed["page_title"],
    )
    assert "**Page:** /construction/leads.html" in body
    assert "**Page URL:** https://usis-cm.onrender.com/construction/leads.html?q=west" in body
    assert "**Page title:** Leads" in body


def test_feedback_requires_session(client, no_dev_admin):
    r = client.post("/api/v1/feedback", json={"title": "x", "details": "y" * 5})
    assert r.status_code == 401


def _signed_in(monkeypatch):
    monkeypatch.setattr(
        "app.api.v1.current_user",
        lambda: SimpleNamespace(
            user=SimpleNamespace(first_name="Sam", last_name="Lee", email="sam@t.com")
        ),
    )


def test_feedback_requires_title_and_details(client, monkeypatch):
    _signed_in(monkeypatch)
    r = client.post("/api/v1/feedback", json={"title": "", "details": ""})
    assert r.status_code == 400


def test_feedback_posts_page_url_to_github(client, monkeypatch):
    _signed_in(monkeypatch)
    captured = {}

    def fake_submit(**kwargs):
        captured.update(kwargs)
        return feedback_svc.SubmitResult(ok=True, status="created", message="Report sent.", issue_number=44)

    monkeypatch.setattr(feedback_svc, "submit_github_issue", fake_submit)

    r = client.post(
        "/api/v1/feedback",
        json={
            "kind": "bug",
            "title": "Save failed",
            "details": "The save button stays disabled.",
            "page": "/usis-dashboard-dark.html",
            "pageUrl": "https://usis-cm.onrender.com/usis-dashboard-dark.html",
            "pageTitle": "Dashboard",
        },
    )
    assert r.status_code == 200
    assert r.get_json()["issueNumber"] == 44
    assert "**Page:** /usis-dashboard-dark.html" in captured["body"]
    assert "**Page URL:** https://usis-cm.onrender.com/usis-dashboard-dark.html" in captured["body"]


def test_submit_skips_github_when_token_missing():
    result = feedback_svc.submit_github_issue(
        title="[bug] x",
        body="body",
        labels=["bug"],
        config=SimpleNamespace(GITHUB_FEEDBACK_TOKEN="", GITHUB_FEEDBACK_OWNER="cdnighthawk", GITHUB_FEEDBACK_REPO="CM_Deploy"),
        client=httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(500))),
    )
    assert result.status == "not_configured"
