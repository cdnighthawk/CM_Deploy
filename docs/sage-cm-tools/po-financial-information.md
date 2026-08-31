# PO Financial Information

Status: complete
Sage CM module: Procurement
Official help: https://help.sagecm.intacct.com/Content/ReleaseNotes/October-2023/oct-23-projects-menu.htm

## Purpose

PO Financial Information is a **read-only financial status** page for purchase orders on the project: approved vs pending PO totals, open vs billed, and related bills. It is the PO counterpart to Subcontract Financial Information. Sage help names the menu item but does **not** publish an Add/Overview field list for this page. Figures below are the documented analytics / PO / bill measures that this kind of page surfaces. Column titles that are not on a dedicated help topic are marked **not confirmed in help**.

## Where it lives

- Project menu → **Procurement** → **PO financial information**
- Inquiry / summary, not a create form
- Complements POs list, Bills list, and Project Analytics (transaction type PO / Bill)
- TeamLink: vendors see approved PO COs; this GC financial page is internal

## Who uses it

- PMs and AP: remaining commitment vs billed
- Controllers: approved vs pending PO exposure
- View-only; approvals happen on the PO and Bill records

## Prerequisites

- Project; typically an approved prime and at least one PO
- Select prime if the project has more than one (pattern used elsewhere; **not confirmed** as a control on this exact page)

## What the user fills out

No create fields. Likely filters (not confirmed in help):

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Project | Yes | Current project | |
| Prime Contract # | Likely | Lookup | Other financial pages are prime-scoped |
| Date range | Likely | Dates | Analytics uses PO **Status Date** and bill **Issue Date** |

Displayed measures (from Project Analytics API v3 Overview by transaction type — these **are** confirmed field names in analytics, not necessarily the on-page labels):

| Measure | Meaning |
|---|---|
| PO_Approved_Subtotal / Total | POs Approved (committed when status date is set) |
| PO_Pending_Subtotal / Total | Not yet approved |
| PO_ApprovedAndPending_* | Combined |
| PO_Approved_Open_Subtotal / Total | Approved POs still open (PO to Bill has not closed items) |
| Bill_Approved_* / Bill_Pending_* | Bills including PO-matched |
| Bill_NoPO_* | Manual / no-PO bills |

Open vs closed PO items exist **only** through PO to Bill.

## What Sage CM saves

- Header record: none
- Line / child records: none
- System-generated values: aggregations over existing POs and bills
- Files / attachments: none
- Audit / workflow fields: none

## Statuses and lifecycle

No status. It reflects PO header statuses and bill Approved flags.

**Committed PO cost** still means PO **Approved + status date**. Pending POs may show in Pending columns only.

## Dates that drive alerts

None. Underlying Reminder Date / Payment Due live on PO and Bill.

## Relationships

- Upstream: POs, PO COs, bills
- Downstream: none (inquiry)
- Sibling: Subcontract financial information; Project Analytics

## Reports and exports

- Dedicated export of this page is not confirmed in help
- Use Analytics dashboards (export Excel/PDF/JPEG) and PO/bill detail reports

## USIS / CM_Deploy mapping

| Sage concept | USIS table / API / page | Status |
|---|---|---|
| PO financial inquiry page | none | none |
| PO + bill allocation totals | `commitments.total_amount` + `commitment_bill_allocations` | stub |
| Vendor invoice amounts | `vendor_invoices.amount` | partial |

## Sources

- Official Sage help URLs used
  - https://help.sagecm.intacct.com/Content/ReleaseNotes/October-2023/oct-23-projects-menu.htm
  - https://help.sagecm.intacct.com/Content/Modules/Procurement/POs/POsOverview.htm
  - https://help.sagecm.intacct.com/Content/Modules/Procurement/Bills/BillsOverview.htm
  - https://help.sagecm.intacct.com/Content/Modules/Reporting/Analytics_ProjectFinancials/APIs/v3/ProjectAnalytics_APIs_V3_Overview_Transaction.htm
  - https://help.sagecm.intacct.com/Content/Modules/Reporting/Analytics_ProjectFinancials/ResourceCenter_Analytics_ProjectFinancials.htm
- Local files reviewed
  - `backend/app/models/commitment.py`
  - `backend/app/models/vendor_invoice.py`
