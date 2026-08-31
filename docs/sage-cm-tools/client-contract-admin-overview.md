# Client Contract Admin Overview

Status: complete
Sage CM module: Client Contract Admin
Official help: https://help.sagecm.intacct.com/Content/GettingStarted/ImplementationPlan_Financials_01_JobCostCodes_Prime_Budgets.htm

## Purpose

The Client Contract Admin Overview is the project landing page for owner-side financial setup. It is the entry point for the Contract Admin Setup Wizard (job cost codes + prime contract + original budgets) and a hub to the rest of the Client Contract Admin tools: prime contracts, allowance packages, CPRs, change orders, prime invoices, budget/invoice history, and estimated percent complete. Sage treats this as the first financial implementation step: no POs, subcontracts, timecards, or invoices can be recorded until a prime contract is Approved with a status date.

## Where it lives

- Project menu → **Client Contract Admin** → **Client Contract Admin Overview**
- Replaced the old Project Home **Financials** tab (October 2023 project menu)
- Overview / hub page, not a record list and not a single-record form
- Not a TeamLink or mobile data-entry tool; it is an internal project-home hub

## Who uses it

- Project managers and contract administrators start the Contract Admin Setup Wizard here
- Financial admins review whether codes, prime contract, and budgets exist before procurement
- System administrators unlock or re-run setup when workflow or auto-lock blocks edits
- Most field users only view; they do not create records from this page

## Prerequisites

- A project must exist
- Client (owner) and your firm should already be in the project directory before the wizard creates the prime contract
- Optional: a Sage CM estimate, master cost-code list, sample JCC template, or Excel 97-2003 (`.xls`) import file
- Optional: tax codes in Settings → Company Settings → Taxation
- Optional: scope templates in Settings → Templates and Reports → Scope Templates

## What the user fills out

This page is a hub. The only create action launched from it is the **Contract Admin Setup Wizard**. Users do not fill a single “overview” record.

### Contract Admin Setup Wizard (from this page)

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Customer / client company | Yes | Project directory company | Wizard first step; can add New customer |
| Job cost code / budget source | Yes | Choice | Use Sage CM Estimate (if estimate exists); Use Microsoft Excel Import File (recommended if no estimate); Create From Sage CM Sample JCC Templates; Select Cost Codes from the Master Cost Code List in Settings |
| Excel file | Conditional | `.xls` | Required when Excel source is selected. Sheet must be `Sheet1`. See budgets / job cost codes docs for columns |
| Estimate | Conditional | Existing estimate | Required when “Use Sage CM Estimate” is selected |
| Classification Type | Conditional | Lookup | CSI, NAHB, etc. when using sample JCC templates |
| Division / Major / Minor / Subminor level | Conditional | Choice | Master list import is one level at a time |
| Create Owner Codes from Internal Grouping Codes | No | Checkbox | Maps an internal grouping field to owner codes |
| Create Project Job Cost Codes from Estimate Cost Codes with Non Zero Subtotals Only | No | Checkbox | Default on when using an estimate |
| Work Subject | Yes (wizard prime header) | Text | Prime contract subject |
| Issue Date | Yes (wizard) | Date | Prime contract issue date |
| Owner PO Ref | No | Text | Owner purchase-order reference on the prime |
| Contract Type | Yes | Enum | Fixed Lump Sum; Cost Plus with GMP; Cost Plus without GMP; Unit Price. Drives which budgets apply and how prime invoices work |
| Status / Status Date | Yes for financial unlock | Enum + date | Must become Approved with a status date before procurement and time/expense |

## What Sage CM saves

The overview itself is not a persisted document. The wizard writes three related record sets:

- Header record: one **prime contract** (client, contractor, architect/rep, type, status, status date, retainage defaults, scope)
- Line / child records: **job cost codes** for the project; **original contract items** (Schedule of Values / GMP / unit-price items); **cost budgets** by resource (M/L/E/S/O); **labor hour** and **equipment hour** budgets
- System-generated values (IDs, numbers, dates, totals): prime contract number (defaulted from project; Sage 100 Contractor AccountingLink requires numeric, no leading zero); job cost code Order #; contract amount / GMP totals; estimated profitability % = `((Contract Amount - Cost Budget) / Contract Amount) * 100`; estimated markup % = `((Contract Amount - Cost Budget) / Cost Budget) * 100`
- Files / attachments: none on the overview; files attach later to prime, CPR, CO, invoice records
- Audit / workflow fields: if a prime-contract workflow rule applies, Status is disabled until the rule is abandoned or completed

## Statuses and lifecycle

This page has no status. It exists so users can get a prime contract to **Approved + status date**, which unlocks Client Contract Admin, Procurement, and Time & Expense transactions.

Prime contract sequence (set on the prime, not here): Draft → Pending Submission → Pending → Not Approved → Approved → Approved and Closed.

**Approved and Closed** locks new financial transactions for everyone except Admins. Nonfinancial project records stay editable. Analytics still show the contract.

## Dates that drive alerts

None on the overview itself. Downstream dates live on the prime (issue, estimated/actual start, substantial completion, finish, notice to proceed) and on CPRs/COs/invoices.

## Relationships

- Upstream: Project, project directory (client + your firm), optional estimate or master cost-code list
- Downstream: Job Cost Codes, Prime Contracts, Budgets, Allowance Packages, CPRs, Change Orders, Prime Invoices, Budget and Invoice History, Estimated Percent Complete, and all Procurement / Time & Expense tools that require an approved prime

## Reports and exports

- No dedicated “overview” detail report
- Wizard can import from Excel; after setup, use prime contract, budget, and analytics reports
- Project Financial Analytics (General info → Project Analytics) is the financial dashboard that replaced the old Financials tab content

## USIS / CM_Deploy mapping

USIS has no Client Contract Admin Overview page or wizard. Closest surfaces are project contract + SOV + pay-app tabs on the project detail page.

| Sage concept | USIS table / API / page | Status |
|---|---|---|
| Client Contract Admin Overview hub | none | none |
| Contract Admin Setup Wizard | none | none |
| Prime contract created by wizard | `project_contracts` / `GET|POST /api/v1/projects/{id}/contracts` | partial |
| Job cost codes created by wizard | `rfi_cost_codes` | stub |
| Original budgets / SOV | `prime_contract_sov_lines` / `GET|PUT /api/v1/projects/{id}/prime-contract/sov` | partial |

## Sources

- Official Sage help URLs used
  - https://help.sagecm.intacct.com/Content/GettingStarted/ImplementationPlan_Financials_01_JobCostCodes_Prime_Budgets.htm
  - https://help.sagecm.intacct.com/Content/Modules/ContractAdministration/SetupWizards/ContractAdminSetupWizard.htm
  - https://help.sagecm.intacct.com/Content/Modules/ContractAdministration/PrimeContract/PrimeContractOverview.htm
  - https://help.sagecm.intacct.com/Content/ReleaseNotes/October-2023/oct-23-projects-menu.htm
- Local files reviewed
  - `backend/app/models/project_contract.py`
  - `backend/app/models/prime_contract_sov.py`
  - `backend/app/models/rfi_lookups.py` (`CostCode`)
  - `docs/sage-cm-tools/_TEMPLATE.md`
