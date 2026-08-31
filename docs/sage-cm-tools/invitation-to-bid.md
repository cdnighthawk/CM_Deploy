# Invitation to bid

Status: complete
Sage CM module: Preconstruction (Drawings / Specifications / ITB)
Official help: https://help.sagecm.intacct.com/Content/Modules/DwgsSpecsITB/InvitationToBid/InvitationToBidOverview.htm

## Purpose

ITB is an **email + TeamLink** tool to announce a job and **gauge interest**. Vendors see bid due date/time and linked drawings/specs; they answer Bidding / Not Bidding / undecided — they do **not** submit priced quotes. Priced quotes are **RFP packages**.

## Where it lives

- Lead or Project Home → **Invitation to bid (ITB)** under Preconstruction
- Tabs: general/bid info, **Linked Files**, **Vendors**, messages
- Mobile: not listed as an ITB add/edit module (vendors use TeamLink)
- TeamLink: vendors need a valid email; leads need **Show In Portal**

## Who uses it

- Bid captain / Bid Contact sends invitations and answers private vendor questions
- Estimators add vendors from bidder list, master list, previous ITB, or classification
- Vendors respond in TeamLink and send private messages

## Prerequisites

- Lead or project exists
- Companies and contacts in Contact Management with **email**
- For leads: Show In Portal
- Optional: drawings and specifications uploaded
- Bid Contact and Bid Due Date/Time live on the **lead/project** (Edit), not only on ITB

## What the user fills out

### Bid header (lead/project Edit, also used by ITB)

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Bid Contact (Main Bid Contact / Bid Captain) | Recommended | Lookup | Internal stakeholder overseeing the opportunity |
| Bid Due Date | Recommended | Date | Shown in TeamLink; alerts for Bid/PM/Sales |
| Bid Time | Recommended | Time | |

### Linked Files tab

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Add / drag files | No | Files | New uploads |
| Link Existing | No | Choice | Drawings & Specs, Photos, All Other Records |
| Feature Name / Album | No | Lookup | Filter |
| Grant Access | No | Checkbox | Per file; required for TeamLink viewing. Linked files are **not** email attachments |

### Vendors tab — Add vendors

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| View | Yes | Choice | Add Vendor from Previous ITB; Master List; Bidder List; Add By Classification |
| Source / Project (previous ITB) | No | Filter | |
| Distance Filter | No | Filter | All views |
| Company Type / Vendor Type / Ship State / Bill State | No | Filter | Classification view |
| Search | No | Text | |
| Company + Contact | Yes | Multi-select | Bid Contact checkbox on contacts helps filter |

### Vendor ITB status (after add)

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Status | Yes (defaults) | Lookup | **No Response** (default); Undecided - Waiting For Plans; Undecided - Reviewing Plans; Undecided - Need Assistance; Not Bidding; Bidding |

Bulk: update Status or Delete selected vendors.

### Send Invitation email

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Template | Yes | Lookup | |
| Recipients List | Yes | Contacts | Each vendor gets a **private** individual email |
| CC List | No | Contacts | |
| Subject / Body | No | Text | |
| Email Upload Attachments | No | Files | Email-only; not added to Linked Files / TeamLink |
| Grant Access on linked files | No | Checkbox | Portal access |

General messages and private vendor messages: functions exist; extra form fields **not confirmed in help**.

## What Sage CM saves

- Header record: ITB tied to the lead/project bid contact and bid date/time
- Line / child records: vendor rows (company, contact, status); linked files; message threads
- System-generated values (IDs, numbers, dates, totals): TeamLink hyperlink + security code on emails
- Files / attachments: linked drawings/specs/photos; optional email-only attachments
- Audit / workflow fields: vendor status; private vs general messages

## Statuses and lifecycle

Vendor status: No Response → undecided variants → **Bidding** or **Not Bidding**. RFP add-from-ITB can filter **Bidding Only**.

## Dates that drive alerts

Lead/project **owner bid due date** (user is Bid, PM, or Sales Contact). ITB itself is not a separate row on the alerts table.

## Relationships

- Upstream: lead/project, directory/companies, drawings/specs
- Downstream: TeamLink responses; RFP “Add From ITB - Bidding Only”; not a priced bid

## Reports and exports

- Email ITB; general messages
- TeamLink portal listing
- Implementation plan: Estimating – Invitation to bid (optional)

## USIS / CM_Deploy mapping

| Sage concept | USIS table / API / page | Status |
|---|---|---|
| ITB header + vendor status list | none | none |
| Bid due / invited | `lead_estimates.due_at`, `invited_at`, `crm_stage` | partial |
| BuildingConnected opportunity | `lead_estimates` CSV/API | implemented |
| Priced vendor request | `rfps` (RFP, not ITB) | none |
| TeamLink ITB | none | none |

## Sources

- Official Sage help URLs used
  - https://help.sagecm.intacct.com/Content/Modules/DwgsSpecsITB/InvitationToBid/InvitationToBidOverview.htm
  - https://help.sagecm.intacct.com/Content/Modules/DwgsSpecsITB/InvitationToBid/InvitationToBid_AddVendors.htm
  - https://help.sagecm.intacct.com/Content/Modules/DwgsSpecsITB/InvitationToBid/InvitationToBid_UpdateVendors.htm
  - https://help.sagecm.intacct.com/Content/Modules/DwgsSpecsITB/InvitationToBid/InvitationToBid_UpdateGeneralInfo.htm
  - https://help.sagecm.intacct.com/Content/Modules/DwgsSpecsITB/InvitationToBid/InvitationToBid_EmailingInfo.htm
  - https://help.sagecm.intacct.com/Content/Modules/DwgsSpecsITB/InvitationToBid/InvitationToBid_LinkDrawingsSpecs.htm
  - https://help.sagecm.intacct.com/Content/GettingStarted/ImplementationPlan_Est_Opt_ITB.htm
- Local files reviewed
  - `backend/app/models/lead_estimate.py`
  - `backend/app/models/rfp.py`
