# Feature settings

Status: complete
Sage CM module: Administration
Official help: https://help.sagecm.intacct.com/Content/Administration/Settings/FeatureSettings/FeatureSettings_TimeExpenses.htm

## Purpose

Feature Settings are administrator-maintained pick lists and module toggles (Time & Expenses, Correspondence, Contact Management, Contract Admin, etc.). They do not store project transactions. Users pick these values on create/edit forms. You cannot delete a list value that is referenced on a record.

## Where it lives

- Settings (gear) → Feature Settings → module section (Time & Expenses, Correspondence, Contact Management, …).
- Admin only. Lists then appear on project/lead forms and imports (exact string match).

## Who uses it

Administrators. Financial Admins do not get Settings unless given a custom role. End users only consume the lists.

## Prerequisites

Administrator login. Plan lists before first transactions so imports and filters stay stable.

## What the user fills out

Each subsection is a grid: Add → type in footer → Save.

### Time & Expenses — toggles (Timecard settings)

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Mark Imported Timecards as Pending | No | Checkbox | Recommended; else Excel imports are Approved |
| Show Only Cost Codes with Labor Hour Budgets | No | Checkbox | JCC dropdown requires labor hour budget > 0 |
| Show Only Cost Codes with Equipment Hour Budgets | No | Checkbox | Same for equipment |
| Show Only Currently Owned Equipment | No | Checkbox | Equipment with a purchase date |
| 1st Day of Week | Yes | Enum | Weekly labor form |
| Restrict Labor Timecard Add / Update by Payroll Weeks | No | Checkbox + integer | 0 = admins any week; 1 = current week only; 2 = current+prior; … |
| Do you wish to establish Field Crews for Timecards? | No | Checkbox | Crew leader + employees + optional equipment |
| Do you wish to use Clock In / Out for Timecards? | No | Checkbox | Off by default |
| Track Breaks? | If clock-in | Checkbox | |
| Use Geofencing? | If clock-in | Checkbox | Browser IP (web) vs GPS (mobile) |
| Geofencing Units / Distance | If geofence | Enum + number | Miles or kilometers around project address |
| Do you wish to use Clock In/Out for Field Crews? | If clock-in + crews | Checkbox | Leader punches the crew |

### Time & Expenses — lists

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Employee departments | No | Text rows | Org grouping |
| Payroll items | Yes for labor | Text rows | ST, OT, etc.; typically match accounting |
| Payroll burdens / burden templates | No | Rates | Used on employee Timecard Rates |
| Workers compensation codes | No | Code, Description, Lumpsum or Percentage, rate | US; optional on labor card; burden math in official WC help |
| Miscellaneous expense types | No | Text rows | Gas, Food, Lodging |
| Miscellaneous expense payment types | Yes for expenses | Text rows | Cash, Check, Credit Card – Amex/Visa/MC, Commercial Acct, Do Not Export |

### Correspondence — lists (each has its own help page under Feature Settings)

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| RFI Types | No | Text rows | Cannot delete if referenced |
| RFI Reason options | No | Text rows | Referenced from RFI add |
| RFI Priority options | No | Text rows | |
| Journal types | No | Text rows | Overview: categorize journals |
| Issue types | No | Text rows | Issues overview |
| Submittal types | No | Text rows | Shop Drawings, Schedules, Samples, Mockups, … |
| Submittal Item Status | Yes for item status | Text rows | Import must match |
| Transmittal types | No | Text rows | Changes, Contract, Mockups, Progress Invoice, Samples, Shop Drawings, Schedule |
| Transmittal Sender options | No | Text rows | |
| Transmitted For options | No | Text rows | Per transmittal item |

A single “Correspondence feature settings” hub page is linked from the Correspondence resource center; the fetched hub did not enumerate every list. Additional correspondence lists (if any) are not confirmed in help.

### Contact Management (referenced from employees)

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Contact titles | No | Text rows | Salutation/Title on employees |

### Contract Admin (referenced from COs)

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Initiated By options | No | Text rows | Used on CO add (not this assignment’s create forms) |

Other Feature Settings modules (Procurement types, Documentation, QC, Safety, Scheduling) exist in the product; their full list names were not fetched for this file. Do not invent them.

## What Sage CM saves

- Header record: none. Module setting rows + toggle booleans.
- Line / child records: each list option; WC code + burden type/rate.
- System-generated values: none.
- Files / attachments: none.
- Audit / workflow fields: referenced-in-use blocks delete.

## Statuses and lifecycle

Options stay until unused. Archiving a payroll item inactivates standard employee rates that use it.

## Dates that drive alerts

None. Geofence distance is spatial, not a date.

## Relationships

- Downstream: every create form and Excel import that requires an exact list match.
- Sibling: Company Settings (numbering, locking); Workflow (approvers still need feature access from roles).

## Reports and exports

List values appear as filter columns on log reports. Payment types also drive AccountingLink export rules.

## USIS / CM_Deploy mapping

| Sage concept | USIS table / API / page | Status |
|---|---|---|
| Feature pick lists | none (hardcoded enums in places) | none |
| RFI configurable fieldsets | `rfi_configurable_fields`, `rfi_custom_field_defs` | partial — Procore fieldsets, not Sage lists |
| HRMS module settings | `hrms_module_settings` (key/JSON) | stub |
| Clock-in / geofence defaults | `DEFAULT_GEOFENCE_RADIUS_M` in `field_ops.py` | stub — code constant, not admin UI |
| Payroll items | none | none |

## Sources

- https://help.sagecm.intacct.com/Content/Administration/Settings/FeatureSettings/FeatureSettings_TimeExpenses.htm
- https://help.sagecm.intacct.com/Content/Administration/Settings/FeatureSettings/FeatureSettings_TimeExpenses_MiscExpensePaymentTypes.htm
- https://help.sagecm.intacct.com/Content/Administration/Settings/FeatureSettings/FeatureSettings_TimeExpenses_WorkmensCompCodes.htm
- https://help.sagecm.intacct.com/Content/Administration/Settings/FeatureSettings/FeatureSettings_Correspondence_RFITypes.htm
- https://help.sagecm.intacct.com/Content/Administration/Settings/FeatureSettings/FeatureSettings_Correspondence_SubmittalTypes.htm
- https://help.sagecm.intacct.com/Content/Administration/Settings/FeatureSettings/FeatureSettings_Correspondence_TransmittalTypes.htm
- https://help.sagecm.intacct.com/Content/Modules/Correspondence/ResourceCenter_Correspondence.htm
- Local: `backend/app/models/rfi.py`, `backend/app/models/hrms_core.py`, `backend/app/models/field_ops.py`
