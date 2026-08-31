# Work orders

Status: complete
Sage CM module: Documentation
Official help: https://help.sagecm.intacct.com/Content/Modules/Documentation/WorkOrders/WOOverview.htm

## Purpose

Work orders (WOs) are field directives — daily crew instructions, owner-directed work, or back-charge documentation — with optional estimated and actual cost lines. WO dollars do **not** hit project analytics until a wizard copies them into a prime CO, prime invoice, PO, subcontract, or SCO.

## Where it lives

- **Project Home** → Documentation → **Work Orders**.
- Add wizard: header → items → linked files; items can be added later (Skip).
- **Documentation Overview** → Team Open Items (Issued To and Reviewer).
- **Mobile:** WO R; E (items, headers, reviewer comments); A (items, headers); D (items).
- **TeamLink:** not a create surface for internals; open WO email can include portal follow-up.

## Who uses it

Typical Issued By / Issued To / Reviewer (official table):

| Type of firm | Issued by | Issued to | Reviewer (optional) |
|---|---|---|---|
| Owner | Owner | GC / Architect / Engineer | Owner / Architect |
| GC | GC | GC (field crew) | |
| GC | GC | Subcontractor | |
| Architect | Architect | GC / Engineer / Consultant | Owner / Architect |
| Subcontractor | Subcontractor | Subcontractor | |

PMs/supers create WOs; reviewers enter Review Comments; accounting converts approved WOs to CO/invoice/commitment.

## Prerequisites

- Project; your firm and Issued To company in the **project directory**.
- Optional prime contract; Settings → Feature Settings → Documentation → **WO Type**.
- Job cost codes (default used if line cost code blank); tax codes; resource defaults (else **M** materials).
- Cost database / estimates / POs / bills / sub invoices / timecards if importing lines.
- Cost Plus prime contract for **Billable Status**.

## What the user fills out

### Header (Actions → Add Manually)

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Project number | No | Project picker | |
| Prime Contract number | No | Prime contract | Optional on add |
| Issue Date | No | Date | Defaults to today; drives alerts |
| WO # | No | Text/number | Auto-generated; user may override |
| Subject | Yes | Text | |
| WO Type | No | Dropdown | Filtering; Feature Settings → Documentation |
| Issued By Company / Contact | Yes (help: select) | Directory | Key Contacts |
| Issued To Company / Contact | Yes (help: select) | Directory | Open-item “issued to” |
| WO Description | No | Text | |
| Prime Contract # | No | Reference | Listed again under references |
| CPR / CO # | No | Reference | |
| Subcontract # | No | Reference | |
| SCO # | No | Reference | |
| Drawing | No | Reference | |
| Location | No | Text | |
| Spec. Section | No | Text | |
| Other | No | Text | |
| Status | No | Status | Open used by open-items email; Approved sets Status Date |
| Status Date | Conditional | Date | Date Status is set to **Approved** |
| Billable Status | No | Status | **Cost Plus prime contracts only** |
| Address Type | No | Enum | **Used only for printing** |
| Cost Reviewer Company / Contact | No | Directory | Optional reviewer |
| Type of Costs to Review | No | Choice | Review Actual **or** Review Estimated |
| Review Date | No | Date | |
| Review Comments | No | Text | Null + Open status = open item for reviewer |

### Work Order Items

Default line values: Job Cost Code, Tax Code, Resource (used when a line is left blank). Optional **Show Estimated Cost and Sell Rates**.

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Item # | Yes (help: enter) | Text/number | Sort order |
| Description | Yes | Text | |
| Quantity | Yes | Number | Import labor/equipment: hours or days from selected rate |
| Units | Yes (help: enter) | Text | |
| Cost Rate (actual) | Yes (help: enter) | Money | Importing items populates **actual** rates, not estimated |
| Sell Rate (actual) | Yes (help: enter) | Money | Also called proposal rate |
| Estimated Cost Rate | If show estimated | Money | |
| Estimated Sell Rate | If show estimated | Money | |
| Cost Code | No | Job cost code | Default if blank |
| Tax code | No | Tax code | Default if blank |
| Resource | No | Resource | Default if blank; else **M** (materials). Categorizes M / L / E / S / O |

### Item import sources (Add / Import Items)

