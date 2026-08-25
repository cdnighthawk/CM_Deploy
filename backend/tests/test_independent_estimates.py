"""Independent estimates per lead: create, copy, lock, unlock, backfill."""
from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import select

from app.extensions import db
from app.models.estimate import Estimate
from app.models.lead_estimate import LeadEstimate
from app.models.takeoff_line_item import TakeoffLineItem
from app.services.estimate_backfill import backfill_default_estimate_for_lead


def _make_lead(external_id: str, **kwargs) -> LeadEstimate:
    le = LeadEstimate(external_id=external_id, name=kwargs.pop("name", "Estimate parent"), **kwargs)
    db.session.add(le)
    db.session.commit()
    return le


def _cleanup_lead(external_id: str) -> None:
    row = db.session.scalar(select(LeadEstimate).where(LeadEstimate.external_id == external_id))
    if row is not None:
        db.session.delete(row)
        db.session.commit()


def test_create_fresh_estimate(client, flask_app):
    eid = "est-fresh-" + uuid.uuid4().hex[:12]
    try:
        with flask_app.app_context():
            le = _make_lead(eid)
            lid = str(le.id)

        created = client.post(
            f"/api/v1/leads/{lid}/estimates",
            json={"name": "Turner – Bid Set", "gc_name": "Turner Construction", "fee_percentage": 8.5},
        )
        assert created.status_code == 201, created.get_data(as_text=True)
        item = created.get_json()["item"]
        assert item["name"] == "Turner – Bid Set"
        assert item["gc_name"] == "Turner Construction"
        assert item["fee_percentage"] == 8.5
        assert item["status"] == "draft"
        assert item["lead_estimate_id"] == lid
        assert item["takeoff_lines"] == []
        est_id = item["id"]

        listed = client.get(f"/api/v1/leads/{lid}/estimates")
        assert listed.status_code == 200
        names = [x["name"] for x in listed.get_json()["items"]]
        assert "Turner – Bid Set" in names

        fetched = client.get(f"/api/v1/estimates/{est_id}")
        assert fetched.status_code == 200
        body = fetched.get_json()["item"]
        assert body["id"] == est_id
        assert body["lead"]["id"] == lid
        assert body["name"] == "Turner – Bid Set"

        compat = client.get(f"/api/v1/lead-estimates/{lid}")
        assert compat.status_code == 200
        assert compat.get_json()["item"]["current_estimate_id"] == est_id
    finally:
        with flask_app.app_context():
            _cleanup_lead(eid)


def test_copy_estimate_deep_copies_lines(client, flask_app):
    eid = "est-copy-" + uuid.uuid4().hex[:12]
    try:
        with flask_app.app_context():
            le = _make_lead(eid, fee_percentage=Decimal("6.0"))
            lid = str(le.id)

        src = client.post(
            f"/api/v1/leads/{lid}/estimates",
            json={"name": "Original", "fee_percentage": 6},
        )
        assert src.status_code == 201, src.get_data(as_text=True)
        src_id = src.get_json()["item"]["id"]

        line = client.post(
            f"/api/v1/estimates/{src_id}/takeoff-lines",
            json={
                "description": "Lockers",
                "quantity": 2,
                "unit": "EA",
                "unit_cost": 100,
                "cost_type": "M",
                "section": "10 51 00",
            },
        )
        assert line.status_code == 201, line.get_data(as_text=True)
        src_line_id = line.get_json()["item"]["id"]

        copied = client.post(
            f"/api/v1/leads/{lid}/estimates",
            json={"name": "Rev A – IFC", "copy_from_estimate_id": src_id},
        )
        assert copied.status_code == 201, copied.get_data(as_text=True)
        copy_item = copied.get_json()["item"]
        assert copy_item["name"] == "Rev A – IFC"
        assert copy_item["created_from_id"] == src_id
        assert copy_item["fee_percentage"] == 6.0
        assert len(copy_item["takeoff_lines"]) == 1
        copy_line = copy_item["takeoff_lines"][0]
        assert copy_line["id"] != src_line_id
        assert copy_line["description"] == "Lockers"
        assert copy_line["quantity"] == 2.0
        assert copy_line["extended_total"] == 200.0
        assert copy_line["estimate_id"] == copy_item["id"]

        src_again = client.get(f"/api/v1/estimates/{src_id}")
        assert len(src_again.get_json()["item"]["takeoff_lines"]) == 1
        assert src_again.get_json()["item"]["takeoff_lines"][0]["id"] == src_line_id
    finally:
        with flask_app.app_context():
            _cleanup_lead(eid)


def test_lock_rejects_takeoff_writes(client, flask_app):
    eid = "est-lock-" + uuid.uuid4().hex[:12]
    try:
        with flask_app.app_context():
            le = _make_lead(eid)
            lid = str(le.id)

        created = client.post(f"/api/v1/leads/{lid}/estimates", json={"name": "Bid"})
        est_id = created.get_json()["item"]["id"]
        line = client.post(
            f"/api/v1/estimates/{est_id}/takeoff-lines",
            json={"description": "A", "quantity": 1, "unit": "EA", "unit_cost": 5, "cost_type": "M"},
        )
        assert line.status_code == 201
        line_id = line.get_json()["item"]["id"]

        locked = client.post(f"/api/v1/estimates/{est_id}/lock")
        assert locked.status_code == 200, locked.get_data(as_text=True)
        assert locked.get_json()["item"]["estimate_locked_at"]

        denied = client.post(
            f"/api/v1/estimates/{est_id}/takeoff-lines",
            json={"description": "B", "quantity": 1, "unit": "EA", "unit_cost": 1, "cost_type": "M"},
        )
        assert denied.status_code == 403
        assert denied.get_json()["error_code"] == "ESTIMATE_LOCKED"

        patch_denied = client.patch(f"/api/v1/takeoff-lines/{line_id}", json={"quantity": 9})
        assert patch_denied.status_code == 403
        assert patch_denied.get_json()["error_code"] == "ESTIMATE_LOCKED"

        delete_denied = client.delete(f"/api/v1/takeoff-lines/{line_id}")
        assert delete_denied.status_code == 403
    finally:
        with flask_app.app_context():
            _cleanup_lead(eid)


