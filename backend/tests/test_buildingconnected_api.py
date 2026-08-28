"""Tests for BuildingConnected OAuth + sync routes (mocked HTTP to APS/BC)."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import delete, select
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


def test_bc_write_helpers_and_errors():
    from app.integrations.buildingconnected_write import (
        build_opportunity_patch_body,
        get_submission_change_block_reason,
        message_for_bc_http_error,
    )

    assert build_opportunity_patch_body({"submissionState": "DECLINED"}) == {
        "submissionState": "DECLINED"
    }
    assert build_opportunity_patch_body({"submissionState": "DECLINED", "note": "Too far"})[
        "declineReasons"
    ] == ["OTHER"]
    try:
        build_opportunity_patch_body({"submissionState": "SUBMITTED"})
        raise AssertionError("expected SUBMITTED to fail")
    except ValueError as exc:
        assert "SUBMITTED" in str(exc)
    assert get_submission_change_block_reason(external_id=None, submission_state="UNDECIDED", is_archived=False)
    assert get_submission_change_block_reason(
        external_id="abc", submission_state="SUBMITTED", is_archived=False
    )
    assert "data:write" in message_for_bc_http_error(403, {"detail": "insufficient scope data:write"})
    privilege = message_for_bc_http_error(
        403, {"detail": "Token does not have the privilege for this request."}
    )
    assert "Reconnect BC" in privilege
    assert "data:write" in privilege
    assert "not found" in message_for_bc_http_error(404, {}).lower()


def test_bc_write_disabled_returns_403(client, flask_app):
    flask_app.config["BC_WRITE_ENABLED"] = False
    r = client.patch(
        "/api/v1/lead-estimates/does-not-exist/buildingconnected",
        json={"submissionState": "DECLINED"},
    )
    assert r.status_code == 403


def test_bc_write_patches_opportunity(monkeypatch, client, flask_app):
    _skip_if_no_bc_table(flask_app)
    flask_app.config["BC_WRITE_ENABLED"] = True
    flask_app.config["SECRET_KEY"] = "unit-test-secret-key-not-for-production-use"
    flask_app.config["BUILDINGCONNECTED_API_BASE"] = (
        "https://developer.api.autodesk.com/construction/buildingconnected/v2"
    )

    calls = {"patch": None}

    class _WriteClient:
        def __init__(self, _token, _base):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def patch_opportunity(self, opportunity_id, patch):
            calls["patch"] = (opportunity_id, patch)
            return {"id": opportunity_id, "submissionState": patch["submissionState"]}

        def get_opportunity(self, opportunity_id):
            return {"id": opportunity_id, "submissionState": "DECLINED", "isArchived": False}

    monkeypatch.setattr(_integration_bc, "BuildingConnectedClient", _WriteClient)
    monkeypatch.setattr(_integration_bc, "_ensure_access_token", lambda: "at-write")

    eid = "bc-write-" + uuid.uuid4().hex[:10]
    with flask_app.app_context():
        le = LeadEstimate(external_id=eid, name="Write test lead", submission_state="UNDECIDED")
        db.session.add(le)
        db.session.commit()
        lead_id = str(le.id)

    try:
        r = client.patch(
            f"/api/v1/lead-estimates/{lead_id}/buildingconnected",
            json={"submissionState": "DECLINED", "note": "Too far"},
        )
        assert r.status_code == 200, r.get_data(as_text=True)
        body = r.get_json()
        assert body.get("ok") is True
        assert calls["patch"][0] == eid
        assert calls["patch"][1]["submissionState"] == "DECLINED"
        with flask_app.app_context():
            row = db.session.scalar(select(LeadEstimate).where(LeadEstimate.external_id == eid))
            assert row is not None
            assert str(row.submission_state).upper() == "DECLINED"
    finally:
        with flask_app.app_context():
            row = db.session.scalar(select(LeadEstimate).where(LeadEstimate.external_id == eid))
            if row is not None:
                db.session.delete(row)
                db.session.commit()


def test_bc_bulk_write_patches_opportunities(monkeypatch, client, flask_app):
    _skip_if_no_bc_table(flask_app)
    flask_app.config["BC_WRITE_ENABLED"] = True
    flask_app.config["SECRET_KEY"] = "unit-test-secret-key-not-for-production-use"
    flask_app.config["BUILDINGCONNECTED_API_BASE"] = (
        "https://developer.api.autodesk.com/construction/buildingconnected/v2"
    )

    patched_ids: list[str] = []

    class _WriteClient:
        def __init__(self, _token, _base):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def patch_opportunity(self, opportunity_id, patch):
            patched_ids.append(opportunity_id)
            return {"id": opportunity_id, "submissionState": patch["submissionState"]}

        def get_opportunity(self, opportunity_id):
            return {"id": opportunity_id, "submissionState": "WILL_SUBMIT", "isArchived": False}

    monkeypatch.setattr(_integration_bc, "BuildingConnectedClient", _WriteClient)
    monkeypatch.setattr(_integration_bc, "_ensure_access_token", lambda: "at-write")

    eids = ["bc-bulk-a-" + uuid.uuid4().hex[:8], "bc-bulk-b-" + uuid.uuid4().hex[:8]]
    lead_ids: list[str] = []
    with flask_app.app_context():
        for eid in eids:
            le = LeadEstimate(external_id=eid, name="Bulk write " + eid, submission_state="UNDECIDED")
            db.session.add(le)
            db.session.flush()
            lead_ids.append(str(le.id))
        db.session.commit()

    try:
        r = client.post(
            "/api/v1/lead-estimates/bulk/buildingconnected",
            json={"ids": lead_ids, "submissionState": "WILL_SUBMIT"},
        )
        assert r.status_code == 200, r.get_data(as_text=True)
        body = r.get_json()
        assert body.get("ok") is True
        assert body.get("updated_count") == 2
        assert body.get("failed_count") == 0
        assert sorted(patched_ids) == sorted(eids)
        with flask_app.app_context():
            for eid in eids:
                row = db.session.scalar(select(LeadEstimate).where(LeadEstimate.external_id == eid))
                assert row is not None
                assert str(row.submission_state).upper() == "WILL_SUBMIT"
    finally:
        with flask_app.app_context():
            for eid in eids:
                row = db.session.scalar(select(LeadEstimate).where(LeadEstimate.external_id == eid))
                if row is not None:
                    db.session.delete(row)
            db.session.commit()


def test_bc_bulk_write_disabled_returns_403(client, flask_app):
    flask_app.config["BC_WRITE_ENABLED"] = False
    r = client.post(
        "/api/v1/lead-estimates/bulk/buildingconnected",
        json={"ids": ["does-not-exist"], "submissionState": "WILL_SUBMIT"},
    )
    assert r.status_code == 403


def test_bc_bulk_write_rejects_empty_ids(client, flask_app):
    flask_app.config["BC_WRITE_ENABLED"] = True
    r = client.post(
        "/api/v1/lead-estimates/bulk/buildingconnected",
        json={"ids": [], "submissionState": "WILL_SUBMIT"},
    )
    assert r.status_code == 400


def test_estimate_ui_filter_excludes_grouped_children():
    from sqlalchemy.dialects import postgresql

    from app.api._lead_estimate_queries import (
        active_estimate_queue_filter,
        lead_estimates_ui_filter,
    )

    sql = str(
        lead_estimates_ui_filter("will_submit").compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    ).lower()
    assert "child" in sql
    assert "parent" in sql
    assert "due_at" in sql

    queue_sql = str(
        active_estimate_queue_filter().compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    ).lower()
    assert queue_sql == sql


def test_desktop_queue_filter_requires_open_due_date():
    from sqlalchemy.dialects import postgresql

    from app.api._lead_estimate_queries import desktop_estimate_queue_filter

    sql = str(
        desktop_estimate_queue_filter().compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    ).lower()
    assert "due_at" in sql
    assert "child" in sql


def test_group_summary_for_lead_roles(monkeypatch):
    from types import SimpleNamespace

    from app.api import v1 as v1_mod

    parent = SimpleNamespace(
        id=uuid.uuid4(),
        external_id="p-1",
        external_parent_id=None,
        is_parent=True,
        name="Park",
        number="26063",
        trade_name="Operable Partitions",
        client={"company": {"name": "Parent"}},
        submission_state="WILL_SUBMIT",
        workflow_bucket="ACCEPTED_ACTIVE_PARENT",
        is_archived=False,
        due_at=None,
        source=None,
        crm_stage="New Lead",
        win_probability=None,
        members=None,
        bc_updated_at=None,
        project_id=None,
        primary_estimate_id=None,
        primary_rfp_id=None,
        estimate_locked_at=None,
        estimate_approved_at=None,
        estimate_approved_by_user_id=None,
        location=None,
    )
    child = SimpleNamespace(
        id=uuid.uuid4(),
        external_id="c-1",
        external_parent_id="p-1",
        is_parent=False,
        name="Park",
        number=None,
        trade_name="Lockers",
        client={"company": {"name": "VCC"}},
        submission_state="WILL_SUBMIT",
        workflow_bucket="ACCEPTED_ACTIVE_CHILD",
        is_archived=False,
        due_at=None,
        source=None,
        crm_stage="New Lead",
        win_probability=None,
        members=None,
        bc_updated_at=None,
        project_id=None,
        primary_estimate_id=None,
        primary_rfp_id=None,
        estimate_locked_at=None,
        estimate_approved_at=None,
        estimate_approved_by_user_id=None,
        location=None,
    )

    class _Rows:
        def __init__(self, rows):
            self._rows = rows

        def all(self):
            return self._rows

    class _Session:
        def scalar(self, _stmt):
            return parent

        def scalars(self, _stmt):
            return _Rows([child])

    monkeypatch.setattr(v1_mod.db, "session", _Session())
    child_gs = v1_mod._group_summary_for_lead(child)
    assert child_gs["role"] == "child"
    assert child_gs["parent"]["external_id"] == "p-1"
    assert [c["external_id"] for c in child_gs["children"]] == ["c-1"]

    standalone = SimpleNamespace(external_id="s-1", external_parent_id=None, is_parent=False)

    class _Empty:
        def scalar(self, _stmt):
            return None

        def scalars(self, _stmt):
            return _Rows([])

    monkeypatch.setattr(v1_mod.db, "session", _Empty())
    alone = v1_mod._group_summary_for_lead(standalone)
    assert alone == {"role": "standalone", "parent": None, "children": []}


def test_group_child_sort_puts_stubs_last():
    from types import SimpleNamespace

    from app.api.v1 import _group_child_sort_key

    live = SimpleNamespace(
        is_archived=False,
        workflow_bucket="ACCEPTED_ACTIVE_CHILD",
        client={"company": {"name": "VCC"}},
        trade_name="Lockers",
        name="Park",
    )
    stub = SimpleNamespace(
        is_archived=False,
        workflow_bucket="ACCEPTED_ACTIVE_CHILD",
        client=None,
        trade_name=None,
        name="Park",
    )
    declined = SimpleNamespace(
        is_archived=True,
        workflow_bucket="DECLINED_ARCHIVED_CHILD",
        client={"company": {"name": "Nibbi Brothers"}},
        trade_name="Signage",
        name="Park",
    )
    ordered = sorted([stub, declined, live], key=_group_child_sort_key)
    assert ordered == [live, declined, stub]


def test_lead_estimate_group_summary_lists_children(client, flask_app):
    from sqlalchemy.exc import OperationalError

    try:
        with flask_app.app_context():
            db.session.execute(select(LeadEstimate.external_id).limit(1))
    except OperationalError as exc:
        pytest.skip(f"database unavailable: {exc}")

    suffix = uuid.uuid4().hex[:10]
    parent_id = f"gs-parent-{suffix}"
    child_vcc = f"gs-vcc-{suffix}"
    child_nibbi = f"gs-nibbi-{suffix}"
    child_stub = f"gs-stub-{suffix}"
    standalone_id = f"gs-alone-{suffix}"
    ids = [parent_id, child_vcc, child_nibbi, child_stub, standalone_id]

    with flask_app.app_context():
        db.session.add_all(
            [
                LeadEstimate(
                    external_id=parent_id,
                    name="City Park Group",
                    number="26063",
                    is_parent=True,
                    submission_state="WILL_SUBMIT",
                    workflow_bucket="ACCEPTED_ACTIVE_PARENT",
                    trade_name="Operable Partitions",
                    client={"company": {"name": "Parent GC"}},
                ),
                LeadEstimate(
                    external_id=child_vcc,
                    external_parent_id=parent_id,
                    name="City Park Group",
                    is_parent=False,
                    submission_state="WILL_SUBMIT",
                    workflow_bucket="ACCEPTED_ACTIVE_CHILD",
                    trade_name="Fire Extinguishers & Cabinets",
                    client={"company": {"name": "VCC"}},
                ),
                LeadEstimate(
                    external_id=child_nibbi,
                    external_parent_id=parent_id,
                    name="City Park Group",
                    is_parent=False,
                    submission_state="WILL_SUBMIT",
                    workflow_bucket="ACCEPTED_ACTIVE_CHILD",
                    trade_name="Miscellaneous Building Specialties",
                    client={"company": {"name": "Nibbi Brothers"}},
                ),
                LeadEstimate(
                    external_id=child_stub,
                    external_parent_id=parent_id,
                    name="City Park Group",
                    is_parent=False,
                    submission_state="WILL_SUBMIT",
                    workflow_bucket="ACCEPTED_ACTIVE_CHILD",
                ),
                LeadEstimate(
                    external_id=standalone_id,
                    name="Standalone job",
                    is_parent=False,
                    submission_state="WILL_SUBMIT",
                    workflow_bucket="ACCEPTED_ACTIVE_ORPHAN",
                ),
            ]
        )
        db.session.commit()

    try:
        from app.api.v1 import _group_summary_for_lead

        with flask_app.app_context():
            parent_row = db.session.scalar(
                select(LeadEstimate).where(LeadEstimate.external_id == parent_id)
            )
            child_row = db.session.scalar(
                select(LeadEstimate).where(LeadEstimate.external_id == child_vcc)
            )
            alone_row = db.session.scalar(
                select(LeadEstimate).where(LeadEstimate.external_id == standalone_id)
            )
            parent_gs = _group_summary_for_lead(parent_row)
            child_gs = _group_summary_for_lead(child_row)
            alone_gs = _group_summary_for_lead(alone_row)

        assert parent_gs["role"] == "group"
        assert parent_gs["parent"]["external_id"] == parent_id
        assert parent_gs["parent"]["number"] == "26063"
        child_ids = [c["external_id"] for c in parent_gs["children"]]
        assert child_ids == [child_nibbi, child_vcc, child_stub]
        assert parent_gs["children"][0]["company_name"] == "Nibbi Brothers"
        assert parent_gs["children"][1]["company_name"] == "VCC"
        assert parent_gs["children"][2]["trade_name"] is None

        assert child_gs["role"] == "child"
        assert [c["external_id"] for c in child_gs["children"]] == child_ids

        assert alone_gs["role"] == "standalone"
        assert alone_gs["parent"] is None
        assert alone_gs["children"] == []
    finally:
        with flask_app.app_context():
            db.session.rollback()
            db.session.execute(delete(LeadEstimate).where(LeadEstimate.external_id.in_(ids)))
            db.session.commit()
