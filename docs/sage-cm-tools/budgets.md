# Budgets

Status: complete
Sage CM module: Client Contract Admin
Official help: https://help.sagecm.intacct.com/Content/Modules/ContractAdministration/PrimeContract/PrimeContractBudgetsOverview.htm

## Purpose

Original budgets live **on the prime contract**, per job cost code. Sage stores four budget families: contract amount (revenue / GMP / estimated unit-price value), cost budgets by resource (M/L/E/S/O, no fee), labor hours, and equipment hours. Revised budgets on analytics = original ± change orders that are **Approved with a status date**. Cost budgets are compared to committed cost (POs, subcontracts, SCOs, timecards, anticipated costs) and cost-to-date (bills, sub invoices, timecards).

## Where it lives

- Not a top-level menu item named “Budgets.” Path: Project menu → **Client Contract Admin** → **Prime Contracts** → open a prime → **Original Prime Contract Budgets**
  - **Cost Budgets**
  - **Labor Hours**
  - **Equipment Hours**
  - Original contract items / amounts (SOV, GMP, unit-price items)
- Also populated by Contract Admin Setup Wizard and Excel import
- Inquiry of original vs revised vs invoiced is **Prime contract budget and invoice history** (separate tool)
- Not a TeamLink form

## Who uses it

- Estimators / PMs enter original cost and hour budgets at job start
- Contract admins maintain SOV / GMP / unit-price items
- Financial analysts compare budget vs committed vs cost-to-date in Project Analytics
- Admins unlock a posted prime (when auto-lock is on and no workflow) to edit cost budgets

## Prerequisites

- Prime contract exists
- Job cost codes exist and are attached to the prime
- Cost Plus without GMP: no revenue/GMP budget; still enter cost and hour budgets
- Workflow: original cost budgets cannot be added/modified while a applicable rule is initiated or the transaction is already approved unless the rule is abandoned

## What the user fills out

### Cost Budgets (per job cost code)

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Materials (M) cost | No | Money | Exclude profit/fee. Excel: `MatlCostBudget` |
| Labor base cost | No | Money | Excel: `LbrBaseCostBudget` |
| Labor burden cost | No | Money | Excel: `LbrBurdenCostBudget` |
| Equipment base cost | No | Money | Excel: `EqpBaseCostBudget` |
| Equipment burden cost | No | Money | Excel: `EqpBurdenCostBudget` |
| Subcontract (S) cost | No | Money | Excel: `SubCostBudget` |
| Other (O) cost | No | Money | Excel: `OtherCostBudget` |

JCC total cost budget = sum of the five resource budgets.

Import Job Cost Code is available from Cost Budgets if a code was missing from the prime.

### Labor Hours

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Lbr. Hr. Budget | No | Hours | Excel: `LbrHrsBudget`. Leave 0 on codes with no labor timecards. Filter: Show Only Cost Codes with Lbr. Hour Budgets |

### Equipment Hours

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Eqp. Run Time Hrs | No | Hours | Excel: `EqpRunTimeHrsBudget` |
| Eqp. Down Time Hrs | No | Hours | Excel: `EqpDownTimeHrsBudget` |
| Eqp. Idle Time Hrs | No | Hours | Excel: `EqpIdleTimeHrsBudget` |

Help’s add-manual prime form also shows a single **Eqp. Hr. Budget**; the Excel split (run/down/idle) is the more complete persisted shape.

### Contract amount / revenue (per JCC or as SOV items)

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Revenue / Prime Contract Amount / GMP | Conditional | Money | Excel: `RevenueBudget`. FLS = proposal / SOV / bank draws. Cost Plus with GMP = GMP. Unit Price = estimated contract from estimated quantities. **Does not apply** to Cost Plus without GMP |
| Original contract item (SOV) fields | See prime-contracts.md | | ItemCode, description, qty, units, unit price, JCC, tax |

### How contract type uses budgets

| Contract type | Revenue / contract amount | M/L/E/S/O cost | Labor hours | Equipment hours |
|---|---|---|---|---|
| Fixed Lump Sum | Yes (SOV / bank draws) | Yes | Yes | Yes |
| Cost Plus with GMP | Yes (GMP) | Yes | Yes | Yes |
| Cost Plus without GMP | No | Yes | Yes | Yes |
| Unit Price | Yes (estimated) | Yes | Yes | Yes |

Approved COs with a status date add/deduct those same columns (Cost Plus without GMP: no revenue impact).

## What Sage CM saves

- Header record: budgets are children of the prime, not a standalone “budget document”
- Line / child records: per-JCC cost by resource; per-JCC hour budgets; original contract items
- System-generated values (IDs, numbers, dates, totals): JCC cost total; prime cost total; estimated profitability and markup % on the prime; **revised** cost/revenue/hours after Approved COs; pending vs approved CPR/CO amounts appear in analytics APIs (`RevenueBudget_PendingCOs_*`, `RevenueBudget_ApprovedCPRs_*`) but CPR amounts do **not** revise official budgets until copied to an Approved CO
- Files / attachments: none on the budget grids
- Audit / workflow fields: same workflow/auto-lock rules as the prime

## Statuses and lifecycle

Budgets have no independent status. They become “official original” when saved on the prime. They become **revised** when a CO is **Approved with a status date**.

CPRs never revise budgets, even if the CPR is Approved.

## Dates that drive alerts

None on the budget grids. Analytics date-filter for budget/CO dashboards uses CO **Status Date** (start-date filter is not available on dashboards that include prime budgets or COs).

## Relationships

- Upstream: Prime contract + job cost codes
- Downstream: Project Analytics (budget vs committed vs cost-to-date vs prime invoice); prime invoices bill against SOV/CO items, not against cost budgets; procurement commitments consume cost budget
- Allowance packages can seed SOV and cost values when the wizard is run from an estimate that tagged allowance items

## Reports and exports

- Prime record Cost Budgets / Labor Hours / Equipment Hours grids
- Excel import (`ImportJCCsPrimeBudgets`)
- Project Financial Analytics Cost and Revenue dashboards
- Analytics API v1 Overview Detailed: `RevenueBudget_*`, `CostBudget_*`, variance fields

## USIS / CM_Deploy mapping

| Sage concept | USIS table / API / page | Status |
|---|---|---|
| Original SOV / scheduled value | `prime_contract_sov_lines.scheduled_value` | partial |
| Resource cost budgets (M/L/E/S/O) | none | none |
| Labor / equipment hour budgets | none | none |
| Revised budget from COs | none | none |
| Project contract lump value | `project_contracts.contract_value` | stub (header only, not per JCC) |

## Sources

- Official Sage help URLs used
  - https://help.sagecm.intacct.com/Content/Modules/ContractAdministration/PrimeContract/PrimeContractBudgetsOverview.htm
  - https://help.sagecm.intacct.com/Content/Modules/ContractAdministration/PrimeContract/PrimeContractOriginalBudgetsCost.htm
  - https://help.sagecm.intacct.com/Content/Modules/Import/ImportJCCsPrimeBudgets.htm
  - https://help.sagecm.intacct.com/Content/Modules/ContractAdministration/CO/COOverview.htm
- Local files reviewed
  - `backend/app/models/prime_contract_sov.py`
  - `backend/app/models/project_contract.py`
