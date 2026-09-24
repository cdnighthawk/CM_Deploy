"""Job-scoped openings workspace: register, sets, reconcile, apply, RFPs."""
from __future__ import annotations

import uuid

from sqlalchemy import select

from app.extensions import db
from app.models.estimate import Estimate
from app.models.lead_estimate import LeadEstimate
from app.material_configurator import LARSEN_CABINET_KEY, resolve_configuration
from app.models.takeoff_line_item import TakeoffLineItem


def _make_lead(external_id: str, **kwargs) -> LeadEstimate:
    le = LeadEstimate(external_id=external_id, name=kwargs.pop("name", "Openings parent"), **kwargs)
    db.session.add(le)
    db.session.commit()
    return le


def _cleanup_lead(external_id: str) -> None:
    row = db.session.scalar(select(LeadEstimate).where(LeadEstimate.external_id == external_id))
    if row is not None:
        db.session.delete(row)
        db.session.commit()


def _create_estimate(client, flask_app) -> tuple[str, str]:
    eid = "openings-" + uuid.uuid4().hex[:12]
    with flask_app.app_context():
        le = _make_lead(eid)
        lid = str(le.id)
    created = client.post(f"/api/v1/leads/{lid}/estimates", json={"name": "Openings bid"})
    assert created.status_code == 201, created.get_data(as_text=True)
    return eid, created.get_json()["item"]["id"]


SET_08_ITEMS = [
    {"qty": 3, "category": "hinge", "description": "Hinges", "manufacturer": "Hager", "catalog": "BB1279", "finish": "652"},
    {"qty": 1, "category": "lockset", "description": "Mortise lock", "manufacturer": "Schlage", "catalog": "L9453", "finish": "626"},
    {"qty": 1, "category": "closer", "description": "Closer", "manufacturer": "LCN", "catalog": "4040XP", "finish": "689"},
    {"qty": 1, "category": "stop", "description": "Wall stop", "manufacturer": "Ives", "catalog": "WS407", "finish": "626"},
    {"qty": 1, "category": "seal", "description": "Seals", "manufacturer": "Pemko", "catalog": "S88", "finish": ""},
]
SET_12_ITEMS = [
    {"qty": 6, "category": "hinge", "description": "Pair hinges", "manufacturer": "Hager", "catalog": "BB1279-P", "finish": "652"},
    {"qty": 2, "category": "exit_device", "description": "Exit device", "manufacturer": "Von Duprin", "catalog": "99L", "finish": "626"},
    {"qty": 2, "category": "closer", "description": "Closer", "manufacturer": "LCN", "catalog": "4040XP", "finish": "689"},
    {"qty": 1, "category": "coordinator", "description": "Coordinator", "manufacturer": "Ives", "catalog": "COR52", "finish": ""},
    {"qty": 1, "category": "flush_bolt", "description": "Flush bolts", "manufacturer": "Ives", "catalog": "FB458", "finish": "626"},
    {"qty": 1, "category": "threshold", "description": "Threshold", "manufacturer": "Pemko", "catalog": "171A", "finish": ""},
]
SET_01_ITEMS = [
    {"qty": 3, "category": "hinge", "description": "Hinges", "manufacturer": "Hager", "catalog": "BB1191", "finish": "652"},
    {"qty": 1, "category": "lockset", "description": "Cylindrical lock", "manufacturer": "Schlage", "catalog": "ND80", "finish": "626"},
    {"qty": 1, "category": "stop", "description": "Wall stop", "manufacturer": "Ives", "catalog": "WS407", "finish": "626"},
]


def _seed_sets(client, est_id: str) -> None:
    for set_no, title, pair, fire, items in (
        ("08", "Office rated closer", False, True, SET_08_ITEMS),
        ("12", "Pair exit", True, True, SET_12_ITEMS),
        ("01", "Wood office", False, False, SET_01_ITEMS),
    ):
        r = client.post(
            f"/api/v1/estimates/{est_id}/hardware-sets",
            json={"set_no": set_no, "title": title, "pair_set": pair, "fire_required": fire, "items": items},
        )
        assert r.status_code == 201, r.get_data(as_text=True)


