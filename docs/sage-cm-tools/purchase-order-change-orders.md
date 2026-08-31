# Purchase Order Change Orders

Status: complete
Sage CM module: Procurement
Official help: https://help.sagecm.intacct.com/Content/Modules/Procurement/POCOs/POCOsAddManually.htm

## Purpose

A PO CO changes **one already-approved PO**: you may change **quantity** on an existing PO line or **add a new item**. You cannot change other PO fields through the PO CO. It is the control document for price, spec, delivery, or client-driven PO revisions. External Vendor TeamLink users can view **approved** PO COs under TeamLink Project Home → Procurement.

## Where it lives

- Project menu → **Procurement** → PO COs (Actions → Add PO CO)
- Also: create from an approved PO
- Overview: https://help.sagecm.intacct.com/Content/Modules/Procurement/POCOs/POCOsOverview.htm
- Numbering: Settings → Company Settings → Numbering
- Optional PO CO types

## Who uses it

- Buyers / PMs issue PO COs
- Vendors view approved PO COs in TeamLink
- Workflow approvers when PO CO rules exist
- Admins lock/unlock and define PO CO types

## Prerequisites

- Target **PO is already Approved**
- Prime still selected (and must have been approved to create the original PO)
- Optional: PO CO types; numbering format
- Specify PO CO numbering before first use

## What the user fills out

### Create a PO CO manually

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Project | No to change | Project | Optionally update |
| Prime Contract | Yes | Prime | |
| Supplier Company | Yes | Vendor | |
| PO | Yes | Approved PO | One PO CO → one PO |
| PO CO # | No | Text | Auto next from numbering |
| Order Number | No | Integer | Auto next |
| Issue Date | No | Date | Defaults to today |
| Subject | No | Text | Defaults to the PO’s subject |
| PO CO Type | No | Lookup | Optional |
| Status | Yes | Enum | Default **Pending**. Disabled if workflow applies. Same family as other procurement docs: Draft → Pending Submission → Pending → Not Approved → Approved (exact default documented as Pending) |
| Status Date | Typical | Date | not labeled on the short add page; procurement siblings use it with Approved for analytics. Mark **not confirmed on POCO add page** if you model a dedicated column — confirm on Edit header help |
| Link Related PO Files | No | Checkbox | |
| PO Lines — select items with a change | No | Multi-select + Quantity | Only **Quantity** on existing items; or add new items after create |

Edit after create: header; add/import PO CO line items; edit existing PO CO items; print/share; lock/unlock.

New items after create follow the same item shape as PO lines (Item #, Description, Quantity, Units, Unit Price, JCC, tax, resource) — add/import is documented; full column list on the POCO add page is only Quantity on copied PO lines.

## What Sage CM saves

- Header record: PO CO (number, order number, subject, type, status, issue date, supplier, prime, parent PO)
- Line / child records: quantity deltas on existing PO items; new items
- System-generated values: PO CO # and order number
- Files / attachments: optional link of related PO files; print/share
- Audit / workflow fields: workflow lock; lock/unlock

## Statuses and lifecycle

Create defaults to **Pending**. Workflow-controlled status uses the same Draft / Pending Submission / Pending / Not Approved / Approved family as other contract-admin and procurement transactions (workflow settings list **Purchase order change orders (PO COs)**).

Help’s PO CO overview does **not** repeat the “Approved + status date = committed cost” sentence used for POs and SCOs. Treat committed-cost timing for PO CO amounts as **not confirmed in help** beyond: the parent PO must already be approved, and TeamLink shows **approved** PO COs.

## Dates that drive alerts

- Issue Date
- Status Date (if present on edit header — not confirmed on add page)

## Relationships

- Upstream: Exactly one approved PO
- Downstream: Revised PO quantities/items for later bills; TeamLink vendor view when approved
- Distinct from **SCO** (subcontract) and **CO** (prime)

## Reports and exports

- Print or share a PO CO
- Lock or unlock

## USIS / CM_Deploy mapping

| Sage concept | USIS table / API / page | Status |
|---|---|---|
| PO CO header / lines | none | none |
| Quantity change on PO line | none (would need a child of `commitments`) | none |
| Parent PO | `commitments` (purchase_order) | implemented (parent only) |

## Sources

- Official Sage help URLs used
  - https://help.sagecm.intacct.com/Content/Modules/Procurement/POCOs/POCOsOverview.htm
  - https://help.sagecm.intacct.com/Content/Modules/Procurement/POCOs/POCOsAddManually.htm
  - https://help.sagecm.intacct.com/Content/Administration/Settings/Workflow/Workflow_ContractsProcurement_Overview.htm
- Local files reviewed
  - `backend/app/models/commitment.py`
