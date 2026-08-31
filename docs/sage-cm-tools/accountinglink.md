# AccountingLink

Status: complete
Sage CM module: Companion products
Official help: https://help.sagecm.intacct.com/Content/AccountingLink/CLSageIntacct/IntegrationOverview/IntegrationOverview.htm

## Purpose

AccountingLink is the **bridge utility** between Sage Construction Management (operations, contracts, procurement, time) and an accounting system. The official integration overview documents **Sage Intacct Construction** (US, CA, AU/NZ, UK): import/export/sync of customers, vendors, employees, projects, cost codes, commitments, invoices, payments, and job-cost actuals. Accounting staff post from SCM to Intacct and pull JTD costs and AP/AR payments back.

## Where it lives

- Standalone **AccountingLink for Sage Intacct** utility (not a Project Home documentation form).
- Help home: AccountingLink for Sage Intacct — implementation guides, Intacct configuration, SCM configuration, AccountingLink configuration, functions and troubleshooting.
- Compatible Intacct: Construction US, CA, AU/NZ, UK.
- **Mobile:** not an AccountingLink client. Payment-due alerts on prime invoices, bills, and sub invoices **clear** when payment is updated through AccountingLink Update Payment.

Other accounting targets (QuickBooks, etc.) are mentioned in some Sage marketing/search snippets; **this file only documents the official Intacct overview table**. Other ERPs are **not confirmed** on the fetched IntegrationOverview page.

## Who uses it

| Product | Personas | Purpose |
|---|---|---|
| Sage Construction Management | Estimators | ITB, estimates, vendor RFP packages |
| Sage Construction Management | PMs, supers, engineers, coordinators, accounting | Contract admin, procurement, time, job cost, budget, documentation, correspondence, QC, safety, scheduling |
| AccountingLink for Sage Intacct | Accounting staff | Import, export, sync customers/vendors/employees; post transactions to Intacct |
| Sage Intacct | Accounting staff | Corporate accounting |

## Prerequisites

- Sage CM and Sage Intacct Construction tenant (region edition).
- Implementation: SCM implementation guide + Intacct configuration + AccountingLink configuration (official home topics).
- Tax codes in SCM linked to Intacct tax schedules.
- Master/standard cost codes alignment (Intacct → SCM standard codes; SCM project cost codes → Intacct project cost codes/types).

Exact AccountingLink login/connection field names are **not confirmed** on IntegrationOverview.htm (see configuration subguides).

## What the user fills out

AccountingLink is a sync console, not a Sage “Add Manually” record. Operators choose entities to **post**, **repost**, **sync**, or **export**. Official data map:

### Contact management

| SCM | Direction | Intacct | Notes |
|---|---|---|---|
| Companies | >>> and <<< | Customers | Sync |
| Companies | >>> and <<< | Vendors | Sync |
| Company | >>> and <<< | Insurance | Sync |
| Employees | >>> and <<< | Employees | Sync |
| Customer & Vendor Contacts | >>> and <<< | Contacts | Sync |

### Projects and contracts

| SCM | Direction | Intacct | Notes |
|---|---|---|---|
| Project | >>> | Projects | |
| Master Cost Codes | <<< | Standard Cost Codes | |
| Project Cost Codes and Cost Types | >>> | Project Cost Codes / Cost Types | |
| Prime Contract Cost Budget | >>> | Estimate (Cost Budgets) | Post/repost |
| Change Order Cost Budgets | >>> | Estimate Change / Budget Revision | Post only |

### Commitments and AP

| SCM | Direction | Intacct |
|---|---|---|
| Purchase Order | >>> | (PO) |
| PO Change Order | >>> | |
| Subcontract | >>> | |
| Subcontract Change Order | >>> | |
| Bills associated with PO | >>> | |
| Bills not associated with PO | >>> | |
| Sub Invoices | >>> | |
| Employee Misc Expenses | >>> | |

