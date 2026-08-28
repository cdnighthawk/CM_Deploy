"""Purchase-order issue / receive hooks that honor submittal QC holds."""
from __future__ import annotations

from typing import Any

from flask import Blueprint, request

from ._perms import current_user
from ._rfi_service import ApiError, _parse_uuid
from . import _commitment_service as commitment_svc

purchase_orders_bp = Blueprint("purchase_orders_api", __name__, url_prefix="/api/purchase-orders")


def _jsonify(obj: Any):
    from flask import jsonify

    return jsonify(obj)


def _err(exc: ApiError):
    return _jsonify({"error": exc.message}), exc.status


@purchase_orders_bp.post("/<commitment_id>/issue")
def issue_purchase_order(commitment_id: str):
    cid = _parse_uuid(commitment_id)
    if cid is None:
        return _jsonify({"error": "invalid id"}), 400
    data = request.get_json(silent=True) or {}
    try:
        return _jsonify(commitment_svc.issue_purchase_order(cid, data, current_user()))
    except ApiError as exc:
        return _err(exc)


@purchase_orders_bp.post("/<commitment_id>/receipts")
def post_purchase_order_receipt(commitment_id: str):
    cid = _parse_uuid(commitment_id)
    if cid is None:
        return _jsonify({"error": "invalid id"}), 400
    data = request.get_json(silent=True) or {}
    try:
        return _jsonify(commitment_svc.create_purchase_order_receipt(cid, data, current_user())), 201
    except ApiError as exc:
        return _err(exc)
