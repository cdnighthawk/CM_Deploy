# TeamLink portal

Status: complete
Sage CM module: Companion products
Official help: https://help.sagecm.intacct.com/Content/TeamLinkPortal/TeamLinkPortalHome.htm

## Purpose

TeamLink is the **free, browser-only** portal for **external** customers, architects, bidders, and vendors. It cuts phone/email by giving controlled access to lead/project records (ITBs, RFPs, correspondence, documentation, live schedule). **Internal employees cannot use TeamLink.** Locked records stay read-only for the collaborator’s original response.

## Where it lives

- Not a Project Home “module form.” Configuration is on the lead/project (**Show In Portal**), project **directory** (external collaborator + TeamLink role), and emails (open items / invitations) that include a **hyperlink + security code**.
- Portal URL is browser-based (all browsers). No internal employee login.
- **Leads:** Show In Portal on create or Lead Home so bidders see ITBs.
- **Photos:** album **Show In Portal** required (photo must be in that album).
- **Schedules:** TeamLink live Gantt (Owner/Architect read-only; Vendor = assigned tasks only).

## Who uses it

- External: owners, architects, subcontractors, suppliers, ITB bidders.
- Internal Sage users **configure** access (directory, roles, Show In Portal) but do not sit in the portal themselves.
- Two authentication methods (both on projects; **only one** on leads).

## Prerequisites

- External collaborator added to the **lead or project directory** (required for both methods).
- Method 2: assign a **TeamLink security role** (Vendor, Architect, Owner are cited for schedules; roles are customizable).
- Lead ITB visibility: **Show In Portal** on the lead.
- Photo albums: Show In Portal on the album.
- Open-items / invitation emails generate method-1 style hyperlink + security code.

## What the user fills out

TeamLink is not a Sage “create record” tool. Setup and portal login fields:

### Internal setup

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Show In Portal (lead) | For ITBs | Checkbox | Create lead or Lead Home |
| Show In Portal (photo album) | For photos | Checkbox | Album + membership required |
| External collaborator in directory | Yes | Directory | Required both methods |
| TeamLink Role | Method 2 | Role | e.g. Vendor, Architect, Owner; customizable |
| Open items Company / Contact | For email | Directory | Sends hyperlink + security code |

### Authentication method comparison (official)

| Role/Feature | Method 1 | Method 2 |
|---|---|---|
| Implementation | Easy | Needs additional steps |
| Applicable to | Leads and projects | **Projects only** |
| Controls / user security roles | Not applicable | Granular customizable roles |
| TeamLink Role required | No | Yes |
| Add external collaborator to directory | Required | Required |
| Access method | Hyperlink → one lead/project record | Username + password login |
| Available information | Only that lead or project record | All referenced records + all projects where access granted |
| View other projects | No | Yes, if in that project directory and has a TeamLink role |
| Can respond to record | Yes | Yes |
| Add new records or transactions | None | Several (types **not enumerated** on the overview) |

### Portal collaborator actions (confirmed)

- Respond to unlocked records (RFP packages, CPR pricing, correspondence, documentation). After lock, original response is read-only.
- View Show In Portal photo albums.
- View live schedule per role (Owner/Architect read-only; Vendor assigned tasks).
- Follow open-items email link + security code.

Username/password field labels for method 2 are **not confirmed in help** beyond “log in using a username and password.”

## What Sage CM saves

- **Header record:** No TeamLink document type. Directory flags, TeamLink role assignment, Show In Portal bits, and issued security codes/links.
- **Line / child records:** Portal responses written back onto the underlying Sage records (RFI, submittal, etc.).
- **System-generated values:** Security code on open-items / invitation email.
- **Files / attachments:** Collaborators see files allowed by role/record; they do not get a separate TeamLink file store.
- **Audit / workflow fields:** Record lock → collaborator cannot modify; original response remains.

## Statuses and lifecycle

1. Add collaborator to directory; optionally assign TeamLink role (method 2).
2. Set Show In Portal on lead/albums as needed.
3. Collaborator opens hyperlink (method 1) or logs in (method 2).
4. Respond while unlocked; locked records become read-only.
5. Internal staff continue in Sage CM (they never use the portal).

## Dates that drive alerts

TeamLink has no alert-date row. Open-item emails use the **source feature** dates (meeting items, owner items, WOs, punchlist, etc.).

## Relationships

- **Upstream:** Directory, security roles, Show In Portal, Feature Settings.
- **Downstream:** Responses on RFPs, CPRs, correspondence, documentation; schedule collaboration; photo viewing.
- **USIS:** no external portal; field staff use the USIS mobile app with employee login.

## Reports and exports

- None specific to TeamLink. Source-module reports still apply.
- Related: View ITBs and RFPs for leads in the TeamLink portal (linked topic on the overview).

## USIS / CM_Deploy mapping

| Sage concept | USIS table / API / page | Status |
|---|---|---|
| TeamLink portal / roles | none | none |
| Show In Portal | none | none |
| Open-items hyperlink + code | none | none |
| External directory collaborator | companies/contacts (internal CRM) | none |

## Sources

- Official Sage help URLs used
  - https://help.sagecm.intacct.com/Content/TeamLinkPortal/TeamLinkPortalHome.htm
  - https://help.sagecm.intacct.com/Content/Modules/Scheduling/Schedules/Schedule_CollaborateOnLiveSchedule.htm
  - https://help.sagecm.intacct.com/Content/Modules/Documentation/ProgressPhotos/ProgressPhotos_AlbumShowInPortal.htm
  - https://help.sagecm.intacct.com/Content/Modules/Emailing/OpenItemsEmail.htm
- Local files reviewed
  - No USIS equivalent
