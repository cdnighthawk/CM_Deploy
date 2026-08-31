# Procurement RFPs

Status: complete
Sage CM module: Procurement
Official help: https://help.sagecm.intacct.com/Content/Modules/Procurement/RFPPackages/RFPPackagesOverview.htm

## Purpose

A procurement request-for-pricing (RFP) package collects vendor prices for one scope (concrete, doors, electrical, etc.). After award, the winning bidder is issued a **PO** or **subcontract**. Packages can be created in Procurement or inside an estimate (estimate items must be linked to the package). Awarded estimate RFP packages can convert automatically to POs/subcontracts — exclude those estimate lines when importing into other commitments to avoid double-buyout.

This is **not** a Change Proposal Request (CPR) and not USIS’s preconstruction `rfps` vertical slice.

## Where it lives

- Project menu → **Procurement** → **Requests for proposals (RFPs)**
- Also: Estimates → RFP packages (nearly identical; estimate items must be tagged)
- Actions → Add Manually: header → bidders → bid items → files
- Send bid invitations; analyze vendor bids
- TeamLink / email invitations for bidders (send-invitations help)

## Who uses it

- Estimators and PMs create packages and add bidders
- Vendors submit prices (invitation / portal)
- Procurement awards and converts to PO or subcontract

## Prerequisites

- Project; **Prime Contract** is selected on add (help requires this field)
- Companies in Contact Management (master list, bidder list, classification) and/or project ITB
- Optional: drawings/specs/photos to link; cost database / estimate for item import after create

## What the user fills out

### Step 1 — General RFP package information

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Project # | Yes | Project | |
| Prime Contract | Yes | Prime | |
| From Contact | No | Contact | Usually PM or accounting user |
| From Company | Yes (disabled) | Account name | Cannot change |
| Issue Date | No | Date | Defaults to today |
| RFP Package # | Yes | Text | |
| Title | Yes | Text | |
| Bid Due Date and Time | No | Date/time | |
| Work Scope | No | Rich text | |
| Inclusions / Exclusions / Clarifications | No | Rich text | |

### Step 2 — Bidders list

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Vendor view | Yes to pick a list | Choice | Add From ITB - Bidding Only; Add From Master List; Add From Bidder List; Add By Classification |
| Vendors / contacts | No (can add later) | Multi-select | Search available |

### Step 3 — Bid items

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Item # | No | Text | |
| Description | Yes | Text | Help says “Enter a Description” |
| Manufacturer | Listed on add page | Text | Help lists as an enter field; treat as optional unless UI marks required |
| Manufacturer Part # | Listed | Text | |
| UPC | Listed | Text | |
| Qty | Yes | Number | |
| Unit | Yes | Text | |

After create, **Add or import vendor items** can import labor/equipment/work/estimate/anticipated-cost items (same family as PO import) and assign cost codes.

### Step 4 — Files

48 files / 500 MB; link Drawings & Specs, Photos, All Other Records.

## What Sage CM saves

- Header record: RFP package (number, title, prime, issue date, bid due, scope, from contact)
- Line / child records: bidders; bid items; per-vendor prices (analyze bids); optional links to estimate lines
- System-generated values: package number; award conversion to PO/subcontract
- Files / attachments: uploaded/linked package files
- Audit / workflow fields: not confirmed as using the contract/procurement approval workflow list (that list names COs, CPRs, primes, invoices, bills, POs, PO COs, sub invoices, SCOs — **RFP packages are not on that list**)

## Statuses and lifecycle

RFP package status values are **not confirmed in help** on the overview/add pages (USIS uses a free-text `Draft` default — do not treat that as Sage). Documented lifecycle:

1. Create package + bidders + items
2. Send bid invitations
3. Analyze vendor bids
4. Award → add PO or subcontract from estimate RFP or standalone RFP

## Dates that drive alerts

- Bid Due Date and Time
- Issue Date

## Relationships

- Upstream: Prime; optional estimate / ITB / cost database
- Downstream: PO (Add from estimate RFP or standalone RFP); subcontract (same); anticipated-cost and bill imports should exclude estimate items tagged on awarded RFPs

## Reports and exports

- Analyze vendor bids
- Excel import of package items
- Convert to PO/subcontract wizards

## USIS / CM_Deploy mapping

USIS `rfps` is a minimal public-token quote slice (title, status, due_at, line items, vendor_label + JSON prices). It is not Sage procurement RFP packages.

| Sage concept | USIS table / API / page | Status |
|---|---|---|
| RFP package header | `rfps` (`title`, `status`, `due_at`, `project_id`) | stub |
| Bid items | `rfp_line_items` | stub |
| Vendor quotes | `rfp_vendor_quotes.line_prices` JSON | stub |
| Prime, scope, bidder source views | none | none |
| Award → commitment | `commitments.rfp_id` | stub |
| Public token portal | `rfps.public_token` | stub (USIS-only) |

## Sources

- Official Sage help URLs used
  - https://help.sagecm.intacct.com/Content/Modules/Procurement/RFPPackages/RFPPackagesOverview.htm
  - https://help.sagecm.intacct.com/Content/Modules/Procurement/RFPPackages/RFPPackages_AddManually.htm
  - https://help.sagecm.intacct.com/Content/Modules/Procurement/RFPPackages/RFPPackages_AddImportItems.htm
- Local files reviewed
  - `backend/app/models/rfp.py`
  - `backend/app/models/commitment.py` (`rfp_id`)
