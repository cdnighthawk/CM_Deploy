# Estimates

Status: complete
Sage CM module: Preconstruction / Estimating
Official help: https://help.sagecm.intacct.com/Content/Modules/Estimating/Estimates/AddEstimate/AddEstimateWizardManually.htm

## Purpose

Each lead or project can have **multiple estimates** (Base Bid, Rev 1, Rev 2). An estimate holds a WBS/cost codes, cost line items (manual, cost database, or Excel), markups, narrative scope (inclusions, exclusions, clarifications), and estimate-level **RFP packages**. If awarded, the Contract Setup Wizard can create job cost codes, client contracts, budgets, POs, and subcontracts from the estimate.

## Where it lives

- Lead or Project Home → **Estimates** → View Estimate
- Tabs confirmed in help: Items, Scope; Bid Management view for RFP packages
- Properties: Estimate Properties Details (Edit after wizard)
- Mobile: not listed as estimate add/edit
- TeamLink: vendors see ITB/RFP, not the internal estimate

## Who uses it

- Estimators build items and scope
- Reviewer named on the header owns the review due date
- Bid managers create RFP packages from the estimate
- PMs run Contract Setup after award

## Prerequisites

- Lead or project exists
- Optional: Local or RSMeans cost database
- Estimate Title must be **unique** among estimates on that lead/project
- Estimate # is auto-sequenced (user can override)

## What the user fills out

### Add Estimate wizard (Manually from Scratch)

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Lead or Project # | No | Lookup | Prefilled |
| Estimate # | No | Text | Auto next number; editable |
| Estimate Title | Yes | Text | Unique per lead/project |
| Size & Units | No | Number + unit | e.g. 3000 SF |
| Reviewer | No | Lookup | Final estimate reviewer |
| Review Due Date | No | Date | Before proposal is sent |
| Prospect/Customer Company | No | Lookup | Import dialog |
| Prospect/Customer Contact | No | Lookup | |
| Address | No | Choice | Applicable address from company/contact |

Add options: **Manually from Scratch** (documented). Other add options on that screen are **not confirmed in help**.

### Items tab — work / manual lines

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Cost Code | No | Lookup | Group filter |
| Description | Yes (in practice) | Text | |
| Quantity / Unit | Yes for import | Number / text | Import: Quantity and Unit required; Unit max 10 characters |
| Item Code | No | Text | Import `Code` can pull work-item rates from the cost DB |
| Sort Number | Yes on import | Number | Import `Number`; can restart per section |
| Manufacturer / Catalog # / UPC | No | Text | Manufacturer Info tab |
| Resource rates M/L/E/S/O | No | See cost-database.md | Conv, waste (M), base/burden (L/E), sell markup |
| Sell markup option | No | Choice | Lumpsum; Manual; Margin Percentage; percent over cost; Same as Cost. Sell ≥ cost |
| RFP Package / Proposal comment / Internal comment | No | Lookup / text | Comments tab |
| Location | Conditional | Lookup | If estimate locations enabled |

Excel import (official columns from Import Estimate help extract): Number*, Quantity*, Unit*, Code, MatlConv/MatlWaste/MatlUnits, labor/equipment conv and rate columns. Full remaining column list is long; do not invent names beyond that extract.

### Scope tab

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Inclusions | No | Text | Work covered; can instead live on cost-code details — do not duplicate both |
| Exclusions | No | Text | Work not covered |
| Clarifications | No | Text | Assumptions / under-detailed drawing items |
| Scope Templates | No | Import | Settings → Templates & Reports → Scope Templates |

### Labor item details (when line is a labor item)

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Item Code / Description / Qty / Units | Yes in practice | Text / number | |
| Labor conv, unit, base cost, burden cost, sell markup | No | Number | Item Resource Units & Rates tab |

## What Sage CM saves

- Header record: estimate #, title, size/units, reviewer, review due, customer/contact/address, properties
- Line / child records: cost items (manual, work, labor, equipment, crew, assembly); cost-code WBS; scope at estimate and/or cost-code level; RFP packages linked to items
- System-generated values (IDs, numbers, dates, totals): next Estimate #; cost and sell totals from resource formulas
- Files / attachments: linked files on the estimate record (file management list includes Estimates)
- Audit / workflow fields: reviewer; Contract Setup copies scope to prime

## Statuses and lifecycle

No single official Draft/Pending/Approved list on the add wizard. Review Due Date implies a review step. After award: Contract Setup → financial project. Multiple estimates stay as versions (Base Bid, Rev 1).

## Dates that drive alerts

- **Review Due Date** — not listed on the Home alerts table (only Estimate **RFP** bid due is listed). Treat review due as a stored date, not a confirmed Home alert.
- Child RFP **Bid Due Date** — yes (see estimate-rfp-packages.md)

## Relationships

- Upstream: lead/project, cost database, customer
- Downstream: RFP packages, prime/JCC/budgets/POs/subs via Contract Setup

## Reports and exports

- Estimate Proposal Template (mail merge: estimate scope then cost-code scope)
- Excel import of estimate items (`*.xls`)
- View Estimate / Edit properties

## USIS / CM_Deploy mapping

| Sage concept | USIS table / API / page | Status |
|---|---|---|
| Estimate header | `estimates` / `backend/app/models/estimate.py` | implemented |
| Version / lock / approve | `version`, `estimate_locked_at`, `approved_at`, `is_current` | implemented |
| Takeoff lines | `takeoff_line_items` | implemented |
| Priced lines | `estimate_line_items` | implemented |
| Estimate APIs / UI | `/api/v1/estimates`, `construction/estimate.html`, `estimate-detail.html` | implemented |
| Sage WBS + M/L/E/S/O + scope tabs + Contract Setup | none as Sage estimate | none |
| Render | `GET /api/v1/lead-estimates/<id>/render/estimate-summary` | partial |

## Sources

- Official Sage help URLs used
  - https://help.sagecm.intacct.com/Content/Modules/Estimating/Estimates/AddEstimate/AddEstimateWizardManually.htm
  - https://help.sagecm.intacct.com/Content/Modules/Estimating/Estimates/Scope/EstimateScope.htm
  - https://help.sagecm.intacct.com/Content/Modules/Estimating/Estimates/CostLineItems/AddItemsFromCostDB.htm
  - https://help.sagecm.intacct.com/Content/Modules/Estimating/Estimates/CostLineItems/ItemDetails_ManuallyEnteredAndWorkItems.htm
  - https://help.sagecm.intacct.com/Content/Modules/Estimating/Estimates/CostLineItems/ItemDetails_Labor.htm
  - https://help.sagecm.intacct.com/Content/Modules/Import/ImportEstimate.htm
  - https://help.sagecm.intacct.com/Content/GettingStarted/Definitions.htm
- Local files reviewed
  - `backend/app/models/estimate.py`
  - `backend/app/models/takeoff_line_item.py`
  - `W3CRM-v3.0-13_September_2025/gulp/src/construction/estimate-detail.html`