def test_unlock_admin_only(client, flask_app, monkeypatch):
    eid = "est-unlock-" + uuid.uuid4().hex[:12]
    try:
        with flask_app.app_context():
            le = _make_lead(eid)
            lid = str(le.id)

        created = client.post(f"/api/v1/leads/{lid}/estimates", json={"name": "Bid"})
        est_id = created.get_json()["item"]["id"]
        client.post(f"/api/v1/estimates/{est_id}/lock")

        import app.api.v1 as v1

        monkeypatch.setattr(v1, "_can_unlock_lead_estimate", lambda _cu: False)
        forbidden = client.post(f"/api/v1/estimates/{est_id}/unlock")
        assert forbidden.status_code == 403
        assert forbidden.get_json()["error_code"] == "UNLOCK_FORBIDDEN"

        monkeypatch.setattr(v1, "_can_unlock_lead_estimate", lambda _cu: True)
        unlocked = client.post(f"/api/v1/estimates/{est_id}/unlock")
        assert unlocked.status_code == 200, unlocked.get_data(as_text=True)
        assert unlocked.get_json()["item"]["estimate_locked_at"] is None

        allowed = client.post(
            f"/api/v1/estimates/{est_id}/takeoff-lines",
            json={"description": "After unlock", "quantity": 1, "unit": "EA", "unit_cost": 2, "cost_type": "M"},
        )
        assert allowed.status_code == 201, allowed.get_data(as_text=True)
    finally:
        with flask_app.app_context():
            _cleanup_lead(eid)


def test_backfill_attaches_orphaned_lines(flask_app):
    eid = "est-backfill-" + uuid.uuid4().hex[:12]
    try:
        with flask_app.app_context():
            le = _make_lead(eid, fee_percentage=Decimal("7.25"), crm_stage="Awarded")
            line = TakeoffLineItem(
                lead_estimate_id=le.id,
                description="Orphan",
                quantity=Decimal("3"),
                unit="EA",
                unit_cost=Decimal("10"),
                extended_total=Decimal("30"),
            )
            db.session.add(line)
            db.session.commit()
            line_id = line.id
            lead_id = le.id

            backfill_default_estimate_for_lead(db.session.connection(), lead_id)
            db.session.commit()
            db.session.expire_all()

            attached = db.session.get(TakeoffLineItem, line_id)
            assert attached is not None
            assert attached.estimate_id is not None
            est = db.session.get(Estimate, attached.estimate_id)
            assert est is not None
            assert est.lead_estimate_id == lead_id
            assert est.name == "Original Estimate"
            assert est.is_current is True
            assert est.status == "awarded"
            assert est.fee_percentage == Decimal("7.2500") or float(est.fee_percentage) == 7.25

            orphans = db.session.scalars(
                select(TakeoffLineItem).where(
                    TakeoffLineItem.lead_estimate_id == lead_id,
                    TakeoffLineItem.estimate_id.is_(None),
                )
            ).all()
            assert orphans == []
    finally:
        with flask_app.app_context():
            _cleanup_lead(eid)


def test_patch_estimate_and_lock_rejects_metadata(client, flask_app):
    eid = "est-patch-" + uuid.uuid4().hex[:12]
    try:
        with flask_app.app_context():
            le = _make_lead(eid)
            lid = str(le.id)

        created = client.post(f"/api/v1/leads/{lid}/estimates", json={"name": "Bid"})
        est_id = created.get_json()["item"]["id"]
        patched = client.patch(
            f"/api/v1/estimates/{est_id}",
            json={"name": "Turner – Bid Set", "gc_name": "Turner", "fee_percentage": 9.25, "rom": 50000},
        )
        assert patched.status_code == 200, patched.get_data(as_text=True)
        item = patched.get_json()["item"]
        assert item["name"] == "Turner – Bid Set"
        assert item["gc_name"] == "Turner"
        assert item["fee_percentage"] == 9.25
        assert item["rom"] == 50000

        client.post(f"/api/v1/estimates/{est_id}/lock")
        denied = client.patch(f"/api/v1/estimates/{est_id}", json={"name": "Should fail"})
        assert denied.status_code == 403
        assert denied.get_json()["error_code"] == "ESTIMATE_LOCKED"
    finally:
        with flask_app.app_context():
            _cleanup_lead(eid)


def test_delete_unlocked_estimate(client, flask_app):
    eid = "est-del-" + uuid.uuid4().hex[:12]
    try:
        with flask_app.app_context():
            le = _make_lead(eid)
            lid = str(le.id)

        first = client.post(f"/api/v1/leads/{lid}/estimates", json={"name": "Keep"})
        second = client.post(f"/api/v1/leads/{lid}/estimates", json={"name": "Drop"})
        drop_id = second.get_json()["item"]["id"]
        assert first.status_code == 201
        deleted = client.delete(f"/api/v1/estimates/{drop_id}")
        assert deleted.status_code == 200
        assert client.get(f"/api/v1/estimates/{drop_id}").status_code == 404
    finally:
        with flask_app.app_context():
            _cleanup_lead(eid)
