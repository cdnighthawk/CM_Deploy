"""Purchase-order issue, shipments, receive, and 3-way match."""
from __future__ import annotations

from typing import Any

from flask import Blueprint, request

from ._perms import current_user
from ._rfi_service import ApiError, _parse_uuid
from . import _commitment_service as commitment_svc
from . import _purchase_order_fulfillment as po_ful

purchase_orders_bp = Blueprint("purchase_orders_api", __name__, url_prefix="/api/purchase-orders")


def _jsonify(obj: Any):
    from flask import jsonify

    return jsonify(obj)


def _err(exc: ApiError):
    return _jsonify({"error": exc.message}), exc.status


def _cid(raw: str):
    cid = _parse_uuid(raw)
    if cid is None:
        raise ApiError("invalid id", 400)
    return cid


@purchase_orders_bp.get("/<commitment_id>")
def get_purchase_order(commitment_id: str):
    try:
        return _jsonify(po_ful.tracking_payload(_cid(commitment_id), current_user()))
    except ApiError as exc:
        return _err(exc)


@purchase_orders_bp.post("/<commitment_id>/issue")
def issue_purchase_order(commitment_id: str):
    data = request.get_json(silent=True) or {}
    try:
        return _jsonify(commitment_svc.issue_purchase_order(_cid(commitment_id), data, current_user()))
    except ApiError as exc:
        return _err(exc)


@purchase_orders_bp.get("/<commitment_id>/shipments")
def list_shipments(commitment_id: str):
    try:
        return _jsonify(po_ful.list_shipments(_cid(commitment_id), current_user()))
    except ApiError as exc:
        return _err(exc)


@purchase_orders_bp.post("/<commitment_id>/shipments")
def create_shipment(commitment_id: str):
    data = request.get_json(silent=True) or {}
    try:
        return _jsonify(po_ful.create_shipment(_cid(commitment_id), data, current_user())), 201
    except ApiError as exc:
        return _err(exc)


@purchase_orders_bp.patch("/<commitment_id>/shipments/<shipment_id>")
def patch_shipment(commitment_id: str, shipment_id: str):
    sid = _parse_uuid(shipment_id)
    if sid is None:
        return _jsonify({"error": "invalid id"}), 400
    data = request.get_json(silent=True) or {}
    try:
        return _jsonify(po_ful.patch_shipment(_cid(commitment_id), sid, data, current_user()))
    except ApiError as exc:
        return _err(exc)


@purchase_orders_bp.delete("/<commitment_id>/shipments/<shipment_id>")
def delete_shipment(commitment_id: str, shipment_id: str):
    sid = _parse_uuid(shipment_id)
    if sid is None:
        return _jsonify({"error": "invalid id"}), 400
    try:
        po_ful.delete_shipment(_cid(commitment_id), sid, current_user())
        return _jsonify({"ok": True})
    except ApiError as exc:
        return _err(exc)


@purchase_orders_bp.post("/<commitment_id>/receipts")
def post_purchase_order_receipt(commitment_id: str):
    data = request.get_json(silent=True) or {}
    try:
        return _jsonify(po_ful.post_receipt(_cid(commitment_id), data, current_user())), 201
    except ApiError as exc:
        return _err(exc)


@purchase_orders_bp.post("/<commitment_id>/three-way-match")
def three_way_match(commitment_id: str):
    try:
        return _jsonify(po_ful.run_three_way_match(_cid(commitment_id), current_user()))
    except ApiError as exc:
        return _err(exc)
