"""Test RFP create API validation for project_id and estimate_id."""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.extensions import db
from app.models import Estimate, LeadEstimate, Project, ProjectMember, Role, User, UserRole


@pytest.fixture
def no_dev_admin(monkeypatch):
    monkeypatch.setenv("USIS_API_DEV_ALLOW_ANY", "0")


def _setup_user_and_project(client):
    """Create a user, project, and estimate for testing."""
    with client.application.app_context():
        role = db.session.scalar(select(Role).where(Role.code == "standard"))
        if role is None:
            role = Role(code="standard", name="Standard")
            db.session.add(role)
            db.session.flush()
        u = User(email="rfp_test_" + uuid.uuid4().hex[:8] + "@t.com", first_name="Test", last_name="User")
        db.session.add(u)
        db.session.flush()
        db.session.add(UserRole(user_id=u.id, role_id=role.id))
        p = Project(name="RFP-Test-" + uuid.uuid4().hex[:8])
        p2 = Project(name="RFP-Test2-" + uuid.uuid4().hex[:8])
        db.session.add_all([p, p2])
        db.session.flush()
        db.session.add(ProjectMember(user_id=u.id, project_id=p.id, member_role="estimator"))
        db.session.add(ProjectMember(user_id=u.id, project_id=p2.id, member_role="estimator"))
        est = Estimate(project_id=p.id, name="Test Estimate")
        db.session.add(est)
        le = LeadEstimate(name="Test Lead", project_id=p.id)
        db.session.add(le)
        db.session.flush()
        est_no_proj = Estimate(lead_estimate_id=le.id, name="Lead Estimate No Project")
        db.session.add(est_no_proj)
        db.session.commit()
        return {
            "uid": str(u.id),
            "pid": str(p.id),
            "pid2": str(p2.id),
            "est_id": str(est.id),
            "le_id": str(le.id),
            "est_no_proj_id": str(est_no_proj.id),
        }


def test_create_rfp_with_valid_project_id(client, no_dev_admin):
    """Test creating an RFP with a valid project UUID."""
    ctx = _setup_user_and_project(client)
    resp = client.post(
        "/api/v1/rfps",
        json={"project_id": ctx["pid"], "title": "Valid RFP"},
        headers={"X-Usis-User-Id": ctx["uid"]},
    )
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["entity"] == "rfp"
    assert data["item"]["project_id"] == ctx["pid"]
    assert data["item"]["title"] == "Valid RFP"


def test_create_rfp_with_non_uuid_project_id(client, no_dev_admin):
    """Test creating an RFP with a non-UUID project_id (e.g., job number) returns 400."""
    ctx = _setup_user_and_project(client)
    resp = client.post(
        "/api/v1/rfps",
        json={"project_id": "25270", "title": "Invalid RFP"},
        headers={"X-Usis-User-Id": ctx["uid"]},
    )
    assert resp.status_code == 400
    data = resp.get_json()
    assert "error" in data
    assert "valid UUID" in data["error"]


def test_create_rfp_with_json_integer_project_id(client, no_dev_admin):
    """Test creating an RFP with a JSON integer project_id returns 400."""
    ctx = _setup_user_and_project(client)
    resp = client.post(
        "/api/v1/rfps",
        json={"project_id": 25270, "title": "Invalid RFP"},
        headers={"X-Usis-User-Id": ctx["uid"]},
    )
    assert resp.status_code == 400
    data = resp.get_json()
    assert "error" in data
    assert "valid UUID" in data["error"]


def test_create_rfp_with_unknown_project_uuid(client, no_dev_admin):
    """Test creating an RFP with a valid UUID that doesn't exist returns 400."""
    ctx = _setup_user_and_project(client)
    fake_uuid = str(uuid.uuid4())
    resp = client.post(
        "/api/v1/rfps",
        json={"project_id": fake_uuid, "title": "Unknown Project RFP"},
        headers={"X-Usis-User-Id": ctx["uid"]},
    )
    assert resp.status_code == 400
    data = resp.get_json()
    assert "error" in data
    assert "does not exist" in data["error"]


def test_create_rfp_with_valid_estimate_in_project(client, no_dev_admin):
    """Test creating an RFP with a valid estimate that belongs to the project."""
    ctx = _setup_user_and_project(client)
    resp = client.post(
        "/api/v1/rfps",
        json={"project_id": ctx["pid"], "estimate_id": ctx["est_id"], "title": "RFP with Estimate"},
        headers={"X-Usis-User-Id": ctx["uid"]},
    )
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["entity"] == "rfp"
    assert data["item"]["project_id"] == ctx["pid"]
    assert data["item"]["source_estimate_id"] == ctx["est_id"]


def test_create_rfp_with_estimate_from_wrong_project(client, no_dev_admin):
    """Test creating an RFP with an estimate that belongs to a different project returns 400."""
    ctx = _setup_user_and_project(client)
    resp = client.post(
        "/api/v1/rfps",
        json={"project_id": ctx["pid2"], "estimate_id": ctx["est_id"], "title": "Wrong Estimate RFP"},
        headers={"X-Usis-User-Id": ctx["uid"]},
    )
    assert resp.status_code == 400
    data = resp.get_json()
    assert "error" in data
    assert "does not belong" in data["error"]


