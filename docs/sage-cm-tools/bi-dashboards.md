# BI dashboards

Status: complete
Sage CM module: Reporting / Analytics
Official help: https://help.sagecm.intacct.com/Content/Modules/Reporting/Analytics_ProjectFinancials/AddDashboard/ResourceCenter_AddDashboard.htm

## Purpose

Custom BI dashboards are user-designed Syncfusion Bold BI canvases that bind to Sage Construction Management analytics APIs (hours, overview totals, historical hours, etc.). They sit beside Sage-provided standard summary dashboards (Labor Hours Overview, Equipment Hours Overview, project financial heat maps). This file is the **designer**: add dashboard, pick API, drop widgets, publish.

## Where it lives

- Analytics / Project financials → add custom dashboard (resource center).
- Standard dashboards live on the same Analytics module (see project-analytics.md and labor/equipment hours overviews).
- Export of a widget is on the live dashboard (hover chrome), not only in the designer.
- Admin/PM/Financial roles with Project financials. Time & Expense Field User has no Analytics in the default matrix.
- Not TeamLink.

## Who uses it

Administrators and financial/PMs who may publish dashboards. Consumers only need Analytics access to view published boards.

## Prerequisites

- Review the official API field lists before binding widgets (CoreconAPI_Hours, CoreconAPI_HoursHistorical, CoreconAPI_OverviewDetailsSimple, and other v1 analytics APIs on the same path).
- Default font size / export options understood.
- Syncfusion Bold BI widget docs (linked from Sage help) for control-specific properties.

## What the user fills out

### Create / publish

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| API data source | Yes | Lookup | Sage analytics API (review fields first) |
| Default font size | No | Number | Widget default |
| Export options | No | Flags | Widget Excel/PDF/JPEG |
| Number Card widget | No | Widget | Single metric |
| KPI Card widget | No | Widget | |
| Grid widget | No | Widget | |
| Pivot Grid widget | No | Widget | |
| Bar widget | No | Widget | |
| Text widget | No | Widget | |
| Master widget filter | No | Filter | Cross-widget filter |
| PUBLISH | Yes | Action | |
| Dashboard Name | Yes | Text | Publish dialog |
| Description | No | Text | Publish dialog |

Widget-internal property sheets (axis, aggregation, color) follow Bold BI, not a Sage field table. Do not invent Sage-specific widget properties.

### Runtime filters (standard + custom boards)

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Single vs multi-project | Yes | Enum | Single: project, prime, JCC. Multi: project and prime |
| Start / End date | No | Date | See transaction date mapping below. Start date disabled when the board includes prime budgets or COs |
| Heat map grain | System | | Project, prime, or JCC depending on selection count |

## What Sage CM saves

- Header record: published dashboard (name, description, API binding, widget layout, font/export defaults).
- Line / child records: widgets + optional master filter. Data is queried live from APIs, not copied into the dashboard row.
- System-generated values: API metrics (hours, costs, projections). Ctrl+scroll if labels clip.
- Files / attachments: per-widget export Excel/PDF/JPEG.
- Audit / workflow fields: none.

## Statuses and lifecycle

Designer → Publish. Unpublished work is not confirmed as a named “draft” status in help. Standard Sage dashboards cannot be replaced by deleting APIs.

## Dates that drive alerts

None. Date filters use official transaction dates:

- Revenue: prime Status Date; CO Status Date; prime invoice Issue Date
- Cost: PO/sub/SCO Status Date; bill/subinvoice Issue Date; labor/equipment timecard Date; miscellaneous expense Transaction Date

## Relationships

- Upstream: analytics APIs; approved/pending transactions; Field % Complete (hours boards).
- Downstream: Excel/PDF/JPEG snapshots; fiscal-year filtering (Company Settings fiscal year start).
- Sibling: log reports (row lists) vs BI (widgets).

## Reports and exports

Widget chrome export. Standard analytical reports listed with Field % Complete (Projected Labor/Equipment Hour Overview, etc.).

## USIS / CM_Deploy mapping

| Sage concept | USIS table / API / page | Status |
|---|---|---|
| Bold BI designer | none | none |
| CoreconAPI_Hours-style metrics | `GET /api/v1/dashboard/hours-by-project` | stub |
| Power BI embed | reports catalog `powerbi_dashboard` | stub |
| HRMS dashboard | `GET /hrms/dashboard`; `usis-hrms-home.html` | partial — HR not project financials |
| ApexCharts on USIS dashboard | `usis-dashboard-dark.html` | implemented — not Sage BI |

## Sources

- https://help.sagecm.intacct.com/Content/Modules/Reporting/Analytics_ProjectFinancials/AddDashboard/ResourceCenter_AddDashboard.htm
- https://help.sagecm.intacct.com/Content/Modules/Reporting/Analytics_ProjectFinancials/ResourceCenter_Analytics_ProjectFinancials.htm
- https://help.sagecm.intacct.com/Content/Modules/Reporting/Analytics_ProjectFinancials/APIs/v1/ProjectAnalytics_APIs_V1_Hours.htm
- https://help.sagecm.intacct.com/Content/Modules/Reporting/Analytics_ProjectFinancials/APIs/v1/ProjectAnalytics_APIs_V1_OverviewDetailedSimple.htm
- Local: `backend/app/api/_reports_catalog_service.py`, `backend/app/hrms/_dashboard_service.py`
