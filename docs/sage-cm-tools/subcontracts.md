# Subcontracts

Status: complete
Sage CM module: Procurement
Official help: https://help.sagecm.intacct.com/Content/Modules/Procurement/Subcontract/SubcontractOverview.htm

## Purpose

A subcontract procures a firm’s work (often labor + material + equipment) **with retainage** and **scope changes via SCOs**. Creating one is like a prime: scope, inclusions/exclusions, and a schedule of values. Four **subcontract types** drive how **sub invoices** work: Fixed Lump Sum, Cost Plus with GMP, Cost Plus without GMP, Unit Price. **Committed cost = Approved + status date.** POs do not have retainage or SCOs; use this tool when they do.

## Where it lives

- Project menu → **Procurement** → **Subcontracts**
- Actions: Add Manually; from WO, CPR, CO, estimate RFP, standalone RFP, project directory; Copy
- Record: header, default line values, original items (SOV / GMP / unit price), tax, drawings/specs, lock
- TeamLink: sub invoices may be created there (notifications to PM); subcontract create is internal
- Insurance expired: red warning

## Who uses it

- PMs / contract admins issue subcontracts
- Financial staff set default retainage (else prime defaults apply)
- AP / PMs process sub invoices
- Admins enforce “Do not allow Subcontracts or SCOs to be modified after Sub Invoices have been created”

## Prerequisites

- Vendor in project directory
- Prime **Approved with a status date**
- Job cost codes for original items
- Optional: tax codes; scope templates
- Feature Settings → Procurement for post-invoice lock

## What the user fills out

### Header — Add subcontracts manually

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Project # | Yes | Project | |
| Prime Contract # | Yes | Approved prime | |
| CO # | No | CO lookup | |
| WO # | No | WO lookup | |
| Issue Date | Yes | Date | |
| Subcontract # | Yes | Text | |
| Subcontract Status | Yes | Enum | Draft, Pending Submission, Pending, Not Approved, Approved. Disabled if workflow applies |
| Status Date | No | Date | **With Approved = committed cost** |
| Subcontract Type | Yes | Enum | Fixed Lump Sum; Cost Plus without GMP; Cost Plus with GMP; Unit Price. **Cannot change** once original items exist |
| Subject | Yes | Text | |
| Subcontractor Company | Yes | Project directory | |
| Subcontractor Address Type | Yes | Address type | |
| Subcontractor Contact | No | Contact | |
| Prime Contractor Company | Yes (disabled) | Company | Contractor on the prime |
| Prime Contractor Address Type | Yes | Address type | |
| Prime Contractor Contact | No | Contact | |
| Scope of Work | Yes | Rich text | |
| Inclusions / Exclusions / Clarifications | No | Rich text | Or Import Scope from templates |
| Estimated Start / Substantial Completion / Finish | No | Date | |
| Actual Notice to Proceed / Start / Substantial Completion / Finish | No | Date | |
| Default Retention % — Work Completed | No | Percent | Blank → prime default. Copied to sub invoices |
| Default Retention % — Stored Material | No | Percent | Same |
| Incentives Per Day | No | Money | |
| Liquidated Damages Per Day | No | Money | |

### Default line item values

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Job Cost Code | No | JCC | Fallback (help heading says “SCO items” but this is the original-item default) |
| Tax Code | No | AP tax | Fallback |

### Original items (SOV / unit price / GMP)

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Item # | No | Text | Optional update |
| Description | Yes | Text | |
| Quantity | Yes | Number | Unit Price: estimated project quantity |
| Units of measure | Yes | Text | |
| Unit Price | Yes | Money | |
| Cost Code | Yes or default | JCC | |
| Tax Code | No | AP tax | |

Imports: labor, equipment, work, estimate, estimate summary, anticipated costs, job cost codes.

Type meaning (from add help):

- **FLS:** lump amounts by JCC; firm price
- **Cost Plus without GMP:** codes assigned, no advance dollars; actual + fee
- **Cost Plus with GMP:** max per code / overall cap
- **Unit Price:** qty × unit price; invoiced qty may exceed estimate

## What Sage CM saves

- Header record: subcontract (number, type, status, status date, parties, scope, retainage defaults, schedule dates, incentives/LDs)
- Line / child records: original items; tax total; linked drawings/specs; later SCOs and sub invoices
- System-generated values: subcontract #; committed total when Approved + status date
- Files / attachments: import drawings/specs; download/share/email
- Audit / workflow fields: workflow lock; lock/unlock; type/status/status date frozen if a sub invoice exists; original items frozen if the Feature Setting is on

## Statuses and lifecycle

**Draft → Pending Submission → Pending → Not Approved → Approved**

| Status | Effect |
|---|---|
| Not Approved or earlier | Not in job-cost committed dashboards |
| **Approved + status date** | Committed Cost in Project Analytics |

If a sub invoice exists: type, status, and status date **cannot change**.

## Dates that drive alerts

- Issue Date / Status Date (analytics committed = Status Date)
- Estimated and actual start / substantial completion / finish
- Notice to Proceed

## Relationships

- Upstream: Approved prime; directory vendor; JCCs; optional RFP/CPR/CO/WO
- Downstream: SCOs; sub invoices (retainage from this header); Cost Plus prime invoice if sub invoice is Billable
- One subcontract cannot cover two primes

## Reports and exports

- Download, share, or email subcontract
- View subcontract status
- Analytics Subcontract_* and RevisedSubcontract_*
- About the subcontract schedule of values (related help)

## USIS / CM_Deploy mapping

| Sage concept | USIS table / API / page | Status |
|---|---|---|
| Subcontract header | `commitments` (`commitment_kind=subcontract`) | partial |
| Status / dates / vendor / retainage % | `commitments` | partial |
| Type, scope, SOV-style original items | lines exist; no subcontract_type enum | stub |
| SCO child | none (plan: future `subcontract_change_orders`) | none |
| Textura contract id | `commitments.textura_contract_id` | stub |
| Project procurement UI | `project-detail-procurement.js` | partial |

## Sources

- Official Sage help URLs used
  - https://help.sagecm.intacct.com/Content/Modules/Procurement/Subcontract/SubcontractOverview.htm
  - https://help.sagecm.intacct.com/Content/Modules/Procurement/Subcontract/SubcontractAddManual.htm
- Local files reviewed
  - `backend/app/models/commitment.py`
  - `Plan/22. Sage_CM_subcontracts_SCO_and_P2P_alignment.txt`
