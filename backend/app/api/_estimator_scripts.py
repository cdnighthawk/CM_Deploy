"""Catalog of estimator scripts + per-estimate bid scope (standard vs GC package)."""
from __future__ import annotations

import re
import uuid
from typing import Any, Mapping

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from ..extensions import db
from ..models import Estimate
from ..models.estimator_script import (
    EstimateBidScope,
    EstimateBidScopeItem,
    EstimatorScript,
    EstimatorStandardSpec,
)
from . import _workflow_service as wf
from ._perms import CurrentUser
from ._rfi_service import ApiError, _parse_uuid

PROCESS_ESTIMATOR_SCOPE = "estimator_scope"

USIS_STANDARD_SPECS: tuple[tuple[str, str, int], ...] = (
    ("09 29 00", "Gypsum Board", 10),
    ("09 91 00", "Painting", 20),
    ("09 65 00", "Resilient Flooring", 30),
    ("09 68 00", "Carpeting", 40),
    ("09 51 00", "Acoustical Ceilings", 50),
    ("06 20 23", "Interior Finish Carpentry", 60),
    ("08 11 13", "Hollow Metal Doors and Frames", 70),
    ("08 71 00", "Door Hardware", 80),
    ("10 00 00", "Division 10 Specialties", 90),
)

SCRIPT_SEEDS: tuple[dict[str, Any], ...] = (
    {
        "script_key": PROCESS_ESTIMATOR_SCOPE,
        "name": "Overall bid-scope pass",
        "kind": "overall",
        "spec_prefixes": [],
        "applies_when": "always",
        "description": "Decide what we are bidding: USIS standard specs, or every spec in a GC bid package.",
        "sort_order": 0,
    },
    {
        "script_key": "spec.gypsum",
        "name": "Gypsum / drywall",
        "kind": "spec",
        "spec_prefixes": ["09 29", "0929"],
        "applies_when": "always",
        "description": "Board types, ratings, shaft walls, accessories.",
        "sort_order": 10,
    },
    {
        "script_key": "spec.paint",
        "name": "Painting",
        "kind": "spec",
        "spec_prefixes": ["09 91", "0991"],
        "applies_when": "always",
        "description": "MPI systems, sheen, VOC, substrates.",
        "sort_order": 20,
    },
    {
        "script_key": "spec.resilient_floor",
        "name": "Resilient flooring",
        "kind": "spec",
        "spec_prefixes": ["09 65", "0965"],
        "applies_when": "always",
        "description": "LVT/VCT, adhesive, moisture, transitions.",
        "sort_order": 30,
    },
    {
        "script_key": "spec.carpet",
        "name": "Carpeting",
        "kind": "spec",
        "spec_prefixes": ["09 68", "0968"],
        "applies_when": "always",
        "description": "Broadloom / tile, attic stock, transitions.",
        "sort_order": 40,
    },
    {
        "script_key": "spec.ceiling",
        "name": "Acoustical ceilings",
        "kind": "spec",
        "spec_prefixes": ["09 51", "0951"],
        "applies_when": "always",
        "description": "Grid, tile, seismic, rated assemblies.",
        "sort_order": 50,
    },
    {
        "script_key": "spec.trim",
        "name": "Finish carpentry / trim",
        "kind": "spec",
        "spec_prefixes": ["06 20", "0620"],
        "applies_when": "always",
        "description": "Trim, millwork, reveal systems.",
        "sort_order": 60,
    },
    {
        "script_key": "spec.doors",
        "name": "Doors and hardware",
        "kind": "spec",
        "spec_prefixes": ["08 11", "08 14", "08 71", "0811", "0814", "0871"],
        "applies_when": "always",
        "description": "HM/wood doors, frames, hardware sets.",
        "sort_order": 70,
    },
    {
        "script_key": "spec.div10",
        "name": "Division 10 specialties",
        "kind": "spec",
        "spec_prefixes": ["10"],
        "applies_when": "always",
        "description": "Lockers, toilet accessories, corners, specialties. Family + frozen snapshot.",
        "sort_order": 90,
    },
)


def _digits(raw: str | None) -> str:
    return re.sub(r"\D", "", str(raw or ""))


def prefix_matches(prefix: str, spec_code: str) -> bool:
    p = _digits(prefix)
    s = _digits(spec_code)
    return bool(p) and bool(s) and s.startswith(p)


def script_public(row: EstimatorScript) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "scriptKey": row.script_key,
        "name": row.name,
        "kind": row.kind,
        "specPrefixes": list(row.spec_prefixes or []),
        "appliesWhen": row.applies_when,
        "description": row.description or "",
        "isActive": row.is_active,
        "sortOrder": row.sort_order,
    }


