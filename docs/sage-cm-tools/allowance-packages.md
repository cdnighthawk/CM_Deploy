# Allowance Packages

Status: complete
Sage CM module: Client Contract Admin
Official help: https://help.sagecm.intacct.com/Content/Modules/ContractAdministration/AllowancePackage/AllowancePackageAddManual.htm

## Purpose

An allowance package lets the client pick finishes or allowances that were carried as placeholder money in the prime. Each package has allowance **items** (budgeted sell and cost) and **selection options** (manufacturer, catalog, sell/cost). The client chooses options in TeamLink; the Financial Summary shows allowance vs selected options. A later CO from the package posts the variance: original allowance items as negatives plus the selected options.

## Where it lives

- Project menu → **Client Contract Admin** → **Allowance Packages**
- List + Actions → Add Manually; also created by Contract Admin Setup Wizard when the source estimate has allowance-tagged items
- Record form: header → items/options → files
- **TeamLink**: client reviews items, picks options, sees Financial Summary. Package can be locked so TeamLink cannot change it
- Mobile: not confirmed in help as a dedicated create app; TeamLink is the client path

## Who uses it

- PMs / contract admins create packages and item options
- Clients (TeamLink) select options
- Contract admins convert a locked package to a change order
- Estimators indirectly seed packages when the wizard uses an estimate with Allowance checked

## Prerequisites

- Approved prime contract (add form: **Approved Prime Contract**)
- Job cost codes on the project (default JCC required when adding items)
- Optional: tax codes; work-item catalog for importing options
- If using the estimate path: estimate line items tagged Allowance; wizard creates one package per estimate cost code with total > 0 and copies those lines — it does **not** create options (those are added after)

## What the user fills out

### Header — Add Manually, Step 1

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Project # | Yes | Project | Defaults to current |
| Prime Contract # | Yes | Approved prime | |
| Issue Date | Yes | Date | Defaults to today |
| Allowance Package # | Yes | Text | Auto next number from company numbering |
| Subject | Yes | Text | |
| Client Company | Yes (disabled) | Company | Copied from prime; not editable |
| Client Address Type | Yes | Address type | |
| Client Contact | No | Contact | |
| Prime Contractor Company | Yes (disabled) | Company | Copied from prime |
| Prime Contractor Address Type | Yes | Address type | |
| Prime Contractor Contact | No | Contact | |
| Follow Up Date | No | Date | |
| Reqd. Completion Date | No | Date | Help also spells “Reqd Completion Date” |
| Actual Completion Date | No | Date | Older help typo: “Atual Completion Date” — UI label is Actual Completion Date |

### Default line-item values (Step 2)

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Resource | Yes | Enum | Materials (M), Labor (L), Equipment (E), Sub (S), Other (O) |
| Job Cost Code | Yes | JCC | |
| Tax Code | No | Tax | |

### Allowance item

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Item # | No | Text | Sort / identity |
| Description | Yes | Text | |
| Quantity | Yes | Number | |
| Unit of measure | No | Text | |
| Sell Rate (customer rate) | Yes | Money | |
| Cost Rate (internal) | No | Money | |
| Manufacturer / Catalog # / UPC | No on item; used on options | Text | Word template also exposes these on items |

### Selection options (per item; default three rows; Add Options / Add Selection)

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Option # | No | Text | |
| Description | Typical | Text | Requiredness not restated in current help; older add page listed it with sell rate |
| Manufacturer | No | Text | |
| Catalog # | No | Text | |
| UPC | No | Text | |
| Sell Rate | Typical | Money | Customer rate for the option |
| Cost Rate | No | Money | Internal |
| Resource | No | M/L/E/S/O | Older add page; confirm on option row if shown |

User can Skip item entry and add later. Files are Step 3 (or Skip and Finish).

## What Sage CM saves

- Header record: allowance package (number, subject, issue date, parties from prime, follow-up / required / actual completion)
- Line / child records: allowance items (qty, sell, cost, JCC, tax, resource); option rows; **selected option** (client TeamLink choice); calculated variance (contract subtotal less cost budget)
- System-generated values (IDs, numbers, dates, totals): package number; item/option counts; ItemsSubtotal, ItemsTax, ItemsTotal; ItemsCostBudgetMatl/Lbr/Eqp/Sub/Other/Total; ItemsContractSubtotalLessCostBudget; same for selected options and impact totals (Word template bookmarks)
- Files / attachments: up to 48 files per drop, 500 MB total; link Drawings & Specs, Photos, or All Other Records from the same project/lead
- Audit / workflow fields: lock for TeamLink after send / before CO; Actions email “allowance package response request”

## Statuses and lifecycle

Help does not publish Draft → Pending → Approved for allowance packages. Lifecycle that **is** documented:

1. Create package + items; add options (wizard will not create options)
2. Email response request; client selects in TeamLink
3. Lock package (no further TeamLink edits)
4. Convert package to a **change order**: proposed items = original allowance items (negative) + selected options; CO subtotal = variance
5. CO must still be **Approved with a status date** before budgets / analytics / prime invoices change

## Dates that drive alerts

- Follow Up Date
- Reqd. Completion Date
- Actual Completion Date
- Issue Date

Exact alert rules for those dates are not confirmed in help.

## Relationships

- Upstream: Approved prime; job cost codes; optional estimate allowance lines
- Downstream: Change order (Allowance to CO wizard); prime invoice only after that CO is Approved with a status date on or before the invoice issue date (FLS / Unit Price)

## Reports and exports

- Prime contract allowance package Microsoft Word / mail-merge template (general bookmarks + AllowanceItems table)
- Download/share not separately documented beyond standard record files
- Training: Allowance packages; Allowance to CO Wizard

## USIS / CM_Deploy mapping

| Sage concept | USIS table / API / page | Status |
|---|---|---|
| Allowance package header / items / options | none | none |
| Client selection / TeamLink | none | none |
| Variance CO from package | none | none |

## Sources

- Official Sage help URLs used
  - https://help.sagecm.intacct.com/Content/Modules/ContractAdministration/AllowancePackage/AllowancePackageAddManual.htm
  - https://help.sagecm.intacct.com/Content/Modules/ContractAdministration/ChangeBusProcesses/ChangeBusProcesses.htm
  - https://help.sagecm.intacct.com/Content/Modules/Reporting/DetailReportTemplates/ContractAdministration/PrimeContractAllowancePackage.htm
- Local files reviewed
  - `backend/app/models/project_contract.py` (prime only; no allowance entity)
