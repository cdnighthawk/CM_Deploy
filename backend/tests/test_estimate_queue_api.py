"""Desktop Estimating → Queue (``GET /api/v1/estimate-queue``)."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.extensions import db
from app.models import Role, RoleModulePermission, User, UserRole
from app.models.lead_estimate import LeadEstimate


@pytest.fixture
def no_dev_admin(monkeypatch):
    monkeypatch.setenv("USIS_API_DEV_ALLOW_ANY", "0")


def _estimator(email: str | None = None) -> User:
    role = db.session.scalar(select(Role).where(Role.code == "estimator-queue-test"))
    if role is None:
        role = Role(code="estimator-queue-test", name="Estimator queue test")
        db.session.add(role)
        db.session.flush()
        db.session.add(
            RoleModulePermission(role_id=role.id, module_code="leads", access_level="write")
        )
        db.session.add(
            RoleModulePermission(role_id=role.id, module_code="estimate", access_level="write")
        )
    u = User(
        email=email or f"queue_{uuid.uuid4().hex[:10]}@gousis.com",
        first_name="Queue",
        last_name="Tester",
        is_active=True,
        is_superuser=False,
    )
    db.session.add(u)
    db.session.flush()
    db.session.add(UserRole(user_id=u.id, role_id=role.id))
    return u


def test_estimate_queue_requires_sign_in(client, no_dev_admin):
    r = client.get("/api/v1/estimate-queue")
    assert r.status_code == 401
    assert "authentication required" in (r.get_json() or {}).get("error", "")


def test_estimate_queue_returns_desktop_items(client, no_dev_admin):
    eid = "queue-" + uuid.uuid4().hex[:12]
    due = datetime.now(timezone.utc) + timedelta(days=3)
    with client.application.app_context():
        u = _estimator()
        le = LeadEstimate(
            external_id=eid,
            name="Wheeler HS",
            number="26-101",
            trade_name="Signage",
            submission_state="WILL_SUBMIT",
            due_at=due,
            is_archived=False,
            location={"city": "Boise", "state": "ID", "zip": "83702", "complete": "100 Main"},
            client={"company": {"name": "Hoffman"}},
        )
        db.session.add(le)
        db.session.commit()
        uid = str(u.id)
        lead_id = str(le.id)

    r = client.get("/api/v1/estimate-queue", headers={"X-Usis-User-Id": uid})
    assert r.status_code == 200, r.get_data(as_text=True)
    items = r.get_json()["items"]
    match = next(x for x in items if x["leadEstimateId"] == lead_id)
    assert match["name"] == "Wheeler HS"
    assert match["number"] == "26-101"
    assert match["tradeName"] == "Signage"
    assert match["submissionState"] == "WILL_SUBMIT"
    assert match["city"] == "Boise"
    assert match["state"] == "ID"
    assert match["siteZip"] == "83702"
    assert match["siteAddress"] == "100 Main"
    assert match["gcName"] == "Hoffman"


def test_estimate_queue_hides_declined_and_archived(client, no_dev_admin):
    suffix = uuid.uuid4().hex[:8]
    with client.application.app_context():
        u = _estimator()
        keep = LeadEstimate(
            external_id=f"keep-{suffix}",
            name="Keep me",
            submission_state="UNDECIDED",
            is_archived=False,
        )
        declined = LeadEstimate(
            external_id=f"declined-{suffix}",
            name="Declined",
            submission_state="DECLINED",
            is_archived=False,
        )
        archived = LeadEstimate(
            external_id=f"archived-{suffix}",
            name="Archived",
            submission_state="WILL_SUBMIT",
            is_archived=True,
        )
        db.session.add_all([keep, declined, archived])
        db.session.commit()
        uid = str(u.id)
        keep_id = str(keep.id)
        declined_id = str(declined.id)
        archived_id = str(archived.id)

    r = client.get("/api/v1/estimate-queue", headers={"X-Usis-User-Id": uid})
    assert r.status_code == 200
    ids = {x["leadEstimateId"] for x in r.get_json()["items"]}
    assert keep_id in ids
    assert declined_id not in ids
    assert archived_id not in ids


def test_estimate_queue_accepts_desktop_microsoft_token(client, no_dev_admin, monkeypatch):
    email = f"rodrigo_queue_{uuid.uuid4().hex[:8]}@gousis.com"
    with client.application.app_context():
        u = _estimator(email)
        db.session.commit()
        uid = str(u.id)

    def fake_entra(token: str | None = None, authorization: str | None = None):
        if token != "desktop-graph-token":
            return None
        return db.session.get(User, uuid.UUID(uid))

    monkeypatch.setattr("app.api._auth_desktop.entra_user_from_bearer", fake_entra)
    r = client.get(
        "/api/v1/estimate-queue",
        headers={"Authorization": "Bearer desktop-graph-token"},
    )
    assert r.status_code == 200, r.get_data(as_text=True)
    assert "items" in r.get_json()


def test_entra_user_from_bearer_matches_email(client, no_dev_admin, monkeypatch):
    email = f"rodrigo_map_{uuid.uuid4().hex[:8]}@gousis.com"
    with client.application.app_context():
        u = _estimator(email)
        db.session.commit()
        expected_id = u.id

        monkeypatch.setitem(client.application.config, "MS_ENTRA_TENANT_ID", "tenant-1")
        monkeypatch.setattr(
            "app.api._auth_desktop._email_from_token",
            lambda token, tenant, extra: email,
        )
        from app.api._auth_desktop import entra_user_from_bearer

        found = entra_user_from_bearer("any-token")
        assert found is not None
        assert found.id == expected_id
