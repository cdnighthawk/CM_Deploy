# Prime Invoices

Status: complete
Sage CM module: Client Contract Admin
Official help: https://help.sagecm.intacct.com/Content/Modules/ContractAdministration/PrimeInvoice/PrimeInvoiceOverview.htm

## Purpose

Prime contract invoices are owner progress billings (Application for Payment commercially; bank draw residentially). They are **not** subcontract invoices. The wizard changes with contract type: FLS uses current work / stored / % complete on SOV and CO lines; Unit Price uses current invoiced quantity; Cost Plus imports approved billable expenses and timecards. Retainage is tracked **by job cost code**, not by SOV/CO line. Only **approved** invoices appear in analytics and AccountingLink.

## Where it lives

- Project menu → **Client Contract Admin** → **Prime invoices**
- Actions → Add Manually opens the type-specific wizard
- Also: convert work order → prime invoice (Cost Plus)
- Download / email invoice or lien waiver
- TeamLink: not the create path for the GC; client may receive emailed PDF

## Who uses it

- Project accountants / PMs prepare draws
- Owner/architect certify offline; user then checks Approved
- Admins unlock after AccountingLink auto-lock for non-financial edits
- Workflow approvers when prime-invoice rules exist

## Prerequisites

- Prime **Approved with a status date**
- FLS / Unit Price: COs that should bill this period must be Approved with issue **and** status dates **before** the planned invoice issue date
- Cost Plus: expenses/timecards must be Approved, Billable, amount > 0, date ≤ invoice issue date, and not already on a prior prime invoice
- Optional: sales/GST codes on billed retainage by JCC; default Cost Plus markups
- Do not check Approved until the invoice is complete

## What the user fills out

### Common header (FLS add wizard Step 2; Unit Price add is the same family)

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Project # | Yes | Project | **Cannot change after save** — delete and recreate |
| Prime Contract # | Yes | Prime | Client, contractor, architect/rep default from prime |
| Client Contact / Client Address Type | Address type typical | | Address Type usually Company Billing Address |
| Contractor Contact / Contractor Address Type | Address type typical | | |
| Architect/Client Rep Contact / Address Type | No | | |
| Sort Order # | Yes (defaulted) | Integer | **Not the invoice date.** Determines previous-invoice amounts. Auto next. Two invoices may share a date if order #s differ |
| Invoice # | No | Text | Auto next from numbering |
| Issue Date | No | Date | Defaults to today. Analytics filter date for prime invoices |
| Terms | No | Terms lookup | Auto-calculates Payment Due Date from term text |
| Payment Due Date | No | Date | Override terms |
| Approved | No | Checkbox | Unchecked = pending. Disabled if workflow applies. **Do not select until reviewed** |
| Work Retainage % | Typical | Percent | Default from prime (e.g. 10 = 10%) |
| Stored Material Retainage % | FLS | Percent | Default from prime; FLS stored materials |

### FLS — method (Step 3)

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Entry method | Yes | Choice | A: original contract and CO lines in separate steps; B: amount per JCC for unbilled original + CO lines; C: Invoice Retainage Only |

### FLS / shared line entry

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Current Work | One of work / stored / % | Money | **This period only** — excludes prior |
| Current Stored | One of work / stored / % | Money | This period only |
| % Complete | One of work / stored / % | Percent | **Cumulative**, includes prior periods |
| Tax Code | No | Tax | Bulk action available |
| Job Cost Code filter | No | JCC | Option B |

Bulk actions: % Complete, Current Work, Current Stored, Tax Code.

Negative approved CO lines must be imported and billed in full.

### FLS Option C / retainage release (by JCC, not by item)

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Work Retainage Release Amount or % | Conditional | Money / percent | Cannot exceed previous + current retainage |
| Stored Retainage Release Amount or % | Conditional | Money / percent | |
| Show Owner Code | No | Toggle | Filter/display owner codes |

Always invoice or release retainage **last** on a mixed invoice.