def _opening(mark, **kw):
    row = {
        "mark": mark,
        "qty": 1,
        "leaf_count": 1,
        "width_in": 36,
        "height_in": 84,
        "hand": "RH",
        "fire_rating_min": 90,
        "material": "hm",
        "door_type_code": "D4",
        "frame_type_code": "F2",
        "frame_material": "hm",
        "frame_construction": "kd",
        "hardware_set_no": "08",
        "scope_flag": "in",
        "source": "csv",
    }
    row.update(kw)
    return row


def _seed_twelve(client, est_id: str) -> None:
    rows = []
    for i in range(8):
        rows.append(_opening(f"10{i + 1}"))
    rows.append(_opening("201", leaf_count=2, width_in=72, height_in=84, hardware_set_no="12", hand="PAIR"))
    rows.append(_opening("202", leaf_count=2, width_in=72, height_in=84, hardware_set_no="12", hand="PAIR"))
    rows.append(
        _opening(
            "301",
            material="wood",
            fire_rating_min=0,
            hardware_set_no="01",
            frame_material="hm",
        )
    )
    rows.append(
        _opening(
            "401",
            hardware_set_no="01",
            frame_material="existing",
            remarks="E.T.R. frame",
        )
    )
    r = client.post(f"/api/v1/estimates/{est_id}/openings/import", json={"rows": rows})
    assert r.status_code == 201, r.get_data(as_text=True)
    assert r.get_json()["opening_count"] == 12


def test_larsen_configurator_still_resolves():
    from decimal import Decimal

    resolved = resolve_configuration(
        manufacturer="Larsen",
        item="LARS-2409-R",
        mounting_type="Recessed",
        base_cost=Decimal("184"),
        configurator_key=LARSEN_CABINET_KEY,
        selections=None,
    )
    assert resolved.snapshot["key"] == LARSEN_CABINET_KEY
    assert resolved.unit_cost == Decimal("184")


def test_openings_stub_and_trade_map(client, flask_app):
    eid, est_id = _create_estimate(client, flask_app)
    try:
        r = client.get(f"/api/v1/estimates/{est_id}/openings")
        assert r.status_code == 200, r.get_data(as_text=True)
        body = r.get_json()
        assert body["openings"] == []
        assert body["reconcile"]["openings_in_scope"] == 0
        tm = client.get("/api/v1/spec-trade-map")
        assert tm.status_code == 200
        prefixes = {x["csi_prefix"] for x in tm.get_json()["items"]}
        assert {"08 11", "08 12", "08 14", "08 71"} <= prefixes
        openings_rows = [x for x in tm.get_json()["items"] if x.get("trade_group") == "openings"]
        assert openings_rows
        assert all(x["default_in_scope"] is False for x in openings_rows)
    finally:
        with flask_app.app_context():
            _cleanup_lead(eid)


def test_openings_csv_round_trip_and_range(client, flask_app):
    eid, est_id = _create_estimate(client, flask_app)
    try:
        r = client.post(
            f"/api/v1/estimates/{est_id}/openings/import",
            json={"rows": [_opening("101–104", hardware_set_no="08")]},
        )
        assert r.status_code == 201, r.get_data(as_text=True)
        assert r.get_json()["opening_count"] == 4
        exp = client.get(f"/api/v1/estimates/{est_id}/openings/export")
        assert exp.status_code == 200
        assert b"mark," in exp.data
        assert b"101" in exp.data
    finally:
        with flask_app.app_context():
            _cleanup_lead(eid)


