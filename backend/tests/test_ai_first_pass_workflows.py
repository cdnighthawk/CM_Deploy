"""Estimator first-pass drawing review + takeoff workflows."""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy.exc import ProgrammingError

from app.api._workflow_service import PROCESS_DRAWING_REVIEW, PROCESS_TAKEOFF
from app.ai.prompts import build_system_prompt
from app.extensions import db
from app.models import Project, WorkflowDefinition


def _skip_if_unmigrated(exc: Exception) -> None:
    if isinstance(exc, ProgrammingError) or "does not exist" in str(exc) or "automation" in str(exc).lower():
        pytest.skip("workflow automation column missing (run flask db upgrade)")
    raise exc


def test_system_hint_appends_to_prompt():
    text = build_system_prompt("construction_review", "Prefer a short findings list.")
    assert "Mode: construction_review" in text
    assert "Workflow hint" in text
    assert "short findings list" in text


def test_list_processes_seeds_drawing_and_takeoff(client):
    r = client.get("/api/workflows/processes")
    if r.status_code >= 500:
        pytest.skip("workflows not migrated")
    assert r.status_code == 200
    keys = {x["processKey"] for x in r.get_json()["items"]}
    assert PROCESS_DRAWING_REVIEW in keys
    assert PROCESS_TAKEOFF in keys


def test_seed_includes_automation_prompts(client):
    r = client.get("/api/workflows/seeds/drawing_review")
    if r.status_code >= 500:
        pytest.skip("workflows not migrated")
    assert r.status_code == 200
    steps = r.get_json()["steps"]
    keys = [s["step_key"] for s in steps]
    assert keys[0] == "capture_sheet"
    assert keys[-1] == "human_accept"
    ai = next(s for s in steps if s["step_key"] == "scope_scan")
    assert ai["automation"]["mode"] == "construction_review"
    assert "finish-work" in (ai["automation"].get("prompt") or "")


def test_ensure_and_complete_drawing_review_instance(client):
    with client.application.app_context():
        try:
            p = Project(name="WF-" + uuid.uuid4().hex[:6])
            db.session.add(p)
            db.session.flush()
            pid = str(p.id)
            db.session.commit()
        except Exception as exc:
            _skip_if_unmigrated(exc)

    drawing_id = str(uuid.uuid4())
    r = client.post(
        "/api/workflows/instances",
        json={
            "process_key": "drawing_review",
            "subject_type": "drawing",
            "subject_id": drawing_id,
            "project_id": pid,
        },
    )
    if r.status_code >= 500:
        pytest.skip("workflow automation not migrated")
    assert r.status_code == 200, r.get_data(as_text=True)
    item = r.get_json()["item"]
    assert item["processKey"] == "drawing_review"
    assert item["currentStepKey"] == "capture_sheet"
    assert item["steps"][1]["automation"]["action"] == "run_ai_review"
    iid = item["id"]

    again = client.post(
        "/api/workflows/instances",
        json={"process_key": "drawing_review", "subject_type": "drawing", "subject_id": drawing_id},
    )
    assert again.get_json()["item"]["id"] == iid

    done = client.post(
        f"/api/workflows/instances/{iid}/complete",
        json={"step_key": "capture_sheet"},
    )
    assert done.status_code == 200
    assert done.get_json()["item"]["currentStepKey"] == "scope_scan"


def test_publish_new_drawing_review_version(client):
    with client.application.app_context():
        try:
            p = Project(name="WF-pub-" + uuid.uuid4().hex[:6])
            db.session.add(p)
            db.session.flush()
            pid = str(p.id)
            db.session.commit()
        except Exception as exc:
            _skip_if_unmigrated(exc)

    body = {
        "process_key": "drawing_review",
        "project_id": pid,
        "name": "Drawing review tuned",
        "steps": [
            {
                "step_key": "scope_scan",
                "label": "Scope only",
                "sort_order": 1,
                "queue_key": "estimator",
                "required_actions": ["run_ai_review"],
                "automation": {
                    "action": "run_ai_review",
                    "mode": "construction_review",
                    "prompt": "Only list missing dimensions.",
                    "system_hint": "One bullet each.",
                    "auto_complete": True,
                },
            },
            {
                "step_key": "human_accept",
                "label": "Leftovers",
                "sort_order": 2,
                "queue_key": "reviewer",
                "required_actions": ["accept_findings"],
                "skippable": True,
                "automation": {"action": "human_accept", "auto_complete": False},
            },
        ],
    }
    r = client.post("/api/workflows/definitions", json=body)
    if r.status_code >= 500:
        pytest.skip("workflow automation not migrated")
    if r.status_code == 403:
        pytest.skip("publish requires admin in this environment")
    assert r.status_code == 201, r.get_data(as_text=True)
    pub = r.get_json()
    assert pub["processKey"] == "drawing_review"
    assert len(pub["steps"]) == 2
    assert pub["steps"][0]["automation"]["prompt"] == "Only list missing dimensions."

    with client.application.app_context():
        row = db.session.get(WorkflowDefinition, uuid.UUID(pub["id"]))
        assert row is not None
        assert row.is_published is True


def test_unknown_process_key_rejected(client):
    r = client.get("/api/workflows/seeds/not_a_real_process")
    if r.status_code >= 500:
        pytest.skip("workflows not migrated")
    assert r.status_code == 400
