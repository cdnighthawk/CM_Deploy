# Issues

Status: complete
Sage CM module: Correspondence
Official help: https://help.sagecm.intacct.com/Content/Modules/Correspondence/Issues/IssuesOverview.htm

## Purpose

Issues provide chronological documentation of a project problem from occurrence through resolution, with companies involved and dated issue items. They are commonly attached as support when presenting a CPR or CO. They are not RFIs (questions/answers) and not USIS tracker issues (AI/punch/safety inbox).

## Where it lives

- Lead or Project Home → Correspondence → Issues → Actions → Add Manually; open Issue # for details.
- Correspondence Calendar / Alerts (Due date) while open.
- Email: Actions send issue details to companies involved (TeamLink/email template).
- Mobile: project correspondence; TeamLink for external companies involved if emailed with portal access.
- Estimator default role does **not** include Issues.

## Who uses it

PMs, supers, estimating/PMs, financial admins, admins create/edit/email/close. Companies Involved receive the issue details email; Coordinated By is typically your firm.

## Prerequisites

- Coordinated By and Companies Involved companies/contacts on the project directory.
- Optional issue types (and priorities if used) in Feature Settings → Correspondence.
- Default numbering for Issues.

Official add wizard: https://help.sagecm.intacct.com/Content/Modules/Correspondence/Issues/IssuesAddManually.htm. Word template bookmarks remain the print-merge names.

## What the user fills out

### Step 1 — General

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Project number | Yes | Context | Prefilled, editable |
| Issue Date | No | Date | Defaults today |
| Issue Number | No | Text | Auto from numbering; editable. Help text on this page mistakenly says “comply notice number” |
| Type | No | Lookup | Feature Settings → Correspondence |
| Subject | Yes | Text | Brief subject |
| Priority | Yes | Lookup | Required on add |
| Due Date | No | Date | Correspondence Calendar + Home Alerts |
| Description | No | Text | Optional on add |
| Coordinated By — Company | Yes | Lookup | Project directory; typically your firm |
| Coordinated By — Address Type | Yes | Lookup | |
| Coordinated By — Contact | No | Lookup | Print template From* bookmarks |

### References

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Prime contract # | No | Text/lookup | IssueRefPrimeContract |
| CPR / CO # | No | Text/lookup | IssueRefCO |
| Subcontract # | No | Text/lookup | IssueRefSubcontract |
| SCO # | No | Text/lookup | IssueRefSCO |
| Drawing | No | Text/lookup | IssueRefDrawing |
| Location | No | Text | IssueRefLocation |
| Spec. Section | No | Text | IssueRefSpecSection |
| Other | No | Text | IssueRefOther |

### Resolution / status / impact

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Resolution | No | Text | IssueResolution |
| Status | Yes to close | Enum | Open vs Closed (overview: Close an issue). Bookmark IssueStatus |
| Total Impact | No | Money/text | IssueTotalImpact — exact numeric vs text not confirmed in help |

### Step 2 — Companies Involved

Skip allowed. Must already exist in Contact Management and the project directory.

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Company + Contact | No (skip OK) | Multi-select | Search; Add or Add & Next. These are the people Sage emails (“Issue details to the companies involved”), not user assignees. |

### Step 3 — Issue items (manual)

Skip allowed.

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Item # | No | Text | Editable |
| Description | Yes | Text | Per item |
| Date | No | Date | Item date |
| Financial Impact | No | Money/text | On-form label; print bookmark ItemImpact |
| Reference | No | Text | On-form; print bookmark ItemRef |
| Add New Line | No | Action | More items |

### Step 3 — Import issue items (instead of or with manual)

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Import source | Yes if importing | Enum | Import Daily Log References; Journal; Permit; Punchlist; RFI; Submittal References |
| From / To Date | No | Date | Filter the import list |
| Search | No | Text | Keyword |
| Selected records | Yes if importing | Multi-select | Add / Add & Next |

### Step 4 — Files

Local upload (48 files / 500 MB, background + email) or Link Existing (Drawings & Specs, Photos, All Other Records). Skip and Finish allowed.

## What Sage CM saves

- Header record: issue (number, dates, subject, type, priority, description, due date, coordinated-by company/contact, references, resolution, status, total impact).
- Line / child records: Companies Involved (directory company + contact; print merges phone/email); Issue items (item #, description, date, financial impact, reference; can be imported from daily logs, journals, permits, punchlist, RFIs, submittals). Print template also has ItemDueDate — that label is **not** on the add-item form.
- System-generated values: Issue # from numbering; project snapshot fields on the print template.
- Files / attachments: Linked Files on the issue.
- Audit / workflow fields: Closed removes the issue from Correspondence Calendar and Alerts. No Sequential/Parallel response workflow (that is RFI/submittal).

## Statuses and lifecycle

Open → Closed (Close an issue). While open, Due Date alerts fire. Used as supporting documentation on CPR/CO (link via reference fields, not an automatic spawn).

## Dates that drive alerts

Issue Due Date. Item Due Date is stored and printed; it is not listed on the global Alerts correspondence table (only the issue Due date is). Item due may still appear on the issue detail/calendar — not confirmed in help.

## Relationships

- Upstream: project directory, issue types, numbering.
- Downstream: CPR/CO references; email to companies involved; log/detail reports.

## Reports and exports

- Default template: IssuesDetails.dot (upload category Issue Details).
- Print/share PDF or Word; Save to Linked Files; email template “Issue details to the companies involved.”
- Log reports for issues.

## USIS / CM_Deploy mapping

| Sage concept | USIS table / API / page | Status |
|---|---|---|
| Issue header | `tracker_issues` (title, description, severity, status, due_date, cost/schedule impact) | partial |
| Coordinated By company/contact | none (assignee is `assignee_id` user) | none |
| Companies Involved | none | none |
| Issue items chronology | `tracker_issue_events` (action/detail/payload) | partial |
| CPR/CO/drawing links | `linked_rfi_id`, `linked_change_order_id`, `drawing_id` | partial |
| Source types (AI, punch, safety) | `source_type` / `source_id` | implemented — Sage-only has no equivalent |
| Close / resolved | `resolved_at`, status | partial |

## Sources

- https://help.sagecm.intacct.com/Content/Modules/Correspondence/Issues/IssuesAddManually.htm
- https://help.sagecm.intacct.com/Content/Modules/Correspondence/Issues/IssuesOverview.htm
- https://help.sagecm.intacct.com/Content/Modules/Reporting/DetailReportTemplates/Correspondence/IssuesDetails.htm
- https://help.sagecm.intacct.com/Content/Modules/AlertsCalendars/AlertsCalendar_All.htm
- https://help.sagecm.intacct.com/Content/Administration/Settings/TemplatesReports/EmailTemplates/EmailTemplates_Module_Correspondence.htm
- Local: `backend/app/models/issue.py`
