# Labor Hours Overview

Status: complete
Sage CM module: Analytics / Time and Expenses
Official help: https://help.sagecm.intacct.com/Content/Modules/Reporting/Analytics_ProjectFinancials/review-field-percent-complete.htm

## Purpose

Labor Hours Overview is a BI dashboard (Labor tab in project financial analytics) that compares labor hour budgets (prime + COs/CPRs) to approved and pending labor timecard hours, remaining hours, percent of budget used, and projected hours/cost using Field % Complete. It is a read-mostly analytics surface, not a timecard editor.

## Where it lives

- Analytics / Project financials → Labor tab → Labor Hours Overview dashboard.
- Also reachable from roles that have “Labor hours overview” (Admin, Estimating/PM, PM, Superintendent, Financial Admin — not Time & Expense Field User).
- Related on-screen summary: Actions → View Labor Timecard Summary on Lbr. Timecards (transaction list grouping, not the BI dashboard).
- Mobile / TeamLink: no dedicated Field User access to this dashboard in the default role matrix.

## Who uses it

Project managers, superintendents, financial admins, and estimators/PMs review hours vs budget and projections. Field users enter timecards but do not get this overview by default.

## Prerequisites

- Approved labor (and pending, for some metrics) timecards with project, prime, JCC.
- Labor hour budgets on the prime contract and approved/pending COs and CPRs (`HourBudget_*_L` series).
- Optional: Field % Complete entered on Single Project & Prime analytics (Review Field % Complete).
- Security role with Labor hours overview / Project financials.

## What the user fills out

This dashboard has no create form. Users set analytics scope and the Field % Complete used in projections.

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Scope | Yes | Enum | Single project (by project, prime, JCC) vs multi-project (project and prime) |
| Project / Prime Contract | Yes for single | Lookup | Single Project & Prime unlocks Review Field % Complete |
| Job cost code filter | No | Lookup | Heat maps/grids can filter to JCC |
| Start / End date | No | Date | Filters timecards by Date. Start date not available on dashboards that include prime budgets or COs |
| Field % Complete | No | Percent | Observed field completion; drives Projected labor hours = approved labor hours / Field % Complete |
| Labor Timecard Summary grouping (sibling tool) | No | Dropdown | Employee+Date and richer Employee+Project+Prime+Cost Code+Payroll Item+Labor Code+Date views |

## What Sage CM saves

- Header record: none for the dashboard itself. Field % Complete is saved on the project/prime analytics context (entered from Review Field % Complete).
- Line / child records: none. Metrics are computed from budgets and timecards.
- System-generated values (CoreconAPI_Hours / OverviewDetailsSimple, official API field names):
  - HourBudget_Prime_L, HourBudget_ApprovedCOs_L, HourBudget_Revised_L, HourBudget_PendingCOs_L, HourBudget_ApprovedCPRs_L, HourBudget_PendingCPRs_L
  - LbrTimecard_Approved_Hours, LbrTimecard_Pending_Hours, LbrTimecard_ApprovedAndPending_Hours
  - Projected_Hours_L = approved hours / EstimatedFieldPercentComplete
  - LbrTimecard_Projected_Total = (approved cost / approved hours) × projected hours
  - HourBudget_Remaining_L = revised labor hour budget − approved hours
  - Percent_HourBudget_L = approved hours / revised budget × 100
  - DailyLog_Manpower_JobCostCodeManpowerHours (comparison series)
- Files / attachments: export chart/grid to Excel, PDF, or JPEG from widget chrome.
- Audit / workflow fields: none on the dashboard.

## Statuses and lifecycle

Read-only. Timecard Pending vs Approved changes the approved vs pending hour series. Changing Field % Complete refreshes Labor Hours Overview, Labor Production Overview For Single Job Cost Code, Labor Productivity Using Daily Log Quantities, and Projected Labor Hour Overview.

## Dates that drive alerts

None on this dashboard. Analytics date filters use labor timecard Date. Budget/CO status dates apply when the dashboard includes those series (start-date filter then disabled).

## Relationships

- Upstream: labor timecards, prime/CO/CPR hour budgets, daily log manpower hours, Field % Complete.
- Downstream: Projected Labor Hour Overview report; Cost Plus billing uses approved billable cards, not this dashboard.

## Reports and exports

- Labor Hours Overview dashboard (widgets maximize + Excel/PDF/JPEG).
- Projected Labor Hour Overview; Labor Production Overview For Single Job Cost Code; Labor Productivity Using Daily Log Quantities.
- Labor Timecard Summary (T&E list tool).
- API: CoreconAPI_Hours, CoreconAPI_HoursHistorical, CoreconAPI_OverviewDetailsSimple.

## USIS / CM_Deploy mapping

| Sage concept | USIS table / API / page | Status |
|---|---|---|
| Hours by project chart | `GET /api/v1/dashboard/hours-by-project` (sum `hrms_timesheet_entries.hours_worked`) | partial |
| Labor hour budgets / CO hour budgets | none | none |
| Field % Complete | none | none |
| Projected hours formulas | none | none |
| Daily log manpower hours | `daily_reports.sections.manpower` JSON | stub |
| Power BI embed | reports catalog `powerbi_dashboard` | stub |

## Sources

- https://help.sagecm.intacct.com/Content/Modules/Reporting/Analytics_ProjectFinancials/review-field-percent-complete.htm
- https://help.sagecm.intacct.com/Content/Modules/Reporting/Analytics_ProjectFinancials/ResourceCenter_Analytics_ProjectFinancials.htm
- https://help.sagecm.intacct.com/Content/Modules/Reporting/Analytics_ProjectFinancials/APIs/v1/ProjectAnalytics_APIs_V1_Hours.htm
- https://help.sagecm.intacct.com/Content/Modules/Reporting/Analytics_ProjectFinancials/APIs/v1/ProjectAnalytics_APIs_V1_OverviewDetailedSimple.htm
- https://help.sagecm.intacct.com/Content/Modules/HRLbrTimecardsMiscExp/EmployeeTimecards/LaborTimecardsViewSummary.htm
- https://help.sagecm.intacct.com/Content/Administration/Settings/CompanySettings/CompanySettings_SecurityRoles_Default.htm
- Local: `backend/app/api/v1.py`, `backend/app/models/hrms_core.py`, `backend/app/api/_reports_catalog_service.py`