def test_create_rfp_with_non_uuid_estimate_id(client, no_dev_admin):
    """Test creating an RFP with a non-UUID estimate_id returns 400."""
    ctx = _setup_user_and_project(client)
    resp = client.post(
        "/api/v1/rfps",
        json={"project_id": ctx["pid"], "estimate_id": "12345", "title": "Invalid Estimate RFP"},
        headers={"X-Usis-User-Id": ctx["uid"]},
    )
    assert resp.status_code == 400
    data = resp.get_json()
    assert "error" in data
    assert "valid UUID" in data["error"]


def test_create_rfp_with_unknown_estimate_uuid(client, no_dev_admin):
    """Test creating an RFP with a valid estimate UUID that doesn't exist returns 400."""
    ctx = _setup_user_and_project(client)
    fake_est_uuid = str(uuid.uuid4())
    resp = client.post(
        "/api/v1/rfps",
        json={"project_id": ctx["pid"], "estimate_id": fake_est_uuid, "title": "Unknown Estimate RFP"},
        headers={"X-Usis-User-Id": ctx["uid"]},
    )
    assert resp.status_code == 400
    data = resp.get_json()
    assert "error" in data
    assert "does not exist" in data["error"]


def test_create_rfp_with_estimate_no_project_id_valid_lead(client, no_dev_admin):
    """Test creating an RFP with an estimate that has no project_id but valid lead_estimate_id."""
    ctx = _setup_user_and_project(client)
    resp = client.post(
        "/api/v1/rfps",
        json={
            "project_id": ctx["pid"],
            "lead_estimate_id": ctx["le_id"],
            "estimate_id": ctx["est_no_proj_id"],
            "title": "RFP with Lead Estimate",
        },
        headers={"X-Usis-User-Id": ctx["uid"]},
    )
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["entity"] == "rfp"
    assert data["item"]["project_id"] == ctx["pid"]


def test_create_rfp_without_project_or_lead(client, no_dev_admin):
    """Test creating an RFP without project_id or lead_estimate_id returns 400."""
    ctx = _setup_user_and_project(client)
    resp = client.post(
        "/api/v1/rfps",
        json={"title": "Invalid RFP"},
        headers={"X-Usis-User-Id": ctx["uid"]},
    )
    assert resp.status_code == 400
    data = resp.get_json()
    assert "error" in data
    assert "required" in data["error"]


def test_create_rfp_with_non_uuid_lead_estimate_id(client, no_dev_admin):
    """Test creating an RFP with a non-UUID lead_estimate_id returns 400."""
    ctx = _setup_user_and_project(client)
    resp = client.post(
        "/api/v1/rfps",
        json={"lead_estimate_id": "12345", "title": "Invalid Lead RFP"},
        headers={"X-Usis-User-Id": ctx["uid"]},
    )
    assert resp.status_code == 400
    data = resp.get_json()
    assert "error" in data
    assert "valid UUID" in data["error"]


def test_create_rfp_with_unknown_lead_estimate_uuid(client, no_dev_admin):
    """Test creating an RFP with a valid lead_estimate UUID that doesn't exist returns 400."""
    ctx = _setup_user_and_project(client)
    fake_le_uuid = str(uuid.uuid4())
    resp = client.post(
        "/api/v1/rfps",
        json={"lead_estimate_id": fake_le_uuid, "title": "Unknown Lead RFP"},
        headers={"X-Usis-User-Id": ctx["uid"]},
    )
    assert resp.status_code == 400
    data = resp.get_json()
    assert "error" in data
    assert "does not exist" in data["error"]


def test_create_rfp_with_valid_lead_estimate_only(client, no_dev_admin):
    """Test creating an RFP with only a valid lead_estimate_id (no project_id)."""
    ctx = _setup_user_and_project(client)
    resp = client.post(
        "/api/v1/rfps",
        json={"lead_estimate_id": ctx["le_id"], "title": "Lead Only RFP"},
        headers={"X-Usis-User-Id": ctx["uid"]},
    )
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["entity"] == "rfp"
    assert data["item"]["lead_estimate_id"] == ctx["le_id"]


def test_create_rfp_with_estimate_no_project_validation(client, no_dev_admin):
    """Test validating estimate_id even when no project_id is given."""
    ctx = _setup_user_and_project(client)
    fake_est_uuid = str(uuid.uuid4())
    resp = client.post(
        "/api/v1/rfps",
        json={"lead_estimate_id": ctx["le_id"], "estimate_id": fake_est_uuid, "title": "Invalid Estimate RFP"},
        headers={"X-Usis-User-Id": ctx["uid"]},
    )
    assert resp.status_code == 400
    data = resp.get_json()
    assert "error" in data
    assert "does not exist" in data["error"]

