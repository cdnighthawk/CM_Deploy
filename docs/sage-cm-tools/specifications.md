# Specifications

Status: complete
Sage CM module: Drawings / Specifications / ITB (Lead or Project Library)
Official help: https://help.sagecm.intacct.com/Content/GettingStarted/Definitions.htm

## Purpose

Specifications are the written quality and product requirements that accompany drawings. Sage stores one **specification record per uploaded file** (PDF preferred; DOC/DOCX allowed) on the lead or project library so they can be burst-reviewed, numbered, and linked to ITB/RFP.

A dedicated “Specifications overview” page was not found in official help (implementation plans link “View” from wizards). Fields below are from the Add Lead / Add Project wizard, file-management pages, ITB linking, and February 2026 release notes.

## Where it lives

- Lead or Project Home → **Specifications** (Project Library / Lead Library)
- Also: Add Lead / Add Project wizard steps 6–7
- Linked Files on ITB, RFP, and other records via **Drawings & Specs**
- Mobile: specifications **read**
- TeamLink: default roles grant **All** specifications (Owner/Architect/Vendor)

## Who uses it

- Estimators and PMs upload spec books
- Bid captains link specs to ITB
- Architects/owners view in TeamLink
- PMs optionally show Prime # / Prime Subject columns (Feb 2026)

## Prerequisites

- Lead or project exists
- Files: PDF recommended; DOC, DOCX, or other allowed
- Same 500 MB / special-character filename rules as other uploads
- Background upload option (“Process in background”) during wizards

## What the user fills out

### Upload / wizard

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Specification files | Yes to create records | PDF, DOC, DOCX, other | Drag/drop or File Explorer; one record per file |
| Specification # | No | Text | Editable after upload |
| Title | No | Text | Editable after upload |

### List / optional columns (Feb 2026)

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Prime # | No | Display | Optional column on project Specifications page |
| Prime Subject | No | Display | Optional column; ties the spec row to a prime contract |

Whether Prime # is editable on the spec form or only a list column is **not confirmed in help**.

### Linking (not new metadata)

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Link Existing → Drawings & Specs | No | Picker | Same lead/project only |
| Feature Name filter | No | Lookup | |

Do **not** invent CSI section, revision, or discipline fields for specs. Those are confirmed for **drawings**, not for specifications, unless a future help page lists them.

## What Sage CM saves

- Header record: specification #, title, linked file; optional prime display fields
- Line / child records: none described (no revision model like drawings in help)
- System-generated values (IDs, numbers, dates, totals): one record per uploaded file
- Files / attachments: the spec file; Grant Access for TeamLink
- Audit / workflow fields: not confirmed in help

## Statuses and lifecycle

No spec status workflow in help. Replace/update is done by uploading/linking files; a formal revision chain is **not confirmed in help**.

## Dates that drive alerts

None listed on the alerts table.

## Relationships

- Upstream: lead/project; optional prime contract (display)
- Downstream: ITB, RFP, file viewer/annotations

## Reports and exports

- Download via All Project Linked Files
- Link into ITB/RFP
- No spec Excel import page found (drawing log import is separate)

## USIS / CM_Deploy mapping

| Sage concept | USIS table / API / page | Status |
|---|---|---|
| Spec file as document | `documents.document_type = specification` | partial |
| Spec section lookup (CSI code/title + optional PDF) | `rfi_spec_sections` / `backend/app/models/rfi_lookups.py` | partial |
| Spec book import | `POST /api/v1/projects/<id>/spec-book/import`, `spec-sections/from-catalog` | partial |
| Spec viewer | `construction/specs-viewer.html` | implemented |
| Sage spec log (#, title, prime columns) | none as a dedicated spec log | stub |

## Sources

- Official Sage help URLs used
  - https://help.sagecm.intacct.com/Content/GettingStarted/Definitions.htm
  - https://help.sagecm.intacct.com/Content/Modules/Leads/ProjectLeadsAddManually.htm
  - https://help.sagecm.intacct.com/Content/Modules/Projects/ProjectAddManually.htm
  - https://help.sagecm.intacct.com/Content/GettingStarted/ImplementationPlan_Est_02_Drawings_Specs.htm
  - https://help.sagecm.intacct.com/Content/Modules/DwgsSpecsITB/InvitationToBid/InvitationToBid_LinkDrawingsSpecs.htm
  - https://help.sagecm.intacct.com/Content/ReleaseNotes/February-2026/February-2026-WhatsNew.htm
- Local files reviewed
  - `backend/app/models/document.py`
  - `backend/app/models/rfi_lookups.py`
  - `W3CRM-v3.0-13_September_2025/gulp/src/construction/specs-viewer.html`
