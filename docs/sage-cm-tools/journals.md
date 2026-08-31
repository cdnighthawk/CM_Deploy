# Journals

Status: complete
Sage CM module: Correspondence
Official help: https://help.sagecm.intacct.com/Content/Modules/Correspondence/Journals/JournalsOverview.htm

## Purpose

Journals record everyday project correspondence (letters, emails, faxes, notes, phone calls) with reminder and due dates so follow-up is not trapped in personal inboxes. Emailing a journal includes a TeamLink link so the respondent comments on the record; the From contact is alerted. Sage recommends journals for routine questions and RFIs for schedule/budget-significant requests.

## Where it lives

- Lead or Project Home → Correspondence → Journals → Actions → Add Manually; Journal # for details.
- Correspondence Calendar / Alerts (Reminder date; respondent due/responded).
- Actions → Send Journal (email + TeamLink); Print or share; Create Follow Up Journal.
- TeamLink: preferred response channel. Standard-email replies must be moved from Email and re-associated.
- Mobile: correspondence; Estimators have Journals (unlike Issues).

## Who uses it

Internal staff with Journals access (all default roles except Time & Expense Field User). From = originator (often your firm). Respondent = To company/contact on the directory. CC list on send cannot replace the Respondent record.

## Prerequisites

- From and Respondent companies/contacts on the lead or project directory.
- Optional journal types in Feature Settings → Correspondence.
- Default numbering for Journals.
- Email template: Journal.

Official add wizard: https://help.sagecm.intacct.com/Content/Modules/Correspondence/Journals/JournalsAddManually.htm. Print bookmarks (Body vs on-form Message) are listed where they differ.

## What the user fills out

### Step 1 — General

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Lead / Project number | Yes | Context | Prefilled, editable |
| Issue Date | Yes | Date | Prefilled |
| Journal # | Yes | Text | Prefilled from numbering |
| Journal Type | Yes | Lookup | Letter, Fax, Email, Note, etc. Feature Settings → Correspondence → Journal Types |
| Reminder Date | No | Date | Correspondence calendar + alert |
| Due Date | No | Date | Correspondence calendar + alert |
| Issue Time | No | Time | Optional |
| Subject | Yes | Text | Brief subject |
| Message | Yes | Text | On-form label. Word template bookmark is Body |
| From Company | Yes | Lookup | Project directory; typically your firm, prefilled |
| From Address Type | Yes | Lookup | With Company |
| From Contact | No | Lookup | Receives TeamLink alert when respondents comment |

### References (Step 1)

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

### Step 2 — Respondents (companies/contacts Sage stores)

Optional but recommended. Skip allowed. Companies/contacts must already be in Contact Management and the project directory.

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Company + Contact | No (skip OK) | Multi-select | Search + Add or Add & Next |

Print template To* bookmarks (ToCompany, ToContact, address/phones/email) merge from these respondent rows. Alerts: Journal respondents → Response due date; Date responded. Order Number / Sent Date on a journal respondent grid were **not** listed on the add page (those labels are confirmed on RFI/submittal respondent grids only).

### Status / follow-up

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Closed | Yes to leave calendar | Checkbox/status | Edit journal and mark Closed after response |
| Follow Up Journal | No | Action | Creates a linked new journal |

### Email send (not all persisted on the journal header)

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Email template | Yes | Lookup | Journal template |
| Recipients / CC | Yes / No | Directory | CC is for that send |
| Grant Access on Linked Files | No | Checkbox | TeamLink file share; not email attachments |
| Email Upload Attachments | No | Files | Attached to email only; not added to Linked Files |

### Files

Linked Files after create (upload / link existing). Print can Save PDF/DOC to Linked Files with Show In Portal default on.

## What Sage CM saves

- Header record: journal (number, type, issue date/time, subject, message/body, reminder date, due date, From company/contact/address type, references, open/closed).
- Line / child records: TeamLink comments/responses; optional follow-up journal link; email message log for the send.
- System-generated values: Journal #; alert rows; inbound portal notification to From.
- Files / attachments: Linked Files; email-only uploads are not on the record.
- Audit / workflow fields: Closed flag; no Contract Admin value workflow.

## Statuses and lifecycle

Open → Closed. Only open journals stay on Correspondence Calendar and Alerts. Follow-up creates a second linked journal.

## Dates that drive alerts

Reminder Date (journal). Respondent Response due date and Date responded.

## Relationships

- Upstream: directory, journal types, numbering.
- Downstream: TeamLink comments; follow-up journal; Email module re-association for off-portal replies.
- Sibling: RFI for formal Q&A with schedule/cost impact.

## Reports and exports

- Journals Word template (From/To + general bookmarks).
- Print PDF / DOC / DOCX; Save to Linked Files; Email Journal template.
- Log reports.

## USIS / CM_Deploy mapping

| Sage concept | USIS table / API / page | Status |
|---|---|---|
| Journal header | none | none |
| From / Respondent companies | none | none |
| Graph mail archive | `correspondence_items` (subject, from, sent_at, files) | implemented — ingest, not Sage journals |
| Follow-up / closed calendar | none | none |

## Sources

- https://help.sagecm.intacct.com/Content/Modules/Correspondence/Journals/JournalsAddManually.htm
- https://help.sagecm.intacct.com/Content/Modules/Correspondence/Journals/JournalsOverview.htm
- https://help.sagecm.intacct.com/Content/Modules/Correspondence/Journals/JournalsEmailing.htm
- https://help.sagecm.intacct.com/Content/Modules/Correspondence/Journals/JournalsPrinting.htm
- https://help.sagecm.intacct.com/Content/Modules/Reporting/DetailReportTemplates/Correspondence/Journals.htm
- https://help.sagecm.intacct.com/Content/Modules/AlertsCalendars/AlertsCalendar_All.htm
- Local: `backend/app/models/correspondence.py`
