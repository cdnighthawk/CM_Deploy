"""Unit tests for Textura client helpers (no database)."""
from __future__ import annotations

from app.integrations.textura_client import _normalize_record_list, _uri_to_job_path


def test_normalize_record_list_array():
    rows = [{"id": "1"}, {"id": "2"}]
    assert _normalize_record_list(rows) == rows


def test_normalize_record_list_wrapped():
    payload = {"projects": [{"id": "9", "projectName": "X"}]}
    out = _normalize_record_list(payload)
    assert len(out) == 1
    assert out[0]["id"] == "9"


def test_uri_to_job_path_relative():
    assert _uri_to_job_path("/api/v1/export/invoices/82", "https://example.com/ebis/api") == "/api/v1/export/invoices/82"


def test_uri_to_job_path_absolute_same_host():
    base = "https://services.texturacorp.com/ebis/api"
    uri = "https://services.texturacorp.com/ebis/api/v1/export/invoices/82"
    assert _uri_to_job_path(uri, base) == "/ebis/api/v1/export/invoices/82" or _uri_to_job_path(uri, base).endswith("/invoices/82")