def test_twelve_opening_fixture_reconcile_apply_rfp(client, flask_app):
    eid, est_id = _create_estimate(client, flask_app)
    try:
        _seed_sets(client, est_id)
        _seed_twelve(client, est_id)
        recon = client.get(f"/api/v1/estimates/{est_id}/openings/reconcile").get_json()["reconcile"]
        assert recon["missing_set"] == 0
        assert recon["unknown_set"] == 0
        assert recon["openings_in_scope"] == 12
        assert recon["apply_blocked"] is False

        pair = client.post(
            f"/api/v1/estimates/{est_id}/openings",
            json=_opening("501", leaf_count=2, hardware_set_no="08"),
        )
        assert pair.status_code == 201
        flags = pair.get_json()["item"]["conflicts"]["active"]
        assert "pair_mismatch" in flags
        client.delete(f"/api/v1/estimates/{est_id}/openings/{pair.get_json()['item']['id']}")

        applied = client.post(f"/api/v1/estimates/{est_id}/openings/apply", json={"roll_up": True})
        assert applied.status_code == 200, applied.get_data(as_text=True)
        with flask_app.app_context():
            lines = list(
                db.session.scalars(
                    select(TakeoffLineItem).where(
                        TakeoffLineItem.estimate_id == uuid.UUID(est_id),
                        TakeoffLineItem.source_kind == "opening",
                    )
                ).all()
            )
            hinge_08 = [
                ln
                for ln in lines
                if ln.line_role == "hardware_item"
                and isinstance(ln.configuration_json, dict)
                and (ln.configuration_json.get("catalogNumber") == "BB1279")
            ]
            assert hinge_08, [ln.description for ln in lines]
            assert float(hinge_08[0].quantity) == 24
            frames = [ln for ln in lines if ln.line_role == "frame"]
            frame_marks = []
            for ln in frames:
                cfg = ln.configuration_json or {}
                frame_marks.extend((cfg.get("attributes") or {}).get("openingMarks") or [])
            assert "401" not in frame_marks
            assert all(ln.door_opening_id is None for ln in lines)
        leftover = client.post(
            f"/api/v1/estimates/{est_id}/takeoff-lines",
            json={
                "description": "Estimator authored leftover",
                "quantity": 1,
                "unit": "EA",
                "unit_cost": 10,
                "cost_type": "M",
            },
        )
        assert leftover.status_code == 201, leftover.get_data(as_text=True)
        authored_id = leftover.get_json()["item"]["id"]

        extra = client.post(f"/api/v1/estimates/{est_id}/openings", json=_opening("109"))
        assert extra.status_code == 201
        reapplied = client.post(f"/api/v1/estimates/{est_id}/openings/apply", json={"roll_up": True})
        assert reapplied.status_code == 200, reapplied.get_data(as_text=True)
        with flask_app.app_context():
            hinge_08 = list(
                db.session.scalars(
                    select(TakeoffLineItem).where(
                        TakeoffLineItem.estimate_id == uuid.UUID(est_id),
                        TakeoffLineItem.source_kind == "opening",
                        TakeoffLineItem.line_role == "hardware_item",
                    )
                ).all()
            )
            match = [
                ln
                for ln in hinge_08
                if isinstance(ln.configuration_json, dict) and ln.configuration_json.get("catalogNumber") == "BB1279"
            ]
            assert match
            assert float(match[0].quantity) == 27
            leftover = db.session.get(TakeoffLineItem, uuid.UUID(authored_id))
            assert leftover is not None
            assert leftover.description == "Estimator authored leftover"

        rfps = client.post(f"/api/v1/estimates/{est_id}/openings/draft-rfps", json={})
        assert rfps.status_code == 201, rfps.get_data(as_text=True)
        items = rfps.get_json()["items"]
        assert len(items) == 2
        titles = {x["title"] for x in items}
        assert "Doors & frames" in titles
        assert "Door hardware" in titles

        hw_id = next(x["id"] for x in items if x["title"] == "Door hardware")
        detail = client.get(f"/api/v1/rfps/{hw_id}")
        assert detail.status_code == 200, detail.get_data(as_text=True)
        body = detail.get_json()
        rfp_item = body.get("item") or body
        lines_out = rfp_item.get("line_items") or rfp_item.get("lines") or []
        texts = " ".join(str(x.get("description") or "") for x in lines_out).lower()
        assert "closer" in texts or "4040xp" in texts
        assert "leaf" not in texts
        for ln in lines_out:
            snap = ln.get("product_snapshot") or {}
            assert "unit_cost" not in snap
            assert ln.get("unit_cost") in (None, 0, 0.0)
    finally:
        with flask_app.app_context():
            _cleanup_lead(eid)


