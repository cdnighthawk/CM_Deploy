"""Additional v1 routes for Plans 3–6 (takeoff by project, documents, estimates, RFP)."""
from __future__ import annotations

import secrets
import uuid
from decimal import Decimal
from typing import Any, Mapping

from flask import Blueprint, request
from sqlalchemy import func, or_, select

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
from ._rfi_service import _parse_dt
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
        ).all()
        return _jsonify({"items": [_takeoff_line_public(x) for x in lines], "entity": "takeoff_line_items"})

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
        if at not in ("measurement", "user_note", "ai_review"):
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
        title = str(data.get("title") or "").strip()[:255] or None
        due_at = _parse_dt(data.get("due_at"))
        e = Estimate(
            lead_estimate_id=le_id,
            project_id=pj_id,
            title=title,
            status="Draft",
            version=1,
            due_at=due_at,
        )
        db.session.add(e)
        db.session.flush()
        if le_id:
            le = db.session.get(LeadEstimate, le_id)
            if le is not None:
                le.primary_estimate_id = e.id
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
        eid = _parse_uuid_param(estimate_id)
        if not eid:
            return _jsonify({"error": "invalid estimate id"}), 400
        est = db.session.get(Estimate, eid)
        if est is None:
            return _jsonify({"error": "estimate not found"}), 404
        data = request.get_json(silent=True)
        if not isinstance(data, Mapping):
            return _jsonify({"error": "expected JSON object body"}), 400
        if "title" in data:
            t = data.get("title")
            est.title = str(t).strip()[:255] or None if t is not None else None
        if "status" in data and data["status"] is not None:
            est.status = str(data["status"]).strip()[:40] or est.status
        if "notes" in data:
            n = data.get("notes")
            est.notes = str(n) if n is not None else None
        if "total" in data:
            tv = data.get("total")
            est.total = None if tv is None else _decimal_from_json(tv, Decimal("0"))
        if "due_at" in data:
            est.due_at = _parse_dt(data.get("due_at"))
        db.session.commit()
        return _jsonify(
            {
                "item": {
                    "id": str(est.id),
                    "lead_estimate_id": str(est.lead_estimate_id) if est.lead_estimate_id else None,
                    "project_id": str(est.project_id) if est.project_id else None,
                    "version": est.version,
                    "status": est.status,
                    "title": est.title,
                    "notes": est.notes,
                    "total": float(est.total) if est.total is not None else None,
                    "due_at": _iso(est.due_at),
                },
                "entity": "estimate",
            }
        )

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
            }

        return _jsonify({"items": [pub(x) for x in rows], "entity": "rfps"})

    @bp.post("/rfps")
    def create_rfp():
        data = request.get_json(silent=True)
        if not isinstance(data, Mapping):
            return _jsonify({"error": "expected JSON object body"}), 400
        le_id = _parse_uuid_param(str(data.get("lead_estimate_id") or "").strip())
        pj_id = _parse_uuid_param(str(data.get("project_id") or "").strip())
        title = str(data.get("title") or "RFP")[:500]
        token = secrets.token_urlsafe(32)[:64]
        r = Rfp(lead_estimate_id=le_id, project_id=pj_id, title=title, public_token=token, status="Draft")
        db.session.add(r)
        db.session.flush()
        if le_id:
            le = db.session.get(LeadEstimate, le_id)
            if le is not None:
                le.primary_rfp_id = r.id
        db.session.commit()
        return _jsonify({"item": {"id": str(r.id), "public_token": r.public_token}, "entity": "rfp"}), 201

    @bp.get("/rfps/<rfp_id>")
    def get_rfp(rfp_id: str):
        rid = _parse_uuid_param(rfp_id)
        if not rid:
            return _jsonify({"error": "invalid rfp id"}), 400
        r = db.session.get(Rfp, rid)
        if r is None:
            return _jsonify({"error": "rfp not found"}), 404
        lines = db.session.scalars(
            select(RfpLineItem).where(RfpLineItem.rfp_id == rid).order_by(RfpLineItem.sort_order)
        ).all()
        return _jsonify(
            {
                "item": {
                    "id": str(r.id),
                    "title": r.title,
                    "status": r.status,
                    "due_at": _iso(r.due_at),
                    "public_token": r.public_token,
                    "line_items": [
                        {
                            "id": str(x.id),
                            "description": x.description,
                            "quantity": float(x.quantity),
                            "unit": x.unit,
                        }
                        for x in lines
                    ],
                },
                "entity": "rfp",
            }
        )

    @bp.get("/rfps/<rfp_id>/email-preview")
    def rfp_email_preview(rfp_id: str):
        rid = _parse_uuid_param(rfp_id)
        if not rid:
            return _jsonify({"error": "invalid rfp id"}), 400
        r = db.session.get(Rfp, rid)
        if r is None:
            return _jsonify({"error": "rfp not found"}), 404
        html = f"<html><body><h2>{r.title}</h2><p>Vendor portal: /public/rfp/{r.public_token}</p></body></html>"
        return _jsonify({"html": html, "entity": "rfp_email_preview"})
