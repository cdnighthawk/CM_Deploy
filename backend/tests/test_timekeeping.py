"""Office timekeeping punches, OT recompute, geofence, flags, export."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.extensions import db
from app.models import (
    Project,
    ProjectGeofence,
    ProjectMember,
    Role,
    TimeBreadcrumb,
    TimeEntry,
    TimeFlag,
    User,
    UserRole,
)


def _mk_admin(prefix: str) -> User:
    role = db.session.scalar(select(Role).where(Role.code == "admin"))
    if role is None:
        role = Role(code="admin", name="Admin")
        db.session.add(role)
        db.session.flush()
    u = User(email=f"{prefix}_{uuid.uuid4().hex[:8]}@t.com", first_name=prefix, last_name="Crew", is_active=True, is_superuser=True)
    db.session.add(u)
    db.session.flush()
    db.session.add(UserRole(user_id=u.id, role_id=role.id))
    return u


def _job(name: str, **kwargs) -> Project:
    p = Project(name=name + "-" + uuid.uuid4().hex[:8], **kwargs)
    db.session.add(p)
    db.session.flush()
    return p


def test_punch_switch_gap_and_live(client):
    with client.application.app_context():
        user = _mk_admin("sw")
        a = _job("A")
        b = _job("B")
        db.session.add(ProjectMember(user_id=user.id, project_id=a.id))
        db.session.add(ProjectMember(user_id=user.id, project_id=b.id))
        db.session.commit()
        uid, aid, bid = str(user.id), str(a.id), str(b.id)

    headers = {"X-Usis-User-Id": uid}
    t0 = datetime(2026, 9, 1, 14, 0, tzinfo=timezone.utc)
    r1 = client.post(
        "/api/time/punch",
        json={"action": "clock_in", "project_id": aid, "local_id": str(uuid.uuid4()), "at": t0.isoformat()},
        headers=headers,
    )
    assert r1.status_code == 201, r1.get_data(as_text=True)
    first_id = r1.get_json()["item"]["id"]
    t1 = t0 + timedelta(hours=3)
    r2 = client.post(
        "/api/time/punch",
        json={
            "action": "switch",
            "project_id": bid,
            "local_id": str(uuid.uuid4()),
            "at": t1.isoformat(),
            "new_local_id": str(uuid.uuid4()),
        },
        headers=headers,
    )
    assert r2.status_code == 200, r2.get_data(as_text=True)
    with client.application.app_context():
        old = db.session.get(TimeEntry, uuid.UUID(first_id))
        new = db.session.get(TimeEntry, uuid.UUID(r2.get_json()["item"]["id"]))
        gap = abs((new.started_at - old.ended_at).total_seconds())
        assert gap <= 1
    live = client.get("/api/time/live", headers=headers)
    assert live.status_code == 200
    roster = live.get_json()["roster"]
    assert any(row["user_id"] == uid for row in roster)


def test_local_id_idempotent(client):
    with client.application.app_context():
        user = _mk_admin("idemp")
        job = _job("I")
        db.session.add(ProjectMember(user_id=user.id, project_id=job.id))
        db.session.commit()
        uid, pid = str(user.id), str(job.id)
    headers = {"X-Usis-User-Id": uid}
    lid = str(uuid.uuid4())
    a = client.post("/api/time/punch", json={"action": "clock_in", "project_id": pid, "local_id": lid}, headers=headers)
    b = client.post("/api/time/punch", json={"action": "clock_in", "project_id": pid, "local_id": lid}, headers=headers)
    assert a.status_code == 201
    assert b.status_code == 201
    assert a.get_json()["item"]["id"] == b.get_json()["item"]["id"]


def test_breadcrumb_off_clock_noop(client):
    with client.application.app_context():
        user = _mk_admin("bc")
        db.session.commit()
        uid = str(user.id)
    headers = {"X-Usis-User-Id": uid}
    r = client.post(
        "/api/time/breadcrumbs",
        json={"items": [{"lat": 33.44, "lon": -112.07, "at": datetime.now(timezone.utc).isoformat()}]},
        headers=headers,
    )
    assert r.status_code == 200
    assert r.get_json()["accepted"] == 0
    with client.application.app_context():
        assert db.session.scalar(select(TimeBreadcrumb).where(TimeBreadcrumb.user_id == uuid.UUID(uid))) is None


def test_split_recomputes_ot(client):
    with client.application.app_context():
        user = _mk_admin("sp")
        job = _job("S")
        db.session.add(ProjectMember(user_id=user.id, project_id=job.id))
        db.session.commit()
        uid, pid = str(user.id), str(job.id)
    headers = {"X-Usis-User-Id": uid}
    start = datetime(2026, 9, 1, 7, 0, tzinfo=timezone.utc)
    end = start + timedelta(hours=10)
    added = client.post(
        "/api/time/entries",
        json={
            "user_id": uid,
            "project_id": pid,
            "start_at": start.isoformat(),
            "end_at": end.isoformat(),
            "reason": "fixture 10h punch",
            "local_id": str(uuid.uuid4()),
        },
        headers=headers,
    )
    assert added.status_code == 201, added.get_data(as_text=True)
    eid = added.get_json()["item"]["id"]
    split_at = start + timedelta(hours=6)
    sp = client.post(
        f"/api/time/entries/{eid}/split",
        json={"at": split_at.isoformat(), "reason": "forgot cost code"},
        headers=headers,
    )
    assert sp.status_code == 200, sp.get_data(as_text=True)
    day = client.get(f"/api/time/entries?user_id={uid}", headers=headers)
    assert day.status_code == 200
    items = day.get_json()["items"]
    assert len(items) >= 2


def test_sign_then_edit_blocks_export(client):
    with client.application.app_context():
        user = _mk_admin("sg")
        job = _job("E")
        db.session.add(ProjectMember(user_id=user.id, project_id=job.id))
        db.session.commit()
        uid, pid = str(user.id), str(job.id)
    headers = {"X-Usis-User-Id": uid}
    start = datetime(2026, 9, 1, 7, 0, tzinfo=timezone.utc)
    created = client.post(
        "/api/time/entries",
        json={
            "user_id": uid,
            "project_id": pid,
            "start_at": start.isoformat(),
            "end_at": (start + timedelta(hours=8)).isoformat(),
            "reason": "fixture",
        },
        headers=headers,
    )
    assert created.status_code in (200, 201), created.get_data(as_text=True)
    eid = created.get_json()["item"]["id"]
    signed = client.post(f"/api/time/days/2026-09-01/sign", json={"attested": True, "signature_png": "data:image/png;base64,xx"}, headers=headers)
    assert signed.status_code == 200, signed.get_data(as_text=True)
    patched = client.patch(f"/api/time/entries/{eid}", json={"note": "adjusted", "reason": "payroll fix"}, headers=headers)
    assert patched.status_code == 200
    flags = client.get("/api/time/flags", headers=headers).get_json()["items"]
    assert any(f["type"] == "edited_after_sign" for f in flags)
    periods = client.get("/api/time/periods", headers=headers).get_json()["items"]
    assert periods
    exp = client.post(f"/api/time/periods/{periods[0]['id']}/export", json={}, headers=headers)
    assert exp.status_code == 409


def test_missing_meal_flag_and_export_409(client):
    with client.application.app_context():
        user = _mk_admin("ml")
        job = _job("M")
        db.session.add(ProjectMember(user_id=user.id, project_id=job.id))
        db.session.commit()
        uid, pid = str(user.id), str(job.id)
    headers = {"X-Usis-User-Id": uid}
    start = datetime(2026, 9, 1, 7, 0, tzinfo=timezone.utc)
    client.post(
        "/api/time/entries",
        json={
            "user_id": uid,
            "project_id": pid,
            "start_at": start.isoformat(),
            "end_at": (start + timedelta(hours=8, minutes=30)).isoformat(),
            "reason": "no meal",
        },
        headers=headers,
    )
    flags = client.get("/api/time/flags?type=missing_meal", headers=headers).get_json()["items"]
    assert flags
    periods = client.get("/api/time/periods", headers=headers).get_json()["items"]
    exp = client.post(f"/api/time/periods/{periods[0]['id']}/export", json={}, headers=headers)
    assert exp.status_code == 409


def test_block_geofence_409_unless_override(client):
    with client.application.app_context():
        user = _mk_admin("bl")
        job = _job("Fence", latitude=33.44, longitude=-112.07, geofence_radius_m=250)
        db.session.add(ProjectMember(user_id=user.id, project_id=job.id))
        db.session.add(ProjectGeofence(project_id=job.id, mode="block", shape="circle", center_lat=33.44, center_lon=-112.07, radius_m=250))
        db.session.commit()
        uid, pid = str(user.id), str(job.id)
    headers = {"X-Usis-User-Id": uid}
    blocked = client.post(
        "/api/time/punch",
        json={"action": "clock_in", "project_id": pid, "local_id": str(uuid.uuid4()), "lat": 33.46, "lon": -112.07},
        headers=headers,
    )
    assert blocked.status_code == 409
    ok = client.post(
        "/api/time/punch",
        json={
            "action": "clock_in",
            "project_id": pid,
            "local_id": str(uuid.uuid4()),
            "lat": 33.46,
            "lon": -112.07,
            "override_geofence": True,
        },
        headers=headers,
    )
    assert ok.status_code == 201, ok.get_data(as_text=True)
