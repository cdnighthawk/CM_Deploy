# Estimate RFP packages

Status: complete
Sage CM module: Estimating (Bid Management) / Procurement
Official help: https://help.sagecm.intacct.com/Content/Modules/Procurement/RFPPackages/RFPPackages_AddManually.htm

## Purpose

An RFP package requests **priced** quotes for a scope (concrete, doors, electrical). Estimate-created packages **must link estimate items** to the package and are managed from the estimate **Bid Management** view. Procurement-created packages are almost the same but are not required to link estimate lines. Awarded packages can become a PO or subcontract.

This is not an ITB (interest only).

## Where it lives

- Estimate → Bid Management view (estimate-scoped packages)
- Project Home → Procurement → **RFPs** → Actions → Add Manually (procurement-scoped)
- TeamLink: bidders respond; **Vendor Locking** and Date Responded drive open items
- Mobile: not listed as RFP add

## Who uses it

- Estimators create packages per trade and link items
- PMs/accounting set From Contact
- Vendors submit prices in TeamLink
- Procurement issues PO/sub to the winner

## Prerequisites

- Project (procurement path) or lead/project estimate (estimate path)
- Prime Contract selected on the procurement add wizard
- Companies with contacts and email; Bid Contact / Is Bidder flags help
- Estimate items exist if creating from an estimate

## What the user fills out

Official add wizard is documented on the **procurement** path. Definitions say the estimate path is nearly identical **plus item linking**.

### Step 1 — General

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Project # | No | Lookup | Prefilled; editable |
| Prime Contract | Yes (procurement wizard) | Lookup | |
| RFP Package # | Yes | Text | |
| Title | Yes | Text | |
| Bid Due Date and Time | No | Date/time | Home alert: Estimate RFP packages / Procurement RFP packages |
| From Contact | No | Lookup | Usually PM or accounting. **From Company** is the account name and **cannot be changed** |
| Issue Date | No | Date | Defaults to today |
| Work Scope | No | Text | |
| Inclusions / Exclusions / Clarifications | No | Text | Package-level narrative |

### Step 2 — Bidders

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Vendor View | Yes | Choice | Add From ITB - Bidding Only; Master List; Bidder List; Add By Classification |
| Search | No | Text | |
| Company + Contact | Yes | Multi-select | Can add more after create |

### Step 3 — Bid items

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Item # | No | Text | Editable |
| Description | Yes in practice | Text | |
| Manufacturer | No | Text | |
| Manufacturer Part # | No | Text | |
| UPC | No | Text | |
| Qty | Yes in practice | Number | |
| Unit | Yes in practice | Text | |

Estimate path: **link existing estimate items** to the package (required per Definitions). Extra link-dialog field names: **not confirmed in help**.

### Step 4 — Files

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Drag / Add local files | No | Files | Up to 48 at a time; **500 MB** total; special characters → `_` |
| Link Existing | No | Choice | Drawings & Specs, Photos, All Other Records (same lead/project only) |

### Response / open-item fields (persisted; used by Team Open Items)

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Vendor Locking | System/user | Boolean | Open item when False |
| Date Responded | System/vendor | Date | Open item when null for that bidder |
| Line prices | Vendor | Currency | Not listed on the add form; implied by “submit pricing” |

## What Sage CM saves

- Header record: package #, title, prime, bid due, from contact/company, issue date, scope text
- Line / child records: bid items; bidder rows; linked estimate items (estimate path); vendor responses/prices
- System-generated values (IDs, numbers, dates, totals): From Company = account name; issue date default today
- Files / attachments: uploaded and linked files
- Audit / workflow fields: Vendor Locking; Date Responded; TeamLink access

## Statuses and lifecycle

No named Draft/Sent/Awarded list on the add page. Open-item logic: unlocked + bidder assigned + Date Responded null. After award: PO or subcontract. Multiple packages per estimate are normal.

## Dates that drive alerts

- **Bid Due Date** — Home alerts (Estimate RFP packages and Procurement RFP packages)

## Relationships

- Upstream: estimate items and/or procurement project + prime; ITB Bidding vendors
- Downstream: PO / subcontract; TeamLink quotes

## Reports and exports

- Bid Management comparison (implied; extra columns not confirmed)
- TeamLink vendor response
- USIS analog: RFP compare page

## USIS / CM_Deploy mapping

| Sage concept | USIS table / API / page | Status |
|---|---|---|
| RFP header | `rfps` / `backend/app/models/rfp.py` | partial |
| Line items | `rfp_line_items` (description, qty, unit, notes) | partial |
| Vendor quotes | `rfp_vendor_quotes` (`vendor_label`, `line_prices` JSON) | partial |
| Public token | `rfps.public_token` | implemented |
| Status / due | `status` default Draft; `due_at` | partial |
| APIs / UI | `/api/v1/rfp`; `usis-rfp-list.html`, `usis-rfp-detail.html`, `usis-rfp-compare.html`; estimate-detail RFP tab | partial |
| Prime, From Contact, Vendor Locking, TeamLink, estimate-item link | none | none |

## Sources

- Official Sage help URLs used
  - https://help.sagecm.intacct.com/Content/Modules/Procurement/RFPPackages/RFPPackages_AddManually.htm
  - https://help.sagecm.intacct.com/Content/GettingStarted/Definitions.htm
  - https://help.sagecm.intacct.com/Content/Modules/Emailing/OpenItemsEmail.htm
  - https://help.sagecm.intacct.com/Content/Modules/AlertsCalendars/AlertsCalendar_All.htm
- Local files reviewed
  - `backend/app/models/rfp.py`
  - `W3CRM-v3.0-13_September_2025/gulp/src/construction/estimate-detail.html`
  - `W3CRM-v3.0-13_September_2025/gulp/src/usis-rfp-list.html`
