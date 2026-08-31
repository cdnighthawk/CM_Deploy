# Prime Contract Budget and Invoice History

Status: complete
Sage CM module: Client Contract Admin
Official help: https://help.sagecm.intacct.com/Content/ReleaseNotes/October-2023/oct-23-projects-menu.htm

## Purpose

This is an **inquiry / history** page, not a create form. It shows, for a selected prime, how original budgets, approved change orders, and prime invoices stack over time — the “budget and invoice history overview” listed on the Project menu. Use it to see original vs revised contract amount, billed to date, retainage, and remaining balance without opening each invoice.

Sage does not publish a dedicated field-by-field help topic for this overview (the October 2023 menu rename is the page that names it). Column-level labels below that are not on an Add/Overview help page are marked **not confirmed in help** and taken from related prime, budget, invoice, and analytics topics.

## Where it lives

- Project menu → **Client Contract Admin** → **Prime contract budget and invoice history overview**
- Overview / history grid, not a record form
- Related: Prime Contracts → Original Prime Contract Budgets; Prime Invoices list; Project Analytics
- Not a TeamLink create tool

## Who uses it

- PMs and project accountants reconcile draws against revised contract
- Controllers review billed vs remaining and retainage held
- View-only for most roles; no approval action lives here

## Prerequisites

- Project and at least one prime contract
- Meaningful history requires original budgets and (typically) approved invoices
- Select the prime when the project has more than one

## What the user fills out

Users do not create a history record. Typical filters (project menu + analytics patterns):

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Project | Yes | Current project | From project home |
| Prime Contract # | Yes if multiple primes | Lookup | History is per prime |
| Date range | No | Dates | Analytics cost/revenue filters use invoice **Issue Date** and CO/prime **Status Date**. Whether this page exposes the same filters is not confirmed in help |

Displayed history (composed from documented prime / invoice / analytics fields):

| Displayed value | Source tool | Notes |
|---|---|---|
| Original contract amount / GMP / estimated UP value | Prime original budgets | Not used for Cost Plus without GMP |
| Approved CO impact | COs Approved + status date | Order # sequences “previous CO” |
| Revised contract | Original ± approved COs | |
| Prime invoice #, order #, issue date, approved flag | Prime invoices | Order #, not date, sequences prior billed |
| Billed to date / current / retainage by JCC | Prime invoices | Retainage is by JCC |
| Remaining / balance to finish | Calculated | Same idea as pay-app “balance to finish including retainage” |

Exact grid column headers on this page are **not confirmed in help**.

## What Sage CM saves

- Header record: none — read model over prime + COs + invoices
- Line / child records: none created
- System-generated values: running previous-invoice amounts (driven by invoice **Sort Order #**); revised budgets (driven by CO status date)
- Files / attachments: none
- Audit / workflow fields: none

## Statuses and lifecycle

No status. It reflects:

- Prime: Approved / Approved and Closed still appear in financial analytics
- CO: only Approved + status date revise the budget side
- Invoice: only Approved invoices count in analytics; pending invoices may still list on the invoice tool

## Dates that drive alerts

None. History is driven by prime/CO **Status Date** and invoice **Issue Date**.

## Relationships

- Upstream: Prime contracts, original budgets, COs, prime invoices
- Downstream: None (inquiry). Project Analytics is the dashboard counterpart

## Reports and exports

- Export of this specific overview is not confirmed in help
- Use prime invoice detail reports, lien waivers, and Project Financial Analytics / BI exports instead

## USIS / CM_Deploy mapping

| Sage concept | USIS table / API / page | Status |
|---|---|---|
| Budget + invoice history overview | none | none |
| Pay-app running totals | `pay_applications` header money fields | partial |
| Corecon prime + invoice lines | `corecon_transactions` (Prime Invoice / Prime Invoice Retainage) | implemented (import only) |

## Sources

- Official Sage help URLs used
  - https://help.sagecm.intacct.com/Content/ReleaseNotes/October-2023/oct-23-projects-menu.htm
  - https://help.sagecm.intacct.com/Content/Modules/ContractAdministration/PrimeContract/PrimeContractBudgetsOverview.htm
  - https://help.sagecm.intacct.com/Content/Modules/ContractAdministration/PrimeInvoice/PrimeInvoiceOverview.htm
  - https://help.sagecm.intacct.com/Content/Modules/Reporting/Analytics_ProjectFinancials/ResourceCenter_Analytics_ProjectFinancials.htm
- Local files reviewed
  - `backend/app/models/pay_application.py`
  - `backend/app/models/corecon_transaction.py`
