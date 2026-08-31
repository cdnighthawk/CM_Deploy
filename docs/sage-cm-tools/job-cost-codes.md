# Job Cost Codes

Status: complete
Sage CM module: Client Contract Admin
Official help: https://help.sagecm.intacct.com/Content/Modules/ContractAdministration/JobCostCodes/JobCostCodesOverview.htm

## Purpose

Job cost codes (JCCs) are the project-specific work-breakdown identifiers Sage uses on every financial line: budgets, CPRs, COs, POs, bills, subcontracts, SCOs, sub invoices, timecards, and retainage. They do **not** store original budgets (those live on the prime). Resource type is not encoded in the code: Sage already has five built-in resources — Materials (M), Labor (L), Equipment (E), Sub (S), Other (O).

## Where it lives

- Project menu → **Client Contract Admin** → **Job Cost Codes**
- Record list with Actions → Add Manually, import, bulk order reset
- Also created by the Contract Admin Setup Wizard on Client Contract Admin Overview
- Not a TeamLink create form; codes appear as lookups on vendor/client transactions

## Who uses it

- Contract admins and PMs create and maintain the project code list
- Estimators seed codes from an estimate or Excel
- Accounting staff map codes (or internal grouping) to ERP service items via AccountingLink
- Everyone who enters a financial line selects a code; they typically do not edit the master list

## Prerequisites

- Project exists
- Review Settings job cost code / classification options
- Optional: master cost-code list, sample JCC templates, another project to copy from, or Excel import
- Optional: AR/AP tax codes (Settings → Company Settings → Taxation)
- Optional: workers compensation codes (Settings → Feature Settings → Time & Expenses)
- Optional: owner cost-code list when the owner’s WBS differs from yours
- RSMeans users must label the uploaded list **CSI 2016** (with a space), even for newer CSI years

## What the user fills out

### Add job cost codes manually (Actions → Add Manually)

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Project # | Yes | Project | Defaults to current project |
| Order Number | No | Integer | Sort order of the list; bulk reset available |
| Code | Yes | Text (not numeric) | `01100` and `1100` sort differently. Do not append `-M` / `-L`; resource is a separate field on transactions |
| Description | Yes | Text | |
| Quantity | Yes | Number | Usually `1` for FLS / Cost Plus. For Unit Price, use estimated project quantity |
| Units | No (typically set) | Text | Usually `LS` for FLS / Cost Plus; unit of measure for Unit Price |
| Default Tax Code | No | Tax lookup | Typically blank except Canada |
| Internal grouping — Division code + description | No | Text | Hidden by default; add via Columns |
| Internal grouping — Major code + description | No | Text | Same |
| Internal grouping — Minor code + description | No | Text | Same |
| Internal grouping — Subminor code + description | No | Text | Same |
| Owner Code | No | Owner cost-code lookup | Owner/customer WBS mapped to this internal code |
| Default Workers Compensation Code | No | Lookup | Used on labor timecards |
| Default AP Tax Code | No | Tax lookup | POs, bills, subcontracts, SCOs, sub-invoice retainage, misc expenses |
| Default AR Tax Code | No | Tax lookup | Prime, CPR, CO, prime-invoice retainage |

### Excel / wizard columns (when creating codes with budgets)

Confirmed in the Excel import help. These are written onto the **code** and, where noted, onto the **prime budget**.

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Order | Yes | Number | Sort order |
| CostCode | Yes | Text | AccountingLink match key (or an internal grouping field) |
| CostCodeDescription | Yes | Text | |
| ItemCode | No | Text | SOV item code; usually blank |
| Quantity | Yes | Number | Defaults to 1 if omitted |
| Units | Yes | Text | |
| CostCodeDiv / CostCodeDivDesc | No | Text | Internal division |
| CostCodeMaj / CostCodeMajDesc | No | Text | Internal major |
| CostCodeMin / CostCodeMinDesc | No | Text | Internal minor |
| CostCodeSubmin / CostCodeSubminDesc | No | Text | Internal subminor |
| ARTaxCode | No | Text | Must already exist in Taxation |
| APTaxCode | No | Text | Must already exist in Taxation |
| WorkCompCode | No | Text | Must already exist in Time & Expenses settings |
| OwnerCostCode / OwnerCostCodeDesc | No | Text | Owner WBS |

Budget columns (`MatlCostBudget`, `LbrBaseCostBudget`, …, `RevenueBudget`, hour budgets) are **prime budget** fields, not stored as the job cost code itself. See `budgets.md`.

## What Sage CM saves

- Header record: one job cost code per project (codes are project-specific)
- Line / child records: optional owner-code link; default tax and workers-comp assignments
- System-generated values (IDs, numbers, dates, totals): Sage integer job cost code ID (exported as `job_cost_code_corecon_id` in Corecon transaction extract); Order #; created/modified timestamps
- Files / attachments: none on the code itself
- Audit / workflow fields: none specific to JCC create; codes become required FKs on later transactions

Corecon / analytics persist: JobCostCode, JobCostCodeDescription, JobCostCodeQuantity, JobCostCodeUnit, Internal Division/Major/Minor/SubMinor + descriptions, OwnerCostCode + description.

## Statuses and lifecycle

Job cost codes do not use Draft / Pending / Approved. They are active project master data. You can add codes at any time; Sage recommends creating them during project setup because every later financial line needs a code.

Deleting or changing a code after transactions exist is restricted in practice (transactions already reference it). Exact delete rules are not confirmed in help.

## Dates that drive alerts

None. Codes have no due or status dates.

## Relationships

- Upstream: Project; optional estimate, master list, another project, or Excel
- Downstream: Prime contract SOV / budgets; CPR proposed items; CO items; allowance items; anticipated costs; PO / bill / subcontract / SCO lines; prime and sub invoice retainage; labor and equipment timecards
- AccountingLink maps CostCode or an internal grouping field to the ERP service item

## Reports and exports

- Job Cost Codes list (on-page Columns, bulk order)
- Excel import/export via Contract Admin Setup Wizard
- Project Financial Analytics APIs expose JobCostCodeId, Order, Code, Description, Quantity, Unit, internal grouping, owner code
- Corecon transaction-details export includes the same code hierarchy

## USIS / CM_Deploy mapping

USIS stores a thin project code list used by RFIs and commitments. It does not model order, quantity, units, grouping, owner codes, or default tax/comp.

| Sage concept | USIS table / API / page | Status |
|---|---|---|
| Job cost code | `rfi_cost_codes` (`CostCode`: `code`, `description`, `is_active`) | stub |
| Order #, Quantity, Units | none | none |
| Internal grouping / owner codes | none (Corecon import has the columns on `corecon_transactions`) | none |
| Default AR/AP tax, workers comp | none | none |
| Commitment line cost code | `commitment_line_items.cost_code_id` → `rfi_cost_codes` | partial |

## Sources

- Official Sage help URLs used
  - https://help.sagecm.intacct.com/Content/Modules/ContractAdministration/JobCostCodes/JobCostCodesOverview.htm
  - https://help.sagecm.intacct.com/Content/Modules/ContractAdministration/JobCostCodes/JobCostCodesAddManual.htm
  - https://help.sagecm.intacct.com/Content/Modules/Import/ImportJCCsPrimeBudgets.htm
  - https://help.sagecm.intacct.com/Content/Administration/Settings/CompanySettings/CompanySettings_CostCodes.htm
- Local files reviewed
  - `backend/app/models/rfi_lookups.py`
  - `backend/app/models/corecon_transaction.py` (job cost code + owner code columns)
  - `backend/app/models/commitment.py`
