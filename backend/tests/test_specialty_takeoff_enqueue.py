"""Specialty-takeoff follower after estimate folder provision."""
from __future__ import annotations

import uuid
from types import SimpleNamespace

from app.services import estimate_folder_provision as provision
from app.services import specialty_takeoff_enqueue as enqueue


def _estimate(**kwargs):
    return SimpleNamespace(
        id=kwargs.get("id", uuid.uuid4()),
        project_id=kwargs.get("project_id"),
        lead_estimate_id=kwargs.get("lead_estimate_id"),
        folder_path=kwargs.get("folder_path"),
        folder_provision_status=None,
        folder_provision_error=None,
        folder_provisioned_at=None,
    )


class _FakeSession:
    def __init__(self, est, events: list[str]):
        self._est = est
        self._events = events

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def get(self, _model, _eid):
        return self._est

    def commit(self):
        self._events.append("commit")


def _run_provision(flask_app, monkeypatch, est, result, *, post=None):
    events: list[str] = []

    def fake_session(*_args, **_kwargs):
        return _FakeSession(est, events)

    monkeypatch.setattr(provision, "Session", fake_session)
    monkeypatch.setattr(provision, "_expire_cached_estimate", lambda *_a, **_k: None)
    monkeypatch.setattr(provision, "provision_estimate_folder", lambda *_a, **_k: result)
    if post is not None:
        monkeypatch.setattr(enqueue, "post_queue", post)
    flask_app.config["SPECIALTY_TAKEOFF_QUEUE_URL"] = "http://queue.example/specialty-takeoff"
    flask_app.config["SPECIALTY_TAKEOFF_QUEUE_TOKEN"] = ""
    flask_app.config["SPECIALTY_TAKEOFF_SLUGS"] = ""
    with flask_app.app_context():
        out = provision.provision_estimate_folder_by_id(est.id)
    return out, events


def test_default_specialty_slugs_are_nine():
    assert enqueue.SPECIALTY_SLUGS == (
        "bathroom_partitions",
        "bathroom_accessories",
        "lockers",
        "wall_protection",
        "fire_extinguisher_cabinets",
        "commercial_millwork",
        "doors",
        "markerboards",
        "signage",
    )
    assert len(enqueue.SPECIALTY_SLUGS) == 9


def test_on_estimate_folder_ready_noop_when_url_unset(flask_app, monkeypatch):
    posts: list = []

    def fake_post(*args, **kwargs):
        posts.append(args)
        return 200

    monkeypatch.setattr(enqueue, "post_queue", fake_post)
    flask_app.config["SPECIALTY_TAKEOFF_QUEUE_URL"] = ""
    eid = uuid.uuid4()
    with flask_app.app_context():
        enqueue.on_estimate_folder_ready(eid, r"Y:\Estimates\23044 - Turner Bid")
    assert posts == []


def test_on_estimate_folder_ready_posts_confirmed_payload(flask_app, monkeypatch):
    captured: list[dict] = []

    def fake_post(url, payload, headers, timeout):
        captured.append(
            {"url": url, "payload": dict(payload), "headers": dict(headers), "timeout": timeout}
        )
        return 202

    monkeypatch.setattr(enqueue, "post_queue", fake_post)
    flask_app.config["SPECIALTY_TAKEOFF_QUEUE_URL"] = "http://queue.example/specialty-takeoff"
    flask_app.config["SPECIALTY_TAKEOFF_QUEUE_TOKEN"] = "queue-secret"
    flask_app.config["SPECIALTY_TAKEOFF_QUEUE_TIMEOUT_SEC"] = "5"
    flask_app.config["SPECIALTY_TAKEOFF_SLUGS"] = ""
    eid = uuid.uuid4()
    folder = r"Y:\Estimates\23044 - Turner Bid"
    with flask_app.app_context():
        enqueue.on_estimate_folder_ready(eid, folder)

    assert len(captured) == 1
    call = captured[0]
    assert call["url"] == "http://queue.example/specialty-takeoff"
    assert call["timeout"] == 5.0
    assert call["headers"][enqueue.QUEUE_HEADER] == "queue-secret"
    assert call["headers"]["Content-Type"] == "application/json"
    body = call["payload"]
    assert set(body) == {"schema", "estimate_id", "folder_path", "status", "specialties", "artifact_roots"}
    assert body["schema"] == "usis.specialty_takeoff.v1"
    assert body["estimate_id"] == str(eid)
    assert body["folder_path"] == folder
    assert body["status"] == "ready_for_takeoff"
    assert body["specialties"] == list(enqueue.SPECIALTY_SLUGS)
    assert set(body["artifact_roots"]) == set(enqueue.SPECIALTY_SLUGS)
    for slug in enqueue.SPECIALTY_SLUGS:
        assert body["artifact_roots"][slug] == folder + "\\03_Takeoff\\" + slug + "\\"


