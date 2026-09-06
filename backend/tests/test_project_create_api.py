"""POST /api/v1/projects — create a job from the Projects page."""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from app.extensions import db
from app.models import Project, ProjectMember, User


def _skip_if_no_db(flask_app):
    with flask_app.app_context():
        try:
            db.session.execute(text("SELECT 1"))
        except OperationalError as exc:
            pytest.skip(f"database unavailable: {exc}")


def test_create_project_minimal(client, flask_app):
    _skip_if_no_db(flask_app)
    name = "Create-" + uuid.uuid4().hex[:8]
    r = client.post("/api/v1/projects", json={"name": name})
    assert r.status_code == 201, r.get_data(as_text=True)
    item = r.get_json()["item"]
    assert item["name"] == name
    assert item["status"] == "active"
    assert item["project_type"] == "commercial"
    assert item["id"]

    with client.application.app_context():
        p = db.session.get(Project, uuid.UUID(item["id"]))
        assert p is not None
        assert p.name == name
        assert p.status == "active"


def test_create_project_with_location_and_number(client, flask_app):
    _skip_if_no_db(flask_app)
    number = "N-" + uuid.uuid4().hex[:8]
    r = client.post(
        "/api/v1/projects",
        json={
            "name": "Warehouse addition",
            "number": number,
            "city": "Phoenix",
            "state": "AZ",
            "project_type": "commercial",
        },
    )
    assert r.status_code == 201, r.get_data(as_text=True)
    item = r.get_json()["item"]
    assert item["number"] == number
    assert item["city"] == "Phoenix"
    assert item["state"] == "AZ"


def test_create_project_requires_name(client):
    r = client.post("/api/v1/projects", json={})
    assert r.status_code == 400
    assert "name" in (r.get_json() or {}).get("error", "").lower()


def test_create_project_duplicate_number(client, flask_app):
    _skip_if_no_db(flask_app)
    number = "DUP-" + uuid.uuid4().hex[:8]
    first = client.post("/api/v1/projects", json={"name": "First job", "number": number})
    assert first.status_code == 201, first.get_data(as_text=True)
    second = client.post("/api/v1/projects", json={"name": "Second job", "number": number})
    assert second.status_code == 409
    assert "number" in (second.get_json() or {}).get("error", "").lower()


def test_create_project_assigns_creator(client, flask_app):
    _skip_if_no_db(flask_app)
    with client.application.app_context():
        u = User(
            email=f"proj_create_{uuid.uuid4().hex[:8]}@t.com",
            first_name="Pat",
            last_name="Creator",
            is_active=True,
        )
        db.session.add(u)
        db.session.commit()
        uid = str(u.id)

    name = "Assigned-" + uuid.uuid4().hex[:8]
    r = client.post(
        "/api/v1/projects",
        json={"name": name},
        headers={"X-Usis-User-Id": uid},
    )
    assert r.status_code == 201, r.get_data(as_text=True)
    pid = r.get_json()["item"]["id"]

    with client.application.app_context():
        member = db.session.get(
            ProjectMember, {"user_id": uuid.UUID(uid), "project_id": uuid.UUID(pid)}
        )
        assert member is not None
