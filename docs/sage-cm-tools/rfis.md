# RFIs (Request for Information)

Status: complete
Sage CM module: Correspondence
Official help: https://help.sagecm.intacct.com/Content/Modules/Correspondence/RFI/RFIOverview.htm

## Purpose

RFIs document significant questions that need review and can affect schedule or budget (for example, interpretation of a drawing detail or spec note). Sage stores **originator, coordinator, and respondent as project-directory companies and contacts**. The Main Respondent contact on add becomes a row in the Respondents grid — that child record (dates + response text) is what Sage actually saves for each answering firm. Journals are for lighter correspondence.

## Where it lives

- Lead or Project Home → Correspondence → RFIs → Actions → Add Manually; RFI # for details; Edit header; Import Company/Contact on Respondents.
- Actions → Send RFI To Respondents (email + TeamLink). Create Follow Up RFI links a new RFI.
- Correspondence Calendar / Alerts on respondent due/responded dates.
- TeamLink: preferred response. Off-portal email must be re-associated from Email.
- Mobile: Sage CM apps. TeamLink for external respondents.

## Who uses it

Internal coordinator (typically your firm) creates and sends. Originator is usually the subcontractor/supplier asking (or the GC). Respondents are architect/engineer/owner (or GC, depending on who is logged in). CC Recipients get email but cannot respond in the portal.

Example company roles (official table):

| User perspective | Originator | Coordinator | Respondent |
|---|---|---|---|
| Subcontractor | Subcontractor or supplier | Subcontractor | GC / architect / engineer / consultant / owner |
| General contractor | GC or subcontractor | GC | Architect / engineer / consultant / owner |
| Architect or engineer | GC / subcontractor / supplier | GC | Architect / engineer / consultant / owner |

## Prerequisites

- Originator, Coordinated By, and respondent companies/contacts on the project directory (or add-to-directory from the import dialog).
- Feature Settings → Correspondence: RFI Types, Reason options, Priority options.
- Default numbering for RFIs.
- Approved files to Grant Access for TeamLink.

## What the user fills out

### Step 1 — General Information (Add Manually)

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Lead / Project number | Yes | Context | Prefilled, editable |
| Issue Date | Yes | Date | Prefilled |
| RFI # | Yes | Text | Prefilled from numbering |
| RFI Type | No | Lookup | Filter/sort; admin list |
| Reason | No | Lookup | Admin list |
| Priority | No | Lookup | Admin list |
| Subject | Yes | Text | Brief subject |
| Request | Yes | Text | The question |
| Suggestion By Originator or Coordinator | No | Text | Optional proposed answer |

### Originator (company Sage stores)

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Originator Company | Yes | Lookup | Directory. Typically sub/supplier providing docs/samples (help text on add) |
| Originator Address Type | Yes | Lookup | With Company |
| Originator Contact | No | Lookup | Recommended |

### Coordinated By (company Sage stores)

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Coordinated By Company | Yes | Lookup | Typically your firm |
| Coordinated By Address Type | Yes | Lookup | |
| Coordinated By Contact | No | Lookup | Receives portal alerts when respondents post |

### Main Respondent (creates the first Respondents child)

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Main Respondent Company | Yes | Lookup | Party responsible for answering |
| Main Respondent Address Type | Yes | Lookup | |
| Main Respondent Contact | Conditional | Lookup | **If you do not select a contact, the company is not added to the RFI Respondents section** |

### References

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Prime contract # | No | Lookup/text | Magnifying glass to pick existing |
| CPR / CO # | No | Lookup/text | |
| Subcontract # | No | Lookup/text | |
| SCO # | No | Lookup/text | |
| Drawing | No | Lookup/text | |
| Location | No | Text | |
| Spec. Section | No | Text | |
| Other | No | Text | |

### Response Workflow (header)

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Use Response Workflow? | No | Checkbox | |
| Workflow Type | If workflow on | Enum | Sequential (must also Auto Notify): next respondent emailed after current posts in TeamLink. Parallel: all respondents emailed at once |
| Auto Notify Respondents | Required if Sequential | Checkbox | Parallel: optional notify remaining respondents + coordinator on new posts |

### Schedule and Financial Impact

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Check Impact To Be Determined | Default on | Checkbox | Default when creating |
| Schedule Impact | No | Checkbox + Work Days | Clear TBD, then set days |
| Financial Impact | No | Checkbox + Amount | Clear TBD, then set amount |

### Status (Edit header — not the add wizard)

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Responsible Company | No | Enum | Originator, coordinator, or a main respondent — must be **manually selected and saved** to show on the RFIs listing |
| Closed | Yes to leave calendar | Status | After all responses; blocks TeamLink response edits |

