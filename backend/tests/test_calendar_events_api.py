"""API tests for categorized calendar events feed."""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

import pytest
from sqlalchemy import select

from app.extensions import db
from app.models import (
    Commitment,
    Company,
    Project,
    ProjectMaterialOrder,
    ProjectMember,
    ProjectScheduleItem,
    Rfi,
    RfiAssignee,
    Role,
    Submittal,
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
        p = Project(
            name="CalProj-" + uuid.uuid4().hex[:8],
            start_date=date(2026, 7, 1),
            status="active",
        )
        v = Company(name="CalVendor-" + uuid.uuid4().hex[:6], company_type="vendor")
        db.session.add_all([p, v])
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
            vendor_company_id=v.id,
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

    r_active_before = client.get("/api/v1/calendar-events?project_status=active", headers=hdr)
    assert r_active_before.status_code == 200
    assert any(x["project_id"] == pid for x in r_active_before.get_json()["items"])

    with client.application.app_context():
        proj = db.session.get(Project, uuid.UUID(pid))
        assert proj is not None
        proj.status = "complete"
        db.session.commit()

    r_active = client.get("/api/v1/calendar-events?project_status=active", headers=hdr)
    assert r_active.status_code == 200
    active_items = r_active.get_json()["items"]
    assert not any(x["project_id"] == pid for x in active_items)


def test_calendar_events_assignee_me_filter(client, no_dev_admin):
    with client.application.app_context():
        role = db.session.scalar(select(Role).where(Role.code == "standard"))
        if role is None:
            role = Role(code="standard", name="Standard")
            db.session.add(role)
            db.session.flush()
        owner = User(email="cal_own_" + uuid.uuid4().hex[:8] + "@t.com", first_name="A", last_name="Owner")
        assignee = User(
            email="cal_asg_" + uuid.uuid4().hex[:8] + "@t.com",
            first_name="B",
            last_name="Assignee",
        )
        db.session.add_all([owner, assignee])
        db.session.flush()
        db.session.add(UserRole(user_id=owner.id, role_id=role.id))
        db.session.add(UserRole(user_id=assignee.id, role_id=role.id))
        p = Project(name="CalAssign-" + uuid.uuid4().hex[:8], status="active")
        db.session.add(p)
        db.session.flush()
        db.session.add(ProjectMember(user_id=owner.id, project_id=p.id))
        db.session.add(ProjectMember(user_id=assignee.id, project_id=p.id))
        db.session.add(
            ProjectScheduleItem(
                project_id=p.id,
                title="Submit closeout docs",
                start_date=date(2026, 8, 28),
                end_date=date(2026, 8, 29),
                assignee_user_id=assignee.id,
            )
        )
        db.session.add(
            ProjectScheduleItem(
                project_id=p.id,
                title="Unassigned window",
                start_date=date(2026, 8, 28),
                end_date=date(2026, 8, 29),
            )
        )
        owner_id = str(owner.id)
        assignee_id = str(assignee.id)
        db.session.commit()

    mine = client.get(
        "/api/v1/calendar-events?assignee=me",
        headers={"X-Usis-User-Id": assignee_id},
    )
    assert mine.status_code == 200, mine.get_data(as_text=True)
    mine_items = mine.get_json()["items"]
    assert any(x["source_type"] == "schedule_item" and "Submit closeout docs" in x["title"] for x in mine_items)
    assert not any("Unassigned window" in x["title"] for x in mine_items)
    assert not any(x["category"] == "project_milestone" for x in mine_items)
    assert mine.get_json()["assignee_user_id"] == assignee_id

    others = client.get(
        "/api/v1/calendar-events?assignee=me",
        headers={"X-Usis-User-Id": owner_id},
    )
    assert others.status_code == 200
    assert others.get_json()["items"] == []

    r_bad = client.get(
        "/api/v1/calendar-events?assignee=nope",
        headers={"X-Usis-User-Id": assignee_id},
    )
    assert r_bad.status_code == 400


def test_calendar_events_assignee_me_includes_rfi_and_submittal(client, no_dev_admin):
    with client.application.app_context():
        role = db.session.scalar(select(Role).where(Role.code == "standard"))
        if role is None:
            role = Role(code="standard", name="Standard")
            db.session.add(role)
            db.session.flush()
        assignee = User(
            email="cal_doc_" + uuid.uuid4().hex[:8] + "@t.com",
            first_name="Dana",
            last_name="Cole",
        )
        db.session.add(assignee)
        db.session.flush()
        db.session.add(UserRole(user_id=assignee.id, role_id=role.id))
        p = Project(name="CalDocs-" + uuid.uuid4().hex[:8], status="active")
        db.session.add(p)
        db.session.flush()
        db.session.add(ProjectMember(user_id=assignee.id, project_id=p.id))
        rfi = Rfi(
            project_id=p.id,
            number=4,
            subject="Submit closeout package",
            status="open",
            due_at=datetime(2026, 9, 3, 12, 0, tzinfo=timezone.utc),
        )
        db.session.add(rfi)
        db.session.flush()
        db.session.add(RfiAssignee(rfi_id=rfi.id, user_id=assignee.id, is_required=True))
        db.session.add(
            Submittal(
                project_id=p.id,
                number=7,
                title="Door hardware cut sheets",
                status="open",
                due_at=datetime(2026, 9, 4, 12, 0, tzinfo=timezone.utc),
                assigned_reviewer_id=assignee.id,
            )
        )
        db.session.add(
            Rfi(
                project_id=p.id,
                number=5,
                subject="Someone else's RFI",
                status="open",
                due_at=datetime(2026, 9, 5, 12, 0, tzinfo=timezone.utc),
            )
        )
        assignee_id = str(assignee.id)
        db.session.commit()

    mine = client.get(
        "/api/v1/calendar-events?assignee=me",
        headers={"X-Usis-User-Id": assignee_id},
    )
    assert mine.status_code == 200, mine.get_data(as_text=True)
    items = mine.get_json()["items"]
    titles = [x["title"] for x in items]
    assert any(x["source_type"] == "rfi" and "Submit closeout package" in x["title"] for x in items)
    assert any(x["source_type"] == "submittal" and "Door hardware cut sheets" in x["title"] for x in items)
    assert any("Dana Cole" in t for t in titles)
    assert not any("Someone else's RFI" in t for t in titles)
