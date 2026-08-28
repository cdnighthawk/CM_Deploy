"""Submittal QC gate: revisions, completeness, AI, checklist, stamp, holds."""
from __future__ import annotations

import secrets
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any, Mapping

from sqlalchemy import func, or_, select
from sqlalchemy.orm import selectinload

from ..extensions import db
from ..models import (
    AuditLog,
    Company,
    Document,
    Drawing,
    DrawingAnnotation,
    Project,
    Submittal,
    SubmittalAudit,
    SubmittalChecklistItem,
    SubmittalHold,
    SubmittalRevision,
    User,
    WorkflowInstance,
)
from ..submittals.checklist_templates import list_templates, template_items_for
from . import _submittal_service as sub_svc
from . import _workflow_service as wf
from ._perms import CurrentUser
from ._rfi_service import ApiError, _parse_dt, _parse_uuid
from ._submittal_service import (
    _append_audit,
    _can_edit_submittal,
    _can_view_submittal,
    _document_public,
    _get_submittal_eager,
    _iso,
    _is_admin,
    _is_writer,
    _submittal_docs,
    _utcnow,
)

STAMP_TO_STATUS = {
    "no_exceptions": "internally_approved",
    "make_corrections_noted": "approved_as_noted",
    "revise_resubmit": "revise_resubmit",
    "rejected": "rejected",
    "for_info_only": "for_info_only",
}
RELEASE_OK_STATUSES = frozenset(
    {"released", "internally_approved", "approved_as_noted", "for_info_only"}
)
STAMP_VALUES = frozenset(STAMP_TO_STATUS)
CHECKLIST_RESULTS = frozenset({"pass", "fail", "na", "blank"})
AI_STATUSES = frozenset({"not_run", "queued", "complete", "failed", "overridden"})
MIN_REVIEW_SECONDS = 180
PUBLIC_TOKEN_TTL_DAYS = 14


def _user_name(u: User | None) -> str | None:
    if u is None:
        return None
    name = " ".join(p for p in (u.first_name, u.last_name) if p).strip()
    return name or u.email


def _project_code(project: Project) -> str:
    raw = (project.number or "").strip()
    if raw:
        return "".join(ch for ch in raw if ch.isalnum())[:12] or "PRJ"
    return "PRJ"


def _next_submittal_number(project: Project) -> str:
    nxt = db.session.scalar(
        select(func.coalesce(func.max(Submittal.number), 0)).where(Submittal.project_id == project.id)
    )
    seq = int(nxt or 0) + 1
    return f"SUB-{_project_code(project)}-{seq:04d}"


def _next_revision_letter(current: str | None) -> str:
    raw = (current or "A").strip().upper()
    if raw.isdigit():
        return "A"
    if len(raw) == 1 and "A" <= raw <= "Y":
        return chr(ord(raw) + 1)
    if raw == "Z":
        return "AA"
    return "B"


def _global_audit(
    cu: CurrentUser | None,
    entity_id: uuid.UUID,
    action: str,
    message: str,
    changes: dict[str, Any] | None = None,
) -> None:
    db.session.add(
        AuditLog(
            user_id=cu.id if cu else None,
            entity_type="submittal",
            entity_id=entity_id,
            action=action,
            message=message,
            changes=changes,
        )
    )


def _load_submittal_qc(sid: uuid.UUID) -> Submittal | None:
    return db.session.scalars(
        select(Submittal)
        .where(Submittal.id == sid)
        .options(
            selectinload(Submittal.documents),
            selectinload(Submittal.audit_entries),
            selectinload(Submittal.line_items),
            selectinload(Submittal.revisions).selectinload(SubmittalRevision.checklist_items),
            selectinload(Submittal.revisions).selectinload(SubmittalRevision.documents),
            selectinload(Submittal.holds),
            selectinload(Submittal.vendor),
            selectinload(Submittal.assigned_reviewer),
            selectinload(Submittal.project),
        )
    ).first()


def _current_revision(s: Submittal) -> SubmittalRevision | None:
    if s.current_revision_id:
        for rev in s.revisions or []:
            if rev.id == s.current_revision_id:
                return rev
        return db.session.get(SubmittalRevision, s.current_revision_id)
    currents = [r for r in (s.revisions or []) if r.is_current]
    return currents[-1] if currents else None


def _sync_reviewer_from_workflow(s: Submittal) -> None:
    if not s.workflow_instance_id:
        return
    inst = wf.get_instance(s.workflow_instance_id)
    if inst is None:
        return
    step = wf.current_ready_step(inst)
    s.assigned_reviewer_id = step.assignee_user_id if step else None


def _ensure_holds(s: Submittal) -> None:
    existing = {h.hold_type: h for h in (s.holds or [])}
    if s.action_type == "informational":
        return
    for hold_type, reason in (
        ("procurement", "Internal QC not released"),
        ("receive", "Field receive blocked until approved submittal"),
        ("install", "Install blocked until approved submittal"),
    ):
        if hold_type not in existing:
            h = SubmittalHold(submittal_id=s.id, hold_type=hold_type, is_active=True, reason=reason)
            db.session.add(h)


def _release_holds(s: Submittal, reason: str) -> None:
    for h in s.holds or []:
        h.is_active = False
        h.reason = reason


def _seed_checklist(rev: SubmittalRevision, s: Submittal) -> None:
    items = template_items_for(spec_section=s.spec_section, trade=s.trade)
    s.spec_requirements = [row["template_key"] for row in items]
    for row in items:
        db.session.add(
            SubmittalChecklistItem(
                revision_id=rev.id,
                template_key=row["template_key"],
                sort_order=row["sort_order"],
                label=row["label"],
                required=bool(row.get("required", True)),
                source="template",
            )
        )