| Import | Confirmed filters / notes |
|---|---|
| Labor items (cost database) | Rates: Hr. Bill, Hr. Cost, Daily Bill, Daily Cost (daily = hourly × 8); Default Cost Code; Qty hours or days |
| Equipment items (cost database) | Hr/Daily/Project Hr/Daily bill or cost; Rental Daily/Weekly/Monthly; Default Cost Code |
| Work items (cost database) | Filter Type text or classification; rates Total/M/L/E/S/O cost or sell; L/E cost = base + burden |
| Estimate items | Estimate #; optional cost-code filter; Exclude Estimate Items tagged in an RFP Package (avoid PO/sub dupes) |
| Estimate items summary | Grouped/summed by code, description, UOM; qty is entire estimate (no cost-code filter) |
| PO items | Supplier; PO; optional Summarized Records Reference Target Feature and Record Number; **Include Daily Log Quantity** |
| Bill items | Supplier; Bill; optional summarized reference; qty editable |
| Sub invoices | Subcontract + Sub Invoice; summarized by Job Cost Code |
| Labor timecards | From Date / To Date; optional summarized reference |
| Equipment timecards | From Date / To Date; optional summarized reference |
| Employee miscellaneous expenses | Employee; From Date / To Date |

### Linked files

Same as other documentation: 48 files / 500 MB; Link Existing Files Photos / Drawings & Specs / All Other Records.

## What Sage CM saves

- **Header record:** WO number, dates, subject, type, parties, references, status, billable status, address type, reviewer block.
- **Line / child records:** WO items with actual (and optional estimated) rates, qty, units, cost code, tax, resource.
- **System-generated values:** WO #; Status Date when Approved; default cost code / tax / resource; Resource default M; daily rates = hourly × 8 on labor/equipment import.
- **Files / attachments:** Linked files on the WO.
- **Audit / workflow fields:** Issued To / Reviewer open-item flags; Review Comments; conversion wizards (job cost only after copy).

## Statuses and lifecycle

| Status / action | Effect |
|---|---|
| Open | Team Open Items for Issued To; reviewer open item if Review Comments null |
| Approved | Status Date stored; typical gate before conversion |
| Close a WO | Official function (close) |
| Convert to CPR or CO | Lump sum → prime CO (Appr. or Pending Revenue Budget) |
| Convert to prime invoice | Cost Plus → Billings To Date |
| Add subcontract, PO, or SCO from WO | Any contract type → Appr. or Pending Committed Cost |
| Document back charges | Same WO feature |

Until conversion, WO costs are **not** in project analytics.

## Dates that drive alerts

- **Issue date** — Documentation Calendar / Home Alerts.
- Review Date is reviewer workflow, not listed on the alerts table.

## Relationships

- **Upstream:** Directory, prime contract, CPR/CO, subcontract/SCO, drawings, cost database, estimates, POs, bills, sub invoices, timecards, daily log quantities.
- **Downstream:** Prime CO, prime invoice, PO, subcontract, SCO; email to issued contact or reviewer; print/share WO.

## Reports and exports

- Print or share a WO.
- Email WO to issued contact; email WO to reviewer.
- Team Open Items from Documentation Overview.

## USIS / CM_Deploy mapping

No native WO module. Corecon/Sage import columns exist on transaction rows only.

| Sage concept | USIS table / API / page | Status |
|---|---|---|
| WO header IDs/dates | `corecon_transactions.work_order_corecon_id`, `work_order_number`, `work_order_subject`, `work_order_issue_date_*`, `work_order_status_date_*` | stub |
| WO items / rates / resource | none | none |
| Convert to CO / invoice / PO | none | none |
| Mobile WO | none | none |

## Sources

- Official Sage help URLs used
  - https://help.sagecm.intacct.com/Content/Modules/Documentation/WorkOrders/WOOverview.htm
  - https://help.sagecm.intacct.com/Content/Modules/Documentation/WorkOrders/WOAddManually.htm
  - https://help.sagecm.intacct.com/Content/Modules/Emailing/OpenItemsEmail.htm
  - https://help.sagecm.intacct.com/Content/Modules/AlertsCalendars/AlertsCalendar_All.htm
  - https://help.sagecm.intacct.com/Content/Mobile/MobileApp_Apple/MobileApp_AppleiOS_Overview.htm
- Local files reviewed
  - `backend/app/models/corecon_transaction.py`
