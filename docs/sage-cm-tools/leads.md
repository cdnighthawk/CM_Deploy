# Leads

Status: complete
Sage CM module: Leads
Official help: https://help.sagecm.intacct.com/Content/Modules/Leads/ProjectLeadsOverview.htm

## Purpose

A lead is a **job opportunity** (the structure to be built), not the prospect’s company name. Estimating and sales use leads to track drawings, specs, ITB, estimates, limited correspondence, and photos **before award**. After award, the Lead to Project wizard converts the lead into a project.

## Where it lives

- Global nav: **Leads** list (List, Kanban, Insights, Active Lead Gantt, bid calendar)
- Record: **Lead Home** with a reduced menu vs projects
- Features available on leads (official list): Lead library (drawings, specifications); Lead team (employee access, lead directory); Preconstruction (ITB, estimates); Correspondence (journals, RFIs, submittals, transmittals); Documentation (photos); Quality control (checklists); Safety (site hazard assessments)
- Mobile: Lead Add Wizard (add); title and address (read/edit); lead directory (read/add/delete)
- TeamLink: **Show In Portal** must be on for bidders to see ITB details

## Who uses it

- Estimators and sales create and stage leads
- Bid captains set Bid Contact, bid due date/time, and Show In Portal
- Administrators configure lead stages and lead/project classifications
- Vendors view ITB/RFP in TeamLink when the lead is shown in portal

## Prerequisites

- Optional: lead/project classifications in Settings → Feature Settings → Lead / Project
- Optional: lead stages in the same settings area
- Optional: latest drawings and specifications in PDF
- Prospect company/contact can be new or existing
- Lead to Project wizard is allowed **only after the lead is awarded**

## What the user fills out

Add Lead Wizard fields, grouped by step.

### Step 1 — Prospect / client

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| New vs Existing Customer | Yes | Choice | New creates a company + contact; Existing picks a company |
| Company Name | Conditional | Text | Required for New Customer |
| First Name / Last Name | Conditional | Text | Required for New Customer |
| Display Name | Yes | Text | Auto First + Last; required |
| Email | Recommended | Email | |
| Default Tax Code | No | Lookup | Typically blank for US clients |
| Default Payment Terms | No | Lookup | Relevant later on prime invoices |
| New Contact / Existing Contact | No | Choice | Additional contact on the prospect |

### Step 2 — Lead number, title, currency, address

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Lead # | Yes | Text | Not auto-generated; max **25** alphanumeric. Changing it updates related documentation |
| Lead Title | Yes | Text | Structure description, not company name |
| Currency | Yes | Lookup | New currencies require Sage support + org ID |
| Bid Due Date and Time | No | Date/time | Copied onto ITB and RFP packages; appears on bid calendar |
| Show In Portal | No | Checkbox | Required for TeamLink ITB visibility; can set later on Lead Home |
| Sales Contact | No | Lookup | Internal stakeholder; used in alerts and workflow approvals |
| Bid Contact | No | Lookup | Bid captain; ITB emails and alerts |
| Project Manager | No | Lookup | Alerts and workflow |
| Est. Start Date | No | Date | Active Lead Gantt |
| Est. Finish Date | No | Date | Active Lead Gantt |
| Lead Address | No | Address | |

### Step 3 — Stage and classifications

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Stage Level | No | Lookup | User-defined stages (e.g. Reviewing → Plans → Bidding → Bid Submitted → Awarded). A lead can have multiple stage rows; the latest is current |
| Date (stage started) | No | Date | Defaults to today |
| Est. Close Date | No | Date | Typically same as bid date; used in trailing-90-day stage analysis |
| Estimated job Amount | No | Currency | Zero or blank if unknown |
| Classifications | No | Lookups | One option per classification defined in Feature Settings |

