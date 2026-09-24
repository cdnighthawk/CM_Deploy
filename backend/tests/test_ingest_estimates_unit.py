"""No-DB tests for the ingest estimate folder map."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.services.ingest_estimates import (
    due_at_in_range,
    effective_due_at,
    estimate_matches_query,
    human_job_number,
    parse_due_bound,
    serialize_ingest_estimate,
)


def test_human_job_number_prefers_lead_then_project_skips_uuid():
    uid = str(uuid.uuid4())
    assert human_job_number(None, None) is None
    assert human_job_number("", uid) is None
    assert human_job_number(uid, "26061") == "26061"
    assert human_job_number("25270", "24000") == "25270"


def test_serialize_never_uses_estimate_uuid_as_job_number():
    est_id = uuid.uuid4()
    est = SimpleNamespace(
        id=est_id,
        name="Original Estimate",
        folder_path=None,
        folder_provision_status=None,
        folder_provisioned_at=None,
        is_current=True,
        lead_estimate_id=None,
        project_id=None,
        due_at=None,
        updated_at=None,
    )
    item = serialize_ingest_estimate(est, lead=None, projects={})
    assert item["id"] == str(est_id)
    assert item["job_number"] is None
    assert item["folder_path"] is None
    assert item["projects"] == []
    assert item["due_at"] is None


def test_serialize_uses_provisioned_folder_and_linked_project():
    job_id = uuid.uuid4()
    lead_id = uuid.uuid4()
    est_id = uuid.uuid4()
    job = SimpleNamespace(id=job_id, number="26061", name="Civic Center", deleted_at=None, status="planning")
    lead = SimpleNamespace(
        id=lead_id,
        number="26061",
        name="Civic Center",
        project_id=job_id,
        project=job,
        is_archived=False,
        workflow_bucket=None,
        submission_state="UNDECIDED",
        due_at=datetime(2026, 9, 30, 17, 0, tzinfo=timezone.utc),
    )
    est = SimpleNamespace(
        id=est_id,
        name="Original Estimate",
        folder_path=r"Y:\Estimates\26061 - Original Estimate",
        folder_provision_status="ready",
        folder_provisioned_at=None,
        is_current=True,
        lead_estimate_id=lead_id,
        project_id=job_id,
        due_at=None,
        updated_at=None,
    )
    item = serialize_ingest_estimate(est, lead=lead, projects={job_id: job})
    assert item["job_number"] == "26061"
    assert item["folder_path"] == r"Y:\Estimates\26061 - Original Estimate"
    assert item["folder_provision_status"] == "ready"
    assert item["project_id"] == str(job_id)
    assert item["lead_estimate_id"] == str(lead_id)
    assert "26061" in item["folder_hints"]
    assert item["projects"][0]["number"] == "26061"
    assert item["due_at"] == "2026-09-30T17:00:00+00:00"


def test_effective_due_prefers_estimate_then_lead():
    lead_due = datetime(2026, 8, 1, tzinfo=timezone.utc)
    est_due = datetime(2026, 9, 15, tzinfo=timezone.utc)
    lead = SimpleNamespace(due_at=lead_due)
    est = SimpleNamespace(due_at=est_due)
    assert effective_due_at(est, lead) == est_due
    assert effective_due_at(SimpleNamespace(due_at=None), lead) == lead_due
    assert effective_due_at(SimpleNamespace(due_at=None), None) is None


def test_parse_due_bound_date_only_and_datetime():
    start = parse_due_bound("2026-08-21", label="due_from")
    assert start == datetime(2026, 8, 21, tzinfo=timezone.utc)
    end = parse_due_bound("2026-09-20", label="due_to", end_of_day=True)
    assert end == datetime(2026, 9, 20, 23, 59, 59, 999999, tzinfo=timezone.utc)
    instant = parse_due_bound("2026-09-20T17:00:00Z", label="due_from")
    assert instant == datetime(2026, 9, 20, 17, 0, tzinfo=timezone.utc)
    assert parse_due_bound("", label="due_from") is None
    with pytest.raises(ValueError, match="due_from"):
        parse_due_bound("not-a-date", label="due_from")


def test_due_at_in_range_supports_30_day_through_future():
    due_from = parse_due_bound("2026-08-21", label="due_from")
    past = datetime(2026, 8, 1, tzinfo=timezone.utc)
    recent = datetime(2026, 8, 22, tzinfo=timezone.utc)
    future = datetime(2027, 1, 1, tzinfo=timezone.utc)
    assert due_at_in_range(None, due_from=None, due_to=None) is True
    assert due_at_in_range(None, due_from=due_from, due_to=None) is False
    assert due_at_in_range(past, due_from=due_from, due_to=None) is False
    assert due_at_in_range(recent, due_from=due_from, due_to=None) is True
    assert due_at_in_range(future, due_from=due_from, due_to=None) is True
    due_to = parse_due_bound("2026-09-20", label="due_to", end_of_day=True)
    same_day = datetime(2026, 9, 20, 18, 0, tzinfo=timezone.utc)
    after = datetime(2026, 9, 21, tzinfo=timezone.utc)
    assert due_at_in_range(same_day, due_from=due_from, due_to=due_to) is True
    assert due_at_in_range(after, due_from=due_from, due_to=due_to) is False


def test_estimate_matches_accdocs_project_key_and_proj_number():
    item = {
        "id": "aaa",
        "job_number": "240142",
        "name": "Turner – Bid Set",
        "folder_path": r"Y:\Estimates\240142 - Turner Bid Set",
        "project_id": "bbb",
        "project_number": "240142",
        "project_name": "Turner Bid Civic",
        "lead_estimate_id": None,
        "lead_number": None,
        "lead_name": None,
        "folder_hints": ["240142", "Turner Bid Civic"],
        "projects": [{"id": "bbb", "number": "240142", "name": "Turner Bid Civic"}],
    }
    assert estimate_matches_query(item, "PROJ-2024-0142")
    assert estimate_matches_query(item, "240142")
    assert estimate_matches_query(item, "Turner Bid Civic")
    assert not estimate_matches_query(item, "999999-nope")