def _create_revision_shell(s: Submittal, letter: str, *, current: bool) -> SubmittalRevision:
    if current:
        for rev in s.revisions or []:
            rev.is_current = False
    rev = SubmittalRevision(
        submittal_id=s.id,
        revision=letter,
        is_current=current,
        ai_status="not_run",
    )
    db.session.add(rev)
    db.session.flush()
    _seed_checklist(rev, s)
    if current:
        s.current_revision_id = rev.id
        s.revision = letter
    return rev


def _qc_schema_ready() -> bool:
    bind = db.session.get_bind()
    if bind is None:
        return False
    from sqlalchemy import inspect as sa_inspect

    return bool(sa_inspect(bind).has_table("submittal_revisions"))


def bootstrap_qc(s: Submittal, cu: CurrentUser, project: Project | None = None) -> None:
    """Called from create_submittal after the row exists."""
    if not _qc_schema_ready():
        return
    project = project or db.session.get(Project, s.project_id)
    if project is None:
        return
    if not s.submittal_number:
        s.submittal_number = _next_submittal_number(project)
        # number already assigned; regenerate display using that number
        s.submittal_number = f"SUB-{_project_code(project)}-{int(s.number):04d}"
    if not s.action_type:
        s.action_type = "action"
    if not s.public_token:
        s.public_token = secrets.token_urlsafe(32)[:64]
        s.public_token_expires_at = _utcnow() + timedelta(days=PUBLIC_TOKEN_TTL_DAYS)
    if s.created_by_user_id is None:
        s.created_by_user_id = cu.id
    if not s.revisions:
        _create_revision_shell(s, "A", current=True)
    if not s.workflow_instance_id:
        inst = wf.start_instance(
            process_key=wf.PROCESS_SUBMITTAL_QC,
            subject_type="submittal",
            subject_id=s.id,
            project_id=s.project_id,
            cu=cu,
        )
        s.workflow_instance_id = inst.id
        _sync_reviewer_from_workflow(s)
    _ensure_holds(s)
    db.session.flush()


def _revision_public(rev: SubmittalRevision) -> dict[str, Any]:
    findings = rev.ai_findings if isinstance(rev.ai_findings, list) else []
    severities = [str(f.get("severity") or "").lower() for f in findings if isinstance(f, Mapping)]
    max_sev = None
    for key in ("critical", "major", "minor", "info"):
        if key in severities:
            max_sev = key
            break
    return {
        "id": str(rev.id),
        "revision": rev.revision,
        "isCurrent": rev.is_current,
        "packageComplete": bool(rev.package_complete),
        "completenessScore": float(rev.completeness_score) if rev.completeness_score is not None else None,
        "aiStatus": rev.ai_status,
        "aiOverriddenReason": rev.ai_overridden_reason,
        "aiFindings": findings,
        "aiMaxSeverity": max_sev,
        "humanStamp": rev.human_stamp,
        "stampComments": rev.stamp_comments,
        "reviewedBy": str(rev.reviewed_by_user_id) if rev.reviewed_by_user_id else None,
        "reviewStartedAt": _iso(rev.review_started_at),
        "reviewCompletedAt": _iso(rev.review_completed_at),
        "reviewDurationSeconds": rev.review_duration_seconds,
        "checklistComplete": bool(rev.checklist_complete),
        "rubberStampSuspect": bool(rev.rubber_stamp_suspect),
        "rushException": bool(rev.rush_exception),
        "documentIds": [str(d.id) for d in (rev.documents or [])],
        "checklist": [_checklist_public(i) for i in (rev.checklist_items or [])],
    }


def _checklist_public(item: SubmittalChecklistItem) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "templateKey": item.template_key,
        "sortOrder": item.sort_order,
        "label": item.label,
        "required": item.required,
        "result": item.result,
        "comment": item.comment,
        "source": item.source,
        "aiFindingRef": item.ai_finding_ref,
        "disposition": item.disposition,
        "completedBy": str(item.completed_by_user_id) if item.completed_by_user_id else None,
        "completedAt": _iso(item.completed_at),
    }


def _hold_public(h: SubmittalHold) -> dict[str, Any]:
    return {
        "id": str(h.id),
        "holdType": h.hold_type,
        "isActive": bool(h.is_active),
        "reason": h.reason,
    }


def _is_overdue(s: Submittal) -> bool:
    if s.needed_by_date is None:
        if s.due_at is None:
            return False
        due = s.due_at.date() if isinstance(s.due_at, datetime) else s.due_at
    else:
        due = s.needed_by_date
    if s.status in RELEASE_OK_STATUSES or s.status in {"cancelled", "superseded"}:
        return False
    return due < date.today()


