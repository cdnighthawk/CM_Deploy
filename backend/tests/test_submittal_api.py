"""API tests for Procore-style submittals (log, audit, attachments, annotations)."""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.extensions import db
from app.models import Project, Role, User, UserRole


@pytest.fixture
def no_dev_admin(monkeypatch):
    monkeypatch.setenv("USIS_API_DEV_ALLOW_ANY", "0")


def test_submittal_create_list_detail_audit(client):
    with client.application.app_context():
        p = Project(name="T-" + uuid.uuid4().hex[:10])
        db.session.add(p)
        db.session.flush()
        pid = str(p.id)
        db.session.commit()

    r = client.post(
        f"/api/v1/projects/{pid}/submittals",
        json={"title": "Concrete mix", "spec_section": "03 30 00", "submittal_type": "Shop Drawing"},
    )
    assert r.status_code == 201
    body = r.get_json()
    assert body["item"]["title"] == "Concrete mix"
    assert body["item"]["number"] == 1
    assert any(a.get("action") == "create" for a in body.get("audit", []))

    r2 = client.get(f"/api/v1/projects/{pid}/submittals")
    assert r2.status_code == 200
    items = r2.get_json()["items"]
    assert len(items) == 1
    assert items[0]["current_attachment"] is None

    sid = items[0]["id"]
    r3 = client.get(f"/api/v1/projects/{pid}/submittals/{sid}")
    assert r3.status_code == 200
    d3 = r3.get_json()
    assert d3["item"]["id"] == sid
    assert d3["permissions"]["can_edit"] is True


def test_submittal_attachment_versioning(client):
    with client.application.app_context():
        p = Project(name="Att-" + uuid.uuid4().hex[:8])
        db.session.add(p)
        db.session.flush()
        pid = str(p.id)
        db.session.commit()

    r = client.post(f"/api/v1/projects/{pid}/submittals", json={"title": "Shop dwg"})
    assert r.status_code == 201
    sid = r.get_json()["item"]["id"]

    r1 = client.post(
        f"/api/v1/projects/{pid}/submittals/{sid}/attachments",
        json={
            "file_url": "https://example.com/a.pdf",
            "title": "Rev 0",
            "mime_type": "application/pdf",
            "original_filename": "a.pdf",
        },
    )
    assert r1.status_code == 201
    doc1 = r1.get_json()["item"]["id"]
    assert r1.get_json()["item"]["version"] == 1

    r2 = client.post(
        f"/api/v1/projects/{pid}/submittals/{sid}/attachments",
        json={
            "file_url": "https://example.com/b.pdf",
            "title": "Rev 1",
            "mime_type": "application/pdf",
            "parent_document_id": doc1,
        },
    )
    assert r2.status_code == 201
    assert r2.get_json()["item"]["version"] == 2

    r3 = client.get(f"/api/v1/projects/{pid}/submittals/{sid}")
    vers = [a["version"] for a in r3.get_json()["attachments"]]
    assert sorted(vers) == [1, 2]


def test_annotation_requires_ball_in_court_or_admin(client, no_dev_admin):
    with client.application.app_context():
        role = db.session.scalar(select(Role).where(Role.code == "standard"))
        if role is None:
            role = Role(code="standard", name="Standard")
            db.session.add(role)
            db.session.flush()

        u1 = User(email="bic_owner_" + uuid.uuid4().hex[:8] + "@t.com", first_name="Ann", last_name="Owner")
        u2 = User(email="bic_other_" + uuid.uuid4().hex[:8] + "@t.com", first_name="Bob", last_name="Other")
        db.session.add_all([u1, u2])
        db.session.flush()
        db.session.add_all(
            [
                UserRole(user_id=u1.id, role_id=role.id),
                UserRole(user_id=u2.id, role_id=role.id),
            ]
        )
        p = Project(name="BIC test")
        db.session.add(p)
        db.session.flush()
        pid = str(p.id)
        db.session.commit()
        uid1 = str(u1.id)
        uid2 = str(u2.id)

    r = client.post(
        f"/api/v1/projects/{pid}/submittals",
        json={"title": "Markup gate", "ball_in_court": u1.email},
        headers={"X-Usis-User-Id": uid1},
    )
    assert r.status_code == 201
    sid = r.get_json()["item"]["id"]

    r_att = client.post(
        f"/api/v1/projects/{pid}/submittals/{sid}/attachments",
        json={"file_url": "https://example.com/x.pdf", "mime_type": "application/pdf"},
        headers={"X-Usis-User-Id": uid1},
    )
    assert r_att.status_code == 201
    did = r_att.get_json()["item"]["id"]

    r_bic = client.patch(
        f"/api/v1/projects/{pid}/submittals/{sid}",
        json={"ball_in_court": u2.email},
        headers={"X-Usis-User-Id": uid1},
    )
    assert r_bic.status_code == 200
    r_forbid = client.put(
        f"/api/v1/documents/{did}/submittal-annotations",
        json={"items": [{"type": "stamp", "stampId": "approved", "page": 0, "x": 0.1, "y": 0.1}]},
        headers={"X-Usis-User-Id": uid1},
    )
    assert r_forbid.status_code == 403

    r_ok = client.put(
        f"/api/v1/documents/{did}/submittal-annotations",
        json={"items": [{"type": "stamp", "stampId": "approved", "page": 0, "x": 0.2, "y": 0.2}]},
        headers={"X-Usis-User-Id": uid2},
    )
    assert r_ok.status_code == 200
    assert len(r_ok.get_json()["items"]) == 1


def test_annotation_admin_override(client, no_dev_admin):
    with client.application.app_context():
        uadm = User(email="adm_" + uuid.uuid4().hex[:8] + "@t.com", is_superuser=True)
        db.session.add(uadm)
        db.session.flush()
        p = Project(name="Admin ann")
        db.session.add(p)
        db.session.flush()
        pid = str(p.id)
        db.session.commit()
        adm_id = str(uadm.id)

    r = client.post(
        f"/api/v1/projects/{pid}/submittals",
        json={"title": "X", "ball_in_court": "someone_else@x.com"},
        headers={"X-Usis-User-Id": adm_id},
    )
    sid = r.get_json()["item"]["id"]
    r_att = client.post(
        f"/api/v1/projects/{pid}/submittals/{sid}/attachments",
        json={"file_url": "https://example.com/z.pdf", "mime_type": "application/pdf"},
        headers={"X-Usis-User-Id": adm_id},
    )
    did = r_att.get_json()["item"]["id"]
    r_put = client.put(
        f"/api/v1/documents/{did}/submittal-annotations",
        json={"items": [{"type": "stroke", "page": 0, "points": [[0, 0], [0.1, 0.1]], "width": 0.01}]},
        headers={"X-Usis-User-Id": adm_id},
    )
    assert r_put.status_code == 200


def test_get_project_detail(client):
    with client.application.app_context():
        uid = uuid.uuid4().hex[:10]
        p = Project(name=f"Detail-{uid}", number=f"NUM-{uid}", status="active", project_type="commercial")
        db.session.add(p)
        db.session.flush()
        pid = str(p.id)
        db.session.commit()

    r = client.get(f"/api/v1/projects/{pid}")
    assert r.status_code == 200
    body = r.get_json()
    assert body.get("entity") == "project"
    assert body["item"]["name"] == f"Detail-{uid}"
    assert body["item"]["number"] == f"NUM-{uid}"
    assert body["item"]["status"] == "active"

    missing = client.get(f"/api/v1/projects/{uuid.uuid4()}")
    assert missing.status_code == 404
