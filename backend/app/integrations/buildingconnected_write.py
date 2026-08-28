"""Helpers for BuildingConnected opportunity write-back (submissionState / outcome)."""
from __future__ import annotations

from typing import Any

WRITABLE_SUBMISSION_STATES = ("UNDECIDED", "WILL_SUBMIT", "DECLINED")
WRITABLE_OUTCOME_STATES = ("UNKNOWN", "WON", "LOST", "OTHER")
OUTCOME_OTHER_REASONS = ("CANCELED", "REBID", "CLIENT_NOT_AWARDED", "OTHER")
DECLINE_REASONS = (
    "LOCATION",
    "TRADE",
    "CLIENT",
    "UNION_STATUS",
    "PREVAILING_WAGE_STATUS",
    "BID_DUE_DATE",
    "MISSING_INFO",
    "PROJECT_SIZE",
    "MARKET_SECTOR",
    "TOO_BUSY",
    "OTHER",
)


def normalize_enum(value: Any) -> str | None:
    if value is None or value == "":
        return None
    return str(value).strip().upper()


def is_bc_write_enabled(config: dict[str, Any] | None = None, *, flask_env: str | None = None) -> bool:
    raw = ""
    if config:
        raw = str(config.get("BC_WRITE_ENABLED") or "").strip().lower()
    if raw in ("1", "true", "yes", "on"):
        return True
    if raw in ("0", "false", "no", "off"):
        return False
    env = (flask_env or "").strip().lower()
    return env != "production"


def get_submission_change_block_reason(
    *,
    external_id: str | None,
    submission_state: str | None,
    is_archived: bool | None,
    outcome_state: str | None = None,
) -> str | None:
    if not (external_id or "").strip():
        return "This lead is not linked to a BuildingConnected opportunity."
    if is_archived is True:
        return "Archived opportunities cannot be updated from here."
    if normalize_enum(submission_state) == "SUBMITTED":
        return "Already submitted. BuildingConnected status cannot be changed from here."
    outcome = normalize_enum(outcome_state)
    if outcome in ("WON", "LOST"):
        return f"Opportunity outcome is {outcome}; submission state is no longer changeable."
    return None


def build_opportunity_patch_body(data: dict[str, Any]) -> dict[str, Any]:
    patch: dict[str, Any] = {}
    if "submissionState" in data or "submission_state" in data:
        raw = data.get("submissionState", data.get("submission_state"))
        state = normalize_enum(raw)
        if not state:
            raise ValueError("submissionState is required")
        if state == "SUBMITTED":
            raise ValueError(
                "BuildingConnected does not allow setting submissionState to SUBMITTED via API. "
                "Use UNDECIDED, WILL_SUBMIT, or DECLINED."
            )
        if state not in WRITABLE_SUBMISSION_STATES:
            raise ValueError(
                f'Unsupported submissionState "{raw}". Use UNDECIDED, WILL_SUBMIT, or DECLINED.'
            )
        patch["submissionState"] = state

    reasons = data.get("declineReasons", data.get("decline_reasons"))
    note = data.get("note")
    if reasons is not None:
        if not isinstance(reasons, list):
            raise ValueError("declineReasons must be an array of strings")
        normalized = [normalize_enum(r) for r in reasons if normalize_enum(r)]
        unknown = next((r for r in normalized if r not in DECLINE_REASONS), None)
        if unknown:
            raise ValueError(f'Unsupported declineReason "{unknown}"')
        if normalized and patch.get("submissionState") not in (None, "DECLINED"):
            raise ValueError("declineReasons can only be set when submissionState is DECLINED")
        if normalized:
            patch["declineReasons"] = normalized
    elif patch.get("submissionState") == "DECLINED" and isinstance(note, str) and note.strip():
        patch["declineReasons"] = ["OTHER"]

    outcome = data.get("outcome")
    if outcome is not None:
        if not isinstance(outcome, dict):
            raise ValueError("outcome must be an object")
        ostate = normalize_enum(outcome.get("state"))
        if not ostate:
            raise ValueError("outcome.state is required when outcome is provided")
        if ostate not in WRITABLE_OUTCOME_STATES:
            raise ValueError(
                f'Unsupported outcome.state "{outcome.get("state")}". Use UNKNOWN, WON, LOST, or OTHER.'
            )
        out: dict[str, Any] = {"state": ostate}
        if ostate == "OTHER":
            other = normalize_enum(outcome.get("otherReason") or outcome.get("other_reason")) or "OTHER"
            if other not in OUTCOME_OTHER_REASONS:
                raise ValueError(
                    f'Unsupported outcome.otherReason "{outcome.get("otherReason")}". '
                    "Use CANCELED, REBID, CLIENT_NOT_AWARDED, or OTHER."
                )
            out["otherReason"] = other
        patch["outcome"] = out

    if "submissionState" not in patch and "outcome" not in patch:
        raise ValueError("Provide submissionState and/or outcome to update BuildingConnected")
    return patch


def message_for_bc_http_error(status: int, body: Any, action: str = "BuildingConnected request") -> str:
    hint = ""
    if isinstance(body, dict):
        hint = str(
            body.get("detail")
            or body.get("title")
            or body.get("message")
            or body.get("developerMessage")
            or body.get("error_description")
            or (body.get("error") if isinstance(body.get("error"), str) else "")
            or ""
        )
    blob = f"{hint} {body!s}"
    if status == 401:
        return "BuildingConnected authorization expired or is invalid. Reconnect BuildingConnected."
    if status == 403:
        if (
            "scope" in blob.lower()
            or "data:write" in blob.lower()
            or "privilege" in blob.lower()
            or "auth-010" in blob.lower()
        ):
            return (
                "BuildingConnected write is not authorized on this connection. "
                "In Autodesk APS the app needs data:write, then Reconnect BC while signed in "
                "as a Bid Board Pro user who can change bid status."
            )
        if "bid board" in blob.lower() or "subscription" in blob.lower() or "pro" in blob.lower():
            return "BuildingConnected denied this update. Confirm the office has Bid Board Pro."
        return hint or (
            "BuildingConnected denied this update (403). Confirm Autodesk granted API access "
            "and the office has Bid Board Pro."
        )
    if status == 404:
        return "That BuildingConnected opportunity was not found."
    if status == 429:
        return "BuildingConnected rate-limited the request. Try again in a moment."
    if hint:
        return f"{action} failed ({status}): {hint}"
    return f"{action} failed ({status})."


def apply_opportunity_to_lead(row: Any, opportunity: dict[str, Any]) -> None:
    """Copy writable BC fields onto an existing LeadEstimate without wiping CRM fields."""
    if opportunity.get("submissionState") is not None:
        row.submission_state = str(opportunity.get("submissionState"))
    if opportunity.get("workflowBucket") is not None:
        row.workflow_bucket = str(opportunity.get("workflowBucket"))
    if "isArchived" in opportunity:
        row.is_archived = bool(opportunity.get("isArchived"))
    if "outcome" in opportunity:
        row.outcome = opportunity.get("outcome")
    if "declineReasons" in opportunity:
        row.decline_reasons = opportunity.get("declineReasons")
    if "isParent" in opportunity:
        row.is_parent = bool(opportunity.get("isParent"))
    if opportunity.get("parentId") is not None:
        row.external_parent_id = str(opportunity.get("parentId"))
    raw = dict(row.raw_row) if isinstance(row.raw_row, dict) else {}
    raw.update(opportunity)
    row.raw_row = raw
