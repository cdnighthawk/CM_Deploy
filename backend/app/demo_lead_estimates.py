"""Canonical demo ``lead_estimates`` rows for local dev (keyed by ``external_id``)."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models.lead_estimate import LeadEstimate

_DEMO_ATTRS = (
    "name",
    "number",
    "trade_name",
    "submission_state",
    "source",
    "workflow_bucket",
    "client",
    "location",
    "project_information",
    "trade_specific_instructions",
)


def _demo_rows() -> list[LeadEstimate]:
    # submission_state None/blank => ``submission_state=undecided`` on the Leads page API.
    # Estimates page loads ``undecided,will_submit,submitted`` so the same rows appear there too.
    return [
        LeadEstimate(
            external_id="usis-seed-demo-bc-1",
            name="Sample project – West Campus",
            number="SAMPLE-BC-1001",
            trade_name="Concrete",
            submission_state=None,
            source="BUILDING_CONNECTED",
            workflow_bucket="Active",
            project_information="Sample job for local dev. Click the project # or lead name on Leads / Estimate to open lead detail.",
            trade_specific_instructions="Include alternate for fly ash mix. Coordinate pour dates with GC superintendent.",
            client={"company": {"name": "Demo General Contractors Inc."}},
            location={"city": "Los Angeles", "state": "CA"},
        ),
        LeadEstimate(
            external_id="usis-seed-demo-corecon-1",
            name="Sample project – CORECON active job",
            number="SAMPLE-CC-2002",
            trade_name="Electrical",
            submission_state=None,
            source="CORECON",
            workflow_bucket="Bid",
            client={"company": {"name": "Demo Subcontractor LLC"}},
            location={"city": "San Diego", "state": "CA"},
        ),
        LeadEstimate(
            external_id="usis-seed-demo-bc-2",
            name="Sample project – East Lot",
            number="SAMPLE-BC-1003",
            trade_name="Steel",
            submission_state=None,
            source="BUILDING_CONNECTED",
            client={"company": {"name": "Another Demo Client"}},
            location={"city": "Phoenix", "state": "AZ"},
        ),
    ]


def upsert_demo_lead_estimates(sess: Session, *, force: bool = False) -> int:
    """Insert or update canonical demo rows (keyed by ``external_id``).

    ``force`` is kept for CLI compatibility; behavior is always upsert-by-external_id for the
    three demo keys (safe alongside real CSV data).
    """
    _ = force  # CLI compatibility; upsert always runs for the three demo keys.
    demo_rows = _demo_rows()
    for row in demo_rows:
        hit = sess.scalar(select(LeadEstimate).where(LeadEstimate.external_id == row.external_id))
        if hit:
            for attr in _DEMO_ATTRS:
                setattr(hit, attr, getattr(row, attr))
        else:
            sess.add(row)
    return len(demo_rows)
