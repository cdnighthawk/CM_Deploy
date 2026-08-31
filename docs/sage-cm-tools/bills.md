# Bills

Status: complete
Sage CM module: Procurement
Official help: https://help.sagecm.intacct.com/Content/Modules/Procurement/Bills/BillsOverview.htm

## Purpose

A bill is the supplier invoice after a PO is delivered (or a no-PO expense). **PO to Bill** is the recommended path: it matches received quantities to open PO items and prevents overbilling. One PO can generate many bills. Manual bills exist for costs without a PO. **Only approved bills** are Cost to Date in Project Analytics and exportable via AccountingLink. Cost Plus primes can import **Billable** bill lines into the prime invoice.

## Where it lives

- Project menu → **Procurement** → **Bills**
- Actions → Add from PO (recommended); Add Manually; Excel import; Copy
- Record: header, default line values, bill items, tax, lock
- Expired insurance: warning in red; bill still saves
- TeamLink: not the GC create path

## Who uses it

- AP / project accountants enter or match bills
- PMs set Billable / Unbillable / On Hold for Cost Plus
- Workflow approvers; Admins unlock after AccountingLink auto-lock
- AccountingLink maps **Bill Type** to the ERP

## Prerequisites

- Prime **Approved with a status date**
- Vendor in project directory
- Job cost code on every bill item
- Optional: bill types (Feature Settings → Procurement); tax codes
- Duplicate invoice setting: Settings → Feature Settings → Procurement → **Check Duplicate Invoice Numbers on Bills and Sub Invoices for all Active Projects**
- PO path: PO **Approved with a status date**; PO items open/closed only via PO to Bill

## What the user fills out

### Header — Add a bill manually

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Project # | Yes | Project | |
| Prime Contract | Yes | Approved prime | |
| CO # | No | CO lookup | |
| WO # | No | WO lookup | |
| Issue Date | No | Date | Defaults to today. Analytics cost filter date for bills |
| Invoice # | Yes | Text | Vendor invoice / reference. Unique across all active projects if the duplicate setting is on; else unique per project + vendor |
| Approved | No | Checkbox | Unchecked = pending. Disabled if workflow applies |
| Bill Type | No | Lookup | Feature Settings → Procurement; affects AccountingLink |
| Subject | Yes | Text | Coordinated By section |
| Company (vendor) | Yes | Project directory | Add new/existing inline |
| Address | Yes | Address | |
| Contact | No | Contact | |
| Terms | No | Terms | |
| Payment Due | No | Date | |

### Default line item values

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Job Cost Code | No | JCC | Fallback |
| Tax Code | No | AP tax | Fallback |
| Resource | No | M/L/E/S/O | Default **M** |
| Billable Status | No | Enum | Default **Billable**. Billable / Unbillable / On Hold. Cost Plus prime invoices only |

### Bill items

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Item # | Yes | Text | Sort order |
| Description | Yes | Text | |
| Quantity | Yes | Number | |
| Units | No | Text | |
| Unit Price | Yes | Money | |
| Cost Code | No | JCC | Required in practice (fallback or explicit). Overview: a JCC **must** be referenced |
| Tax Code | No | AP tax | |
| Resource | Yes or default | M/L/E/S/O | |
| Billable | No | Billable / Unbillable / On Hold | On Hold = uncertain at prime-invoice import time |

Imports: labor, equipment, work, estimate, estimate summary, anticipated costs, job cost codes (same rate-to-import lists as POs).

## What Sage CM saves

- Header record: bill (invoice #, issue date, approved, type, subject, vendor, terms, due, prime, CO/WO)
- Line / child records: bill items; tax total; PO-to-Bill quantity match / open-closed on PO items
- System-generated values: line totals; Corecon TransactionSource Bill and Bill No PO
- Files / attachments: print/share; AccountingLink lock
- Audit / workflow fields: workflow lock; export auto-lock; cannot edit lines imported into a Cost Plus prime invoice until removed from that invoice

## Statuses and lifecycle

**Approved checkbox** (not the five-step list).

| State | Effect |
|---|---|
| Pending | Saved; **not** in analytics; not exportable as approved |
| **Approved** | Cost to Date; AccountingLink |

PO item Open/Closed is updated only by PO to Bill.

## Dates that drive alerts

- Issue Date
- Payment Due
- Duplicate invoice check is number-based, not date-based

## Relationships

- Upstream: Approved prime; optional approved PO; JCCs
- Downstream: Project Analytics cost-to-date; Cost Plus prime invoice (Billable lines); AccountingLink AP
- Fuel/truck costs may be a bill **or** a miscellaneous expense

## Reports and exports

- Print or share a bill
- Excel import
- AccountingLink (optional auto-lock)
- Analytics Bill_* and Bill_NoPO_*

## USIS / CM_Deploy mapping

| Sage concept | USIS table / API / page | Status |
|---|---|---|
| Vendor bill header | `vendor_invoices` | partial |
| Invoice #, dates, amount, PO # | `vendor_invoices` | partial |
| Approval / paid | `submitted_at`, `decided_at`, `paid_at`, `status` | partial (USIS AP workflow, not Sage Approved checkbox) |
| 3-way match | `match_status` | partial |
| Files | `vendor_invoices_files` | partial |
| Allocation to PO | `commitment_bill_allocations` + `commitment_id` | partial |
| Bill lines (JCC, resource, billable) | none first-class | none |
| PO to Bill wizard | none | none |

## Sources

- Official Sage help URLs used
  - https://help.sagecm.intacct.com/Content/Modules/Procurement/Bills/BillsOverview.htm
  - https://help.sagecm.intacct.com/Content/Modules/Procurement/Bills/BillsAddManual.htm
- Local files reviewed
  - `backend/app/models/vendor_invoice.py`
  - `backend/app/models/commitment.py` (`CommitmentBillAllocation`)
  - `Plan/22. Sage_CM_subcontracts_SCO_and_P2P_alignment.txt`