def register_row(s: Submittal) -> dict[str, Any]:
    rev = _current_revision(s)
    vendor = s.vendor
    reviewer = s.assigned_reviewer
    findings = (rev.ai_findings if rev and isinstance(rev.ai_findings, list) else []) or []
    severities = [str(f.get("severity") or "").lower() for f in findings if isinstance(f, Mapping)]
    max_sev = None
    for key in ("critical", "major", "minor", "info"):
        if key in severities:
            max_sev = key
            break
    needed = s.needed_by_date or (s.due_at.date() if s.due_at else None)
    return {
        "id": str(s.id),
        "projectId": str(s.project_id),
        "submittalNumber": s.submittal_number or f"SUB-{int(s.number):04d}",
        "number": s.number,
        "title": s.title,
        "specSection": s.spec_section,
        "trade": s.trade,
        "submittalType": s.submittal_type,
        "actionType": s.action_type or "action",
        "status": s.status,
        "revision": rev.revision if rev else s.revision,
        "vendorName": vendor.name if vendor else s.responsible_contractor,
        "reviewerName": _user_name(reviewer) or s.ball_in_court,
        "assignedReviewerId": str(s.assigned_reviewer_id) if s.assigned_reviewer_id else None,
        "neededByDate": needed.isoformat() if needed else None,
        "isOverdue": _is_overdue(s),
        "packageComplete": bool(rev.package_complete) if rev else False,
        "aiStatus": rev.ai_status if rev else "not_run",
        "aiMaxSeverity": max_sev,
        "checklistComplete": bool(rev.checklist_complete) if rev else False,
        "rubberStampSuspect": bool(rev.rubber_stamp_suspect) if rev else False,
        "released": s.status == "released" or s.released_at is not None,
        "publicToken": s.public_token,
    }


def qc_detail(s: Submittal) -> dict[str, Any]:
    rev = _current_revision(s)
    inst = wf.get_instance(s.workflow_instance_id) if s.workflow_instance_id else None
    stamp_gates = stamp_gate_state(s, rev) if rev else {"canStamp": False, "unmet": ["No current revision"]}
    return {
        "item": {**sub_svc._submittal_public(s, include_lines=True), **register_row(s)},
        "revision": _revision_public(rev) if rev else None,
        "revisions": [_revision_public(r) for r in (s.revisions or [])],
        "holds": [_hold_public(h) for h in (s.holds or [])],
        "workflow": wf.instance_public(inst) if inst else None,
        "stampGates": stamp_gates,
        "attachments": [_document_public(d) for d in _submittal_docs(s)],
        "audit": [sub_svc._audit_public(a) for a in sorted(s.audit_entries or [], key=lambda x: x.created_at or _utcnow(), reverse=True)],
        "permissions": {
            "can_edit": True,
            "can_annotate": True,
        },
    }


def list_register(cu: CurrentUser, args: Mapping[str, Any]) -> dict[str, Any]:
    if not _is_writer(cu) and not sub_svc.can_view_submittal_log(cu):
        raise ApiError("not allowed to view submittals", 403)
    stmt = (
        select(Submittal)
        .options(
            selectinload(Submittal.revisions).selectinload(SubmittalRevision.checklist_items),
            selectinload(Submittal.vendor),
            selectinload(Submittal.assigned_reviewer),
            selectinload(Submittal.holds),
        )
        .order_by(Submittal.created_at.desc())
    )
    pid = _parse_uuid(args.get("project_id"))
    if pid:
        stmt = stmt.where(Submittal.project_id == pid)
    status = (str(args.get("status") or "")).strip()
    if status:
        stmt = stmt.where(Submittal.status == status)
    trade = (str(args.get("trade") or "")).strip()
    if trade:
        stmt = stmt.where(Submittal.trade == trade)
    spec = (str(args.get("spec_section") or "")).strip()
    if spec:
        stmt = stmt.where(Submittal.spec_section.ilike(f"%{spec}%"))
    reviewer = _parse_uuid(args.get("reviewer_id"))
    if reviewer:
        stmt = stmt.where(Submittal.assigned_reviewer_id == reviewer)
    rows = db.session.scalars(stmt.limit(500)).all()
    items = [register_row(s) for s in rows]
    if str(args.get("overdue") or "") in ("1", "true"):
        items = [i for i in items if i["isOverdue"]]
    if str(args.get("rubber_stamp") or "") in ("1", "true"):
        items = [i for i in items if i["rubberStampSuspect"]]
    return {"entity": "submittals", "items": items, "permissions": {"can_create": _is_writer(cu)}}


def create_from_api(data: Mapping[str, Any], cu: CurrentUser) -> dict[str, Any]:
    pid = _parse_uuid(data.get("project_id"))
    if pid is None:
        raise ApiError("project_id is required", 400)
    project = db.session.get(Project, pid)
    if project is None or project.deleted_at is not None:
        raise ApiError("project not found", 404)
    payload = dict(data)
    if data.get("needed_by_date") and not data.get("due_at"):
        payload["due_at"] = str(data.get("needed_by_date"))
    body = sub_svc.create_submittal(pid, payload, cu)
    s = _load_submittal_qc(uuid.UUID(body["item"]["id"]))
    assert s is not None
    if "trade" in data:
        s.trade = (str(data.get("trade")).strip()[:40] or None) if data.get("trade") else None
    if "action_type" in data:
        at = str(data.get("action_type") or "action").strip().lower()
        s.action_type = "informational" if at == "informational" else "action"
    if "vendor_id" in data:
        s.vendor_id = _parse_uuid(data.get("vendor_id"))
    if data.get("needed_by_date"):
        raw = str(data.get("needed_by_date"))[:10]
        s.needed_by_date = date.fromisoformat(raw)
    if "notes" in data:
        s.notes = (str(data.get("notes")).strip() or None) if data.get("notes") else None
    if "linked_drawing_ids" in data and isinstance(data.get("linked_drawing_ids"), list):
        s.linked_drawing_ids = [str(x) for x in data["linked_drawing_ids"]]
    bootstrap_qc(s, cu, project)
    db.session.commit()
    s2 = _load_submittal_qc(s.id)
    assert s2 is not None
    return qc_detail(s2)


