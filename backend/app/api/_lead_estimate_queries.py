"""Lead estimate list filters (shared by REST and AI tools)."""
from __future__ import annotations

from typing import Any

from sqlalchemy import String, and_, cast, func, literal, or_

from ..models import LeadEstimate


def submission_state_norm_sql():
    co = func.trim(func.coalesce(LeadEstimate.submission_state, literal("")))
    return func.replace(func.replace(func.lower(co), "_", ""), "-", "")


def submission_state_norm_param(submission_state: str) -> str:
    return (submission_state or "").strip().lower().replace("_", "").replace("-", "")


def _not_archived_or_declined() -> Any:
    """Leads/Estimates boards never list Bid Board archived or declined invitations."""
    bucket = func.upper(func.coalesce(LeadEstimate.workflow_bucket, literal("")))
    return and_(
        LeadEstimate.is_archived.is_(False),
        ~bucket.like("%ARCHIVED%"),
        ~bucket.like("%DECLINED%"),
        submission_state_norm_sql() != literal("declined"),
    )


def _not_grouped_child() -> Any:
    """Bid Board's active list is parents and standalones, not grouped child trades."""
    bucket = func.upper(func.coalesce(LeadEstimate.workflow_bucket, literal("")))
    not_child_bucket = ~bucket.like("%CHILD%")
    standalone_or_parent = or_(
        LeadEstimate.is_parent.is_(True),
        LeadEstimate.external_parent_id.is_(None),
        func.trim(func.coalesce(LeadEstimate.external_parent_id, literal(""))) == literal(""),
    )
    return and_(not_child_bucket, standalone_or_parent)


def _has_open_due_date() -> Any:
    """Bid Board's current board is still-due work, not expired or undated invitations."""
    return and_(LeadEstimate.due_at.isnot(None), LeadEstimate.due_at >= func.now())


def _has_assignee() -> Any:
    """Bid Board's visible Undecided rows are assigned; follower-only invites stay off the board."""
    return func.upper(func.coalesce(cast(LeadEstimate.members, String), literal(""))).like("%ASSIGNEE%")


def _explicit_state_ok(norm_sql, norms: list[str]) -> Any:
    clauses: list[Any] = [norm_sql == literal(n) for n in norms if n]
    if not clauses:
        raise ValueError("submission_state has no valid tokens")
    return or_(*clauses) if len(clauses) > 1 else clauses[0]


def lead_estimates_ui_filter(submission_state: str) -> Any:
    st_in = (submission_state or "").strip()
    if not st_in:
        raise ValueError("submission_state cannot be empty")
    board_ok = and_(_not_archived_or_declined(), _not_grouped_child())
    norm_sql = submission_state_norm_sql()
    norms = [submission_state_norm_param(p) for p in st_in.split(",") if p.strip()]
    state_ok = _explicit_state_ok(norm_sql, norms)

    if len(norms) == 1 and norms[0] == "undecided":
        return and_(state_ok, board_ok, _has_open_due_date(), _has_assignee())
    return and_(state_ok, board_ok)
