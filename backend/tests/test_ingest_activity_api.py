"""Ingest dashboard aggregation and agent event webhook."""
from __future__ import annotations

import io
import json
import uuid
from datetime import datetime, timedelta, timezone

from app.extensions import db
from app.models import Document, LeadEstimate, Project
from app.services.ingest_activity import estimate_folder_hint


def _pdf_bytes() -> bytes:
    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


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


def _bind_org(flask_app):
    return _ensure_org(flask_app)


def _events_ready(flask_app) -> bool:
    from sqlalchemy import inspect

    with flask_app.app_context():
        return "ingest_agent_events" in inspect(db.engine).get_table_names()


def test_estimate_folder_hint_uses_pr53_field_when_present():
    class Fake:
        estimate_folder_path = r"Y:\Estimates\25270 Civic Center"
        number = "25270"
        name = "Civic Center"

    assert estimate_folder_hint(project=Fake()) == r"Y:\Estimates\25270 Civic Center"


def test_estimate_folder_hint_falls_back_to_number():
    class Fake:
        number = "24060"
        name = "High School"

    assert estimate_folder_hint(lead=Fake()) == r"Y:\Estimates\24060 High School"
    assert estimate_folder_hint() is None


def test_ingest_activity_lists_recent_uploads(client, flask_app):
    _ensure_org(flask_app)
    headers = _auth(flask_app)
    number = "24" + uuid.uuid4().hex[:4]
    pdf = _pdf_bytes()
    with flask_app.app_context():
        org_id = _bind_org(flask_app)
        job = Project(name="IngestDash-" + uuid.uuid4().hex[:6], number=number, organization_id=org_id)
        db.session.add(job)
        db.session.commit()
        pid = str(job.id)

    drawn = client.post(
        "/api/drawings",
        data={
            "file": (io.BytesIO(pdf), "A101_PLAN.pdf"),
            "metadata": json.dumps(
                {
                    "project_id": pid,
                    "source": "autodesk_desktop_connector",
                    "relative_path": f"{number}/Architectural/A101_PLAN.pdf",
                }
            ),
        },
        content_type="multipart/form-data",
        headers=headers,
    )
    assert drawn.status_code == 201, drawn.get_data(as_text=True)

    spec = client.post(
        "/api/documents",
        data={
            "file": (io.BytesIO(b"%PDF-1.4 spec"), "Addendum-1.pdf"),
            "metadata": json.dumps(
                {
                    "project_id": pid,
                    "source": "autodesk_desktop_connector",
                    "document_type": "specification",
                    "relative_path": f"{number}/Specs/Addendum-1.pdf",
                }
            ),
        },
        content_type="multipart/form-data",
        headers=headers,
    )
    assert spec.status_code == 201, spec.get_data(as_text=True)

    listed = client.get("/api/v1/ingest/activity?days=14&limit=50")
    assert listed.status_code == 200, listed.get_data(as_text=True)
    body = listed.get_json()
    assert body["entity"] == "ingest_activity"
    assert body["status"]["last_upload_at"]
    assert body["status"]["watch_hint"]
    ids = {row["id"] for row in body["items"]}
    assert drawn.get_json()["drawing"]["id"] in ids
    assert spec.get_json()["document"]["id"] in ids
    match = next(row for row in body["items"] if row["id"] == drawn.get_json()["drawing"]["id"])
    assert match["kind"] == "drawing"
    assert match["source"] == "autodesk_desktop_connector"
    assert match["project_id"] == pid
    assert match["project_url"].endswith("project-detail.html?id=" + pid)
    assert match["estimate_folder_path"]
    assert match["estimate_folder_path"].startswith("Y:\\Estimates\\" + number)

    projects = {row["project_id"]: row for row in body["projects"]}
    assert pid in projects
    assert projects[pid]["upload_count"] >= 2
    assert projects[pid]["is_new"] is True

    drawings_only = client.get("/api/v1/ingest/activity?kind=drawing&days=14")
    assert drawings_only.status_code == 200
    kinds = {row["kind"] for row in drawings_only.get_json()["items"] if row["project_id"] == pid}
    assert kinds == {"drawing"}

    docs_only = client.get(f"/api/v1/ingest/activity?kind=document&project_id={pid}&days=14")
    assert docs_only.status_code == 200
    assert all(row["kind"] == "document" for row in docs_only.get_json()["items"])

    ingest_only = client.get("/api/v1/ingest/activity?source=ingest&days=14")
    assert ingest_only.status_code == 200
    sources = {row["source"] for row in ingest_only.get_json()["items"] if row["project_id"] == pid}
    assert sources == {"autodesk_desktop_connector"}

    searched = client.get(f"/api/v1/ingest/activity?q=Addendum-1&project_id={pid}")
    assert searched.status_code == 200
    assert any("Addendum" in (row["filename"] or "") for row in searched.get_json()["items"])


