# Estimated Percent Complete

Status: complete
Sage CM module: Client Contract Admin
Official help: https://help.sagecm.intacct.com/Content/Modules/Reporting/Analytics_ProjectFinancials/review-field-percent-complete.htm

## Purpose

Estimated percent complete (also called **Field % Complete**) is a **forecast input**, not a billing % complete. For each job cost code, the field team records observed percent complete. Sage uses it to project remaining labor and equipment hours/cost:

- Projected labor hours = approved labor timecard hours / Field % Complete
- Total projected labor cost = (total approved labor timecard cost / approved labor timecard hours) × projected labor hours
- Projected equipment hours = equipment timecard hours / Field % Complete
- Total projected equipment cost uses the same pattern with equipment timecard cost and hours

This is **not** the cumulative **% Complete** on a prime invoice line (that value bills the owner).

## Where it lives

- Project menu → **Client Contract Admin** → **Estimated percent complete details**
- Also: Project Analytics → Single Project & Prime → select project + prime → **Review Estimated Field Percent Complete Details** (or Review Field % Complete)
- Grid of job cost codes with an editable Field % Complete column
- Not TeamLink; internal forecasting

## Who uses it

- Superintendents / PMs enter field percents
- Project accountants review Projected Cost At Completion dashboards
- Viewers of Labor Hours and Equipment Hours overview dashboards consume the result

## Prerequisites

- Project and prime selected (Single Project & Prime)
- Job cost codes exist
- Projections are only meaningful after approved labor/equipment timecards exist
- Anticipated costs are a separate step in “Estimate project costs at completion” (procurement setting + anticipated cost entry)

## What the user fills out

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Project | Yes | Project | Analytics: Single Project & Prime |
| Prime Contract # | Yes | Prime | |
| Field % Complete (per job cost code) | No | Percent | Entered on **Estimated Field Percent Complete Details**. One value per cost code as needed |

No header record, lines, or files are created beyond saving those percents.

## What Sage CM saves

- Header record: none
- Line / child records: per-JCC **EstimatedFieldPercentComplete** / Field % Complete (analytics API name)
- System-generated values: projected labor/equipment hours and cost on Cost, Labor, and Equipment analytics tabs
- Files / attachments: none
- Audit / workflow fields: not confirmed in help

## Statuses and lifecycle

No Draft/Approved. Saving the grid immediately updates:

**Cost tab:** Projected Cost At Completion Overview dashboard and report; Project Cost At Completion Overview Without Tax report.

**Labor tab:** Labor Hours Overview; Labor Production Overview For Single Job Cost Code; Labor Productivity Using Daily Log Quantities; Projected Labor Hour Overview.

**Equipment tab:** Equipment Hours Overview; Projected Equipment Hour Overview.

## Dates that drive alerts

None. This is not a due-date tool.

## Relationships

- Upstream: Job cost codes; labor/equipment timecards (actuals in the formulas)
- Sibling: Anticipated costs (committed forecast of unbought work)
- Distinct from prime invoice % Complete (billing)

## Reports and exports

- Dashboards listed above
- Analytics API Cost v1: `EstimatedFieldPercentComplete`; `LbrTimecard_Projected_Total`; `EqpTimecard_Projected_Total`

## USIS / CM_Deploy mapping

| Sage concept | USIS table / API / page | Status |
|---|---|---|
| Field % complete per JCC | none | none |
| Invoice line percent_complete | `pay_application_lines.percent_complete` | partial — **billing** %, not field % |
| Projected cost at completion | none | none |

## Sources

- Official Sage help URLs used
  - https://help.sagecm.intacct.com/Content/Modules/Reporting/Analytics_ProjectFinancials/review-field-percent-complete.htm
  - https://help.sagecm.intacct.com/Content/Modules/Reporting/Analytics_ProjectFinancials/forecasting-proj-cost-at-completion.htm
  - https://help.sagecm.intacct.com/Content/Modules/Reporting/Analytics_ProjectFinancials/APIs/v1/ProjectAnalytics_APIs_V1_Cost.htm
  - https://help.sagecm.intacct.com/Content/ReleaseNotes/October-2023/oct-23-projects-menu.htm
- Local files reviewed
  - `backend/app/models/pay_application.py`
