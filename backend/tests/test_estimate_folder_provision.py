"""Estimate project-folder provisioning (sanitization, mkdir, create hooks)."""
from __future__ import annotations

import uuid
from pathlib import Path

from sqlalchemy import select

from app.extensions import db
from app.models.estimate import Estimate
from app.models.lead_estimate import LeadEstimate
from app.services import estimate_folder_provision as provision


def _make_lead(external_id: str, **kwargs) -> LeadEstimate:
    from app.tenancy import ensure_usis_organization

    org = ensure_usis_organization()
    le = LeadEstimate(
        external_id=external_id,
        name=kwargs.pop("name", "Folder parent"),
        organization_id=org.id,
        **kwargs,
    )
    db.session.add(le)
    db.session.commit()
    return le


def _cleanup_lead(external_id: str) -> None:
    row = db.session.scalar(select(LeadEstimate).where(LeadEstimate.external_id == external_id))
    if row is not None:
        db.session.delete(row)
        db.session.commit()


def test_sanitize_windows_folder_name():
    assert provision.sanitize_windows_folder_name(r'Kaiser <> Fresno: "A/B"') == "Kaiser Fresno A B"
    assert provision.sanitize_windows_folder_name("  dots...  ") == "dots"
    assert provision.sanitize_windows_folder_name("CON") == "_CON"
    assert provision.sanitize_windows_folder_name("") == "Estimate"
    assert provision.sanitize_windows_folder_name("a" * 200).endswith("aaa") or len(
        provision.sanitize_windows_folder_name("a" * 200)
    ) <= provision.FOLDER_NAME_MAX


def test_estimate_folder_name_uses_job_and_name():
    name = provision.estimate_folder_name("23044", "Turner – Bid Set")
    assert name.startswith("23044 - ")
    assert "Turner" in name
    assert ":" not in name
    assert "/" not in name


def test_resolve_provision_endpoint_base_and_aliases():
    assert (
        provision.resolve_provision_endpoint("http://data-server.example:5055")
        == "http://data-server.example:5055/provision/estimate-folder"
    )
    assert (
        provision.resolve_provision_endpoint("http://data-server.example:5055/provision/estimate-folder")
        == "http://data-server.example:5055/provision/estimate-folder"
    )
    assert (
        provision.resolve_provision_endpoint("http://data-server.example:5055/provision/estimate-folder/")
        == "http://data-server.example:5055/provision/estimate-folder"
    )
    assert (
        provision.resolve_provision_endpoint("http://data-server.example:5055/provision/estimate-folders")
        == "http://data-server.example:5055/provision/estimate-folders"
    )
    assert (
        provision.resolve_provision_endpoint("http://data-server.example:5055/estimate-folder")
        == "http://data-server.example:5055/estimate-folder"
    )
    assert provision.resolve_provision_endpoint("") is None
    assert provision.resolve_provision_endpoint(None) is None


def test_create_local_folder_tree_idempotent(tmp_path: Path):
    dest, created = provision.create_local_folder_tree(tmp_path, "23044 - Sample Job")
    assert created is True
    root = Path(dest)
    assert (root / "01_Bid_Docs").is_dir()
    assert (root / "02_Processed" / "drawings").is_dir()
    assert (root / "02_Processed" / "specs").is_dir()
    assert (root / "02_Processed" / "other").is_dir()
    assert (root / "03_Takeoff").is_dir()
    assert (root / "04_Correspondence").is_dir()
    assert (root / "05_Reports").is_dir()
    readme = (root / "README.txt").read_text(encoding="utf-8")
    assert "BidDocProcessor" in readme

    dest2, created2 = provision.create_local_folder_tree(tmp_path, "23044 - Sample Job")
    assert dest2 == dest
    assert created2 is False
    assert (root / "01_Bid_Docs").is_dir()


