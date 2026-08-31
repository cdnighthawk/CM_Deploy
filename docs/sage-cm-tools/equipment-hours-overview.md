# Equipment Hours Overview

Status: complete
Sage CM module: Analytics / Equipment
Official help: https://help.sagecm.intacct.com/Content/Modules/Reporting/Analytics_ProjectFinancials/review-field-percent-complete.htm

## Purpose

Equipment Hours Overview is the Equipment-tab BI dashboard that compares equipment hour budgets to equipment timecard hours (RT/IT/DT rolled to hours), remaining hours, percent of budget, and projected equipment hours/cost using Field % Complete. It is analytics, not the equipment timecard form.

## Where it lives

- Analytics / Project financials → Equipment tab → Equipment Hours Overview.
- Default roles with “Equipment hours overview”: Admin, Estimating/PM, PM, Superintendent, Financial Admin (not Field User).
- Equipment module stats tiles link to pending/approved equipment cards, not this dashboard.
- Mobile / TeamLink: no Field User access in the default matrix.

## Who uses it

PMs, supers, financial admins, and estimating/PMs reviewing owned-equipment utilization vs budget and projections.

## Prerequisites

- Equipment items with rates; equipment timecards (hours are the costed usage series).
- Equipment hour budgets on prime / COs / CPRs (`HourBudget_*_E`).
- Optional Field % Complete on Single Project & Prime.
- Feature setting “Show Only Cost Codes with Equipment Hour Budgets” only affects data entry, not this dashboard.

## What the user fills out

No create form. Scope and Field % Complete only.

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Scope | Yes | Enum | Single project (project, prime, JCC) vs multi-project |
| Project / Prime | Yes for single | Lookup | Enables Review Field % Complete |
| Job cost code | No | Filter | Heat map / grid |
| Start / End date | No | Date | Equipment timecard Date. Start date disabled when dashboard includes prime budgets or COs |
| Field % Complete | No | Percent | Projected equipment hours = equipment timecard hours / Field % Complete |

## What Sage CM saves

- Header record: none. Field % Complete stored on the analytics project/prime context.
- Line / child records: none.
- System-generated values (official API names):
  - HourBudget_Prime_E, HourBudget_ApprovedCOs_E, HourBudget_Revised_E, HourBudget_PendingCOs_E, HourBudget_ApprovedCPRs_E, HourBudget_PendingCPRs_E
  - EqpTimecard_Hours, EqpTimecard_Hours_NoCORef, EqpTimecard_Hours_WithCORef
  - Projected_Hours_E = EqpTimecard_Hours / EstimatedFieldPercentComplete
  - EqpTimecard_Projected_Total = (EqpTimecard_CostTotal / EqpTimecard_Hours) × Projected_Hours_E
  - HourBudget_Remaining_E; Percent_HourBudget_E
  - RevisedEqpHourBudget_Less_EqpHours; RevisedEqpHourBudget_Less_ProjectedEqpHours; ProjectedEqpHours_Less_RevisedEqpHourBudget
  - DailyLog_MajorEqp_JobCostCodeEquipmentHours
- Files / attachments: widget export Excel / PDF / JPEG.
- Audit / workflow fields: none.

## Statuses and lifecycle

Read-only. Changing Field % Complete refreshes Equipment Hours Overview and Projected Equipment Hour Overview. Rental costs on POs/bills are not this hours series.

## Dates that drive alerts

None. Filter date = equipment timecard Date.

## Relationships

- Upstream: equipment timecards, equipment hour budgets, daily log major equipment hours, Field % Complete.
- Downstream: Projected Equipment Hour Overview; Cost Plus invoice import still uses approved billable equipment cards.

## Reports and exports

- Equipment Hours Overview dashboard.
- Projected Equipment Hour Overview.
- Equipment utilization reports (from equipment timecards overview).
- APIs: CoreconAPI_Hours, CoreconAPI_HoursHistorical.

## USIS / CM_Deploy mapping

| Sage concept | USIS table / API / page | Status |
|---|---|---|
| Equipment hours dashboard | none | none |
| Equipment hour budgets | none | none |
| Equipment timecard hours | none | none |
| Daily log equipment hours | `daily_reports.sections.equipment` | stub |
| Field % Complete | none | none |

## Sources

- https://help.sagecm.intacct.com/Content/Modules/Reporting/Analytics_ProjectFinancials/review-field-percent-complete.htm
- https://help.sagecm.intacct.com/Content/Modules/Reporting/Analytics_ProjectFinancials/APIs/v1/ProjectAnalytics_APIs_V1_Hours.htm
- https://help.sagecm.intacct.com/Content/Modules/Reporting/Analytics_ProjectFinancials/APIs/v1/ProjectAnalytics_APIs_V1_HoursHistorical.htm
- https://help.sagecm.intacct.com/Content/Modules/Equipment/EquipmentTimecards/EquipmentTimecardsOverview.htm
- https://help.sagecm.intacct.com/Content/Administration/Settings/CompanySettings/CompanySettings_SecurityRoles_Default.htm
- Local: `backend/app/models/field_ops.py`
