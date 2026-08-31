# Change Proposal Requests

Status: complete
Sage CM module: Client Contract Admin
Official help: https://help.sagecm.intacct.com/Content/Modules/ContractAdministration/CPR/CPROverview.htm

## Purpose

A change proposal request (CPR) tracks a potential owner change from inception through customer acceptance or rejection. It holds scope, schedule impact, **impacted vendors** (who price in TeamLink), and **proposed items** (the priced owner-facing lines). CPRs are used most on Fixed Lump Sum and Unit Price primes; Cost Plus changes usually go straight to a change order.

**CPRs never revise budgets or Project Analytics**, even when Approved. Budgets move only after the CPR is copied to a CO that is **Approved with a status date**.

## Where it lives

- Project menu → **Client Contract Admin** → **Change proposal requests (CPRs)**
- List + Actions → Add Manually; convert from estimate; convert from work orders
- Record: header → impacted vendors → files; then edit to add proposed items, tax, hour budgets
- TeamLink: vendors enter pricing and schedule impact only when CPR status is **Pending** or **Pending Submission**; otherwise vendor cost lines are read-only
- Email from Sage includes a secure TeamLink link

## Who uses it

- PMs / contract admins create CPRs, import vendor costs into proposed items, and run CPR → CO / CPR → Procurement wizards
- Impacted subcontractors and suppliers price in TeamLink
- Owner/customer reviews the proposal (status/date updated after review)
- Admins configure Initiated By options and default CPR/CO markups

## Prerequisites

- Prime contract **Approved with a status date**
- Owner/customer in the project directory
- Job cost codes (required on Proposed Items)
- Optional: tax codes; default CPR/CO markups on the prime / Feature Settings
- Review Settings → Feature Settings → Contract Admin → CPR/CO Initiated By options

## What the user fills out

### Header — Add a CPR manually, Step 1

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Project # | Yes | Project | |
| Prime Contract # | Yes | Approved prime | |
| Issue Date | No | Date | Defaults to today |
| CPR Sort Order # | No | Integer | Auto next; used like CO/SCO order for sequencing |
| CPR # | No | Text | Auto next from numbering |
| Initiated By | No | Lookup | Admin-defined in Feature Settings → Contract Admin |
| Subject | Yes | Text | “Brief Subject” |
| CPR Status | Yes | Enum | Draft, Pending Submission, Pending, Approved, Not Approved. Disabled if workflow applies |
| CPR Status Date | No | Date | Defaults to today; update after customer review |
| Client Company | Yes (disabled) | Company | From prime |
| Client Address Type / Contact | Address type yes; contact no | | |
| Prime Contractor Company | Yes (disabled) | Company | From prime |
| Prime Contractor Address Type / Contact | Address type yes; contact no | | |
| Proposed Scope Of Work | No | Rich text | |
| References — Drawing | No | Drawing lookup | |
| References — Location | No | Text | |
| References — RFI # | No | RFI lookup | |
| References — Spec. Section | No | Text | |
| References — Other | No | Text | |
| Impacted Company Pricing Due Date | No | Date | Follow Up and Completion Dates section |
| Proposal Completion Due Date | No | Date | |
| Schedule impact — To Be Determined Later | No | Checkbox | Default on; clear to enter days |
| Schedule impact days | No | Integer | Days added/removed when TBD is cleared |

### Step 2 — Impacted vendors

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Impacted vendor companies | No on create (Skip allowed) | Multi-select from project directory / vendors | Must exist here **before** their cost lines can be imported into Proposed Items for the CPR → Procurement wizard |

### Proposed items (added after create — Add, edit, or import CPR proposed items)

Help’s add wizard does not collect line items; they are edited on the open CPR. Fields below match the shared CPR/CO/PO item pattern documented on add-import pages. Where a label is only inferred from sibling tools, it is marked.

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Item # | No | Text | Sort order |
| Description | Yes | Text | Shared import pattern |
| Quantity | Yes | Number | |
| Units | No | Text | |
| Unit Price / sell | Typical | Money | Owner-facing proposed amount |
| Job Cost Code | Yes | JCC | Required on Proposed Items list |
| Tax Code | No | AR tax | Default CPR/CO markups may apply |
| Resource | Typical | M/L/E/S/O | not confirmed as a separate CPR proposed-item column in CPR add help; used on related procurement imports |
| Labor / equipment hour budgets | No | Hours | Separate edit: “Edit the labor and equipment hour budgets of a CPR” |

Vendor cost lines live under **Impacted Company Details**, then must be **imported into Proposed Items** before CPR → PO / Subcontract / SCO.

### Files — Step 3

Same 48-file / 500 MB upload + link Drawings & Specs / Photos / All Other Records as other contract-admin records.

## What Sage CM saves

- Header record: CPR (number, order, subject, status, status date, initiated by, parties, scope, references, due dates, schedule days)
- Line / child records: impacted companies; vendor-entered TeamLink prices and schedule impact; proposed items; tax total; hour-budget adjustments
- System-generated values (IDs, numbers, dates, totals): CPR # and sort order; proposed subtotal/tax/total; analytics **does not** include CPR amounts until they sit on an Approved CO
- Files / attachments: uploaded and linked files; optional Link Related Files when converting to procurement
- Audit / workflow fields: workflow lock; lock/unlock CPR; TeamLink read-only unless Pending or Pending Submission

## Statuses and lifecycle

Official sequence: **Draft → Pending Submission → Pending → Approved or Not Approved**.

| Status | Effect |
|---|---|
| Draft | Internal; vendors cannot price in TeamLink |
| Pending Submission / Pending | Vendors can submit TeamLink pricing |
| Approved | Customer accepted. Still **does not** change budgets. Use CPR → CO wizard (approved CPRs only) and/or CPR → Procurement |
| Not Approved | Rejected; no budget impact |

After customer review, update **both status and status date**.

## Dates that drive alerts

- Issue Date
- Status Date
- Impacted Company Pricing Due Date
- Proposal Completion Due Date

## Relationships

- Upstream: Approved prime; JCCs; optional estimate or work orders
- Downstream: Change order (CPR to CO wizard — one or more approved CPRs → one CO; item format As in CPR or Summarize By JCC); PO / subcontract / SCO (CPR to Procurement wizard — vendor must be on an approved CPR with items imported into Proposed Items; SCO only if that vendor already has a subcontract)
- Related: default markups; tax logic shared with prime/CO items

## Reports and exports

- Download, share, or email a CPR
- CPR to CO and CPR to Procurement wizards
- Analytics: `RevenueBudget_ApprovedCPRs_*` / `RevenueBudget_PendingCPRs_*` are informational; official revised budget is still the CO

## USIS / CM_Deploy mapping

| Sage concept | USIS table / API / page | Status |
|---|---|---|
| CPR header / proposed items / impacted vendors | none | none |
| TeamLink vendor pricing | none | none |
| Convert CPR → CO / PO / subcontract | none | none |
| Estimate RFP (different tool) | `rfps` | stub — not this Sage CPR |

## Sources

- Official Sage help URLs used
  - https://help.sagecm.intacct.com/Content/Modules/ContractAdministration/CPR/CPROverview.htm
  - https://help.sagecm.intacct.com/Content/Modules/ContractAdministration/CPR/CPRAddManual.htm
  - https://help.sagecm.intacct.com/Content/Modules/ContractAdministration/SetupWizards/CPRToCOWizard.htm
  - https://help.sagecm.intacct.com/Content/Modules/Procurement/SetupWizards/CPRToProcurementWizard.htm
- Local files reviewed
  - `backend/app/models/rfp.py` (USIS RFP is not Sage CPR)
