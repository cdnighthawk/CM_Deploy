"""Lead estimate list filters (shared by REST and AI tools)."""
from __future__ import annotations

from typing import Any

from sqlalchemy import and_, func, literal, or_

from ..models import LeadEstimate


def submission_state_norm_sql():
    co = func.trim(func.coalesce(LeadEstimate.submission_state, literal("")))
    return func.replace(func.replace(func.lower(co), "_", ""), "-", "")


def submission_state_norm_param(submission_state: str) -> str:
    return (submission_state or "").strip().lower().replace("_", "").replace("-", "")


def lead_estimates_ui_filter(submission_state: str) -> Any:
    st_in = (submission_state or "").strip()
    if not st_in:
        raise ValueError("submission_state cannot be empty")
    not_archived = or_(LeadEstimate.is_archived.is_(False), LeadEstimate.is_archived.is_(None))
    norm_sql = submission_state_norm_sql()

    parts = [p.strip() for p in st_in.split(",") if p.strip()]
    norms = [submission_state_norm_param(p) for p in parts]

    if len(norms) == 1 and norms[0] == "undecided":
        empty_or_ws = func.trim(func.coalesce(LeadEstimate.submission_state, literal(""))) == literal("")
        state_ok = or_(empty_or_ws, norm_sql == literal("undecided"))
        return and_(state_ok, not_archived)

    empty_or_ws = func.trim(func.coalesce(LeadEstimate.submission_state, literal(""))) == literal("")
    clauses: list[Any] = []
    for n in norms:
        if not n:
            continue
        if n == "undecided":
            clauses.append(or_(empty_or_ws, norm_sql == literal("undecided")))
        else:
            clauses.append(norm_sql == literal(n))
    if not clauses:
        raise ValueError("submission_state has no valid tokens")
    state_ok = or_(*clauses) if len(clauses) > 1 else clauses[0]
    return and_(state_ok, not_archived)
