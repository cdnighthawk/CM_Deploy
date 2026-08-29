"""Golden State / AGC San Diego planroom lead list + weekly CSV import."""
from __future__ import annotations

from datetime import date
from typing import Any

from flask import Blueprint, request
from sqlalchemy import and_, or_, select
from werkzeug.utils import secure_filename

from ..extensions import db
from ..golden_state_planroom_csv import parse_agcs_weekly_listing, upsert_planroom_rows
from ..golden_state_planroom_detail import apply_detail_updates
from ..golden_state_planroom_geo import coords_for_planroom_row
from ..golden_state_planroom_score import score_planroom_lead, sort_key_fit
from ..models.golden_state_planroom_lead import GoldenStatePlanroomLead
from ._office_location import resolve_office_origin
from ._serializers import haversine_miles
from .v1 import _jsonify

_MAX_LIST = 5000


def _distance_miles(row: GoldenStatePlanroomLead, origin: tuple[float, float] | None) -> float | None:
    if origin is None:
        return None
    dest = coords_for_planroom_row(row)
    if dest is None:
        return None
    return round(haversine_miles(origin, dest), 1)


def _parse_query_date(raw: str | None, label: str) -> date | None:
    if not raw or not str(raw).strip():
        return None
    text = str(raw).strip()
    try:
        return date.fromisoformat(text[:10])
    except ValueError as exc:
        raise ValueError(f"invalid {label} (use YYYY-MM-DD)") from exc


def _row_public(row: GoldenStatePlanroomLead, origin: tuple[float, float] | None = None) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "plan_number": row.plan_number,
        "name": row.name,
        "location": row.location,
        "bid_date": row.bid_date.isoformat() if row.bid_date else None,
        "bid_time": row.bid_time,
        "addenda_count": row.addenda_count,
        "estimate_high": str(row.estimate_high) if row.estimate_high is not None else None,
        "is_new": row.is_new,
        "bid_date_changed": row.bid_date_changed,
        "listing_week": row.listing_week.isoformat() if row.listing_week else None,
        "source": row.source,
        "source_file": row.source_file,
        "project_url": row.project_url,
        "detail": row.detail,
        "details_fetched_at": row.details_fetched_at.isoformat() if row.details_fetched_at else None,
        "crm_stage": row.crm_stage,
        "notes": row.notes,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        "distance_miles": _distance_miles(row, origin),
        "fit": score_planroom_lead(
            name=row.name,
            location=row.location,
            estimate_high=row.estimate_high,
        ),
    }


def _apply_list_filters(filt, args):
    q = (args.get("q") or "").strip()
    if q:
        like = f"%{q}%"
        filt = and_(
            filt,
            or_(
                GoldenStatePlanroomLead.name.ilike(like),
                GoldenStatePlanroomLead.plan_number.ilike(like),
                GoldenStatePlanroomLead.location.ilike(like),
            ),
        )
    location = (args.get("location") or "").strip()
    if location:
        filt = and_(filt, GoldenStatePlanroomLead.location.ilike(f"%{location}%"))
    new_only = (args.get("new_only") or "").strip().lower()
    if new_only in {"1", "true", "yes"}:
        filt = and_(filt, GoldenStatePlanroomLead.is_new.is_(True))
    changed = (args.get("date_changed") or "").strip().lower()
    if changed in {"1", "true", "yes"}:
        filt = and_(filt, GoldenStatePlanroomLead.bid_date_changed.is_(True))
    bid_from = _parse_query_date(args.get("bid_from"), "bid_from")
    if bid_from:
        filt = and_(filt, GoldenStatePlanroomLead.bid_date >= bid_from)
    bid_to = _parse_query_date(args.get("bid_to"), "bid_to")
    if bid_to:
        filt = and_(filt, GoldenStatePlanroomLead.bid_date <= bid_to)
    return filt


def _sort_spec(sort: str | None) -> tuple[str, bool]:
    key = (sort or "fit_score").strip().lower()
    desc = key.startswith("-")
    if desc:
        key = key[1:]
    if key in {"fit", "score"}:
        key = "fit_score"
    return key, desc


