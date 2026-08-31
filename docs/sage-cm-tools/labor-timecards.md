# Labor timecards

Status: complete
Sage CM module: Time and Expenses
Official help: https://help.sagecm.intacct.com/Content/Modules/HRLbrTimecardsMiscExp/EmployeeTimecards/LaborTimecardsOverview.htm

## Purpose

Labor timecards record an employee’s hours against a project, approved prime contract, and job cost code, with a payroll item (and optional labor/craft code and workers comp code). Approved cards become committed cost / cost-to-date, can export to payroll or AccountingLink, and can import into Cost Plus prime invoices when Billable.

## Where it lives

- Project Home → Time & Expenses → Lbr. Timecards → Actions (Add Single Employee Timecards, Add Single Employee Weekly Timecards, crew, import).
- Global Time & Expenses module → Timecard and Expense Stats → three-dot menu on labor tiles.
- Record list of pending/approved cards; daily form (up to five entries per submit) and weekly grid (hours per weekday).
- Mobile: Sage CM mobile apps support timecard entry and clock-in conversion. TeamLink does not create labor timecards.

## Who uses it

- All default roles that have Labor timecards (entry only) can create: Admin, Estimating/PM, PM, Superintendent, Financial Admin, Time & Expense Field User.
- Approve: Administrator, Financial Administrator, or custom role with Timecard Approval. Default Project Manager cannot approve.
- With Time & Expense workflow (5+ licenses): managers approve subordinates (and optional indirect reports from the user profile). Employees cannot approve their own cards.

## Prerequisites

- Employee exists, Is Active, Track Time & Expenses checked; payroll items assigned on the employee profile.
- Payroll items (and optional workers comp codes, labor/craft codes, burden templates) in Feature Settings → Time & Expenses.
- Approved prime contract with Status Date; job cost codes. Optional: labor hour budgets if “Show Only Cost Codes with Labor Hour Budgets” is on.
- Optional: field crews if crew entry is used.
- AccountingLink + Sage Intacct: if Retrieve SC Project Timesheets is on, you cannot enter new cards in Sage CM — import from Intacct only.

## What the user fills out

### Daily — single employee (Add Single Employee Timecards)

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Date | No (defaults today) | Date | Copy entry for next N consecutive days (weekends/holidays not skipped) |
| Company | Yes | Lookup | Prefilled; changeable |
| Employee | Yes | Lookup | Prefilled; changeable. Strict rules can limit the list |
| Project | Yes | Lookup | Required on each entry |
| Prime Contract | Yes | Lookup | Approved contract |
| CO or WO number | No | Lookup | Change order or work order |
| Labor Code | No | Lookup | Union/craft standard rates; when set, payroll items come from the labor item form |
| Payroll Item | Yes | Lookup | From employee profile, or from labor item if Labor Code set (e.g. ST, OT) |
| Workers Comp. Code | No | Lookup | If blank, default from the project’s job cost code listing |
| Billable Status | Yes | Enum | Default Billable. Billable / Unbillable / On Hold (On Hold confirmed on import). Applies to Cost Plus prime invoices |
| Job Cost Code | Yes | Lookup | May be filtered to codes with labor hour budget > 0 |
| Hours | Yes | Decimal | Hours for that date / entry |
| Mileage | No | Decimal | Reference only; not job-costed |
| Comments | No | Text | Per entry |
| Additional entries | No | Repeat | Up to five entries per submission (different payroll item or JCC) |

### Weekly — single employee (Add Single Employee Weekly Timecards)

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Week of | No | Date | Any day in the week; first weekday from Feature Settings → 1st Day of Week |
| Company / Employee | Yes | Lookup | Prefilled |
| Show Mileage / Show Comments | No | Checkbox | Reveals per-day mileage and comment rows |
| Project / Prime Contract | Yes | Lookup | Per entry row |
| CO or WO number | No | Lookup | Per entry |
| Labor Code | No | Lookup | Same as daily |
| Payroll Item | Yes | Lookup | Same as daily |
| JCC | Yes | Lookup | Job cost code |
| Billable Status | Yes | Enum | Default Billable |
| Entry Hours (Sun–Sat or configured week) | Yes | Decimal per day | One row of hours per weekday |
| Entry Mileage per day | No | Decimal | If Show Mileage |
| Entry Comments per day | No | Text | If Show Comments |

### Crew timecards (related create path)

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Project / Prime Contract | Yes | Lookup | Step 1 |
| Field Crew Leader | Conditional | Lookup | Required when field crews are enabled |
| Company | Conditional | Lookup | Used when field crews are off |
| Create Equipment Timecard | No | Checkbox | Default on if crew has equipment |
| Employee Hours | Yes | Decimal | Per crew member (or pick employee + hours if crews off) |
| Equipment RT / IT / DT | Conditional | Decimal | If creating equipment cards |

