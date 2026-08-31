# Prime Contracts

Status: complete
Sage CM module: Client Contract Admin
Official help: https://help.sagecm.intacct.com/Content/Modules/ContractAdministration/PrimeContract/PrimeContractOverview.htm

## Purpose

A prime contract (also called a client contract) is the formal agreement between the owner/client and your firm. It holds scope, original budgets, default retainage, and the **contract type** that drives how prime invoices are built. Most jobs have one prime; design-build or CM firms may have several (each PO/subcontract/timecard must attach to exactly one). Sage will not allow procurement, time, or invoices until this record is **Approved with a status date**.

## Where it lives

- Project menu → **Client Contract Admin** → **Prime Contracts** (list) → record form
- Also created by Contract Admin Setup Wizard from Client Contract Admin Overview
- Recommended path: wizard (creates codes + prime + budgets together). Alternative: Actions → Add Manually
- Email/PDF of the prime can be sent to the client for signature
- TeamLink: clients do not create primes; they later see related CPRs, allowance packages, and invoices

## Who uses it

- Contract admins / PMs create and maintain the prime
- Financial admins set retainage defaults, tax, and lock/unlock after AccountingLink export
- Owners/architects receive emailed contract PDFs; they do not edit the Sage record
- Admins can still edit an **Approved and Closed** prime without reverting status

## Prerequisites

- Project exists
- Client and your firm are in the project directory (Architect / Client Rep recommended)
- Job cost codes exist, or you will select them in the add wizard Step 2
- Optional: tax codes; scope templates; default CPR/CO and Cost Plus invoice markups
- AccountingLink + Sage 100 Contractor: prime number must be numeric and must not start with `0`

## What the user fills out

### Header — Add a prime contract manually, Step 1

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Project # | Yes | Project | Defaults to current project |
| Prime Contract # | No (defaulted) | Text / numeric | Defaulted from project. Sage 100 Contractor: digits only, no leading zero |
| Issue Date | Yes (update as needed) | Date | |
| Contract Type | Yes | Enum | Fixed Lump Sum; Cost Plus with GMP; Cost Plus without GMP; Unit Price. Cannot change once SOV/GMP/unit-price items exist |
| Status | Yes | Enum | Draft, Pending Submission, Pending, Not Approved, Approved, Approved and Closed. Disabled when a workflow rule applies |
| Status Date | No on create; **required for financial unlock** | Date | Must be set with Approved before any PO, subcontract, timecard, or invoice |
| Subject | Yes | Text | Work subject |
| Prime Contract Address | No | Address | Used when one project has multiple structures/lots |
| Issued By (Client) — Company | Yes | Project directory company | Owner |
| Issued By — Address Type | Yes | Address type | |
| Issued By — Contact | No | Contact | |
| Issued To (Your Firm) — Company | Yes | Project directory company | |
| Issued To — Address Type | Yes | Address type | |
| Issued To — Contact | No | Contact | |
| Architect / Client Rep — Company | Recommended | Project directory company | Help marks Company + Address Type required **if** the section is used; section itself is optional |
| Architect / Client Rep — Address Type | Conditional | Address type | |
| Architect / Client Rep — Contact | No | Contact | |
| Work Scope | Yes | Rich text | |
| Inclusions / Exclusions / Clarifications | No | Rich text | Or Import Scope from Settings → Templates and Reports → Scope Templates |
| Prime Retainage % — Work Completed | No | Percent | Copied to future prime invoices |
| Prime Retainage % — Stored Materials | No | Percent | FLS only |
| Sub Retainage % — Work Completed | No | Percent | Copied to future subcontracts |
| Sub Retainage % — Stored Materials | No | Percent | FLS only |
| Estimated Start / Substantial Completion / Finish | No | Date | |
| Actual Notice to Proceed / Start / Substantial Completion / Finish | No | Date | |
| Incentives Per Day | No | Money | |
| Liquidated Damages Per Day | No | Money | |

### Step 2 — Select job cost codes

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Job cost codes applicable to this prime | Yes | Multi-select of project JCCs | Each selected code can later hold SOV + cost/hour budgets |

### Step 3 — Estimated budgets and costs (per selected JCC)

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Materials Cost | No | Money | Exclude profit/fee |
| Lbr. Base Cost / Lbr. Burden Cost | No | Money | |
| Eqp. Base Cost / Eqp. Burden Cost | No | Money | |
| Sub Cost | No | Money | |
| Other Cost | No | Money | |
| Lbr. Hr. Budget | No | Hours | Enter only for codes that will have labor timecards |
| Eqp. Hr. Budget | No | Hours | Enter only for codes that will have equipment timecards |
| Prime Contract Amount | Conditional | Money | Required for FLS, Cost Plus with GMP, and Unit Price. Not used for Cost Plus without GMP |