### Unit Price lines

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Current Inv. Qty. | Yes for billed items | Quantity | Only items billed this period |
| Work Retainage % / release | Same as FLS work retainage | | Stored retainage not used on the Unit Price add page |

### Cost Plus (overview rules; line grid labels not fully listed on FLS page)

Import approved Billable bills, timecards, and (optional) work-order conversion. Job cost code required on invoice items. Default Cost Plus markups may apply. Exact Cost Plus column names beyond those rules are not confirmed on the FLS add page — see Cost Plus add help if modeling that type.

## What Sage CM saves

- Header record: prime invoice (order #, invoice #, issue date, terms, due date, approved flag, retainage percents, parties)
- Line / child records: billed original items; billed CO items; retainage release by JCC; tax total; Cost Plus imported expenses
- System-generated values (IDs, numbers, dates, totals): previous / current / billed retainage by JCC; G702-style totals (contract to date, completed and stored, retainage, prior certificates, current payment due). Corecon `TransactionSource` Prime Invoice and Prime Invoice Retainage
- Files / attachments: invoice/lien-waiver PDFs; linked files
- Audit / workflow fields: workflow lock; AccountingLink auto-lock; lock/unlock; reset invoice after contract changes

## Statuses and lifecycle

Prime invoices use an **Approved checkbox**, not the five-step Draft→Approved list.

| State | Effect |
|---|---|
| Pending (Approved unchecked) | Saved but **not** in Project Analytics; not AccountingLink-exportable as approved |
| **Approved** | Cost/revenue-to-date in analytics; exportable; can auto-lock |

Workflow: if a rule is initiated or approved, no edits unless abandoned.

Exported + auto-lock: only an Admin unlocks for **non-financial** changes.

## Dates that drive alerts

- Issue Date (analytics; CO/expense eligibility)
- Payment Due Date
- Expense/timecard date and status date must be ≤ invoice issue date

## Relationships

- Upstream: Approved prime; Approved COs (FLS/UP); approved billable costs (Cost Plus)
- Downstream: AccountingLink AR; lien waiver; customer deposits/advance payments (related help)
- Distinct from sub invoices

## Reports and exports

- Download, share, or email prime invoice details or lien waiver
- Project Analytics PrimeInvoice_Approved_* / Pending_*
- AccountingLink; optional auto-lock on export
- Reset tax codes; reset invoice after contract changes

## USIS / CM_Deploy mapping

USIS models G702/G703-style pay applications, not Sage’s Approved-checkbox + per-type wizards.

| Sage concept | USIS table / API / page | Status |
|---|---|---|
| Prime invoice / pay app header | `pay_applications` / `/api/v1/projects/{id}/pay-applications` | partial |
| SOV billing lines | `pay_application_lines` | partial |
| Status | `draft`, `submitted`, `held`, `certified`, `paid`, `rejected` — **not** Sage Approved checkbox | partial |
| Retainage by JCC | `retainage_total` header + line `retention_to_date` — not JCC-keyed | partial |
| Textura invoice id | `pay_applications.textura_invoice_id` | stub |
| Project detail pay apps UI | `project-detail-pay-apps.js` | partial |

## Sources

- Official Sage help URLs used
  - https://help.sagecm.intacct.com/Content/Modules/ContractAdministration/PrimeInvoice/PrimeInvoiceOverview.htm
  - https://help.sagecm.intacct.com/Content/Modules/ContractAdministration/PrimeInvoice/PrimeInvoiceFLSAdd.htm
  - https://help.sagecm.intacct.com/Content/Modules/ContractAdministration/PrimeInvoice/PrimeInvoiceFLSEdit.htm
  - https://help.sagecm.intacct.com/Content/Modules/ContractAdministration/PrimeInvoice/PrimeInvoiceUnitPriceAdd.htm
- Local files reviewed
  - `backend/app/models/pay_application.py`
  - `backend/app/api/_pay_application_service.py`
  - `W3CRM-v3.0-13_September_2025/gulp/src/assets/js/project-detail-pay-apps.js`
