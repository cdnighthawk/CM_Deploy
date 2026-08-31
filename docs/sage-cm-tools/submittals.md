# Submittals

Status: complete
Sage CM module: Correspondence
Official help: https://help.sagecm.intacct.com/Content/Modules/Correspondence/Submittals/SubmittalsOverview.htm

## Purpose

Submittals collect items required by the specifications (shop drawings, samples, test results, product data) from an **originator** (sub/supplier), through a **coordinator** (typically the GC), to **respondents** (architect/owner) for review. Sage persists a header plus **submittal items** (each with its own status and originator/delivery dates) and a **Respondents** grid (company/contact, order, sent/due/responded, response). Rejected items can be copied to a new linked submittal for resubmission.

## Where it lives

- Lead or Project Home → Correspondence → Submittals → Add Manually or Import From Excel; Submittal # → items, respondents, CC, files.
- Actions: Send Submittal Request To Originator; Send Submittal To Respondents; Copy for Resubmission; copy to other leads/projects.
- Correspondence Calendar uses originator item dates, design-review calculated dates, delivery dates, and respondent due/responded.
- TeamLink: respondents (and originator request) comment/status. If **more than one respondent**, item status is disabled in the portal so reviewers cannot overwrite each other.
- Mobile: Sage CM; TeamLink for externals. Mail-carrier send uses a printed submittal transmittal.

## Who uses it

Same correspondence roles as RFIs. Company role table matches RFIs (originator = provider of items; coordinator = your firm; respondent = reviewer).

## Prerequisites

- Originator, coordinator, and respondent companies on the project directory.
- Feature Settings → Correspondence: Submittal Types; Submittal Item Status.
- Default numbering for Submittals.
- Optional drawings in the drawing log to import as items.

## What the user fills out

### Header (Add / Edit / Excel import)

The dedicated Add Manually wizard page was not fully fetched; **Excel import columns plus Edit sections** are official.

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| ProjectNumber | Yes | Text | ≤ 25 chars |
| PrimeContractNumber | No | Text | ≤ 25 chars |
| SubmittalNumber | Yes | Text | ≤ 25 chars; UI prefilled from numbering |
| SubmittalDate / Issue Date | Yes | Date | Date the submittal was added |
| SubmittalSubject | Yes | Text | |
| SubmittalDescription / Overall Description | Yes | Text | Import required; Edit section Overall Description |
| Submittal Type | No | Lookup | Feature Settings; filter/sort |
| SubmittalOriginatorCompany | Yes | Text/lookup | Must exist before import |
| SubmittalOriginatorContact | No | Text | Must match display name if set |
| SubmittalCoordinatorCompany | Yes | Text/lookup | Typically GC |
| SubmittalCoordinatorContact | No | Text | Display name |
| Originator Due Date / Respondent Due Date | No | Date | Shown on Copy for Resubmission; header-level due dates |
| Use Response Workflow? / Type / Auto Notify | No | Same as RFI | Sequential vs Parallel |
| Status / responsible company | Edit | Enum | Originator or a respondent, or Closed |

### Submittal items (the records Sage saves per product/drawing)

Add / Import Items → Add Manually, Import Drawing, Edit List, Item Details, or bulk action.

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Item Number | Yes if item imported | Numeric | SubmittalItemNumber |
| Description | Yes if item imported | Text | |
| Quantity | Yes if item imported | Numeric | |
| Unit | Yes if item imported | Text | |
| Manufacturer | No | Text | Bulk: Manufacturer |
| Manufacturer Part # / Catalog Number | No | Text | SubmittalItemManufacturerCatalogNumber |
| UPC | No | Text | |
| Prime Contract # | No | Lookup | References |
| CPR / CO # | No | Lookup | |
| Subcontract # | No | Lookup | |
| SCO # | No | Lookup | |
| Drawing | No | Lookup | Or Import Drawing |
| Location | No | Text | |
| Spec. Section | No | Text | |
| Other | No | Text | |
| Due From Originator | No | Date | Alert |
| Rec'd From Originator | No | Date | Alert |
| Status Sent To Originator / Status Response Sent | No | Date | Alert |
| Required On Site Date | No | Date | Alert |
| Lead Time | No | Numeric | Calendar days |
| Design Review Time | No | Numeric | Calendar days |
| Internal Review Time | No | Numeric | Calendar days |
| Anticipated Delivery Date | No | Date | Coordinator/sub estimate |
| Estimated Delivery Date | No | Date | Sub/supplier estimate |
| Actual Delivery Date | No | Date | |
| Status | No | Lookup | Must match Feature Settings Submittal Item Status |
| Status Date | No | Date | If status changes and this is blank, Sage sets it to the update date |