### Job cost reporting (pull)

| SCM | Direction | Intacct |
|---|---|---|
| Summary by Project, Cost Code, Cost Type | <<< | Job Costs by Project, Cost Code, Cost Type |
| ERP JTD Cost Details | <<< | Job Cost GL Details |

### Time

| SCM | Direction | Intacct | Notes |
|---|---|---|---|
| Labor Timecards | >>> and <<< | Project / Payroll Timesheets | Sync |
| Equipment Timecards | >>> | Special Purchasing TD | |

### Client contract / AR

| SCM | Direction | Intacct | Notes |
|---|---|---|---|
| Prime Contract | >>> | Project Contract | Post/repost |
| Prime Contract Items (SOVs) | >>> | Contract Items | Post/repost |
| COs (Revenue) | >>> | Change Orders | |
| Prime Invoices | >>> | Contract Invoices | |

### Payments and tax

| SCM | Direction | Intacct | Notes |
|---|---|---|---|
| AP Payments | <<< | AP Invoice Payments | Clears bill payment-due alerts |
| AR Payments | <<< | AR Invoice Payments | Clears prime invoice payment-due alerts |
| Tax Codes | Linked | Tax Schedules | |
| Cost-to-Date Transactions | >>> | Yes | Linked |
| Client Contract Transactions | >>> | Yes | Linked |
| WIP / Forecasting | >>> | Excel import | |

## What Sage CM saves

- **Header record:** No AccountingLink document in SCM. Posted transactions keep their SCM IDs; Intacct stores the GL/AP/AR side.
- **Line / child records:** Same as source SCM transactions (PO lines, invoice SOVs, timecard lines).
- **System-generated values:** Intacct document numbers after post (exact field names **not confirmed** on overview).
- **Files / attachments:** Not the integration payload on this page.
- **Audit / workflow fields:** Post vs repost vs post-only vs sync; Update Payment removes payment-due alerts.

## Statuses and lifecycle

1. Configure Intacct + SCM + AccountingLink.
2. Sync cards (customers, vendors, employees, insurance, contacts).
3. Push project, cost codes, budgets, contracts, commitments, invoices, timecards, expenses.
4. Pull JTD job cost and AP/AR payments.
5. WIP/forecasting via Excel import path.

WO costs still do **not** hit analytics until converted to CO/invoice/commitment **inside SCM**, then those documents post through AccountingLink.

## Dates that drive alerts

AccountingLink **removes** these alerts when Update Payment runs:

- Prime invoice **payment due date**
- Bill **payment due date**
- Subcontract invoice **payment due date**

## Relationships

- **Upstream:** All SCM financial and time modules.
- **Downstream:** Sage Intacct GL, AP, AR, projects, payroll timesheets.
- **USIS:** `corecon_transactions` is a historical Corecon/Sage CM **import** of posted rows (including work_order_*), not a live AccountingLink.

## Reports and exports

- Job cost summary and ERP JTD details from Intacct into SCM.
- WIP/forecasting Excel import.
- Official home: functions and troubleshooting topics.

## USIS / CM_Deploy mapping

| Sage concept | USIS table / API / page | Status |
|---|---|---|
| AccountingLink sync console | none | none |
| Imported Corecon/Sage rows | `corecon_transactions` (incl. WO/CO/cost-code columns) | stub |
| Intacct customers/vendors/POs | none | none |

## Sources

- Official Sage help URLs used
  - https://help.sagecm.intacct.com/Content/AccountingLink/CLSageIntacct/IntegrationOverview/IntegrationOverview.htm
  - https://help.sagecm.intacct.com/Content/AccountingLink/CLSageIntacct/CLSageIntacct_Home.htm
  - https://help.sagecm.intacct.com/Content/Modules/AlertsCalendars/AlertsCalendar_All.htm
- Local files reviewed
  - `backend/app/models/corecon_transaction.py`
