# Contacts

Status: complete
Sage CM module: Contact Management
Official help: https://help.sagecm.intacct.com/Content/Modules/ContactManagement/Contacts/Contacts_Overview.htm

## Purpose

Contacts are the people (or named desks) under a company: estimators, PMs, owners, “Sales Department,” and your own employees. Sage requires first name, last name, and a company reference. Email is not required but is needed for correspondence, ITB/RFP, and TeamLink.

## Where it lives

- Global nav: **Contact Management** → **Contacts** tab
- Also: Company Profile → Contacts section → Add (including extra locations)
- Overview: Contact Management Insights → Contacts row → Add Manually
- Record form: Contact Details (General, Business Contact Info, Home Contact Info, Comments, TeamLink)
- Mobile: contacts support **read, edit, add**
- TeamLink: a contact can be marked External User and given a username/password

## Who uses it

- Office staff create contacts when entering companies
- Estimators mark **Bid Contact** so ITB and RFP pickers stay short
- PMs put contacts on RFIs, submittals, daily logs, COs, POs, and subcontracts
- Administrators enable TeamLink on external contacts
- HR/timekeepers treat contacts under *your* company as employees (Time & Expenses is the recommended employee form)

## Prerequisites

- Parent company must exist (or be created in the same add flow)
- First name, last name, and company are required to save
- Display Name defaults to First + Last
- TeamLink username must pass Validate User (unique)
- Titles can be configured (import help links Contact titles)

## What the user fills out

### Details tab — General

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Salutation | No | Lookup | Import prefixes: Mr., Mrs., Ms. |
| First Name | Yes | Text | Required with Last Name whenever a contact is included |
| Middle Name | No | Text | |
| Suffix | No | Text | |
| Display Name | Yes | Text | Auto from First + Last; user can override. Import: `ContactDisplayName` |
| Title | No | Lookup / text | Contact titles setting |
| Bid Contact | No | Checkbox | Filters ITB vendor list and RFP bidder list |

### Details tab — Business Contact Info

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Company | Yes | Lookup | Parent company |
| Email | Recommended | Email | Needed for Sage-sent correspondence and portal invites |
| Business Address 1 / 2, City, State, Postal Code, Country | No | Text | If omitted on import, Sage copies the company **shipping** address. `BusinessState` max 15 characters |
| Business Phone | No | Text | |
| Business Fax | No | Text | |
| Mobile Phone | No | Text | |

### Details tab — Home Contact Info (reference only)

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Home Address 1 / 2, City, State, Postal Code, Country | No | Text | Reference; Outlook sync updates all three address types |
| Home Phone / Home Fax | No | Text | |
| Other Address / Phone / Fax | No | Text | Third address type; Outlook sync |

### Comments tab

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Comments | No | Text | Free-form |

### TeamLink tab (external users)

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| External User | No | Checkbox | Enables portal login |
| Username | Conditional | Text | Required if External User; must be unique (Validate User) |
| New Password / Confirm Password | Conditional | Password | Set Password |
| TeamLink Role | Project-level | Lookup | Assigned later on the **project directory**, not on this tab (Owner / Architect / Vendor / custom) |

The TeamLink tab does not appear for companies configured for CPA/Sage Partner authorized users.

### Employee-only fields (import when company is your firm)

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Employee Id | No | Text | Do not include on client/vendor contact imports |
| Hire Date | No | Date | DD-MMM-YYYY, MM-DD-YYYY, or YYYY-MM-DD |
| Department | No | Text | |

Help recommends entering employees in **Time & Expenses** instead, because that form adds education, licenses, and payroll rates.

## What Sage CM saves

- Header record: contact under a company with display name, title, bid-contact flag, three address types, phones, email, comments
- Line / child records: none required; TeamLink credential is stored on the contact when External User is set
- System-generated values (IDs, numbers, dates, totals): Display Name if blank; Active/Inactive
- Files / attachments: not confirmed in help for the contact profile
- Audit / workflow fields: Active/Inactive; TeamLink lock/unlock and password update (related help)

## Statuses and lifecycle

Active → Inactive. Inactive contacts are omitted from directory and bidder pickers. No approval workflow.

## Dates that drive alerts

None on the contact. Bid Contact is a filter, not an alert date. To-dos and correspondence due dates reference the contact as assignee/respondent.

## Relationships

- Upstream: company; Excel import; Outlook via AccountingLink; Add Lead / Add Project New Contact; company multi-location Add
- Downstream: lead/project directory, project groups, ITB vendors, RFP bidders, RFIs/submittals/journals, POs/subcontracts, TeamLink, Time & Expenses employees

## Reports and exports

- Detail reports can print company shipping address, billing address, or **contact business address**
- Combined company/contact Excel import
- TeamLink login emails are sent from the project directory, not the contact list

## USIS / CM_Deploy mapping

| Sage concept | USIS table / API / page | Status |
|---|---|---|
| Contact header | `contacts` / `backend/app/models/company.py` (`Contact`) | implemented |
| Company FK, name, title, email, phone, mobile, primary, notes | `company_id`, `first_name`, `last_name`, `title`, `email`, `phone`, `mobile`, `is_primary`, `notes` | partial |
| Bid Contact, salutation, three address types, TeamLink user | none | none |
| Contacts API | Module guard lists `/api/v1/contacts` as CRM; no dedicated CRUD routes found. AI tools read contacts | stub |
| Directory contacts | Nested on `GET/POST /api/v1/projects/<id>/directory/companies` | partial |
| W3CRM contact UI | No dedicated contacts page; `construction/party.html` is a party/transaction stub | none |

## Sources

- Official Sage help URLs used
  - https://help.sagecm.intacct.com/Content/Modules/ContactManagement/Contacts/Contacts_Overview.htm
  - https://help.sagecm.intacct.com/Content/Modules/ContactManagement/Contacts/Contacts_AddManual.htm
  - https://help.sagecm.intacct.com/Content/Modules/Import/ImportCompanyContacts.htm
  - https://help.sagecm.intacct.com/Content/Modules/ContactManagement/Companies/Companies_AddMultipleLocations.htm
  - https://help.sagecm.intacct.com/Content/GettingStarted/Definitions.htm
- Local files reviewed
  - `backend/app/models/company.py`
  - `backend/app/api/_module_routes.py`
  - `backend/app/ai/tools/handlers.py`
  - `backend/app/api/_procurement_lookup_service.py`