### Original contract items (edited after create)

On the prime record, Original Prime Contract Budgets / contract items (SOV, GMP amounts, or unit-price items):

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Item code | No | Text | Excel `ItemCode`; often blank |
| Description | Yes (typical) | Text | not confirmed as labeled required in add-manual help; present on SOV |
| Quantity / Units / Unit price | Conditional | Number / text / money | Unit Price: quantity = estimated project quantity |
| Job cost code | Yes | JCC | |
| Tax code | No | AR tax | |
| Scheduled / contract value | Conditional | Money | FLS SOV or GMP cap per code |

## What Sage CM saves

- Header record: prime contract (parties, type, status, status date, scope, retainage defaults, schedule dates, incentives/LDs, owner PO ref)
- Line / child records: original contract items (SOV / GMP / unit price); cost budgets by resource per JCC; labor and equipment hour budgets; linked files; optional customer deposits / advance payments (separate topic)
- System-generated values (IDs, numbers, dates, totals): Sage prime contract ID; contract number; estimated profitability and markup %; revised budgets after Approved COs with a status date; Corecon export: `prime_contract_corecon_id`, number, subject, billing type, issue/approval dates, owner/prime company and contact, status, est start/finish, CO impact days
- Files / attachments: upload/link on the prime; email attaches the prime PDF
- Audit / workflow fields: workflow lock while a rule is initiated or approved; AccountingLink auto-lock when posted/exported; Admins can unlock to edit cost budget or (if no invoices) contract items

## Statuses and lifecycle

Official sequence: **Draft → Pending Submission → Pending → Not Approved → Approved → Approved and Closed**.

| Status | Effect |
|---|---|
| Draft / Pending Submission / Pending / Not Approved | Prime exists but **does not** unlock financial transactions |
| **Approved + status date** | Unlocks POs, subcontracts, timecards, invoices. This is the gate Sage documents |
| Approved and Closed | No new Client Contract Admin, Procurement, or Time & Expense transactions except Admins. Project stays active; analytics still include the prime |

Locks after invoices exist: Contract Type, Status, and Status Date cannot change. Original items cannot be added/modified if Settings → Feature Settings → Contract Admin → **Do not allow Prime Contract or Change Order Items to be modified after Prime Invoices have been created** is on. Invoiced items cannot be modified.

## Dates that drive alerts

- Issue Date
- Status Date (financial gate and analytics filter date for the prime)
- Estimated and actual start / substantial completion / finish
- Notice to Proceed
- Reminder/follow-up dates are not on the prime header (those are on CPR/allowance)

Analytics filter for prime revenue uses **Status Date**.

## Relationships

- Upstream: Project, directory companies, job cost codes (or created with the wizard)
- Downstream: Original budgets; allowance packages; CPRs; COs; prime invoices; every PO, bill, subcontract, SCO, sub invoice, anticipated cost, and timecard must reference this prime
- Multiple primes: each commitment/timecard belongs to one prime only

## Reports and exports

- Download, share, or email prime contract (Report → Email Doc or Email PDF)
- Original budget views on the prime (Cost Budgets, Labor Hours, Equipment Hours)
- Project Financial Analytics; BI Summary dashboards
- AccountingLink export; Corecon transaction extract (`TransactionSource` includes Prime Contract)

## USIS / CM_Deploy mapping

| Sage concept | USIS table / API / page | Status |
|---|---|---|
| Prime / client contract header | `project_contracts` (`contract_number`, `title`, `contract_value`, `contract_date`, `start_date`, `substantial_completion_date`, `closeout_date`, `retention_percentage`, `is_primary`) | partial |
| Contract type, status, status date, parties, scope | none on `project_contracts` | none |
| Original SOV | `prime_contract_sov_lines` / `GET\|PUT /api/v1/projects/{id}/prime-contract/sov` | partial |
| Cost / hour budgets by resource | none | none |
| Corecon prime header on transactions | `corecon_transactions` prime_contract_* columns | implemented (import only) |

## Sources

- Official Sage help URLs used
  - https://help.sagecm.intacct.com/Content/Modules/ContractAdministration/PrimeContract/PrimeContractOverview.htm
  - https://help.sagecm.intacct.com/Content/Modules/ContractAdministration/PrimeContract/PrimeContractAddManual.htm
  - https://help.sagecm.intacct.com/Content/Modules/ContractAdministration/PrimeContract/PrimeContractBudgetsOverview.htm
  - https://help.sagecm.intacct.com/Content/Modules/ContractAdministration/SetupWizards/ContractAdminSetupWizard.htm
- Local files reviewed
  - `backend/app/models/project_contract.py`
  - `backend/app/models/prime_contract_sov.py`
  - `backend/app/models/corecon_transaction.py`
  - `backend/app/api/_project_contract_service.py`