def test_ingest_activity_filters_by_lead_estimate(client, flask_app):
    _ensure_org(flask_app)
    suffix = uuid.uuid4().hex[:8]
    with flask_app.app_context():
        org_id = _bind_org(flask_app)
        lead = LeadEstimate(
            external_id=f"ingest-act-{suffix}",
            name=f"Lead Activity {suffix}",
            number="25" + suffix[:4],
            organization_id=org_id,
        )
        db.session.add(lead)
        db.session.flush()
        doc = Document(
            document_type="other",
            title="Spec package",
            original_filename="specs.pdf",
            organization_id=org_id,
            tags={
                "source": "autodesk_desktop_connector",
                "lead_estimate_id": str(lead.id),
                "project_number": lead.number,
            },
        )
        db.session.add(doc)
        db.session.commit()
        lid = str(lead.id)
        did = str(doc.id)

    listed = client.get(f"/api/v1/ingest/activity?lead_estimate_id={lid}&days=14")
    assert listed.status_code == 200, listed.get_data(as_text=True)
    ids = {row["id"] for row in listed.get_json()["items"]}
    assert did in ids
    row = next(item for item in listed.get_json()["items"] if item["id"] == did)
    assert row["lead_estimate_id"] == lid
    assert row["estimate_url"]
    assert row["estimate_folder_path"]


def test_ingest_activity_rejects_bad_paging(client):
    r = client.get("/api/v1/ingest/activity?limit=nope")
    assert r.status_code == 400


def test_ingest_events_require_bearer(client, flask_app):
    flask_app.config["CM_API_KEY"] = "cmk_test_ingest_key"
    r = client.post("/api/ingest/events", json={"event_type": "heartbeat"})
    assert r.status_code == 401


def test_ingest_events_record_and_surface_on_activity(client, flask_app):
    _ensure_org(flask_app)
    if not _events_ready(flask_app):
        with flask_app.app_context():
            from app.models.ingest_event import IngestAgentEvent

            IngestAgentEvent.__table__.create(db.engine, checkfirst=True)
    headers = _auth(flask_app)
    posted = client.post(
        "/api/ingest/events",
        json={
            "event_type": "rescan_complete",
            "source": "accdocs",
            "message": "Rescan finished",
            "uploaded_count": 3,
            "host": "CHARLES-DATA",
        },
        headers=headers,
    )
    assert posted.status_code == 201, posted.get_data(as_text=True)
    item = posted.get_json()["item"]
    assert item["event_type"] == "rescan_complete"
    assert item["uploaded_count"] == 3

    new_proj = client.post(
        "/api/ingest/events",
        json={"event_type": "new_project", "project_number": "25999", "folder_name": "25999 New Job"},
        headers=headers,
    )
    assert new_proj.status_code == 201, new_proj.get_data(as_text=True)

    listed = client.get("/api/v1/ingest/activity?days=3")
    assert listed.status_code == 200
    status = listed.get_json()["status"]
    assert status["agent_reporting"] is True
    assert status["last_rescan_at"]
    types = {ev["event_type"] for ev in listed.get_json()["events"]}
    assert "rescan_complete" in types
    assert "new_project" in types


def test_ingest_events_reject_unknown_type(client, flask_app):
    if not _events_ready(flask_app):
        with flask_app.app_context():
            from app.models.ingest_event import IngestAgentEvent

            IngestAgentEvent.__table__.create(db.engine, checkfirst=True)
    headers = _auth(flask_app)
    r = client.post("/api/ingest/events", json={"event_type": "explode"}, headers=headers)
    assert r.status_code == 400


def test_ingest_activity_excludes_old_rows(client, flask_app):
    _ensure_org(flask_app)
    with flask_app.app_context():
        org_id = _bind_org(flask_app)
        old = Document(
            document_type="other",
            title="Old file",
            original_filename="old.pdf",
            organization_id=org_id,
            tags={"source": "autodesk_desktop_connector"},
        )
        db.session.add(old)
        db.session.flush()
        old.created_at = datetime.now(timezone.utc) - timedelta(days=40)
        db.session.commit()
        oid = str(old.id)
    listed = client.get("/api/v1/ingest/activity?days=7")
    assert listed.status_code == 200
    assert oid not in {row["id"] for row in listed.get_json()["items"]}
