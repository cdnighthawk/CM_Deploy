# Purchase Orders

Status: complete
Sage CM module: Procurement
Official help: https://help.sagecm.intacct.com/Content/Modules/Procurement/POs/POsOverview.htm

## Purpose

A purchase order procures materials or services **without retainage**. Vendor invoices are billed with the **PO to Bill** wizard (one PO → many bills). POs are simpler than subcontracts (no SCO, no holdback). Sage warns in red if the vendor has expired insurance. **Committed cost requires Approved + status date.** The same pair is required before PO to Bill.

## Where it lives

- Project menu → **Procurement** → **Purchase orders (POs)**
- Actions: Add Manually; from WO, CPR, CO, estimate RFP, standalone RFP, project directory; Excel import; Copy
- Record: header, default line values, PO items, lock, files
- TeamLink: vendors can view approved PO COs; PO view/share/email from Sage
- Workflow: if a rule is initiated or approved, the PO cannot be edited unless abandoned

## Who uses it

- PMs / buyers issue POs
- Authorized By (PM or financial admin) is stored on the header
- AP uses PO to Bill
- Admins lock/unlock and maintain PO types

## Prerequisites

- Prime **Approved with a status date**
- Vendor in **project directory**
- Job cost codes for items
- Optional: PO types (Feature Settings → Procurement); tax codes; workflow
- Insurance on the vendor profile (warning only)

## What the user fills out

### Header

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Project # | Yes | Project | |
| Prime Contract | Yes | Approved prime | |
| CO # | No | CO lookup | Reference |
| WO # | No | WO lookup | Reference |
| Issue Date | No | Date | Defaults to today |
| PO # | Yes | Text | Auto / required |
| PO Subject | Yes | Text | |
| PO Type | No | Lookup | Optional categorization |
| PO Status | Yes | Enum | Draft, Pending Submission, Pending, Not Approved, Approved. Disabled if workflow applies |
| Status Date | No | Date | Defaults to today. **With Approved = committed cost** |
| Reminder Date | No | Date | |
| Vendor Company | Yes | Project directory | Can add new/existing company inline |
| Vendor Address | Yes | Address | |
| Vendor Contact | No | Contact | |
| Ship To Address | Recommended | Address | |
| Issued By | No | User | Person adding the PO |
| Authorized By | No | User | PM or financial admin |
| Issued & Authorized By — company Address | No | Address | |
| Terms | No | Terms | |
| FOB | No | Text | |
| Ship Via | No | Text | |

### Default line item values

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Delivery Date | No | Date | Applied when line delivery is blank |
| Job Cost Code | No | JCC | Fallback for lines |
| Tax Code | No | AP tax | Fallback |
| Resource | No | M/L/E/S/O | Fallback |

### PO items

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Item # | Yes | Text | Determines sort order |
| Description | Yes | Text | |
| Quantity | Yes | Number | |
| Units | No | Text | |
| Unit Price | Yes | Money | |
| Cost Code | No | JCC | Falls back to default |
| Tax Code | No | AP tax | Falls back to default |
| Resource | Yes (or default) | M/L/E/S/O | |
| Delivery Date | No | Date | Falls back to default delivery |

Imports: labor, equipment, work items, estimate items, estimate summary, anticipated costs, job cost codes. Exclude estimate items tagged on awarded RFPs.

## What Sage CM saves

- Header record: PO (number, subject, type, status, status date, vendor, ship-to, issued/authorized, terms/FOB/ship via, reminder, prime, CO/WO refs)
- Line / child records: PO items (qty, price, JCC, tax, resource, delivery); open/closed tracked **only via PO to Bill**; bills linked through repeated PO-to-Bill
- System-generated values: PO #; line totals; committed amount when Approved + status date; Corecon PO transaction + item IDs
- Files / attachments: download/share/email PO; link related files from CPR wizard
- Audit / workflow fields: workflow lock; lock/unlock PO; expired-insurance warning (save still allowed)

USIS extra (not Sage help): shipments, receipts, qty shipped/received/invoiced, fulfillment_status — USIS 3-way match, not documented on Sage PO overview.

## Statuses and lifecycle

**Draft → Pending Submission → Pending → Not Approved → Approved**

| Status | Effect |
|---|---|
| Draft / Pending Submission / Pending / Not Approved | Not committed cost; cannot PO-to-Bill |
| **Approved + status date** | Committed Cost in Project Analytics; PO to Bill allowed |

PO item open/closed is a **billing** state from PO to Bill, not the header status.

## Dates that drive alerts

- Reminder Date
- Issue Date / Status Date (analytics committed filter = Status Date)
- Line Delivery Date
- USIS-only ship/needed-on-site dates are not Sage PO header fields in help

## Relationships

- Upstream: Approved prime; directory vendor; JCCs; optional WO/CPR/CO/RFP/estimate/Excel
- Downstream: Bills (many); PO COs (one PO CO per approved PO); Cost Plus prime invoice if bill lines are Billable
- One PO cannot span two primes

## Reports and exports

- Download, share, or email PO
- Excel import
- Analytics PO_Approved_* / PO_Pending_* / PO_Approved_Open_*
- AccountingLink via bills, not the PO itself

## USIS / CM_Deploy mapping

| Sage concept | USIS table / API / page | Status |
|---|---|---|
| PO header | `commitments` (`commitment_kind=purchase_order`) | implemented |
| Status + status_effective_date + approved_at | `commitments.status`, `status_effective_date`, `approved_at` | implemented |
| Workflow lock | `commitments.workflow_rule_active` | partial |
| Lines | `commitment_line_items` | implemented |
| PO types | `procurement_po_types` / `commitments.po_type` | partial |
| PO to many bills | `commitment_bill_allocations` + `vendor_invoices` | partial |
| Shipments / receipts | `purchase_order_shipments`, `purchase_order_receipts` | implemented (USIS extension) |
| Retainage | n/a on Sage PO; `retention_percentage` exists on commitments for subs | n/a |
| Project procurement UI | `project-detail-procurement.js` | partial |

## Sources

- Official Sage help URLs used
  - https://help.sagecm.intacct.com/Content/Modules/Procurement/POs/POsOverview.htm
  - https://help.sagecm.intacct.com/Content/Modules/Procurement/POs/POsAddManual.htm
  - https://help.sagecm.intacct.com/Content/Modules/Procurement/SetupWizards/CPRToProcurementWizard.htm
- Local files reviewed
  - `backend/app/models/commitment.py`
  - `backend/app/models/purchase_order.py`
  - `backend/app/models/procurement.py`
  - `Plan/22. Sage_CM_subcontracts_SCO_and_P2P_alignment.txt`
