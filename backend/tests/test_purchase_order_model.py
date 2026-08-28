"""PO shipment/receipt tables register; ship-date helpers follow the brief."""
from datetime import date, timedelta


def test_purchase_order_tables_in_metadata(flask_app):
    from app.extensions import db

    names = db.metadata.tables.keys()
    assert "commitments" in names
    assert "commitment_line_items" in names
    assert "purchase_order_shipments" in names
    assert "purchase_order_shipment_lines" in names
    assert "purchase_order_receipts" in names
    assert "purchase_order_receipt_lines" in names
    assert "vendor_invoices" in names


def test_commitment_ship_date_helpers():
    from app.models import Commitment

    po = Commitment(
        title="Doors",
        commitment_kind="purchase_order",
        promised_ship_date=date(2026, 8, 20),
        revised_ship_date=date(2026, 8, 25),
        needed_on_site_date=date(2026, 8, 22),
    )
    assert po.ship_date == date(2026, 8, 25)
    assert po.late_vs_job is True
    assert po.missed_ship_date is True

    po.actual_ship_date = date(2026, 8, 24)
    assert po.missed_ship_date is False

    po.revised_ship_date = None
    assert po.ship_date == date(2026, 8, 20)
    assert po.late_vs_job is False


def test_commitment_not_late_when_dates_missing():
    from app.models import Commitment

    po = Commitment(title="Hardware", commitment_kind="purchase_order")
    assert po.ship_date is None
    assert po.missed_ship_date is False
    assert po.late_vs_job is False

    po.promised_ship_date = date.today() + timedelta(days=3)
    assert po.missed_ship_date is False
