# Anticipated Costs

Status: complete
Sage CM module: Procurement
Official help: https://help.sagecm.intacct.com/Content/Modules/Procurement/AnticipatedExpenses/AnticipatedExpensesOverview.htm

## Purpose

Anticipated costs are future expenses not yet bought (late fixtures, cleanup, unidentified vendors). Without them, budget-vs-committed dashboards show a fake surplus. Sage treats them as **committed cost** in Project Analytics. When the real PO/subcontract is written, the anticipated row is **deleted** or marked **Accounted For** so it is not double-counted.

Method is company-wide: Settings → Feature Settings → Procurement → **Itemized Breakdown** or **Summarize by JCC**. Changing the method **deletes all existing anticipated costs**.

## Where it lives

- Project menu → **Procurement** → **Anticipated costs**
- Itemized: Actions → Add Manually; Excel import; import from cost database / estimate
- Summarize by JCC: import job cost codes and values; edit values — **no Excel import**
- Not a TeamLink create form

## Who uses it

- PMs and project accountants maintain the unbought-work forecast
- Estimators import remaining estimate lines (excluding awarded RFP tags)
- Controllers use them with Field % Complete for projected cost at completion

## Prerequisites

- Prime **Approved with a status date**
- Job cost codes
- Feature setting: Itemized vs Summarize by JCC
- Itemized add is **only** available in Itemized Breakdown mode

## What the user fills out

### Itemized — Add anticipated cost items manually

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Project | Yes | Project | Defaulted |
| Prime Contract | Yes | Approved prime | Defaulted if only one |
| Job Cost Code | Yes | JCC | Per row |
| Description | No | Text | Optional update |
| Resource | Yes | Enum | M, L, E, S, O |
| Quantity | Yes | Number | |
| Unit Price | Yes | Money | |
| Unit of measure | No | Text | |
| Accounted For | No | Checkbox | **Itemized only.** Set when a real PO/subcontract covers the item |

### Itemized — list filters (import page)

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Not Accounted For Only | No | Checkbox | Default on |

### Summarize by JCC

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Job cost code | Yes | JCC | Import codes + dollar values |
| Amount per JCC | Yes | Money | No Accounted For checkbox in this mode |

Excel columns for itemized import are not fully listed in the overview; do not invent them.

## What Sage CM saves

- Header record: none (project + prime scoped list)
- Line / child records: itemized rows (JCC, resource, qty, unit price, unit, accounted-for) **or** per-JCC summary amounts
- System-generated values: line total (qty × unit price); analytics AnticipatedCost_Subtotal / Tax / Total
- Files / attachments: none on the add-manual page
- Audit / workflow fields: none documented; switching method wipes the table

## Statuses and lifecycle

No Draft/Approved. Lifecycle:

1. Enter/import anticipated amounts
2. Review ongoing
3. When buyout happens: delete the rows **or** mark Accounted For (itemized)
4. Remaining unaccounted amounts stay in committed-cost analytics

They are categorized as committed cost immediately (help does not require an Approved + status date on anticipated rows). That differs from POs/subcontracts.

## Dates that drive alerts

None documented.

## Relationships

- Upstream: Approved prime; JCCs; optional estimate / cost database
- Downstream: Import into PO, bill, subcontract, SCO, RFP items; Projected Cost At Completion (with Field % Complete)
- Exclude estimate items tagged on awarded RFPs when importing

## Reports and exports

- Project Analytics committed cost includes anticipated
- Excel import (itemized only)
- Forecasting help: Estimate project costs at completion

## USIS / CM_Deploy mapping

| Sage concept | USIS table / API / page | Status |
|---|---|---|
| Anticipated cost items / JCC summary | none | none |
| Accounted For flag | none | none |
| Feature setting Itemized vs JCC | none | none |

## Sources

- Official Sage help URLs used
  - https://help.sagecm.intacct.com/Content/Modules/Procurement/AnticipatedExpenses/AnticipatedExpensesOverview.htm
  - https://help.sagecm.intacct.com/Content/Modules/Procurement/AnticipatedExpenses/AnticipatedExpenses_AddManually.htm
  - https://help.sagecm.intacct.com/Content/Modules/Procurement/AnticipatedExpenses/AnticipatedExpenses_Import.htm
  - https://help.sagecm.intacct.com/Content/Modules/Reporting/Analytics_ProjectFinancials/forecasting-proj-cost-at-completion.htm
- Local files reviewed
  - `backend/app/models/commitment.py` (no anticipated entity)