def get_detail(sid: uuid.UUID, cu: CurrentUser) -> dict[str, Any]:
    s = _load_submittal_qc(sid)
    if s is None:
        raise ApiError("submittal not found", 404)
    if not _can_view_submittal(cu, s):
        raise ApiError("not allowed to view this submittal", 403)
    bootstrap_qc(s, cu)
    db.session.commit()
    s2 = _load_submittal_qc(sid)
    assert s2 is not None
    out = qc_detail(s2)
    inst = wf.get_instance(s2.workflow_instance_id) if s2.workflow_instance_id else None
    step = wf.current_ready_step(inst) if inst else None
    out["permissions"] = {
        "can_edit": _can_edit_submittal(cu, s2) or (inst is not None and step is not None and wf.can_act_on_step(cu, inst, step)),
        "can_annotate": _can_edit_submittal(cu, s2),
        "canAct": inst is not None and step is not None and wf.can_act_on_step(cu, inst, step),
    }
    return out


def patch_qc(sid: uuid.UUID, data: Mapping[str, Any], cu: CurrentUser) -> dict[str, Any]:
    s = _load_submittal_qc(sid)
    if s is None:
        raise ApiError("submittal not found", 404)
    if not _can_edit_submittal(cu, s):
        raise ApiError("not allowed to edit this submittal", 403)
    sub_svc.patch_submittal(sid, data, cu)
    s = _load_submittal_qc(sid)
    assert s is not None
    if "trade" in data:
        s.trade = (str(data.get("trade")).strip()[:40] or None) if data.get("trade") else None
    if "action_type" in data:
        at = str(data.get("action_type") or "action").strip().lower()
        s.action_type = "informational" if at == "informational" else "action"
    if "vendor_id" in data:
        s.vendor_id = _parse_uuid(data.get("vendor_id"))
    if "needed_by_date" in data:
        raw = data.get("needed_by_date")
        s.needed_by_date = date.fromisoformat(str(raw)[:10]) if raw else None
    if "notes" in data:
        s.notes = (str(data.get("notes")).strip() or None) if data.get("notes") else None
    if "linked_drawing_ids" in data and isinstance(data.get("linked_drawing_ids"), list):
        s.linked_drawing_ids = [str(x) for x in data["linked_drawing_ids"]]
    if "rush_exception" in data:
        rev = _current_revision(s)
        if rev is not None and (_is_admin(cu) or cu.has_role("standard")):
            rev.rush_exception = bool(data.get("rush_exception"))
            rev.rush_exception_by_user_id = cu.id
            rev.rush_exception_reason = (str(data.get("rush_exception_reason") or "").strip() or None)
    s.updated_by_user_id = cu.id
    db.session.commit()
    return get_detail(sid, cu)


def create_revision(sid: uuid.UUID, cu: CurrentUser) -> dict[str, Any]:
    s = _load_submittal_qc(sid)
    if s is None:
        raise ApiError("submittal not found", 404)
    if not _can_edit_submittal(cu, s):
        raise ApiError("not allowed", 403)
    current = _current_revision(s)
    letter = _next_revision_letter(current.revision if current else s.revision)
    if current:
        current.is_current = False
    rev = _create_revision_shell(s, letter, current=True)
    _append_audit(s, "revision", f"Opened revision {letter}", None, {"revision": letter}, cu.id)
    _global_audit(cu, s.id, "revision", f"Opened revision {letter}")
    db.session.commit()
    return get_detail(sid, cu)


def attach_revision_document(
    sid: uuid.UUID, rev_id: uuid.UUID, data: Mapping[str, Any], cu: CurrentUser
) -> dict[str, Any]:
    s = _load_submittal_qc(sid)
    if s is None:
        raise ApiError("submittal not found", 404)
    rev = db.session.get(SubmittalRevision, rev_id)
    if rev is None or rev.submittal_id != s.id:
        raise ApiError("revision not found", 404)
    body = sub_svc.add_submittal_attachment(sid, data, cu)
    doc = db.session.get(Document, uuid.UUID(body["item"]["id"]))
    if doc is not None and doc not in rev.documents:
        rev.documents.append(doc)
        db.session.commit()
    return body


def recompute_completeness(sid: uuid.UUID, rev_id: uuid.UUID, cu: CurrentUser) -> dict[str, Any]:
    s = _load_submittal_qc(sid)
    if s is None:
        raise ApiError("submittal not found", 404)
    rev = next((r for r in (s.revisions or []) if r.id == rev_id), None)
    if rev is None:
        raise ApiError("revision not found", 404)
    docs = list(rev.documents or []) or _submittal_docs(s)
    drawings = list(s.linked_drawing_ids or [])
    required = [i for i in (rev.checklist_items or []) if i.source == "template" and i.required]
    score_parts = 0
    total = 4
    if docs:
        score_parts += 1
    if s.spec_section:
        score_parts += 1
    if s.title:
        score_parts += 1
    if drawings or any(i.result == "na" and i.template_key == "always.drawing_or_na" for i in rev.checklist_items or []):
        score_parts += 1
    rev.completeness_score = round(100.0 * score_parts / total, 2)
    rev.package_complete = bool(docs) and bool(s.spec_section) and bool(s.title)
    if rev.package_complete and s.status in ("draft", "incomplete"):
        s.status = "in_qc"
        s.received_at = s.received_at or _utcnow()
        _advance_if_action(s, "completeness", cu)
    elif not rev.package_complete and s.status == "draft":
        s.status = "incomplete"
    _append_audit(
        s,
        "completeness",
        f"Completeness {rev.completeness_score}",
        None,
        {"package_complete": rev.package_complete, "score": float(rev.completeness_score or 0)},
        cu.id,
    )
    _global_audit(cu, s.id, "completeness", "Recomputed completeness")
    db.session.commit()
    return get_detail(sid, cu)


