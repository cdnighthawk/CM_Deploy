# Project groups

Status: complete
Sage CM module: Projects (Project Team)
Official help: https://help.sagecm.intacct.com/Content/Modules/Projects/ProjectGroups/ProjectGroupsOverview.htm

## Purpose

Project groups are **optional named lists of directory contacts** used to blast email and to import respondents onto issues, journals, RFIs, and submittals. Examples: Subcontractors; Owner, CM, and Architect; Key Project Contacts.

## Where it lives

- Project Home → **Project groups** (Project Team)
- Functions: Add Project Groups; View/Edit Project Group Contacts
- Not on leads in the overview (project-scoped)
- Mobile / TeamLink: not listed as a standalone module

## Who uses it

- PMs build distribution lists after the directory is populated
- Correspondence authors import a group as respondents or companies involved
- Anyone using Email Form CC Recipients

## Prerequisites

- Companies are in Contact Management **and** the **project directory**
- Creating groups is optional

## What the user fills out

A dedicated “Add project group” field table was not published on the overview page. Confirmed user-facing data:

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Group name | Yes (implied) | Text | Examples in help: Subcontractors; Owner, CM Firm and Architect; Key Project Contacts. Exact label **not confirmed in help** — do not invent a Code or Description field |
| Contacts | Yes (implied) | Multi-select | Must already be on the project directory |

If you later find ProjectGroups_Add.htm, replace “implied” with the official labels.

### Features that import a project group

| Feature | Import target |
|---|---|
| Email Form | CC Recipients |
| Submittals | Respondents |
| RFIs | Respondents |
| Journals | Respondents |
| Issues | Companies Involved |

## What Sage CM saves

- Header record: named group on the project
- Line / child records: contact membership
- System-generated values (IDs, numbers, dates, totals): not confirmed in help
- Files / attachments: none
- Audit / workflow fields: none

## Statuses and lifecycle

No status. Edit membership as the directory changes. Deleting a directory contact’s effect on groups is **not confirmed in help**.

## Dates that drive alerts

None.

## Relationships

- Upstream: project directory
- Downstream: email CC, RFI/submittal/journal respondents, issue companies involved

## Reports and exports

None listed. Groups are an input picker, not a report.

## USIS / CM_Deploy mapping

| Sage concept | USIS table / API / page | Status |
|---|---|---|
| Project group header + members | none | none |
| RFI/submittal respondents | `rfi` / `submittal` models — individual assignees, no group import | none |
| Project members | `project_members` — users, not company-contact groups | none |

## Sources

- Official Sage help URLs used
  - https://help.sagecm.intacct.com/Content/Modules/Projects/ProjectGroups/ProjectGroupsOverview.htm
- Local files reviewed
  - `backend/app/models/project_member.py`
  - `backend/app/models/rfi.py`
  - `backend/app/models/submittal.py`
