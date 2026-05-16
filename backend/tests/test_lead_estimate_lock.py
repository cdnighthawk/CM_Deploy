"""Lead estimate takeoff lock / approval guards."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest


@pytest.fixture
def locked_lead():
    return SimpleNamespace(
        id=uuid.uuid4(),
        project_id=None,
        estimate_locked_at=datetime.now(timezone.utc),
        estimate_approved_at=None,
        estimate_approved_by_user_id=None,
    )


def test_post_takeoff_line_returns_403_when_lead_locked(client, monkeypatch, locked_lead):
    import app.api.v1 as v1

    monkeypatch.setattr(v1, "_resolve_lead", lambda ident: locked_lead if ident == "lead-x" else None)
    r = client.post(
        "/api/v1/lead-estimates/lead-x/takeoff-lines",
        json={"description": "x", "quantity": 1, "unit": "EA", "unit_cost": 0, "cost_type": "M"},
    )
    assert r.status_code == 403
    assert "locked" in (r.get_json() or {}).get("error", "").lower()


def test_unlock_estimate_forbidden_when_policy_denies(client, monkeypatch, locked_lead):
    import app.api.v1 as v1

    monkeypatch.setattr(v1, "_can_unlock_lead_estimate", lambda _cu: False)
    monkeypatch.setattr(v1, "_resolve_lead", lambda ident: locked_lead if ident == "lead-x" else None)
    r = client.post("/api/v1/lead-estimates/missing/unlock-estimate")
    assert r.status_code == 404
    r = client.post("/api/v1/lead-estimates/lead-x/unlock-estimate")
    assert r.status_code == 403
