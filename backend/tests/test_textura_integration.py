"""Tests for Textura TPM integration routes (mocked HTTP)."""
from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError

from app.api import _integration_textura
from app.extensions import db
from app.models import PayApplication, Project, TexturaCredential, TexturaSyncLog

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "textura"


def _skip_if_no_textura_tables(flask_app):
    with flask_app.app_context():
        try:
            db.session.execute(select(TexturaCredential.label).limit(1))
        except OperationalError as exc:
            pytest.skip(f"textura tables missing (run flask db upgrade): {exc}")


def _load_fixture(name: str):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class _FakeTexturaClient:
    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self) -> _FakeTexturaClient:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def test_connection(self) -> None:
        return None

    def get_owner_projects(self):
        return _load_fixture("owner_projects.json")

    def export_invoices(self):
        return _load_fixture("invoices_export.json")


def test_textura_status_unconfigured(client, flask_app):
    _skip_if_no_textura_tables(flask_app)
    flask_app.config["TEXTURA_USERNAME"] = None
    flask_app.config["TEXTURA_PASSWORD"] = None
    r = client.get("/api/v1/integrations/textura/status")
    assert r.status_code == 200
    body = r.get_json()
    assert body["configured"] is False
    assert body["entity"] == "textura_status"


def test_textura_sync_disabled_returns_403(client, flask_app):
    _skip_if_no_textura_tables(flask_app)
    flask_app.config["TEXTURA_SYNC_ENABLED"] = False
    r = client.post("/api/v1/integrations/textura/sync")
    assert r.status_code == 403


def test_textura_credentials_and_sync_projects_invoices(client, flask_app, monkeypatch):
    _skip_if_no_textura_tables(flask_app)
    flask_app.config["TEXTURA_SYNC_ENABLED"] = True
    flask_app.config["TEXTURA_AUTO_CREATE_PROJECTS"] = True
    flask_app.config["SECRET_KEY"] = "unit-test-secret-key-not-for-production-use"
    flask_app.config["TEXTURA_USERNAME"] = None
    flask_app.config["TEXTURA_PASSWORD"] = None

    monkeypatch.setattr(_integration_textura, "TexturaClient", _FakeTexturaClient)

    r_cred = client.put(
        "/api/v1/integrations/textura/credentials",
        json={"username": "api@test.com", "password": "secret"},
    )
    assert r_cred.status_code == 200

    try:
        r_sync = client.post("/api/v1/integrations/textura/sync")
        assert r_sync.status_code == 200, r_sync.get_data(as_text=True)
        body = r_sync.get_json()
        assert body.get("loaded", 0) >= 1

        with flask_app.app_context():
            proj = db.session.scalar(
                select(Project).where(Project.textura_project_id == "3022")
            )
            assert proj is not None
            assert proj.name == "Sample Tower Renovation"
            proj.number = "PRJ-3022"
            db.session.commit()
            proj_id = proj.id

        r_sync2 = client.post("/api/v1/integrations/textura/sync")
        assert r_sync2.status_code == 200
        assert r_sync2.get_json().get("loaded", 0) >= 1

        with flask_app.app_context():
            pa = db.session.scalars(
                select(PayApplication).where(
                    PayApplication.project_id == proj_id,
                    PayApplication.textura_invoice_id.isnot(None),
                )
            ).first()
            assert pa is not None
            assert pa.status == "certified"
            assert len(pa.lines) == 2
    finally:
        with flask_app.app_context():
            for pa in db.session.scalars(select(PayApplication)).all():
                if pa.textura_invoice_id:
                    db.session.delete(pa)
            for proj in db.session.scalars(
                select(Project).where(Project.textura_project_id == "3022")
            ).all():
                db.session.delete(proj)
            for log in db.session.scalars(select(TexturaSyncLog)).all():
                db.session.delete(log)
            cred = db.session.get(TexturaCredential, "default")
            if cred is not None:
                db.session.delete(cred)
            db.session.commit()


def test_textura_project_scoped_sync(client, flask_app, monkeypatch):
    _skip_if_no_textura_tables(flask_app)
    flask_app.config["TEXTURA_SYNC_ENABLED"] = True
    flask_app.config["SECRET_KEY"] = "unit-test-secret-key-not-for-production-use"

    monkeypatch.setattr(_integration_textura, "TexturaClient", _FakeTexturaClient)

    with flask_app.app_context():
        p = Project(name="Scoped sync", number="PRJ-3022", status="active", project_type="commercial")
        db.session.add(p)
        db.session.commit()
        pid = str(p.id)

    client.put(
        "/api/v1/integrations/textura/credentials",
        json={"username": "u", "password": "p"},
    )

    try:
        r = client.post(f"/api/v1/projects/{pid}/integrations/textura/sync")
        assert r.status_code == 200, r.get_data(as_text=True)
        with flask_app.app_context():
            count = db.session.scalar(
                select(func.count())
                .select_from(PayApplication)
                .where(PayApplication.project_id == uuid.UUID(pid))
            )
            assert count and count >= 1
    finally:
        with flask_app.app_context():
            p = db.session.get(Project, uuid.UUID(pid))
            if p:
                for pa in list(p.pay_applications):
                    db.session.delete(pa)
                db.session.delete(p)
            cred = db.session.get(TexturaCredential, "default")
            if cred:
                db.session.delete(cred)
            db.session.commit()
