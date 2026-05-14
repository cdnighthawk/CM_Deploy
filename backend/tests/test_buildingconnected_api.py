"""Tests for BuildingConnected OAuth + sync routes (mocked HTTP to APS/BC)."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.exc import OperationalError

from app.api import _integration_bc
from app.extensions import db
from app.models.buildingconnected_oauth import BuildingConnectedOAuthToken
from app.models.lead_estimate import LeadEstimate


def _skip_if_no_bc_table(flask_app):
    with flask_app.app_context():
        try:
            db.session.execute(select(BuildingConnectedOAuthToken.label).limit(1))
        except OperationalError as exc:
            pytest.skip(f"buildingconnected_oauth_tokens missing (run flask db upgrade): {exc}")


def test_bc_oauth_start_missing_config_returns_503(client, flask_app):
    flask_app.config["AUTODESK_CLIENT_ID"] = None
    flask_app.config["AUTODESK_OAUTH_REDIRECT_URI"] = None
    r = client.get("/api/v1/integrations/buildingconnected/oauth/start")
    assert r.status_code == 503


def test_bc_oauth_start_redirects_when_configured(client, flask_app):
    flask_app.config["AUTODESK_CLIENT_ID"] = "test-client-id"
    flask_app.config["AUTODESK_OAUTH_REDIRECT_URI"] = "http://127.0.0.1:5000/cb"
    flask_app.config["AUTODESK_OAUTH_SCOPES"] = "data:read"
    r = client.get("/api/v1/integrations/buildingconnected/oauth/start", follow_redirects=False)
    assert r.status_code == 302
    loc = r.headers.get("Location") or ""
    assert "developer.api.autodesk.com/authentication/v2/authorize" in loc
    assert "client_id=test-client-id" in loc


def test_bc_oauth_callback_rejects_bad_state(client, flask_app):
    flask_app.config["AUTODESK_CLIENT_ID"] = "x"
    flask_app.config["AUTODESK_OAUTH_REDIRECT_URI"] = "http://127.0.0.1/cb"
    with client.session_transaction() as sess:
        sess[_integration_bc.BC_OAUTH_STATE_KEY] = "expected"
    r = client.get(
        "/api/v1/integrations/buildingconnected/oauth/callback?code=abc&state=wrong",
        follow_redirects=False,
    )
    assert r.status_code == 400


def test_bc_oauth_callback_persists_tokens(monkeypatch, client, flask_app):
    _skip_if_no_bc_table(flask_app)
    flask_app.config["AUTODESK_CLIENT_ID"] = "cid"
    flask_app.config["AUTODESK_CLIENT_SECRET"] = "sec"
    flask_app.config["AUTODESK_OAUTH_REDIRECT_URI"] = "http://127.0.0.1/cb"
    flask_app.config["SECRET_KEY"] = "unit-test-secret-key-not-for-production-use"

    def fake_exchange(**kwargs):
        return {
            "access_token": "at-test",
            "refresh_token": "rt-test",
            "expires_in": 3600,
        }

    monkeypatch.setattr(_integration_bc, "exchange_authorization_code", fake_exchange)

    with client.session_transaction() as sess:
        sess[_integration_bc.BC_OAUTH_STATE_KEY] = "st1"

    try:
        r = client.get(
            "/api/v1/integrations/buildingconnected/oauth/callback?code=ccode&state=st1",
            follow_redirects=False,
        )
        assert r.status_code == 200
        assert r.get_json() == {"ok": True, "entity": "buildingconnected_oauth"}
        with flask_app.app_context():
            row = db.session.get(BuildingConnectedOAuthToken, "default")
            assert row is not None
            assert row.access_token == "at-test"
            assert _integration_bc._decrypt_refresh(row.refresh_token_encrypted) == "rt-test"
    finally:
        with flask_app.app_context():
            row = db.session.get(BuildingConnectedOAuthToken, "default")
            if row is not None:
                db.session.delete(row)
                db.session.commit()


def test_bc_sync_disabled_returns_403(client, flask_app):
    flask_app.config["BUILDINGCONNECTED_SYNC_ENABLED"] = False
    r = client.post("/api/v1/integrations/buildingconnected/sync")
    assert r.status_code == 403


class _FakeBCClient:
    def __init__(self, _token: str, _base: str):
        pass

    def __enter__(self) -> _FakeBCClient:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def iter_projects(self, **kwargs):
        eid = "bc-api-test-" + uuid.uuid4().hex[:12]
        yield {
            "id": eid,
            "name": "Synced via fake BC",
            "number": "BC-FAKE-1",
            "submissionState": "undecided",
        }


def test_bc_sync_upserts_lead_estimates(monkeypatch, client, flask_app):
    _skip_if_no_bc_table(flask_app)
    flask_app.config["BUILDINGCONNECTED_SYNC_ENABLED"] = True
    flask_app.config["AUTODESK_CLIENT_ID"] = "cid"
    flask_app.config["AUTODESK_CLIENT_SECRET"] = "sec"
    flask_app.config["SECRET_KEY"] = "unit-test-secret-key-not-for-production-use"
    flask_app.config["BUILDINGCONNECTED_API_BASE"] = (
        "https://developer.api.autodesk.com/construction/buildingconnected/v2"
    )

    monkeypatch.setattr(_integration_bc, "BuildingConnectedClient", _FakeBCClient)

    with flask_app.app_context():
        enc = _integration_bc._encrypt_refresh("rt-fake")
        row = BuildingConnectedOAuthToken(
            label="default",
            refresh_token_encrypted=enc,
            access_token="at-fake",
            access_expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        db.session.add(row)
        db.session.commit()

    try:
        r = client.post("/api/v1/integrations/buildingconnected/sync")
        assert r.status_code == 200, r.get_data(as_text=True)
        body = r.get_json()
        assert body.get("ok") is True
        assert body.get("loaded", 0) >= 1
        with flask_app.app_context():
            row = db.session.scalars(
                select(LeadEstimate).where(LeadEstimate.name == "Synced via fake BC").limit(1)
            ).first()
            assert row is not None
    finally:
        with flask_app.app_context():
            tok = db.session.get(BuildingConnectedOAuthToken, "default")
            if tok is not None:
                db.session.delete(tok)
            for le in db.session.scalars(
                select(LeadEstimate).where(LeadEstimate.name == "Synced via fake BC")
            ).all():
                db.session.delete(le)
            db.session.commit()