### Respondents grid (the records Sage saves for answers)

Add via Import Company / Contact (must exist in Contact Management and project directory, or add existing/new company to directory from the dialog).

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Company + Contact | Yes | Lookup | Multi-select from directory |
| Response Due Date | No | Date | Can set on import; alert date |
| Order Number | No | Number | Sequence for Sequential workflow; inline Edit |
| Sent Date | No | Date | When sent to this respondent |
| Responded Date | No | Date | Auto when they respond in TeamLink |
| Response text / company details | No | Text | **RFI Respondent Details** form — this is the official answer storage per company |

### CC Recipients

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Company + Contact | No | Lookup | Email only; **cannot respond online** |

### Files (Add step 2 / Edit Linked Files)

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Local upload | No | Files | Up to 48 files / 500 MB per batch; background upload + email confirmation |
| Link Existing | No | Drawings & Specs / Photos / All Other Records | Same lead/project only |
| Grant Access | On send | Checkbox | TeamLink; Linked Files are **not** email attachments |
| Email Upload Attachments | On send | Files | Email only; **not** added to Linked Files |

## What Sage CM saves

- Header record: RFI (number, issue date, type, reason, priority, subject, request, suggestion, originator company/contact/address type, coordinator company/contact/address type, references, impact flags/days/amount, response workflow type, auto-notify, responsible company, closed).
- Line / child records: **Respondents** (company, contact, order, sent, due, responded, response body); **CC Recipients**; TeamLink comments; follow-up RFI link.
- System-generated values: RFI #; default TBD impact; Responded Date from portal; listing “ball in court” only after Responsible Company is saved.
- Files / attachments: Linked Files; email-only uploads excluded.
- Audit / workflow fields: Sequential/Parallel notify; Closed locks portal edits.

## Statuses and lifecycle

Open (responsible company may be originator / coordinator / a respondent) → Closed. Create Follow Up RFI for a linked successor. Unofficial email replies must be filed back onto the RFI.

## Dates that drive alerts

RFI respondent Response due date and Date responded. Header Issue Date is not on the global alerts table.

## Relationships

- Upstream: directory, RFI type/reason/priority, numbering, drawings/specs files.
- Downstream: follow-up RFI; CPR/CO via references/impact; TeamLink; Email re-association.
- USIS difference: USIS `RfiAssignee` / `RfiDistribution` are **users**, plus official reply pointer — not Sage company respondent rows.

## Reports and exports

- RFI detail Word templates; log reports.
- Email: RFI to respondent response request; RFI to originator with response.
- Print vs TeamLink: portal preferred.

## USIS / CM_Deploy mapping

| Sage concept | USIS table / API / page | Status |
|---|---|---|
| RFI header | `rfis` (number, subject, question, status, due_at, cost/schedule impact) | partial |
| Originator company/contact | `received_from_user_id`, `responsible_contractor_company_id` | stub — user/company, not Sage trio |
| Coordinator | `rfi_manager_user_id`, `created_by_user_id` | partial |
| Respondents (company + dates + response) | `rfi_assignees` (user, ball_in_court, responded_at); `rfi_replies` | partial — users/thread, not directory companies |
| CC Recipients | `rfi_distribution` | partial |
| Official response | `official_response` / `official_response_reply_id` | implemented |
| Sequential/Parallel TeamLink workflow | none | none |
| Custom fields / revisions | `rfi_custom_field_*`, `rfi_revisions` | implemented — Procore-oriented |
| Pages | `construction/rfi-create.html`, rfi-detail | partial |

## Sources

- https://help.sagecm.intacct.com/Content/Modules/Correspondence/RFI/RFIOverview.htm
- https://help.sagecm.intacct.com/Content/Modules/Correspondence/RFI/RFIAddManually.htm
- https://help.sagecm.intacct.com/Content/Modules/Correspondence/RFI/RFIEdit.htm
- https://help.sagecm.intacct.com/Content/Modules/Correspondence/RFI/RFIEmailingRespondents.htm
- https://help.sagecm.intacct.com/Content/Modules/Correspondence/RFI/RFIUseResponseWorkflow.htm
- https://help.sagecm.intacct.com/Content/Administration/Settings/FeatureSettings/FeatureSettings_Correspondence_RFITypes.htm
- https://help.sagecm.intacct.com/Content/Modules/AlertsCalendars/AlertsCalendar_All.htm
- Local: `backend/app/models/rfi.py`, `backend/app/api/_rfi_service.py`