def standard_spec_public(row: EstimatorStandardSpec) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "specCode": row.spec_code,
        "specTitle": row.spec_title,
        "sortOrder": row.sort_order,
        "isActive": row.is_active,
    }


def ensure_script_catalog() -> None:
    existing = {r.script_key for r in db.session.scalars(select(EstimatorScript)).all()}
    for seed in SCRIPT_SEEDS:
        if seed["script_key"] in existing:
            continue
        db.session.add(
            EstimatorScript(
                script_key=seed["script_key"],
                name=seed["name"],
                kind=seed["kind"],
                spec_prefixes=list(seed.get("spec_prefixes") or []),
                applies_when=seed.get("applies_when") or "always",
                description=seed.get("description"),
                sort_order=int(seed.get("sort_order") or 0),
            )
        )
    specs = {r.spec_code for r in db.session.scalars(select(EstimatorStandardSpec)).all()}
    for code, title, order in USIS_STANDARD_SPECS:
        if code in specs:
            continue
        db.session.add(EstimatorStandardSpec(spec_code=code, spec_title=title, sort_order=order))
    db.session.flush()


def list_scripts(*, kind: str | None = None, active_only: bool = True) -> dict[str, Any]:
    ensure_script_catalog()
    stmt = select(EstimatorScript).order_by(EstimatorScript.sort_order, EstimatorScript.name)
    rows = list(db.session.scalars(stmt).all())
    if kind:
        rows = [r for r in rows if r.kind == kind]
    if active_only:
        rows = [r for r in rows if r.is_active]
    return {"entity": "estimator_scripts", "items": [script_public(r) for r in rows]}


def list_standard_specs() -> dict[str, Any]:
    ensure_script_catalog()
    rows = db.session.scalars(
        select(EstimatorStandardSpec).order_by(EstimatorStandardSpec.sort_order, EstimatorStandardSpec.spec_code)
    ).all()
    return {"entity": "estimator_standard_specs", "items": [standard_spec_public(r) for r in rows if r.is_active]}


def replace_standard_specs(items: list[Mapping[str, Any]], cu: CurrentUser) -> dict[str, Any]:
    if not (cu.is_dev_admin or cu.has_role("admin", "superuser")):
        raise ApiError("not allowed to amend standard specs", 403)
    for row in db.session.scalars(select(EstimatorStandardSpec)).all():
        db.session.delete(row)
    db.session.flush()
    for i, raw in enumerate(items):
        code = str(raw.get("spec_code") or raw.get("specCode") or "").strip()
        title = str(raw.get("spec_title") or raw.get("specTitle") or code).strip()
        if not code:
            continue
        db.session.add(
            EstimatorStandardSpec(
                spec_code=code[:20],
                spec_title=title[:200],
                sort_order=int(raw.get("sort_order") or raw.get("sortOrder") or (i + 1) * 10),
                is_active=bool(raw.get("is_active", raw.get("isActive", True))),
            )
        )
    db.session.commit()
    return list_standard_specs()


def get_script(script_key: str) -> EstimatorScript | None:
    return db.session.scalar(select(EstimatorScript).where(EstimatorScript.script_key == script_key))


def match_script(spec_code: str) -> EstimatorScript | None:
    ensure_script_catalog()
    rows = [
        r
        for r in db.session.scalars(select(EstimatorScript).where(EstimatorScript.kind == "spec")).all()
        if r.is_active
    ]
    ranked: list[tuple[int, EstimatorScript]] = []
    for row in rows:
        for prefix in row.spec_prefixes or []:
            if prefix_matches(str(prefix), spec_code):
                ranked.append((len(_digits(str(prefix))), row))
                break
    if not ranked:
        return None
    ranked.sort(key=lambda x: (-x[0], x[1].sort_order))
    return ranked[0][1]


def upsert_script(data: Mapping[str, Any], cu: CurrentUser) -> EstimatorScript:
    if not (cu.is_dev_admin or cu.has_role("admin", "superuser")):
        raise ApiError("not allowed to amend scripts", 403)
    key = str(data.get("script_key") or data.get("scriptKey") or "").strip()
    if not key:
        raise ApiError("script_key is required", 400)
    row = get_script(key)
    if row is None:
        row = EstimatorScript(script_key=key[:80], name=key, kind="spec")
        db.session.add(row)
    if data.get("name"):
        row.name = str(data.get("name"))[:200]
    if data.get("kind"):
        kind = str(data.get("kind")).strip()
        if kind not in ("overall", "spec"):
            raise ApiError("kind must be overall or spec", 400)
        row.kind = kind
    if "spec_prefixes" in data or "specPrefixes" in data:
        raw = data.get("spec_prefixes") if "spec_prefixes" in data else data.get("specPrefixes")
        row.spec_prefixes = [str(x).strip() for x in (raw or []) if str(x).strip()]
    if data.get("applies_when") or data.get("appliesWhen"):
        row.applies_when = str(data.get("applies_when") or data.get("appliesWhen"))[:40]
    if "description" in data:
        row.description = str(data.get("description") or "") or None
    if "is_active" in data or "isActive" in data:
        row.is_active = bool(data.get("is_active") if "is_active" in data else data.get("isActive"))
    if data.get("sort_order") is not None or data.get("sortOrder") is not None:
        row.sort_order = int(data.get("sort_order") or data.get("sortOrder") or 0)
    db.session.flush()
    wf.ensure_default_definition(process_key=row.script_key, project_id=None)
    db.session.commit()
    return row