def _advance_if_action(s: Submittal, action: str, cu: CurrentUser | None) -> None:
    if not s.workflow_instance_id:
        return
    inst = wf.get_instance(s.workflow_instance_id)
    if inst is None:
        return
    step = wf.current_ready_step(inst)
    if step is None:
        return
    actions = [str(a) for a in (step.required_actions or [])]
    if action in actions:
        wf.complete_step(inst, step.step_key, cu=cu)
        _sync_reviewer_from_workflow(s)
        if step.on_approve_status and s.status not in STAMP_TO_STATUS.values():
            if action != "stamp":
                s.status = step.on_approve_status


def stamp_gate_state(s: Submittal, rev: SubmittalRevision) -> dict[str, Any]:
    unmet: list[str] = []
    if not rev.package_complete:
        unmet.append("Package is not complete")
    required = [i for i in (rev.checklist_items or []) if i.required]
    unfinished = [i for i in required if (i.result or "blank") not in ("pass", "fail", "na")]
    if unfinished:
        unmet.append(f"{len(unfinished)} required checklist item(s) still blank")
    findings = [f for f in (rev.ai_findings or []) if isinstance(f, Mapping)]
    for i, finding in enumerate(findings):
        sev = str(finding.get("severity") or "").lower()
        if sev not in ("critical", "major"):
            continue
        ref = str(finding.get("id") or finding.get("ref") or i)
        row = next(
            (c for c in (rev.checklist_items or []) if c.source == "ai_finding" and (c.ai_finding_ref == ref or c.template_key == f"ai.{ref}")),
            None,
        )
        if row is None or not row.disposition:
            unmet.append(f"Critical/Major AI finding lacks disposition: {finding.get('title') or ref}")
    if rev.ai_status not in ("complete", "overridden"):
        unmet.append("AI review must be complete or overridden with a reason")
    elif rev.ai_status == "overridden" and not (rev.ai_overridden_reason or "").strip():
        unmet.append("AI override requires a written reason")
    duration = rev.review_duration_seconds
    if rev.review_started_at and duration is None:
        duration = int((_utcnow() - rev.review_started_at).total_seconds())
    if not ((duration or 0) >= MIN_REVIEW_SECONDS or rev.rush_exception):
        unmet.append("Review duration under 180 seconds (need superintendent/PM rush exception)")
    return {"canStamp": not unmet, "unmet": unmet, "reviewDurationSeconds": duration}


def start_review_clock(rev: SubmittalRevision) -> None:
    if rev.review_started_at is None:
        rev.review_started_at = _utcnow()


def patch_checklist(
    sid: uuid.UUID, rev_id: uuid.UUID, data: Mapping[str, Any], cu: CurrentUser
) -> dict[str, Any]:
    s = _load_submittal_qc(sid)
    if s is None:
        raise ApiError("submittal not found", 404)
    rev = next((r for r in (s.revisions or []) if r.id == rev_id), None)
    if rev is None:
        raise ApiError("revision not found", 404)
    _assert_can_act(s, cu)
    start_review_clock(rev)
    items = data.get("items") if isinstance(data.get("items"), list) else [data]
    for raw in items:
        if not isinstance(raw, Mapping):
            continue
        item = None
        iid = _parse_uuid(raw.get("id"))
        if iid:
            item = next((c for c in rev.checklist_items if c.id == iid), None)
        if item is None and raw.get("template_key"):
            item = next((c for c in rev.checklist_items if c.template_key == raw.get("template_key")), None)
        if item is None and raw.get("label") and raw.get("source") == "custom":
            item = SubmittalChecklistItem(
                revision_id=rev.id,
                template_key=str(raw.get("template_key") or f"custom.{uuid.uuid4().hex[:8]}"),
                sort_order=int(raw.get("sort_order") or len(rev.checklist_items or [])),
                label=str(raw.get("label"))[:500],
                required=bool(raw.get("required", False)),
                source="custom",
            )
            db.session.add(item)
            rev.checklist_items.append(item)
        if item is None:
            continue
        if "result" in raw:
            result = (str(raw.get("result") or "").strip().lower() or None)
            if result and result not in CHECKLIST_RESULTS:
                raise ApiError("result must be pass, fail, na, or blank", 400)
            item.result = None if result == "blank" else result
        if "comment" in raw:
            item.comment = (str(raw.get("comment")).strip() or None) if raw.get("comment") is not None else None
        if item.result == "fail" and not (item.comment or "").strip():
            raise ApiError("comment is required when a checklist item fails", 400)
        if "disposition" in raw:
            item.disposition = (str(raw.get("disposition")).strip() or None) if raw.get("disposition") else None
        item.completed_by_user_id = cu.id
        item.completed_at = _utcnow()
    required = [i for i in rev.checklist_items if i.required]
    rev.checklist_complete = all((i.result or "blank") in ("pass", "fail", "na") for i in required)
    if rev.checklist_complete:
        _advance_if_action(s, "complete_checklist", cu)
    _append_audit(s, "checklist", "Updated QC checklist", None, {"complete": rev.checklist_complete}, cu.id)
    db.session.commit()
    return get_detail(sid, cu)


