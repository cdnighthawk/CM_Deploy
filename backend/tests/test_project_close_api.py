"""Close a project by setting status to complete and stamping closeout_date."""
from __future__ import annotations

import uuid
from datetime import date, timedelta

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


def _add_project(status: str = "active", closeout: date | None = None) -> str:
    p = Project(
        name="Close-" + uuid.uuid4().hex[:8],
        number="C-" + uuid.uuid4().hex[:6],
        status=status,
        project_type="commercial",
        closeout_date=closeout,
    )
    db.session.add(p)
    db.session.flush()
    pid = str(p.id)
    db.session.commit()
    return pid


def test_patch_complete_stamps_closeout_date(client, flask_app):
    _skip_if_no_db(flask_app)
    with client.application.app_context():
        pid = _add_project("active")

    r = client.patch(f"/api/v1/projects/{pid}", json={"status": "complete"})
    assert r.status_code == 200, r.get_data(as_text=True)
    item = r.get_json()["item"]
    assert item["status"] == "complete"
    assert item["closeout_date"] == date.today().isoformat()


def test_patch_complete_keeps_explicit_closeout_date(client, flask_app):
    _skip_if_no_db(flask_app)
    chosen = (date.today() - timedelta(days=3)).isoformat()
    with client.application.app_context():
        pid = _add_project("active")

    r = client.patch(
        f"/api/v1/projects/{pid}",
        json={"status": "complete", "closeout_date": chosen},
    )
    assert r.status_code == 200, r.get_data(as_text=True)
    item = r.get_json()["item"]
    assert item["status"] == "complete"
    assert item["closeout_date"] == chosen


def test_patch_complete_does_not_overwrite_existing_closeout(client, flask_app):
    _skip_if_no_db(flask_app)
    existing = date.today() - timedelta(days=10)
    with client.application.app_context():
        pid = _add_project("active", existing)

    r = client.patch(f"/api/v1/projects/{pid}", json={"status": "complete"})
    assert r.status_code == 200, r.get_data(as_text=True)
    item = r.get_json()["item"]
    assert item["status"] == "complete"
    assert item["closeout_date"] == existing.isoformat()


def test_reopen_complete_project_keeps_closeout_date(client, flask_app):
    _skip_if_no_db(flask_app)
    existing = date.today() - timedelta(days=2)
    with client.application.app_context():
        pid = _add_project("complete", existing)

    r = client.patch(f"/api/v1/projects/{pid}", json={"status": "active"})
    assert r.status_code == 200, r.get_data(as_text=True)
    item = r.get_json()["item"]
    assert item["status"] == "active"
    assert item["closeout_date"] == existing.isoformat()


def test_bulk_complete_stamps_closeout_date(client, flask_app):
    _skip_if_no_db(flask_app)
    with client.application.app_context():
        ids = [_add_project("active"), _add_project("on_hold")]

    r = client.post("/api/v1/projects/bulk", json={"ids": ids, "status": "complete"})
    assert r.status_code == 200, r.get_data(as_text=True)
    assert r.get_json().get("updated_count") == 2

    with client.application.app_context():
        for pid in ids:
            p = db.session.get(Project, uuid.UUID(pid))
            assert p is not None
            assert p.status == "complete"
            assert p.closeout_date == date.today()
