"""API tests for project pay applications (G702-style)."""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.extensions import db
from app.models import PrimeContractSovLine, Project, Role, User, UserRole


@pytest.fixture
def no_dev_admin(monkeypatch):
    monkeypatch.setenv("USIS_API_DEV_ALLOW_ANY", "0")


def test_pay_application_create_patch_lines_delete(client, no_dev_admin):
    with client.application.app_context():
        role = db.session.scalar(select(Role).where(Role.code == "standard"))
        if role is None:
            role = Role(code="standard", name="Standard")
            db.session.add(role)
            db.session.flush()
        u = User(email="pay_u_" + uuid.uuid4().hex[:8] + "@t.com", first_name="Pay", last_name="App")
        db.session.add(u)
        db.session.flush()
        db.session.add(UserRole(user_id=u.id, role_id=role.id))
        p = Project(name="PayProj-" + uuid.uuid4().hex[:8], contract_value="100000.00")
        db.session.add(p)
        db.session.flush()
        pid = str(p.id)
        uid = str(u.id)
        db.session.commit()

    hdr = {"X-Usis-User-Id": uid}

    r0 = client.post(f"/api/v1/projects/{pid}/pay-applications", json={}, headers=hdr)
    assert r0.status_code == 201, r0.get_data(as_text=True)
    body0 = r0.get_json()
    assert body0["item"]["application_number"] == 1
    assert body0["item"]["original_contract_sum"] == "100000.00"
    aid = body0["item"]["id"]

    r1 = client.patch(
        f"/api/v1/projects/{pid}/pay-applications/{aid}",
        json={
            "period_to": "2026-05-31",
            "net_change_by_change_orders": "5000.00",
            "lines": [
                {
                    "sort_order": 0,
                    "phase_code": "001",
                    "description": "Mobilization",
                    "scheduled_value": "10000.00",
                    "net_change_co": "0",
                    "work_from_previous": "0",
                    "work_this_period": "5000.00",
                    "materials_stored": "0",
                    "retention_to_date": "500.00",
                }
            ],
        },
        headers=hdr,
    )
    assert r1.status_code == 200, r1.get_data(as_text=True)
    b1 = r1.get_json()
    assert len(b1["lines"]) == 1
    assert b1["item"]["contract_sum_to_date"] == "105000.00"
    assert b1["item"]["total_completed_and_stored_to_date"] == "5000.00"

    r2 = client.get(f"/api/v1/projects/{pid}/pay-applications", headers=hdr)
    assert r2.status_code == 200
    assert len(r2.get_json()["items"]) == 1

    r3 = client.delete(f"/api/v1/projects/{pid}/pay-applications/{aid}", headers=hdr)
    assert r3.status_code == 204


def test_pay_application_collection_status_and_paid_on(client, no_dev_admin):
    with client.application.app_context():
        role = db.session.scalar(select(Role).where(Role.code == "standard"))
        if role is None:
            role = Role(code="standard", name="Standard")
            db.session.add(role)
            db.session.flush()
        u = User(email="pay_col_" + uuid.uuid4().hex[:8] + "@t.com", first_name="Pay", last_name="Col")
        db.session.add(u)
        db.session.flush()
        db.session.add(UserRole(user_id=u.id, role_id=role.id))
        p = Project(name="PayCol-" + uuid.uuid4().hex[:8], contract_value="25000.00")
        db.session.add(p)
        db.session.flush()
        pid = str(p.id)
        uid = str(u.id)
        db.session.commit()

    hdr = {"X-Usis-User-Id": uid}
    created = client.post(f"/api/v1/projects/{pid}/pay-applications", json={}, headers=hdr)
    assert created.status_code == 201, created.get_data(as_text=True)
    aid = created.get_json()["item"]["id"]
    assert created.get_json()["item"]["paid_at"] is None

    held = client.patch(
        f"/api/v1/projects/{pid}/pay-applications/{aid}",
        json={"status": "held"},
        headers=hdr,
    )
    assert held.status_code == 200, held.get_data(as_text=True)
    assert held.get_json()["item"]["status"] == "held"
    assert held.get_json()["item"]["paid_at"] is None

    paid = client.patch(
        f"/api/v1/projects/{pid}/pay-applications/{aid}",
        json={"status": "paid", "paid_at": "2026-08-15"},
        headers=hdr,
    )
    assert paid.status_code == 200, paid.get_data(as_text=True)
    item = paid.get_json()["item"]
    assert item["status"] == "paid"
    assert item["paid_at"] is not None
    assert str(item["paid_at"]).startswith("2026-08-15")

    rejected = client.patch(
        f"/api/v1/projects/{pid}/pay-applications/{aid}",
        json={"status": "rejected"},
        headers=hdr,
    )
    assert rejected.status_code == 200, rejected.get_data(as_text=True)
    assert rejected.get_json()["item"]["status"] == "rejected"
    assert rejected.get_json()["item"]["paid_at"] is None


