# DocuSign

Status: complete
Sage CM module: Companion products
Official help: https://help.sagecm.intacct.com/Content/IntegrationsPublicAPIs/eSignatures/DocuSign/StartESignProcess.htm

## Purpose

Sage CM **e-Sign** sends a **linked file** (usually a report PDF saved onto a contract/procurement record) through **DocuSign**. Users pick Parallel vs Sequential signing, recipients (Signer or Carbon Copy), optional DocuSign templates and extra authentication, then track yellow/green/red status on the file’s three-dot **E-Sign** menu.

## Where it lives

- **Not** a Documentation or QC list. It is an action on **Linked Files** of supported records.
- Confirmed record types you open, then Reports → Save PDF to Linked Files → file menu → **E-Sign**:
  - Estimates
  - Prime Contracts
  - CPRs
  - COs
  - Prime Invoices
  - POs
  - Bills
  - Subcontracts
  - SCOs
  - Sub Invoices
- **Before you begin:** Enable and configure DocuSign integration (separate admin topic).
- **Mobile:** e-Sign is **not** on the iOS feature matrix.

## Who uses it

- PMs/contract admins initiate envelopes from financial/contract records.
- Signers are directory **company + contact**; Sage **auto-populates** by document type (example: prime invoices → prime contact, architect, owner contact).
- Carbon Copy recipients view/download/print only.
- Extra SMS/phone authentication: typically **Enterprise DocuSign**, often a per-use fee.

## Prerequisites

- DocuSign integration enabled and configured.
- Record of a supported type; ability to run Reports and **Save PDF to Linked Files**.
- Signer name + email; directory company/contact for auto-fill.
- Optional DocuSign template in the connected DocuSign account.

## What the user fills out

### Save PDF to Linked Files (before e-Sign)

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Reports option | Yes | Dropdown | Record-specific report |
| Format | If applicable | Dropdown | |
| Template | Yes | Report template | |
| Export Option | Yes | Dropdown | **Save PDF to Linked Files** |

### Initiate Esign (file → three-dot → E-Sign)

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Initiate Esign | Yes | Action | E-sign and Document Info section |
| Use DocuSign Template(s) | No | Checkbox + dropdown | Connected DocuSign templates |
| Set Signing Order | For sequential | Checkbox | Parallel vs Sequential |
| Signing order mode | Yes | Choice | **Parallel** (all order 1) or **Sequential** (1, 2, 3…; same recipient can appear more than once) |
| Company and Contact | Yes | Directory | Auto-populated by document type; user may change |
| Name | No (update) | Text | Per signer |
| Email address | Yes | Email | |
| Recipient Type | Yes | Enum | **Signer** or **Carbon Copy** |
| Additional authentication | No | Checkbox | “Do you want to use additional authentication?” — SMS/phone code; Enterprise / fees |
| Email Template | No | Dropdown | |
| Email Subject | No | Text | User may update |
| Email Message | Review | Text | |
| Send Document vs Save as Draft | Yes | Action | Send now or later |
| Add Another Signer | No | Action | More recipients |

Sequential example in help: PO → manager approval → purchasing signature → manager copy.

## What Sage CM saves

- **Header record:** None. Envelope metadata hangs on the **linked file**.
- **Line / child records:** Signers (name, email, type, order, auth).
- **System-generated values:** DocuSign envelope/status; color on the file.
- **Files / attachments:** Source PDF in Linked Files; signed document and certificates downloaded from **DocuSign’s server** when complete.
- **Audit / workflow fields:** Draft vs sent; in-progress / complete / error colors.

## Statuses and lifecycle

| Color / action | Meaning |
|---|---|
| Save as Draft | Envelope not sent |
| Yellow | Signing in progress |
| Green | Signing complete |
| Red | Error |
| E-Sign menu | View status, view signers, view/download signed document or certificates |

Carbon Copy activity is not tracked beyond recording recipient info on the envelope.

## Dates that drive alerts

No e-Sign row on the alerts calendar. Contract/invoice dates remain those of the source record.

## Relationships

- **Upstream:** Supported financial/contract records; Reports → linked PDF; DocuSign account.
- **Downstream:** Signed PDF + certificate on DocuSign; file menu in SCM.
- **Not listed** on the start-e-Sign page: daily logs, meetings, punchlists, safety records.

## Reports and exports

- The payload **is** a report PDF saved to Linked Files.
- Download signed document and certificates from the E-Sign menu (DocuSign server).

## USIS / CM_Deploy mapping

| Sage concept | USIS table / API / page | Status |
|---|---|---|
| DocuSign e-Sign on linked files | none | none |
| Document store | `documents.file_url` | none (no envelope workflow) |

## Sources

- Official Sage help URLs used
  - https://help.sagecm.intacct.com/Content/IntegrationsPublicAPIs/eSignatures/DocuSign/StartESignProcess.htm
  - https://help.sagecm.intacct.com/Content/Mobile/MobileApp_Apple/MobileApp_AppleiOS_Overview.htm
- Local files reviewed
  - `backend/app/models/document.py`
