"""Desktop queue payload shape — no database required."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

from app.api._serializers import desktop_queue_item
from app.integrations.ms_entra_oidc import claims_email, graph_email


def test_desktop_queue_item_maps_cloud_estimate_fields():
    due = datetime(2026, 8, 30, 17, 0, tzinfo=timezone.utc)
    row = SimpleNamespace(
        id="bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
        name="Wheeler",
        number="26-101",
        trade_name="Signage",
        submission_state="WILL_SUBMIT",
        due_at=due,
        location={"city": "Boise", "state": "ID", "zip": "83702", "complete": "100 Main"},
        client={"company": {"name": "Hoffman"}},
        workflow_bucket="WILL_SUBMIT",
        is_parent=True,
        external_parent_id=None,
        is_archived=False,
        primary_estimate_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        estimate_approved_at=None,
        final_value=Decimal("1250.50"),
    )
    item = desktop_queue_item(row)
    assert item["leadEstimateId"] == "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
    assert item["name"] == "Wheeler"
    assert item["tradeName"] == "Signage"
    assert item["city"] == "Boise"
    assert item["siteZip"] == "83702"
    assert item["gcName"] == "Hoffman"
    assert item["workflowBucket"] == "WILL_SUBMIT"
    assert item["isParent"] is True
    assert item["cloudEstimateId"] == "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    assert item["total"] == 1250.5


def test_claims_email_prefers_work_account():
    assert claims_email({"preferred_username": "rodrigo@gousis.com"}) == "rodrigo@gousis.com"


def test_client_company_includes_office():
    from app.api._serializers import client_company_name
    from app.api.v1 import _client_contact_line

    client = {
        "company": {"name": "Erickson-Hall Construction Co."},
        "office": {"name": "Escondido"},
        "lead": {
            "firstName": "Michael",
            "lastName": "Budd",
            "email": "mbudd@ericksonhall.com",
            "phoneNumber": "+1 760-796-7700",
        },
    }
    assert client_company_name(client) == "Erickson-Hall Construction Co. - Escondido"
    assert _client_contact_line(client) == "Michael Budd | +1 760-796-7700 | mbudd@ericksonhall.com"
    assert graph_email({"mail": None, "userPrincipalName": "Rodrigo@gousis.com"}) == "rodrigo@gousis.com"
