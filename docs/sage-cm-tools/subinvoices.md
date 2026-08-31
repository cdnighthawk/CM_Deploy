# Subinvoices

Status: complete
Sage CM module: Procurement
Official help: https://help.sagecm.intacct.com/Content/Modules/Procurement/SubInvoice/SubInvoiceOverview.htm

## Purpose

Subcontract invoices (sub invoices) are **progress payments to subcontractors** — not owner prime invoices and not PO bills. Wizards handle retainage, SCOs, and prior billing. Process varies by **subcontract type**. Retainage is stored **by job cost code**, not by SOV or SCO line. Always bill retainage **last**. **Only approved** sub invoices appear in Project Analytics and AccountingLink.

## Where it lives

- Project menu → **Procurement** → **Subinvoices**
- Actions → Add Manually (FLS / Cost Plus / Unit Price wizards)
- TeamLink: subs can create invoices; email goes to PM on prime/sub, else Internal Stakeholders PM, else first Administrator
- Download/email invoice or lien waiver
- Expired insurance: red warning

## Who uses it

- AP / PMs review and approve
- Subcontractors submit via TeamLink
- Workflow approvers
- Admins unlock after export auto-lock (non-financial only)

## Prerequisites

- Subcontract **Approved with a status date**
- Job cost codes (SOV, unit price, SCO, cost-plus entries, billed retainage)
- Optional: sales tax on cost-plus entries and billed retainage
- Review SCOs: Approved with status date **earlier than** the planned invoice issue date
- Duplicate invoice setting shared with bills (all active projects vs per project + vendor)

## What the user fills out

### Header — Add a subcontract invoice for a Fixed Lump Sum subcontract

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Project # | Yes | Project | **Cannot change after save** |
| Prime Contract # | Yes | Prime | |
| CO # | No | Owner CO | |
| WO # | No | WO | |
| Prime Contact | No | Contact | |
| Prime Address Type | Yes | Address type | Default Company Billing Address |
| Subcontract # | Yes | Approved subcontract | |
| Sub Contact | No | Contact | |
| Sub Address Type | Yes | Address type | Default Company Billing Address |
| Sort Order # | Yes | Integer | **Not the invoice date.** Determines previous invoice amounts. Auto next |
| Invoice # | Yes | Text | Vendor’s invoice number. Duplicate rules same as bills |
| Issue Date | No | Date | Defaults to today. Analytics filter date |
| Terms | No | Terms | Calculates Payment Due Date |
| Payment Due Date | No | Date | |
| Billable Status | No | Billable / Unbillable / On Hold | **Cost Plus prime import only.** Help states it is not applicable for FLS subcontracts |
| Approved | No | Checkbox | Default off (pending). Check only when complete. Disabled if workflow applies |
| Work Retainage % | No | Percent | Default from subcontract (e.g. 10 = 10%) |
| Stored Material Retainage % | No | Percent | Default from subcontract |

### FLS Step 2 — Unbilled original items (SOV)

Skipped if all SOVs are 100% billed. Fully invoiced SOVs omitted.

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Current Work **or** % Complete | Yes for billed rows | Money or percent | Current Work = this period only. % Complete = **cumulative** |
| Current Stored | Typical | Money | This period only |

### FLS Step 3 — Unbilled SCO items

Skipped if all SCOs 100% billed. Import only SCOs with issue **and** status date **before** this invoice’s issue date. Negative approved SCO lines: import and bill in full.

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Current Work or % Complete | Yes for billed rows | Money or percent | Same period vs cumulative rules |
| Current Stored | Typical | Money | This period only |

### FLS Step 4 — Release retainage (by JCC)

Usually a **separate** invoice after work meets spec.

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Work Retainage Release Amount | Conditional | Money | ≤ previous + current retainage |
| Stored Retainage Release Amount | Conditional | Money | Same cap |
| Tax Code | No | Tax | Typically blank in the US |

Cost Plus and Unit Price have their own add topics; billing-methods help describes the type-specific grids. Do not invent Cost Plus column names beyond: JCC required; tax optional on cost-plus entries and retainage.

## What Sage CM saves

- Header record: sub invoice (order #, invoice #, issue date, terms, due, approved, retainage %, billable status, parties)
- Line / child records: billed SOV; billed SCO; retainage release by JCC; tax total
- System-generated values: previous / current / billed retainage by JCC; net retainage (analytics SubInvoice_*_NetRetainage)
- Files / attachments: invoice and lien waiver PDFs
- Audit / workflow fields: workflow lock; cannot edit if imported into a Cost Plus **prime** invoice until removed; export auto-lock; reset after subcontract changes

## Statuses and lifecycle

**Approved checkbox** (pending if unchecked).

| State | Effect |
|---|---|
| Pending | Not in analytics; not AccountingLink |
| **Approved** | Cost to date; exportable; may auto-lock |

This is **not** the Draft → Approved commitment sequence.

## Dates that drive alerts

- Issue Date
- Payment Due Date
- SCO issue + status dates vs this issue date
- TeamLink create notification (no due-date field)

## Relationships

- Upstream: Approved subcontract; eligible SCOs
- Downstream: Analytics; AccountingLink; Cost Plus prime invoice if Billable
- Creating a sub invoice can freeze subcontract/SCO edits (Feature Setting)

## Reports and exports

- Download, share, or email sub invoice or lien waiver
- Troubleshoot missing retainage
- Reset tax codes; reset after subcontract changes
- Analytics SubInvoice_Approved_* / Pending_* including NetRetainage

## USIS / CM_Deploy mapping

`vendor_invoices` is email-intake AP (PO/bills), not Sage sub-invoice wizards.

| Sage concept | USIS table / API / page | Status |
|---|---|---|
| Sub invoice header / SOV / SCO / retainage-by-JCC | none | none |
| Vendor AP invoice | `vendor_invoices` | stub (wrong tool) |
| Pay application | `pay_applications` | none for subs (owner draws) |

## Sources

- Official Sage help URLs used
  - https://help.sagecm.intacct.com/Content/Modules/Procurement/SubInvoice/SubInvoiceOverview.htm
  - https://help.sagecm.intacct.com/Content/Modules/Procurement/SubInvoice/SubInvoiceFLSAdd.htm
- Local files reviewed
  - `backend/app/models/vendor_invoice.py`
  - `backend/app/models/pay_application.py`
