# Tests and inspections

Status: complete
Sage CM module: QC and Safety
Official help: https://help.sagecm.intacct.com/Content/Modules/QCSafety/TestInspection/TestInspectionAddManually.htm

## Purpose

Test / Inspections records a lab or field test campaign: header (what is being tested, spec/standard references) plus **samples taken** (when, how much, who prepared them, testing company/facility, pass/fail status). Open-item email treats the test as open when **Test Overall Status is Open**, a sample is **Pending**, and **Testing Company** matches the emailed firm.

## Where it lives

- **Project Home** → Quality Control → **Test / Inspections**.
- Add wizard: header → samples → linked files (help labels two consecutive “Step 2”s: samples, then files).
- **Team Open Items** on Quality and Safety overview.
- **Mobile:** Test and inspections R, E, A (no Delete in the iOS matrix).
- **Alerts calendar:** Tests are **not** listed on the QC alerts-date table (open items only).

## Who uses it

- QC/PM creates the test header (subject, type, references).
- Field/lab staff add samples (Prepared By, location, quantity).
- **Testing Company** (directory) is the lab that appears on Team Open Items while samples are Pending.
- Admins define **Type** values in Feature Settings → QC & Safety.

## Prerequisites

- Project; optional prime contract.
- Testing company / prepared-by contacts in the **project directory** (magnifying-glass lookup).
- Test and inspection **Type** options in Feature Settings → QC & Safety.

## What the user fills out

### Header (step 1)

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Project number | No | Project picker | |
| Prime Contract | No | Prime contract | |
| Test # | Yes (auto) | Text/number | Auto-generated; required; user may update |
| Type | No | Dropdown | Help also says “meeting Type” in one sentence — that is the **test/inspection Type** list from Feature Settings |
| Subject | Yes | Text | |
| Description | No | Text | Description of the test |
| Test Frequency | No | Reference | |
| Standard Test # | No | Reference | |
| Spec. Section | No | Reference | |
| Other | No | Reference | |

**Test Overall Status** is used by open items (Open). The add-header page does not list it as a required control; persist it as a workflow field confirmed on OpenItemsEmail.

### Defaults for Samples Test Results (step 2)

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Location | No | Text | Where samples were taken; copied onto each sample |
| Testing Facility | No | Text | Where samples are sent for testing |
| Prepared By Contact | No | Directory contact | Person who supervised prepared samples; copies to sample rows |
| Testing Company | No | Directory company | Firm responsible for testing; open-item match |

### Each sample (Samples Taken)

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Sample Date | Yes | Date | |
| Sample Time | No | Time | |
| Quantity | Yes | Number | |
| Size | No | Text | e.g. EA, CuYd, CuFt |
| Location | No | Text | Defaults from header defaults |
| Prepared By | No | Contact | Defaults from Prepared By Contact |
| Status | Yes (help: select) | Enum | **Pending** (default), **Compliance**, **Non-Compliance** |

Add New Line for more samples. Skip samples is allowed.

### Linked files

48 files / 500 MB; Link Existing Files Photos / Drawings & Specs / All Other Records. Help text says files “relevant to the sample.”

## What Sage CM saves

- **Header record:** Test #, type, subject, description, references, prime contract, overall status, default location/facility/prepared-by/testing company.
- **Line / child records:** Samples (date, time, qty, size, location, prepared by, status).
- **System-generated values:** Test #; sample Status default Pending.
- **Files / attachments:** Linked files on the test (and/or sample — help wording is sample-relevant).
- **Audit / workflow fields:** Overall Status Open; sample Pending → Team Open Items for Testing Company.

## Statuses and lifecycle

| Level | Status | Effect |
|---|---|---|
| Test overall | Open | Required for open-item email |
| Sample | Pending | Required for open-item email |
| Sample | Compliance | Pass |
| Sample | Non-Compliance | Fail |

Closed/complete overall status names beyond **Open** are **not confirmed in help**.

## Dates that drive alerts

Not on the QC alerts-date table. Sample Date is operational only. Team Open Items is the follow-up channel.

## Relationships

- **Upstream:** Feature Settings types; directory testing company; specs (Standard Test #, Spec. Section).
- **Downstream:** Team Open Items; linked lab reports/photos.
- **Sibling:** Permits (building department) vs this tool (lab/field tests).

## Reports and exports

- Standard detail/log naming **not confirmed in help**.
- Mobile add/edit (no delete).

## USIS / CM_Deploy mapping

| Sage concept | USIS table / API / page | Status |
|---|---|---|
| Test / inspection header + samples | none | none |
| Safety-automation inspection form | `docs/safety-automation/templates/forms/INSPECTION.md` | none (paper/HTML packet, not Sage tests) |
| Document type | `documents.document_type` has no test/inspection enum | none |

## Sources

- Official Sage help URLs used
  - https://help.sagecm.intacct.com/Content/Modules/QCSafety/TestInspection/TestInspectionAddManually.htm
  - https://help.sagecm.intacct.com/Content/Modules/Emailing/OpenItemsEmail.htm
  - https://help.sagecm.intacct.com/Content/Mobile/MobileApp_Apple/MobileApp_AppleiOS_Overview.htm
- Local files reviewed
  - `docs/safety-automation/templates/forms/INSPECTION.md`
  - `backend/app/models/document.py`
