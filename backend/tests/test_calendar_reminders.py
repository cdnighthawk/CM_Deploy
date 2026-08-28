"""Due-date reminders for assigned schedule windows."""
from __future__ import annotations

import uuid
from datetime import date, timedelta

import pytest
from sqlalchemy import select

from app.extensions import db
from app.models import Project, ProjectScheduleItem, Role, User, UserRole
from app.models.hrms_core import HrmsNotification


@pytest.fixture
def no_dev_admin(monkeypatch):
    monkeypatch.setenv("USIS_API_DEV_ALLOW_ANY", "0")


def test_due_schedule_reminders_once(client, no_dev_admin):
    tomorrow = date.today() + timedelta(days=1)
    with client.application.app_context():
        role = db.session.scalar(select(Role).where(Role.code == "standard"))
        if role is None:
            role = Role(code="standard", name="Standard")
            db.session.add(role)
            db.session.flush()
        actor = User(email="rem_actor_" + uuid.uuid4().hex[:8] + "@t.com")
        assignee = User(
            email="rem_asg_" + uuid.uuid4().hex[:8] + "@t.com",
            first_name="Kim",
            last_name="Ortiz",
        )
        db.session.add_all([actor, assignee])
        db.session.flush()
        db.session.add(UserRole(user_id=actor.id, role_id=role.id))
        p = Project(name="RemProj-" + uuid.uuid4().hex[:8], status="active")
        db.session.add(p)
        db.session.flush()
        db.session.add(
            ProjectScheduleItem(
                project_id=p.id,
                title="Receive door hardware",
                start_date=tomorrow,
                end_date=tomorrow,
                assignee_user_id=assignee.id,
            )
        )
        actor_id = str(actor.id)
        assignee_id = str(assignee.id)
        db.session.commit()

    first = client.post(
        "/api/v1/integrations/calendar-reminders/run",
        headers={"X-Usis-User-Id": actor_id},
    )
    assert first.status_code == 200, first.get_data(as_text=True)
    assert first.get_json()["sent"] >= 1

    second = client.post(
        "/api/v1/integrations/calendar-reminders/run",
        headers={"X-Usis-User-Id": actor_id},
    )
    assert second.status_code == 200
    assert second.get_json()["sent"] == 0

    with client.application.app_context():
        notes = db.session.scalars(
            select(HrmsNotification).where(HrmsNotification.user_id == uuid.UUID(assignee_id))
        ).all()
        assert any("Receive door hardware" in (n.title or "") for n in notes)


def test_calendar_reminders_accept_cron_secret(client, flask_app, no_dev_admin, monkeypatch):
    monkeypatch.setitem(flask_app.config, "BC_SYNC_CRON_SECRET", "cal-cron-secret")
    r = client.post(
        "/api/v1/integrations/calendar-reminders/run",
        headers={"X-Cron-Secret": "cal-cron-secret"},
    )
    assert r.status_code == 200, r.get_data(as_text=True)
    assert r.get_json()["entity"] == "calendar_reminders"
