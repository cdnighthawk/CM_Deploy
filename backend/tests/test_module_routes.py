"""Module path resolution for before_request permission gating."""
from __future__ import annotations

from app.api._module_routes import resolve_modules


def test_feedback_route_not_module_gated():
    assert resolve_modules("/api/v1/feedback") is None
    assert resolve_modules("/api/v1/feedback/issues/confirm") is None


def test_hr_me_self_service_routes_not_module_gated():
    assert resolve_modules("/api/v1/hr/me/hire-wizard") is None
    assert resolve_modules("/api/v1/hr/me/hire-application") is None
    assert resolve_modules("/api/v1/hr/me/i9-section1/documents") is None
    assert resolve_modules("/api/v1/hr/me/w4/sign") is None


def test_hr_admin_routes_remain_module_gated():
    assert resolve_modules("/api/v1/hr/dashboard-summary") == ("hr",)
    assert resolve_modules("/api/v1/hr/employees/a1700000-0000-4000-8000-000000000001") == ("hr",)


def test_desktop_estimate_queue_uses_leads_or_estimate():
    assert resolve_modules("/api/v1/estimate-queue") == ("leads", "estimate")


def test_vendor_invoice_routes_use_ap_module():
    assert resolve_modules("/api/v1/ap/invoices") == ("ap",)
    assert resolve_modules("/api/v1/ap/mailbox/sync") == ("ap",)
