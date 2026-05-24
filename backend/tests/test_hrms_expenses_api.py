"""HRMS expense report API."""
from __future__ import annotations

import io
import uuid
from datetime import date

import pytest
from sqlalchemy import select

from app.extensions import db
from app.models import Project, Role, User, UserRole
from app.models.hrms_core import HrmsExpenseReport


@pytest.fixture
def expense_project(flask_app):
    with flask_app.app_context():
        p = Project(name=f"ExpProj-{uuid.uuid4().hex[:8]}", status="active", project_type="commercial")
        db.session.add(p)
        db.session.commit()
        pid = p.id
        yield str(pid)
        p2 = db.session.get(Project, pid)
        if p2 is not None:
            db.session.delete(p2)
            db.session.commit()


@pytest.fixture
def expense_users(flask_app, expense_project):
    with flask_app.app_context():
        emp_email = f"exp.emp.{uuid.uuid4().hex[:8]}@usis.local"
        admin_email = f"exp.admin.{uuid.uuid4().hex[:8]}@usis.local"
        employee = User(email=emp_email, first_name="Exp", last_name="Employee", is_active=True, is_superuser=True)
        admin = User(email=admin_email, first_name="Exp", last_name="Admin", is_active=True)
        db.session.add_all([employee, admin])
        db.session.flush()
        hr_admin_role = db.session.scalar(select(Role).where(Role.code == "hr_admin"))
        if hr_admin_role is None:
            hr_admin_role = Role(code="hr_admin", name="HR Admin")
            db.session.add(hr_admin_role)
            db.session.flush()
        db.session.add(UserRole(user_id=admin.id, role_id=hr_admin_role.id))
        db.session.commit()
        out = {
            "employee_id": str(employee.id),
            "admin_id": str(admin.id),
            "project_id": expense_project,
        }
        yield out
        for uid in (employee.id, admin.id):
            u = db.session.get(User, uid)
            if u is not None:
                db.session.delete(u)
        db.session.commit()


def _headers(user_id: str) -> dict[str, str]:
    return {"X-Usis-User-Id": user_id, "Accept": "application/json"}


def test_expense_report_submit_requires_receipt(client, expense_users):
    emp = expense_users["employee_id"]
    proj = expense_users["project_id"]
    h = _headers(emp)
    r = client.post("/api/v1/hrms/expense-reports", json={"title": "Test trip"}, headers=h)
    assert r.status_code == 200
    report_id = r.get_json()["item"]["id"]
    r2 = client.post(
        f"/api/v1/hrms/expense-reports/{report_id}/lines",
        json={
            "spent_at": date.today().isoformat(),
            "amount": "42.50",
            "category": "fuel",
            "project_id": proj,
            "merchant": "Gas station",
        },
        headers=h,
    )
    assert r2.status_code == 200
    r3 = client.post(f"/api/v1/hrms/expense-reports/{report_id}/submit", headers=h)
    assert r3.status_code == 400
    assert "receipt" in (r3.get_json().get("error") or "").lower()


def test_expense_full_workflow(client, expense_users):
    emp = expense_users["employee_id"]
    admin = expense_users["admin_id"]
    proj = expense_users["project_id"]
    h_emp = _headers(emp)
    h_admin = _headers(admin)

    r = client.post("/api/v1/hrms/expense-reports", json={"title": "Field tools March"}, headers=h_emp)
    assert r.status_code == 200
    report_id = r.get_json()["item"]["id"]

    r_line = client.post(
        f"/api/v1/hrms/expense-reports/{report_id}/lines",
        json={
            "spent_at": date.today().isoformat(),
            "amount": "89.99",
            "category": "tools",
            "project_id": proj,
            "merchant": "Supply Co",
            "description": "Drill bits",
        },
        headers=h_emp,
    )
    assert r_line.status_code == 200
    line_id = r_line.get_json()["item"]["id"]

    data = {"file": (io.BytesIO(b"\xff\xd8\xff fake jpeg"), "receipt.jpg")}
    r_up = client.post(
        f"/api/v1/hrms/expense-reports/{report_id}/lines/{line_id}/receipt",
        data=data,
        content_type="multipart/form-data",
        headers={"X-Usis-User-Id": emp},
    )
    assert r_up.status_code == 200

    r_sub = client.post(f"/api/v1/hrms/expense-reports/{report_id}/submit", headers=h_emp)
    assert r_sub.status_code == 200
    assert r_sub.get_json()["item"]["status"] == "submitted"

    r_appr = client.get("/api/v1/hrms/expense-reports/approvals", headers=h_admin)
    assert r_appr.status_code == 200
    ids = [row["id"] for row in r_appr.get_json().get("items") or []]
    assert report_id in ids

    r_ok = client.post(f"/api/v1/hrms/expense-reports/{report_id}/approve", headers=h_admin)
    assert r_ok.status_code == 200
    assert r_ok.get_json()["item"]["status"] == "approved"

    r_csv = client.get("/api/v1/hrms/expense-reports/export.csv", headers=h_admin)
    assert r_csv.status_code == 200
    assert "text/csv" in (r_csv.content_type or "")
    assert b"Field tools March" in r_csv.data

    r_reimb = client.post(f"/api/v1/hrms/expense-reports/{report_id}/mark-reimbursed", headers=h_admin)
    assert r_reimb.status_code == 200
    assert r_reimb.get_json()["item"]["status"] == "reimbursed"

    with client.application.app_context():
        row = db.session.get(HrmsExpenseReport, uuid.UUID(report_id))
        assert row is not None
        assert row.reimbursed_at is not None


def test_expense_reject_requires_reason(client, expense_users):
    emp = expense_users["employee_id"]
    admin = expense_users["admin_id"]
    proj = expense_users["project_id"]
    h_emp = _headers(emp)
    h_admin = _headers(admin)

    r = client.post("/api/v1/hrms/expense-reports", json={"title": "Reject me"}, headers=h_emp)
    report_id = r.get_json()["item"]["id"]
    r_line = client.post(
        f"/api/v1/hrms/expense-reports/{report_id}/lines",
        json={
            "spent_at": date.today().isoformat(),
            "amount": "10.00",
            "category": "meals",
            "project_id": proj,
        },
        headers=h_emp,
    )
    line_id = r_line.get_json()["item"]["id"]
    client.post(
        f"/api/v1/hrms/expense-reports/{report_id}/lines/{line_id}/receipt",
        data={"file": (io.BytesIO(b"\xff\xd8\xff x"), "r.jpg")},
        content_type="multipart/form-data",
        headers={"X-Usis-User-Id": emp},
    )
    client.post(f"/api/v1/hrms/expense-reports/{report_id}/submit", headers=h_emp)

    r_bad = client.post(f"/api/v1/hrms/expense-reports/{report_id}/reject", json={}, headers=h_admin)
    assert r_bad.status_code == 400

    r_ok = client.post(
        f"/api/v1/hrms/expense-reports/{report_id}/reject",
        json={"rejection_reason": "Missing itemized receipt"},
        headers=h_admin,
    )
    assert r_ok.status_code == 200
    assert r_ok.get_json()["item"]["status"] == "rejected"
