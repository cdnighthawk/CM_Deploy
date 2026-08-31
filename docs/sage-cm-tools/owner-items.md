# Owner items

Status: complete
Sage CM module: Documentation
Official help: https://help.sagecm.intacct.com/Content/Modules/Emailing/OpenItemsEmail.htm

## Purpose

Owner items are a Documentation feature for tracking materials or deliverables the **owner’s supplier** still owes the job. Sage treats an owner item as open when **Actual Delivery is null** and the **Supplier** company/contact matches the person you email from Team Open Items. That is the only official field contract published on help.sagecm.intacct.com for this tool.

## Where it lives

- **Documentation** module (default security-role matrix lists **Owner items** under Documentation, alongside meeting items).
- **Documentation Overview** and **Project Team → Team Open Items**: owner items appear in the open-items email when Actual Delivery is null.
- Dedicated list/form path is **not confirmed in help** (guessed URLs under `Documentation/OwnerItems/` and `Documentation/OwnerItem/` returned 404 or timed out).
- **Alerts calendar:** Owner items are **not** in the Documentation alerts table (unlike daily logs, meetings, and WOs).
- **Mobile:** Owner items are **not** on the iOS feature matrix.
- **Linked-files feature list** (upload-from-record help) lists Daily Logs, Meetings, and Work Orders but **does not list Owner Items** — file support is **not confirmed in help**.

## Who uses it

- PMs/supers record owner-furnished or owner-purchased items and the supplier responsible for delivery.
- External **Supplier** company/contact receives Team Open Items email (hyperlink + security code) while Actual Delivery is empty.
- Internal employees cannot use TeamLink; they work the record in Sage CM (exact form **not confirmed in help**).

## Prerequisites

- Project (and project directory company/contact for the supplier).
- Documentation module access (Owner items permission on the security role).
- Remaining prerequisites (prime contract, item catalog) are **not confirmed in help**.

## What the user fills out

Dedicated Add Manually help for Owner Items was **not found** after search and URL retry. Do not invent a full create form. Confirmed fields used by open-item email:

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Supplier Company | Yes (for open-item match) | Directory company | Filter: Supplier is the selected company |
| Supplier Contact | Yes (for contact-level match) | Directory contact | Filter: Supplier is the selected company **and contact** |
| Actual Delivery | No | Date | **Null = open**; any value removes the item from Team Open Items |

### Fields not confirmed in help

The following are **not confirmed in help**. Do not model them as official Sage names until a help topic or tenant screenshot exists:

- Item #, Description, Quantity, Units
- Anticipated / required-on-site dates (those names are documented on **Submittals**, not Owner Items)
- Location, spec section, drawing, prime contract
- Status enum other than the implied “undelivered vs delivered”
- Linked files

If a future help page appears, expected path pattern is `Content/Modules/Documentation/...` (same module as meetings and WOs).

## What Sage CM saves

- **Header record:** At least a documentation owner-item record keyed for Team Open Items (Supplier + Actual Delivery). Full header schema **not confirmed in help**.
- **Line / child records:** Not confirmed. Open-items email treats “owner items” as records, not as meeting-style child items.
- **System-generated values:** Not confirmed.
- **Files / attachments:** Not listed on Upload files from within a record — **not confirmed**.
- **Audit / workflow fields:** Open while Actual Delivery is null; email includes portal hyperlink + security code.

## Statuses and lifecycle

No named Draft/Approved status in help. Operational lifecycle from open-item rules:

1. Create owner item with a Supplier (form **not confirmed**).
2. While Actual Delivery is null → included in Team Open Items for that supplier.
3. Enter Actual Delivery → drops off open items.

## Dates that drive alerts

- **Actual Delivery** drives open-item email only.
- **Not** listed on Home Alerts / Documentation Calendar feature-date table.

Do not confuse with Submittal **Material Delivery To Site** dates (Anticipated / Estimated / Actual Delivery Date) — those are Correspondence, not Owner Items.

## Relationships

- **Upstream:** Project directory supplier; Documentation module.
- **Downstream:** Team Open Items email from Documentation Overview or Project Team.
- **Not the same as:** Owner **cost codes** (Client Contract Admin → Job Cost Codes → Owner Cost Codes: Order Number, Code, Description).
- **Not the same as:** Work orders issued by an Owner (that is the WO Issued By pattern).

## Reports and exports

- Team Open Items email (Documentation / Project Team).
- Dedicated owner-item log/detail report name is **not confirmed in help**.

## USIS / CM_Deploy mapping

Nothing in USIS models owner-furnished delivery tracking.

| Sage concept | USIS table / API / page | Status |
|---|---|---|
| Owner item + Actual Delivery + Supplier | none | none |
| Owner cost codes (different tool) | none | none |
| Submittal actual delivery (different tool) | submittals material dates | none (do not reuse as Owner Items) |

## Sources

- Official Sage help URLs used
  - https://help.sagecm.intacct.com/Content/Modules/Emailing/OpenItemsEmail.htm (Owner items row)
  - https://help.sagecm.intacct.com/Content/Administration/Settings/CompanySettings/CompanySettings_SecurityRoles_Default.htm (Owner items under Documentation)
  - https://help.sagecm.intacct.com/Content/Modules/AlertsCalendars/AlertsCalendar_All.htm (no owner-item date)
  - https://help.sagecm.intacct.com/Content/Modules/FileManagement/UploadingFilesFromFeature.htm (Owner Items omitted from feature list)
  - https://help.sagecm.intacct.com/Content/Mobile/MobileApp_Apple/MobileApp_AppleiOS_Overview.htm (omitted)
- Local files reviewed
  - No USIS model
- **Gap:** `.../Documentation/OwnerItems/OwnerItemsOverview.htm` and `.../OwnerItem/OwnerItemOverview.htm` were not available (404 / timeout). Do not invent remaining field names.
