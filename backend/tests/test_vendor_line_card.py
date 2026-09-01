"""Vendor line cards: manufacturer vs distributor, spec coverage, brand matching."""
from __future__ import annotations

import secrets
import uuid

import pytest
from sqlalchemy import select

from app.api._vendor_line_card import csi_covers, match_line_card
from app.extensions import db
from app.models import Company, Project, Rfp, RfpLineItem, Role, User, UserRole


@pytest.fixture
def no_dev_admin(monkeypatch):
    monkeypatch.setenv("USIS_API_DEV_ALLOW_ANY", "0")


def _staff(client):
    with client.application.app_context():
        role = db.session.scalar(select(Role).where(Role.code == "standard"))
        if role is None:
            role = Role(code="standard", name="Standard")
            db.session.add(role)
            db.session.flush()
        u = User(email="vlc_" + uuid.uuid4().hex[:8] + "@t.com", first_name="Line", last_name="Card")
        db.session.add(u)
        db.session.flush()
        db.session.add(UserRole(user_id=u.id, role_id=role.id))
        db.session.commit()
        return {"uid": str(u.id), "hdr": {"X-Usis-User-Id": str(u.id)}}


def test_csi_covers_parent_and_child():
    assert csi_covers("102100", "102113")
    assert csi_covers("102113", "102100")
    assert csi_covers("102800", "102800")
    assert not csi_covers("102800", "102600")
    assert not csi_covers("102100", "102800")


def test_match_bobrick_not_scranton():
    cards = [("102100", "Bobrick"), ("102100", "ASI"), ("102800", "")]
    channels = {"102100": "distributor", "102800": "distributor", "102600": "manufacturer"}
    bobrick = match_line_card(
        supply_role="distributor",
        cards=cards,
        needs=[{"csi": "102100", "manufacturer": "Bobrick"}],
        channels=channels,
    )
    scranton = match_line_card(
        supply_role="distributor",
        cards=cards,
        needs=[{"csi": "102113", "manufacturer": "Scranton"}],
        channels=channels,
    )
    wall = match_line_card(
        supply_role="distributor",
        cards=cards,
        needs=[{"csi": "102600", "manufacturer": "Inpro"}],
        channels=channels,
    )
    assert bobrick["matched"] is True
    assert scranton["matched"] is False
    assert wall["matched"] is False


def test_match_manufacturer_direct_buy():
    cards = [("102600", "Inpro")]
    channels = {"102600": "manufacturer", "102800": "distributor"}
    ok = match_line_card(
        supply_role="manufacturer",
        cards=cards,
        needs=[{"csi": "102600", "manufacturer": "Inpro"}],
        channels=channels,
    )
    accessories = match_line_card(
        supply_role="manufacturer",
        cards=cards,
        needs=[{"csi": "102800", "manufacturer": "Bobrick"}],
        channels=channels,
    )
    assert ok["matched"] is True
    assert accessories["matched"] is False


