"""Additional v1 routes for Plans 3–6 (takeoff by project, documents, estimates, RFP)."""
from __future__ import annotations

import secrets
import uuid
from decimal import Decimal
from typing import Any, Mapping

from flask import Blueprint, request
from sqlalchemy import func, or_, select
from sqlalchemy.orm import joinedload

from ..extensions import db
from ..models import (
    Document,
    Drawing,
    DrawingAnnotation,
    Estimate,
    EstimateLineItem,
    LeadEstimate,
    Rfp,
    RfpLineItem,
    TakeoffLineItem,
)
from ._perms import current_user
from ._rfi_service import ApiError, _parse_dt
from ._rfp_quotes_service import (
    attach_staff_quote_pdf,
    mailbox_ready,
    new_mail_tag,
    quote_attachment_file,
    quotes_mailbox,
    serialize_rfp,
    send_invitations,
    send_preview,
    sync_quotes_mailbox,
)
from .v1 import (
    _apply_takeoff_payload,
    _decimal_from_json,
    _iso,
    _jsonify,
    _parse_uuid_param,
    _project_exists,
    _takeoff_line_public,
    _takeoff_writes_enabled,
)


def _next_sort_order_for_project(project_id: uuid.UUID) -> int:
    m = db.session.scalar(
        select(func.coalesce(func.max(TakeoffLineItem.sort_order), -1)).where(
            TakeoffLineItem.project_id == project_id
        )
    )
    return int(m if m is not None else -1) + 1


def _project_takeoff_filter(project_id: uuid.UUID):
    lead_ids = select(LeadEstimate.id).where(LeadEstimate.project_id == project_id)
    return or_(TakeoffLineItem.project_id == project_id, TakeoffLineItem.lead_estimate_id.in_(lead_ids))


def _decimal_str_for_rollup(d: Decimal) -> str:
    """Plain decimal string without scientific notation; trim trailing zeros."""
    s = format(d, "f")
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s if s else "0"


def _coerce_decimal_for_rollup(val: Any) -> Decimal | None:
    if val is None:
        return None
    if isinstance(val, Decimal):
        return val
    if isinstance(val, bool):
        return None
    if isinstance(val, int):
        return Decimal(val)
    if isinstance(val, float):
        if val != val or val in (float("inf"), float("-inf")):  # NaN / inf
            return None
        return Decimal(str(val))
    if isinstance(val, str):
        s = val.strip()
        if not s:
            return None
        try:
            return Decimal(s)
        except Exception:
            return None
    return None


def _measurement_quantity_hint(md: Any) -> Decimal | None:
    """Optional numeric hints from measurement JSON (only well-known keys, safe parse)."""
    if not isinstance(md, dict):
        return None
    for key in ("quantity", "length", "total_length", "distance", "area", "area_sf", "computed_quantity"):
        q = _coerce_decimal_for_rollup(md.get(key))
        if q is not None:
            return q
    return None


def _measurement_unit_hint(md: Any) -> str | None:
    if not isinstance(md, dict):
        return None
    for key in ("unit", "measure_unit", "measurement_unit", "uom"):
        raw = md.get(key)
        if not isinstance(raw, str):
            continue
        u = raw.strip()[:50]
        if not u:
            continue
        if len(u) > 40 or any(ch.isspace() for ch in u):
            continue
        if not all(ch.isalnum() or ch in "/-._" for ch in u):
            continue
        return u
    return None


def _effective_qty_and_unit(t: TakeoffLineItem) -> tuple[Decimal | None, str | None]:
    """Resolve quantity and unit for rollups; return (None, None) if quantity unusable."""
    qty = _coerce_decimal_for_rollup(t.quantity)
    if qty is None:
        return None, None
    if qty == 0:
        hint = _measurement_quantity_hint(t.measurement_data)
        if hint is not None:
            qty = hint
    u = (t.unit or "").strip()[:50]
    if not u:
        u = _measurement_unit_hint(t.measurement_data) or ""
    if not u:
        u = "EA"
    return qty, u


def _takeoff_rollups(lines: list[TakeoffLineItem]) -> dict[str, Any]:
    """Lightweight job totals from line quantity/unit (+ safe measurement_data hints)."""
    out: dict[str, Any] = {"line_count": len(lines)}
    if not lines:
        return out
    total = Decimal("0")
    by_unit: dict[str, Decimal] = {}
    any_qty = False
    for t in lines:
        qty, unit = _effective_qty_and_unit(t)
        if qty is None or not unit:
            continue
        any_qty = True
        total += qty
        by_unit[unit] = by_unit.get(unit, Decimal("0")) + qty
    if any_qty:
        out["qty_sum_decimal"] = _decimal_str_for_rollup(total)
        out["by_unit"] = {k: _decimal_str_for_rollup(v) for k, v in sorted(by_unit.items())}
    return out


