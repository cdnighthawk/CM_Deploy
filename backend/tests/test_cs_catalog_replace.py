"""Replace Construction Specialties (or a test manufacturer) without wiping other vendors."""
from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import OperationalError

from app.extensions import db
from app.models.material_pricing import MaterialPrice
from scripts.load_material_pricing import replace_manufacturer_rows


def _db_available(flask_app) -> bool:
    with flask_app.app_context():
        try:
            db.session.execute(text("SELECT 1"))
            return True
        except OperationalError:
            db.session.rollback()
            return False


def test_replace_manufacturer_copies_labor_and_keeps_other_vendors(client):
    if not _db_available(client.application):
        pytest.skip("PostgreSQL is not available for catalog replace tests")
    token = uuid.uuid4().hex[:8]
    mfr = f"USIS-CS-Replace-{token}"
    bob_item = f"B-{token}"
    with client.application.app_context():
        keep = MaterialPrice(
            manufacturer="Bobrick",
            item=bob_item,
            category="Grab Bar",
            labor_per=Decimal("0.25"),
            cost=Decimal("45"),
        )
        matched = MaterialPrice(
            manufacturer=mfr,
            item="BG-10",
            category="Bumper",
            labor_per=Decimal("1.50"),
            cost=Decimal("99"),
        )
        leftover = MaterialPrice(
            manufacturer=mfr,
            item="OLD-GONE",
            category="Rail",
            labor_per=Decimal("9"),
        )
        db.session.add_all([keep, matched, leftover])
        db.session.commit()
        bob_id = keep.id
        matched_id = matched.id
        leftover_id = leftover.id

        payloads = [
            {
                "manufacturer": mfr,
                "item": "CS-BG-10",
                "category": "Bumper Guard",
                "csi_spec_section": "102600",
                "description": "Acrovyn Bumper Guard BG-10",
                "mounting_type": "Bumper-Mounted",
                "cost": None,
                "labor_per": None,
                "currency": "USD",
                "unit_of_measure": "EA",
            },
            {
                "manufacturer": mfr,
                "item": "CS-SCR-48",
                "category": "Crash Rail",
                "csi_spec_section": "102600",
                "description": "new crash rail",
                "mounting_type": None,
                "cost": None,
                "labor_per": None,
                "currency": "USD",
                "unit_of_measure": "EA",
            },
        ]
        plan = replace_manufacturer_rows(db, MaterialPrice, payloads, mfr)
        assert plan.updated_count == 1
        assert plan.inserted_count == 1
        assert plan.deleted_count == 1
        assert plan.labor_copied == 1

        bob = db.session.get(MaterialPrice, bob_id)
        assert bob is not None
        assert bob.labor_per == Decimal("0.25")
        assert bob.item == bob_item

        updated = db.session.get(MaterialPrice, matched_id)
        assert updated is not None
        assert updated.item == "CS-BG-10"
        assert updated.labor_per == Decimal("1.50")
        assert updated.cost is None
        assert updated.category == "Bumper Guard"

        assert db.session.get(MaterialPrice, leftover_id) is None
        inserted = db.session.scalar(
            select(MaterialPrice).where(
                MaterialPrice.manufacturer == mfr,
                MaterialPrice.item == "CS-SCR-48",
            )
        )
        assert inserted is not None
        assert inserted.labor_per is None

        for row in db.session.scalars(select(MaterialPrice).where(MaterialPrice.manufacturer == mfr)):
            db.session.delete(row)
        leftover_bob = db.session.get(MaterialPrice, bob_id)
        if leftover_bob is not None and leftover_bob.item == bob_item:
            db.session.delete(leftover_bob)
        db.session.commit()
