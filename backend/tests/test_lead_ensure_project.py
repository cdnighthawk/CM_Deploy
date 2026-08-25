"""Lead/estimate workspace project for the shared Specs book."""
from __future__ import annotations

import uuid

from sqlalchemy import select

from app.extensions import db
from app.models import LeadEstimate, Project, SpecSection


def test_ensure_project_creates_planning_workspace(client):
    eid = "test-ensure-proj-" + uuid.uuid4().hex[:10]
    number = "SW-" + uuid.uuid4().hex[:8]
    with client.application.app_context():
        le = LeadEstimate(external_id=eid, name="Specs workspace lead", number=number)
        db.session.add(le)
        db.session.commit()
        lead_id = str(le.id)

    opened = client.get(f"/api/v1/lead-estimates/{eid}")
    assert opened.status_code == 200
    opened_pid = opened.get_json()["item"]["project_id"]
    assert opened_pid

    first = client.post(f"/api/v1/lead-estimates/{eid}/ensure-project")
    assert first.status_code == 200, first.get_data(as_text=True)
    body = first.get_json()
    pid = body["project_id"]
    assert pid == opened_pid
    assert body["item"]["project_id"] == pid

    with client.application.app_context():
        proj = db.session.get(Project, uuid.UUID(pid))
        assert proj is not None
        assert proj.status == "planning"
        assert proj.name == "Specs workspace lead"

    again = client.post(f"/api/v1/lead-estimates/{lead_id}/ensure-project")
    assert again.status_code == 200
    assert again.get_json()["project_id"] == pid

    listed = client.get(f"/api/v1/projects/{pid}/rfi-lookups/spec_sections")
    assert listed.status_code == 200
    assert listed.get_json()["items"] == []

    added = client.post(
        f"/api/v1/projects/{pid}/spec-sections/from-catalog",
        json={"codes": ["08 71 00"]},
    )
    assert added.status_code == 201, added.get_data(as_text=True)
    items = added.get_json()["items"]
    assert items
    assert items[0]["code"] == "08 71 00"

    with client.application.app_context():
        rows = db.session.scalars(select(SpecSection).where(SpecSection.project_id == uuid.UUID(pid))).all()
        assert len(rows) == 1


def test_ensure_project_reuses_job_with_same_number(client):
    number = "N-" + uuid.uuid4().hex[:8]
    with client.application.app_context():
        project = Project(name="Existing job", number=number, status="active")
        db.session.add(project)
        db.session.flush()
        pid = str(project.id)
        lead = LeadEstimate(
            external_id="le-" + uuid.uuid4().hex[:10],
            name="Unlinked lead",
            number=number,
            submission_state="UNDECIDED",
        )
        db.session.add(lead)
        db.session.flush()
        lid = str(lead.id)
        db.session.commit()

    detail = client.get(f"/api/v1/lead-estimates/{lid}")
    assert detail.status_code == 200
    item = detail.get_json()["item"]
    assert item["project_id"] == pid
    assert item.get("drawing_project_id") == pid

    ensured = client.post(f"/api/v1/lead-estimates/{lid}/ensure-project")
    assert ensured.status_code == 200, ensured.get_data(as_text=True)
    body = ensured.get_json()
    assert body["project_id"] == pid
    assert body["item"]["project_id"] == pid
    assert body["item"].get("drawing_project_id") == pid


def test_award_promotes_planning_workspace(client):
    eid = "test-award-ws-" + uuid.uuid4().hex[:10]
    with client.application.app_context():
        le = LeadEstimate(external_id=eid, name="Award after specs", number="AW-1")
        db.session.add(le)
        db.session.commit()

    ensured = client.post(f"/api/v1/lead-estimates/{eid}/ensure-project")
    pid = ensured.get_json()["project_id"]
    awarded = client.post(f"/api/v1/lead-estimates/{eid}/award", json={})
    assert awarded.status_code == 200, awarded.get_data(as_text=True)
    item = awarded.get_json()["item"]
    assert item["project_id"] == pid
    assert item["crm_stage"] == "Awarded"

    with client.application.app_context():
        proj = db.session.get(Project, uuid.UUID(pid))
        assert proj is not None
        assert proj.status == "active"
