# Project analytics

Status: complete
Sage CM module: Analytics / Project financials
Official help: https://help.sagecm.intacct.com/Content/Modules/Reporting/Analytics_ProjectFinancials/ResourceCenter_Analytics_ProjectFinancials.htm

## Purpose

Project financial analytics is the BI engine for one or many projects: heat maps, bar charts, grids, and drill-in cost reports by cost code, division, owner code, transaction type, resource, and vendor. It rolls approved (and some pending) committed cost and cost-to-date from primes, COs, POs, bills, subs, labor/equipment timecards, and miscellaneous expenses. Field % Complete drives labor/equipment projections.

## Where it lives

- Analytics module / Project financials resource center; Project Home may link to project analytics (implementation plans mention viewing financial status of ongoing projects).
- Single Project & Prime → Review Field % Complete.
- Labor tab / Equipment tab dashboards (see labor-hours-overview.md, equipment-hours-overview.md).
- Security: Project financials = Yes for Admin, Estimating/PM, PM, Financial Admin. Estimator and Superintendent and Field User do **not** get Project financials on the default matrix (Superintendent has hours overviews but not this financials row).
- Not TeamLink.

## Who uses it

PMs, estimating/PMs, financial admins, admins. Superintendents use hours overviews, not the full financials module, unless given a custom role.

## Prerequisites

- Approved financial transactions with status/issue dates.
- Job cost codes and owner/division codes if you drill those dimensions.
- Fiscal year start in Company Settings for current/prior year boards.
- Optional Field % Complete for hour/cost projections.

## What the user fills out

Analytics is mostly filters, not a create form.

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Single project vs multi-projects | Yes | Enum | Single: results by project, prime, JCC. Multi: project and prime |
| Project / Prime Contract | Yes for single | Lookup | Unlocks Field % Complete |
| Start date / End date | No | Date | Start **not** available when the dashboard includes prime contract budgets or COs |
| Field % Complete | No | Percent | Observed %; Projected labor hours = approved labor hours / this value; Projected equipment hours = equipment hours / this value |
| Heat map / chart maximize | No | UI | Hover corner for Excel/PDF/JPEG |
| Browser zoom | No | Ctrl+wheel | If labels or numbers clip |

Users do not type committed-cost amounts here; those come from approved source documents.

## What Sage CM saves

- Header record: Field % Complete on the project/prime analytics context (the only analytics input Sage persists from this page).
- Line / child records: none.
- System-generated values (definitions + API):
  - **Committed cost** (Sage definition) includes booked costs: approved POs; approved bills not from POs; approved subs/SCOs; approved labor timecards; approved equipment timecards; approved misc expenses; anticipated costs.
  - **Cost to date** uses the same approved cost family (misc expenses and timecards included).
  - Overview API examples: LbrTimecard_Approved_Total, _OnBillRates, _Pending_Total, _ApprovedAndPending_Total; hour budget and remaining series; Percent_HourBudget_L/E.
  - Detail cost reports drill: cost code, division, owner code, transaction type, transaction resource (M/L/E/S/O), vendor.
- Files / attachments: widget exports.
- Audit / workflow fields: none. Pending CA/P workflow items may appear in pending series on some APIs (Overview detailed simple **omits** pending totals and tax).

## Statuses and lifecycle

Read-only. Changing Field % Complete refreshes Labor Hours Overview, Labor Production Overview For Single JCC, Labor Productivity Using Daily Log Quantities, Projected Labor Hour Overview, Equipment Hours Overview, Projected Equipment Hour Overview.

Year-end: official implementation tips topic exists (fiscal year-end closing and reporting) — procedure fields not fetched here.

## Dates that drive alerts

None. Filter dates = Status Date (primes, COs, POs, subs, SCOs) or Issue Date (invoices, bills, subinvoices) or Date (timecards) or Transaction Date (misc expenses).

## Relationships

- Upstream: every cost/revenue document; hour budgets; daily log manpower/equipment hours (API comparison series).
- Downstream: custom BI dashboards using the same APIs; AccountingLink does not post from analytics.
- Definitions: rental equipment cost is PO/bill, not equipment timecard cost (unless you set rates).

## Reports and exports

- Standard BI summary dashboards and analytical reports (resource center).
- Item details summed by job cost code (detail report family).
- Widget Excel/PDF/JPEG.
- APIs: CoreconAPI_OverviewDetailsSimple, CoreconAPI_Hours, CoreconAPI_HoursHistorical.

## USIS / CM_Deploy mapping

| Sage concept | USIS table / API / page | Status |
|---|---|---|
| Project financial heat maps | none | none |
| Field % Complete | none | none |
| Committed cost rollup | commitments / AP models (procurement) | partial — no Sage analytics cube |
| Hours vs budget | `dashboard/hours-by-project` | stub |
| Daily log quantities | `daily_reports.sections` | stub |
| Power BI | catalog embed | stub |

## Sources

- https://help.sagecm.intacct.com/Content/Modules/Reporting/Analytics_ProjectFinancials/ResourceCenter_Analytics_ProjectFinancials.htm
- https://help.sagecm.intacct.com/Content/Modules/Reporting/Analytics_ProjectFinancials/review-field-percent-complete.htm
- https://help.sagecm.intacct.com/Content/GettingStarted/Definitions.htm
- https://help.sagecm.intacct.com/Content/Modules/Reporting/Analytics_ProjectFinancials/APIs/v1/ProjectAnalytics_APIs_V1_OverviewDetailedSimple.htm
- https://help.sagecm.intacct.com/Content/Administration/Settings/CompanySettings/CompanySettings_SecurityRoles_Default.htm
- Local: `backend/app/api/v1.py`, `backend/app/api/_reports_catalog_service.py`
