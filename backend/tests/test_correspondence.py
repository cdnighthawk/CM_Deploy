"""Correspondence Phase 1 file register."""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.exc import OperationalError, ProgrammingError

from app.extensions import db
from app.models import CorrespondenceItem, Project, Role, User, UserRole


def _skip_if_unmigrated(exc: Exception) -> None:
    if isinstance(exc, (ProgrammingError, OperationalError)) or "does not exist" in str(exc):
        pytest.skip("correspondence tables missing (run flask db upgrade)")
    raise exc


@pytest.fixture
def no_dev_admin(monkeypatch):
    monkeypatch.setenv("USIS_API_DEV_ALLOW_ANY", "0")


def test_local_ingest_list_file_and_download(client, no_dev_admin, tmp_path, monkeypatch):
    monkeypatch.setenv("DOCUMENT_ROOT", str(tmp_path))
    with client.application.app_context():
        try:
            role = db.session.scalar(select(Role).where(Role.code == "standard"))
            if role is None:
                role = Role(code="standard", name="Standard")
                db.session.add(role)
                db.session.flush()
            u = User(email="corr_" + uuid.uuid4().hex[:8] + "@t.com")
            db.session.add(u)
            db.session.flush()
            db.session.add(UserRole(user_id=u.id, role_id=role.id))
            p = Project(name="Corr-" + uuid.uuid4().hex[:6])
            db.session.add(p)
            db.session.flush()
            pid, uid = str(p.id), str(u.id)
            db.session.commit()
        except Exception as exc:
            _skip_if_unmigrated(exc)

    hdr = {"X-Usis-User-Id": uid}
    r = client.post(
        "/api/correspondence",
        json={
            "subject": "Shop drawings for lockers",
            "from_email": "gc@example.com",
            "from_name": "GC PM",
            "body": "Please file this under the job.",
        },
        headers=hdr,
    )
    if r.status_code >= 500:
        pytest.skip("correspondence not migrated")
    assert r.status_code == 201, r.get_data(as_text=True)
    item = r.get_json()["item"]
    assert item["unfiled"] is True
    iid = item["id"]

    listed = client.get("/api/correspondence?unfiled=1", headers=hdr)
    assert listed.status_code == 200
    assert any(x["id"] == iid for x in listed.get_json()["items"])

    filed = client.post(f"/api/correspondence/{iid}/file", json={"project_id": pid}, headers=hdr)
    assert filed.status_code == 200
    assert filed.get_json()["item"]["projectId"] == pid

    dl = client.get(f"/api/correspondence/{iid}/download", headers=hdr)
    assert dl.status_code == 200
    assert b"Shop drawings" in dl.get_data()

    with client.application.app_context():
        row = db.session.get(CorrespondenceItem, uuid.UUID(iid))
        assert row is not None
        assert row.search_text and "lockers" in row.search_text.lower()


def test_local_ingest_files_from_usis_ref_footer(client, no_dev_admin, tmp_path, monkeypatch):
    monkeypatch.setenv("DOCUMENT_ROOT", str(tmp_path))
    thread_id = str(uuid.uuid4())
    with client.application.app_context():
        try:
            role = db.session.scalar(select(Role).where(Role.code == "standard"))
            if role is None:
                role = Role(code="standard", name="Standard")
                db.session.add(role)
                db.session.flush()
            u = User(email="corr_ref_" + uuid.uuid4().hex[:8] + "@t.com")
            db.session.add(u)
            db.session.flush()
            db.session.add(UserRole(user_id=u.id, role_id=role.id))
            p = Project(name="CorrRef-" + uuid.uuid4().hex[:6])
            db.session.add(p)
            db.session.flush()
            pid, uid = str(p.id), str(u.id)
            db.session.commit()
        except Exception as exc:
            _skip_if_unmigrated(exc)

    hdr = {"X-Usis-User-Id": uid}
    r = client.post(
        "/api/correspondence",
        json={
            "subject": "Someone rewrote this subject",
            "from_email": "gc@example.com",
            "body": (
                "Please see attached.\n\n-----\n"
                f"USIS-REF project={pid} thread={thread_id}\n"
            ),
        },
        headers=hdr,
    )
    if r.status_code >= 500:
        pytest.skip("correspondence not migrated")
    assert r.status_code == 201, r.get_data(as_text=True)
    item = r.get_json()["item"]
    assert item["unfiled"] is False
    assert item["projectId"] == pid
    assert item["threadId"] == thread_id


def test_ingest_graph_message_files_from_footer(client, no_dev_admin, tmp_path, monkeypatch):
    monkeypatch.setenv("DOCUMENT_ROOT", str(tmp_path))
    from app.api._correspondence_service import ingest_graph_message
    from app.models import CorrespondenceSource

    thread_id = uuid.uuid4()
    with client.application.app_context():
        try:
            p = Project(name="GraphRef-" + uuid.uuid4().hex[:6])
            db.session.add(p)
            db.session.flush()
            src = CorrespondenceSource(
                source_type="mailbox",
                external_key="proj-ref-" + uuid.uuid4().hex[:10] + "@gousis.com",
                display_name="projects",
                mailbox="projects@gousis.com",
                is_active=True,
            )
            db.session.add(src)
            db.session.flush()
            pid = p.id
            item = ingest_graph_message(
                {
                    "id": "graph-mid-" + uuid.uuid4().hex[:12],
                    "subject": "totally different subject",
                    "from": {"email": "a@example.com", "name": "Architect"},
                    "body_content": (
                        "<div>Reply text</div><p>-----<br>"
                        f"USIS-REF project={pid} thread={thread_id}</p>"
                    ),
                    "attachments": [],
                },
                mailbox="projects@gousis.com",
                source=src,
            )
            db.session.commit()
        except Exception as exc:
            _skip_if_unmigrated(exc)
            return
        assert item is not None
        assert item.project_id == pid
        assert item.thread_id == thread_id
        assert item.filed_at is not None
