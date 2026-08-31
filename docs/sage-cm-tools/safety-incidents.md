# Safety incidents

Status: complete
Sage CM module: QC and Safety
Official help: https://help.sagecm.intacct.com/Content/Modules/QCSafety/SafetyAccident/SafetyAccidentOverview.htm

## Purpose

Safety Incidents (help still uses “Safety Accident” in templates and URLs) is the OSHA-oriented log of jobsite events: medical treatment beyond first aid, lost workdays, restricted work, loss of consciousness, or death. The record stores cause/description, safety violations, corrective action, time lost, plus child tables for **personal injuries**, **property/equipment damage**, and **witnesses**.

## Where it lives

- **Project Home** → QC and Safety / Safety → **Safety Incidents**.
- Functions: Add Safety Incident; Add or Edit Personal Injury; Add or Edit Property or Equipment Damages; Add or Edit Witnesses; Printing a Safety Incident.
- **Mobile:** Safety incidents R, E, A, D.
- **Alerts / Team Open Items:** Incidents are **not** on the Safety alerts-date table and **not** on the open-items email table.
- Default Word template category: **Safety Accident** (`SafetyAccident.dot`).

The dedicated “Add Safety Incident” field-by-field topic was **not found** (guessed `SafetyAccidentAddManually.htm` returned 404). Header and child fields below come from the official **mail-merge / bookmark** list, which is what Sage persists for reports.

## Who uses it

- **Recorded By** company/contact (must be in the **project directory**) documents the accident.
- Medical/safety staff add injured persons, property owners, and witnesses.
- Office prints the incident and runs project or **multi-project** log reports (Apr 2025).

## Prerequisites

- Project; Recorded By in the project directory.
- Optional prime contract (merge field SafetyAccidentRefPrimeContract).

## What the user fills out

### Header (persisted — Safety accident general information bookmarks)

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Date (SafetyAccidentDate) | Yes (implied) | Date | Incident date; log report filter IncidentDateFrom/To |
| Time (SafetyAccidentTime) | No | Time | |
| Location (SafetyAccidentLocation) | No | Text | |
| Description (SafetyAccidentDescription) | No | Text | Cause / what happened |
| Safety violation (SafetyAccidentViolation) | No | Text | Log report IncludeSafetyViolation |
| Corrective action (SafetyAccidentCorrectiveAction) | No | Text | |
| Time lost (SafetyAccidentTimeLost) | No | Yes/No or hours | Log filter **LostTime**; overview examples include lost work days |
| Prime contract (SafetyAccidentRefPrimeContract) | No | Prime contract | |
| Recorded By company / contact | Yes (prerequisite) | Directory | Shipping-address fields merge onto the report |

Recorded By merge fields (from contact/company, not retyped): prefix, first/middle/last, suffix, contact, title, mobile, email, company code/name, address, phones, fax, website, gov tax ID.

Exact UI labels on the add form beyond these bookmark names are **not confirmed in a create-topic**; use the bookmark names as the persistence contract.

### Personal injury (merge table SafetyAccidentInjury)

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Injured name (prefix, first, middle, last, suffix) | No | Text | Or InjuredContact |
| Title / Craft | No | Text | InjuredTitle, InjuredCraft |
| Age / Gender | No | Text | |
| Company + company address/phone/fax | No | Text / directory | |
| Home address / phone / email | No | Text | |
| Description of injury | No | Text | InjuredDescriptionOfInjury; log IncludeInjuryDesc |
| Severity of injury | No | Text | InjuredSeverityOfInjury; log InjuryStatus |
| Work activity | No | Text | InjuredWorkActivity |
| Loss work days | No | Number | InjuredLossWorkDays |
| Restricted work days | No | Number | InjuredRestrictedWorkDays |
| Estimated medical expenses | No | Money | |
| Actual medical expenses | No | Money | |

### Property / equipment damage (merge table PropertyDamage)

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Property owner contact / company | No | Text | + owner address, phone, fax |
| Item description | No | Text | PropertyItemDescription |
| Manufacturer / Model / Model year / Serial number | No | Text | |
| Damage description | No | Text | |
| Estimated damage amount | No | Money | |
| Actual damage amount | No | Money | |

