"""Client/server connection and site error log."""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select
from werkzeug.security import generate_password_hash

from app.extensions import db
from app.models import Role, User, UserRole
from app.models.client_error import ClientErrorEvent


@pytest.fixture
def no_dev_admin(monkeypatch):
    monkeypatch.setenv("USIS_API_DEV_ALLOW_ANY", "0")


def _admin(client) -> str:
    email = "err_adm_" + uuid.uuid4().hex[:8] + "@t.com"
    with client.application.app_context():
        u = User(
            email=email,
            first_name="Err",
            last_name="Admin",
            is_superuser=True,
            is_active=True,
            password_hash=generate_password_hash("pw-err-1"),
        )
        db.session.add(u)
        db.session.flush()
        uid = str(u.id)
        db.session.commit()
        return uid


def test_anonymous_can_post_connect_error(client, no_dev_admin):
    marker = "Failed to fetch " + uuid.uuid4().hex
    r = client.post(
        "/api/v1/client-errors",
        json={
            "kind": "connect",
            "message": marker,
            "url": "/api/v1/projects/" + uuid.uuid4().hex,
            "method": "GET",
            "page": "/construction/projects.html",
        },
    )
    assert r.status_code == 200, r.get_data(as_text=True)
    body = r.get_json()
    assert body["stored"] == 1

    with client.application.app_context():
        row = db.session.scalar(
            select(ClientErrorEvent).where(ClientErrorEvent.message == marker)
        )
        assert row is not None
        assert row.kind == "connect"
        assert row.page == "/construction/projects.html"


def test_duplicate_connect_error_is_skipped(client, no_dev_admin):
    payload = {
        "kind": "connect",
        "message": "Failed to fetch " + uuid.uuid4().hex,
        "url": "/api/v1/leads/" + uuid.uuid4().hex,
    }
    first = client.post("/api/v1/client-errors", json=payload)
    second = client.post("/api/v1/client-errors", json=payload)
    assert first.get_json()["stored"] == 1
    assert second.get_json()["stored"] == 0
    assert second.get_json()["skipped"] == 1


def test_admin_can_list_client_errors(client, no_dev_admin):
    aid = _admin(client)
    hdr = {"X-Usis-User-Id": aid}
    marker = "HTTP 502 " + uuid.uuid4().hex
    client.post(
        "/api/v1/client-errors",
        json={"kind": "http_error", "message": marker, "url": "/api/v1/auth/status", "status": 502},
        headers=hdr,
    )
    listed = client.get("/api/v1/admin/client-errors?kind=http_error", headers=hdr)
    assert listed.status_code == 200, listed.get_data(as_text=True)
    items = listed.get_json()["items"]
    assert any(marker in (x.get("message") or "") for x in items)


def test_client_error_list_requires_admin(client, no_dev_admin):
    with client.application.app_context():
        role = db.session.scalar(select(Role).where(Role.code == "standard"))
        if role is None:
            role = Role(code="standard", name="Standard")
            db.session.add(role)
            db.session.flush()
        u = User(email="err_std_" + uuid.uuid4().hex[:8] + "@t.com", first_name="S", last_name="T")
        db.session.add(u)
        db.session.flush()
        db.session.add(UserRole(user_id=u.id, role_id=role.id))
        uid = str(u.id)
        db.session.commit()

    r = client.get("/api/v1/admin/client-errors", headers={"X-Usis-User-Id": uid})
    assert r.status_code == 403


def test_server_exception_is_logged(client, no_dev_admin):
    from app.api._client_error_service import record_from_exception

    marker = "simulated crash " + uuid.uuid4().hex
    with client.application.app_context():
        record_from_exception(RuntimeError(marker))
        row = db.session.scalar(
            select(ClientErrorEvent)
            .where(ClientErrorEvent.message.contains(marker))
        )
        assert row is not None
        assert row.kind == "server"