**Calculated (saved/displayed, not typed):**

- Review - Return to Originator = Required On Site − Lead Time
- Review - Completion Date = Return to Originator − Design Review Time
- Review - Submission Date = Completion − Internal Review Time

Copy for Resubmission can copy material/design-review dates, anticipated/estimated delivery, and Link Related Files. Description, quantity, manufacturer, and references copy by default.

### Respondents (the records Sage saves for reviewers)

Same import pattern as RFIs (directory / add existing / add new).

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Company + Contact | Yes | Lookup | |
| Response Due Date | No | Date | On import and grid |
| Order Number | No | Number | Sequential workflow |
| Sent Date | No | Date | Coordinator sent items to this respondent |
| Responded Date / Response Date | No | Date | Auto from TeamLink |
| Response / company details | No | Text | **Submittal Respondent Details** page |

### CC Recipients

Email only; cannot respond online.

### Files

Same Linked Files / Grant Access / Email Upload rules as RFIs (48 files / 500 MB; drawings & specs / photos / other).

## What Sage CM saves

- Header record: submittal (number, issue date, subject, description, type, originator company/contact, coordinator company/contact, optional header dues, workflow, responsible party, closed).
- Line / child records: **submittal items** (identity, manufacturer, references, originator dates, lead/review times, delivery dates, status + status date); **respondents**; **CC**; resubmission link to prior submittal.
- System-generated values: item status date default; three design-review calculated dates; TeamLink responded date.
- Files / attachments: Linked Files on header (and items via drawings).
- Audit / workflow fields: Sequential/Parallel; Closed; portal item-status lock when multiple respondents.

## Statuses and lifecycle

Header: responsible company = originator or a respondent → Closed. Each item has its own status (admin list; e.g. approved/rejected — exact default status names not listed on fetched pages). Rejected items → Copy for Resubmission → new submittal. After responses, coordinator emails/prints responses back to the originator.

## Dates that drive alerts

See correspondence-overview.md table (originator trio, four design-review dates, three delivery dates, respondent due/responded).

## Relationships

- Upstream: specs, drawings, directory, item statuses, types.
- Downstream: transmittal wizards for groups of submittals; originator request email; respondent review; resubmission; procurement of approved materials (process, not an automatic PO).
- USIS: one `Submittal` with Procore-like ball-in-court users, revisions, QC checklist, AE stamp — not Sage item+respondent-company model.

## Reports and exports

- Submittal Items Request report/email (long-lead items).
- Email templates: request to originator; to respondent; originator with response.
- Log reports; detail templates.
- Excel import/export of the item grid.

## USIS / CM_Deploy mapping

| Sage concept | USIS table / API / page | Status |
|---|---|---|
| Submittal header | `submittals` | partial |
| Originator company/contact | `responsible_contractor`, `received_from`, `vendor_id` | stub |
| Coordinator | `created_by_user_id`, `assigned_reviewer_id` | stub |
| Respondents + dates + response | `approvers` JSON; `ae_action`; no company respondent table | stub |
| Submittal items | `submittal_line_items` (spec, description, manufacturer, model) | partial — missing Sage date/status/qty/unit |
| Item status / status date | header `status` only | none at item level |
| Revisions / QC / AI / stamp | `submittal_revisions`, checklist, holds | implemented — Sage-only |
| Transmit to AE | `POST .../transmit-to-ae` | partial vs Sage transmittal |
| Public token | `public_token` | implemented — not TeamLink |

## Sources

- https://help.sagecm.intacct.com/Content/Modules/Correspondence/Submittals/SubmittalsOverview.htm
- https://help.sagecm.intacct.com/Content/Modules/Correspondence/Submittals/SubmittalsEdit.htm
- https://help.sagecm.intacct.com/Content/Modules/Import/ImportSubmittals.htm
- https://help.sagecm.intacct.com/Content/Modules/Correspondence/Submittals/SubmittalsEmailingOriginatorRequest.htm
- https://help.sagecm.intacct.com/Content/Modules/Correspondence/Submittals/SubmittalsEmailingRespondents.htm
- https://help.sagecm.intacct.com/Content/Modules/Correspondence/Submittals/SubmittalsCopyResubmission.htm
- https://help.sagecm.intacct.com/Content/Administration/Settings/FeatureSettings/FeatureSettings_Correspondence_SubmittalTypes.htm
- Local: `backend/app/models/submittal.py`, `backend/app/api/submittals_bp.py`
