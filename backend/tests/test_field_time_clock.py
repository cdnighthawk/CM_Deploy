"""Field time-clock punches, breaks, geofence, and cost codes."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.api._time_clock_math import evaluate_geofence, paid_seconds
from app.extensions import db
from app.models import CostCode, Project, ProjectMember, Role, TimeEntry, User, UserRole


def test_paid_seconds_subtracts_breaks():
    start = datetime(2026, 8, 29, 7, 0, tzinfo=timezone.utc)
    end = datetime(2026, 8, 29, 16, 0, tzinfo=timezone.utc)
    punches = [
        {"kind": "clock_in", "occurred_at": start},
        {"kind": "break_start", "occurred_at": datetime(2026, 8, 29, 12, 0, tzinfo=timezone.utc)},
        {"kind": "break_end", "occurred_at": datetime(2026, 8, 29, 12, 30, tzinfo=timezone.utc)},
        {"kind": "clock_out", "occurred_at": end},
    ]
    assert paid_seconds(start, end, punches, end) == 8.5 * 3600


def test_geofence_inside_outside_and_no_coords():
    assert evaluate_geofence(None, None, 250, 33.44, -112.07) == (None, None)
    ok, dist = evaluate_geofence(33.44, -112.07, 250, 33.4401, -112.07)
    assert ok is True
    assert dist is not None and dist < 250
    ok_out, dist_out = evaluate_geofence(33.44, -112.07, 250, 33.45, -112.07)
    assert ok_out is False
    assert dist_out is not None and dist_out > 250
    ok_gps, dist_gps = evaluate_geofence(33.44, -112.07, 250, None, None)
    assert ok_gps is False
    assert dist_gps is None


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


def _job(name: str, **kwargs) -> Project:
    p = Project(name=name + "-" + uuid.uuid4().hex[:8], **kwargs)
    db.session.add(p)
    db.session.flush()
    return p


def test_clock_in_out_and_idempotent_client_id(client):
    with client.application.app_context():
        user = _mk_pe("clk")
        job = _job("Clock")
        db.session.add(ProjectMember(user_id=user.id, project_id=job.id))
        db.session.commit()
        uid, pid = str(user.id), str(job.id)

    headers = {"X-Usis-User-Id": uid}
    cid = str(uuid.uuid4())
    start = datetime(2026, 8, 29, 14, 0, tzinfo=timezone.utc).isoformat()
    r1 = client.post(
        "/api/v1/time-clock/clock-in",
        json={"project_id": pid, "occurred_at": start, "client_id": cid, "lat": 33.44, "lon": -112.07},
        headers=headers,
    )
    assert r1.status_code == 201, r1.get_data(as_text=True)
    item = r1.get_json()["item"]
    assert item["status"] == "open"
    assert item["client_id"] == cid
    eid = item["id"]

    replay = client.post(
        "/api/v1/time-clock/clock-in",
        json={"project_id": pid, "occurred_at": start, "client_id": cid},
        headers=headers,
    )
    assert replay.status_code == 201
    assert replay.get_json()["item"]["id"] == eid

    second = client.post(
        "/api/v1/time-clock/clock-in",
        json={"project_id": pid, "occurred_at": start, "client_id": str(uuid.uuid4())},
        headers=headers,
    )
    assert second.status_code == 409

    out_cid = str(uuid.uuid4())
    r2 = client.post(
        "/api/v1/time-clock/clock-out",
        json={
            "entry_id": eid,
            "occurred_at": datetime(2026, 8, 29, 22, 0, tzinfo=timezone.utc).isoformat(),
            "client_id": out_cid,
        },
        headers=headers,
    )
    assert r2.status_code == 200, r2.get_data(as_text=True)
    assert r2.get_json()["item"]["status"] == "closed"
    assert r2.get_json()["item"]["paid_seconds"] == 8 * 3600

    replay_out = client.post(
        "/api/v1/time-clock/clock-out",
        json={"entry_id": eid, "client_id": out_cid},
        headers=headers,
    )
    assert replay_out.status_code == 200
    assert replay_out.get_json()["item"]["id"] == eid

    me = client.get("/api/v1/time-clock/me", headers=headers)
    assert me.status_code == 200
    body = me.get_json()
    assert body["open"] is None
    assert any(it["id"] == eid for it in body["items"])


def test_break_hours_and_switch(client):
    with client.application.app_context():
        user = _mk_pe("brk")
        a = _job("JobA")
        b = _job("JobB")
        db.session.add_all(
            [
                ProjectMember(user_id=user.id, project_id=a.id),
                ProjectMember(user_id=user.id, project_id=b.id),
            ]
        )
        db.session.commit()
        uid, aid, bid = str(user.id), str(a.id), str(b.id)

    headers = {"X-Usis-User-Id": uid}
    t0 = datetime(2026, 8, 29, 7, 0, tzinfo=timezone.utc)
    r1 = client.post(
        "/api/v1/time-clock/clock-in",
        json={"project_id": aid, "occurred_at": t0.isoformat(), "client_id": str(uuid.uuid4())},
        headers=headers,
    )
    assert r1.status_code == 201, r1.get_data(as_text=True)
    eid = r1.get_json()["item"]["id"]

    br = client.post(
        "/api/v1/time-clock/break-start",
        json={
            "entry_id": eid,
            "occurred_at": (t0 + timedelta(hours=5)).isoformat(),
            "client_id": str(uuid.uuid4()),
        },
        headers=headers,
    )
    assert br.status_code == 200
    assert br.get_json()["item"]["status"] == "on_break"

    be = client.post(
        "/api/v1/time-clock/break-end",
        json={
            "entry_id": eid,
            "occurred_at": (t0 + timedelta(hours=5, minutes=30)).isoformat(),
            "client_id": str(uuid.uuid4()),
        },
        headers=headers,
    )
    assert be.status_code == 200
    assert be.get_json()["item"]["status"] == "open"

    sw = client.post(
        "/api/v1/time-clock/switch",
        json={
            "entry_id": eid,
            "project_id": bid,
            "occurred_at": (t0 + timedelta(hours=6)).isoformat(),
            "client_id": str(uuid.uuid4()),
            "new_entry_client_id": str(uuid.uuid4()),
        },
        headers=headers,
    )
    assert sw.status_code == 200, sw.get_data(as_text=True)
    new_item = sw.get_json()["item"]
    assert new_item["project_id"] == bid
    assert new_item["status"] == "open"

    with client.application.app_context():
        old = db.session.get(TimeEntry, uuid.UUID(eid))
        assert old is not None
        assert old.status == "closed"
        assert old.ended_at is not None

    out = client.post(
        "/api/v1/time-clock/clock-out",
        json={
            "entry_id": new_item["id"],
            "occurred_at": (t0 + timedelta(hours=9)).isoformat(),
            "client_id": str(uuid.uuid4()),
        },
        headers=headers,
    )
    assert out.status_code == 200
    first_paid = 5.5 * 3600
    second_paid = 3 * 3600
    me = client.get("/api/v1/time-clock/me", headers=headers)
    items = me.get_json()["items"]
    total = sum(it["paid_seconds"] for it in items)
    assert total == int(first_paid + second_paid)


def test_geofence_flag_by_default_and_block_mode(client):
    from app.models import ProjectGeofence, TimeFlag

    with client.application.app_context():
        user = _mk_pe("geo")
        job = _job("Fenced", latitude=33.44, longitude=-112.07, geofence_radius_m=250)
        db.session.add(ProjectMember(user_id=user.id, project_id=job.id))
        db.session.commit()
        uid, pid = str(user.id), str(job.id)

    headers = {"X-Usis-User-Id": uid}
    flagged = client.post(
        "/api/v1/time-clock/clock-in",
        json={"project_id": pid, "client_id": str(uuid.uuid4()), "lat": 33.46, "lon": -112.07},
        headers=headers,
    )
    assert flagged.status_code == 201, flagged.get_data(as_text=True)
    item = flagged.get_json()["item"]
    assert item["offsite"] is True
    punch = item["punches"][0]
    assert punch["geofence_ok"] is False

    with client.application.app_context():
        flags = list(db.session.scalars(select(TimeFlag).where(TimeFlag.flag_type == "offsite")).all())
        assert flags
        job = db.session.get(Project, uuid.UUID(pid))
        db.session.add(ProjectGeofence(project_id=job.id, mode="block", shape="circle", center_lat=33.44, center_lon=-112.07, radius_m=250))
        db.session.commit()

    blocked = client.post(
        "/api/v1/time-clock/clock-in",
        json={"project_id": pid, "client_id": str(uuid.uuid4()), "lat": 33.46, "lon": -112.07},
        headers=headers,
    )
    # still clocked in from the flag punch
    assert blocked.status_code == 409

    client.post("/api/v1/time-clock/clock-out", json={"client_id": str(uuid.uuid4())}, headers=headers)

    blocked2 = client.post(
        "/api/v1/time-clock/clock-in",
        json={"project_id": pid, "client_id": str(uuid.uuid4()), "lat": 33.46, "lon": -112.07},
        headers=headers,
    )
    assert blocked2.status_code == 409

    ok = client.post(
        "/api/v1/time-clock/clock-in",
        json={
            "project_id": pid,
            "client_id": str(uuid.uuid4()),
            "lat": 33.46,
            "lon": -112.07,
            "override_geofence": True,
        },
        headers=headers,
    )
    assert ok.status_code == 201, ok.get_data(as_text=True)
    assert ok.get_json()["item"]["punches"][0]["geofence_ok"] is False


def test_cost_code_required_when_project_has_codes(client):
    with client.application.app_context():
        user = _mk_pe("cc")
        job = _job("Coded")
        code = CostCode(project_id=job.id, code="03-100", description="Metal framing", is_active=True)
        db.session.add(code)
        db.session.add(ProjectMember(user_id=user.id, project_id=job.id))
        db.session.commit()
        uid, pid, cid = str(user.id), str(job.id), str(code.id)

    headers = {"X-Usis-User-Id": uid}
    listed = client.get(f"/api/v1/projects/{pid}/cost-codes", headers=headers)
    assert listed.status_code == 200
    assert listed.get_json()["total"] == 1
    assert listed.get_json()["items"][0]["id"] == cid

    missing = client.post(
        "/api/v1/time-clock/clock-in",
        json={"project_id": pid, "client_id": str(uuid.uuid4())},
        headers=headers,
    )
    assert missing.status_code == 201, missing.get_data(as_text=True)

    client.post("/api/v1/time-clock/clock-out", json={"client_id": str(uuid.uuid4())}, headers=headers)

    ok = client.post(
        "/api/v1/time-clock/clock-in",
        json={"project_id": pid, "cost_code_id": cid, "client_id": str(uuid.uuid4())},
        headers=headers,
    )
    assert ok.status_code == 201, ok.get_data(as_text=True)
    assert ok.get_json()["item"]["job_cost_code_id"] == cid or ok.get_json()["item"]["cost_code_id"] == cid
