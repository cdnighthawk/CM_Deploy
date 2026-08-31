"""Tests for /api/v1/ai ingest routes (Grok behind the company API)."""
from __future__ import annotations

import uuid
from unittest.mock import patch

from app.ai.grok_client import ChatCompletionResult


def test_package_classify_not_configured(client, monkeypatch):
    monkeypatch.setenv("USIS_AI_ENABLED", "0")
    monkeypatch.delenv("USIS_XAI_API_KEY", raising=False)
    r = client.post(
        "/api/v1/ai/package-classify",
        json={"item": {"files": []}},
    )
    assert r.status_code == 503


def test_package_classify_returns_item(client, monkeypatch):
    monkeypatch.setenv("USIS_AI_ENABLED", "1")
    monkeypatch.setenv("USIS_XAI_API_KEY", "test-key")
    sid = str(uuid.uuid4())
    fake = ChatCompletionResult(
        content='{"files":[{"sourceId":"%s","type":"Drawing","revision":"Addendum 1","confidence":0.91,"needsReview":false}]}'
        % sid
    )
    with patch("app.ai.ingest_api.chat_completion", return_value=fake):
        r = client.post(
            "/api/v1/ai/package-classify",
            json={
                "item": {
                    "sessionDefaultRevision": "Bid Set",
                    "folders": [{"relativePath": "Addendum 1", "name": "Addendum 1"}],
                    "files": [
                        {
                            "sourceId": sid,
                            "relativePath": "Addendum 1/A-101.pdf",
                            "fileName": "A-101.pdf",
                            "localType": "Other",
                            "localRevision": "Bid Set",
                        }
                    ],
                }
            },
        )
    assert r.status_code == 200
    item = r.get_json()["item"]
    assert item["files"][0]["sourceId"] == sid
    assert item["files"][0]["type"] == "Drawing"
    assert item["files"][0]["revision"] == "Addendum 1"


def test_sheet_identity_returns_items(client, monkeypatch):
    monkeypatch.setenv("USIS_AI_ENABLED", "1")
    monkeypatch.setenv("USIS_XAI_API_KEY", "test-key")
    rid = str(uuid.uuid4())
    fake = ChatCompletionResult(
        content='{"items":[{"rowId":"%s","sheetNumber":"A-101","sheetTitle":"FIRST FLOOR PLAN","revisionLabel":"Rev 1","confidence":0.92,"needsReview":false}]}'
        % rid
    )
    with patch("app.ai.ingest_api.chat_completion", return_value=fake):
        r = client.post(
            "/api/v1/ai/sheet-identity",
            json={
                "items": [
                    {
                        "rowId": rid,
                        "sourceFileName": "BidSet.pdf",
                        "sourcePage": 12,
                        "pageLabel": "12",
                    }
                ]
            },
        )
    assert r.status_code == 200
    items = r.get_json()["items"]
    assert items[0]["rowId"] == rid
    assert items[0]["sheetNumber"] == "A-101"
    assert items[0]["sheetTitle"] == "FIRST FLOOR PLAN"


def test_spec_sections_returns_item(client, monkeypatch):
    monkeypatch.setenv("USIS_AI_ENABLED", "1")
    monkeypatch.setenv("USIS_XAI_API_KEY", "test-key")
    fake = ChatCompletionResult(
        content='{"sections":[{"sectionNumber":"26 05 00","sectionTitle":"COMMON WORK RESULTS","startPage":41,"endPage":48,"confidence":0.88}]}'
    )
    with patch("app.ai.ingest_api.chat_completion", return_value=fake):
        r = client.post(
            "/api/v1/ai/spec-sections",
            json={
                "item": {
                    "fileName": "ProjectManual.pdf",
                    "pageCount": 80,
                    "pages": [{"page": 41, "textExcerpt": "SECTION 26 05 00"}],
                }
            },
        )
    assert r.status_code == 200
    sections = r.get_json()["item"]["sections"]
    assert sections[0]["sectionNumber"] == "26 05 00"
    assert sections[0]["startPage"] == 41