def persist_ai_review(
    sid: uuid.UUID, rev_id: uuid.UUID, data: Mapping[str, Any], cu: CurrentUser
) -> dict[str, Any]:
    s = _load_submittal_qc(sid)
    if s is None:
        raise ApiError("submittal not found", 404)
    rev = next((r for r in (s.revisions or []) if r.id == rev_id), None)
    if rev is None:
        raise ApiError("revision not found", 404)
    _assert_can_act(s, cu)
    start_review_clock(rev)
    status = str(data.get("ai_status") or data.get("status") or "queued").strip()
    if status not in AI_STATUSES:
        raise ApiError("invalid ai_status", 400)
    if status == "overridden":
        reason = str(data.get("ai_overridden_reason") or data.get("reason") or "").strip()
        if not reason:
            raise ApiError("AI override requires a written reason", 400)
        rev.ai_overridden_reason = reason
        rev.ai_status = "overridden"
    else:
        rev.ai_status = status
    findings = data.get("findings")
    if isinstance(findings, list):
        rev.ai_findings = findings
        _insert_ai_checklist_rows(rev, findings)
    if data.get("raw_response") is not None:
        rev.raw_response = str(data.get("raw_response"))
    annotation_id = _parse_uuid(data.get("annotation_id"))
    drawing_ids = [uuid.UUID(str(x)) for x in (s.linked_drawing_ids or []) if _parse_uuid(x)]
    if annotation_id:
        rev.ai_review_annotation_id = annotation_id
    elif drawing_ids and isinstance(findings, list):
        drawing = db.session.get(Drawing, drawing_ids[0])
        if drawing is not None:
            sev = None
            for key in ("critical", "major", "minor", "info"):
                if any(str(f.get("severity") or "").lower() == key for f in findings if isinstance(f, Mapping)):
                    sev = key
                    break
            ann = DrawingAnnotation(
                drawing_id=drawing.id,
                type="ai_review",
                data={"mode": "submittal_review", "submittalId": str(s.id), "revisionId": str(rev.id)},
                severity=sev,
                issues={"findings": findings},
                raw_response=rev.raw_response,
                created_by_user_id=cu.id,
            )
            db.session.add(ann)
            db.session.flush()
            rev.ai_review_annotation_id = ann.id
    if status in ("complete", "overridden"):
        _advance_if_action(s, "run_ai_review", cu)
    _append_audit(s, "ai_run", f"AI review {rev.ai_status}", None, {"ai_status": rev.ai_status}, cu.id)
    _global_audit(cu, s.id, "ai_run", f"AI review {rev.ai_status}")
    db.session.commit()
    return get_detail(sid, cu)


def _insert_ai_checklist_rows(rev: SubmittalRevision, findings: list[Any]) -> None:
    existing = {c.ai_finding_ref for c in (rev.checklist_items or []) if c.ai_finding_ref}
    sort = max((c.sort_order for c in (rev.checklist_items or [])), default=0) + 1
    for i, finding in enumerate(findings):
        if not isinstance(finding, Mapping):
            continue
        sev = str(finding.get("severity") or "").lower()
        if sev not in ("critical", "major"):
            continue
        ref = str(finding.get("id") or finding.get("ref") or i)
        if ref in existing:
            continue
        label = str(finding.get("suggested_checklist_item") or finding.get("title") or f"AI finding {ref}")
        row = SubmittalChecklistItem(
            revision_id=rev.id,
            template_key=f"ai.{ref}",
            sort_order=sort,
            label=label[:500],
            required=True,
            source="ai_finding",
            ai_finding_ref=ref,
        )
        db.session.add(row)
        rev.checklist_items.append(row)
        sort += 1
        existing.add(ref)


def apply_stamp(sid: uuid.UUID, rev_id: uuid.UUID, data: Mapping[str, Any], cu: CurrentUser) -> dict[str, Any]:
    s = _load_submittal_qc(sid)
    if s is None:
        raise ApiError("submittal not found", 404)
    rev = next((r for r in (s.revisions or []) if r.id == rev_id), None)
    if rev is None:
        raise ApiError("revision not found", 404)
    _assert_can_act(s, cu)
    stamp = str(data.get("stamp") or data.get("human_stamp") or "").strip()
    if stamp not in STAMP_VALUES:
        raise ApiError("invalid stamp", 400)
    if stamp == "make_corrections_noted" and not str(data.get("comments") or data.get("stamp_comments") or "").strip():
        raise ApiError("notes are required for approved as noted", 400)
    start_review_clock(rev)
    if rev.review_started_at:
        rev.review_duration_seconds = int((_utcnow() - rev.review_started_at).total_seconds())
    if data.get("rush_exception"):
        rev.rush_exception = True
        rev.rush_exception_by_user_id = cu.id
        rev.rush_exception_reason = (str(data.get("rush_exception_reason") or "").strip() or None)
    gates = stamp_gate_state(s, rev)
    if not gates["canStamp"]:
        raise ApiError("; ".join(gates["unmet"]), 409)
    rev.human_stamp = stamp
    rev.stamp_comments = (str(data.get("comments") or data.get("stamp_comments") or "").strip() or None)
    rev.reviewed_by_user_id = cu.id
    rev.review_completed_at = _utcnow()
    rev.rubber_stamp_suspect = _rubber_stamp_suspect(rev)
    status = STAMP_TO_STATUS[stamp]
    inst = wf.get_instance(s.workflow_instance_id) if s.workflow_instance_id else None
    stamp_step = next((st for st in (inst.steps if inst else []) if "stamp" in (st.required_actions or [])), None)
    if stamp_step and stamp_step.on_approve_status:
        status = stamp_step.on_approve_status
    s.status = status
    s.internally_reviewed_at = _utcnow()
    s.response = rev.stamp_comments
    _advance_if_action(s, "stamp", cu)
    if stamp in ("revise_resubmit", "rejected"):
        next_letter = _next_revision_letter(rev.revision)
        rev.is_current = False
        _create_revision_shell(s, next_letter, current=True)
        s.status = status
        # holds stay on
    else:
        _maybe_auto_release(s)
    _append_audit(s, "stamp", f"Stamped {stamp}", None, {"stamp": stamp, "status": s.status}, cu.id)
    _global_audit(cu, s.id, "stamp", f"Stamped {stamp}")
    from ._submittal_notifications import enqueue_submittal_email

    enqueue_submittal_email(s, "stamped", cu)
    db.session.commit()
    return get_detail(sid, cu)


