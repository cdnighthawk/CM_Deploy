"""Module path resolution for before_request permission gating."""
from __future__ import annotations

from app.api._module_routes import resolve_modules
from app.permissions.access import http_method_min_level


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


def test_desktop_project_queue_uses_projects():
    assert resolve_modules("/api/v1/project-queue") == ("projects",)


def test_ingest_routes_use_documents_module():
    assert resolve_modules("/api/v1/ingest/projects") == ("documents",)
    assert resolve_modules("/api/v1/ingest/files") == ("documents",)
    assert resolve_modules("/api/v1/ingest/errors") == ("documents",)


def test_desktop_ingest_ai_uses_ai_or_documents():
    assert resolve_modules("/api/v1/ai/package-classify") == ("ai", "documents")
    assert resolve_modules("/api/v1/ai/spec-sections") == ("ai", "documents")
    assert resolve_modules("/api/v1/ai/sheet-identity") == ("ai", "documents")


def test_vendor_invoice_routes_use_ap_module():
    assert resolve_modules("/api/v1/ap/invoices") == ("ap",)
    assert resolve_modules("/api/v1/ap/mailbox/sync") == ("ap",)


def test_field_photo_and_daily_report_routes_use_projects_module():
    assert resolve_modules("/api/v1/daily-reports/a1700000-0000-4000-8000-000000000001") == ("projects",)
    assert resolve_modules("/api/v1/photos/a1700000-0000-4000-8000-000000000001/file") == ("projects",)
    assert resolve_modules("/api/v1/photos/a1700000-0000-4000-8000-000000000001") == ("projects",)


def test_daily_pretask_routes_use_safety_or_projects():
    assert resolve_modules("/api/v1/safety/summary") == ("safety",)
    assert resolve_modules("/api/v1/safety/pretasks") == ("safety",)
    assert resolve_modules("/api/v1/safety/company-profile") == ("safety",)
    assert resolve_modules("/api/v1/daily-pretasks/a1700000-0000-4000-8000-000000000001") == (
        "safety",
        "projects",
    )
    assert resolve_modules("/api/v1/projects/a1700000-0000-4000-8000-000000000001/daily-pretasks") == (
        "projects",
    )
    pid = "a1700000-0000-4000-8000-000000000001"
    assert resolve_modules(f"/api/v1/projects/{pid}/safety-profile") == ("safety", "projects")
    assert resolve_modules(f"/api/v1/projects/{pid}/safety-packet/preview") == ("safety", "projects")


def test_spec_section_delete_is_write_not_admin():
    path = "/api/v1/projects/1ff506fd-fe21-4455-9dae-72697f0bd344/rfi-lookups/spec_sections/9814519d-6bec-48cc-bb38-3e1e28e21bc8"
    assert http_method_min_level("DELETE", path) == "write"
    assert http_method_min_level("POST", path) == "write"
    assert http_method_min_level("DELETE", "/api/v1/rfis/1ff506fd-fe21-4455-9dae-72697f0bd344") == "admin"
    assert http_method_min_level("DELETE") == "admin"
