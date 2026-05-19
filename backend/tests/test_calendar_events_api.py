"""API tests for categorized calendar events feed."""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

import pytest
from sqlalchemy import select

from app.extensions import db
from app.models import (
    Commitment,
    Project,
    ProjectMaterialOrder,
    ProjectScheduleItem,
    Rfi,
    Role,
    User,
    UserRole,
)


@pytest.fixture
def no_dev_admin(monkeypatch):
    monkeypatch.setenv("USIS_API_DEV_ALLOW_ANY", "0")


def test_calendar_events_procurement_and_schedule(client, no_dev_admin):
    with client.application.app_context():
        role = db.session.scalar(select(Role).where(Role.code == "standard"))
        if role is None:
            role = Role(code="standard", name="Standard")
            db.session.add(role)
            db.session.flush()
        u = User(email="cal_u_" + uuid.uuid4().hex[:8] + "@t.com", first_name="C", last_name="U")
        db.session.add(u)
        db.session.flush()
        db.session.add(UserRole(user_id=u.id, role_id=role.id))
        p = Project(name="CalProj-" + uuid.uuid4().hex[:8], start_date=date(2026, 7, 1))
        db.session.add(p)
        db.session.flush()
        pid = str(p.id)
        uid = str(u.id)

        db.session.add(
            ProjectScheduleItem(
                project_id=p.id,
                title="Level 2 install",
                start_date=date(2026, 6, 1),
                end_date=date(2026, 6, 5),
            )
        )
        c = Commitment(
            project_id=p.id,
            commitment_kind="purchase_order",
            title="PO-1",
            reference_number="PO-1",
        )
        db.session.add(c)
        db.session.flush()
        db.session.add(
            ProjectMaterialOrder(
                project_id=p.id,
                commitment_id=c.id,
                vendor_name="Acme Supply",
                order_date=date(2026, 5, 20),
                expected_delivery_date=date(2026, 6, 15),
                status="ordered",
            )
        )
        db.session.add(
            Rfi(
                project_id=p.id,
                number=1,
                subject="Clarify spec",
                status="open",
                due_at=datetime(2026, 6, 20, 12, 0, tzinfo=timezone.utc),
            )
        )
        db.session.commit()

    hdr = {"X-Usis-User-Id": uid}

    r_all = client.get("/api/v1/calendar-events", headers=hdr)
    assert r_all.status_code == 200, r_all.get_data(as_text=True)
    items = r_all.get_json()["items"]
    cats = {x["category"] for x in items}
    assert "schedule" in cats
    assert "procurement_order" in cats
    assert "procurement_delivery" in cats
    assert "rfi" in cats
    assert "project_milestone" in cats

    r_proc = client.get("/api/v1/calendar-events?preset=procurement", headers=hdr)
    assert r_proc.status_code == 200
    proc_cats = {x["category"] for x in r_proc.get_json()["items"]}
    assert "schedule" not in proc_cats
    assert "procurement_order" in proc_cats

    r_proj = client.get(
        f"/api/v1/calendar-events?project_id={pid}&preset=project", headers=hdr
    )
    assert r_proj.status_code == 200
    body = r_proj.get_json()
    assert body["project_id"] == pid
    proj_cats = {x["category"] for x in body["items"]}
    assert "schedule" in proj_cats
    assert "procurement_order" not in proj_cats

    r_range = client.get(
        "/api/v1/calendar-events?start=2026-06-01&end=2026-06-10", headers=hdr
    )
    assert r_range.status_code == 200
    range_items = r_range.get_json()["items"]
    assert any(x["category"] == "schedule" for x in range_items)
    assert not any(x["category"] == "procurement_delivery" for x in range_items)
