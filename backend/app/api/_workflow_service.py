"""Shared amendable workflow engine (definitions, queues, frozen instances)."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Mapping

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from ..extensions import db
from ..models import (
    AuditLog,
    User,
    WorkflowDefinition,
    WorkflowDefinitionStep,
    WorkflowInstance,
    WorkflowInstanceStep,
    WorkflowQueue,
    WorkflowQueueMember,
)
from ._perms import CurrentUser
from ._rfi_service import ApiError, _parse_uuid

PROCESS_SUBMITTAL_QC = "submittal_qc"

DEFAULT_QUEUES = (
    ("intake", "Intake / completeness"),
    ("trade_qc", "Trade QC"),
    ("pm", "Project management"),
)

DEFAULT_SUBMITTAL_QC_STEPS: list[dict[str, Any]] = [
    {
        "step_key": "log_completeness",
        "label": "Log & completeness",
        "sort_order": 1,
        "queue_key": "intake",
        "required_actions": ["completeness"],
        "on_approve_status": "in_qc",
        "entry_condition": None,
        "skippable": False,
    },
    {
        "step_key": "local_ai_review",
        "label": "Local AI review",
        "sort_order": 2,
        "queue_key": "trade_qc",
        "required_actions": ["run_ai_review"],
        "on_approve_status": "in_qc",
        "entry_condition": None,
        "skippable": False,
    },
    {
        "step_key": "trade_qc_stamp",
        "label": "Trade QC stamp",
        "sort_order": 3,
        "queue_key": "trade_qc",
        "required_actions": ["complete_checklist", "stamp"],
        "on_approve_status": None,
        "entry_condition": None,
        "skippable": False,
    },
    {
        "step_key": "transmit_ae",
        "label": "Transmit to GC/AE",
        "sort_order": 4,
        "queue_key": "pm",
        "required_actions": ["transmit"],
        "on_approve_status": "submitted_to_ae",
        "entry_condition": "not_informational",
        "skippable": True,
    },
    {
        "step_key": "log_ae_action",
        "label": "Log AE action",
        "sort_order": 5,
        "queue_key": "pm",
        "required_actions": ["ae_action"],
        "on_approve_status": "ae_returned",
        "entry_condition": "require_ae_before_release",
        "skippable": True,
    },
    {
        "step_key": "release_holds",
        "label": "Release holds",
        "sort_order": 6,
        "queue_key": "pm",
        "required_actions": ["release"],
        "on_approve_status": "released",
        "entry_condition": None,
        "skippable": False,
    },
]


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


def _user_name(u: User | None) -> str | None:
    if u is None:
        return None
    name = " ".join(p for p in (u.first_name, u.last_name) if p).strip()
    return name or u.email


def _is_admin(cu: CurrentUser) -> bool:
    return cu.is_dev_admin or cu.has_role("admin", "superuser")


def _audit(
    *,
    cu: CurrentUser | None,
    entity_type: str,
    entity_id: uuid.UUID | None,
    action: str,
    message: str,
    changes: dict[str, Any] | None = None,
) -> None:
    db.session.add(
        AuditLog(
            user_id=cu.id if cu else None,
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            message=message,
            changes=changes,
        )
    )


def _step_snapshot(step: WorkflowDefinitionStep | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(step, Mapping):
        return {
            "step_key": step["step_key"],
            "label": step["label"],
            "sort_order": int(step.get("sort_order") or 0),
            "queue_key": step.get("queue_key"),
            "required_actions": list(step.get("required_actions") or []),
            "on_approve_status": step.get("on_approve_status"),
            "entry_condition": step.get("entry_condition"),
            "skippable": bool(step.get("skippable")),
        }
    return {
        "step_key": step.step_key,
        "label": step.label,
        "sort_order": step.sort_order,
        "queue_key": step.queue_key,
        "required_actions": list(step.required_actions or []),
        "on_approve_status": step.on_approve_status,
        "entry_condition": step.entry_condition,
        "skippable": bool(step.skippable),
    }


def ensure_default_queues(process_key: str = PROCESS_SUBMITTAL_QC) -> None:
    existing = {
        q.queue_key
        for q in db.session.scalars(select(WorkflowQueue).where(WorkflowQueue.process_key == process_key)).all()
    }
    for key, name in DEFAULT_QUEUES:
        if key not in existing:
            db.session.add(WorkflowQueue(process_key=process_key, queue_key=key, name=name))


def ensure_default_definition(
    *,
    process_key: str = PROCESS_SUBMITTAL_QC,
    project_id: uuid.UUID | None = None,
) -> WorkflowDefinition:
    ensure_default_queues(process_key)
    stmt = select(WorkflowDefinition).where(
        WorkflowDefinition.process_key == process_key,
        WorkflowDefinition.project_id == project_id,
        WorkflowDefinition.is_published.is_(True),
    ).order_by(WorkflowDefinition.version.desc())
    published = db.session.scalars(stmt).first()
    if published is not None:
        return published

    latest = db.session.scalars(
        select(WorkflowDefinition)
        .where(WorkflowDefinition.process_key == process_key, WorkflowDefinition.project_id == project_id)
        .order_by(WorkflowDefinition.version.desc())
    ).first()
    version = (latest.version + 1) if latest else 1
    definition = WorkflowDefinition(
        process_key=process_key,
        version=version,
        name="Submittal QC (default)",
        project_id=project_id,
        is_published=True,
        published_at=_utcnow(),
        notes="Seeded default. Admins may publish a new version to change steps/queues.",
    )
    db.session.add(definition)
    db.session.flush()
    for row in DEFAULT_SUBMITTAL_QC_STEPS:
        db.session.add(
            WorkflowDefinitionStep(
                definition_id=definition.id,
                step_key=row["step_key"],
                label=row["label"],
                sort_order=row["sort_order"],
                queue_key=row["queue_key"],
                required_actions=row["required_actions"],
                on_approve_status=row["on_approve_status"],
                entry_condition=row["entry_condition"],
                skippable=row["skippable"],
            )
        )
    db.session.flush()
    return definition


def published_definition(process_key: str, project_id: uuid.UUID | None = None) -> WorkflowDefinition:
    if project_id is not None:
        scoped = db.session.scalars(
            select(WorkflowDefinition)
            .options(selectinload(WorkflowDefinition.steps))
            .where(
                WorkflowDefinition.process_key == process_key,
                WorkflowDefinition.project_id == project_id,
                WorkflowDefinition.is_published.is_(True),
            )
            .order_by(WorkflowDefinition.version.desc())
        ).first()
        if scoped is not None:
            return scoped
    global_def = db.session.scalars(
        select(WorkflowDefinition)
        .options(selectinload(WorkflowDefinition.steps))
        .where(
            WorkflowDefinition.process_key == process_key,
            WorkflowDefinition.project_id.is_(None),
            WorkflowDefinition.is_published.is_(True),
        )
        .order_by(WorkflowDefinition.version.desc())
    ).first()
    if global_def is not None:
        return global_def
    return ensure_default_definition(process_key=process_key, project_id=None)


def start_instance(
    *,
    process_key: str,
    subject_type: str,
    subject_id: uuid.UUID,
    project_id: uuid.UUID | None = None,
    cu: CurrentUser | None = None,
) -> WorkflowInstance:
    definition = published_definition(process_key, project_id)
    steps = list(definition.steps or [])
    if not steps:
        raise ApiError("workflow definition has no steps", 400)
    snapshot = [_step_snapshot(s) for s in steps]
    instance = WorkflowInstance(
        process_key=process_key,
        definition_id=definition.id,
        definition_version=definition.version,
        snapshot=snapshot,
        subject_type=subject_type,
        subject_id=subject_id,
        status="open",
        current_step_key=snapshot[0]["step_key"],
    )
    db.session.add(instance)
    db.session.flush()
    for i, row in enumerate(snapshot):
        db.session.add(
            WorkflowInstanceStep(
                instance_id=instance.id,
                step_key=row["step_key"],
                label=row["label"],
                sort_order=row["sort_order"],
                queue_key=row["queue_key"],
                required_actions=row["required_actions"],
                on_approve_status=row["on_approve_status"],
                entry_condition=row["entry_condition"],
                skippable=bool(row.get("skippable")),
                status="ready" if i == 0 else "pending",
            )
        )
    db.session.flush()
    _audit(
        cu=cu,
        entity_type="workflow_instance",
        entity_id=instance.id,
        action="start",
        message=f"Started {process_key} v{definition.version}",
        changes={"subject_type": subject_type, "subject_id": str(subject_id)},
    )
    return instance


def get_instance(instance_id: uuid.UUID) -> WorkflowInstance | None:
    return db.session.scalars(
        select(WorkflowInstance)
        .where(WorkflowInstance.id == instance_id)
        .options(selectinload(WorkflowInstance.steps))
    ).first()


def current_ready_step(instance: WorkflowInstance) -> WorkflowInstanceStep | None:
    ready = [s for s in (instance.steps or []) if s.status == "ready"]
    if ready:
        return min(ready, key=lambda s: s.sort_order)
    return None


def queue_member_ids(process_key: str, queue_key: str | None) -> set[uuid.UUID]:
    if not queue_key:
        return set()
    queue = db.session.scalar(
        select(WorkflowQueue).where(
            WorkflowQueue.process_key == process_key,
            WorkflowQueue.queue_key == queue_key,
        )
    )
    if queue is None:
        return set()
    rows = db.session.scalars(
        select(WorkflowQueueMember.user_id).where(WorkflowQueueMember.queue_id == queue.id)
    ).all()
    return set(rows)


def can_act_on_step(cu: CurrentUser, instance: WorkflowInstance, step: WorkflowInstanceStep) -> bool:
    if _is_admin(cu) or cu.is_dev_admin:
        return True
    if cu.id is None:
        return False
    if step.assignee_user_id and step.assignee_user_id == cu.id:
        return True
    return cu.id in queue_member_ids(instance.process_key, step.queue_key)


def assign_instance_step(
    instance_id: uuid.UUID,
    data: Mapping[str, Any],
    cu: CurrentUser,
) -> WorkflowInstance:
    instance = get_instance(instance_id)
    if instance is None:
        raise ApiError("workflow instance not found", 404)
    step_key = (str(data.get("step_key") or instance.current_step_key or "")).strip()
    step = next((s for s in instance.steps if s.step_key == step_key), None)
    if step is None:
        raise ApiError("step not found on instance", 404)
    if not (_is_admin(cu) or cu.id in queue_member_ids(instance.process_key, step.queue_key)):
        raise ApiError("not allowed to assign this queue", 403)
    uid = _parse_uuid(data.get("user_id") or data.get("assignee_user_id"))
    if uid is None:
        raise ApiError("user_id is required", 400)
    members = queue_member_ids(instance.process_key, step.queue_key)
    if step.queue_key and uid not in members:
        raise ApiError("user is not in the live queue for this step", 409)
    user = db.session.get(User, uid)
    if user is None:
        raise ApiError("user not found", 404)
    step.assignee_user_id = uid
    if step.status == "pending":
        step.status = "ready"
        instance.current_step_key = step.step_key
    _audit(
        cu=cu,
        entity_type="workflow_instance",
        entity_id=instance.id,
        action="assign",
        message=f"Assigned {step.step_key} to {user.email}",
        changes={"step_key": step.step_key, "user_id": str(uid)},
    )
    db.session.flush()
    return instance


def complete_step(
    instance: WorkflowInstance,
    step_key: str,
    *,
    cu: CurrentUser | None = None,
    skip: bool = False,
) -> WorkflowInstanceStep:
    step = next((s for s in instance.steps if s.step_key == step_key), None)
    if step is None:
        raise ApiError("step not found on instance", 404)
    step.status = "skipped" if skip else "complete"
    step.completed_at = _utcnow()
    step.completed_by_user_id = cu.id if cu else None
    remaining = sorted(
        [s for s in instance.steps if s.status in ("pending", "ready")],
        key=lambda s: s.sort_order,
    )
    if remaining:
        nxt = remaining[0]
        nxt.status = "ready"
        instance.current_step_key = nxt.step_key
        instance.status = "open"
    else:
        instance.current_step_key = None
        instance.status = "complete"
    db.session.flush()
    return step


def instance_public(instance: WorkflowInstance) -> dict[str, Any]:
    steps_out = []
    for s in sorted(instance.steps or [], key=lambda x: x.sort_order):
        assignee = db.session.get(User, s.assignee_user_id) if s.assignee_user_id else None
        steps_out.append(
            {
                "id": str(s.id),
                "stepKey": s.step_key,
                "label": s.label,
                "sortOrder": s.sort_order,
                "queueKey": s.queue_key,
                "requiredActions": list(s.required_actions or []),
                "onApproveStatus": s.on_approve_status,
                "entryCondition": s.entry_condition,
                "skippable": s.skippable,
                "status": s.status,
                "assigneeUserId": str(s.assignee_user_id) if s.assignee_user_id else None,
                "assigneeName": _user_name(assignee),
                "completedAt": _iso(s.completed_at),
            }
        )
    return {
        "id": str(instance.id),
        "processKey": instance.process_key,
        "definitionId": str(instance.definition_id) if instance.definition_id else None,
        "definitionVersion": instance.definition_version,
        "snapshot": instance.snapshot,
        "status": instance.status,
        "currentStepKey": instance.current_step_key,
        "steps": steps_out,
    }


def definition_public(definition: WorkflowDefinition) -> dict[str, Any]:
    return {
        "id": str(definition.id),
        "processKey": definition.process_key,
        "version": definition.version,
        "name": definition.name,
        "projectId": str(definition.project_id) if definition.project_id else None,
        "isPublished": definition.is_published,
        "publishedAt": _iso(definition.published_at),
        "steps": [_step_snapshot(s) | {"id": str(s.id)} for s in (definition.steps or [])],
    }


def publish_definition(data: Mapping[str, Any], cu: CurrentUser) -> WorkflowDefinition:
    if not _is_admin(cu):
        raise ApiError("not allowed to publish workflow definitions", 403)
    process_key = str(data.get("process_key") or PROCESS_SUBMITTAL_QC).strip()
    project_id = _parse_uuid(data.get("project_id"))
    steps_raw = data.get("steps")
    if not isinstance(steps_raw, list) or not steps_raw:
        raise ApiError("steps array is required", 400)
    latest = db.session.scalars(
        select(WorkflowDefinition)
        .where(WorkflowDefinition.process_key == process_key, WorkflowDefinition.project_id == project_id)
        .order_by(WorkflowDefinition.version.desc())
    ).first()
    version = (latest.version + 1) if latest else 1
    definition = WorkflowDefinition(
        process_key=process_key,
        version=version,
        name=str(data.get("name") or f"{process_key} v{version}")[:200],
        project_id=project_id,
        is_published=True,
        published_at=_utcnow(),
        notes=(str(data.get("notes")).strip() or None) if data.get("notes") else None,
        created_by_user_id=cu.id,
    )
    db.session.add(definition)
    db.session.flush()
    for i, row in enumerate(steps_raw):
        if not isinstance(row, Mapping):
            raise ApiError("each step must be an object", 400)
        db.session.add(
            WorkflowDefinitionStep(
                definition_id=definition.id,
                step_key=str(row.get("step_key") or row.get("stepKey") or f"step_{i + 1}")[:80],
                label=str(row.get("label") or f"Step {i + 1}")[:200],
                sort_order=int(row.get("sort_order") or row.get("sortOrder") or i + 1),
                queue_key=(str(row.get("queue_key") or row.get("queueKey") or "").strip() or None),
                required_actions=list(row.get("required_actions") or row.get("requiredActions") or []),
                on_approve_status=(
                    str(row.get("on_approve_status") or row.get("onApproveStatus") or "").strip() or None
                ),
                entry_condition=(
                    str(row.get("entry_condition") or row.get("entryCondition") or "").strip() or None
                ),
                skippable=bool(row.get("skippable")),
            )
        )
    _audit(
        cu=cu,
        entity_type="workflow_definition",
        entity_id=definition.id,
        action="publish",
        message=f"Published {process_key} v{version}",
    )
    db.session.commit()
    return published_definition(process_key, project_id)


def list_definitions(process_key: str, project_id: uuid.UUID | None = None) -> dict[str, Any]:
    stmt = (
        select(WorkflowDefinition)
        .options(selectinload(WorkflowDefinition.steps))
        .where(WorkflowDefinition.process_key == process_key)
        .order_by(WorkflowDefinition.version.desc())
    )
    rows = db.session.scalars(stmt).all()
    if project_id is not None:
        rows = [r for r in rows if r.project_id in (None, project_id)]
    return {"entity": "workflow_definitions", "items": [definition_public(r) for r in rows]}


def set_queue_members(process_key: str, queue_key: str, user_ids: list[uuid.UUID], cu: CurrentUser) -> dict[str, Any]:
    if not _is_admin(cu):
        raise ApiError("not allowed to amend queues", 403)
    ensure_default_queues(process_key)
    queue = db.session.scalar(
        select(WorkflowQueue).where(
            WorkflowQueue.process_key == process_key,
            WorkflowQueue.queue_key == queue_key,
        )
    )
    if queue is None:
        raise ApiError("queue not found", 404)
    existing = db.session.scalars(select(WorkflowQueueMember).where(WorkflowQueueMember.queue_id == queue.id)).all()
    for row in existing:
        db.session.delete(row)
    for uid in user_ids:
        if db.session.get(User, uid) is None:
            raise ApiError(f"user not found: {uid}", 404)
        db.session.add(WorkflowQueueMember(queue_id=queue.id, user_id=uid))
    _audit(
        cu=cu,
        entity_type="workflow_queue",
        entity_id=queue.id,
        action="members",
        message=f"Updated {process_key}/{queue_key} membership",
        changes={"user_ids": [str(u) for u in user_ids]},
    )
    db.session.commit()
    return queue_public(queue)


def queue_public(queue: WorkflowQueue) -> dict[str, Any]:
    members = []
    rows = db.session.scalars(
        select(WorkflowQueueMember)
        .options(selectinload(WorkflowQueueMember.user))
        .where(WorkflowQueueMember.queue_id == queue.id)
    ).all()
    for m in rows:
        members.append(
            {
                "userId": str(m.user_id),
                "name": _user_name(m.user),
                "email": m.user.email if m.user else None,
            }
        )
    return {
        "id": str(queue.id),
        "processKey": queue.process_key,
        "queueKey": queue.queue_key,
        "name": queue.name,
        "members": members,
    }


def list_queues(process_key: str) -> dict[str, Any]:
    ensure_default_queues(process_key)
    rows = db.session.scalars(select(WorkflowQueue).where(WorkflowQueue.process_key == process_key)).all()
    return {"entity": "workflow_queues", "items": [queue_public(q) for q in rows]}