### Bulk / import (Excel) — persisted columns Sage accepts

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Date, employee, project, prime, cost code, hours, payroll item, billable | Yes* | Mixed | Exact column names for labor import were not confirmed in help in this pass; treat daily/weekly form fields as the source of truth. Do not invent import headers. |
| Mark Imported Timecards as Pending | Admin setting | Checkbox | Feature Settings; recommended so imports stay Pending |

## What Sage CM saves

- Header record: one labor timecard per employee + date + (typically) one cost/payroll slice. Daily submit can create up to five cards. Weekly creates one card per day that has hours (not confirmed as one-vs-many row shape in help — Sage lists them as individual pending cards after save).
- Line / child records: no separate “line item” table in help; each entry column/row becomes a timecard. Crew submit also creates equipment timecards when requested.
- System-generated values: status = Pending on create; Base cost = hours × employee payroll item base rate; Burden = hours × (payroll item burden + workers comp burden); Billable total from bill rate; workers comp defaulted from JCC if omitted; cost/bill rate resolution order: (1) labor code + project + payroll item, (2) employee project-specific rates, (3) employee default payroll rates.
- Files / attachments: not on the daily/weekly form in official add help. Receipts belong on miscellaneous expenses.
- Audit / workflow fields: created/updated by user; approved by / approved date (not named on add form); exported/locked after AccountingLink; payroll-week edit window when Restrict Labor Timecard Add / Update is on.

## Statuses and lifecycle

Pending (initial) → Approved (Financial Admin / Admin / manager) → optionally Locked after export. Pending + Approved both appear on Labor Timecard Summary. Only Approved rolls into analytics Committed Cost / Cost To Date. Cost Plus prime invoice import requires Approved + Billable + billable total > 0 + timecard date earlier than invoice Issue Date.

Clock-in conversion creates Pending labor (and optional equipment) cards; they then follow this same approval path.

## Dates that drive alerts

- Timecard Date (daily) / each weekday (weekly): analytics filter date; invoice eligibility.
- Payroll week window: blocks add/edit outside Allow Add / Update for N weeks.
- Effective Date on payroll rates: which base/burden/bill rate applies.
- T&E workflow: email to manager/approver (no due date on the card itself).

## Relationships

- Upstream: employee + payroll rates, labor codes, workers comp, job cost codes, approved prime, optional CO/WO, clock-in entries, crew definitions.
- Downstream: Labor Hours Overview / Projected Labor Hour Overview; project analytics; Cost Plus prime invoices; AccountingLink / CSV payroll; daily-log manpower comparison via CoreconAPI_Hours.

## Reports and exports

- Labor Timecard Summary (grouped views listed above).
- Standard log report: Labor timecards.
- Export approved cards to Excel/CSV or AccountingLink.
- Equipment add form also offers Export To Excel of the session summary (equipment, not labor).

## USIS / CM_Deploy mapping

| Sage concept | USIS table / API / page | Status |
|---|---|---|
| Labor timecard header (date, hours, project) | `hrms_timesheet_periods`, `hrms_timesheet_entries` | partial |
| Payroll Item / Labor Code / Workers Comp | `wage_rates` (prevailing-wage reference); `hr_employee_pay_scales` | partial — not timecard FKs |
| Job cost code on time | `time_entries.cost_code_id` (clock only); timesheet entry has `project_id` only | stub |
| Billable Status / CO / WO | none | none |
| Approve / lock / AccountingLink | none on timesheets (`status` draft on period) | stub |
| Crew timecards | none | none |
| Clock-in → pending card | `time_entries` / `time_punches` stay as punches; no convert wizard | none |

## Sources

- https://help.sagecm.intacct.com/Content/Modules/HRLbrTimecardsMiscExp/EmployeeTimecards/LaborTimecardsOverview.htm
- https://help.sagecm.intacct.com/Content/Modules/HRLbrTimecardsMiscExp/EmployeeTimecards/LaborTimecardsAddDaily.htm
- https://help.sagecm.intacct.com/Content/Modules/HRLbrTimecardsMiscExp/EmployeeTimecards/LaborTimecardsAddWeekly.htm
- https://help.sagecm.intacct.com/Content/Modules/HRLbrTimecardsMiscExp/FieldCrewTimecards/CrewTimecardsAddDaily.htm
- https://help.sagecm.intacct.com/Content/Modules/HRLbrTimecardsMiscExp/EmployeeTimecards/LaborTimecardsViewSummary.htm
- https://help.sagecm.intacct.com/Content/Modules/HRLbrTimecardsMiscExp/EmployeeTimecards/LaborTimecardsLimitJCCs.htm
- https://help.sagecm.intacct.com/Content/Administration/Settings/FeatureSettings/FeatureSettings_TimeExpenses.htm
- https://help.sagecm.intacct.com/Content/Administration/Settings/FeatureSettings/FeatureSettings_TimeExpenses_WorkmensCompCodes.htm
- Local: `backend/app/models/hrms_core.py`, `backend/app/models/wage_rate.py`, `backend/app/models/hr.py`