def _rubber_stamp_suspect(rev: SubmittalRevision) -> bool:
    duration = rev.review_duration_seconds or 0
    if duration < MIN_REVIEW_SECONDS:
        return True
    comments = [c for c in (rev.checklist_items or []) if (c.comment or "").strip()]
    dispositions = [
        c
        for c in (rev.checklist_items or [])
        if c.source == "ai_finding" and c.disposition and c.disposition != "accepted"
    ]
    if not comments and not dispositions:
        return True
    if rev.ai_status == "not_run":
        return True
    return False


def _maybe_auto_release(s: Submittal) -> None:
    project = s.project or db.session.get(Project, s.project_id)
    require_ae = bool(project.require_ae_before_release) if project else False
    if s.status not in {"internally_approved", "approved_as_noted"}:
        if s.action_type == "informational" or s.status == "for_info_only":
            _release_holds(s, "Informational / for-info-only")
            if s.status != "for_info_only":
                s.status = "for_info_only"
        return
    ae_ok = (s.ae_action or "").strip().lower() in {"approved", "approved_as_noted", "approved as noted", "no_exceptions"}
    if require_ae and not ae_ok:
        return
    s.status = "released"
    s.released_at = _utcnow()
    _release_holds(s, "Released after internal QC")
    if s.workflow_instance_id:
        inst = wf.get_instance(s.workflow_instance_id)
        if inst:
            for step in inst.steps:
                if step.status in ("pending", "ready") and step.skippable:
                    cond = (step.entry_condition or "")
                    if cond == "not_informational" and s.action_type == "informational":
                        wf.complete_step(inst, step.step_key, skip=True)
                    elif cond == "require_ae_before_release" and not require_ae:
                        wf.complete_step(inst, step.step_key, skip=True)
            release = next((st for st in inst.steps if "release" in (st.required_actions or [])), None)
            if release and release.status in ("pending", "ready"):
                wf.complete_step(inst, release.step_key)


def assign_reviewer(sid: uuid.UUID, data: Mapping[str, Any], cu: CurrentUser) -> dict[str, Any]:
    s = _load_submittal_qc(sid)
    if s is None:
        raise ApiError("submittal not found", 404)
    if not s.workflow_instance_id:
        bootstrap_qc(s, cu)
    inst = wf.assign_instance_step(s.workflow_instance_id, data, cu)
    _sync_reviewer_from_workflow(s)
    reviewer = db.session.get(User, s.assigned_reviewer_id) if s.assigned_reviewer_id else None
    if reviewer:
        s.ball_in_court = reviewer.email
    _append_audit(s, "assignment", "Assigned reviewer", None, {"reviewer_id": str(s.assigned_reviewer_id)}, cu.id)
    from ._submittal_notifications import enqueue_submittal_email

    enqueue_submittal_email(s, "assigned", cu)
    db.session.commit()
    return get_detail(sid, cu)


def transmit_to_ae(sid: uuid.UUID, data: Mapping[str, Any], cu: CurrentUser) -> dict[str, Any]:
    s = _load_submittal_qc(sid)
    if s is None:
        raise ApiError("submittal not found", 404)
    _assert_can_act(s, cu)
    s.submitted_to_ae_at = _utcnow()
    s.status = "submitted_to_ae"
    _advance_if_action(s, "transmit", cu)
    _append_audit(s, "transmit", "Transmitted to GC/AE", None, {"notes": data.get("notes")}, cu.id)
    from ._submittal_notifications import enqueue_submittal_email

    enqueue_submittal_email(s, "transmitted", cu)
    db.session.commit()
    return get_detail(sid, cu)


def log_ae_action(sid: uuid.UUID, data: Mapping[str, Any], cu: CurrentUser) -> dict[str, Any]:
    s = _load_submittal_qc(sid)
    if s is None:
        raise ApiError("submittal not found", 404)
    action = str(data.get("ae_action") or data.get("action") or "").strip()
    if not action:
        raise ApiError("ae_action is required", 400)
    s.ae_action = action[:80]
    s.ae_action_at = _utcnow()
    s.status = "ae_returned"
    _advance_if_action(s, "ae_action", cu)
    _maybe_auto_release(s)
    _append_audit(s, "ae_action", f"AE action {action}", None, {"ae_action": action}, cu.id)
    db.session.commit()
    return get_detail(sid, cu)


