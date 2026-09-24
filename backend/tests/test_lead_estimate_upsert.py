"""BuildingConnected lead upsert must keep Hub estimate links and tenant key."""
from __future__ import annotations

import uuid

from sqlalchemy import select

from app.extensions import db
from app.lead_estimate_csv_load import upsert_lead_estimate_norm_rows
from app.models.lead_estimate import LeadEstimate
from app.tenancy import default_organization_id


def test_bc_upsert_preserves_estimate_link_and_crm_stage(flask_app):
    eid = "bc-upsert-" + uuid.uuid4().hex[:12]
    estimate_id = uuid.uuid4()
    try:
        with flask_app.app_context():
            org_id = default_organization_id()
            assert org_id is not None
            first = upsert_lead_estimate_norm_rows(
                db.session,
                [
                    {
                        "id": eid,
                        "name": "Original BC name",
                        "submissionState": "UNDECIDED",
                        "source": "buildingconnected",
                    }
                ],
                organization_id=org_id,
            )
            assert first[0] == 1
            row = db.session.scalar(select(LeadEstimate).where(LeadEstimate.external_id == eid))
            assert row is not None
            row.primary_estimate_id = estimate_id
            row.crm_stage = "Estimating"
            db.session.commit()

            second = upsert_lead_estimate_norm_rows(
                db.session,
                [
                    {
                        "id": eid,
                        "name": "Updated from BuildingConnected",
                        "submissionState": "WILL_SUBMIT",
                        "source": "buildingconnected",
                    }
                ],
                organization_id=org_id,
            )
            assert second[0] == 1
            db.session.expire_all()
            row = db.session.scalar(select(LeadEstimate).where(LeadEstimate.external_id == eid))
            assert row is not None
            assert row.name == "Updated from BuildingConnected"
            assert (row.submission_state or "").upper() == "WILL_SUBMIT"
            assert row.primary_estimate_id == estimate_id
            assert row.crm_stage == "Estimating"
            assert row.organization_id == org_id
            assert row.source == "buildingconnected"
    finally:
        with flask_app.app_context():
            row = db.session.scalar(select(LeadEstimate).where(LeadEstimate.external_id == eid))
            if row is not None:
                db.session.delete(row)
                db.session.commit()
