"""Leads list-query params + personal saved filters."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select

from app.extensions import db
from app.models import Company, CompanyOffice, LeadEstimate, SavedListFilter, User
from app.api._serializers import haversine_miles, location_coords


def _future():
    return datetime.now(tz=timezone.utc) + timedelta(days=21)


def _past():
    return datetime.now(tz=timezone.utc) - timedelta(days=7)


def _open_lead(**kwargs) -> LeadEstimate:
    defaults = dict(
        external_id="lf-" + uuid.uuid4().hex[:12],
        name="Open Bid",
        number="P-100",
        trade_name="Drywall",
        submission_state="UNDECIDED",
        is_archived=False,
        is_parent=True,
        due_at=_future(),
        crm_stage="New Lead",
        market_sector="Commercial",
        final_value=Decimal("250000.00"),
        client={"company": {"name": "Acme GC"}},
        location={"city": "Sacramento", "state": "CA"},
    )
    defaults.update(kwargs)
    return LeadEstimate(**defaults)


def _user(flask_app, email=None):
    with flask_app.app_context():
        u = User(
            email=email or f"lf_{uuid.uuid4().hex[:8]}@example.com",
            first_name="Lee",
            last_name="Filter",
            is_active=True,
            is_superuser=True,
        )
        db.session.add(u)
        db.session.commit()
        return str(u.id)


def test_lead_list_q_and_trade_and_sector(client, flask_app):
    with flask_app.app_context():
        keep = _open_lead(name="Capitol Drywall Fitout", trade_name="Drywall", market_sector="Commercial")
        drop = _open_lead(name="Paint Shop", trade_name="Paint", market_sector="Government")
        db.session.add_all([keep, drop])
        db.session.commit()
        kid, did = str(keep.id), str(drop.id)
    try:
        r = client.get("/api/v1/lead-estimates?limit=200&submission_state=undecided&q=Capitol&trade=drywall&sector=commercial")
        assert r.status_code == 200
        ids = {x["id"] for x in r.get_json()["items"]}
        assert kid in ids
        assert did not in ids
    finally:
        with flask_app.app_context():
            for eid in (kid, did):
                row = db.session.get(LeadEstimate, uuid.UUID(eid))
                if row:
                    db.session.delete(row)
            db.session.commit()


def test_lead_list_due_range_and_value(client, flask_app):
    with flask_app.app_context():
        soon = _open_lead(name="Soon due", due_at=datetime.now(tz=timezone.utc) + timedelta(days=5), final_value=Decimal("80000"))
        later = _open_lead(name="Later due", due_at=datetime.now(tz=timezone.utc) + timedelta(days=40), final_value=Decimal("900000"))
        db.session.add_all([soon, later])
        db.session.commit()
        sid, lid = str(soon.id), str(later.id)
    try:
        start = (datetime.now(tz=timezone.utc) + timedelta(days=1)).date().isoformat()
        end = (datetime.now(tz=timezone.utc) + timedelta(days=10)).date().isoformat()
        r = client.get(
            f"/api/v1/lead-estimates?limit=200&submission_state=undecided&due_from={start}&due_to={end}T23:59:59Z&value_min=10000&value_max=100000"
        )
        assert r.status_code == 200
        ids = {x["id"] for x in r.get_json()["items"]}
        assert sid in ids
        assert lid not in ids
    finally:
        with flask_app.app_context():
            for eid in (sid, lid):
                row = db.session.get(LeadEstimate, uuid.UUID(eid))
                if row:
                    db.session.delete(row)
            db.session.commit()


def test_lead_list_lost_stage_relaxes_default_hide(client, flask_app):
    with flask_app.app_context():
        lost = _open_lead(
            name="Lost job",
            crm_stage="Lost",
            due_at=_past(),
            is_archived=True,
        )
        open_row = _open_lead(name="Still open")
        db.session.add_all([lost, open_row])
        db.session.commit()
        lost_id, open_id = str(lost.id), str(open_row.id)
    try:
        default = client.get("/api/v1/lead-estimates?limit=200&submission_state=undecided")
        assert default.status_code == 200
        default_ids = {x["id"] for x in default.get_json()["items"]}
        assert lost_id not in default_ids

        filtered = client.get("/api/v1/lead-estimates?limit=200&submission_state=undecided&stage=lost")
        assert filtered.status_code == 200
        ids = {x["id"] for x in filtered.get_json()["items"]}
        assert lost_id in ids
        assert open_id not in ids
    finally:
        with flask_app.app_context():
            for eid in (lost_id, open_id):
                row = db.session.get(LeadEstimate, uuid.UUID(eid))
                if row:
                    db.session.delete(row)
            db.session.commit()


def test_submitted_list_includes_past_due(client, flask_app):
    marker = "SubList-" + uuid.uuid4().hex[:8]
    with flask_app.app_context():
        current = _open_lead(name=f"{marker} current", submission_state="SUBMITTED")
        past = _open_lead(name=f"{marker} past", submission_state="SUBMITTED", due_at=_past())
        will = _open_lead(name=f"{marker} estimating", submission_state="WILL_SUBMIT")
        db.session.add_all([current, past, will])
        db.session.commit()
        cid, pid, wid = str(current.id), str(past.id), str(will.id)
    try:
        r = client.get(
            f"/api/v1/lead-estimates?limit=200&submission_state=submitted&q={marker}"
        )
        assert r.status_code == 200
        ids = {x["id"] for x in r.get_json()["items"]}
        assert cid in ids
        assert pid in ids
        assert wid not in ids
    finally:
        with flask_app.app_context():
            for eid in (cid, pid, wid):
                row = db.session.get(LeadEstimate, uuid.UUID(eid))
                if row:
                    db.session.delete(row)
            db.session.commit()


def test_lead_list_company_id_matches_client_name(client, flask_app):
    with flask_app.app_context():
        co = Company(name="UniqueFilterGC XYZ", company_type="gc")
        db.session.add(co)
        db.session.flush()
        hit = _open_lead(name="Hit", client={"company": {"name": "UniqueFilterGC XYZ"}})
        miss = _open_lead(name="Miss", client={"company": {"name": "Other Builder"}})
        db.session.add_all([hit, miss])
        db.session.commit()
        cid, hid, mid = str(co.id), str(hit.id), str(miss.id)
    try:
        r = client.get(f"/api/v1/lead-estimates?limit=200&submission_state=undecided&company_id={cid}")
        assert r.status_code == 200
        ids = {x["id"] for x in r.get_json()["items"]}
        assert hid in ids
        assert mid not in ids
    finally:
        with flask_app.app_context():
            for eid in (hid, mid):
                row = db.session.get(LeadEstimate, uuid.UUID(eid))
                if row:
                    db.session.delete(row)
            co = db.session.get(Company, uuid.UUID(cid))
            if co:
                db.session.delete(co)
            db.session.commit()


def test_saved_filters_crud_and_default(client, flask_app):
    uid = _user(flask_app)
    hdr = {"X-Usis-User-Id": uid}
    r = client.get("/api/v1/saved-filters?table_key=crm.leads", headers=hdr)
    assert r.status_code == 200
    assert r.get_json()["items"] == []

    created = client.post(
        "/api/v1/saved-filters",
        headers=hdr,
        json={
            "table_key": "crm.leads",
            "name": "Due this month",
            "query_json": {"trade": "drywall", "sector": "commercial"},
            "is_default": True,
        },
    )
    assert created.status_code == 201, created.get_data(as_text=True)
    item = created.get_json()["item"]
    fid = item["id"]
    assert item["is_default"] is True
    assert item["query_json"]["trade"] == "drywall"

    second = client.post(
        "/api/v1/saved-filters",
        headers=hdr,
        json={
            "table_key": "crm.leads",
            "name": "Gov only",
            "query_json": {"sector": "government"},
            "is_default": True,
        },
    )
    assert second.status_code == 201
    sid = second.get_json()["item"]["id"]

    listed = client.get("/api/v1/saved-filters?table_key=crm.leads", headers=hdr)
    rows = listed.get_json()["items"]
    by_id = {x["id"]: x for x in rows}
    assert by_id[fid]["is_default"] is False
    assert by_id[sid]["is_default"] is True

    clash = client.post(
        "/api/v1/saved-filters",
        headers=hdr,
        json={"table_key": "crm.leads", "name": "Gov only", "query_json": {"q": "x"}},
    )
    assert clash.status_code == 409

    overwritten = client.post(
        "/api/v1/saved-filters",
        headers=hdr,
        json={"table_key": "crm.leads", "name": "Gov only", "query_json": {"q": "x"}, "overwrite": True},
    )
    assert overwritten.status_code == 201
    assert overwritten.get_json()["item"]["query_json"]["q"] == "x"

    patched = client.patch(
        f"/api/v1/saved-filters/{fid}",
        headers=hdr,
        json={"name": "Drywall commercial", "is_default": True},
    )
    assert patched.status_code == 200
    assert patched.get_json()["item"]["name"] == "Drywall commercial"

    deleted = client.delete(f"/api/v1/saved-filters/{fid}", headers=hdr)
    assert deleted.status_code == 200
    gone = client.get("/api/v1/saved-filters?table_key=crm.leads", headers=hdr)
    ids = {x["id"] for x in gone.get_json()["items"]}
    assert fid not in ids
    assert sid in ids

    other = _user(flask_app)
    sneak = client.get("/api/v1/saved-filters?table_key=crm.leads", headers={"X-Usis-User-Id": other})
    assert sneak.get_json()["items"] == []

    with flask_app.app_context():
        leftover = db.session.scalars(select(SavedListFilter).where(SavedListFilter.user_id == uuid.UUID(uid))).all()
        for row in leftover:
            db.session.delete(row)
        for u in (uid, other):
            user = db.session.get(User, uuid.UUID(u))
            if user:
                db.session.delete(user)
        db.session.commit()


def test_location_coords_and_haversine():
    assert location_coords({"coords": {"lat": 38.5816, "lng": -121.4944}}) == (38.5816, -121.4944)
    miles = haversine_miles((38.5816, -121.4944), (38.678, -121.176))
    assert 15 < miles < 30


def _sync_default_office_coords(company: Company) -> None:
    rows = list(
        db.session.scalars(select(CompanyOffice).where(CompanyOffice.company_id == company.id)).all()
    )
    if not rows:
        return
    default = next((o for o in rows if o.is_default), rows[0])
    for office in rows:
        office.is_default = office.id == default.id
        office.city = company.city
        office.state = company.state
        office.postal_code = company.postal_code
        office.latitude = company.latitude
        office.longitude = company.longitude


def _office_self(flask_app, **kwargs):
    with flask_app.app_context():
        row = db.session.scalar(
            select(Company)
            .where(Company.company_type == "self", Company.deleted_at.is_(None))
            .order_by(Company.created_at.asc())
            .limit(1)
        )
        created = False
        if row is None:
            row = Company(name="USIS Office Test", company_type="self", country="US")
            db.session.add(row)
            created = True
        snapshot = {
            "created": created,
            "id": None,
            "city": row.city,
            "state": row.state,
            "postal_code": row.postal_code,
            "latitude": row.latitude,
            "longitude": row.longitude,
        }
        for k, v in kwargs.items():
            setattr(row, k, v)
        db.session.flush()
        _sync_default_office_coords(row)
        db.session.commit()
        snapshot["id"] = str(row.id)
        return snapshot


def _restore_office(flask_app, snapshot):
    with flask_app.app_context():
        row = db.session.get(Company, uuid.UUID(snapshot["id"]))
        if row is None:
            return
        if snapshot["created"]:
            db.session.delete(row)
        else:
            row.city = snapshot["city"]
            row.state = snapshot["state"]
            row.postal_code = snapshot["postal_code"]
            row.latitude = snapshot["latitude"]
            row.longitude = snapshot["longitude"]
            _sync_default_office_coords(row)
        db.session.commit()


def test_lead_list_distance_from_office(client, flask_app):
    snap = _office_self(
        flask_app,
        city="Sacramento",
        state="CA",
        postal_code="95814",
        latitude=38.5816,
        longitude=-121.4944,
    )
    with flask_app.app_context():
        near = _open_lead(
            name="Near office",
            location={"city": "Folsom", "state": "CA", "coords": {"lat": 38.678, "lng": -121.176}},
        )
        far = _open_lead(
            name="Far job",
            location={"city": "Honolulu", "state": "HI", "coords": {"lat": 21.3074, "lng": -157.8613}},
        )
        no_geo = _open_lead(name="City only", location={"city": "Sacramento", "state": "CA"})
        db.session.add_all([near, far, no_geo])
        db.session.commit()
        nid, fid, xid = str(near.id), str(far.id), str(no_geo.id)
    try:
        office = client.get("/api/v1/office-location")
        assert office.status_code == 200
        body = office.get_json()
        assert body["configured"] is True
        assert body["city"] == "Sacramento"

        missing = client.get("/api/v1/lead-estimates?limit=200&submission_state=undecided&distance_miles=abc")
        assert missing.status_code == 400

        r = client.get("/api/v1/lead-estimates?limit=200&submission_state=undecided&distance_miles=50")
        assert r.status_code == 200
        payload = r.get_json()
        ids = {x["id"] for x in payload["items"]}
        assert nid in ids
        assert fid not in ids
        assert xid not in ids
        near_row = next(x for x in payload["items"] if x["id"] == nid)
        assert near_row["distance_miles"] is not None
        assert near_row["distance_miles"] < 50
        assert payload["office"]["latitude"] == 38.5816
    finally:
        with flask_app.app_context():
            for eid in (nid, fid, xid):
                row = db.session.get(LeadEstimate, uuid.UUID(eid))
                if row:
                    db.session.delete(row)
            db.session.commit()
        _restore_office(flask_app, snap)


def test_lead_list_distance_requires_office(client, flask_app, monkeypatch):
    snap = _office_self(flask_app, latitude=None, longitude=None, city=None, state=None, postal_code=None)
    try:
        r = client.get("/api/v1/lead-estimates?limit=200&submission_state=undecided&distance_miles=25")
        assert r.status_code == 400
        assert "office" in (r.get_json() or {}).get("error", "").lower()
    finally:
        _restore_office(flask_app, snap)


def test_patch_office_location_uses_geocode(client, flask_app, monkeypatch):
    monkeypatch.setattr(
        "app.api._office_location.geocode_us_address",
        lambda query: (33.1192, -117.0864),
    )
    snap = _office_self(flask_app, latitude=None, longitude=None, city=None, state=None, postal_code=None)
    try:
        r = client.patch(
            "/api/v1/office-location",
            json={"city": "Escondido", "state": "CA", "postal_code": "92025"},
        )
        assert r.status_code == 200, r.get_data(as_text=True)
        body = r.get_json()
        assert body["configured"] is True
        assert body["city"] == "Escondido"
        assert body["latitude"] == 33.1192
        assert body["longitude"] == -117.0864
    finally:
        _restore_office(flask_app, snap)


def test_saved_filters_reject_unknown_table(client, flask_app):
    uid = _user(flask_app)
    hdr = {"X-Usis-User-Id": uid}
    r = client.post(
        "/api/v1/saved-filters",
        headers=hdr,
        json={"table_key": "estimating.list", "name": "Nope", "query_json": {}},
    )
    assert r.status_code == 400
    with flask_app.app_context():
        user = db.session.get(User, uuid.UUID(uid))
        if user:
            db.session.delete(user)
            db.session.commit()
