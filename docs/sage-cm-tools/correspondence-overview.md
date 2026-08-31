# Correspondence overview

Status: complete
Sage CM module: Correspondence
Official help: https://help.sagecm.intacct.com/Content/Modules/Correspondence/ResourceCenter_Correspondence.htm

## Purpose

Correspondence Overview is the project (or lead) landing page for Issues, Journals, RFIs, Submittals, and the Correspondence Calendar. Transmittals are a formal send package (often launched from Documentation on Project Home, and via wizards from drawings/submittals) but are part of the same correspondence family in settings, numbering, email templates, and alerts. The overview is a stats/calendar hub, not a single record type.

## Where it lives

- Lead or Project Home → Correspondence section → Correspondence Overview; also Issues, Journals, RFIs, Submittals.
- Transmittals: Project Home → Documentation → Transmittals (official add page path), also listed under Correspondence in the resource center and default numbering.
- Correspondence Calendar (feature calendar) and global Alerts list/calendar.
- TeamLink: external originators/respondents comment on journals, RFIs, and submittals via portal links on outbound email.
- Mobile: correspondence records can be viewed/acted per mobile app capabilities (see mobile overview); TeamLink is the external channel.

## Who uses it

Default roles with Correspondence (Issues, Journals, RFI, Submittals, Transmittals, calendar): Admin, Estimator (journals/RFI/submittals/transmittals — not Issues), Estimating/PM, PM, Superintendent, Financial Admin. Time & Expense Field User has no correspondence module access.

## Prerequisites

- Companies/contacts in Contact Management and on the lead/project directory before they can be referenced as From, Originator, Coordinator, Respondent, or Companies Involved.
- Feature Settings → Correspondence lists (types, reasons, priorities, item statuses, transmitted-for, senders).
- Company Settings → Numbering for Issues, RFIs, Transmittals, Journals, Submittals.
- Email templates (Correspondence module) and TeamLink if external response is required.

## What the user fills out

The overview itself has no create header. Users filter the calendar and open child tools.

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Lead / Project | Yes | Context | From Quick Select / Home |
| Calendar feature filters | No | Checkboxes | Clear features you do not want on the Correspondence Calendar |
| Open-items email | No | Action | Email open items to external team members (shared correspondence function) |

Child create fields are documented in issues.md, journals.md, rfis.md, submittals.md, transmittals.md.

**Sage persists people as company + contact roles, not as USIS-style user assignees:**

| Tool | Originator / From | Coordinator | Respondent / To | Other people records |
|---|---|---|---|---|
| Journal | From company + contact | — | Respondent (To) company + contact | CC via email send |
| Issue | Coordinated By (From) company + contact | Coordinated By | Companies Involved (company + contact rows) | Issue item owners are not a separate user table |
| RFI | Originator company + contact + address type | Coordinated By company + contact | Main Respondent on add (contact required to create a Respondents row); additional Respondents with Order #, Sent, Due, Responded, response text | CC Recipients (email only, cannot respond in portal) |
| Submittal | Originator company + contact | Coordinated By | Respondents (same date/response child as RFI) | CC Recipients; originator also has item-level due/received/status-sent dates |
| Transmittal | From company + contact + address type | — | To company + contact + address type | Items + Transmitted For; no TeamLink respondent thread |

## What Sage CM saves

- Header record: none for the overview.
- Line / child records: the five correspondence tools; linked files; TeamLink comments stored on the journal/RFI/submittal respondent side.
- System-generated values: default numbers per Numbering settings; calendar/alert rows from each tool’s dates (see Dates).
- Files / attachments: per-record Linked Files (upload, link drawings/specs/photos/other). Email Upload Attachments are not added to Linked Files.
- Audit / workflow fields: Open vs Closed on journals/RFIs/submittals/issues so only open items remain on the calendar. RFI/submittal Response Workflow (Sequential/Parallel, Auto Notify) is per record, not the Contract Admin value workflow.

## Statuses and lifecycle

Overview is always live. Child records: mark Closed after responses so they drop off Correspondence Calendar and Alerts. Follow-up RFI/Journal actions create a linked new record.

## Dates that drive alerts

Official Correspondence alert dates (Alerts calendar):

| Feature | Date |
|---|---|
| Issues | Due date |
| Journals | Reminder date |
| Journal respondents | Response due date; Date responded |
| RFI respondents | Response due date; Date responded |
| Submittal items (originator) | Due from originator; Received from originator; Status response sent back |
| Submittal items (design review) | Review planned submission; review completion; return to originator; material required on site |
| Submittal items (delivery) | Anticipated / Estimated / Actual delivery |
| Submittal respondents | Respondent due date; Date responded |
| Transmittals | Due date |

## Relationships

- Upstream: project directory, Feature Settings Correspondence, numbering, email templates, TeamLink.
- Downstream: CPR/CO support (especially Issues); submittal transmittals; Create Follow Up RFI/Journal; Reports log + detail Word templates.

## Reports and exports

- Standard log reports for correspondence features.
- Detail report templates (RFI, submittal, journal, issue, transmittal Word mail-merge).
- Email templates: Journal; Issue details to companies involved; RFI to respondent / originator with response; Submittal request to originator / to respondent / originator with response; Transmittal.

## USIS / CM_Deploy mapping

| Sage concept | USIS table / API / page | Status |
|---|---|---|
| Correspondence overview / calendar | none | none |
| Graph mail archive (not Sage journals) | `correspondence_sources`, `correspondence_items`; `backend/app/api/correspondence_bp.py` | implemented — different product shape |
| RFIs | `rfis` + assignees/replies | partial (Procore-style users, not Sage originator/respondent companies) |
| Submittals | `submittals` + items/revisions | partial |
| Issues | `tracker_issues` | partial — unified tracker, not Sage issue items |
| Journals / transmittals | none | none |

## Sources

- https://help.sagecm.intacct.com/Content/Modules/Correspondence/ResourceCenter_Correspondence.htm
- https://help.sagecm.intacct.com/Content/GettingStarted/ImplementationPlan_FieldPM_02_Correspondence.htm
- https://help.sagecm.intacct.com/Content/Modules/AlertsCalendars/AlertsCalendar_All.htm
- https://help.sagecm.intacct.com/Content/Administration/Settings/TemplatesReports/EmailTemplates/EmailTemplates_Module_Correspondence.htm
- https://help.sagecm.intacct.com/Content/Administration/Settings/CompanySettings/CompanySettings_DefaultNumbering.htm
- Local: `backend/app/models/correspondence.py`, `backend/app/api/_correspondence_service.py`