def test_create_estimate_triggers_http_provision(client, flask_app, monkeypatch, tmp_path):
    calls: list[dict] = []

    def fake_http(url, payload, headers, timeout):
        calls.append({"url": url, "payload": dict(payload), "headers": dict(headers), "timeout": timeout})
        return 200, {"ok": True, "path": r"Y:\Estimates\23044 - Turner Bid", "created": True}

    monkeypatch.setattr(provision, "_http_post_json", fake_http)
    flask_app.config["ESTIMATE_FOLDER_PROVISION_URL"] = "http://data-server.example:5055"
    flask_app.config["ESTIMATE_FOLDER_PROVISION_TOKEN"] = "secret-token"
    flask_app.config["ESTIMATE_FOLDER_ROOT"] = ""

    eid = "est-folder-http-" + uuid.uuid4().hex[:12]
    try:
        with flask_app.app_context():
            le = _make_lead(eid, number="23044", name="Kaiser Fresno")
            lid = str(le.id)

        created = client.post(
            f"/api/v1/leads/{lid}/estimates",
            json={"name": "Turner – Bid Set"},
        )
        assert created.status_code == 201, created.get_data(as_text=True)
        item = created.get_json()["item"]
        est_id = item["id"]
        assert calls, "create-estimate should POST to the provisioner"
        assert calls[0]["url"] == "http://data-server.example:5055/provision/estimate-folder"
        assert calls[0]["headers"][provision.PROVISION_HEADER] == "secret-token"
        assert calls[0]["payload"]["estimate_id"] == est_id
        assert calls[0]["payload"]["job_number"] == "23044"
        assert calls[0]["payload"]["name"] == "Turner – Bid Set"
        assert "project_uuid" in calls[0]["payload"]
        assert item["folder_provision_status"] == "ready"
        assert item["folder_path"] == r"Y:\Estimates\23044 - Turner Bid"

        with flask_app.app_context():
            row = db.session.get(Estimate, uuid.UUID(est_id))
            assert row is not None
            assert row.folder_provision_status == "ready"
            assert row.folder_path == r"Y:\Estimates\23044 - Turner Bid"
            assert row.folder_provisioned_at is not None
    finally:
        with flask_app.app_context():
            _cleanup_lead(eid)


def test_create_estimate_survives_provision_failure(client, flask_app, monkeypatch):
    def boom(*_args, **_kwargs):
        raise TimeoutError("provisioner timed out")

    monkeypatch.setattr(provision, "_http_post_json", boom)
    flask_app.config["ESTIMATE_FOLDER_PROVISION_URL"] = "http://data-server.example:5055"
    flask_app.config["ESTIMATE_FOLDER_ROOT"] = ""

    eid = "est-folder-fail-" + uuid.uuid4().hex[:12]
    try:
        with flask_app.app_context():
            le = _make_lead(eid, number="24001")
            lid = str(le.id)

        created = client.post(f"/api/v1/leads/{lid}/estimates", json={"name": "Still created"})
        assert created.status_code == 201, created.get_data(as_text=True)
        item = created.get_json()["item"]
        assert item["name"] == "Still created"
        assert item["folder_provision_status"] == "failed"
        assert "timed out" in (item.get("folder_provision_error") or "")

        listed = client.get(f"/api/v1/leads/{lid}/estimates")
        assert listed.status_code == 200
        assert any(x["id"] == item["id"] for x in listed.get_json()["items"])
    finally:
        with flask_app.app_context():
            _cleanup_lead(eid)


def test_create_estimate_local_mkdir(client, flask_app, tmp_path):
    flask_app.config["ESTIMATE_FOLDER_PROVISION_URL"] = ""
    flask_app.config["ESTIMATE_FOLDER_ROOT"] = str(tmp_path)

    eid = "est-folder-mkdir-" + uuid.uuid4().hex[:12]
    try:
        with flask_app.app_context():
            le = _make_lead(eid, number="25010", name="Local mkdir lead")
            lid = str(le.id)

        created = client.post(f"/api/v1/leads/{lid}/estimates", json={"name": "Bid Set"})
        assert created.status_code == 201, created.get_data(as_text=True)
        item = created.get_json()["item"]
        assert item["folder_provision_status"] == "ready"
        dest = Path(item["folder_path"])
        assert dest.is_dir()
        assert (dest / "01_Bid_Docs").is_dir()
        assert (dest / "README.txt").is_file()
    finally:
        with flask_app.app_context():
            _cleanup_lead(eid)


