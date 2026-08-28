"""Bulk project status updates."""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from app.extensions import db
from app.models import Project


def _skip_if_no_db(flask_app):
    with flask_app.app_context():
        try:
            db.session.execute(text("SELECT 1"))
        except OperationalError as exc:
            pytest.skip(f"database unavailable: {exc}")


def test_projects_bulk_status(client, flask_app):
    _skip_if_no_db(flask_app)
    ids: list[str] = []
    with client.application.app_context():
        for i in range(2):
            p = Project(
                name=f"Bulk-{i}-{uuid.uuid4().hex[:8]}",
                number=f"B{i}-{uuid.uuid4().hex[:4]}",
                status="active",
                project_type="commercial",
            )
            db.session.add(p)
            db.session.flush()
            ids.append(str(p.id))
        db.session.commit()

    r = client.post("/api/v1/projects/bulk", json={"ids": ids, "status": "on_hold"})
    assert r.status_code == 200, r.get_data(as_text=True)
    body = r.get_json()
    assert body.get("ok") is True
    assert body.get("updated_count") == 2
    assert body.get("failed_count") == 0

    with client.application.app_context():
        for pid in ids:
            p = db.session.get(Project, uuid.UUID(pid))
            assert p is not None
            assert p.status == "on_hold"


def test_projects_bulk_invalid_status(client, flask_app):
    _skip_if_no_db(flask_app)
    with client.application.app_context():
        p = Project(name="Bulk-bad-" + uuid.uuid4().hex[:8], status="active")
        db.session.add(p)
        db.session.flush()
        pid = str(p.id)
        db.session.commit()

    r = client.post(
        "/api/v1/projects/bulk",
        json={"ids": [pid], "status": "not-a-status"},
    )
    assert r.status_code == 400
    assert "status" in (r.get_json() or {}).get("error", "").lower()


def test_projects_bulk_empty_ids(client):
    r = client.post("/api/v1/projects/bulk", json={"ids": [], "status": "active"})
    assert r.status_code == 400