Log filters: PropertyDamageStatus; IncludePropDesc; IncludeDamageDesc.

### Witnesses (merge table Witness)

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Witness name (prefix … suffix) / contact / title | No | Text | |
| Company + company address/phone/fax | No | Text | |
| Home address / phone / email | No | Text | |
| Observation location | No | Text | WitnessObservationLocation |
| Observation description | No | Text | WitnessObservationDescription |

### Linked files

Punchlist-style upload-from-record list includes **Safety Incidents**: Add or Link Existing (Photos, Drawings & Specs, All Other Records). Limits follow the generic file topic (10 files at once on that page; add wizards elsewhere use 48/500 MB).

## What Sage CM saves

- **Header record:** Date, time, location, description, violation, corrective action, time lost, prime contract, recorded-by.
- **Line / child records:** Injuries; property damage rows; witnesses.
- **System-generated values:** Incident identity used by `vw_SafetyIncidentInfo` and log reports (internal ID **not named** in user help).
- **Files / attachments:** Linked files; Word merge `SafetyAccident.dot`.
- **Audit / workflow fields:** LostTime, InjuryStatus, PropertyDamageStatus on reports — pick-list values **not enumerated in help**.

## Statuses and lifecycle

No Draft/Approved workflow in help. Report filters imply injury status, property-damage status, and lost-time flags. Overview examples: medical treatment other than first aid; lost work days; restriction of work or motion; loss of consciousness; death.

## Dates that drive alerts

Incident date is **not** on the Safety alerts table. Use log reports (IncidentDateFrom/To) for follow-up, not Home Alerts.

## Relationships

- **Upstream:** Project directory Recorded By; optional prime contract.
- **Downstream:** Print incident; project and multi-project log reports; Word template.
- **Not** USIS Cal/OSHA incident packet (different fields: §342 call, 300 log, etc.).

## Reports and exports

Data views: `vw_SafetyIncidentInfo`, `vw_SafetyIncidentInjuries`, `vw_SafetyIncidentPropertyDamage`, `vw_SafetyIncidentWitnesses`.

**Project-specific / multi-project standard reports:**

- Injuries by Project and Safety Incident
- Injuries by Date and Safety Incident
- Property Damage by Project and Safety Incident
- Property Damage by Date and Safety Incident
- Safety Incidents by Project
- Safety Incidents by Date

Filters include ProjectId, PrimeContractId, RecordedByContactId, LostTime, InjuryStatus, PropertyDamageStatus, date range, include-description flags.

Path: Reports → Project Specific Reports → Safety Incidents → Multi-Project Reports (Apr 2025).

## USIS / CM_Deploy mapping

| Sage concept | USIS table / API / page | Status |
|---|---|---|
| Sage incident header + children | none | none |
| Incident / near miss paper form | `docs/safety-automation/templates/forms/INCIDENT.md` | none (packet, not Sage) |
| Pretask near miss | `daily_pretasks.near_miss`, `near_miss_notes` | none |
| Safety training (not incidents) | `safety_training_records` | none |

USIS INCIDENT fields (type Injury/Illness/Near miss/Property/Violence, Cal/OSHA §342, 300 log) are **not** Sage bookmark names — do not conflate.

## Sources

- Official Sage help URLs used
  - https://help.sagecm.intacct.com/Content/Modules/QCSafety/SafetyAccident/SafetyAccidentOverview.htm
  - https://help.sagecm.intacct.com/Content/Modules/Reporting/DetailReportTemplates/QCSafety/SafetyAccidents.htm
  - https://help.sagecm.intacct.com/Content/Modules/Reporting/LogReports/QCSafety/ViewsReports_SafetyIncidents.htm
  - https://help.sagecm.intacct.com/Content/ReleaseNotes/April-2025/April-2025-WhatsNew-BE-safety-cross-project-log-reports.htm
  - https://help.sagecm.intacct.com/Content/Modules/FileManagement/UploadingFilesFromFeature.htm
- Local files reviewed
  - `docs/safety-automation/templates/forms/INCIDENT.md`
  - `backend/app/models/safety.py`
  - `backend/app/models/safety_training.py`
