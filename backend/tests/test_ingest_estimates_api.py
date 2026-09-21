"""Bearer GET /api/ingest/estimates — desktop agent estimate folder map."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from app.extensions import db
from app.models import Estimate, LeadEstimate, Project
from app.services.ingest_estimates import human_job_number


def _auth(flask_app, key: str = "cmk_test_ingest_key"):
    flask_app.config["CM_API_KEY"] = key
    flask_app.config["CM_INGEST_API_KEY"] = None
    return {
        "Authorization": f"Bearer {key}",
        "User-Agent": "CM-Autodesk-Ingestion-Agent/1.1",
    }


def _ensure_org(flask_app):
    from sqlalchemy import text

    from app.tenancy import set_current_organization_id

    with flask_app.app_context():
        row = db.session.execute(text("SELECT id FROM organizations WHERE slug = 'usis'")).first()
        if row is None:
            oid = uuid.uuid4()
            db.session.execute(
                text(
                    "INSERT INTO organizations (id, name, slug, microsoft_sso_enabled, allow_join_by_domain, "
                    "status, plan_key, seat_cap_office, seat_cap_field, seat_cap_vendor_token) "
                    "VALUES (:id, :name, 'usis', false, false, 'active', 'full', 50, 50, 500)"
                ),
                {"id": oid, "name": "US Interior Specialties"},
            )
            db.session.commit()
        else:
            oid = row[0]
        set_current_organization_id(oid)
        return oid


def test_human_job_number_skips_uuid():
    uid = str(uuid.uuid4())
    assert human_job_number(None, None) is None
    assert human_job_number("", uid) is None
    assert human_job_number(uid, "26061") == "26061"
    assert human_job_number("25270", "24000") == "25270"


def test_ingest_estimates_requires_configured_key(client, flask_app):
    flask_app.config["CM_API_KEY"] = None
    flask_app.config["CM_INGEST_API_KEY"] = None
    r = client.get("/api/ingest/estimates")
    assert r.status_code == 503
    assert r.get_json()["error"]


def test_ingest_estimates_requires_bearer(client, flask_app):
    flask_app.config["CM_API_KEY"] = "cmk_test_ingest_key"
    r = client.get("/api/ingest/estimates")
    assert r.status_code == 401
    assert r.is_json


def test_ingest_estimates_rejects_wrong_key(client, flask_app):
    headers = _auth(flask_app)
    r = client.get("/api/ingest/estimates", headers={**headers, "Authorization": "Bearer wrong-key-value-xx"})
    assert r.status_code == 401


def test_ingest_estimates_returns_folder_map(client, flask_app):
    headers = _auth(flask_app)
    suffix = uuid.uuid4().hex[:8]
    number = "26" + suffix[:4]
    with flask_app.app_context():
        org_id = _ensure_org(flask_app)
        job = Project(name=f"Civic Center {suffix}", number=number, organization_id=org_id)
        db.session.add(job)
        db.session.flush()
        lead = LeadEstimate(
            external_id=f"ingest-est-{suffix}",
            name=f"Civic Center {suffix}",
            number=number,
            project_id=job.id,
            is_archived=False,
            is_parent=True,
            submission_state="UNDECIDED",
            due_at=datetime(2026, 9, 30, 17, 0, tzinfo=timezone.utc),
            organization_id=org_id,
        )
        db.session.add(lead)
        db.session.flush()
        est = Estimate(
            name="Original Estimate",
            lead_estimate_id=lead.id,
            project_id=job.id,
            is_current=True,
            folder_provision_status="ready",
            folder_path=rf"Y:\Estimates\{number} - Original Estimate",
            due_at=datetime(2026, 9, 30, 17, 0, tzinfo=timezone.utc),
            organization_id=org_id,
        )
        db.session.add(est)
        db.session.commit()
        est_id = str(est.id)
        job_id = str(job.id)
        lead_id = str(lead.id)

    listed = client.get("/api/ingest/estimates", headers=headers)
    assert listed.status_code == 200, listed.get_data(as_text=True)
    body = listed.get_json()
    assert body["entity"] == "ingest_estimates"
    assert isinstance(body["estimates"], list)
    match = next((row for row in body["estimates"] if row["id"] == est_id), None)
    assert match is not None
    assert match["job_number"] == number
    assert match["name"] == "Original Estimate"
    assert match["folder_path"] == rf"Y:\Estimates\{number} - Original Estimate"
    assert match["folder_provision_status"] == "ready"
    assert match["project_id"] == job_id
    assert match["project_number"] == number
    assert match["project_name"]
    assert match["lead_estimate_id"] == lead_id
    assert match["lead_number"] == number
    assert match["is_current"] is True
    assert number in match["folder_hints"]
    assert any(p["id"] == job_id for p in match["projects"])
    assert as_uuid_or_none(match["job_number"]) is None
    assert match["due_at"] and "2026-09-30" in match["due_at"]

    alias = client.get("/api/estimates", headers=headers)
    assert alias.status_code == 200
    assert any(row["id"] == est_id for row in alias.get_json()["estimates"])


def as_uuid_or_none(value: str | None):
    from app.services.ingest import as_uuid

    return as_uuid(value)


def test_ingest_estimates_job_number_from_project_not_uuid(client, flask_app):
    headers = _auth(flask_app)
    suffix = uuid.uuid4().hex[:8]
    number = "24" + suffix[:4]
    with flask_app.app_context():
        org_id = _ensure_org(flask_app)
        job = Project(name=f"High School {suffix}", number=number, organization_id=org_id)
        db.session.add(job)
        db.session.flush()
        est = Estimate(
            name="Plan set",
            project_id=job.id,
            folder_provision_status="ready",
            folder_path=rf"Y:\Estimates\{number} - Plan set",
            organization_id=org_id,
        )
        db.session.add(est)
        db.session.commit()
        est_id = str(est.id)
        job_id = str(job.id)

    listed = client.get(f"/api/ingest/estimates?project_id={job_id}", headers=headers)
    assert listed.status_code == 200, listed.get_data(as_text=True)
    match = next(row for row in listed.get_json()["estimates"] if row["id"] == est_id)
    assert match["job_number"] == number
    assert match["job_number"] != est_id
    assert as_uuid_or_none(match["job_number"]) is None


def test_ingest_estimates_omits_uuid_when_no_human_number(client, flask_app):
    headers = _auth(flask_app)
    suffix = uuid.uuid4().hex[:8]
    with flask_app.app_context():
        org_id = _ensure_org(flask_app)
        lead = LeadEstimate(
            external_id=f"ingest-est-nonum-{suffix}",
            name=f"No Number {suffix}",
            number=None,
            is_archived=False,
            is_parent=True,
            submission_state="UNDECIDED",
            organization_id=org_id,
        )
        db.session.add(lead)
        db.session.flush()
        est = Estimate(name="Draft", lead_estimate_id=lead.id, organization_id=org_id)
        db.session.add(est)
        db.session.commit()
        est_id = str(est.id)

    listed = client.get("/api/ingest/estimates", headers=headers)
    assert listed.status_code == 200
    match = next(row for row in listed.get_json()["estimates"] if row["id"] == est_id)
    assert match["job_number"] is None
    assert match["folder_path"] is None


def test_ingest_estimates_matches_accdocs_project_key(client, flask_app):
    headers = _auth(flask_app)
    suffix = uuid.uuid4().hex[:8]
    with flask_app.app_context():
        org_id = _ensure_org(flask_app)
        job = Project(name=f"Turner Bid {suffix}", number="240142", organization_id=org_id)
        db.session.add(job)
        db.session.flush()
        est = Estimate(
            name="Turner – Bid Set",
            project_id=job.id,
            folder_provision_status="ready",
            folder_path=r"Y:\Estimates\240142 - Turner Bid Set",
            organization_id=org_id,
        )
        db.session.add(est)
        db.session.commit()
        est_id = str(est.id)
        job_id = str(job.id)

    by_key = client.get("/api/ingest/estimates?q=PROJ-2024-0142", headers=headers)
    assert by_key.status_code == 200, by_key.get_data(as_text=True)
    assert any(row["id"] == est_id for row in by_key.get_json()["estimates"])

    by_name = client.get(f"/api/ingest/estimates?project_key=Turner%20Bid%20{suffix}", headers=headers)
    assert by_name.status_code == 200
    assert any(row["id"] == est_id for row in by_name.get_json()["estimates"])

    by_id = client.get(f"/api/ingest/estimates?project_id={job_id}", headers=headers)
    assert by_id.status_code == 200
    rows = by_id.get_json()["estimates"]
    assert len(rows) == 1
    assert rows[0]["id"] == est_id

    ready = client.get("/api/ingest/estimates?has_folder=1&q=240142", headers=headers)
    assert ready.status_code == 200
    assert any(row["id"] == est_id for row in ready.get_json()["estimates"])


def test_ingest_estimates_pagination_and_bad_limit(client, flask_app):
    headers = _auth(flask_app)
    page = client.get("/api/ingest/estimates?limit=2&offset=0", headers=headers)
    assert page.status_code == 200
    body = page.get_json()
    assert body["limit"] == 2
    assert body["offset"] == 0
    assert len(body["estimates"]) <= 2
    assert "has_more" in body
    assert "count" in body

    bad = client.get("/api/ingest/estimates?limit=nope", headers=headers)
    assert bad.status_code == 400


def test_ingest_estimates_due_from_through_future(client, flask_app):
    headers = _auth(flask_app)
    suffix = uuid.uuid4().hex[:8]
    now = datetime.now(timezone.utc)
    with flask_app.app_context():
        org_id = _ensure_org(flask_app)
        old_lead = LeadEstimate(
            external_id=f"ingest-due-old-{suffix}",
            name=f"Old Bid {suffix}",
            number="21" + suffix[:4],
            is_archived=False,
            is_parent=True,
            submission_state="SUBMITTED",
            due_at=now - timedelta(days=45),
            organization_id=org_id,
        )
        recent_lead = LeadEstimate(
            external_id=f"ingest-due-recent-{suffix}",
            name=f"Recent Bid {suffix}",
            number="22" + suffix[:4],
            is_archived=False,
            is_parent=True,
            submission_state="SUBMITTED",
            due_at=now - timedelta(days=10),
            organization_id=org_id,
        )
        future_lead = LeadEstimate(
            external_id=f"ingest-due-future-{suffix}",
            name=f"Future Bid {suffix}",
            number="23" + suffix[:4],
            is_archived=False,
            is_parent=True,
            submission_state="WILL_SUBMIT",
            due_at=now + timedelta(days=20),
            organization_id=org_id,
        )
        undated_lead = LeadEstimate(
            external_id=f"ingest-due-none-{suffix}",
            name=f"No Due {suffix}",
            number="24" + suffix[:4],
            is_archived=False,
            is_parent=True,
            submission_state="UNDECIDED",
            due_at=None,
            organization_id=org_id,
        )
        db.session.add_all([old_lead, recent_lead, future_lead, undated_lead])
        db.session.flush()
        old_est = Estimate(name="Old", lead_estimate_id=old_lead.id, organization_id=org_id)
        recent_est = Estimate(
            name="Recent",
            lead_estimate_id=recent_lead.id,
            due_at=recent_lead.due_at,
            organization_id=org_id,
        )
        future_est = Estimate(name="Future", lead_estimate_id=future_lead.id, organization_id=org_id)
        undated_est = Estimate(name="Undated", lead_estimate_id=undated_lead.id, organization_id=org_id)
        db.session.add_all([old_est, recent_est, future_est, undated_est])
        db.session.commit()
        old_id = str(old_est.id)
        recent_id = str(recent_est.id)
        future_id = str(future_est.id)
        undated_id = str(undated_est.id)

    due_from = (now - timedelta(days=30)).date().isoformat()
    listed = client.get(f"/api/ingest/estimates?due_from={due_from}", headers=headers)
    assert listed.status_code == 200, listed.get_data(as_text=True)
    ids = {row["id"] for row in listed.get_json()["estimates"]}
    assert recent_id in ids
    assert future_id in ids
    assert old_id not in ids
    assert undated_id not in ids
    recent = next(row for row in listed.get_json()["estimates"] if row["id"] == recent_id)
    assert recent["due_at"]
    future = next(row for row in listed.get_json()["estimates"] if row["id"] == future_id)
    assert future["due_at"]

    bounded = client.get(
        f"/api/ingest/estimates?due_from={due_from}&due_to={now.date().isoformat()}",
        headers=headers,
    )
    assert bounded.status_code == 200
    bounded_ids = {row["id"] for row in bounded.get_json()["estimates"]}
    assert recent_id in bounded_ids
    assert future_id not in bounded_ids

    alias = client.get(f"/api/ingest/estimates?due_after={due_from}", headers=headers)
    assert alias.status_code == 200
    assert recent_id in {row["id"] for row in alias.get_json()["estimates"]}

    bad = client.get("/api/ingest/estimates?due_from=not-a-date", headers=headers)
    assert bad.status_code == 400
    inverted = client.get("/api/ingest/estimates?due_from=2026-12-01&due_to=2026-01-01", headers=headers)
    assert inverted.status_code == 400
