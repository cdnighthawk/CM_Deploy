"""Lead/estimate workspace project for the shared Specs book."""
from __future__ import annotations

import uuid

from sqlalchemy import select

from app.extensions import db
from datetime import datetime, timezone

from app.models import Drawing, Estimate, LeadEstimate, Project, SpecSection


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


def test_award_creates_active_job_and_marks_estimate(client):
    eid = "test-award-est-" + uuid.uuid4().hex[:10]
    with client.application.app_context():
        le = LeadEstimate(external_id=eid, name="Convert estimate", number="CJ-" + uuid.uuid4().hex[:8])
        db.session.add(le)
        db.session.flush()
        est = Estimate(lead_estimate_id=le.id, name="Bid set", status="draft", is_current=True)
        db.session.add(est)
        db.session.commit()
        estimate_id = str(est.id)

    awarded = client.post(
        f"/api/v1/lead-estimates/{eid}/award",
        json={"estimate_id": estimate_id},
    )
    assert awarded.status_code == 200, awarded.get_data(as_text=True)
    body = awarded.get_json()
    item = body["item"]
    assert body["project_id"]
    assert item["project_id"] == body["project_id"]
    assert item["crm_stage"] == "Awarded"

    with client.application.app_context():
        proj = db.session.get(Project, uuid.UUID(body["project_id"]))
        assert proj is not None
        assert proj.status == "active"
        est = db.session.get(Estimate, uuid.UUID(estimate_id))
        assert est is not None
        assert est.status == "awarded"
        assert str(est.project_id) == body["project_id"]


def test_award_allows_locked_estimate(client):
    eid = "test-award-lock-" + uuid.uuid4().hex[:10]
    with client.application.app_context():
        le = LeadEstimate(
            external_id=eid,
            name="Locked award",
            number="CJ-" + uuid.uuid4().hex[:8],
            estimate_locked_at=datetime.now(timezone.utc),
        )
        db.session.add(le)
        db.session.flush()
        est = Estimate(
            lead_estimate_id=le.id,
            name="Locked bid",
            status="submitted",
            is_current=True,
            estimate_locked_at=datetime.now(timezone.utc),
        )
        db.session.add(est)
        db.session.commit()
        estimate_id = str(est.id)

    awarded = client.post(
        f"/api/v1/lead-estimates/{eid}/award",
        json={"estimate_id": estimate_id},
    )
    assert awarded.status_code == 200, awarded.get_data(as_text=True)
    item = awarded.get_json()["item"]
    assert item["crm_stage"] == "Awarded"
    assert item["project_id"]

    with client.application.app_context():
        est = db.session.get(Estimate, uuid.UUID(estimate_id))
        assert est is not None
        assert est.status == "awarded"
        assert est.estimate_locked_at is not None


def test_award_moves_drawings_from_same_number_workspace(client):
    number = "25270-" + uuid.uuid4().hex[:6]
    with client.application.app_context():
        leftover = Project(name="Planning leftover", number=number, status="planning")
        job = Project(name="Awarded job", number=number, status="active")
        db.session.add_all([leftover, job])
        db.session.flush()
        drawing = Drawing(
            project_id=leftover.id,
            title="A0-000",
            sheet_number="A0-000",
            original_filename="A0-000.pdf",
            mime_type="application/pdf",
        )
        spec = SpecSection(project_id=leftover.id, code="10 14 00", title="Signage")
        lead = LeadEstimate(
            external_id="le-award-move-" + uuid.uuid4().hex[:8],
            name="Proton leftover",
            number=number,
            project_id=job.id,
        )
        db.session.add_all([drawing, spec, lead])
        db.session.commit()
        leftover_id = leftover.id
        job_id = job.id
        drawing_id = drawing.id
        spec_id = spec.id
        lead_ext = lead.external_id

    awarded = client.post(f"/api/v1/lead-estimates/{lead_ext}/award", json={})
    assert awarded.status_code == 200, awarded.get_data(as_text=True)
    assert awarded.get_json()["project_id"] == str(job_id)

    with client.application.app_context():
        assert db.session.get(Drawing, drawing_id).project_id == job_id
        assert db.session.get(SpecSection, spec_id).project_id == job_id
        assert db.session.get(Project, leftover_id) is not None


def test_list_drawings_includes_same_number_workspace(client):
    number = "25270-" + uuid.uuid4().hex[:6]
    with client.application.app_context():
        leftover = Project(name="Planning leftover", number=number, status="planning")
        job = Project(name="Awarded job", number=number, status="active")
        db.session.add_all([leftover, job])
        db.session.flush()
        drawing = Drawing(
            project_id=leftover.id,
            title="A0-103",
            sheet_number="A0-103",
            original_filename="A0-103.pdf",
            mime_type="application/pdf",
        )
        lead = LeadEstimate(
            external_id="le-list-move-" + uuid.uuid4().hex[:8],
            name="Proton leftover",
            number=number,
            project_id=job.id,
        )
        db.session.add_all([drawing, lead])
        db.session.commit()
        job_id = str(job.id)
        drawing_id = drawing.id

    listed = client.get(f"/api/v1/projects/{job_id}/drawings")
    assert listed.status_code == 200, listed.get_data(as_text=True)
    sheets = listed.get_json()["items"]
    assert any(s.get("sheet_number") == "A0-103" for s in sheets)
    with client.application.app_context():
        assert db.session.get(Drawing, drawing_id).project_id == uuid.UUID(job_id)
