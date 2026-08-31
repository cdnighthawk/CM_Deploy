# Subcontract Financial Information

Status: complete
Sage CM module: Procurement
Official help: https://help.sagecm.intacct.com/Content/ReleaseNotes/October-2023/oct-23-projects-menu.htm

## Purpose

Subcontract Financial Information is the **read-only status** page for subcontracts: original vs revised (approved SCOs), billed via sub invoices, and retainage held/released. It is the subcontract counterpart to PO Financial Information. Sage names the menu item; it does **not** publish an Add/Overview field catalog. Measures below come from documented subcontract, SCO, sub-invoice, and analytics APIs. On-page column titles are **not confirmed in help**.

## Where it lives

- Project menu → **Procurement** → **Subcontract financial information**
- Inquiry / summary, not a create form
- Complements Subcontracts, SCOs, Subinvoices, and Project Analytics
- Related help also mentions viewing **subcontract status** from the subcontract tool
- Internal GC page; TeamLink is for sub invoice entry, not this dashboard

## Who uses it

- PMs: remaining subcontract value and retainage
- AP: approved vs pending sub invoices
- Controllers: revised subcontract (original + approved SCOs) vs billed

## Prerequisites

- Project; typically an approved prime and at least one subcontract
- Meaningful retainage/billed columns require approved sub invoices

## What the user fills out

No create fields. Likely filters (not confirmed in help):

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Project | Yes | Current project | |
| Prime Contract # | Likely | Lookup | |
| Date range | Likely | Dates | Analytics: subcontract/SCO **Status Date**; sub invoice **Issue Date** |

Confirmed analytics measures (API v3 Overview by transaction type):

| Measure | Meaning |
|---|---|
| Subcontract_Approved_Subtotal / Total | Subcontracts Approved + status date = committed |
| Subcontract_Pending_* | Not committed |
| SCO_Approved_* / SCO_Pending_* | SCOs; approved + status date hit original budgets (FLS / CP+GMP) |
| RevisedSubcontract_Approved_* | Original + approved SCOs |
| RevisedSubcontract_Approved_Open_* | Revised less billed / still open |
| SubInvoice_Approved_GrossTotal / Subtotal / Total / NetRetainage | Approved sub invoices |
| SubInvoice_Pending_* / NetRetainage | Pending (not in cost-to-date dashboards) |

Retainage on the source documents is **by job cost code**, not by SOV line.

## What Sage CM saves

- Header record: none
- Line / child records: none
- System-generated values: aggregations over subcontracts, SCOs, sub invoices
- Files / attachments: none
- Audit / workflow fields: none

## Statuses and lifecycle

No status. Interpretation of source statuses:

| Source | When it hits this page’s “approved / committed” side |
|---|---|
| Subcontract | **Approved + status date** |
| SCO | **Approved + status date** (type-dependent budget impact) |
| Sub invoice | **Approved** checkbox |

## Dates that drive alerts

None on this page.

## Relationships

- Upstream: Subcontracts, SCOs, sub invoices
- Downstream: none (inquiry)
- Sibling: PO financial information; Project Analytics

## Reports and exports

- Page-level export not confirmed in help
- Subcontract / SCO / sub invoice detail reports and lien waivers
- Analytics export Excel/PDF/JPEG

## USIS / CM_Deploy mapping

| Sage concept | USIS table / API / page | Status |
|---|---|---|
| Subcontract financial inquiry | none | none |
| Subcontract header totals | `commitments.total_amount` (kind=subcontract) | stub |
| SCO / sub invoice / retainage-by-JCC | none | none |

## Sources

- Official Sage help URLs used
  - https://help.sagecm.intacct.com/Content/ReleaseNotes/October-2023/oct-23-projects-menu.htm
  - https://help.sagecm.intacct.com/Content/Modules/Procurement/Subcontract/SubcontractOverview.htm
  - https://help.sagecm.intacct.com/Content/Modules/Procurement/SCO/SCOOverview.htm
  - https://help.sagecm.intacct.com/Content/Modules/Procurement/SubInvoice/SubInvoiceOverview.htm
  - https://help.sagecm.intacct.com/Content/Modules/Reporting/Analytics_ProjectFinancials/APIs/v3/ProjectAnalytics_APIs_V3_Overview_Transaction.htm
- Local files reviewed
  - `backend/app/models/commitment.py`
  - `Plan/22. Sage_CM_subcontracts_SCO_and_P2P_alignment.txt`
