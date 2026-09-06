"""Admin delete for projects, leads, companies, documents, and RFPs."""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import OperationalError
from werkzeug.security import generate_password_hash

from app.extensions import db
from app.models import Company, Document, LeadEstimate, Project, User
from app.models.rfp import Rfp


def _skip_if_no_db(flask_app):
    with flask_app.app_context():
        try:
            db.session.execute(text("SELECT 1"))
        except OperationalError as exc:
            pytest.skip(f"database unavailable: {exc}")


def test_delete_project_soft_hides_from_list(client, flask_app):
    _skip_if_no_db(flask_app)
    with flask_app.app_context():
        p = Project(
            name="Del-" + uuid.uuid4().hex[:8],
            number="D-" + uuid.uuid4().hex[:6],
            status="active",
            project_type="commercial",
        )
        db.session.add(p)
        db.session.commit()
        pid = str(p.id)

    gone = client.delete(f"/api/v1/projects/{pid}")
    assert gone.status_code == 200, gone.get_data(as_text=True)
    assert gone.get_json()["ok"] is True
    assert client.get(f"/api/v1/projects/{pid}").status_code == 404

    listed = client.get("/api/v1/projects?limit=2000")
    assert listed.status_code == 200
    ids = [row["id"] for row in listed.get_json().get("items") or []]
    assert pid not in ids


def test_delete_lead_archives_from_board(client, flask_app):
    _skip_if_no_db(flask_app)
    ext = "del-lead-" + uuid.uuid4().hex[:10]
    with flask_app.app_context():
        le = LeadEstimate(external_id=ext, name="Lead to remove", is_archived=False)
        db.session.add(le)
        db.session.commit()
        lid = str(le.id)

    gone = client.delete(f"/api/v1/lead-estimates/{lid}")
    assert gone.status_code == 200, gone.get_data(as_text=True)
    body = gone.get_json()
    assert body["ok"] is True
    assert body["archived"] is True

    with flask_app.app_context():
        row = db.session.get(LeadEstimate, uuid.UUID(lid))
        assert row is not None
        assert row.is_archived is True


def test_delete_company_soft(client, flask_app):
    _skip_if_no_db(flask_app)
    created = client.post("/api/v1/companies", json={"name": "Del Co " + uuid.uuid4().hex[:6]})
    assert created.status_code == 201, created.get_data(as_text=True)
    cid = created.get_json()["item"]["id"]

    gone = client.delete(f"/api/v1/companies/{cid}")
    assert gone.status_code == 200, gone.get_data(as_text=True)
    with flask_app.app_context():
        row = db.session.get(Company, uuid.UUID(cid))
        assert row is not None
        assert row.deleted_at is not None


def test_delete_document_row(client, flask_app):
    _skip_if_no_db(flask_app)
    with flask_app.app_context():
        p = Project(
            name="DocDel-" + uuid.uuid4().hex[:8],
            number="DD-" + uuid.uuid4().hex[:6],
            status="active",
            project_type="commercial",
        )
        db.session.add(p)
        db.session.commit()
        pid = str(p.id)

    created = client.post(
        f"/api/v1/projects/{pid}/documents",
        json={"title": "Packet", "document_type": "other"},
    )
    assert created.status_code == 201, created.get_data(as_text=True)
    did = created.get_json()["item"]["id"]

    gone = client.delete(f"/api/v1/documents/{did}")
    assert gone.status_code == 200, gone.get_data(as_text=True)
    with flask_app.app_context():
        assert db.session.get(Document, uuid.UUID(did)) is None


def test_project_writer_can_delete_document(client, flask_app, monkeypatch):
    _skip_if_no_db(flask_app)
    monkeypatch.setenv("USIS_API_DEV_ALLOW_ANY", "0")
    email = "writer_doc_" + uuid.uuid4().hex[:8] + "@t.com"
    with flask_app.app_context():
        from app.models import Role, RoleModulePermission, UserRole

        role = Role(code="doc_writer_" + uuid.uuid4().hex[:6], name="Doc Writer")
        db.session.add(role)
        db.session.flush()
        db.session.add(RoleModulePermission(role_id=role.id, module_code="projects", access_level="write"))
        db.session.add(RoleModulePermission(role_id=role.id, module_code="documents", access_level="write"))
        u = User(email=email, password_hash=generate_password_hash("pw-1"), is_active=True)
        db.session.add(u)
        db.session.flush()
        db.session.add(UserRole(user_id=u.id, role_id=role.id))
        p = Project(
            name="DocW-" + uuid.uuid4().hex[:8],
            number="DW-" + uuid.uuid4().hex[:6],
            status="active",
            project_type="commercial",
        )
        db.session.add(p)
        db.session.commit()
        uid = str(u.id)
        pid = str(p.id)

    hdr = {"X-Usis-User-Id": uid}
    created = client.post(
        f"/api/v1/projects/{pid}/documents",
        json={"title": "Packet", "document_type": "other"},
        headers=hdr,
    )
    assert created.status_code == 201, created.get_data(as_text=True)
    did = created.get_json()["item"]["id"]
    gone = client.delete(f"/api/v1/documents/{did}", headers=hdr)
    assert gone.status_code == 200, gone.get_data(as_text=True)


def test_delete_rfp(client, flask_app):
    _skip_if_no_db(flask_app)
    created = client.post("/api/v1/rfps", json={"title": "Delete me"})
    assert created.status_code in (200, 201), created.get_data(as_text=True)
    rid = created.get_json()["item"]["id"]

    gone = client.delete(f"/api/v1/rfps/{rid}")
    assert gone.status_code == 200, gone.get_data(as_text=True)
    with flask_app.app_context():
        assert db.session.get(Rfp, uuid.UUID(rid)) is None


def test_write_user_cannot_delete_project(client, flask_app, monkeypatch):
    _skip_if_no_db(flask_app)
    monkeypatch.setenv("USIS_API_DEV_ALLOW_ANY", "0")
    email = "writer_del_" + uuid.uuid4().hex[:8] + "@t.com"
    with flask_app.app_context():
        from app.models import Role, RoleModulePermission, UserRole

        role = db.session.scalar(select(Role).where(Role.code == "standard"))
        if role is None:
            role = Role(code="standard", name="Standard")
            db.session.add(role)
            db.session.flush()
        db.session.add(RoleModulePermission(role_id=role.id, module_code="projects", access_level="write"))
        u = User(email=email, password_hash=generate_password_hash("pw-1"), is_active=True)
        db.session.add(u)
        db.session.flush()
        db.session.add(UserRole(user_id=u.id, role_id=role.id))
        p = Project(
            name="NoDel-" + uuid.uuid4().hex[:8],
            number="ND-" + uuid.uuid4().hex[:6],
            status="active",
            project_type="commercial",
        )
        db.session.add(p)
        db.session.commit()
        uid = str(u.id)
        pid = str(p.id)

    denied = client.delete(f"/api/v1/projects/{pid}", headers={"X-Usis-User-Id": uid})
    assert denied.status_code == 403
