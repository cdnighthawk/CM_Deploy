"""No-DB tests for the ingest estimate folder map."""
from __future__ import annotations

import uuid
from types import SimpleNamespace

from app.services.ingest_estimates import (
    estimate_matches_query,
    human_job_number,
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
        updated_at=None,
    )
    item = serialize_ingest_estimate(est, lead=None, projects={})
    assert item["id"] == str(est_id)
    assert item["job_number"] is None
    assert item["folder_path"] is None
    assert item["projects"] == []


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
