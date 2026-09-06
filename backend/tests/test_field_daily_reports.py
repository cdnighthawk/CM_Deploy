"""Field-app daily reports and photo upload."""
from __future__ import annotations

import io
import uuid

import pytest
from sqlalchemy import select

from app.api._field_service import merge_sections
from app.extensions import db
from app.models import Project, ProjectMember, Role, User, UserRole


def _tiny_jpeg() -> bytes:
    # Minimal JPEG (1x1) so multipart upload does not need Pillow.
    return (
        b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
        b"\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t"
        b"\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e"
        b"\x1d\x1a\x1c\x1c $.' \",#\x1c\x1c(7),01444\x1f'9=82<.342"
        b"\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00"
        b"\xff\xc4\x00\x14\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x08"
        b"\xff\xc4\x00\x14\x10\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00"
        b"\xff\xda\x00\x08\x01\x01\x00\x00?\x00\x7f\xff\xd9"
    )


def test_merge_sections_last_write_wins_per_key():
    existing = {
        "notes": "old note",
        "weather": {"conditions": "sunny", "temp_f": 90, "notes": ""},
        "work_performed": "hung metal",
    }
    incoming = {"notes": "new note", "delays": "rain hold"}
    merged = merge_sections(existing, incoming)
    assert merged["notes"] == "new note"
    assert merged["weather"]["conditions"] == "sunny"
    assert merged["work_performed"] == "hung metal"
    assert merged["delays"] == "rain hold"
    assert "manpower" in merged


def test_get_or_create_and_put_daily_report(client):
    with client.application.app_context():
        p = Project(name="Field-" + uuid.uuid4().hex[:8])
        db.session.add(p)
        db.session.flush()
        pid = str(p.id)
        db.session.commit()

    r1 = client.get(f"/api/v1/projects/{pid}/daily-reports?date=2026-08-28")
    assert r1.status_code == 200, r1.get_data(as_text=True)
    body = r1.get_json()
    assert body["entity"] == "daily_report"
    assert body["item"]["date"] == "2026-08-28"
    assert body["item"]["status"] == "draft"
    rid = body["item"]["id"]

    r2 = client.get(f"/api/v1/projects/{pid}/daily-reports?date=2026-08-28")
    assert r2.get_json()["item"]["id"] == rid

    r3 = client.put(
        f"/api/v1/daily-reports/{rid}",
        json={"sections": {"notes": "hung corner bead", "work_performed": "level 2"}},
    )
    assert r3.status_code == 200, r3.get_data(as_text=True)
    item = r3.get_json()["item"]
    assert item["sections"]["notes"] == "hung corner bead"
    assert item["sections"]["work_performed"] == "level 2"

    r4 = client.put(f"/api/v1/daily-reports/{rid}", json={"status": "complete"})
    assert r4.status_code == 200
    assert r4.get_json()["item"]["status"] == "complete"


def test_field_photo_upload_and_list(client):
    with client.application.app_context():
        p = Project(name="Photo-" + uuid.uuid4().hex[:8])
        db.session.add(p)
        db.session.flush()
        pid = str(p.id)
        db.session.commit()

    data = {
        "file": (io.BytesIO(_tiny_jpeg()), "site.jpg"),
        "caption": "North elevation",
        "location_text": "Grid A",
        "lat": "33.44",
        "lon": "-112.07",
    }
    r = client.post(
        f"/api/v1/projects/{pid}/photos",
        data=data,
        content_type="multipart/form-data",
    )
    assert r.status_code == 201, r.get_data(as_text=True)
    item = r.get_json()["item"]
    assert item["caption"] == "North elevation"
    assert item["location_text"] == "Grid A"
    assert item["file_url"].endswith("/file")

    listed = client.get(f"/api/v1/projects/{pid}/photos")
    assert listed.status_code == 200
    assert listed.get_json()["total"] >= 1

    file_r = client.get(item["file_url"])
    assert file_r.status_code == 200
    assert file_r.data[:2] == b"\xff\xd8"


@pytest.fixture
def no_dev_admin(monkeypatch):
    monkeypatch.setenv("USIS_API_DEV_ALLOW_ANY", "0")


