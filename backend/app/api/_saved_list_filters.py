"""Personal saved list-query presets (Leads filter drawer)."""
from __future__ import annotations

import uuid
from typing import Any, Mapping

from flask import Blueprint
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from ..extensions import db
from ..models import AuditLog, SavedListFilter
from ._perms import current_user

ALLOWED_TABLE_KEYS = frozenset({"crm.leads"})


class SavedFilterError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message = message
        self.status = status


def _jsonify(obj: Any):
    from flask import jsonify

    return jsonify(obj)


def _require_user():
    cu = current_user()
    if cu.user is None or cu.id is None:
        raise SavedFilterError("sign in required", 401)
    return cu


def _parse_uuid(raw: str | None) -> uuid.UUID | None:
    if not raw or not str(raw).strip():
        return None
    try:
        return uuid.UUID(str(raw).strip())
    except ValueError:
        return None


def _clean_table_key(raw: Any) -> str:
    key = str(raw or "").strip()
    if key not in ALLOWED_TABLE_KEYS:
        raise SavedFilterError("table_key must be crm.leads", 400)
    return key


def _clean_name(raw: Any) -> str:
    name = str(raw or "").strip()
    if not name:
        raise SavedFilterError("name is required", 400)
    return name[:80]


def _clean_query(raw: Any) -> dict[str, Any]:
    if raw is None:
        return {}
    if not isinstance(raw, Mapping):
        raise SavedFilterError("query_json must be an object", 400)
    out: dict[str, Any] = {}
    for k, v in raw.items():
        key = str(k).strip()
        if not key or key.startswith("_"):
            continue
        out[key] = v
    return out


def _public(row: SavedListFilter) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "user_id": str(row.user_id),
        "table_key": row.table_key,
        "name": row.name,
        "query_json": row.query_json or {},
        "is_default": bool(row.is_default),
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def _audit(cu, row: SavedListFilter, action: str, changes: dict[str, Any] | None = None) -> None:
    db.session.add(
        AuditLog(
            user_id=cu.user.id if cu.user else None,
            entity_type="saved_list_filter",
            entity_id=row.id,
            action=action,
            changes=changes,
            message=f"{action} saved filter {row.name!r} ({row.table_key})",
        )
    )


def _clear_other_defaults(user_id: uuid.UUID, table_key: str, keep_id: uuid.UUID | None) -> None:
    q = select(SavedListFilter).where(
        SavedListFilter.user_id == user_id,
        SavedListFilter.table_key == table_key,
        SavedListFilter.is_default.is_(True),
    )
    if keep_id is not None:
        q = q.where(SavedListFilter.id != keep_id)
    for other in db.session.scalars(q).all():
        other.is_default = False


def _owned(filter_id: uuid.UUID, user_id: uuid.UUID) -> SavedListFilter:
    row = db.session.get(SavedListFilter, filter_id)
    if row is None or row.user_id != user_id:
        raise SavedFilterError("saved filter not found", 404)
    return row


def list_saved_filters(table_key: str, cu) -> dict[str, Any]:
    rows = db.session.scalars(
        select(SavedListFilter)
        .where(SavedListFilter.user_id == cu.id, SavedListFilter.table_key == table_key)
        .order_by(SavedListFilter.name.asc())
    ).all()
    return {"items": [_public(r) for r in rows], "entity": "saved_list_filters"}


