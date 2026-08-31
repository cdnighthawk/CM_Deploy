# Company settings

Status: complete
Sage CM module: Administration
Official help: https://help.sagecm.intacct.com/Content/Administration/Settings/SettingsHome/SettingsHome.htm

## Purpose

Company Settings hold tenant-wide identity, numbering, security, and global calculation/locking rules. They are not Feature Settings (per-module pick lists) and not Workflow rules. Changing locking/workflow-related global options after go-live is officially discouraged.

## Where it lives

- Settings (gear) → Settings home, then Company Settings: Profile, Global Settings, Numbering, Security (and Users — see users-security-roles.md).
- Settings home also shows Org/Company ID, license count, storage, and AccountingLink/RSMeans add-ons.
- Admin only. Not on Project Home. Not TeamLink.

## Who uses it

Administrators. Company name changes require Sage Customer Support. Extra licenses: billing@SageConstructionManagement.com. Extra storage: Sage CRE Sales.

## Prerequisites

Administrator login. Contact Management should be reviewed before requesting an org name change (name must be unique across active and inactive companies).

## What the user fills out

### Settings home (read + jump-off)

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| User name / security role | System | Display | Opens profile; Change Password |
| Company ID / Org. ID | System | Text | Assigned by Sage; cannot edit |
| Company name | Support | Text | Edit opens Profile; misspelling → Support |
| Licenses | Billing | Count | Caps Standard + T&E users |
| Storage | Sales | Quota | Linked files across features |
| Add-ons | Sales | Flags | AccountingLink (QBD, QBO, Sage 50 Canada, Xero); RSMeans (US/CA) |

### Profile

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Org. Name | Yes | Text | Also an active Contact Management company |
| Company logo | No | File | Appears on detail and log reports |
| Address, phone, fax, website | Yes/No | Address | Copied to the Contact Management company record |
| OCR Email prefix | No | Text | Prefix for `…@invoices.corecon.com` (example in help); vendor PDFs → Files Ready for Processing / Create Bills from PDF |
| Company Type | Yes | Lookup | Changes the word “Customer” on prime/CPR/CO/invoice forms (GC vs sub vs owner) |
| Number of employees | No | Number | Reference only |
| Annual revenue | No | Money | Reference only |
| Accounting System | No | Lookup | AccountingLink target; some values are planning-only |

### Global Settings

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Default currency | Yes | Currency | Default on new lead/project; changeable later |
| Fiscal year start | Yes | Month/day | Filters current vs prior year financial dashboards |
| Transaction locking | Yes | Enum | No locking; Lock transactions (any user locks, admin unlocks); Lock exported transactions (AccountingLink auto-lock; admin temporary unlock) |
| Workflow vs lock | System | Rule | In-progress/completed transaction workflow locks the record; abandon to edit; workflow overrides locking settings |
| Locale | Yes | Enum | English (United States) vs English (United Kingdom) |
| Estimate rounding | Yes | Decimals | Typically 2; up to 4 on unit prices |
| Transaction rounding | Yes | Decimals | Same; set both to 2 for Sage 100/300 AccountingLink |
| Rounding method | System | | Banker’s rounding (IEEE 754 nearest even) |

Official help: configure locking and workflow during initial setup and do not switch types later.

### Numbering

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Default numbering format | Yes per feature family | Enum | 3-digit project-dependent; Project #–3 digit; 5-digit project-dependent; Project #–5 digit; 5-digit globally unique; 7-digit globally unique; 3-digit prime-dependent; Prime Contract #–3 digit |
| Features using the format | System | List | Contracts/changes (primes, CPRs, invoices, allowances, COs); Procurement (POs, PO COs, subs, SCOs); Correspondence (Issues, RFIs, Transmittals, Journals, Submittals); Documentation (Meetings, WOs); QC/Safety (comply, punch, tests, permits, incidents, SHA) |
| Estimate line numbering | Yes | Enum | Unique across estimate vs unique across WBS |

### Security

Documented in users-security-roles.md (password policy, MFA, roles).

## What Sage CM saves

- Header record: company/org profile; global flags; numbering choices; security policy.
- Line / child records: none beyond role trees (Security).
- System-generated values: Org. ID; inbound OCR mailbox; logo on reports.
- Files / attachments: company logo.
- Audit / workflow fields: locking + workflow type interaction; exported transaction lock.

## Statuses and lifecycle

One tenant. Name change is a support process. Locking/workflow type should be treated as immutable after go-live.

## Dates that drive alerts

Fiscal year start (dashboard filters), not an alert. MFA start date lives under Security.

## Relationships

- Upstream: license/storage contracts, Contact Management company.
- Downstream: every numbered record; report logos; AccountingLink; Feature Settings lists; Users.

## Reports and exports

Logo on log and detail reports. No “company settings report.”

## USIS / CM_Deploy mapping

| Sage concept | USIS table / API / page | Status |
|---|---|---|
| Company / org profile | `companies` (directory companies, not a tenant settings row) | stub |
| Default currency / fiscal year / rounding | none | none |
| Transaction locking | none | none |
| Default numbering | per-table sequences (`rfis.number`, `submittals.number`) | partial — no format picker |
| OCR bill inbox | none | none |
| Tenant config | `backend/app/config.py`, env secrets | implemented — different shape |

## Sources

- https://help.sagecm.intacct.com/Content/Administration/Settings/SettingsHome/SettingsHome.htm
- https://help.sagecm.intacct.com/Content/Administration/Settings/CompanySettings/CompanySettings_Profile.htm
- https://help.sagecm.intacct.com/Content/Administration/Settings/CompanySettings/CompanySettings_Global.htm
- https://help.sagecm.intacct.com/Content/Administration/Settings/CompanySettings/CompanySettings_DefaultNumbering.htm
- https://help.sagecm.intacct.com/Content/Administration/Settings/CompanySettings/CompanySettings_Security.htm
- Local: `backend/app/config.py`, `backend/app/models/auth.py`
