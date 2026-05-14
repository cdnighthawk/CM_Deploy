"""Operational playbook checklist API (Plan 22)."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from flask import Blueprint, request
from sqlalchemy import func, or_, select
from sqlalchemy.orm import joinedload

from ..extensions import db
from ..models import (
    ChecklistRun,
    ChecklistRunStep,
    ChecklistTemplate,
    ChecklistTemplateStep,
    Company,
    Project,
    User,
)
from ._notifications import send_plain_notification_email
from ._perms import CurrentUser, current_user
from .v1 import _iso, _jsonify, _parse_uuid_param


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


def _is_playbook_admin(cu: CurrentUser) -> bool:
    return cu.is_dev_admin or cu.has_role("admin", "superuser")


def _can_start_run(cu: CurrentUser) -> bool:
    """Start runs and list templates: any active user except read-only; admins/dev always."""
    if cu.is_dev_admin or _is_playbook_admin(cu):
        return True
    if cu.id is None:
        return False
    if cu.has_role("read_only", "readonly"):
        return False
    return True


def _default_owner_company_id() -> Optional[uuid.UUID]:
    q1 = (
        select(Company.id)
        .where(Company.company_type == "self", Company.deleted_at.is_(None))
        .order_by(Company.created_at.asc())
        .limit(1)
    )
    cid = db.session.scalar(q1)
    if cid is not None:
        return cid
    q2 = (
        select(Company.id)
        .where(Company.deleted_at.is_(None))
        .order_by(Company.created_at.asc())
        .limit(1)
    )
    return db.session.scalar(q2)


def _template_public(t: ChecklistTemplate) -> dict[str, Any]:
    return {
        "id": str(t.id),
        "company_id": str(t.company_id),
        "name": t.name,
        "description": t.description,
        "is_active": t.is_active,
        "created_at": _iso(t.created_at),
        "updated_at": _iso(t.updated_at),
        "step_count": len(t.steps) if t.steps is not None else 0,
    }


def _template_step_public(s: ChecklistTemplateStep) -> dict[str, Any]:
    return {
        "id": str(s.id),
        "template_id": str(s.template_id),
        "sequence": s.sequence,
        "title": s.title,
        "body": s.body,
        "default_assignee_user_id": str(s.default_assignee_user_id)
        if s.default_assignee_user_id
        else None,
    }


def _run_public(run: ChecklistRun, *, include_steps: bool = False) -> dict[str, Any]:
    steps = list(run.run_steps) if run.run_steps is not None else []
    total = len(steps)
    done = sum(1 for s in steps if s.status in ("done", "skipped"))
    pct = int(round(100 * done / total)) if total else 0
    out: dict[str, Any] = {
        "id": str(run.id),
        "template_id": str(run.template_id),
        "title": run.title,
        "project_id": str(run.project_id) if run.project_id else None,
        "created_by_user_id": str(run.created_by_user_id) if run.created_by_user_id else None,
        "status": run.status,
        "is_blocked": run.is_blocked,
        "created_at": _iso(run.created_at),
        "updated_at": _iso(run.updated_at),
        "progress_percent": pct,
        "step_count": total,
    }
    if include_steps:
        out["steps"] = [_run_step_public(x) for x in sorted(steps, key=lambda x: x.sequence)]
    return out


def _run_step_public(s: ChecklistRunStep) -> dict[str, Any]:
    return {
        "id": str(s.id),
        "run_id": str(s.run_id),
        "sequence": s.sequence,
        "title": s.title,
        "body": s.body,
        "assignee_user_id": str(s.assignee_user_id) if s.assignee_user_id else None,
        "status": s.status,
        "completed_at": _iso(s.completed_at),
        "completed_by_user_id": str(s.completed_by_user_id) if s.completed_by_user_id else None,
    }


def _can_view_run(cu: CurrentUser, run: ChecklistRun) -> bool:
    if _is_playbook_admin(cu):
        return True
    if cu.id and run.created_by_user_id == cu.id:
        return True
    steps = list(run.run_steps or ())
    if cu.id and any(s.assignee_user_id == cu.id for s in steps):
        return True
    return False


def _recompute_run_terminal_status(run: ChecklistRun) -> None:
    steps = list(run.run_steps or ())
    if not steps:
        return
    if run.status == "cancelled":
        return
    if all(s.status in ("done", "skipped") for s in steps):
        run.status = "complete"
    else:
        if run.status == "complete":
            run.status = "open"


def _notify_assignees_for_run(*, run: ChecklistRun, event: str, actor: CurrentUser) -> None:
    seen: set[str] = set()
    actor_email = actor.user.email if actor.user else None
    base = f"Playbook run: {run.title}\nEvent: {event}\nRun id: {run.id}"
    for st in run.run_steps or ():
        uid = st.assignee_user_id
        if uid is None:
            continue
        u = db.session.get(User, uid)
        if u is None or not u.email:
            continue
        if u.email in seen:
            continue
        seen.add(u.email)
        if actor_email:
            body = base + f"\n\n— notified by {actor_email}"
        else:
            body = base
        send_plain_notification_email(to=u.email, subject=f"[USIS Playbook] {run.title}", body=body)


def _notify_user_playbook(*, user_id: uuid.UUID, run: ChecklistRun, event: str, actor: CurrentUser) -> None:
    u = db.session.get(User, user_id)
    if u is None or not u.email:
        return
    actor_email = actor.user.email if actor.user else None
    base = f"Playbook run: {run.title}\nEvent: {event}\nRun id: {run.id}"
    if actor_email:
        body = base + f"\n\n— notified by {actor_email}"
    else:
        body = base
    send_plain_notification_email(to=u.email, subject=f"[USIS Playbook] {run.title}", body=body)


def register_playbook_routes(bp: Blueprint) -> None:
    @bp.get("/playbooks/templates")
    def list_templates():
        cu = current_user()
        if not _can_start_run(cu):
            return _jsonify({"error": "forbidden"}), 403
        company_raw = request.args.get("company_id")
        cid = _parse_uuid_param(company_raw) if company_raw else _default_owner_company_id()
        if cid is None:
            return _jsonify({"items": [], "entity": "checklist_templates", "hint": "no company in database"})
        q = (
            select(ChecklistTemplate)
            .options(joinedload(ChecklistTemplate.steps))
            .where(ChecklistTemplate.company_id == cid)
            .order_by(ChecklistTemplate.name.asc())
        )
        if request.args.get("active_only", "1").strip().lower() in ("1", "true", "yes"):
            q = q.where(ChecklistTemplate.is_active.is_(True))
        rows = db.session.scalars(q).unique().all()
        return _jsonify({"items": [_template_public(t) for t in rows], "entity": "checklist_templates"})

    @bp.post("/playbooks/templates")
    def create_template():
        cu = current_user()
        if not _is_playbook_admin(cu):
            return _jsonify({"error": "admin required to manage templates"}), 403
        data = request.get_json(silent=True) or {}
        name = (data.get("name") or "").strip()
        if not name:
            return _jsonify({"error": "name is required"}), 400
        description = data.get("description")
        description_s = str(description).strip() if description is not None else None
        if description_s == "":
            description_s = None
        cid = _parse_uuid_param(str(data.get("company_id") or "")) if data.get("company_id") else _default_owner_company_id()
        if cid is None:
            return _jsonify({"error": "no company available; create a company first"}), 400
        comp = db.session.get(Company, cid)
        if comp is None or comp.deleted_at is not None:
            return _jsonify({"error": "invalid company_id"}), 400
        t = ChecklistTemplate(
            company_id=cid,
            name=name,
            description=description_s,
            is_active=bool(data.get("is_active", True)),
        )
        db.session.add(t)
        db.session.commit()
        db.session.refresh(t)
        return _jsonify({"item": _template_public(t), "entity": "checklist_template"}), 201

    @bp.get("/playbooks/templates/<template_id>")
    def get_template(template_id: str):
        cu = current_user()
        if not _can_start_run(cu):
            return _jsonify({"error": "forbidden"}), 403
        tid = _parse_uuid_param(template_id)
        if not tid:
            return _jsonify({"error": "invalid template id"}), 400
        t = db.session.scalars(
            select(ChecklistTemplate)
            .options(joinedload(ChecklistTemplate.steps))
            .where(ChecklistTemplate.id == tid)
        ).unique().first()
        return _jsonify(
            {
                "item": _template_public(t),
                "steps": [_template_step_public(s) for s in steps],
                "entity": "checklist_template",
            }
        )

    @bp.patch("/playbooks/templates/<template_id>")
    def patch_template(template_id: str):
        cu = current_user()
        if not _is_playbook_admin(cu):
            return _jsonify({"error": "admin required"}), 403
        tid = _parse_uuid_param(template_id)
        if not tid:
            return _jsonify({"error": "invalid template id"}), 400
        t = db.session.get(ChecklistTemplate, tid)
        if t is None:
            return _jsonify({"error": "not found"}), 404
        data = request.get_json(silent=True) or {}
        if "name" in data:
            n = str(data.get("name") or "").strip()
            if not n:
                return _jsonify({"error": "name cannot be empty"}), 400
            t.name = n
        if "description" in data:
            d = data.get("description")
            t.description = str(d).strip() if d is not None and str(d).strip() else None
        if "is_active" in data:
            t.is_active = bool(data.get("is_active"))
        db.session.commit()
        db.session.refresh(t)
        return _jsonify({"item": _template_public(t), "entity": "checklist_template"})

    @bp.delete("/playbooks/templates/<template_id>")
    def delete_template(template_id: str):
        cu = current_user()
        if not _is_playbook_admin(cu):
            return _jsonify({"error": "admin required"}), 403
        tid = _parse_uuid_param(template_id)
        if not tid:
            return _jsonify({"error": "invalid template id"}), 400
        t = db.session.get(ChecklistTemplate, tid)
        if t is None:
            return _jsonify({"error": "not found"}), 404
        n = db.session.scalar(select(func.count()).select_from(ChecklistRun).where(ChecklistRun.template_id == tid)) or 0
        if int(n) > 0:
            return _jsonify({"error": "template has runs; deactivate instead of delete"}), 409
        db.session.delete(t)
        db.session.commit()
        return _jsonify({"ok": True})

    @bp.put("/playbooks/templates/<template_id>/steps")
    def put_template_steps(template_id: str):
        cu = current_user()
        if not _is_playbook_admin(cu):
            return _jsonify({"error": "admin required"}), 403
        tid = _parse_uuid_param(template_id)
        if not tid:
            return _jsonify({"error": "invalid template id"}), 400
        t = db.session.scalars(
            select(ChecklistTemplate).options(joinedload(ChecklistTemplate.steps)).where(ChecklistTemplate.id == tid)
        ).unique().first()
        if t is None:
            return _jsonify({"error": "not found"}), 404
        data = request.get_json(silent=True) or {}
        raw_steps = data.get("steps")
        if not isinstance(raw_steps, list):
            return _jsonify({"error": "body must include steps array"}), 400
        for old in list(t.steps or ()):
            db.session.delete(old)
        db.session.flush()
        seq = 0
        for row in raw_steps:
            if not isinstance(row, dict):
                continue
            title = str(row.get("title") or "").strip()
            if not title:
                continue
            seq += 1
            body = row.get("body")
            body_s = str(body).strip() if body is not None else None
            if body_s == "":
                body_s = None
            duid = _parse_uuid_param(str(row.get("default_assignee_user_id") or "")) if row.get("default_assignee_user_id") else None
            if duid is not None:
                u = db.session.get(User, duid)
                if u is None:
                    return _jsonify({"error": f"invalid default_assignee_user_id for step {seq}"}), 400
            st = ChecklistTemplateStep(
                template_id=t.id,
                sequence=seq,
                title=title,
                body=body_s,
                default_assignee_user_id=duid,
            )
            db.session.add(st)
        db.session.commit()
        db.session.refresh(t)
        steps = sorted(t.steps or (), key=lambda s: s.sequence)
        return _jsonify({"steps": [_template_step_public(s) for s in steps], "entity": "checklist_template_steps"})

    @bp.post("/playbooks/runs")
    def create_run():
        cu = current_user()
        if not _can_start_run(cu):
            return _jsonify({"error": "forbidden"}), 403
        if cu.id is None and not cu.is_dev_admin:
            return _jsonify({"error": "authenticated user required to start a run"}), 403
        data = request.get_json(silent=True) or {}
        tid = _parse_uuid_param(str(data.get("template_id") or ""))
        if not tid:
            return _jsonify({"error": "template_id is required"}), 400
        t = db.session.scalars(
            select(ChecklistTemplate).options(joinedload(ChecklistTemplate.steps)).where(ChecklistTemplate.id == tid)
        ).unique().first()
        if t is None or not t.is_active:
            return _jsonify({"error": "template not found or inactive"}), 404
        steps = sorted(t.steps or (), key=lambda s: s.sequence)
        if not steps:
            return _jsonify({"error": "template has no steps; edit steps first"}), 400
        project_id = _parse_uuid_param(str(data.get("project_id") or "")) if data.get("project_id") else None
        if project_id is not None:
            proj = db.session.get(Project, project_id)
            if proj is None or proj.deleted_at is not None:
                return _jsonify({"error": "invalid project_id"}), 400
        title = (data.get("title") or "").strip() or t.name
        run = ChecklistRun(
            template_id=t.id,
            title=title,
            project_id=project_id,
            created_by_user_id=cu.id,
            status="open",
            is_blocked=bool(data.get("is_blocked", False)),
        )
        db.session.add(run)
        db.session.flush()
        for st in steps:
            rs = ChecklistRunStep(
                run_id=run.id,
                sequence=st.sequence,
                title=st.title,
                body=st.body,
                assignee_user_id=st.default_assignee_user_id,
                status="pending",
            )
            db.session.add(rs)
        db.session.commit()
        db.session.refresh(run)
        run = db.session.scalars(
            select(ChecklistRun).options(joinedload(ChecklistRun.run_steps)).where(ChecklistRun.id == run.id)
        ).unique().first()
        assert run is not None
        _notify_assignees_for_run(run=run, event="run_started", actor=cu)
        return _jsonify({"item": _run_public(run, include_steps=True), "entity": "checklist_run"}), 201

    @bp.get("/playbooks/runs")
    def list_runs():
        cu = current_user()
        if not _can_start_run(cu):
            return _jsonify({"error": "forbidden"}), 403
        q = select(ChecklistRun).options(joinedload(ChecklistRun.run_steps)).order_by(ChecklistRun.created_at.desc())
        if request.args.get("open_only", "").strip().lower() in ("1", "true", "yes"):
            q = q.where(ChecklistRun.status == "open")
        pid = _parse_uuid_param(request.args.get("project_id") or "")
        if pid:
            q = q.where(ChecklistRun.project_id == pid)
        if request.args.get("mine", "").strip().lower() in ("1", "true", "yes"):
            if cu.id is None:
                return _jsonify({"items": [], "entity": "checklist_runs"})
            subq = select(ChecklistRunStep.run_id).where(ChecklistRunStep.assignee_user_id == cu.id).distinct()
            q = q.where(
                or_(ChecklistRun.created_by_user_id == cu.id, ChecklistRun.id.in_(subq)),
            )
        rows = db.session.scalars(q).unique().all()
        visible = [r for r in rows if _can_view_run(cu, r)]
        return _jsonify({"items": [_run_public(r) for r in visible], "entity": "checklist_runs"})

    @bp.get("/playbooks/runs/<run_id>")
    def get_run(run_id: str):
        cu = current_user()
        rid = _parse_uuid_param(run_id)
        if not rid:
            return _jsonify({"error": "invalid run id"}), 400
        run = db.session.scalars(
            select(ChecklistRun).options(joinedload(ChecklistRun.run_steps)).where(ChecklistRun.id == rid)
        ).unique().first()
        if run is None:
            return _jsonify({"error": "not found"}), 404
        if not _can_view_run(cu, run):
            return _jsonify({"error": "forbidden"}), 403
        return _jsonify({"item": _run_public(run, include_steps=True), "entity": "checklist_run"})

    @bp.patch("/playbooks/runs/<run_id>")
    def patch_run(run_id: str):
        cu = current_user()
        rid = _parse_uuid_param(run_id)
        if not rid:
            return _jsonify({"error": "invalid run id"}), 400
        run = db.session.scalars(
            select(ChecklistRun).options(joinedload(ChecklistRun.run_steps)).where(ChecklistRun.id == rid)
        ).unique().first()
        if run is None:
            return _jsonify({"error": "not found"}), 404
        if not _can_view_run(cu, run):
            return _jsonify({"error": "forbidden"}), 403
        data = request.get_json(silent=True) or {}
        if "is_blocked" in data:
            if not (_is_playbook_admin(cu) or (cu.id and run.created_by_user_id == cu.id)):
                return _jsonify({"error": "only admin or run owner can set blocked"}), 403
            run.is_blocked = bool(data.get("is_blocked"))
        if "status" in data:
            new_s = str(data.get("status") or "").strip().lower()
            if new_s != "cancelled":
                return _jsonify({"error": "only status=cancelled is supported via PATCH; completion is derived from steps"}), 400
            if not (_is_playbook_admin(cu) or (cu.id and run.created_by_user_id == cu.id)):
                return _jsonify({"error": "only admin or run owner can cancel"}), 403
            run.status = "cancelled"
        db.session.commit()
        db.session.refresh(run)
        return _jsonify({"item": _run_public(run, include_steps=True), "entity": "checklist_run"})

    @bp.patch("/playbooks/runs/<run_id>/steps/<step_id>")
    def patch_run_step(run_id: str, step_id: str):
        cu = current_user()
        rid = _parse_uuid_param(run_id)
        sid = _parse_uuid_param(step_id)
        if not rid or not sid:
            return _jsonify({"error": "invalid id"}), 400
        run = db.session.scalars(
            select(ChecklistRun).options(joinedload(ChecklistRun.run_steps)).where(ChecklistRun.id == rid)
        ).unique().first()
        if run is None:
            return _jsonify({"error": "not found"}), 404
        if not _can_view_run(cu, run):
            return _jsonify({"error": "forbidden"}), 403
        step = next((s for s in (run.run_steps or ()) if s.id == sid), None)
        if step is None:
            return _jsonify({"error": "step not found"}), 404
        data = request.get_json(silent=True) or {}
        prev_assignee = step.assignee_user_id
        if "assignee_user_id" in data:
            if not (_is_playbook_admin(cu) or (cu.id and run.created_by_user_id == cu.id)):
                return _jsonify({"error": "only admin or run owner can reassign"}), 403
            raw_a = data.get("assignee_user_id")
            if raw_a is None or raw_a == "":
                step.assignee_user_id = None
            else:
                aid = _parse_uuid_param(str(raw_a))
                if not aid:
                    return _jsonify({"error": "invalid assignee_user_id"}), 400
                u = db.session.get(User, aid)
                if u is None:
                    return _jsonify({"error": "user not found"}), 400
                step.assignee_user_id = aid
        if "status" in data:
            st = str(data.get("status") or "").strip().lower()
            if st not in ("pending", "done", "skipped"):
                return _jsonify({"error": "invalid status"}), 400
            if st in ("done", "skipped"):
                can_complete = _is_playbook_admin(cu) or (cu.id and step.assignee_user_id == cu.id)
                if not can_complete and cu.id and run.created_by_user_id == cu.id and step.assignee_user_id is None:
                    can_complete = True
                if not can_complete:
                    return _jsonify({"error": "only assignee, run owner (unassigned steps), or admin can complete step"}), 403
                step.status = st
                step.completed_at = _utcnow()
                step.completed_by_user_id = cu.id
            else:
                can_reopen = _is_playbook_admin(cu) or (cu.id and step.assignee_user_id == cu.id)
                if not can_reopen and cu.id and run.created_by_user_id == cu.id and step.assignee_user_id is None:
                    can_reopen = True
                if not can_reopen:
                    return _jsonify({"error": "only assignee, run owner (unassigned steps), or admin can reopen step"}), 403
                step.status = "pending"
                step.completed_at = None
                step.completed_by_user_id = None
        db.session.flush()
        _recompute_run_terminal_status(run)
        db.session.commit()
        db.session.refresh(step)
        db.session.refresh(run)
        if step.assignee_user_id and step.assignee_user_id != prev_assignee:
            _notify_user_playbook(user_id=step.assignee_user_id, run=run, event="step_assigned", actor=cu)
        return _jsonify({"item": _run_step_public(step), "run": _run_public(run, include_steps=True), "entity": "checklist_run_step"})
