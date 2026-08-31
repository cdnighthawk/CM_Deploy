# Equipment timecards

Status: complete
Sage CM module: Equipment / Time and Expenses
Official help: https://help.sagecm.intacct.com/Content/Modules/Equipment/EquipmentTimecards/EquipmentTimecardsOverview.htm

## Purpose

Equipment timecards record daily (or weekly/crew) usage of owned equipment as run time (RT), idle time (IT), and down time (DT) against a project, approved prime contract, and job cost code. Approved cards hit Committed Cost and Cost To Date. Rental equipment cost is normally a PO/bill; if you still log hours on rented units, set RT/IT/DT rates to zero (or only a fuel rate) to avoid double-counting vendor cost.

## Where it lives

- Project Home → Time & Expenses → Eqp. Timecards → Actions → Add Single Equipment Timecards or Add Multiple Equipment Timecards.
- Global Equipment module → Equipment Timecard Stats → same add actions; convert pending equipment clock-ins.
- Also created from crew timecards when Create Equipment Timecard is selected.
- Mobile: clock-in conversion and field entry via the mobile apps. TeamLink does not enter equipment cards.

## Who uses it

- Entry: Admin, Estimating/PM, PM, Superintendent, Financial Admin, Time & Expense Field User (default role matrix).
- Approval: Administrator / Financial Administrator (same pattern as labor). Default PM has entry only.
- Estimating must have created the equipment items first.

## Prerequisites

- Equipment items in the Estimating / Equipment catalog, typically with project-level RT, IT, and DT hourly rates.
- Approved prime contract with Status Date.
- Job cost codes; optional equipment hour budgets if Feature Settings filters to budgeted codes.
- Optional: Show Only Currently Owned Equipment (items with a purchase date).
- Optional: field crews that include equipment; clock-in conversion.

## What the user fills out

### Add Single Equipment Timecards

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Date | No (defaults today) | Date | Copy entry for next N days |
| Equipment | Yes | Lookup | Owned item (or rented with $0 rates) |
| Project | Yes | Lookup | Per entry |
| Prime Contract | Yes | Lookup | Approved |
| CO or WO number | No | Lookup | Optional |
| Job Cost Code | Yes | Lookup | May filter to codes with equipment hour budget > 0 |
| Billable Status | Yes | Enum | Default Billable; Cost Plus invoice import only |
| Run Time (hours) | No* | Decimal | Leave blank if N/A. Import requires RTHours |
| Idle Time (hours) | No* | Decimal | Import requires ITHours |
| Down Time (hours) | No* | Decimal | Import requires DTHours |
| Comments | No | Text | Per entry |
| Additional entries | No | Repeat | Up to five entries per single-equipment submission |

\* Manual add help: any of RT/IT/DT may be blank. Excel import marks RTHours, ITHours, and DTHours required.

### Add Multiple Equipment Timecards

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Date / copy next days | No | Date | Same as single |
| Project / Prime Contract | Yes | Lookup | Shared header for the batch |
| Job Cost Code | Yes | Lookup | Per the multi-item path |
| Equipment + RT/IT/DT | Yes | Repeat | Add More Equipment for more units |
| Billable Status / Comments / CO-WO | Same as single | | Up to three entries per submission on the multi path (official help) |

### Excel import columns

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Date | Yes | Date | |
| EquipmentCode | Yes | Text | Must exist |
| ProjectNumber | Yes | Text | Must exist |
| PrimeContractNumber | Yes | Text | Must exist |
| ChangeOrderNumber | No | Text | Must exist if provided |
| CostCode | Yes | Text | Project job cost code |
| RTHours / ITHours / DTHours | Yes | Number | e.g. 4.25, 8, 8.5 |
| BillableStatus | Yes | Text | Billable, Unbillable, or On Hold |

### Crew / clock-in

Crew form: RT, IT, DT per equipment line. Convert Pending Clock-In Data can create equipment time entries alongside labor.

## What Sage CM saves

- Header record: equipment timecard (date, equipment, project, prime, optional CO/WO, JCC, billable status, comments).
- Line / child records: RT/IT/DT hour quantities on the same card (not a separate child table in help). Crew/clock-in can create many cards in one wizard.
- System-generated values: Pending on create; cost = hours × project/equipment RT/IT/DT rates; Billable Total; utilization totals. Summary at bottom of add form; Export To Excel of that summary.
- Files / attachments: none on the add form.
- Audit / workflow fields: approval status; exported/locked if Global Settings auto-lock after AccountingLink; Cost Plus import rules same as labor (Approved, Billable, Billable Total > 0, date before invoice Issue Date).

## Statuses and lifecycle

Pending → Approved. Only Approved (plus billable rules) import to Cost Plus invoices and appear in analytics committed/cost-to-date. Rental hours should not carry cost rates if the vendor bill already holds the cost.

## Dates that drive alerts

Timecard Date is the analytics filter date. No due-date alert on the card. Equipment hour budgets on the prime/COs constrain the JCC dropdown when the feature setting is on.

## Relationships

- Upstream: equipment items + rates, job cost codes, approved prime, optional crew, optional equipment clock-in.
- Downstream: Equipment Hours Overview, Projected Equipment Hour Overview, project analytics, Cost Plus prime invoices, AccountingLink, daily-log major equipment hours (CoreconAPI_Hours).

## Reports and exports

- Equipment utilization reports by project, contract, JCC.
- Add-form summary Export To Excel.
- Standard equipment / hours analytics dashboards (see equipment-hours-overview.md).
- Log report name for equipment timecards was listed under Time and Expenses / Equipment in the log-report center; exact standard report title beyond utilization was not confirmed in help.

## USIS / CM_Deploy mapping

| Sage concept | USIS table / API / page | Status |
|---|---|---|
| Equipment catalog | none dedicated (estimate/cost DB may hold items) | none |
| Equipment timecard RT/IT/DT | none | none |
| Daily report equipment section | `daily_reports.sections.equipment` JSON | stub — narrative daily log, not costed cards |
| Field photo of equipment | `field_photos` | unrelated |
| Hours analytics | `GET /api/v1/dashboard/hours-by-project` (labor timesheets only) | none for equipment |

## Sources

- https://help.sagecm.intacct.com/Content/Modules/Equipment/EquipmentTimecards/EquipmentTimecardsOverview.htm
- https://help.sagecm.intacct.com/Content/Modules/Equipment/EquipmentTimecards/EquipmentTimecardsAddManual.htm
- https://help.sagecm.intacct.com/Content/Modules/Import/ImportEquipmentTimecards.htm
- https://help.sagecm.intacct.com/Content/Modules/Equipment/EquipmentJobCosting/EquipmentJobCostingOverview.htm
- https://help.sagecm.intacct.com/Content/GettingStarted/Definitions.htm
- https://help.sagecm.intacct.com/Content/Administration/Settings/FeatureSettings/FeatureSettings_TimeExpenses.htm
- Local: `backend/app/models/field_ops.py` (`DailyReport` equipment section)
