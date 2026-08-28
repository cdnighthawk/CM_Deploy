"""Create-RFI-from-issue builds a full project + issue query string (no database)."""
from __future__ import annotations

import uuid
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

from app.api._issue_service import _issue_rfi_prefill, _rfi_create_redirect


def test_issue_rfi_prefill_and_redirect_include_project_and_issue_fields():
    project_id = uuid.uuid4()
    issue_id = uuid.uuid4()
    row = SimpleNamespace(
        id=issue_id,
        project_id=project_id,
        title="Conduit clash at C-12",
        description="E-301 conflicts with M-208.",
        trade="Electrical",
        cbc_citation="26 05 33",
        sheet_number="E-301",
        cost_impact=1500,
        schedule_impact_days=3,
    )

    prefill = _issue_rfi_prefill(row)
    assert prefill["project_id"] == str(project_id)
    assert prefill["issue_id"] == str(issue_id)
    assert prefill["subject"] == "Conduit clash at C-12"
    assert prefill["question"] == "E-301 conflicts with M-208."
    assert prefill["drawing_number"] == "E-301"
    assert prefill["reference"] == "Electrical · 26 05 33"
    assert prefill["cost_impact"] == 1500
    assert prefill["schedule_impact_days"] == 3

    query = parse_qs(urlparse(_rfi_create_redirect(prefill)).query)
    assert query["project_id"] == [str(project_id)]
    assert query["subject"] == ["Conduit clash at C-12"]
    assert query["question"] == ["E-301 conflicts with M-208."]
    assert query["drawing_number"] == ["E-301"]
    assert query["reference"] == ["Electrical · 26 05 33"]
    assert query["cost_impact"] == ["1500"]
    assert query["schedule_impact_days"] == ["3"]


def test_issue_rfi_prefill_skips_generic_trade_and_empty_sheet():
    row = SimpleNamespace(
        id=uuid.uuid4(),
        project_id=None,
        title="Need clarification",
        description=None,
        trade="General",
        cbc_citation="",
        sheet_number="",
        cost_impact=None,
        schedule_impact_days=None,
    )
    prefill = _issue_rfi_prefill(row)
    assert prefill["question"] == "Need clarification"
    assert prefill["trade"] is None
    assert prefill["drawing_number"] is None
    assert prefill["reference"] is None
    query = parse_qs(urlparse(_rfi_create_redirect(prefill)).query)
    assert "project_id" not in query
    assert query["subject"] == ["Need clarification"]
    assert "drawing_number" not in query
    assert "trade" not in query