def create_saved_filter(data: Mapping[str, Any], cu, *, overwrite: bool = False) -> dict[str, Any]:
    table_key = _clean_table_key(data.get("table_key"))
    name = _clean_name(data.get("name"))
    query_json = _clean_query(data.get("query_json") if "query_json" in data else data.get("query"))
    is_default = bool(data.get("is_default"))

    existing = db.session.scalar(
        select(SavedListFilter).where(
            SavedListFilter.user_id == cu.id,
            SavedListFilter.table_key == table_key,
            SavedListFilter.name == name,
        )
    )
    if existing is not None:
        if not overwrite:
            raise SavedFilterError("a saved filter with that name already exists", 409)
        existing.query_json = query_json
        if is_default:
            _clear_other_defaults(cu.id, table_key, existing.id)
            db.session.flush()
        existing.is_default = is_default
        _audit(cu, existing, "update", {"overwrite": True, "name": name})
        db.session.commit()
        return {"item": _public(existing), "entity": "saved_list_filter", "overwritten": True}

    if is_default:
        _clear_other_defaults(cu.id, table_key, None)
        db.session.flush()
    row = SavedListFilter(
        user_id=cu.id,
        table_key=table_key,
        name=name,
        query_json=query_json,
        is_default=is_default,
    )
    db.session.add(row)
    _audit(cu, row, "create", {"name": name, "table_key": table_key})
    try:
        db.session.commit()
    except IntegrityError as exc:
        db.session.rollback()
        raise SavedFilterError("a saved filter with that name already exists", 409) from exc
    return {"item": _public(row), "entity": "saved_list_filter"}


def update_saved_filter(filter_id: uuid.UUID, data: Mapping[str, Any], cu) -> dict[str, Any]:
    row = _owned(filter_id, cu.id)
    changes: dict[str, Any] = {}
    if "name" in data and data.get("name") is not None:
        row.name = _clean_name(data.get("name"))
        changes["name"] = row.name
    if "query_json" in data or "query" in data:
        row.query_json = _clean_query(data.get("query_json") if "query_json" in data else data.get("query"))
        changes["query_json"] = row.query_json
    if "is_default" in data:
        want_default = bool(data.get("is_default"))
        if want_default:
            _clear_other_defaults(cu.id, row.table_key, row.id)
            db.session.flush()
        row.is_default = want_default
        changes["is_default"] = row.is_default
    _audit(cu, row, "update", changes or None)
    try:
        db.session.commit()
    except IntegrityError as exc:
        db.session.rollback()
        raise SavedFilterError("a saved filter with that name already exists", 409) from exc
    return {"item": _public(row), "entity": "saved_list_filter"}


def delete_saved_filter(filter_id: uuid.UUID, cu) -> dict[str, Any]:
    row = _owned(filter_id, cu.id)
    _audit(cu, row, "delete", {"name": row.name, "table_key": row.table_key})
    db.session.delete(row)
    db.session.commit()
    return {"ok": True}


def register_saved_filter_routes(bp: Blueprint) -> None:
    @bp.get("/saved-filters")
    def list_saved_filters_route():
        from flask import request

        try:
            cu = _require_user()
            table_key = _clean_table_key(request.args.get("table_key") or "crm.leads")
            return _jsonify(list_saved_filters(table_key, cu))
        except SavedFilterError as exc:
            return _jsonify({"error": exc.message}), exc.status

    @bp.post("/saved-filters")
    def create_saved_filter_route():
        from flask import request

        try:
            cu = _require_user()
            data = request.get_json(silent=True) or {}
            overwrite = bool(data.get("overwrite"))
            return _jsonify(create_saved_filter(data, cu, overwrite=overwrite)), 201
        except SavedFilterError as exc:
            return _jsonify({"error": exc.message}), exc.status

    @bp.patch("/saved-filters/<filter_id>")
    def update_saved_filter_route(filter_id: str):
        from flask import request

        fid = _parse_uuid(filter_id)
        if not fid:
            return _jsonify({"error": "invalid id"}), 400
        try:
            cu = _require_user()
            data = request.get_json(silent=True) or {}
            return _jsonify(update_saved_filter(fid, data, cu))
        except SavedFilterError as exc:
            return _jsonify({"error": exc.message}), exc.status

    @bp.delete("/saved-filters/<filter_id>")
    def delete_saved_filter_route(filter_id: str):
        fid = _parse_uuid(filter_id)
        if not fid:
            return _jsonify({"error": "invalid id"}), 400
        try:
            cu = _require_user()
            return _jsonify(delete_saved_filter(fid, cu))
        except SavedFilterError as exc:
            return _jsonify({"error": exc.message}), exc.status