def test_delete_set_lights_unknown_and_apply_block(client, flask_app):
    eid, est_id = _create_estimate(client, flask_app)
    try:
        _seed_sets(client, est_id)
        created = client.post(f"/api/v1/estimates/{est_id}/openings", json=_opening("101"))
        assert created.status_code == 201
        sets = client.get(f"/api/v1/estimates/{est_id}/hardware-sets").get_json()["items"]
        set_08 = next(s for s in sets if s["set_no_normalized"] in ("08", "8"))
        client.delete(f"/api/v1/estimates/{est_id}/hardware-sets/{set_08['id']}")
        recon = client.get(f"/api/v1/estimates/{est_id}/openings/reconcile").get_json()["reconcile"]
        assert recon["unknown_set"] >= 1
        blocked = client.post(f"/api/v1/estimates/{est_id}/openings/apply", json={})
        assert blocked.status_code == 400
        df = client.post(f"/api/v1/estimates/{est_id}/openings/apply", json={"door_frame_only": True})
        assert df.status_code == 200, df.get_data(as_text=True)
    finally:
        with flask_app.app_context():
            _cleanup_lead(eid)


def test_extract_confirm_and_refuse(client, flask_app):
    eid, est_id = _create_estimate(client, flask_app)
    try:
        tsv = "mark\twidth_in\theight_in\thardware_set_no\n601\t36\t84\t08\n"
        review = client.post(
            f"/api/v1/estimates/{est_id}/openings/extract",
            json={"mode": "door_schedule_extract", "tsv": tsv},
        )
        assert review.status_code == 200
        assert review.get_json()["committed"] is False
        assert review.get_json()["openings"]
        refuse = client.post(
            f"/api/v1/estimates/{est_id}/openings/extract/confirm",
            json={"mode": "door_schedule_extract", "tsv": tsv, "confirm": False},
        )
        assert refuse.status_code == 200
        assert refuse.get_json()["committed"] is False
        listed = client.get(f"/api/v1/estimates/{est_id}/openings").get_json()
        assert listed["openings"] == []
        ok = client.post(
            f"/api/v1/estimates/{est_id}/openings/extract/confirm",
            json={"mode": "door_schedule_extract", "tsv": tsv, "confirm": True},
        )
        assert ok.status_code == 200
        assert ok.get_json()["committed"] is True
        assert any(o["mark"] == "601" for o in ok.get_json()["openings"])
    finally:
        with flask_app.app_context():
            _cleanup_lead(eid)


def test_unconfirmed_extract_blocks_apply(client, flask_app):
    eid, est_id = _create_estimate(client, flask_app)
    try:
        r = client.post(
            f"/api/v1/estimates/{est_id}/openings",
            json=_opening("701", source="ai_schedule", confirmed_at=None, hardware_set_no=""),
        )
        assert r.status_code == 201
        with flask_app.app_context():
            from app.models.door_opening import DoorOpening

            op = db.session.get(DoorOpening, uuid.UUID(r.get_json()["item"]["id"]))
            op.confirmed_at = None
            op.source = "ai_schedule"
            db.session.commit()
        recon = client.get(f"/api/v1/estimates/{est_id}/openings/reconcile").get_json()["reconcile"]
        assert recon["unconfirmed"] >= 1
        blocked = client.post(f"/api/v1/estimates/{est_id}/openings/apply", json={"door_frame_only": True})
        assert blocked.status_code == 400
        client.post(f"/api/v1/estimates/{est_id}/openings/{r.get_json()['item']['id']}/confirm")
        ok = client.post(f"/api/v1/estimates/{est_id}/openings/apply", json={"door_frame_only": True})
        assert ok.status_code == 200, ok.get_data(as_text=True)
    finally:
        with flask_app.app_context():
            _cleanup_lead(eid)
