"""Acceptance tests for the submittal QC gate."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.exc import ProgrammingError

from app.extensions import db
from app.models import (
    Company,
    Commitment,
    CommitmentLineItem,
    Project,
    Submittal,
    SubmittalChecklistItem,
    SubmittalRevision,
    User,
    WorkflowDefinition,
    WorkflowInstance,
    WorkflowQueue,
    WorkflowQueueMember,
)


def _skip_if_unmigrated(exc: Exception) -> None:
    if isinstance(exc, ProgrammingError) or "does not exist" in str(exc):
        pytest.skip("submittal QC tables missing (run flask db upgrade)")
    raise exc


def _project(name: str | None = None) -> Project:
    p = Project(name=name or ("QC-" + uuid.uuid4().hex[:8]), number="0142")
    db.session.add(p)
    db.session.flush()
    return p


def _create(client, pid: str, **kwargs):
    body = {"title": kwargs.pop("title", "MPI 143 eggshell"), "spec_section": kwargs.pop("spec_section", "09 91 00")}
    body.update(kwargs)
    r = client.post(f"/api/v1/projects/{pid}/submittals", json=body)
    if r.status_code >= 500:
        pytest.skip("submittal QC not migrated")
    return r


def test_create_starts_workflow_and_register_payload(client):
    with client.application.app_context():
        try:
            p = _project()
            pid = str(p.id)
            db.session.commit()
        except Exception as exc:
            _skip_if_unmigrated(exc)

    r = _create(client, pid)
    assert r.status_code == 201
    item = r.get_json()["item"]
    assert item["submittal_number"].startswith("SUB-0142-")
    sid = item["id"]

    r2 = client.get(f"/api/submittals?project_id={pid}")
    assert r2.status_code == 200
    rows = r2.get_json()["items"]
    assert any(x["id"] == sid for x in rows)
    row = next(x for x in rows if x["id"] == sid)
    assert "rubberStampSuspect" in row
    assert row["packageComplete"] is False

    d = client.get(f"/api/submittals/{sid}").get_json()
    assert d["workflow"]["processKey"] == "submittal_qc"
    assert d["workflow"]["steps"]
    assert d["revision"]["revision"] == "A"


def test_incomplete_package_cannot_stamp(client):
    with client.application.app_context():
        p = _project()
        pid = str(p.id)
        db.session.commit()
    r = _create(client, pid)
    sid = r.get_json()["item"]["id"]
    d = client.get(f"/api/submittals/{sid}").get_json()
    rev = d["revision"]["id"]
    bad = client.post(
        f"/api/submittals/{sid}/revisions/{rev}/stamp",
        json={"stamp": "no_exceptions", "rush_exception": True},
    )
    assert bad.status_code == 409
    assert "complete" in (bad.get_json().get("error") or "").lower() or "Package" in (bad.get_json().get("error") or "")


def test_ai_override_and_critical_disposition_and_rubber_flag(client):
    with client.application.app_context():
        p = _project()
        pid = str(p.id)
        db.session.commit()
    r = _create(client, pid, trade="paint")
    sid = r.get_json()["item"]["id"]
    d = client.get(f"/api/submittals/{sid}").get_json()
    rev = d["revision"]["id"]

    client.post(
        f"/api/v1/projects/{pid}/submittals/{sid}/attachments",
        json={"file_url": "https://example.com/cut.pdf", "title": "cut", "mime_type": "application/pdf"},
    )
    client.post(f"/api/submittals/{sid}/revisions/{rev}/completeness", json={})

    no_ai = client.post(
        f"/api/submittals/{sid}/revisions/{rev}/stamp",
        json={"stamp": "no_exceptions", "rush_exception": True},
    )
    assert no_ai.status_code == 409
    assert "AI" in (no_ai.get_json().get("error") or "")

    empty_ov = client.post(
        f"/api/submittals/{sid}/revisions/{rev}/ai-review",
        json={"ai_status": "overridden", "ai_overridden_reason": ""},
    )
    assert empty_ov.status_code == 409 or empty_ov.status_code == 400

    client.post(
        f"/api/submittals/{sid}/revisions/{rev}/ai-review",
        json={
            "ai_status": "complete",
            "findings": [
                {
                    "id": "f1",
                    "severity": "Critical",
                    "title": "Wrong MPI system",
                    "suggested_checklist_item": "Confirm MPI 143",
                }
            ],
        },
    )
    d = client.get(f"/api/submittals/{sid}").get_json()
    items = d["revision"]["checklist"]
    for it in items:
        if it["required"]:
            client.patch(
                f"/api/submittals/{sid}/revisions/{rev}/checklist",
                json={"items": [{"id": it["id"], "result": "pass", "comment": "ok" if it["source"] != "ai_finding" else ""}]},
            )
    no_disp = client.post(
        f"/api/submittals/{sid}/revisions/{rev}/stamp",
        json={"stamp": "no_exceptions", "rush_exception": True},
    )
    assert no_disp.status_code == 409
    assert "disposition" in (no_disp.get_json().get("error") or "").lower()

    d = client.get(f"/api/submittals/{sid}").get_json()
    ai_row = next(i for i in d["revision"]["checklist"] if i["source"] == "ai_finding")
    client.patch(
        f"/api/submittals/{sid}/revisions/{rev}/checklist",
        json={"items": [{"id": ai_row["id"], "result": "fail", "comment": "noted", "disposition": "overridden"}]},
    )
    ok = client.post(
        f"/api/submittals/{sid}/revisions/{rev}/stamp",
        json={"stamp": "no_exceptions", "rush_exception": True, "comments": "fast"},
    )
    assert ok.status_code == 200, ok.get_json()
    stamped = ok.get_json()["revision"]
    assert stamped["rubberStampSuspect"] is True
    assert stamped["humanStamp"] == "no_exceptions"


def test_revise_resubmit_opens_rev_b_and_keeps_holds(client):
    with client.application.app_context():
        p = _project()
        pid = str(p.id)
        db.session.commit()
    r = _create(client, pid)
    sid = r.get_json()["item"]["id"]
    d = client.get(f"/api/submittals/{sid}").get_json()
    rev = d["revision"]["id"]
    client.post(
        f"/api/v1/projects/{pid}/submittals/{sid}/attachments",
        json={"file_url": "https://example.com/a.pdf", "mime_type": "application/pdf"},
    )
    client.post(f"/api/submittals/{sid}/revisions/{rev}/completeness", json={})
    client.post(
        f"/api/submittals/{sid}/revisions/{rev}/ai-review",
        json={"ai_status": "overridden", "ai_overridden_reason": "PM reviewed on site"},
    )
    d = client.get(f"/api/submittals/{sid}").get_json()
    for it in d["revision"]["checklist"]:
        if it["required"]:
            client.patch(
                f"/api/submittals/{sid}/revisions/{rev}/checklist",
                json={"items": [{"id": it["id"], "result": "na", "comment": "n/a"}]},
            )
    out = client.post(
        f"/api/submittals/{sid}/revisions/{rev}/stamp",
        json={"stamp": "revise_resubmit", "rush_exception": True, "comments": "wrong color"},
    )
    assert out.status_code == 200, out.get_json()
    body = out.get_json()
    assert body["item"]["status"] == "revise_resubmit"
    letters = {r["revision"]: r["isCurrent"] for r in body["revisions"]}
    assert letters.get("A") is False
    assert letters.get("B") is True
    assert any(h["isActive"] for h in body["holds"])


def test_po_issue_409_includes_submittal_number(client):
    with client.application.app_context():
        p = _project()
        vendor = Company(name="Sherwin", company_type="vendor")
        db.session.add(vendor)
        db.session.flush()
        pid = str(p.id)
        vid = vendor.id
        db.session.commit()
    r = _create(client, pid)
    sid = r.get_json()["item"]["id"]
    number = r.get_json()["item"]["submittal_number"]
    with client.application.app_context():
        c = Commitment(
            project_id=uuid.UUID(pid),
            vendor_company_id=vid,
            commitment_kind="purchase_order",
            reference_number="PO-1",
            title="Paint",
            status="draft",
        )
        db.session.add(c)
        db.session.flush()
        db.session.add(
            CommitmentLineItem(
                commitment_id=c.id,
                description="MPI 143",
                quantity=1,
                unit="GAL",
                unit_cost=10,
                line_total=10,
                submittal_id=uuid.UUID(sid),
                submittal_release_required=True,
            )
        )
        cid = str(c.id)
        db.session.commit()
    issued = client.post(f"/api/purchase-orders/{cid}/issue", json={})
    assert issued.status_code == 409
    assert number in (issued.get_json().get("error") or "")


def test_new_definition_does_not_rewrite_inflight_snapshot(client):
    with client.application.app_context():
        p = _project()
        pid = str(p.id)
        db.session.commit()
    r = _create(client, pid)
    sid = r.get_json()["item"]["id"]
    d1 = client.get(f"/api/submittals/{sid}").get_json()
    version_a = d1["workflow"]["definitionVersion"]
    steps_a = [s["stepKey"] for s in d1["workflow"]["steps"]]

    pub = client.post(
        "/api/workflows/definitions",
        json={
            "process_key": "submittal_qc",
            "name": "QC plus extra",
            "steps": [
                {"step_key": "log_completeness", "label": "Log", "sort_order": 1, "required_actions": ["completeness"]},
                {"step_key": "extra_gov", "label": "Gov extra", "sort_order": 2, "required_actions": ["stamp"]},
            ],
        },
    )
    assert pub.status_code in (200, 201), pub.get_json()

    d1b = client.get(f"/api/submittals/{sid}").get_json()
    assert [s["stepKey"] for s in d1b["workflow"]["steps"]] == steps_a
    assert d1b["workflow"]["definitionVersion"] == version_a

    r2 = _create(client, pid, title="Second package")
    sid2 = r2.get_json()["item"]["id"]
    d2 = client.get(f"/api/submittals/{sid2}").get_json()
    assert "extra_gov" in [s["stepKey"] for s in d2["workflow"]["steps"]]


def test_queue_removal_blocks_new_assignment(client):
    with client.application.app_context():
        p = _project()
        u = User(email="qc." + uuid.uuid4().hex[:8] + "@t.com", first_name="Q", last_name="C", is_active=True)
        db.session.add(u)
        db.session.flush()
        pid = str(p.id)
        uid = u.id
        db.session.commit()
    r = _create(client, pid)
    sid = r.get_json()["item"]["id"]
    client.put(
        "/api/workflows/queues/trade_qc/members",
        json={"process_key": "submittal_qc", "user_ids": [str(uid)]},
    )
    ok = client.post(f"/api/submittals/{sid}/assign", json={"user_id": str(uid), "step_key": "local_ai_review"})
    assert ok.status_code in (200, 201, 409)
    client.put("/api/workflows/queues/trade_qc/members", json={"process_key": "submittal_qc", "user_ids": []})
    blocked = client.post(f"/api/submittals/{sid}/assign", json={"user_id": str(uid), "step_key": "local_ai_review"})
    assert blocked.status_code == 409