def test_retry_provision_endpoint(client, flask_app, monkeypatch):
    flask_app.config["ESTIMATE_FOLDER_PROVISION_URL"] = "http://data-server.example:5055"
    flask_app.config["ESTIMATE_FOLDER_ROOT"] = ""

    def fail_once(*_args, **_kwargs):
        raise TimeoutError("down")

    monkeypatch.setattr(provision, "_http_post_json", fail_once)

    eid = "est-folder-retry-" + uuid.uuid4().hex[:12]
    try:
        with flask_app.app_context():
            le = _make_lead(eid, number="26000")
            lid = str(le.id)

        created = client.post(f"/api/v1/leads/{lid}/estimates", json={"name": "Retry me"})
        est_id = created.get_json()["item"]["id"]
        assert created.get_json()["item"]["folder_provision_status"] == "failed"

        def ok_http(url, payload, headers, timeout):
            return 200, {"ok": True, "path": r"Y:\Estimates\26000 - Retry me", "created": False}

        monkeypatch.setattr(provision, "_http_post_json", ok_http)
        retried = client.post(f"/api/v1/estimates/{est_id}/provision-folder")
        assert retried.status_code == 200, retried.get_data(as_text=True)
        body = retried.get_json()
        assert body["ok"] is True
        assert body["created"] is False
        assert body["item"]["folder_provision_status"] == "ready"
        assert body["item"]["folder_path"] == r"Y:\Estimates\26000 - Retry me"
    finally:
        with flask_app.app_context():
            _cleanup_lead(eid)


def test_extra_plan_create_estimate_triggers_provision(client, flask_app, monkeypatch):
    calls: list[str] = []

    def fake_http(url, payload, headers, timeout):
        calls.append(payload["estimate_id"])
        return 200, {"ok": True, "path": r"Y:\Estimates\plan", "created": True}

    monkeypatch.setattr(provision, "_http_post_json", fake_http)
    flask_app.config["ESTIMATE_FOLDER_PROVISION_URL"] = "http://data-server.example:5055"
    flask_app.config["ESTIMATE_FOLDER_ROOT"] = ""

    eid = "est-folder-plan-" + uuid.uuid4().hex[:12]
    try:
        with flask_app.app_context():
            le = _make_lead(eid, number="28000")
            lid = str(le.id)

        created = client.post("/api/v1/estimates", json={"lead_estimate_id": lid, "name": "Plan create"})
        assert created.status_code == 201, created.get_data(as_text=True)
        est_id = created.get_json()["item"]["id"]
        assert est_id in calls
        with flask_app.app_context():
            row = db.session.get(Estimate, uuid.UUID(est_id))
            assert row is not None
            assert row.folder_provision_status == "ready"
    finally:
        with flask_app.app_context():
            _cleanup_lead(eid)


def test_ensure_current_estimate_schedules_provision(flask_app, monkeypatch):
    calls: list[str] = []

    def fake_http(url, payload, headers, timeout):
        calls.append(payload["estimate_id"])
        return 200, {"ok": True, "path": r"Y:\Estimates\auto", "created": True}

    monkeypatch.setattr(provision, "_http_post_json", fake_http)
    flask_app.config["ESTIMATE_FOLDER_PROVISION_URL"] = "http://data-server.example:5055"
    flask_app.config["ESTIMATE_FOLDER_ROOT"] = ""

    eid = "est-folder-ensure-" + uuid.uuid4().hex[:12]
    try:
        with flask_app.app_context():
            from app.api._estimate_service import current_estimate_for_lead, ensure_current_estimate

            le = _make_lead(eid, number="27000")
            assert current_estimate_for_lead(le) is None
            est = ensure_current_estimate(le)
            db.session.commit()
            assert str(est.id) in calls
            db.session.refresh(est)
            assert est.folder_provision_status == "ready"
    finally:
        with flask_app.app_context():
            _cleanup_lead(eid)
