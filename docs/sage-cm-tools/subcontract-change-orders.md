# Subcontract Change Orders

Status: complete
Sage CM module: Procurement
Official help: https://help.sagecm.intacct.com/Content/Modules/Procurement/SCO/SCOOverview.htm

## Purpose

A subcontract change order (SCO) revises an existing subcontract when scope or commercial terms change. GC or sub may initiate. Typical path: finish CPR and/or owner CO, then wizard-create SCOs (or enter manually). **Budget / committed impact = Approved + status date.** Sub invoices (FLS) include an SCO only if it is Approved with a status date **on or before** the sub invoice issue date.

## Where it lives

- Project menu → **Procurement** → **Subcontract change orders (SCOs)**
- Actions → Add Manually; from WO, CPR, or CO
- Record: header, default line values, SCO items, tax, lock
- Feature Settings → Procurement: **Do not allow Subcontracts or SCOs to be modified after Sub Invoices have been created**
- TeamLink: not the primary create path

## Who uses it

- PMs / contract admins write SCOs
- Subs may initiate depending on Feature Settings → Procurement “initiated by”
- AP: once imported on an approved sub invoice, SCO status/date cannot change
- Workflow approvers

## Prerequisites

1. Review initiated-by options (Feature Settings → Procurement)
2. Prime **and** subcontract **Approved with a status date**
3. Job cost codes for proposed items
4. Optional: tax codes

## What the user fills out

### Header — Add an SCO manually

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Project # | Yes | Project | |
| Prime Contract | Yes | Approved prime | |
| Subcontract | Yes | Approved subcontract | Company fields copy from this subcontract and **cannot** be edited |
| CO # | No | Owner CO lookup | |
| WO # | No | WO lookup | |
| Issue Date | No | Date | Defaults to today |
| Sort Order # (Order Number) | Yes | Integer | Auto. **Integer sequence for previous SCO amount** on the SCO report: all SCOs Approved + status date with a **lower** order number |
| SCO # | Yes | Text | Auto from selected subcontract |
| SCO Subject | Yes | Text | |
| Initiated By | No | Lookup | Feature Settings |
| SCO Status | Yes | Enum | Draft, Pending Submission, Pending, Not Approved, Approved. Disabled if workflow applies |
| Status Date | No | Date | Defaults to today. **With Approved = budget + committed + sub-invoice eligibility** |
| Subcontractor Contact / Address | No | | Company locked |
| Prime Contractor Contact / Address | No | | Company locked |
| Scope of Work | No | Rich text | |
| References — Drawing / Location / RFI # / Spec. Section / Other | No | Mixed | |
| Schedule impact — To Be Determined Later | No | Checkbox | If checked, leave days at 0 |
| Work Days (+/−) | No | Integer | Days added or removed from sub schedule |

### Default line values

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Job Cost Code | No | JCC | Fallback |
| Tax Code | No | AP tax | Fallback |

### SCO line items

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Item # | Yes | Text | Sort order |
| Description | Yes | Text | |
| Quantity | Yes | Number | Unit Price new billing item: estimated project quantity |
| Units | No | Text | |
| Unit Price | Yes | Money | |
| Cost Code | No | JCC | Fallback to default |
| Tax Code | No | AP tax | Fallback |

Imports: labor, equipment, work, estimate, estimate summary, anticipated costs, job cost codes.

## What Sage CM saves

- Header record: SCO (order #, SCO #, subject, status, status date, initiated by, parent subcontract, scope, references, schedule days)
- Line / child records: SCO items; tax total
- System-generated values: previous approved SCO amount; Corecon CO-like fields for procurement COs as applicable
- Files / attachments: download/share/email; Link Related Files from CPR wizard
- Audit / workflow fields: workflow lock; lock/unlock; expired insurance warning

## Statuses and lifecycle

**Draft → Pending Submission → Pending → Not Approved → Approved**

| Status | Effect |
|---|---|
| Not Approved or earlier | No original-budget change; not in committed dashboards |
| **Approved + status date** | Affects original subcontract budgets (see table). Job-cost dashboards Committed Cost. FLS sub invoice can import if status date ≤ invoice issue date |

### Budget impact by subcontract type

| Subcontract type | Contract amount / original budgets |
|---|---|
| Fixed Lump Sum | Yes — SCO adds/deducts original budgets |
| Cost Plus with GMP | Yes — same |
| Cost Plus without GMP | (blank in help — no contract-amount impact) |
| Unit Price | (blank in help — no contract-amount impact) |

Locks:

- Imported into a sub invoice **and** SCO Approved → status and status date **cannot change**
- Feature setting on + any sub invoice exists → cannot add/modify SCO items even if not yet invoiced
- **Invoiced SCO items cannot be modified under any circumstances**
- Workflow initiated/approved → no edit unless abandoned

## Dates that drive alerts

- Issue Date and Status Date (both must be before sub invoice issue date for FLS import)
- Schedule impact days

## Relationships

- Upstream: Approved prime + approved subcontract; optional CPR/CO/WO
- Downstream: Revised subcontract committed; FLS sub invoices; Project Analytics
- Distinct from PO CO and owner CO

## Reports and exports

- Download, share, or email SCO
- SCO report previous-amount logic (order #)
- Analytics SCO_Approved_* / Pending_*
- Tax total edit; tax code reference logic

## USIS / CM_Deploy mapping

| Sage concept | USIS table / API / page | Status |
|---|---|---|
| SCO header / items | none | none |
| Parent subcontract | `commitments` (subcontract) | partial |
| Plan direction | `Plan/22` — add `subcontract_change_orders` when financials UI ships | none |

## Sources

- Official Sage help URLs used
  - https://help.sagecm.intacct.com/Content/Modules/Procurement/SCO/SCOOverview.htm
  - https://help.sagecm.intacct.com/Content/Modules/Procurement/SCO/SCOAddManual.htm
  - https://help.sagecm.intacct.com/Content/Modules/Procurement/SetupWizards/CPRToProcurementWizard.htm
- Local files reviewed
  - `Plan/22. Sage_CM_subcontracts_SCO_and_P2P_alignment.txt`
  - `backend/app/models/commitment.py`