def _standard_user_and_project(contract_value: str | None = "100000.00"):
    role = db.session.scalar(select(Role).where(Role.code == "standard"))
    if role is None:
        role = Role(code="standard", name="Standard")
        db.session.add(role)
        db.session.flush()
    u = User(email="pay_sov_" + uuid.uuid4().hex[:8] + "@t.com", first_name="Pay", last_name="Sov")
    db.session.add(u)
    db.session.flush()
    db.session.add(UserRole(user_id=u.id, role_id=role.id))
    p = Project(name="PaySov-" + uuid.uuid4().hex[:8], contract_value=contract_value)
    db.session.add(p)
    db.session.flush()
    return u, p


def test_pay_application_seeds_from_prime_sov(client, no_dev_admin):
    with client.application.app_context():
        u, p = _standard_user_and_project("50000.00")
        db.session.add(
            PrimeContractSovLine(
                project_id=p.id, sort_order=0, phase_code="01", description="General", scheduled_value="20000.00"
            )
        )
        db.session.add(
            PrimeContractSovLine(
                project_id=p.id, sort_order=1, phase_code="02", description="Site", scheduled_value="30000.00"
            )
        )
        pid = str(p.id)
        uid = str(u.id)
        db.session.commit()

    hdr = {"X-Usis-User-Id": uid}
    created = client.post(f"/api/v1/projects/{pid}/pay-applications", json={}, headers=hdr)
    assert created.status_code == 201, created.get_data(as_text=True)
    body = created.get_json()
    lines = body["lines"]
    assert len(lines) == 2
    assert lines[0]["phase_code"] == "01"
    assert lines[0]["scheduled_value"] == "20000.00"
    assert lines[0]["work_this_period"] == "0.00"
    assert lines[1]["description"] == "Site"
    listed = client.get(f"/api/v1/projects/{pid}/pay-applications", headers=hdr)
    assert listed.status_code == 200
    assert listed.get_json()["prime_sov"]["line_count"] == 2
    assert listed.get_json()["prime_sov"]["total_scheduled_value"] == "50000.00"


def test_pay_application_carries_prior_work_into_next_sov(client, no_dev_admin):
    with client.application.app_context():
        u, p = _standard_user_and_project("10000.00")
        db.session.add(
            PrimeContractSovLine(
                project_id=p.id, sort_order=0, phase_code="001", description="Mobilization", scheduled_value="10000.00"
            )
        )
        pid = str(p.id)
        uid = str(u.id)
        db.session.commit()

    hdr = {"X-Usis-User-Id": uid}
    first = client.post(f"/api/v1/projects/{pid}/pay-applications", json={}, headers=hdr)
    assert first.status_code == 201, first.get_data(as_text=True)
    aid = first.get_json()["item"]["id"]
    patched = client.patch(
        f"/api/v1/projects/{pid}/pay-applications/{aid}",
        json={
            "lines": [
                {
                    "sort_order": 0,
                    "phase_code": "001",
                    "description": "Mobilization",
                    "scheduled_value": "10000.00",
                    "work_from_previous": "0",
                    "work_this_period": "4000.00",
                    "materials_stored": "500.00",
                    "retention_to_date": "450.00",
                }
            ]
        },
        headers=hdr,
    )
    assert patched.status_code == 200, patched.get_data(as_text=True)
    submitted = client.patch(
        f"/api/v1/projects/{pid}/pay-applications/{aid}",
        json={"status": "submitted"},
        headers=hdr,
    )
    assert submitted.status_code == 200, submitted.get_data(as_text=True)

    second = client.post(f"/api/v1/projects/{pid}/pay-applications", json={}, headers=hdr)
    assert second.status_code == 201, second.get_data(as_text=True)
    line = second.get_json()["lines"][0]
    assert line["phase_code"] == "001"
    assert line["scheduled_value"] == "10000.00"
    assert line["work_from_previous"] == "4500.00"
    assert line["work_this_period"] == "0.00"
    assert line["retention_to_date"] == "450.00"


def test_map_invoice_status_collection_states():
    from app.integrations.textura_sync import _map_invoice_status

    assert _map_invoice_status("held") == "held"
    assert _map_invoice_status("on hold") == "held"
    assert _map_invoice_status("rejected") == "rejected"
    assert _map_invoice_status("unapproved") == "rejected"
    assert _map_invoice_status("paid") == "paid"
    assert _map_invoice_status("2") == "paid"
    assert _map_invoice_status("1") == "certified"
    assert _map_invoice_status("pending") == "submitted"
