# Change Orders

Status: complete
Sage CM module: Client Contract Admin
Official help: https://help.sagecm.intacct.com/Content/Modules/ContractAdministration/CO/COOverview.htm

## Purpose

A change order (CO) is an executed change to the **prime** scope. Anyone (owner, architect, agency, or your firm) can initiate it. COs exist for all prime types. When marked **Approved with a status date** (help also says “approved with a signed date”), the CO revises prime budgets. Only then do FLS/Unit Price prime invoices import the CO, and only if the CO status date is on or before the invoice issue date.

## Where it lives

- Project menu → **Client Contract Admin** → **Change orders (COs)**
- List + Actions → Add Manually; Add From CPR; convert from estimate, allowance package, or work order
- Record: header → files; then add/import CO items, tax, hour budgets
- TeamLink: not the primary create path (owner review is typically offline + status update)
- Workflow rules can lock the CO

## Who uses it

- Contract admins / PMs create COs and post status after owner execution
- Financial staff confirm budget impact and invoice eligibility
- Admins configure Initiated By and default markups; abandon workflow when edits are needed

## Prerequisites

- Prime **Approved with a status date**
- Reviewer in the project directory
- Job cost codes (required on CO Items)
- Optional: tax codes; default CPR/CO markups
- Settings → Feature Settings → Contract Admin → CPR/CO Initiated By

## What the user fills out

### Header — Add a change order manually, Step 1

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Project # | Yes | Project | |
| Prime Contract # | Yes | Approved prime | |
| Issue Date | No | Date | Defaults to today |
| CO Sort Order # | No | Integer | Auto; **order number** determines “previous CO amount” on the CO report (all Approved COs with status date and a lower order #) |
| CO # | No | Text | Auto next |
| Initiated By | No | Lookup | Feature Settings → Contract Admin |
| Subject | Yes | Text | When converting from CPR, include CPR numbers (e.g. CPR 001, 002, 005) |
| CO Status | Yes | Enum | Draft, Pending Submission, Pending, Approved, Not Approved. Disabled if workflow applies |
| CO Status Date | No | Date | Defaults to today; **this date + Approved** revises budgets and allows invoice import |
| Client Company | Yes (disabled) | Company | From prime |
| Client Address Type / Contact | Address type yes; contact no | | |
| Prime Contractor Company | Yes (disabled) | Company | From prime |
| Prime Contractor Address Type / Contact | Address type yes; contact no | | |
| Proposed Scope Of Work | No | Rich text | |
| References — Drawing / Location / RFI # / Spec. Section / Other | No | Mixed | Same as CPR |
| Schedule impact — To Be Determined Later | No | Checkbox | Clear to enter days |
| Schedule impact days | No | Integer | Persisted as prime `change_order_impact_days` in Corecon extract |

### CO items (added after create)

Same import family as POs (labor/equipment/work database, estimate, JCC). Manual item fields confirmed on sibling procurement add pages and CO edit (“Add, edit, or import CO items”):

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Item # | No | Text | Sort |
| Description | Yes | Text | |
| Quantity | Yes | Number | |
| Units | No | Text | |
| Unit Price | Typical | Money | |
| Job Cost Code | Yes | JCC | |
| Tax Code | No | AR tax | |
| Resource | Typical | M/L/E/S/O | Cost budget impact by resource |

CPR → CO item formats: **As in CPR** or **Summarize By JCC**.

Allowance → CO items: original allowance lines (negative) + selected options.

### Files — Step 2

48 files / 500 MB; link Drawings & Specs, Photos, All Other Records.

## What Sage CM saves

- Header record: CO (order #, CO #, subject, status, status date, initiated by, parties, scope, references, schedule days)
- Line / child records: CO items; tax total; labor/equipment hour budget deltas
- System-generated values (IDs, numbers, dates, totals): CO number and order; previous approved CO amount; Corecon `co_corecon_id`, `co_number`, `co_subject`, issue and status dates
- Files / attachments: uploaded/linked files
- Audit / workflow fields: workflow lock; lock/unlock CO

## Statuses and lifecycle

Official sequence: **Draft → Pending Submission → Pending → Approved or Not Approved**.

| Status | Effect |
|---|---|
| Draft / Pending Submission / Pending / Not Approved | No budget revision; not in analytics; not on prime invoices |
| **Approved + status date** | Revises revenue (except Cost Plus without GMP), cost, and hour budgets. Appears in Project Analytics. Importable on FLS/Unit Price prime invoices if issue date and status date are **on or before** the invoice issue date. Negative approved lines must be imported and billed in full |

Locks: cannot add/modify CO items if a prime invoice exists **and** “Do not allow prime contracts or change orders to be modified after prime invoices have been created” is on. **Invoiced CO items cannot be modified.** Workflow initiated/approved blocks edits unless abandoned.

## Dates that drive alerts

- Issue Date (must be ≤ prime invoice issue date for import)
- Status Date (budget + analytics + invoice eligibility)
- Schedule impact days (finish-date impact including COs)

## Relationships

- Upstream: Approved prime; optional CPR(s), estimate, allowance package, work order
- Downstream: Revised prime budgets; prime invoices (FLS/Unit Price); CPR → Procurement may still create POs/subcontracts/SCOs from the originating CPR
- Corecon `TransactionSource` includes CO

## Reports and exports

- Download, share, or email a CO
- CO report previous-amount logic (order # + Approved + status date)
- Project Analytics (Approved + status date only)
- Unit Price–specific help: “Create COs for Unit Price prime contracts”

## USIS / CM_Deploy mapping

| Sage concept | USIS table / API / page | Status |
|---|---|---|
| Owner change order header / items | none | none |
| Pay-app net change by COs | `pay_applications.net_change_by_change_orders` | stub (amount only) |
| Pay-app line net_change_co | `pay_application_lines.net_change_co` | stub |
| Corecon CO columns | `corecon_transactions` co_* | implemented (import only) |

## Sources

- Official Sage help URLs used
  - https://help.sagecm.intacct.com/Content/Modules/ContractAdministration/CO/COOverview.htm
  - https://help.sagecm.intacct.com/Content/Modules/ContractAdministration/CO/COAddManual.htm
  - https://help.sagecm.intacct.com/Content/Modules/ContractAdministration/SetupWizards/CPRToCOWizard.htm
- Local files reviewed
  - `backend/app/models/pay_application.py`
  - `backend/app/models/corecon_transaction.py`