def register_extra_routes(bp: Blueprint) -> None:
    @bp.get("/projects/<project_id>/takeoff-lines")
    def list_project_takeoff_lines(project_id: str):
        pid = _parse_uuid_param(project_id)
        if not pid:
            return _jsonify({"error": "invalid project id"}), 400
        if not _project_exists(pid):
            return _jsonify({"error": "project not found"}), 404
        lines = db.session.scalars(
            select(TakeoffLineItem)
            .where(_project_takeoff_filter(pid))
            .order_by(TakeoffLineItem.sort_order.asc(), TakeoffLineItem.created_at.asc())
            .options(joinedload(TakeoffLineItem.material_price))
        ).all()
        items = [_takeoff_line_public(x) for x in lines]
        from ..services.employee_pc_cache import maybe_write_takeoff

        maybe_write_takeoff(pid, lines)
        return _jsonify(
            {
                "items": items,
                "entity": "takeoff_line_items",
                "rollups": _takeoff_rollups(lines),
            }
        )

    @bp.post("/projects/<project_id>/takeoff-lines")
    def create_project_takeoff_line(project_id: str):
        if not _takeoff_writes_enabled():
            return _jsonify({"error": "takeoff writes disabled (set TAKEOFF_API_WRITES_ENABLED=1)"}), 403
        pid = _parse_uuid_param(project_id)
        if not pid:
            return _jsonify({"error": "invalid project id"}), 400
        if not _project_exists(pid):
            return _jsonify({"error": "project not found"}), 404
        data = request.get_json(silent=True)
        if not isinstance(data, Mapping):
            data = {}
        try:
            t = TakeoffLineItem(
                lead_estimate_id=None,
                project_id=pid,
                sort_order=(
                    int(data["sort_order"])
                    if data.get("sort_order") is not None
                    else _next_sort_order_for_project(pid)
                ),
            )
            _apply_takeoff_payload(t, data, partial=False)
        except (ValueError, TypeError) as exc:
            return _jsonify({"error": str(exc)}), 400
        db.session.add(t)
        db.session.commit()
        from ..services.employee_pc_cache import cache_project_takeoff

        cache_project_takeoff(pid)
        from ._cost_code_service import sync_project_cost_codes_from_takeoff

        sync_project_cost_codes_from_takeoff(pid)
        return _jsonify({"item": _takeoff_line_public(t), "entity": "takeoff_line_item"}), 201

    @bp.get("/projects/<project_id>/documents")
    def list_project_documents(project_id: str):
        pid = _parse_uuid_param(project_id)
        if not pid:
            return _jsonify({"error": "invalid project id"}), 400
        if not _project_exists(pid):
            return _jsonify({"error": "project not found"}), 404
        rows = db.session.scalars(
            select(Document).where(Document.project_id == pid).order_by(Document.created_at.desc())
        ).all()

        def pub(d: Document) -> dict[str, Any]:
            return {
                "id": str(d.id),
                "document_type": d.document_type,
                "title": d.title,
                "file_url": d.file_url,
                "version": d.version,
                "created_at": _iso(d.created_at),
            }

        return _jsonify({"items": [pub(x) for x in rows], "entity": "documents"})

    @bp.post("/projects/<project_id>/documents")
    def create_project_document(project_id: str):
        pid = _parse_uuid_param(project_id)
        if not pid:
            return _jsonify({"error": "invalid project id"}), 400
        if not _project_exists(pid):
            return _jsonify({"error": "project not found"}), 404
        data = request.get_json(silent=True)
        if not isinstance(data, Mapping):
            return _jsonify({"error": "expected JSON object body"}), 400
        raw_type = str(data.get("document_type") or "other").strip().lower()
        allowed_types = {
            "drawing",
            "rfi",
            "submittal",
            "specification",
            "contract",
            "change_order",
            "invoice",
            "photo",
            "report",
            "ai_review_export",
            "safety_doc",
            "permit",
            "onboarding_packet",
            "policy_acknowledgment",
            "other",
        }
        dtype = raw_type if raw_type in allowed_types else "other"
        title = str(data.get("title") or "Untitled")[:500]
        file_url = str(data.get("file_url") or "")[:1024] or None
        d = Document(project_id=pid, document_type=dtype, title=title, file_url=file_url)
        db.session.add(d)
        db.session.commit()
        return (
            _jsonify(
                {
                    "item": {
                        "id": str(d.id),
                        "document_type": d.document_type,
                        "title": d.title,
                        "file_url": d.file_url,
                    },
                    "entity": "document",
                }
            ),
            201,
        )

    @bp.get("/documents/<document_id>/file")
    def get_document_file(document_id: str):
        """Stream a stored project document (ingest uploads and similar)."""
        from ..services.object_storage import UploadCategory, send_stored_file, stored_exists

        did = _parse_uuid_param(document_id)
        if not did:
            return _jsonify({"error": "invalid document id"}), 400
        row = db.session.get(Document, did)
        if row is None:
            return _jsonify({"error": "document not found"}), 404
        if isinstance(row, Drawing) or row.document_type == "drawing":
            from ..services.employee_pc_cache import respond_drawing_pdf
            from ..services.project_file_keys import preferred_drawing_object_name

            name = preferred_drawing_object_name(row)
            resp = respond_drawing_pdf(row, name)
        else:
            from ..services.project_file_keys import document_object_candidates

            name = f"{row.id}"
            for cand in document_object_candidates(row):
                if stored_exists(UploadCategory.DOCUMENTS, cand):
                    name = cand
                    break
            dl = (row.original_filename or row.title or "document").replace('"', "")[:200]
            mime = (row.mime_type or "application/octet-stream").strip() or "application/octet-stream"
            resp = send_stored_file(
                UploadCategory.DOCUMENTS,
                name,
                mimetype=mime,
                download_name=dl or "document",
            )
        if resp is None:
            return _jsonify({"error": "file not found on server"}), 404
        return resp

    @bp.get("/drawings/<drawing_id>/annotations")
    def list_drawing_annotations(drawing_id: str):
        did = _parse_uuid_param(drawing_id)
        if not did:
            return _jsonify({"error": "invalid drawing id"}), 400
        d = db.session.get(Drawing, did)
        if d is None:
            return _jsonify({"error": "drawing not found"}), 404
        rows = db.session.scalars(
            select(DrawingAnnotation).where(DrawingAnnotation.drawing_id == did).order_by(DrawingAnnotation.created_at)
        ).all()

        def pub(a: DrawingAnnotation) -> dict[str, Any]:
            return {
                "id": str(a.id),
                "type": a.type,
                "data": a.data,
                "severity": a.severity,
                "provider": a.provider,
                "created_at": _iso(a.created_at),
            }

        return _jsonify({"items": [pub(x) for x in rows], "entity": "drawing_annotations"})

    @bp.post("/drawings/<drawing_id>/annotations")
    def create_drawing_annotation(drawing_id: str):
        did = _parse_uuid_param(drawing_id)
        if not did:
            return _jsonify({"error": "invalid drawing id"}), 400
        d = db.session.get(Drawing, did)
        if d is None:
            return _jsonify({"error": "drawing not found"}), 404
        data = request.get_json(silent=True)
        if not isinstance(data, Mapping):
            return _jsonify({"error": "expected JSON object body"}), 400
        at = str(data.get("type") or "user_note").strip()
        if at not in (
            "measurement",
            "user_note",
            "ai_review",
            "cloud",
            "arrow",
            "highlight",
            "text_note",
            "photo_pin",
        ):
            return _jsonify({"error": "invalid annotation type"}), 400
        sev_raw = data.get("severity")
        sev = str(sev_raw).strip() if sev_raw else None
        if sev and sev not in ("info", "minor", "major", "critical"):
            sev = None
        ann = DrawingAnnotation(
            drawing_id=did,
            type=at,
            data=data.get("data") if isinstance(data.get("data"), (dict, list)) else None,
            severity=sev,
            provider=(str(data["provider"]).strip()[:120] if data.get("provider") else None),
        )
        db.session.add(ann)
        db.session.commit()
        if at == "ai_review":
            try:
                from ._issue_service import upsert_from_annotation
                from ._perms import current_user

                upsert_from_annotation(ann, current_user())
                db.session.commit()
            except Exception:
                db.session.rollback()
        return (
            _jsonify(
                {
                    "item": {
                        "id": str(ann.id),
                        "type": ann.type,
                        "data": ann.data,
                        "severity": ann.severity,
                    },
                    "entity": "drawing_annotation",
                }
            ),
            201,
        )

    @bp.patch("/drawing-annotations/<annotation_id>")
    def patch_drawing_annotation(annotation_id: str):
        aid = _parse_uuid_param(annotation_id)
        if not aid:
            return _jsonify({"error": "invalid annotation id"}), 400
        ann = db.session.get(DrawingAnnotation, aid)
        if ann is None:
            return _jsonify({"error": "annotation not found"}), 404
        data = request.get_json(silent=True)
        if not isinstance(data, Mapping):
            return _jsonify({"error": "expected JSON object body"}), 400
        if "data" in data and isinstance(data["data"], (dict, list)):
            ann.data = data["data"]
        if "severity" in data:
            s = str(data["severity"]).strip() if data["severity"] else None
            ann.severity = s if s in ("info", "minor", "major", "critical") else None
        db.session.commit()
        return _jsonify(
            {"item": {"id": str(ann.id), "type": ann.type, "data": ann.data}, "entity": "drawing_annotation"}
        )

    @bp.delete("/drawing-annotations/<annotation_id>")
    def delete_drawing_annotation(annotation_id: str):
        aid = _parse_uuid_param(annotation_id)
        if not aid:
            return _jsonify({"error": "invalid annotation id"}), 400
        ann = db.session.get(DrawingAnnotation, aid)
        if ann is None:
            return _jsonify({"error": "annotation not found"}), 404
        db.session.delete(ann)
        db.session.commit()
        return _jsonify({"ok": True})

    @bp.get("/estimates")
    def list_estimates():
        le_id = _parse_uuid_param((request.args.get("lead_estimate_id") or "").strip())
        pj_id = _parse_uuid_param((request.args.get("project_id") or "").strip())
        q = select(Estimate)
        if le_id:
            q = q.where(Estimate.lead_estimate_id == le_id)
        elif pj_id:
            q = q.where(Estimate.project_id == pj_id)
        else:
            return _jsonify({"error": "pass lead_estimate_id or project_id"}), 400
        rows = db.session.scalars(q.order_by(Estimate.created_at.desc())).all()

        def pub(e: Estimate) -> dict[str, Any]:
            return {
                "id": str(e.id),
                "lead_estimate_id": str(e.lead_estimate_id) if e.lead_estimate_id else None,
                "project_id": str(e.project_id) if e.project_id else None,
                "version": e.version,
                "status": e.status,
                "title": e.title,
                "name": e.name,
                "gc_name": e.gc_name,
                "is_current": bool(e.is_current),
                "total": float(e.total) if e.total is not None else None,
                "due_at": _iso(e.due_at),
            }

        return _jsonify({"items": [pub(x) for x in rows], "entity": "estimates"})

    @bp.post("/estimates")
    def create_estimate():
        data = request.get_json(silent=True)
        if not isinstance(data, Mapping):
            return _jsonify({"error": "expected JSON object body"}), 400
        le_id = _parse_uuid_param(str(data.get("lead_estimate_id") or "").strip())
        pj_id = _parse_uuid_param(str(data.get("project_id") or "").strip())
        if not le_id and not pj_id:
            return _jsonify({"error": "need lead_estimate_id or project_id"}), 400
        title = str(data.get("title") or data.get("name") or "").strip()[:255] or None
        due_at = _parse_dt(data.get("due_at"))
        le = db.session.get(LeadEstimate, le_id) if le_id else None
        e = Estimate(
            lead_estimate_id=le_id,
            project_id=pj_id,
            title=title,
            name=title or "Original Estimate",
            status="draft",
            version=1,
            due_at=due_at,
            fee_percentage=(le.fee_percentage if le is not None and le.fee_percentage is not None else 0),
            profit_margin=le.profit_margin if le is not None else None,
            rom=le.rom if le is not None else None,
        )
        db.session.add(e)
        db.session.flush()
        if le is not None:
            from ._estimate_service import mark_current

            mark_current(e)
        db.session.commit()
        return (
            _jsonify(
                {
                    "item": {
                        "id": str(e.id),
                        "lead_estimate_id": str(e.lead_estimate_id) if e.lead_estimate_id else None,
                        "project_id": str(e.project_id) if e.project_id else None,
                        "version": e.version,
                        "status": e.status,
                        "due_at": _iso(e.due_at),
                    },
                    "entity": "estimate",
                }
            ),
            201,
        )

    @bp.patch("/estimates/<estimate_id>")
    def patch_estimate(estimate_id: str):
        from ._estimate_service import EstimateError, estimate_summary_public, patch_estimate as apply_estimate_patch

        if not _takeoff_writes_enabled():
            return _jsonify(
                {
                    "error": "takeoff writes disabled (set TAKEOFF_API_WRITES_ENABLED=1)",
                    "error_code": "TAKEOFF_WRITES_DISABLED",
                }
            ), 403
        eid = _parse_uuid_param(estimate_id)
        if not eid:
            return _jsonify({"error": "invalid estimate id"}), 400
        est = db.session.get(Estimate, eid)
        if est is None:
            return _jsonify({"error": "estimate not found"}), 404
        data = request.get_json(silent=True)
        if not isinstance(data, Mapping):
            return _jsonify({"error": "expected JSON object body"}), 400
        try:
            apply_estimate_patch(est, data)
        except EstimateError as exc:
            body: dict[str, Any] = {"error": exc.message}
            if exc.error_code:
                body["error_code"] = exc.error_code
            return _jsonify(body), exc.status
        if "total" in data:
            tv = data.get("total")
            est.total = None if tv is None else _decimal_from_json(tv, Decimal("0"))
        if "due_at" in data:
            est.due_at = _parse_dt(data.get("due_at"))
        db.session.commit()
        item = estimate_summary_public(est)
        item["title"] = est.title
        item["notes"] = est.notes
        return _jsonify({"item": item, "entity": "estimate"})

    @bp.post("/estimates/<estimate_id>/line-items")
    def add_estimate_line_item(estimate_id: str):
        eid = _parse_uuid_param(estimate_id)
        if not eid:
            return _jsonify({"error": "invalid estimate id"}), 400
        est = db.session.get(Estimate, eid)
        if est is None:
            return _jsonify({"error": "estimate not found"}), 404
        data = request.get_json(silent=True)
        if not isinstance(data, Mapping):
            return _jsonify({"error": "expected JSON object body"}), 400
        tid = _parse_uuid_param(str(data.get("takeoff_line_item_id") or "").strip())
        if not tid:
            return _jsonify({"error": "takeoff_line_item_id required"}), 400
        tl = db.session.get(TakeoffLineItem, tid)
        if tl is None:
            return _jsonify({"error": "takeoff line not found"}), 404
        markup = None
        if data.get("markup_percentage") is not None:
            markup = _decimal_from_json(data["markup_percentage"], Decimal("0"))
        li = EstimateLineItem(
            estimate_id=eid,
            takeoff_line_item_id=tid,
            sort_order=int(data.get("sort_order") or 0),
            unit_cost=_decimal_from_json(data.get("unit_cost"), tl.unit_cost),
            markup_percentage=markup,
        )
        db.session.add(li)
        db.session.commit()
        return _jsonify({"item": {"id": str(li.id), "takeoff_line_item_id": str(tid)}, "entity": "estimate_line_item"}), 201

    @bp.get("/rfps")
    def list_rfps():
        le_id = _parse_uuid_param((request.args.get("lead_estimate_id") or "").strip())
        pj_id = _parse_uuid_param((request.args.get("project_id") or "").strip())
        q = select(Rfp)
        if le_id:
            q = q.where(Rfp.lead_estimate_id == le_id)
        elif pj_id:
            q = q.where(Rfp.project_id == pj_id)
        rows = db.session.scalars(q.order_by(Rfp.created_at.desc()).limit(200)).all()

        def pub(r: Rfp) -> dict[str, Any]:
            return {
                "id": str(r.id),
                "title": r.title,
                "status": r.status,
                "due_at": _iso(r.due_at),
                "public_token": r.public_token,
                "line_source": r.line_source or "manual",
                "project_id": str(r.project_id) if r.project_id else None,
            }

        return _jsonify({"items": [pub(x) for x in rows], "entity": "rfps"})

    @bp.post("/rfps")
    def create_rfp():
        from ._rfp_body_service import attach_takeoff, default_line_source

        data = request.get_json(silent=True)
        if not isinstance(data, Mapping):
            return _jsonify({"error": "expected JSON object body"}), 400
        le_id = _parse_uuid_param(str(data.get("lead_estimate_id") or "").strip())
        pj_id = _parse_uuid_param(str(data.get("project_id") or "").strip())
        title = str(data.get("title") or "RFP")[:500]
        token = secrets.token_urlsafe(32)[:64]
        source = str(data.get("line_source") or "").strip().lower()
        if source not in ("takeoff", "manual", "narrative"):
            source = default_line_source(pj_id, le_id)
        est_id = _parse_uuid_param(str(data.get("estimate_id") or data.get("source_estimate_id") or "").strip())
        remaining = bool(data.get("remaining") or data.get("remaining_scopes"))
        if remaining:
            source = "takeoff"
        r = Rfp(
            lead_estimate_id=le_id,
            project_id=pj_id,
            title=title,
            public_token=token,
            mail_tag=new_mail_tag(),
            status="Draft",
            line_source=source,
            source_estimate_id=est_id,
            show_line_table=source != "narrative",
            scope_of_work=(str(data.get("scope_of_work") or "").strip() or None),
            inclusions=(str(data.get("inclusions") or "").strip() or None),
            exclusions=(str(data.get("exclusions") or "").strip() or None),
            clarifications=(str(data.get("clarifications") or "").strip() or None),
            due_at=_parse_dt(data.get("due_at")),
        )
        db.session.add(r)
        db.session.flush()
        if le_id:
            le = db.session.get(LeadEstimate, le_id)
            if le is not None:
                le.primary_rfp_id = r.id
        if remaining and est_id:
            attach_takeoff(r, {"estimate_id": str(est_id), "remaining": True})
        elif isinstance(data.get("takeoff_line_ids"), list) and est_id:
            attach_takeoff(r, {"estimate_id": str(est_id), "takeoff_line_ids": data.get("takeoff_line_ids")})
        db.session.commit()
        return _jsonify({"item": serialize_rfp(r), "entity": "rfp"}), 201

    @bp.get("/rfps/mailbox")
    def rfp_mailbox_status():
        return _jsonify(
            {
                "entity": "rfp_mailbox",
                "item": {"mailbox": quotes_mailbox(), "graph_configured": mailbox_ready()},
            }
        )

    @bp.post("/rfps/mailbox/sync")
    def rfp_mailbox_sync():
        from flask import current_app

        from ._integration_bc import cron_secret_matches

        cu = current_user()
        if cu.user is None and not cron_secret_matches(request, current_app):
            return _jsonify({"error": "authentication required"}), 401
        try:
            top = int(request.args.get("top") or 50)
        except (TypeError, ValueError):
            top = 50
        try:
            item = sync_quotes_mailbox(top=top, actor_user_id=cu.id)
        except ApiError as exc:
            return _jsonify({"error": exc.message}), exc.status
        return _jsonify({"entity": "rfp_mailbox_sync", "item": item})

    @bp.get("/rfps/<rfp_id>")
    def get_rfp(rfp_id: str):
        rid = _parse_uuid_param(rfp_id)
        if not rid:
            return _jsonify({"error": "invalid rfp id"}), 400
        r = db.session.get(Rfp, rid)
        if r is None:
            return _jsonify({"error": "rfp not found"}), 404
        return _jsonify({"item": serialize_rfp(r), "entity": "rfp"})

    @bp.get("/rfps/<rfp_id>/email-preview")
    def rfp_email_preview(rfp_id: str):
        rid = _parse_uuid_param(rfp_id)
        if not rid:
            return _jsonify({"error": "invalid rfp id"}), 400
        r = db.session.get(Rfp, rid)
        if r is None:
            return _jsonify({"error": "rfp not found"}), 404
        data = request.get_json(silent=True) if request.is_json else None
        if not isinstance(data, Mapping):
            data = {k: request.args.get(k) for k in request.args}
        return _jsonify(send_preview(r, data if isinstance(data, Mapping) else {}))

    @bp.post("/rfps/<rfp_id>/send")
    def rfp_send(rfp_id: str):
        rid = _parse_uuid_param(rfp_id)
        if not rid:
            return _jsonify({"error": "invalid rfp id"}), 400
        data = request.get_json(silent=True)
        try:
            return _jsonify(
                send_invitations(
                    rid,
                    data if isinstance(data, Mapping) else {},
                    user_id=current_user().id,
                )
            )
        except ApiError as exc:
            return _jsonify({"error": exc.message}), exc.status

    @bp.patch("/rfps/<rfp_id>")
    def patch_rfp(rfp_id: str):
        from ._rfp_body_service import load_rfp, patch_rfp as apply_patch

        rid = _parse_uuid_param(rfp_id)
        if not rid:
            return _jsonify({"error": "invalid rfp id"}), 400
        data = request.get_json(silent=True)
        if not isinstance(data, Mapping):
            return _jsonify({"error": "expected JSON object body"}), 400
        try:
            r = apply_patch(load_rfp(rid), data, confirm_source=bool(data.get("confirm")))
            db.session.commit()
        except ApiError as exc:
            return _jsonify({"error": exc.message}), exc.status
        return _jsonify({"item": serialize_rfp(r), "entity": "rfp"})

    @bp.post("/rfps/<rfp_id>/line-items")
    def add_rfp_line(rfp_id: str):
        from ._rfp_body_service import load_rfp, serialize_line, upsert_line

        rid = _parse_uuid_param(rfp_id)
        if not rid:
            return _jsonify({"error": "invalid rfp id"}), 400
        data = request.get_json(silent=True)
        if not isinstance(data, Mapping):
            return _jsonify({"error": "expected JSON object body"}), 400
        try:
            row = upsert_line(load_rfp(rid), data)
            db.session.commit()
        except ApiError as exc:
            return _jsonify({"error": exc.message}), exc.status
        return _jsonify({"item": serialize_line(row), "entity": "rfp_line_item"}), 201

    @bp.patch("/rfps/<rfp_id>/line-items/<line_id>")
    def patch_rfp_line(rfp_id: str, line_id: str):
        from ._rfp_body_service import load_rfp, serialize_line, upsert_line

        rid = _parse_uuid_param(rfp_id)
        lid = _parse_uuid_param(line_id)
        if not rid or not lid:
            return _jsonify({"error": "invalid id"}), 400
        data = request.get_json(silent=True)
        if not isinstance(data, Mapping):
            return _jsonify({"error": "expected JSON object body"}), 400
        try:
            row = upsert_line(load_rfp(rid), data, lid)
            db.session.commit()
        except ApiError as exc:
            return _jsonify({"error": exc.message}), exc.status
        return _jsonify({"item": serialize_line(row), "entity": "rfp_line_item"})

    @bp.delete("/rfps/<rfp_id>/line-items/<line_id>")
    def delete_rfp_line(rfp_id: str, line_id: str):
        from ._rfp_body_service import delete_line, load_rfp

        rid = _parse_uuid_param(rfp_id)
        lid = _parse_uuid_param(line_id)
        if not rid or not lid:
            return _jsonify({"error": "invalid id"}), 400
        try:
            delete_line(load_rfp(rid), lid)
            db.session.commit()
        except ApiError as exc:
            return _jsonify({"error": exc.message}), exc.status
        return _jsonify({"ok": True, "entity": "rfp_line_item"})

    @bp.get("/rfps/<rfp_id>/takeoff-candidates")
    def rfp_takeoff_candidates(rfp_id: str):
        from ._rfp_body_service import list_takeoff_candidates, load_rfp

        rid = _parse_uuid_param(rfp_id)
        if not rid:
            return _jsonify({"error": "invalid rfp id"}), 400
        eid = _parse_uuid_param((request.args.get("estimate_id") or "").strip())
        try:
            item = list_takeoff_candidates(load_rfp(rid), eid)
        except ApiError as exc:
            return _jsonify({"error": exc.message}), exc.status
        return _jsonify({"item": item, "entity": "rfp_takeoff_candidates"})

    @bp.post("/rfps/<rfp_id>/attach-takeoff")
    def rfp_attach_takeoff(rfp_id: str):
        from ._rfp_body_service import attach_takeoff, load_rfp

        rid = _parse_uuid_param(rfp_id)
        if not rid:
            return _jsonify({"error": "invalid rfp id"}), 400
        data = request.get_json(silent=True)
        if not isinstance(data, Mapping):
            return _jsonify({"error": "expected JSON object body"}), 400
        try:
            r = load_rfp(rid)
            result = attach_takeoff(r, data)
            db.session.commit()
        except ApiError as exc:
            return _jsonify({"error": exc.message}), exc.status
        return _jsonify({"item": serialize_rfp(r), "attach": result, "entity": "rfp"})

    @bp.post("/rfps/<rfp_id>/refresh-takeoff")
    def rfp_refresh_takeoff(rfp_id: str):
        from ._rfp_body_service import load_rfp, refresh_takeoff

        rid = _parse_uuid_param(rfp_id)
        if not rid:
            return _jsonify({"error": "invalid rfp id"}), 400
        try:
            r = load_rfp(rid)
            result = refresh_takeoff(r)
            db.session.commit()
        except ApiError as exc:
            return _jsonify({"error": exc.message}), exc.status
        return _jsonify({"item": serialize_rfp(r), "refresh": result, "entity": "rfp"})

    @bp.get("/rfps/<rfp_id>/drawing-candidates")
    def rfp_drawing_candidates(rfp_id: str):
        from ._rfp_body_service import list_drawing_candidates, load_rfp

        rid = _parse_uuid_param(rfp_id)
        if not rid:
            return _jsonify({"error": "invalid rfp id"}), 400
        try:
            item = list_drawing_candidates(load_rfp(rid))
        except ApiError as exc:
            return _jsonify({"error": exc.message}), exc.status
        return _jsonify({"item": item, "entity": "rfp_drawing_candidates"})

    @bp.put("/rfps/<rfp_id>/drawings")
    def rfp_put_drawings(rfp_id: str):
        from ._rfp_body_service import load_rfp, replace_drawings

        rid = _parse_uuid_param(rfp_id)
        if not rid:
            return _jsonify({"error": "invalid rfp id"}), 400
        data = request.get_json(silent=True)
        if not isinstance(data, Mapping):
            return _jsonify({"error": "expected JSON object body"}), 400
        try:
            r = load_rfp(rid)
            replace_drawings(r, data)
            db.session.commit()
        except ApiError as exc:
            return _jsonify({"error": exc.message}), exc.status
        return _jsonify({"item": serialize_rfp(r), "entity": "rfp"})

    @bp.get("/rfps/<rfp_id>/vendors")
    def rfp_vendors(rfp_id: str):
        from ._rfp_body_service import load_rfp, vendor_directory

        rid = _parse_uuid_param(rfp_id)
        if not rid:
            return _jsonify({"error": "invalid rfp id"}), 400
        try:
            r = load_rfp(rid)
        except ApiError as exc:
            return _jsonify({"error": exc.message}), exc.status
        q = (request.args.get("q") or "").strip()
        trade = (request.args.get("trade") or "").strip()
        return _jsonify({"items": vendor_directory(r, q=q, trade=trade), "entity": "rfp_vendors"})

    @bp.get("/rfps/<rfp_id>/compare")
    def rfp_compare(rfp_id: str):
        from ._rfp_body_service import compare_table, load_rfp

        rid = _parse_uuid_param(rfp_id)
        if not rid:
            return _jsonify({"error": "invalid rfp id"}), 400
        try:
            item = compare_table(load_rfp(rid))
        except ApiError as exc:
            return _jsonify({"error": exc.message}), exc.status
        return _jsonify({"item": item, "entity": "rfp_compare"})

    @bp.post("/rfps/<rfp_id>/award")
    def rfp_award(rfp_id: str):
        from ._rfp_body_service import award_rfp, load_rfp

        rid = _parse_uuid_param(rfp_id)
        if not rid:
            return _jsonify({"error": "invalid rfp id"}), 400
        data = request.get_json(silent=True)
        if not isinstance(data, Mapping):
            return _jsonify({"error": "expected JSON object body"}), 400
        try:
            return _jsonify(award_rfp(load_rfp(rid), data, user_id=current_user().id))
        except ApiError as exc:
            return _jsonify({"error": exc.message}), exc.status

    @bp.post("/rfps/<rfp_id>/clone")
    def rfp_clone(rfp_id: str):
        from ._rfp_body_service import clone_rfp, load_rfp

        rid = _parse_uuid_param(rfp_id)
        if not rid:
            return _jsonify({"error": "invalid rfp id"}), 400
        try:
            clone = clone_rfp(load_rfp(rid))
            db.session.commit()
        except ApiError as exc:
            return _jsonify({"error": exc.message}), exc.status
        return _jsonify({"item": serialize_rfp(clone), "entity": "rfp"}), 201

    @bp.post("/rfps/<rfp_id>/quotes/<quote_id>/attachments")
    def rfp_quote_upload_pdf(rfp_id: str, quote_id: str):
        from ._rfp_body_service import load_rfp

        rid = _parse_uuid_param(rfp_id)
        qid = _parse_uuid_param(quote_id)
        if not rid or not qid:
            return _jsonify({"error": "invalid id"}), 400
        f = request.files.get("file")
        if f is None or not getattr(f, "filename", None):
            return _jsonify({"error": "missing file field (multipart form-data)"}), 400
        data = f.read()
        try:
            r = load_rfp(rid)
            return _jsonify(
                attach_staff_quote_pdf(
                    r,
                    quote_id=qid,
                    company_id=None,
                    filename=f.filename or "quote.pdf",
                    content_type=f.mimetype or "application/pdf",
                    data=data,
                    uploaded_by=current_user().id,
                )
            ), 201
        except ApiError as exc:
            return _jsonify({"error": exc.message}), exc.status

    @bp.post("/rfps/<rfp_id>/quote-pdf")
    def rfp_quote_pdf_for_vendor(rfp_id: str):
        from ._rfp_body_service import load_rfp

        rid = _parse_uuid_param(rfp_id)
        if not rid:
            return _jsonify({"error": "invalid rfp id"}), 400
        f = request.files.get("file")
        if f is None or not getattr(f, "filename", None):
            return _jsonify({"error": "missing file field (multipart form-data)"}), 400
        qid = _parse_uuid_param(request.form.get("quote_id") or "")
        cid = _parse_uuid_param(request.form.get("company_id") or "")
        data = f.read()
        try:
            r = load_rfp(rid)
            return _jsonify(
                attach_staff_quote_pdf(
                    r,
                    quote_id=qid,
                    company_id=cid,
                    filename=f.filename or "quote.pdf",
                    content_type=f.mimetype or "application/pdf",
                    data=data,
                    uploaded_by=current_user().id,
                )
            ), 201
        except ApiError as exc:
            return _jsonify({"error": exc.message}), exc.status

    @bp.get("/rfps/<rfp_id>/quotes/<quote_id>/attachments/<document_id>")
    def rfp_quote_attachment_file(rfp_id: str, quote_id: str, document_id: str):
        from ._rfp_body_service import load_rfp

        rid = _parse_uuid_param(rfp_id)
        qid = _parse_uuid_param(quote_id)
        did = _parse_uuid_param(document_id)
        if not rid or not qid or not did:
            return _jsonify({"error": "invalid id"}), 400
        try:
            return quote_attachment_file(load_rfp(rid), qid, did)
        except ApiError as exc:
            return _jsonify({"error": exc.message}), exc.status
