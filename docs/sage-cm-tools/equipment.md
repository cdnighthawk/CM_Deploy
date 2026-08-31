# Equipment

Status: complete
Sage CM module: Equipment (also Cost Database)
Official help: https://help.sagecm.intacct.com/Content/Modules/Equipment/EquipmentItems/EquipmentItemsAddManually.htm

## Purpose

Equipment items are catalog records used in **estimates** and, for **owned** equipment, in **equipment timecards**. Rental equipment cost is not timecarded; it goes through PO or bill. Each item stores run/idle/down rates, optional spare parts, classifications, and purchase/rental facts.

## Where it lives

- Global nav: **Equipment** (Equipment Stats → Equipment Items)
- Also: **Cost Database** → Equipment tab (same items; Excel import from either place)
- Consumed on estimate lines and Time & Expenses → Equipment timecards
- Mobile: equipment **timecards** are add/edit; the catalog itself is not listed as a mobile module
- TeamLink: not applicable

## Who uses it

- Estimators maintain rates and pull items into estimates
- Equipment managers enter make/model/serial, purchase, and spare parts
- Field timekeepers enter run/idle/down hours on owned equipment

## Prerequisites

- Optional: classification system in Settings → Feature Settings → Cost Codes
- Run Time **Base Cost**, **Burden Cost**, and **Proposal/Bill** rates are required on add (and on Excel import)
- `RentedEquipment` on import: yes = rented, no = owned; **blank defaults to rented**
- Owned vs rented: only owned items are used on equipment timecards (Definitions)

## What the user fills out

### Wizard step 1 — General information and rates

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Code | Yes | Text | Import max 25 characters |
| Description | Yes | Text | Import max 255 characters |
| Run Time Base Cost Rate | Yes | Number | Used in estimating **and** timecards |
| Run Time Burden Cost Rate | Yes | Number | |
| Run Time Bill Rate | Yes | Number | Proposal/bill; usually ≥ cost |
| Idle Time Cost Rate / Bill Rate | No | Number | Timecards only |
| Down Time Cost Rate / Bill Rate | No | Number | Timecards only |
| Daily / Weekly / Monthly Rental Rate | No | Number | Import columns |
| Manufacturer / Model / Model Year / Serial # | No | Text / number | Manual step 2 also has Make, Model, Serial #, Comments |
| Body, Gross Weight, Capacity, Type Fuel, Cylinders, Tires, Work Hrs | No | Text / number | Import identity fields |
| Rented Equipment | No | Yes/No | Import `RentedEquipment`; blank → rented |

### Wizard step 2 — Spare parts (optional; Skip allowed)

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Component name | Yes if adding a part | Text | |
| Make / Model / Serial # / Comments | No | Text | Per part |
| Additional lines | No | Grid | Add New Line if more than five parts |

### Wizard step 3 — Classifications (optional; Skip allowed)

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Classification Type | No | Lookup | e.g. master cost code system |
| Code (Division → Major → Minor → Subminor) | No | Lookup | Drill-down |

### Purchase block (Excel import; may appear on the item form — extra UI labels not confirmed in help)

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Purchase PO Num | No | Text | |
| Purchase Date / Delivery Date | No | Date | DD-MMM-YYYY, MM-DD-YYYY, or YYYY-MM-DD |
| Purchase Price / Freight / Tax / Total / Book Value | No | Number | |
| Purchase Comments | No | Text | |

## What Sage CM saves

- Header record: equipment item with identity, owned/rented, run/idle/down rates, rental rates, purchase facts
- Line / child records: spare-part components; classification assignments
- System-generated values (IDs, numbers, dates, totals): internal item ID
- Files / attachments: not confirmed in help
- Audit / workflow fields: not confirmed in help

## Statuses and lifecycle

No approval workflow in help. Owned items participate in timecards (RT / IT / DT). Rented items stay in estimating / rental-rate fields and procurement.

## Dates that drive alerts

None on the catalog item. Purchase/delivery dates are stored; they are **not** listed on the alerts feature table.

## Relationships

- Upstream: Cost Database / Equipment module
- Downstream: estimate equipment lines; equipment timecards (owned); crews/assemblies can include equipment items

## Reports and exports

- Excel import/export of equipment items (`*.xls`, Sheet1)
- Equipment Stats on the Equipment home

## USIS / CM_Deploy mapping

| Sage concept | USIS table / API / page | Status |
|---|---|---|
| Equipment catalog | none | none |
| Equipment resource on takeoff | `takeoff_line_items.cost_type = E` | stub |
| Equipment timecards | none | none |
| Safety “equipment_check” | `safety.py` checklist type — not a fleet catalog | none |

## Sources

- Official Sage help URLs used
  - https://help.sagecm.intacct.com/Content/Modules/Equipment/EquipmentItems/EquipmentItemsAddManually.htm
  - https://help.sagecm.intacct.com/Content/Modules/Import/ImportEquipmentItems.htm
  - https://help.sagecm.intacct.com/Content/GettingStarted/Definitions.htm
- Local files reviewed
  - `backend/app/models/takeoff_line_item.py`
  - `backend/app/models/safety.py`