def _item_public(item: EstimateBidScopeItem) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "specCode": item.spec_code,
        "specTitle": item.spec_title,
        "scriptKey": item.script_key,
        "included": item.included,
        "itemSource": item.item_source,
        "status": item.status,
        "sortOrder": item.sort_order,
        "workflowInstanceId": str(item.workflow_instance_id) if item.workflow_instance_id else None,
    }


def scope_public(scope: EstimateBidScope) -> dict[str, Any]:
    return {
        "id": str(scope.id),
        "estimateId": str(scope.estimate_id),
        "source": scope.source,
        "bidPackageLabel": scope.bid_package_label,
        "notes": scope.notes,
        "status": scope.status,
        "items": [_item_public(i) for i in (scope.items or [])],
    }


def _get_estimate(estimate_id: uuid.UUID) -> Estimate:
    est = db.session.get(Estimate, estimate_id)
    if est is None:
        raise ApiError("estimate not found", 404)
    return est


def get_scope(estimate_id: uuid.UUID) -> EstimateBidScope | None:
    return db.session.scalar(
        select(EstimateBidScope)
        .options(selectinload(EstimateBidScope.items))
        .where(EstimateBidScope.estimate_id == estimate_id)
    )


def ensure_scope_from_standard(estimate_id: uuid.UUID) -> EstimateBidScope:
    existing = get_scope(estimate_id)
    if existing is not None:
        return existing
    _get_estimate(estimate_id)
    ensure_script_catalog()
    scope = EstimateBidScope(estimate_id=estimate_id, source="standard", status="draft")
    db.session.add(scope)
    db.session.flush()
    specs = db.session.scalars(
        select(EstimatorStandardSpec)
        .where(EstimatorStandardSpec.is_active.is_(True))
        .order_by(EstimatorStandardSpec.sort_order)
    ).all()
    for i, spec in enumerate(specs):
        script = match_script(spec.spec_code)
        db.session.add(
            EstimateBidScopeItem(
                scope_id=scope.id,
                spec_code=spec.spec_code,
                spec_title=spec.spec_title,
                script_key=script.script_key if script else None,
                included=True,
                item_source="standard",
                sort_order=i + 1,
            )
        )
    db.session.flush()
    return get_scope(estimate_id) or scope


def replace_scope(estimate_id: uuid.UUID, data: Mapping[str, Any]) -> EstimateBidScope:
    _get_estimate(estimate_id)
    scope = get_scope(estimate_id)
    if scope is None:
        scope = EstimateBidScope(estimate_id=estimate_id, source="standard", status="draft")
        db.session.add(scope)
        db.session.flush()
    source = str(data.get("source") or scope.source or "standard").strip()
    if source not in ("standard", "bid_package", "mixed"):
        raise ApiError("source must be standard, bid_package, or mixed", 400)
    scope.source = source
    if "bid_package_label" in data or "bidPackageLabel" in data:
        label = data.get("bid_package_label") if "bid_package_label" in data else data.get("bidPackageLabel")
        scope.bid_package_label = (str(label).strip() or None) if label else None
    if "notes" in data:
        scope.notes = str(data.get("notes") or "") or None
    items_raw = data.get("items")
    if isinstance(items_raw, list):
        for old in list(scope.items or []):
            db.session.delete(old)
        db.session.flush()
        for i, raw in enumerate(items_raw):
            if not isinstance(raw, Mapping):
                continue
            code = str(raw.get("spec_code") or raw.get("specCode") or "").strip()
            if not code:
                continue
            title = str(raw.get("spec_title") or raw.get("specTitle") or code).strip()
            script_key = raw.get("script_key") or raw.get("scriptKey")
            if not script_key:
                matched = match_script(code)
                script_key = matched.script_key if matched else None
            included = raw.get("included")
            if included is None:
                included = True
            db.session.add(
                EstimateBidScopeItem(
                    scope_id=scope.id,
                    spec_code=code[:20],
                    spec_title=title[:200],
                    script_key=(str(script_key)[:80] if script_key else None),
                    included=bool(included),
                    item_source=str(raw.get("item_source") or raw.get("itemSource") or source)[:40],
                    status=str(raw.get("status") or "pending")[:40],
                    sort_order=int(raw.get("sort_order") or raw.get("sortOrder") or i + 1),
                )
            )
        scope.status = "draft"
    db.session.flush()
    loaded = get_scope(estimate_id)
    if loaded is None:
        raise ApiError("bid scope missing after save", 500)
    return loaded


