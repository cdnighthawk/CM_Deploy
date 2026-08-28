"""Lead estimate list filters (shared by REST and AI tools)."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Mapping

from sqlalchemy import String, and_, cast, func, literal, or_

from ..models import Company, LeadEstimate

STAGE_ALIASES = {
    "new": "New Lead",
    "newlead": "New Lead",
    "new_lead": "New Lead",
    "invited": "Invited",
    "estimating": "Estimating",
    "submitted": "Submitted",
    "awarded": "Awarded",
    "lost": "Lost",
    "dead": "Lost",
}

CLOSED_STAGES = frozenset({"Awarded", "Lost"})

SECTOR_PATTERNS = {
    "commercial": ("%commercial%", "%private%"),
    "government": ("%government%", "%public%", "%federal%", "%state%", "%municipal%", "%city%"),
}


def _csv_tokens(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [p.strip() for p in str(raw).split(",") if p.strip()]


def _parse_iso_dt(raw: str | None, label: str) -> datetime | None:
    if not raw:
        return None
    text = str(raw).strip()
    if " " in text and "T" in text and text.count("-") >= 2:
        # Query strings turn "+00:00" into a space.
        text = text.replace(" ", "+", 1)
    if len(text) == 10 and text[4] == "-" and text[7] == "-":
        text = text + "T00:00:00"
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"invalid {label} (use ISO-8601)") from exc


def _parse_number(raw: str | None, label: str) -> float | None:
    if raw is None or str(raw).strip() == "":
        return None
    try:
        return float(str(raw).strip())
    except ValueError as exc:
        raise ValueError(f"invalid {label}") from exc


def _normalize_stage(token: str) -> str:
    key = token.strip().lower().replace(" ", "").replace("-", "_")
    if key in STAGE_ALIASES:
        return STAGE_ALIASES[key]
    for label in ("New Lead", "Invited", "Estimating", "Submitted", "Awarded", "Lost"):
        if token.strip().lower() == label.lower():
            return label
    return token.strip()


def _client_company_name_sql():
    return func.coalesce(
        LeadEstimate.client["company"]["name"].astext,
        LeadEstimate.client["name"].astext,
        literal(""),
    )


def _location_city_sql():
    return func.coalesce(LeadEstimate.location["city"].astext, literal(""))


def _location_state_sql():
    return func.coalesce(LeadEstimate.location["state"].astext, literal(""))


def _job_value_sql():
    return func.coalesce(LeadEstimate.final_value, LeadEstimate.rom)


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


def _explicit_state_ok(norm_sql, norms: list[str]) -> Any:
    clauses: list[Any] = [norm_sql == literal(n) for n in norms if n]
    if not clauses:
        raise ValueError("submission_state has no valid tokens")
    return or_(*clauses) if len(clauses) > 1 else clauses[0]


def active_estimate_queue_filter() -> Any:
    """Website Estimates board (will-submit, still due)."""
    return lead_estimates_ui_filter("will_submit")


def desktop_estimate_queue_filter() -> Any:
    """Desktop Estimating → Queue: current Bid Board work only.

    Client filters All / Will submit / Undecided / Submitted among still-due
    parents. Expired invitations stay off the live queue.
    """
    return and_(_not_archived_or_declined(), _not_grouped_child(), _has_open_due_date())


def lead_estimates_ui_filter(submission_state: str) -> Any:
    st_in = (submission_state or "").strip()
    if not st_in:
        raise ValueError("submission_state cannot be empty")
    board_ok = and_(_not_archived_or_declined(), _not_grouped_child())
    norm_sql = submission_state_norm_sql()
    norms = [submission_state_norm_param(p) for p in st_in.split(",") if p.strip()]
    state_ok = _explicit_state_ok(norm_sql, norms)

    if len(norms) == 1 and norms[0] in ("undecided", "willsubmit"):
        return and_(state_ok, board_ok, _has_open_due_date())
    return and_(state_ok, board_ok)


def lead_estimates_ui_filter_relaxed(submission_state: str, *, include_closed: bool, skip_open_due: bool) -> Any:
    """Same as ``lead_estimates_ui_filter`` but can keep Lost/past-due rows when the drawer asks."""
    st_in = (submission_state or "").strip()
    if not st_in:
        raise ValueError("submission_state cannot be empty")
    if include_closed:
        board_ok = _not_grouped_child()
    else:
        board_ok = and_(_not_archived_or_declined(), _not_grouped_child())
    norm_sql = submission_state_norm_sql()
    norms = [submission_state_norm_param(p) for p in st_in.split(",") if p.strip()]
    state_ok = _explicit_state_ok(norm_sql, norms)
    if include_closed:
        return and_(board_ok)
    if (not skip_open_due) and len(norms) == 1 and norms[0] in ("undecided", "willsubmit"):
        return and_(state_ok, board_ok, _has_open_due_date())
    return and_(state_ok, board_ok)


def apply_lead_list_query_params(filt: Any, args: Mapping[str, Any]) -> Any:
    """AND drawer/list-query params onto an existing lead_estimates filter.

    Only fields that exist on ``LeadEstimate`` are applied. ``saved_filter_id`` is ignored
    (analytics / client bookmark only).
    """
    q = (args.get("q") or "").strip()
    if q:
        like = f"%{q}%"
        filt = and_(
            filt,
            or_(
                LeadEstimate.name.ilike(like),
                LeadEstimate.number.ilike(like),
                LeadEstimate.trade_name.ilike(like),
                LeadEstimate.architect.ilike(like),
                LeadEstimate.property_owner.ilike(like),
                _client_company_name_sql().ilike(like),
                _location_city_sql().ilike(like),
                _location_state_sql().ilike(like),
            ),
        )

    trades = _csv_tokens(args.get("trade"))
    if trades:
        filt = and_(filt, or_(*[LeadEstimate.trade_name.ilike(f"%{t}%") for t in trades]))

    company_ids = [_parse_uuid_token(x) for x in _csv_tokens(args.get("company_id"))]
    company_ids = [x for x in company_ids if x]
    if company_ids:
        names = list(
            db_session_company_names(company_ids)
        )
        if names:
            filt = and_(
                filt,
                or_(
                    *[_client_company_name_sql().ilike(f"%{n}%") for n in names],
                    *[LeadEstimate.architect.ilike(f"%{n}%") for n in names],
                    *[LeadEstimate.property_owner.ilike(f"%{n}%") for n in names],
                ),
            )
        else:
            filt = and_(filt, literal(False))

    sectors = [s.lower() for s in _csv_tokens(args.get("sector"))]
    if sectors:
        sector_clauses: list[Any] = []
        for sec in sectors:
            pats = SECTOR_PATTERNS.get(sec, (f"%{sec}%",))
            for pat in pats:
                sector_clauses.append(func.lower(func.coalesce(LeadEstimate.market_sector, literal(""))).like(pat))
        filt = and_(filt, or_(*sector_clauses))

    stages = [_normalize_stage(s) for s in _csv_tokens(args.get("stage"))]
    if stages:
        filt = and_(filt, LeadEstimate.crm_stage.in_(stages))

    due_from = _parse_iso_dt(args.get("due_from") or args.get("due_after"), "due_from")
    due_to = _parse_iso_dt(args.get("due_to") or args.get("due_before"), "due_to")
    if due_from:
        filt = and_(filt, LeadEstimate.due_at.is_not(None), LeadEstimate.due_at >= due_from)
    if due_to:
        filt = and_(filt, LeadEstimate.due_at.is_not(None), LeadEstimate.due_at <= due_to)

    start_from = _parse_iso_dt(args.get("start_from"), "start_from")
    start_to = _parse_iso_dt(args.get("start_to"), "start_to")
    if start_from:
        filt = and_(
            filt,
            LeadEstimate.expected_start_at.is_not(None),
            LeadEstimate.expected_start_at >= start_from,
        )
    if start_to:
        filt = and_(
            filt,
            LeadEstimate.expected_start_at.is_not(None),
            LeadEstimate.expected_start_at <= start_to,
        )

    activity_from = _parse_iso_dt(args.get("activity_from"), "activity_from")
    activity_to = _parse_iso_dt(args.get("activity_to"), "activity_to")
    if activity_from:
        filt = and_(
            filt,
            LeadEstimate.bc_updated_at.is_not(None),
            LeadEstimate.bc_updated_at >= activity_from,
        )
    if activity_to:
        filt = and_(
            filt,
            LeadEstimate.bc_updated_at.is_not(None),
            LeadEstimate.bc_updated_at <= activity_to,
        )

    value_min = _parse_number(args.get("value_min"), "value_min")
    value_max = _parse_number(args.get("value_max"), "value_max")
    job_value = _job_value_sql()
    if value_min is not None:
        filt = and_(filt, job_value.is_not(None), job_value >= value_min)
    if value_max is not None:
        filt = and_(filt, job_value.is_not(None), job_value <= value_max)

    owner_ids = [_parse_uuid_token(x) for x in _csv_tokens(args.get("owner_id"))]
    owner_ids = [x for x in owner_ids if x]
    if owner_ids:
        needles = [str(oid) for oid in owner_ids]
        for oid in owner_ids:
            email = _user_email(oid)
            if email:
                needles.append(email)
        members_as_text = func.lower(func.coalesce(cast(LeadEstimate.members, String), literal("")))
        filt = and_(filt, or_(*[members_as_text.like(f"%{n.lower()}%") for n in needles if n]))

    return filt


def lead_list_order_by(sort: str | None):
    raw = (sort or "").strip().lower()
    if not raw:
        return (
            LeadEstimate.due_at.asc().nullslast(),
            LeadEstimate.name.asc(),
        )
    field, _, direction = raw.partition(".")
    desc = direction == "desc"
    col_map = {
        "due_date": LeadEstimate.due_at,
        "due_at": LeadEstimate.due_at,
        "start_date": LeadEstimate.expected_start_at,
        "expected_start_at": LeadEstimate.expected_start_at,
        "value": func.coalesce(LeadEstimate.final_value, LeadEstimate.rom),
        "name": LeadEstimate.name,
        "updated": LeadEstimate.bc_updated_at,
        "bc_updated_at": LeadEstimate.bc_updated_at,
    }
    col = col_map.get(field, LeadEstimate.due_at)
    expr = col.desc().nullslast() if desc else col.asc().nullslast()
    return (expr, LeadEstimate.name.asc())


def drawer_relaxes_open_board(args: Mapping[str, Any]) -> tuple[bool, bool]:
    """Return (include_closed, skip_open_due) for the default Bid Board hide rules."""
    stages = [_normalize_stage(s) for s in _csv_tokens(args.get("stage"))]
    include_closed = any(s in CLOSED_STAGES for s in stages)
    skip_open_due = include_closed or bool(
        (args.get("due_from") or args.get("due_after") or args.get("due_to") or args.get("due_before") or "").strip()
    )
    return include_closed, skip_open_due


def _parse_uuid_token(raw: str) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(raw).strip())
    except ValueError:
        return None


def db_session_company_names(ids: list[uuid.UUID]) -> list[str]:
    from ..extensions import db

    rows = db.session.scalars(select_companies(ids)).all()
    return [r.name for r in rows if r.name]


def select_companies(ids: list[uuid.UUID]):
    from sqlalchemy import select

    return select(Company).where(Company.id.in_(ids), Company.deleted_at.is_(None))


def _user_email(oid: uuid.UUID) -> str | None:
    from ..extensions import db
    from ..models import User

    u = db.session.get(User, oid)
    return (u.email or "").strip() if u else None