def _order_by(sort: str | None):
    key, desc = _sort_spec(sort)
    col_map = {
        "bid_date": GoldenStatePlanroomLead.bid_date,
        "name": GoldenStatePlanroomLead.name,
        "location": GoldenStatePlanroomLead.location,
        "plan_number": GoldenStatePlanroomLead.plan_number,
        "estimate_high": GoldenStatePlanroomLead.estimate_high,
        "addenda_count": GoldenStatePlanroomLead.addenda_count,
        "is_new": GoldenStatePlanroomLead.is_new,
    }
    col = col_map.get(key, GoldenStatePlanroomLead.bid_date)
    if key not in col_map:
        desc = False
    primary = col.desc().nullslast() if desc else col.asc().nullslast()
    return primary, GoldenStatePlanroomLead.name.asc()


def _sort_items(items: list[dict[str, Any]], sort: str | None) -> list[dict[str, Any]]:
    key, desc = _sort_spec(sort)
    if key == "fit_score":
        return sorted(items, key=sort_key_fit)
    if key == "bid_date":
        items = sorted(items, key=lambda r: (r.get("bid_date") or "9999-99-99", r.get("name") or ""))
        return list(reversed(items)) if desc else items
    if key == "estimate_high":

        def est(row: dict[str, Any]) -> float:
            raw = row.get("estimate_high")
            try:
                return float(raw) if raw is not None else -1.0
            except (TypeError, ValueError):
                return -1.0

        items = sorted(items, key=lambda r: (est(r), r.get("name") or ""))
        return list(reversed(items)) if desc else items
    if key == "name":
        items = sorted(items, key=lambda r: (r.get("name") or "").lower())
        return list(reversed(items)) if desc else items
    return items


def register_golden_state_planroom_routes(bp: Blueprint) -> None:
    @bp.get("/golden-state-planroom/leads")
    def list_golden_state_planroom_leads():
        try:
            limit = max(1, min(int(request.args.get("limit", 500)), 2000))
            offset = max(0, int(request.args.get("offset", 0)))
        except ValueError:
            return _jsonify({"error": "invalid limit or offset"}), 400
        try:
            filt = _apply_list_filters(GoldenStatePlanroomLead.id.isnot(None), request.args)
        except ValueError as exc:
            return _jsonify({"error": str(exc)}), 400
        rows = db.session.scalars(
            select(GoldenStatePlanroomLead)
            .where(filt)
            .order_by(*_order_by(request.args.get("sort")))
            .limit(_MAX_LIST)
        ).all()
        origin = resolve_office_origin()
        items = [_row_public(r, origin) for r in rows]
        strong_only = (request.args.get("strong_only") or "").strip().lower() in {"1", "true", "yes"}
        if strong_only:
            items = [row for row in items if (row.get("fit") or {}).get("band") == "strong"]
        items = _sort_items(items, request.args.get("sort"))
        total = len(items)
        page = items[offset : offset + limit]
        return _jsonify(
            {
                "items": page,
                "total": total,
                "limit": limit,
                "offset": offset,
                "entity": "golden_state_planroom_leads",
            }
        )

    @bp.post("/golden-state-planroom/import")
    def import_golden_state_planroom_csv():
        upload = request.files.get("file")
        if upload is None or not upload.filename:
            return _jsonify({"error": "file is required"}), 400
        filename = secure_filename(upload.filename) or "AGCS_CAProjects.html"
        raw = upload.read()
        if not raw:
            return _jsonify({"error": "empty file"}), 400
        text = raw.decode("utf-8-sig", errors="replace")
        rows, listing_week = parse_agcs_weekly_listing(text, filename=filename)
        if not rows:
            return _jsonify({"error": "no project rows found in listing"}), 400
        loaded, skipped = upsert_planroom_rows(db.session, rows, source_file=filename)
        return _jsonify(
            {
                "loaded": loaded,
                "skipped": skipped,
                "parsed": len(rows),
                "listing_week": listing_week.isoformat() if listing_week else None,
                "source_file": filename,
                "entity": "golden_state_planroom_leads",
            }
        )

    @bp.post("/golden-state-planroom/details")
    def upsert_golden_state_planroom_details():
        body = request.get_json(silent=True) or {}
        items = body.get("items")
        if not isinstance(items, list) or not items:
            return _jsonify({"error": "items is required"}), 400
        updated, skipped = apply_detail_updates(db.session, items)
        return _jsonify(
            {
                "updated": updated,
                "skipped": skipped,
                "entity": "golden_state_planroom_leads",
            }
        )
