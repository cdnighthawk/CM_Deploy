"""API tests for Power BI embed-config (env-gated)."""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.extensions import db
from app.models import Role, User, UserRole

_POWERBI_KEYS = (
    "POWERBI_TENANT_ID",
    "POWERBI_CLIENT_ID",
    "POWERBI_CLIENT_SECRET",
    "POWERBI_WORKSPACE_ID",
    "POWERBI_REPORT_ID",
)


@pytest.fixture
def no_dev_admin(monkeypatch):
    monkeypatch.setenv("USIS_API_DEV_ALLOW_ANY", "0")


@pytest.fixture
def powerbi_env_cleared(monkeypatch):
    for k in _POWERBI_KEYS:
        monkeypatch.delenv(k, raising=False)


def test_powerbi_embed_config_unconfigured(client, no_dev_admin, powerbi_env_cleared):
    with client.application.app_context():
        role = db.session.scalar(select(Role).where(Role.code == "standard"))
        if role is None:
            role = Role(code="standard", name="Standard")
            db.session.add(role)
            db.session.flush()
        u = User(email="pbi_u_" + uuid.uuid4().hex[:8] + "@t.com", first_name="Pbi", last_name="User")
        db.session.add(u)
        db.session.flush()
        db.session.add(UserRole(user_id=u.id, role_id=role.id))
        uid = str(u.id)
        db.session.commit()

    r = client.get("/api/v1/powerbi/embed-config", headers={"X-Usis-User-Id": uid})
    assert r.status_code == 200, r.get_data(as_text=True)
    body = r.get_json()
    assert body["entity"] == "powerbi_embed"
    assert body["configured"] is False
    assert isinstance(body.get("missing_env"), list)
    assert len(body["missing_env"]) > 0
