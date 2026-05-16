"""Reports catalog and HTML render routes (unit-level; no DB required for render tests)."""
from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest

from app.api import _document_render_service as document_render_svc


@pytest.fixture
def fake_lead():
    lid = uuid.uuid4()
    return SimpleNamespace(
        id=lid,
        external_id="test-report-lead",
        name="Report lead",
        number="R-1",
        trade_name="Doors",
    )


def test_reports_catalog_shape(client):
    r = client.get("/api/v1/reports/catalog")
    assert r.status_code == 200
    body = r.get_json()
    assert body.get("entity") == "reports_catalog"
    items = body.get("items") or []
    assert len(items) >= 3
    est = next((x for x in items if x.get("id") == "estimate_summary"), None)
    assert est is not None
    assert est.get("kind") == "html_route"
    assert "{lead_identifier}" in (est.get("url_template") or "")
    params = est.get("required_params") or []
    assert any(p.get("name") == "lead_identifier" for p in params)
    qr = next((x for x in items if x.get("id") == "quote_report"), None)
    assert qr is not None
    assert qr.get("kind") == "html_route"
    assert "/render/quote-report" in (qr.get("url_template") or "")
    col_opts = qr.get("column_options") or []
    assert len(col_opts) >= 5
    assert any(c.get("id") == "notes" for c in col_opts)


def test_render_estimate_summary_html(client, monkeypatch, fake_lead):
    import app.api.v1 as v1

    monkeypatch.setattr(
        v1, "_resolve_lead", lambda ident: fake_lead if ident == "test-report-lead" else None
    )
    monkeypatch.setattr(
        document_render_svc,
        "render_estimate_summary_html",
        lambda lead, cu, *, line_limit=500: "<html><body>estimate-summary</body></html>",
    )
    r = client.get("/api/v1/lead-estimates/test-report-lead/render/estimate-summary")
    assert r.status_code == 200
    assert "text/html" in (r.mimetype or "")
    assert "estimate-summary" in r.get_data(as_text=True)


def test_render_door_schedule_report_html(client, monkeypatch, fake_lead):
    import app.api.v1 as v1

    monkeypatch.setattr(
        v1, "_resolve_lead", lambda ident: fake_lead if ident == "test-report-lead" else None
    )
    monkeypatch.setattr(
        document_render_svc,
        "render_door_schedule_report_html",
        lambda lead, cu: "<html><body>door-schedule</body></html>",
    )
    r = client.get("/api/v1/lead-estimates/test-report-lead/render/door-schedule-html")
    assert r.status_code == 200
    assert "text/html" in (r.mimetype or "")
    assert "door-schedule" in r.get_data(as_text=True)


def test_render_estimate_summary_404(client, monkeypatch):
    import app.api.v1 as v1

    monkeypatch.setattr(v1, "_resolve_lead", lambda _s: None)
    r = client.get("/api/v1/lead-estimates/nonexistent-external-id-xyz/render/estimate-summary")
    assert r.status_code == 404


def test_render_quote_report_html(client, monkeypatch, fake_lead):
    import app.api.v1 as v1

    monkeypatch.setattr(
        v1, "_resolve_lead", lambda ident: fake_lead if ident == "test-report-lead" else None
    )
    monkeypatch.setattr(
        document_render_svc,
        "render_quote_report_html",
        lambda lead, cu, *, columns_raw=None, line_limit=500: "<html><body>quote-report</body></html>",
    )
    r = client.get("/api/v1/lead-estimates/test-report-lead/render/quote-report")
    assert r.status_code == 200
    assert "text/html" in (r.mimetype or "")
    assert "quote-report" in r.get_data(as_text=True)


def test_render_quote_report_passes_columns_query(client, monkeypatch, fake_lead):
    import app.api.v1 as v1

    captured: dict = {}

    def _fake(lead, cu, *, columns_raw=None, line_limit=500):
        captured["columns_raw"] = columns_raw
        captured["line_limit"] = line_limit
        return "<html></html>"

    monkeypatch.setattr(
        v1, "_resolve_lead", lambda ident: fake_lead if ident == "test-report-lead" else None
    )
    monkeypatch.setattr(document_render_svc, "render_quote_report_html", _fake)
    r = client.get(
        "/api/v1/lead-estimates/test-report-lead/render/quote-report"
        "?columns=description,notes&line_limit=100"
    )
    assert r.status_code == 200
    assert captured.get("columns_raw") == "description,notes"
    assert captured.get("line_limit") == 100
