"""Tests for BuildingConnected OAuth + sync routes (mocked HTTP to APS/BC)."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.exc import OperationalError

from app.api import _integration_bc
from app.extensions import db
from app.integrations.buildingconnected_client import BuildingConnectedClient, next_cursor_state
from app.models.buildingconnected_oauth import BuildingConnectedOAuthToken
from app.models.lead_estimate import LeadEstimate


def test_next_cursor_state_prefers_pagination_object():
    assert next_cursor_state({"pagination": {"cursorState": "abc"}}) == "abc"
    assert next_cursor_state({"cursorState": "root"}) == "root"
    assert next_cursor_state({"pagination": {}}) is None
    assert next_cursor_state({}) is None


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


def test_bc_sync_cron_secret_skips_session(monkeypatch, client, flask_app):
    flask_app.config["BUILDINGCONNECTED_SYNC_ENABLED"] = True
    flask_app.config["BC_SYNC_CRON_SECRET"] = "hourly-test-secret"
    flask_app.config["TESTING"] = True
    monkeypatch.setenv("USIS_API_DEV_ALLOW_ANY", "0")

    def fake_token():
        return "at-cron"

    def fake_pull(access_token, full=False):
        assert access_token == "at-cron"
        return (2, 0, 0)

    monkeypatch.setattr(_integration_bc, "_ensure_access_token", fake_token)
    monkeypatch.setattr(_integration_bc, "_pull_and_upsert", fake_pull)

    denied = client.post("/api/v1/integrations/buildingconnected/sync")
    assert denied.status_code == 401

    ok = client.post(
        "/api/v1/integrations/buildingconnected/sync",
        headers={"X-Cron-Secret": "hourly-test-secret"},
    )
    assert ok.status_code == 200, ok.get_data(as_text=True)
    body = ok.get_json()
    assert body.get("ok") is True
    assert body.get("loaded") == 2


class _FakeBCClient:
    def __init__(self, _token: str, _base: str):
        pass

    def __enter__(self) -> _FakeBCClient:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def iter_opportunities(self, **kwargs):
        eid = "bc-api-test-" + uuid.uuid4().hex[:12]
        yield {
            "id": eid,
            "name": "Synced via fake BC",
            "number": "BC-FAKE-1",
            "submissionState": "undecided",
        }

    def iter_projects(self, **kwargs):
        yield from ()


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


def test_iter_opportunities_stops_on_repeated_cursor(monkeypatch):
    cli = BuildingConnectedClient("token", "https://example.test")
    calls = {"n": 0}

    def fake_page(**kwargs):
        calls["n"] += 1
        return {
            "results": [{"id": f"opp-{calls['n']}"}] * 100,
            "pagination": {"cursorState": "same-cursor"},
        }

    monkeypatch.setattr(cli, "get_opportunities_page", fake_page)
    items = list(cli.iter_opportunities())
    assert calls["n"] == 2
    assert len(items) == 200


def test_iter_opportunities_stops_on_short_page(monkeypatch):
    cli = BuildingConnectedClient("token", "https://example.test")
    calls = {"n": 0}

    def fake_page(**kwargs):
        calls["n"] += 1
        return {
            "results": [{"id": "only-one"}],
            "pagination": {"cursorState": "would-loop"},
        }

    monkeypatch.setattr(cli, "get_opportunities_page", fake_page)
    items = list(cli.iter_opportunities())
    assert calls["n"] == 1
    assert [row["id"] for row in items] == ["only-one"]


def test_iter_opportunities_respects_max_pages(monkeypatch):
    cli = BuildingConnectedClient("token", "https://example.test")
    calls = {"n": 0}

    def fake_page(**kwargs):
        calls["n"] += 1
        return {
            "results": [{"id": f"p{calls['n']}"}] * 100,
            "pagination": {"cursorState": f"c{calls['n']}"},
        }

    monkeypatch.setattr(cli, "get_opportunities_page", fake_page)
    items = list(cli.iter_opportunities(max_pages=3))
    assert calls["n"] == 3
    assert len(items) == 300


def test_lead_ui_filter_matches_current_bid_board():
    from sqlalchemy.dialects import postgresql

    from app.api._lead_estimate_queries import lead_estimates_ui_filter

    sql = str(
        lead_estimates_ui_filter("undecided").compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    ).lower()
    assert "archived" in sql
    assert "declined" in sql
    assert "child" in sql
    assert "due_at" in sql
    assert "submission_state" in sql


def test_estimate_ui_filter_excludes_grouped_children():
    from sqlalchemy.dialects import postgresql

    from app.api._lead_estimate_queries import lead_estimates_ui_filter

    sql = str(
        lead_estimates_ui_filter("will_submit").compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    ).lower()
    assert "child" in sql
    assert "parent" in sql
    assert "due_at" in sql
