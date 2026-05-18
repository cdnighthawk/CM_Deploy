"""Smoke tests for dispatch, material orders, submittal line items (migration 0042)."""
from __future__ import annotations

import uuid

import pytest

from app.models import HrEmployeeDispatch, ManufacturerProductData, ProjectMaterialOrder, SubmittalLineItem


def test_models_registered():
    assert HrEmployeeDispatch.__tablename__ == "hr_employee_dispatches"
    assert ProjectMaterialOrder.__tablename__ == "project_material_orders"
    assert SubmittalLineItem.__tablename__ == "submittal_line_items"
    assert ManufacturerProductData.__tablename__ == "manufacturer_product_data"


def test_manufacturer_catalog_lookup(client):
    r = client.get("/api/v1/manufacturer-product-data?manufacturer=Bobrick")
    assert r.status_code in (200, 401, 403)
    if r.status_code == 200:
        data = r.get_json()
        assert data.get("entity") == "manufacturer_product_data"