def test_on_estimate_folder_ready_swallows_http_500_and_raise(flask_app, monkeypatch):
    flask_app.config["SPECIALTY_TAKEOFF_QUEUE_URL"] = "http://queue.example/specialty-takeoff"
    eid = uuid.uuid4()
    folder = r"Y:\Estimates\23044 - Turner Bid"

    monkeypatch.setattr(enqueue, "post_queue", lambda *a, **k: 500)
    with flask_app.app_context():
        enqueue.on_estimate_folder_ready(eid, folder)

    def boom(*_a, **_k):
        raise TimeoutError("queue down")

    monkeypatch.setattr(enqueue, "post_queue", boom)
    with flask_app.app_context():
        enqueue.on_estimate_folder_ready(eid, folder)


def test_swapped_hook_receives_estimate_id_and_folder_path(flask_app, monkeypatch):
    posts: list = []
    seen: list[tuple] = []
    folder = r"Y:\Estimates\23044 - Turner Bid"
    est = _estimate()

    def replacement(estimate_id, folder_path):
        seen.append((estimate_id, folder_path))

    monkeypatch.setattr(enqueue, "post_queue", lambda *a, **k: posts.append(a) or 200)
    enqueue.set_on_estimate_folder_ready(replacement)
    try:
        result = provision.ProvisionResult(
            ok=True, status=provision.STATUS_READY, path=folder, created=True, via="http"
        )
        out, events = _run_provision(flask_app, monkeypatch, est, result)
        assert out.status == "ready"
        assert events == ["commit"]
        assert seen == [(est.id, folder)]
        assert posts == []
    finally:
        enqueue.set_on_estimate_folder_ready(None)


def test_provision_ready_posts_after_commit_and_survives_queue_500(flask_app, monkeypatch):
    posts: list[dict] = []
    folder = r"Y:\Estimates\23044 - Turner Bid"
    est = _estimate()

    def fake_post(url, payload, headers, timeout):
        posts.append({"url": url, "payload": dict(payload), "headers": dict(headers), "timeout": timeout})
        return 500

    result = provision.ProvisionResult(ok=True, status=provision.STATUS_READY, path=folder, created=True, via="http")
    out, events = _run_provision(flask_app, monkeypatch, est, result, post=fake_post)
    assert out.ok is True
    assert out.status == "ready"
    assert out.path == folder
    assert events == ["commit"]
    assert est.folder_provision_status == "ready"
    assert est.folder_path == folder
    assert len(posts) == 1
    body = posts[0]["payload"]
    assert posts[0]["url"] == "http://queue.example/specialty-takeoff"
    assert body["schema"] == "usis.specialty_takeoff.v1"
    assert body["estimate_id"] == str(est.id)
    assert body["folder_path"] == folder
    assert body["status"] == "ready_for_takeoff"
    assert body["specialties"] == list(enqueue.SPECIALTY_SLUGS)
    assert body["artifact_roots"]["doors"] == folder + "\\03_Takeoff\\doors\\"


def test_provision_ready_survives_enqueue_raise(flask_app, monkeypatch):
    folder = r"Y:\Estimates\24001 - Still Ready"
    est = _estimate()

    def boom(*_a, **_k):
        raise RuntimeError("enqueue exploded")

    result = provision.ProvisionResult(ok=True, status=provision.STATUS_READY, path=folder, created=True, via="http")
    out, events = _run_provision(flask_app, monkeypatch, est, result, post=boom)
    assert out.ok is True
    assert out.status == "ready"
    assert out.path == folder
    assert events == ["commit"]
    assert est.folder_provision_status == "ready"
    assert est.folder_path == folder


def test_ready_without_path_does_not_enqueue(flask_app, monkeypatch):
    posts: list = []
    est = _estimate()
    result = provision.ProvisionResult(ok=True, status=provision.STATUS_READY, path="  ")
    out, events = _run_provision(
        flask_app,
        monkeypatch,
        est,
        result,
        post=lambda *a, **k: posts.append(a) or 200,
    )
    assert out.status == "ready"
    assert events == ["commit"]
    assert posts == []


def test_failed_provision_does_not_enqueue(flask_app, monkeypatch):
    posts: list = []
    est = _estimate()
    result = provision.ProvisionResult(ok=False, status=provision.STATUS_FAILED, error="timed out", via="http")
    out, events = _run_provision(
        flask_app,
        monkeypatch,
        est,
        result,
        post=lambda *a, **k: posts.append(a) or 200,
    )
    assert out.status == "failed"
    assert events == ["commit"]
    assert est.folder_provision_status == "failed"
    assert posts == []


def test_unconfigured_provision_does_not_enqueue(flask_app, monkeypatch):
    posts: list = []
    est = _estimate()
    result = provision.ProvisionResult(ok=True, status=provision.STATUS_UNCONFIGURED)
    out, events = _run_provision(
        flask_app,
        monkeypatch,
        est,
        result,
        post=lambda *a, **k: posts.append(a) or 200,
    )
    assert out.status == "unconfigured"
    assert events == []
    assert est.folder_provision_status is None
    assert posts == []