def test_line_card_api_and_rfp_suggestions(client, no_dev_admin):
    ctx = _staff(client)
    hdr = ctx["hdr"]

    dist = client.post(
        "/api/v1/companies",
        headers=hdr,
        json={
            "name": "US Interior Supply " + uuid.uuid4().hex[:6],
            "company_type": "vendor",
            "supply_role": "distributor",
            "email": "quotes.uis+" + uuid.uuid4().hex[:6] + "@example.com",
        },
    )
    assert dist.status_code == 201, dist.get_data(as_text=True)
    did = dist.get_json()["item"]["id"]
    assert dist.get_json()["item"]["supply_role"] == "distributor"

    mfr = client.post(
        "/api/v1/companies",
        headers=hdr,
        json={
            "name": "Inpro " + uuid.uuid4().hex[:6],
            "company_type": "vendor",
            "supply_role": "manufacturer",
            "email": "quotes.inpro+" + uuid.uuid4().hex[:6] + "@example.com",
        },
    )
    assert mfr.status_code == 201, mfr.get_data(as_text=True)
    mid = mfr.get_json()["item"]["id"]

    add = client.post(
        f"/api/v1/companies/{did}/line-card",
        headers=hdr,
        json={"csi_spec_section": "10 21 00", "manufacturers": ["Bobrick", "ASI"]},
    )
    assert add.status_code == 201, add.get_data(as_text=True)
    specs = add.get_json()["specs"]
    assert any(s["csi_spec_section"] == "102100" for s in specs)
    brands = {row["manufacturer"] for spec in specs for row in spec["manufacturers"]}
    assert brands == {"Bobrick", "ASI"}

    acc = client.post(
        f"/api/v1/companies/{did}/line-card",
        headers=hdr,
        json={"csi_spec_section": "10 28 00"},
    )
    assert acc.status_code == 201, acc.get_data(as_text=True)

    listed = client.get(f"/api/v1/companies/{did}/line-card", headers=hdr)
    assert listed.status_code == 200, listed.get_data(as_text=True)
    listed_csis = {s["csi_spec_section"] for s in listed.get_json()["specs"]}
    assert listed_csis == {"102100", "102800"}

    wall = client.post(
        f"/api/v1/companies/{mid}/line-card",
        headers=hdr,
        json={"csi_spec_section": "10 26 00", "manufacturer": "Inpro"},
    )
    assert wall.status_code == 201, wall.get_data(as_text=True)

    channels = client.get("/api/v1/csi-buy-channels", headers=hdr)
    assert channels.status_code == 200
    by_csi = {i["csi_spec_section"]: i["buy_from"] for i in channels.get_json()["items"]}
    assert by_csi.get("102600") == "manufacturer"
    assert by_csi.get("102800") == "distributor"

    with client.application.app_context():
        p = Project(name="VLC-" + uuid.uuid4().hex[:8])
        db.session.add(p)
        db.session.flush()
        rfp = Rfp(project_id=p.id, title="Partitions", public_token=secrets.token_urlsafe(16)[:32], status="Draft")
        db.session.add(rfp)
        db.session.flush()
        db.session.add(
            RfpLineItem(
                rfp_id=rfp.id,
                description="Toilet compartments",
                csi_division="10 21 13",
                product_snapshot={"manufacturer": "Bobrick"},
            )
        )
        db.session.commit()
        rid = str(rfp.id)
        pid = str(p.id)

    sug = client.get(f"/api/v1/rfps/{rid}/vendors?suggested=1", headers=hdr)
    assert sug.status_code == 200, sug.get_data(as_text=True)
    names = [i["name"] for i in sug.get_json()["items"]]
    assert any(i["id"] == did and i["matched"] for i in sug.get_json()["items"]), names
    assert all(i["id"] != mid for i in sug.get_json()["items"])

    with client.application.app_context():
        line = db.session.scalar(select(RfpLineItem).where(RfpLineItem.rfp_id == uuid.UUID(rid)))
        line.product_snapshot = {"manufacturer": "Scranton"}
        db.session.commit()

    sug2 = client.get(f"/api/v1/rfps/{rid}/vendors?suggested=1", headers=hdr)
    assert sug2.status_code == 200
    assert all(i["id"] != did for i in sug2.get_json()["items"])

    with client.application.app_context():
        rfp2 = Rfp(
            project_id=uuid.UUID(pid),
            title="Wall protection",
            public_token=secrets.token_urlsafe(16)[:32],
            status="Draft",
        )
        db.session.add(rfp2)
        db.session.flush()
        db.session.add(
            RfpLineItem(
                rfp_id=rfp2.id,
                description="Corner guards",
                csi_division="10 26 00",
                product_snapshot={"manufacturer": "Inpro"},
            )
        )
        db.session.commit()
        rid2 = str(rfp2.id)

    sug3 = client.get(f"/api/v1/rfps/{rid2}/vendors?suggested=1", headers=hdr)
    assert sug3.status_code == 200
    ids = [i["id"] for i in sug3.get_json()["items"]]
    assert mid in ids
    assert did not in ids

    gone = client.delete(f"/api/v1/companies/{did}/line-card/specs/102100", headers=hdr)
    assert gone.status_code == 200
    left = {s["csi_spec_section"] for s in gone.get_json()["specs"]}
    assert "102100" not in left
    assert "102800" in left
