# Time and Expenses overview

Status: complete
Sage CM module: Time and Expenses
Official help: https://help.sagecm.intacct.com/Content/Modules/HRLbrTimecardsMiscExp/EmployeeTimecards/LaborTimecardsOverview.htm

## Purpose

The Time & Expenses module (and the matching Time & Expenses section on Project Home) is the landing page for labor timecards, equipment timecards, employee miscellaneous expenses, clock in/out conversion, employee/payroll setup, and hour-summary views. It is a stats and navigation hub, not a single transaction form. Financial admins use it to see pending vs approved counts, convert clock-in data, and open the create/approve lists for each cost type.

## Where it lives

- Global nav: Time & Expenses module (company-wide stats across projects).
- Project menu: Project Home → Time & Expenses section (project-scoped links: Lbr. Timecards, Eqp. Timecards, Misc. Expenses, Time & Expense Overview).
- Overview page with Timecard and Expense Stats / Employee and Labor Stats / Clock In / Out Stats tiles; each tile’s three-dot menu opens add, import, convert, or approve actions.
- Mobile: clock in/out and timecard entry are available on the Sage CM mobile apps; TeamLink does not enter timecards.

## Who uses it

- Time & Expense Field User: enter own labor/equipment/misc expense rows; clock in/out.
- Superintendent / Project Manager: enter timecards; view Labor Hours Overview and Equipment Hours Overview; typically cannot approve (default PM role has no approval).
- Financial Administrator / Administrator: approve labor, equipment, and misc expenses; manage employees and payroll rates; convert anyone’s clock-in data.
- Managers (when Time & Expense workflow is enabled, 5+ licenses): approve subordinates’ time/expenses if their security role includes Timecard Approval.

## Prerequisites

- Project with an approved prime contract that has a Status Date.
- Job cost codes on the prime contract (hour budgets optional unless Feature Settings filter to budgeted codes).
- Employees with Track Time & Expenses and payroll items/rates (for labor).
- Equipment items set up in Estimating / Equipment (for equipment timecards).
- Feature Settings → Time & Expenses lists: payroll items, payment types, expense types, workers comp codes, departments.
- Optional: field crews, clock in/out, geofencing, Time & Expense workflow.

## What the user fills out

This overview itself is a dashboard. Users do not create a “Time & Expense Overview” record. They set filters and open child tools from the stats tiles.

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Project (Quick Select / Project Home) | Yes to scope | Lookup | Global Time & Expenses module can show all projects the user can access |
| Date / week range | No | Date | Used when opening add-daily / add-weekly / convert wizards |
| Stats tile action | Yes to act | Menu | Add Single Employee Timecards, Add Weekly, Add Crew, Import From Excel, Convert Pending Clock-In Data, Add Misc. Expenses, Add Equipment Timecards |
| View Labor Timecard Summary grouping | No | Dropdown | Employee+Date; Employee+Status+Date; Employee+Payroll Item+Date; plus project/prime/cost code/labor code variants |

## What Sage CM saves

The overview does not persist its own header. It reads live aggregates from the child tools.

- Header record: none (module landing / project section).
- Line / child records: labor timecards, equipment timecards, miscellaneous expenses, clock-in entries, field crews, employees, payroll rates (each documented in their own tool files).
- System-generated values (IDs, numbers, dates, totals): pending vs approved counts; clocked-in employee/equipment counts; Active Employees count; payroll-item employee counts.
- Files / attachments: none at overview level.
- Audit / workflow fields: color-coded listings when Contract Admin/Procurement workflow is unrelated; Time & Expense approval is on the child records. Exported/locked flags appear after AccountingLink export.

## Statuses and lifecycle

Child records start Pending (labor/equipment) or Draft → Pending Submission → Pending (misc expenses). Approval by Financial Admin / Admin (or manager under T&E workflow) moves them to Approved. Approved rows roll into project analytics Committed Cost and Cost To Date. Not Approved is used on misc expenses. Locked after AccountingLink export when Company Settings → Global Settings auto-lock is on.

## Dates that drive alerts

No overview-level due date. Labor/equipment timecard Date and misc expense Transaction/Expense Date drive analytics filters. Clock-in start/break/end times drive conversion to pending timecards. T&E workflow sends email alerts to approvers (Home → Workflow tab).

## Relationships

- Upstream: employees, payroll items/rates, equipment items, job cost codes, approved prime contract, optional field crews, Feature Settings T&E.
- Downstream: Labor Hours Overview, Equipment Hours Overview, project analytics, Cost Plus prime invoices (Billable + Approved + date before invoice Issue Date), AccountingLink / Excel-CSV payroll export, daily logs (manpower/equipment hours can be compared in analytics APIs).

## Reports and exports

- Standard log reports: Labor timecards; Employee miscellaneous expenses (Reports module and feature landing).
- Labor Timecard Summary (on-screen grouping + Export To Excel from equipment add form).
- Export approved labor timecards to Excel/CSV or AccountingLink.
- Equipment utilization reports by project, contract, and job cost code.

## USIS / CM_Deploy mapping

| Sage concept | USIS table / API / page | Status |
|---|---|---|
| Time & Expenses landing stats | `GET /api/v1/dashboard/hours-by-project`; HRMS dashboard `GET /hrms/dashboard` | partial |
| Labor timecards (daily/weekly lines) | `hrms_timesheet_periods` / `hrms_timesheet_entries` | partial — hours + project, no payroll item / JCC / billable / CO-WO |
| Clock in/out | `time_entries`, `time_punches`; `POST /api/v1/time-clock/clock-in` etc. | implemented |
| Equipment timecards | none | none |
| Misc expenses | `hrms_expense_reports` / `hrms_expense_lines` | partial — employee expense reports, not Sage payment-type/JCC lines |
| Field crews | none | none |
| T&E approval workflow | `workflow_definitions` / `workflow_instances` (generic engine) | stub — not Sage T&E value rules |
| Project Home T&E section | construction project-detail / time-sheet pages | stub |

## Sources

- https://help.sagecm.intacct.com/Content/Modules/HRLbrTimecardsMiscExp/EmployeeTimecards/LaborTimecardsOverview.htm
- https://help.sagecm.intacct.com/Content/Administration/Settings/FeatureSettings/FeatureSettings_TimeExpenses.htm
- https://help.sagecm.intacct.com/Content/Administration/Settings/Workflow/Workflow_TimeExpenses_Overview.htm
- https://help.sagecm.intacct.com/Content/Modules/HRLbrTimecardsMiscExp/EmployeeTimecards/LaborTimecardsViewSummary.htm
- https://help.sagecm.intacct.com/Content/GettingStarted/Definitions.htm
- Local: `backend/app/models/hrms_core.py`, `backend/app/models/field_ops.py`, `backend/app/api/v1.py` (`/dashboard/hours-by-project`)