### Steps 4–8 — Library (optional)

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Drawing Set Date / Drawing Set Name | Conditional | Date / text | If drawings are uploaded |
| Drawing files | No | PDF (preferred), TIFF, DWG, DXF | Burst PDF → one drawing log per page |
| Drawing # / Title / Discipline | No | Text / lookup | Disciplines from Feature Settings → Drawings |
| Specification files | No | PDF, DOC, DOCX, other | One spec record per file |
| Specification # / Title | No | Text | |
| Photos / renderings | No | JPEG (preferred), TIFF, BMP | One photo record per file |

You can **Save & Finish** after step 2 and skip library/stage.

### Lead directory (after wizard)

Add prospect, client, architect, consultants. **Do not** add subcontractors or suppliers to the lead directory (implementation plan). Those firms go on the ITB instead.

## What Sage CM saves

- Header record: lead #, title, currency, address, bid due date/time, Show In Portal, sales/bid/PM contacts, est. start/finish, classifications
- Line / child records: lead stage history (level, start date, est. close, amount); lead directory companies/contacts; drawing log; specifications; photos; ITB; estimates
- System-generated values (IDs, numbers, dates, totals): Last Viewed on the list; stage analysis uses owner bid due **or** stage est. close in trailing 90 days
- Files / attachments: drawing, spec, and photo files linked to library records
- Audit / workflow fields: archive / reactivate; awarded flag for Lead to Project

## Statuses and lifecycle

User-defined **lead stages** (not a fixed Draft/Pending list). Typical path ends in **Awarded**, then Lead to Project. **Archive** / **Reactivate**. Closed/archived leads do not appear in calendars or the alerts list.

## Dates that drive alerts

- Owner **Bid Due Date** (and user is Bid, PM, or Sales Contact)
- Stage **Est. Close Date** (analytics, not listed as a separate alert row)
- Est. Start / Finish (Gantt, not listed as Home alerts)

## Relationships

- Upstream: Contact Management prospect
- Downstream: drawings, specs, ITB, estimates, RFP packages, Lead to Project → project (directory can copy)

## Reports and exports

- Export lead data or download lead files (overview function list)
- Bid calendar
- Lead stage analysis (trailing 90 days)
- Kanban by stage

## USIS / CM_Deploy mapping

USIS “leads” are BuildingConnected trade-scoped opportunities (`lead_estimates`), not Sage’s structure-first lead with a Lead to Project wizard.

| Sage concept | USIS table / API / page | Status |
|---|---|---|
| Lead header | `lead_estimates` / `backend/app/models/lead_estimate.py` | partial |
| Lead # / title / bid due | `number`, `name`, `due_at` | partial |
| CRM stages | `crm_stage` (`New Lead`, `Invited`, `Estimating`, `Submitted`, `Awarded`, `Lost`) | partial |
| Lead list / filters | `GET /api/v1/lead-estimates`; `construction/leads.html`; saved filters `crm.leads` | implemented |
| Lead detail | `construction/lead-detail.html` | implemented |
| Show In Portal / Lead to Project wizard | none | none |
| Lead directory (prospect/architect only) | none as Sage lead directory; project directory is separate | none |
| Golden State planroom ingest | `construction/lead-goldenstate-planroom.html` | implemented |

## Sources

- Official Sage help URLs used
  - https://help.sagecm.intacct.com/Content/Modules/Leads/ProjectLeadsOverview.htm
  - https://help.sagecm.intacct.com/Content/Modules/Leads/ProjectLeadsAddManually.htm
  - https://help.sagecm.intacct.com/Content/GettingStarted/ImplementationPlan_Est_01_Leads.htm
  - https://help.sagecm.intacct.com/Content/GettingStarted/Definitions.htm
  - https://help.sagecm.intacct.com/Content/Modules/AlertsCalendars/AlertsCalendar_All.htm
- Local files reviewed
  - `backend/app/models/lead_estimate.py`
  - `backend/app/api/v1.py` (`/lead-estimates`)
  - `W3CRM-v3.0-13_September_2025/gulp/src/construction/leads.html`