def _mk_pe(prefix: str) -> User:
    role = db.session.scalar(select(Role).where(Role.code == "project_engineer"))
    if role is None:
        role = Role(code="project_engineer", name="Project Engineer")
        db.session.add(role)
        db.session.flush()
    u = User(email=f"{prefix}_{uuid.uuid4().hex[:8]}@t.com", is_active=True)
    db.session.add(u)
    db.session.flush()
    db.session.add(UserRole(user_id=u.id, role_id=role.id))
    return u


def test_field_photo_file_requires_project_access(client, no_dev_admin):
    with client.application.app_context():
        owner = _mk_pe("photo_owner")
        outsider = _mk_pe("photo_out")
        job = Project(name="PhotoScope-" + uuid.uuid4().hex[:8])
        other = Project(name="PhotoOther-" + uuid.uuid4().hex[:8])
        db.session.add_all([job, other])
        db.session.flush()
        db.session.add(ProjectMember(user_id=owner.id, project_id=job.id))
        db.session.add(ProjectMember(user_id=outsider.id, project_id=other.id))
        db.session.commit()
        pid, oid, xid = str(job.id), str(owner.id), str(outsider.id)

    uploaded = client.post(
        f"/api/v1/projects/{pid}/photos",
        data={"file": (io.BytesIO(_tiny_jpeg()), "site.jpg"), "caption": "north"},
        content_type="multipart/form-data",
        headers={"X-Usis-User-Id": oid},
    )
    assert uploaded.status_code == 201, uploaded.get_data(as_text=True)
    item = uploaded.get_json()["item"]
    file_url = item["file_url"]

    ok = client.get(file_url, headers={"X-Usis-User-Id": oid})
    assert ok.status_code == 200
    assert ok.data[:2] == b"\xff\xd8"

    denied = client.get(file_url, headers={"X-Usis-User-Id": xid})
    assert denied.status_code == 404

    sneak = client.patch(
        f"/api/v1/photos/{item['id']}",
        json={"caption": "hacked"},
        headers={"X-Usis-User-Id": xid},
    )
    assert sneak.status_code == 404

    listed = client.get(f"/api/v1/projects/{pid}/photos", headers={"X-Usis-User-Id": oid})
    assert listed.get_json()["items"][0]["caption"] == "north"

    denied_del = client.delete(
        f"/api/v1/photos/{item['id']}",
        headers={"X-Usis-User-Id": xid},
    )
    assert denied_del.status_code == 404
    gone = client.delete(
        f"/api/v1/photos/{item['id']}",
        headers={"X-Usis-User-Id": oid},
    )
    assert gone.status_code == 200, gone.get_data(as_text=True)


def test_put_daily_report_requires_project_access_before_write(client, no_dev_admin):
    with client.application.app_context():
        owner = _mk_pe("rpt_owner")
        outsider = _mk_pe("rpt_out")
        job = Project(name="RptScope-" + uuid.uuid4().hex[:8])
        other = Project(name="RptOther-" + uuid.uuid4().hex[:8])
        db.session.add_all([job, other])
        db.session.flush()
        db.session.add(ProjectMember(user_id=owner.id, project_id=job.id))
        db.session.add(ProjectMember(user_id=outsider.id, project_id=other.id))
        db.session.commit()
        pid, oid, xid = str(job.id), str(owner.id), str(outsider.id)

    created = client.get(
        f"/api/v1/projects/{pid}/daily-reports?date=2026-08-28",
        headers={"X-Usis-User-Id": oid},
    )
    assert created.status_code == 200, created.get_data(as_text=True)
    rid = created.get_json()["item"]["id"]

    owner_put = client.put(
        f"/api/v1/daily-reports/{rid}",
        json={"sections": {"notes": "owner note"}},
        headers={"X-Usis-User-Id": oid},
    )
    assert owner_put.status_code == 200
    assert owner_put.get_json()["item"]["sections"]["notes"] == "owner note"

    sneak = client.put(
        f"/api/v1/daily-reports/{rid}",
        json={"sections": {"notes": "hacked"}},
        headers={"X-Usis-User-Id": xid},
    )
    assert sneak.status_code == 404

    again = client.get(
        f"/api/v1/projects/{pid}/daily-reports?date=2026-08-28",
        headers={"X-Usis-User-Id": oid},
    )
    assert again.status_code == 200
    assert again.get_json()["item"]["sections"]["notes"] == "owner note"