def public_upload(token: str, data: Mapping[str, Any]) -> dict[str, Any]:
    raw = (token or "").strip()
    s = db.session.scalar(select(Submittal).where(Submittal.public_token == raw))
    if s is None:
        raise ApiError("submittal not found", 404)
    if s.public_token_expires_at and s.public_token_expires_at < _utcnow():
        raise ApiError("upload token expired", 403)
    file_url = str(data.get("file_url") or "").strip()
    if not file_url:
        raise ApiError("file_url is required", 400)
    if data.get("title"):
        s.title = str(data.get("title")).strip()[:500] or s.title
    if data.get("notes"):
        s.notes = str(data.get("notes")).strip()
    s.received_at = _utcnow()
    s.received_from = (str(data.get("vendor_label") or data.get("received_from") or "").strip()[:300] or s.received_from)
    cu = CurrentUser(user=None, is_dev_admin=True)
    body = sub_svc.add_submittal_attachment(
        s.id,
        {
            "file_url": file_url,
            "title": data.get("title") or data.get("original_filename"),
            "mime_type": data.get("mime_type"),
            "original_filename": data.get("original_filename"),
        },
        cu,
    )
    s2 = _load_submittal_qc(s.id)
    if s2:
        rev = _current_revision(s2)
        doc = db.session.get(Document, uuid.UUID(body["item"]["id"]))
        if rev is not None and doc is not None and doc not in rev.documents:
            rev.documents.append(doc)
        db.session.commit()
    return {"ok": True, "document": body.get("item"), "submittalNumber": s.submittal_number}


def dashboard_summary(cu: CurrentUser, project_id: uuid.UUID | None = None) -> dict[str, Any]:
    stmt = select(Submittal).options(
        selectinload(Submittal.revisions),
        selectinload(Submittal.holds),
    )
    if project_id:
        stmt = stmt.where(Submittal.project_id == project_id)
    rows = db.session.scalars(stmt.limit(1000)).all()
    now = _utcnow()
    week_ago = now - timedelta(days=7)
    overdue = 0
    in_qc_over_48 = 0
    rubber = 0
    blocking = 0
    for s in rows:
        row = register_row(s)
        if row["isOverdue"]:
            overdue += 1
        if s.status == "in_qc" and s.updated_at and (now - s.updated_at) > timedelta(hours=48):
            in_qc_over_48 += 1
        rev = _current_revision(s)
        if rev and rev.rubber_stamp_suspect and rev.review_completed_at and rev.review_completed_at >= week_ago:
            rubber += 1
        if s.action_type != "informational" and s.status not in RELEASE_OK_STATUSES and any(h.is_active and h.hold_type == "procurement" for h in (s.holds or [])):
            blocking += 1
    return {
        "entity": "submittal_dashboard_summary",
        "overdue": overdue,
        "inQcOver48h": in_qc_over_48,
        "rubberStampSuspectThisWeek": rubber,
        "unreleasedBlockingPos": blocking,
    }


def _assert_can_act(s: Submittal, cu: CurrentUser) -> None:
    if _is_admin(cu) or _can_edit_submittal(cu, s):
        return
    if s.workflow_instance_id:
        inst = wf.get_instance(s.workflow_instance_id)
        step = wf.current_ready_step(inst) if inst else None
        if inst and step and wf.can_act_on_step(cu, inst, step):
            return
    raise ApiError("not allowed to act on this submittal", 403)


def submittal_is_released(s: Submittal) -> bool:
    return s.status in RELEASE_OK_STATUSES or s.released_at is not None


def assert_po_line_released(
    *,
    submittal: Submittal | None,
    release_required: bool,
    project: Project,
    spec_hint: str | None = None,
    allow_held_unapproved: bool = False,
) -> None:
    if not release_required:
        return
    if allow_held_unapproved:
        return
    if submittal is None:
        spec = (spec_hint or "").strip()
        div_09_10 = spec.startswith("09") or spec.startswith("10")
        if project.allow_po_without_submittal and not div_09_10:
            return
        if project.allow_po_without_submittal:
            return
        raise ApiError("PO line requires a linked released submittal", 409)
    if submittal_is_released(submittal):
        return
    number = submittal.submittal_number or f"#{submittal.number}"
    raise ApiError(f"Submittal {number} is not released for procurement", 409)


def controlled_copy_html(sid: uuid.UUID, cu: CurrentUser) -> str:
    s = _load_submittal_qc(sid)
    if s is None:
        raise ApiError("submittal not found", 404)
    if not _can_view_submittal(cu, s):
        raise ApiError("not allowed", 403)
    rev = _current_revision(s)
    stamp = (rev.human_stamp or "unreviewed") if rev else "unreviewed"
    watermark = "" if (rev and rev.is_current and s.status != "superseded") else "SUPERSEDED"
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"><title>{s.submittal_number}</title>
<style>body{{font-family:sans-serif;margin:2rem}} .stamp{{border:4px solid #4a1d96;color:#4a1d96;display:inline-block;padding:.5rem 1rem;font-weight:700;text-transform:uppercase}} .wm{{position:fixed;top:40%;left:10%;font-size:5rem;opacity:.15;transform:rotate(-20deg)}}</style>
</head><body>
{"<div class='wm'>SUPERSEDED</div>" if watermark else ""}
<h1>{s.submittal_number} — {s.title}</h1>
<p>Spec {s.spec_section or "—"} · Rev {(rev.revision if rev else s.revision) or "—"} · Status {s.status}</p>
<div class="stamp">Internal QC: {stamp.replace("_", " ")}</div>
<p>Reviewed {rev.review_completed_at.isoformat() if rev and rev.review_completed_at else "—"}</p>
<p>This is the controlled copy generated by USIS. Architect approval is logged separately.</p>
</body></html>"""
