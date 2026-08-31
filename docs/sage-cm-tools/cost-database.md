# Cost database

Status: complete
Sage CM module: Cost Database / Estimating
Official help: https://help.sagecm.intacct.com/Content/GettingStarted/ImplementationPlan_Est_Opt_CostDatabase.htm

## Purpose

The cost database is the reusable price book for estimates: consistent codes, descriptions, units, and rates so estimators do not retype every line. Sage stores **five item types**: labor items, equipment items, crews, work items, and work assemblies. A **Local** database is yours; **RSMeans** is a licensed add-on (90,000+ items, 1,000+ location factors).

## Where it lives

- Global nav: **Cost Database** (Internal Cost Database Stats; tabs per item type)
- Equipment items can also be imported from the **Equipment** module
- Consumed from a lead/project **Estimate → Items → Add / Import → Add From Cost Database**
- Not a TeamLink tool
- Mobile: not listed as a field add/edit module

## Who uses it

- Estimators and cost engineers maintain Local items
- Administrators configure cost-code classification systems (Feature Settings → Cost Codes)
- Sage sales enables RSMeans
- Timekeepers reuse labor items on labor timecards (payroll rates on the labor item override the employee profile when set)

## Prerequisites

- Optional: classification systems (CSI 95, CSI 2004, CSI 2016 label required if using RSMeans)
- Optional: geographic **locations** for location-specific labor rates
- Optional: quantity **formulas** for work items
- RSMeans: cost-code list in Sage **must** be labeled `CSI 2016` (with a space), even if you use a newer CSI year

## What the user fills out

### Item types (what you maintain)

| Item type | Role | Official create path |
|---|---|---|
| Labor items | Occupations / staff types; estimate lines and timecard payroll rates | Add manually or Excel import |
| Equipment items | Owned/rented equipment rates (also Equipment module) | Add manually or Excel import — see `equipment.md` |
| Work items | Tasks with M/L/E/S/O resource rates (or materials-only) | Add manually or Excel import |
| Crews | Components: equipment + labor items | Add in UI (no Excel template in implementation plan) |
| Work assemblies | Components: equipment + labor + work items; UniFormat when from RSMeans | Add in UI |

### Work item resource model (official)

Each work item has a unit of measure plus **five resources**: Material (M), Labor (L), Equipment (E), Subcontract (S), Other (O).

| Field group | Required | Type | Notes / allowed values |
|---|---|---|---|
| Work item unit of measure | Yes (conceptually) | Text | SF, FT, LF, etc. Formula output unit must match |
| Default quantity formula | No | Formula | Avoids picking a formula each time the item is added to an estimate |
| Classification codes | No | Lookup | Group/filter items |
| M/S/O: Conv. Factor, Waste % (M), Unit, Base Cost Rate, Sell Rate | No | Number | Conversion often 1 when units match the work item |
| L/E: Conv. Factor, Unit, Base Cost Rate, Burden Cost Rate, Sell Rate | No | Number | Time units (Hrs, Day, Week). Productivity calculator can fill conversion |
| Markup / sell | No | Choice | Proposal rate ≥ cost rate. Options documented on estimate items: Lumpsum, Manual, Margin Percentage, percent over cost, Same as Cost |

Official total-cost formulas (per work-item unit):

- M = Conv × (1 + Waste %) × M Base Cost Rate
- L = Conv × (L Base + L Burden)
- E = Conv × (E Base + E Burden)
- S = Conv × S Base
- O = Conv × O Base

Sell uses the same conversions with sell rates (M includes waste).

### Add From Cost Database (on an estimate)

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Target Cost Code | Yes | Choice | Use Existing Cost Code **or** Auto Populate from Cost DB classification (Division / Major / Minor / Subminor / Lowest) |
| Location | Conditional | Lookup | If locations are enabled on the estimate |
| Database | Yes | Choice | Local or an RSMeans database |
| Item kind | Yes | Choice | Work Item (default), Labor, Equipment, Assemblies, Crews |
| Filter | No | Classification (up to 5 codes) or Text Search | Text Search hits Code, Description, Manufacturer |
| Quantity | No | Number | Default 0; editable after add |

RSMeans **unit costs** land in the Work Items table. **Assemblies** use UniFormat and a separate Work Assembly table.

### Labor items (overview-level fields)

Help does not publish a full labor-item add form. Confirmed concepts:

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Code / description (e.g. Carp-F, Elec) | Yes (in practice) | Text | Examples in help |
| Classification codes | No | Lookup | |
| Location-specific estimating rates | No | Table | Multi-city/county |
| Timecard payroll rates | No | Rates | Override employee profile; can be project-specific; Excel import of timecard rates exists |

Exact labor add-form column names beyond Code/Description/classifications/rates: **not confirmed in help**.

## What Sage CM saves

- Header record: one row per labor, equipment, work item, crew, or assembly in the Local (or RSMeans) catalog
- Line / child records: crew/assembly components; location rates; project-specific timecard rates
- System-generated values (IDs, numbers, dates, totals): calculated cost/sell per work-item unit
- Files / attachments: not confirmed in help for catalog items
- Audit / workflow fields: not confirmed in help

## Statuses and lifecycle

Catalog items are maintained, not workflow-approved. Copying an item onto an estimate **snapshots** rates onto the estimate line; later catalog edits do not automatically rewrite existing estimates (behavior implied by “add to estimate”; live-link vs snapshot is **not confirmed in help**).

## Dates that drive alerts

None.

## Relationships

- Downstream: estimate cost lines; labor/equipment timecards; crews and assemblies compose other items
- Upstream: Feature Settings cost codes; optional RSMeans subscription

## Reports and exports

- Export work items to Excel (work item overview)
- Excel import templates for equipment, labor, work items
- No crew/assembly Excel templates in the implementation plan

## USIS / CM_Deploy mapping

| Sage concept | USIS table / API / page | Status |
|---|---|---|
| Local cost catalog | none as a Cost Database module | none |
| Work item M/L/E/S/O | `takeoff_line_items.cost_type` (`L`,`M`,`E`,`S`,`O`) | partial |
| Material list pricing | `material_pricing` / `backend/app/models/material_pricing.py` | partial |
| Manufacturer data sheets | `manufacturer_product_data` | stub |
| RSMeans | none | none |
| Labor/equipment catalog + crews/assemblies | none | none |
| RFI cost codes | `rfi_cost_codes` — project lookup, not a price book | stub |

## Sources

- Official Sage help URLs used
  - https://help.sagecm.intacct.com/Content/GettingStarted/ImplementationPlan_Est_Opt_CostDatabase.htm
  - https://help.sagecm.intacct.com/Content/Modules/Estimating/Estimates/CostLineItems/AddItemsFromCostDB.htm
  - https://help.sagecm.intacct.com/Content/Modules/Estimating/CostDatabase/WorkItems/WorkItemsOverview.htm
  - https://help.sagecm.intacct.com/Content/Modules/Estimating/CostDatabase/LaborItems/LaborItemsOverview.htm
  - https://help.sagecm.intacct.com/Content/GettingStarted/Definitions.htm
- Local files reviewed
  - `backend/app/models/takeoff_line_item.py`
  - `backend/app/models/material_pricing.py`
  - `backend/app/models/rfi_lookups.py`
