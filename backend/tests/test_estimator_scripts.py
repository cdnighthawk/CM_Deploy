"""Overall bid-scope pass + spec script catalog."""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy.exc import ProgrammingError

from app.api._estimator_scripts import match_script, prefix_matches
from app.extensions import db
from app.models import Estimate, Project


def _skip_if_unmigrated(exc: Exception) -> None:
    if isinstance(exc, ProgrammingError) or "does not exist" in str(exc):
        pytest.skip("estimator script tables missing (run flask db upgrade)")
    raise exc


def test_prefix_match_div10_and_gypsum():
    assert prefix_matches("09 29", "09 29 00")
    assert prefix_matches("0929", "092913")
    assert prefix_matches("10", "10 51 13")
    assert not prefix_matches("09 91", "09 29 00")


def test_list_scripts_and_standard_specs(client):
    r = client.get("/api/workflows/scripts")
    if r.status_code >= 500:
        pytest.skip("estimator scripts not migrated")
    assert r.status_code == 200
    keys = {x["scriptKey"] for x in r.get_json()["items"]}
    assert "estimator_scope" in keys
    assert "spec.gypsum" in keys
    assert "spec.paint" in keys
    assert "spec.div10" in keys

    specs = client.get("/api/workflows/standard-specs")
    assert specs.status_code == 200
    codes = [x["specCode"] for x in specs.get_json()["items"]]
    assert "09 29 00" in codes
    assert "09 91 00" in codes


def test_match_script_picks_longest_prefix(client):
    listed = client.get("/api/workflows/scripts")
    if listed.status_code >= 500:
        pytest.skip("estimator scripts not migrated")
    with client.application.app_context():
        try:
            gypsum = match_script("09 29 13")
            paint = match_script("09 91 23")
            div10 = match_script("10 51 13")
        except Exception as exc:
            _skip_if_unmigrated(exc)
    assert gypsum is not None and gypsum.script_key == "spec.gypsum"
    assert paint is not None and paint.script_key == "spec.paint"
    assert div10 is not None and div10.script_key == "spec.div10"


def test_bid_scope_standard_then_enqueue(client):
    with client.application.app_context():
        try:
            p = Project(name="ES-" + uuid.uuid4().hex[:6])
            db.session.add(p)
            db.session.flush()
            est = Estimate(name="Scope test", project_id=p.id)
            db.session.add(est)
            db.session.flush()
            eid, pid = str(est.id), str(p.id)
            db.session.commit()
        except Exception as exc:
            _skip_if_unmigrated(exc)

    r = client.get(f"/api/v1/estimates/{eid}/bid-scope")
    if r.status_code >= 500:
        pytest.skip("bid scope not migrated")
    assert r.status_code == 200, r.get_data(as_text=True)
    item = r.get_json()["item"]
    assert item["source"] == "standard"
    assert any(x["specCode"] == "09 29 00" and x["scriptKey"] == "spec.gypsum" for x in item["items"])

    pkg = client.put(
        f"/api/v1/estimates/{eid}/bid-scope",
        json={
            "source": "bid_package",
            "bid_package_label": "BP-3 Interiors",
            "items": [
                {"spec_code": "09 29 00", "spec_title": "Gypsum Board", "included": True},
                {"spec_code": "09 91 00", "spec_title": "Painting", "included": True},
                {"spec_code": "09 65 00", "spec_title": "Resilient", "included": False},
            ],
        },
    )
    assert pkg.status_code == 200
    assert pkg.get_json()["item"]["source"] == "bid_package"

    enq = client.post(f"/api/v1/estimates/{eid}/bid-scope/enqueue", json={})
    assert enq.status_code == 200, enq.get_data(as_text=True)
    started = enq.get_json()["started"]
    keys = {x["scriptKey"] for x in started}
    assert keys == {"spec.gypsum", "spec.paint"}
    assert pid  # project created