def confirm_scope(estimate_id: uuid.UUID) -> EstimateBidScope:
    scope = get_scope(estimate_id) or ensure_scope_from_standard(estimate_id)
    if not any(i.included for i in (scope.items or [])):
        raise ApiError("confirm at least one spec", 400)
    scope.status = "confirmed"
    db.session.flush()
    return scope


def enqueue_spec_scripts(estimate_id: uuid.UUID, cu: CurrentUser | None = None) -> dict[str, Any]:
    scope = get_scope(estimate_id)
    if scope is None:
        raise ApiError("run the overall pass and save a bid set first", 409)
    if scope.status != "confirmed":
        confirm_scope(estimate_id)
        scope = get_scope(estimate_id)
    if scope is None:
        raise ApiError("bid scope missing", 500)
    est = _get_estimate(estimate_id)
    started = []
    for item in scope.items or []:
        if not item.included:
            continue
        key = item.script_key
        if not key:
            matched = match_script(item.spec_code)
            key = matched.script_key if matched else None
        if not key:
            item.status = "no_script"
            continue
        inst = wf.ensure_instance(
            process_key=key,
            subject_type="estimate",
            subject_id=estimate_id,
            project_id=est.project_id,
            cu=cu,
        )
        item.script_key = key
        item.workflow_instance_id = inst.id
        item.status = "queued" if inst.status == "open" else inst.status
        started.append({"specCode": item.spec_code, "scriptKey": key, "instanceId": str(inst.id)})
    db.session.flush()
    return {"entity": "estimate_bid_scope", "item": scope_public(scope), "started": started}


def seed_steps_for_script(script: EstimatorScript) -> list[dict[str, Any]]:
    if script.kind == "overall":
        return []
    label = script.name
    prefixes = ", ".join(script.spec_prefixes or []) or label
    return [
        {
            "step_key": "spec_review",
            "label": f"{label} first-pass review",
            "sort_order": 1,
            "queue_key": "estimator",
            "required_actions": ["run_ai_review"],
            "on_approve_status": None,
            "entry_condition": None,
            "skippable": False,
            "automation": {
                "action": "run_ai_review",
                "mode": "construction_review",
                "auto_complete": True,
                "prompt": (
                    f"First-pass review for {label} ({prefixes}). Use this spec's rules only. "
                    "List scope on the sheet, missing dimensions, finish-schedule mismatches, "
                    "and leftovers. Structured findings: severity, title, detail, drawing_ref."
                ),
                "system_hint": f"Spec script {script.script_key}. Do not wander into other trades.",
            },
        },
        {
            "step_key": "spec_takeoff",
            "label": f"{label} takeoff propose",
            "sort_order": 2,
            "queue_key": "estimator",
            "required_actions": ["run_ai_review"],
            "on_approve_status": None,
            "entry_condition": None,
            "skippable": False,
            "automation": {
                "action": "run_ai_review",
                "mode": "estimating_review",
                "auto_complete": True,
                "prompt": (
                    f"Propose takeoff lines for {label} only. JSON "
                    '{{"lines":[{{"description":"","unit":"","qty":null,"location":"","notes":""}}],'
                    '"exclusions":[],"assumptions":[]}}. Qty null unless the sheet states it.'
                ),
                "system_hint": f"Spec script {script.script_key}. No catalog SKUs.",
            },
        },
        {
            "step_key": "persist_notes",
            "label": "Save notes",
            "sort_order": 3,
            "queue_key": "estimator",
            "required_actions": ["persist_ai_annotations"],
            "on_approve_status": None,
            "entry_condition": None,
            "skippable": True,
            "automation": {"action": "persist_findings", "auto_complete": True},
        },
        {
            "step_key": "human_apply",
            "label": "Estimator leftovers",
            "sort_order": 4,
            "queue_key": "reviewer",
            "required_actions": ["apply_to_line"],
            "on_approve_status": None,
            "entry_condition": None,
            "skippable": True,
            "automation": {"action": "human_accept", "auto_complete": False},
        },
    ]
