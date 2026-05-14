"""Smoke tests for Plan 1 search and Plan 2 CRM patch."""
from __future__ import annotations

import uuid
from datetime import timezone

from sqlalchemy import select

from app.extensions import db
from app.models import Estimate, LeadEstimate, Project


def test_search_requires_two_chars(client):
    r = client.get("/api/v1/search?q=a")
    assert r.status_code == 200
    assert r.get_json()["items"] == []


def test_search_returns_shape(client, flask_app):
    with flask_app.app_context():
        proj = Project(name="UniqueSearchWidgetXYZ", status="active", project_type="commercial")
        db.session.add(proj)
        db.session.commit()
        pid = str(proj.id)
    try:
        r = client.get("/api/v1/search?q=UniqueSearchWidget")
        assert r.status_code == 200
        data = r.get_json()
        assert data["entity"] == "search"
        labels = " ".join(x.get("label", "") for x in data["items"])
        assert "UniqueSearchWidgetXYZ" in labels
        assert any(x.get("type") == "project" and pid in str(x.get("id", "")) for x in data["items"])
    finally:
        with flask_app.app_context():
            row = db.session.scalar(select(Project).where(Project.id == uuid.UUID(pid)))
            if row:
                db.session.delete(row)
                db.session.commit()


def test_patch_lead_crm_stage(client, flask_app):
    eid = "crm-test-" + uuid.uuid4().hex[:10]
    with flask_app.app_context():
        le = LeadEstimate(external_id=eid, name="CRM patch test", crm_stage="New Lead")
        db.session.add(le)
        db.session.commit()
        uid = str(le.id)
    try:
        r = client.patch(f"/api/v1/lead-estimates/{uid}", json={"crm_stage": "Estimating"})
        assert r.status_code == 200
        assert r.get_json()["item"]["crm_stage"] == "Estimating"
    finally:
        with flask_app.app_context():
            row = db.session.scalar(select(LeadEstimate).where(LeadEstimate.external_id == eid))
            if row:
                db.session.delete(row)
                db.session.commit()


def test_patch_lead_due_at(client, flask_app):
    eid = "crm-due-" + uuid.uuid4().hex[:10]
    with flask_app.app_context():
        le = LeadEstimate(external_id=eid, name="due patch", crm_stage="New Lead")
        db.session.add(le)
        db.session.commit()
        uid = str(le.id)
    try:
        r = client.patch(
            f"/api/v1/lead-estimates/{uid}",
            json={"due_at": "2026-06-15T12:00:00+00:00"},
        )
        assert r.status_code == 200
        item = r.get_json()["item"]
        assert item["due_at"] and "2026-06-15" in item["due_at"]
        with flask_app.app_context():
            row = db.session.scalar(select(LeadEstimate).where(LeadEstimate.external_id == eid))
            assert row is not None
            assert row.due_at is not None
    finally:
        with flask_app.app_context():
            row = db.session.scalar(select(LeadEstimate).where(LeadEstimate.external_id == eid))
            if row:
                db.session.delete(row)
                db.session.commit()


def test_estimate_due_at_create_and_patch(client, flask_app):
    le_ext = "est-due-" + uuid.uuid4().hex[:10]
    with flask_app.app_context():
        le = LeadEstimate(external_id=le_ext, name="est parent", crm_stage="New Lead")
        db.session.add(le)
        db.session.commit()
        lid = str(le.id)
    est_id: str | None = None
    try:
        r = client.post(
            "/api/v1/estimates",
            json={"lead_estimate_id": lid, "title": "V1", "due_at": "2026-07-01"},
        )
        assert r.status_code == 201
        body = r.get_json()
        est_id = body["item"]["id"]
        assert body["item"]["due_at"] is not None
        with flask_app.app_context():
            erow = db.session.scalar(select(Estimate).where(Estimate.id == uuid.UUID(est_id)))
            assert erow is not None
            assert erow.due_at is not None
            assert erow.due_at.astimezone(timezone.utc).date().isoformat() == "2026-07-01"
        r2 = client.patch(f"/api/v1/estimates/{est_id}", json={"due_at": None})
        assert r2.status_code == 200
        assert r2.get_json()["item"]["due_at"] is None
    finally:
        with flask_app.app_context():
            if est_id:
                erow = db.session.scalar(select(Estimate).where(Estimate.id == uuid.UUID(est_id)))
                if erow:
                    db.session.delete(erow)
            row = db.session.scalar(select(LeadEstimate).where(LeadEstimate.external_id == le_ext))
            if row:
                db.session.delete(row)
            db.session.commit()
