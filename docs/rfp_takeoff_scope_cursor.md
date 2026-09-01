# Cursor Implementation Brief — RFP Body + Vendor Quote Email + Drawings

**Date:** 2026-08-31  
**Updated:** 2026-08-31 — `quotes@gousis.com` send + drawing attach/link  
**Repo:** `CM_Deploy`  
**Website product:** **USIS CM** (not FinishWorks)  
**Module:** RFP create / edit / send / public vendor portal  
**Depends on:** existing RFP module (do not rebuild), Estimating takeoff lines, Drawing register / DrawingViewer export, `Company` vendors, SMTP + Celery, `website_product_plan_cursor.md` §4.2  
**Owner company:** US Interior Specialties (USIS) — finish-work subcontractor, CA commercial + government work

Staff need three ways to tell a vendor what to price:

1. **Attach a takeoff** from an existing estimate on the same project / bid (preferred when takeoff exists).
2. **List items by hand** when there is no takeoff yet.
3. **Write a scope + inclusions + exclusions** — always available, and valid as the *only* content when there are no priced lines.

Do **not** rebuild the RFP module. Extend the existing create/edit form, email Jinja2, public token form, and comparison table.

---

## 0. Non-negotiable rules

- Keep xAI/Grok integration untouched.
- Do not regress: public token quote form, per-line pricing math, comparison table, lowest-price highlight, award, CSV export, audit log, Celery/SMTP send, vendor `Company` picker, drawing attachments.
- Staff UI is **W3CRM + Bootstrap 5 + DataTables + `usis-ui.css` LAST + `window.USISUi`**. Do **not** add React / MUI pages (`src/pages/RFP/*.tsx` encyclopedia names are stale).
- Public vendor pages stay in `backend/app/public_portal.py` (or the existing public RFP blueprint). Do not put the vendor form inside W3CRM auth chrome.
- Email / branded PDF stay Flask + Jinja2. No Jinja2 in frontend JS.
- **Never send internal unit cost, markup, tax, profit, or vendor-quote columns to the vendor.** Takeoff attach copies description / qty / unit / notes / CSI / drawing refs only.
- After **Send**, the RFP body is frozen. Estimate edits must not silently change a live RFP.
- Configurable Div 10 lines (lockers, etc.) copy the **frozen product snapshot JSON**, not a live catalog pointer (`penco_locker_configurator_import.md`).
- No new AI mode required. Optional later: existing ChatBot `estimating_review` / purple button. Do not touch ChatBot core.
- Do not invent a second line-item table. Reuse `RFPLineItem`.
- Official vendor quote-request mail is sent **From / Reply-To `quotes@gousis.com`**. Do not send RFPs from the logged-in estimator’s personal mailbox.
- One SMTP message **per invited vendor** (unique public token). Never To/CC a second vendor on the same message.
- Drawings for an RFP are picked from the **existing project Drawing register**. Do not fork a second file store. Prefer tokenized **links**; **attach PDFs** only when the user opts in and the size cap allows.
- Do not touch DrawingViewer canvas / calibration internals. Reuse whatever PDF / watermarked export already exists.

---

## 1. What to build (scope)

On RFP **create and edit** (Draft only), add one section titled **What vendors should price**.

That section has two always-visible narrative fields plus one source picker for priced lines.

### 1.1 Always-on narrative (every RFP)

Three text areas on `RFP`:

| Field | Label | Required? |
|---|---|---|
| `scope_of_work` | Scope of work | Required **if** the RFP has zero line items. Optional if ≥1 line exists. |
| `inclusions` | Inclusions | Optional |
| `exclusions` | Exclusions | Optional |
| `clarifications` | Clarifications / notes to bidders | Optional (include; cheap and estimators use it) |

Plain textarea in v1 (preserve line breaks). Do not ship a heavy rich-text editor. Render with `white-space: pre-wrap` on staff detail, email, and public portal.

Place these **above** the line-item table so a narrative-only RFP does not look empty.

### 1.2 Priced-line source (pick one primary source)

Radio / segmented control (Bootstrap button group):

| Value | Label | When to use |
|---|---|---|
| `takeoff` | Attach takeoff | An estimate / takeoff already exists on this project or bid |
| `manual` | List items | No takeoff yet, or the ask is a short custom list |
| `narrative` | Scope only | Lump-sum or qualitative bid; no line table |

Default:

- If the linked project/bid has at least one estimate with takeoff rows → `takeoff`.
- Else → `manual`.
- User can always switch to `narrative`.

Switching source on a Draft RFP that already has lines:

- `takeoff` → `manual`: keep copied rows, clear `source_estimate_id` / `source_takeoff_line_id` so they become ordinary manual rows. Confirm.
- `manual` / `takeoff` → `narrative`: warn “Hide these N lines from vendors? Lines are kept on the RFP but not shown until you switch back.” Prefer **keep rows, set `show_line_table = false`** rather than delete.
- `narrative` → `takeoff` / `manual`: show the table again.

`line_source` is stored on `RFP` (`takeoff` | `manual` | `narrative`).

### 1.3 Attach takeoff flow

Shown when `line_source = takeoff`.

1. **Estimate picker** — estimates for this `project_id` (and parent bid if the RFP was spawned from CRM). Show name, status, updated-at, line count.
2. **Row picker** — takeoff table of that estimate:
   - Columns: include checkbox, CSI / division, trade, description, qty, unit, room/area, notes.
   - **Do not show** unit cost, total, markup, tax, vendor quote.
   - Header select-all, filter by trade / CSI (reuse takeoff AutoFilter if it already exists; otherwise a simple trade dropdown).
   - “Select remaining scopes” = rows with no awarded vendor quote and not already on another **open** RFP (status not Awarded/Closed). Best-effort; do not block if the flag is imperfect.
3. **Attach selected** copies rows onto `RFPLineItem` (see §3).
4. Banner: “N lines attached from Estimate {name}. Internal pricing is not sent to vendors.”
5. While Draft: buttons **Add more from takeoff** and **Refresh selected from takeoff** (overwrites qty/desc/unit/notes from current takeoff for rows that still have `source_takeoff_line_id`). Refresh is blocked after Sent.

If the project has **no estimates**, do not dead-end. Show empty state:

> No takeoff on this job yet. [List items] or [write a scope] instead.  
> Optional: [Open estimate] if the user has permission.

Do **not** force-create an estimate from the RFP form.

Existing “Create RFP for remaining scopes” on the estimate page must use this attach path (pre-select the current estimate + remaining rows + `line_source=takeoff`).

### 1.4 Manual item list

Shown when `line_source = manual` (and also as the editable table after a takeoff attach — attached rows are editable in Draft).

Reuse the existing RFP line-item table. Minimum columns:

| Column | Notes |
|---|---|
| CSI / Division | optional |
| Description | required |
| Qty | numeric, required if unit set |
| Unit | SF, LF, SY, EA, LS, HR, GAL, SQ, … existing unit list |
| Notes | optional (visible to vendor) |
| Drawing / sheet ref | optional link to existing Drawing |
| Source | badge `Takeoff` or `Manual` (staff only) |

Add row, duplicate, delete (Draft only). Bulk paste is out of v1 unless a paste helper already exists.

Qty may be blank only when unit is `LS` (lump sum) or description is allowance / “quote to spec”.

### 1.5 Scope-only RFPs

When `line_source = narrative`:

- Hide the vendor-facing line table (staff may still see collapsed “internal lines” if any).
- Public form + email show scope / inclusions / exclusions / clarifications.
- Vendor prices a **single lump sum** (`lump_sum_amount`) plus notes / exclusions of their own.
- Comparison table has one pricing row: “Lump sum — {RFP title}”.
- Award still works (one amount per vendor).

---

## 2. Send + public portal + email

### 2.1 Send validation

Block Send / resend unless:

1. At least one invited vendor, due date, and project (existing rules), **and**
2. Content rule: `count(RFPLineItem where not hidden) >= 1` **OR** `scope_of_work` is non-empty after trim.

Warn (do not block) if inclusions **and** exclusions are both empty.

After Send:

- Freeze line snapshots and narrative fields.
- Edit of scope/lines requires a new revision or “Amend & resend” if that already exists; if the module has no revision model, lock fields and only allow “Clone to new RFP”. Do not invent a full revision system in this ticket unless one already exists.

### 2.2 Jinja2 email

Add sections to the existing branded template, only if the field is non-empty:

- Scope of work
- Inclusions
- Exclusions
- Clarifications
- Line-item table (existing) — omit entirely when `line_source = narrative` or no visible lines
- Drawings (filenames + “Open sheet” links; note whether a PDF is also attached)

Do not add internal cost columns.

Full send identity, vendor addressing, and drawing attach/link rules are in **§8–§9**. Those sections win if an older “Send RFP” comment conflicts.

### 2.3 Public vendor form (`/public/rfp/<token>`)

- Render the four narrative fields read-only at the top.
- If visible lines exist: existing per-line unit price + extension math.
- If no visible lines: one required **Lump sum** money input + optional vendor notes / vendor exclusions / file upload (file upload already exists).
- Due-date close behavior unchanged.

---

## 3. Data model

Extend existing models. Do not create `RFPTakeoff` as a second line store.

### `RFP` additions

| Field | Type | Notes |
|---|---|---|
| line_source | String | `takeoff` \| `manual` \| `narrative` |
| source_estimate_id | FK Estimate nullable | last attached estimate (informational; lines hold the real links) |
| scope_of_work | Text nullable | |
| inclusions | Text nullable | |
| exclusions | Text nullable | |
| clarifications | Text nullable | |
| show_line_table | Boolean default true | false when narrative mode hides lines |

### `RFPLineItem` additions

| Field | Type | Notes |
|---|---|---|
| source_takeoff_line_id | FK EstimateLineItem nullable | set when copied from takeoff |
| source_kind | String | `takeoff` \| `manual` \| `ai_suggest` (last unused in v1) |
| hidden_from_vendor | Boolean default false | narrative mode can hide without delete |
| product_snapshot | JSONB nullable | copy from takeoff if present (Div 10 frozen config) |

Copy on attach: description, qty, unit, notes, CSI/division, trade, room/area, drawing refs, `product_snapshot`.  
Do **not** copy unit_cost, markup, tax, total, vendor_quote.

On award: if `source_takeoff_line_id` is set, write the awarded unit/extended price into that takeoff line’s **Vendor Quote** column (existing integration). Manual-only lines do not invent takeoff rows unless the user later runs “Add awarded lines to estimate” (out of v1 if it does not already exist).

---

## 4. Staff UI placement

RFP list page: no change except an optional source chip on the card/row (`Takeoff` / `Items` / `Scope`) using `USISUi.statusChip`, primary `#1F4E5F`. Do not use AI purple.

RFP detail / form (existing page — search before adding a sibling):

```
gulp/src/**/*rfp*
RFP create / edit / detail templates
```

Section order on create/edit:

1. Header (project, title, due, urgency) — existing
2. **What vendors should price** (this ticket)
3. Vendor picker from `Company` — §8
4. Drawings for vendors (link and/or attach) — §9
5. Preview / Send from `quotes@gousis.com` — §8

Project-details toolbar: Estimate parent already lists RFP as a child (`project_details_toolbar_cursor.md`). Do not add a seventh parent.

Comparison table: if `line_source = narrative`, one row. If mixed hidden lines exist, only non-hidden rows appear.

---

## 8. Email quote requests from `quotes@gousis.com`

The RFP module already sends branded mail. This ticket **pins the mailbox, the recipient source, and the preview/send UX**. It does not invent a second mailer.

### 8.1 Identity (lock)

| Header | Value |
|---|---|
| From | `US Interior Specialties <quotes@gousis.com>` |
| Reply-To | `quotes@gousis.com` |
| Bounce / Return-Path | existing SMTP envelope; prefer `quotes@gousis.com` if the mail server allows |
| BCC | `quotes@gousis.com` (so the shared box always has a copy) |
| To | **one** vendor contact per message |
| CC | none by default. Optional per-RFP `cc_estimator` = the sending user’s work email, off unless checked |

Display name may read **USIS Estimating** if that is already the branded From-name. Do not change the address.

Config key (reuse existing SMTP settings object; do not hardcode in three templates):

```
rfp.mail.from_address = quotes@gousis.com
rfp.mail.from_name    = US Interior Specialties
rfp.mail.bcc_self     = true
```

Staff must not be able to override From on the send preview. Reply-To stays the shared box so vendor questions land where they are monitored.

If Graph / M365 send-as is already how SMTP is wired, send **as** `quotes@gousis.com` (mailbox must have Send As). If the current transport is generic SMTP login, use that account but still set From/Reply-To to `quotes@gousis.com` only if the server will not rewrite or SPF-fail. If SPF/DKIM is not aligned yet, still set the headers and log a warning — do not silently fall back to a personal inbox.

### 8.2 Recipients = vendors in the database

Picker is the existing `Company` list filtered to `company_type` in `vendor` | `subcontractor` | `supplier`.

Per selected company:

| Field | Rule |
|---|---|
| Quote email | Required to include in Send. Prefer `quote_email` if that column exists, else primary `email`. |
| Extra contacts | If `Company` already has contacts, show a checkbox list (estimating / sales). Default = primary quote email only. |
| Missing email | Row stays selected but Send is blocked for that row with “Add email on the vendor record.” Deep link to Company edit. Do not invent an on-form email that never writes back. |
| Trade match | Optional filter (drywall, paint, flooring, Div 10). Do not hide vendors that lack a trade tag. |

Send loop:

1. Preview lists every selected vendor + resolved To address + token status.
2. User confirms.
3. Celery task sends **one job per vendor**. Failure on vendor B does not roll back A.
4. RFP status → Sent when at least one message is accepted by SMTP.
5. Per-vendor send row: queued / sent / bounced / opened (opened only if tracking already exists — do not add a new pixel tracker in this ticket).

Do **not** put all vendors on one email. Tokens and pricing must stay private.

Reminders (48h / 24h before due) reuse this same From identity and the same drawing link set. Do not re-attach large PDFs on reminders unless the user checks “include attachments again.”

### 8.3 Preview / Send UI

Existing preview stays. Add a left column “Recipients” and a right column “Message + drawings.”

Must show before send:

- From `quotes@gousis.com`
- Each To line
- Due date / urgency badge
- Scope / inclusions / exclusions / line table (no costs)
- Drawing list with Link / Attached badges
- Public CTA URL pattern (token redacted in the staff preview list except last-4, full URL only inside the per-vendor mock)

Buttons: **Send to all ready vendors** · **Send to selected** · **Save draft**.

Audit log each send: rfp_id, company_id, to_email, from_email, drawing_ids, attach_bytes, message_id, user_id, timestamp.

Inbound replies in `quotes@gousis.com` are **not** a compose thread in USIS CM. If that mailbox is later added to the correspondence allow-list (`project_correspondence_archive_cursor.md`), archive-as-files only. Do not build an in-app inbox on this ticket.

---

## 9. Drawings on the RFP — link and/or attach

Staff pick the sheets that support the quote request. Vendors receive them on the email **and** on the public token page.

### 9.1 Picker

Section **Drawings for vendors** on the Draft RFP form.

Source: project Drawing register (same records DrawingViewer uses). Also allow Documents Hub PDFs tagged as drawings/specs if the register is empty — but prefer the register.

UI:

- Checkbox list: sheet number, title, discipline, revision, updated-at
- Pre-check sheets already referenced on RFP line items
- “Select architectural + finish sheets” helper if discipline exists; otherwise select-none is fine
- Per checked sheet, delivery:

| Mode | Meaning |
|---|---|
| `link` | Tokenized HTTPS download on the email + public portal (default) |
| `attach` | PDF bytes on the SMTP message |
| `both` | Link plus attach |

Default every checked sheet to **`link`**. Attach is opt-in.

Do not attach source CAD (DWG/RVT) in v1. If the only file is CAD, show “PDF rendition required” and keep it as a **link** to the portal viewer / download if a PDF derivative exists; otherwise skip attach and leave the portal link.

### 9.2 Links (default path)

Each invited vendor gets drawing URLs that require **that vendor’s RFP token** (or a child download token bound to the invitation). Unauthenticated `/files/123` is not acceptable.

Link target, in order of reuse:

1. Existing watermarked PDF export if the drawing module already has one
2. Else stored PDF on the drawing record
3. Else public portal page that opens the sheet in a **read-only** viewer (no edit tools, no internal measurements overlay unless those are already vendor-safe)

Watermark text if export already supports it: `{vendor company} · {RFP number} · For pricing only · {date}`. Do not rebuild the canvas to add watermarking in this ticket. If watermark export does not exist, still ship tokenized links and file the watermark as a follow-up.

Links expire with the RFP invitation (due date + existing token TTL). After close/award, downloads 403 unless staff re-opens.

### 9.3 Attachments (opt-in)

Attach only PDF renditions.

Hard cap per message (seed, settings key `rfp.mail.max_attach_mb`): **18 MB**. If selected attaches exceed the cap:

- Do not fail the whole send
- Attach what fits (largest-first drop), convert the rest to **link-only**
- Preview warns: “3 sheets will be attached (12.4 MB). 4 sheets over the cap will be links only.”

Reminder emails default to links only.

### 9.4 Public portal

Same drawing list as the email, above the pricing form:

- Sheet number + title
- Open / download
- No staff annotations that are not type-safe for vendors (hide `ai_review` overlays unless product already shows them to vendors — default **hide**)

### 9.5 Data

Join table (name to match repo style: `RFPDrawing` / `rfp_drawings`):

| Field | Type | Notes |
|---|---|---|
| rfp_id | FK | |
| drawing_id | FK Drawing | |
| document_id | FK Document nullable | only if sourced from Documents Hub |
| delivery | String | `link` \| `attach` \| `both` |
| include_on_portal | Boolean default true | |
| sort_order | Integer | |
| frozen_pdf_path | String nullable | copy-on-send snapshot so a replaced sheet does not change a Sent RFP |

On Send, snapshot the chosen PDF (or path + checksum) onto the join row. Later drawing revisions do not change what a vendor already received. Staff can “Amend & resend” with updated sheets if that flow exists; otherwise clone.

---

## 5. Out of v1

- Two-way live bind (takeoff edit auto-pushes into a Sent RFP).
- Vendor-authored extra line items beyond lump-sum notes.
- Rich text / image-in-scope editor.
- New workflow process_key work (award engine can stay later; this ticket is RFP body + send).
- Forcing an estimate to be created from the RFP form.
- Exposing cost library rates to vendors.
- Attaching DWG/RVT source files.
- New email open-pixel / marketing tracker.
- In-app inbox for `quotes@gousis.com` replies (archive-as-files later, separate brief).
- Rebuilding DrawingViewer to add watermarking if export does not already exist.
- Sending one blast email to every vendor.

---

## 6. Implementation order

1. Columns + migration on `RFP` / `RFPLineItem` + `RFPDrawing`.
2. Staff form: narrative fields + source radio + empty states.
3. Takeoff picker + copy snapshot (no costs).
4. Vendor picker rules (email required, one message per company).
5. Drawing picker (link default, attach opt-in, size cap).
6. Pin SMTP From/Reply-To/BCC to `quotes@gousis.com`.
7. Send validation + preview.
8. Jinja2 email sections including drawing links.
9. Public portal narrative + lump-sum branch + drawing list.
10. Comparison table one-row narrative path.
11. Wire “Create RFP for remaining scopes” to the attach path.
12. Award → vendor-quote column via `source_takeoff_line_id`.
13. Freeze drawing PDF snapshots on Send.

Find real template / model names first. Do not scaffold a parallel RFP app.

---

## 7. Acceptance

- Draft RFP on a job **with** takeoff: attach selected rows; vendor email and public form show qty/desc/unit and **no** unit costs.
- Draft RFP on a job **without** takeoff: list items by hand; send works.
- Draft RFP with only scope + inclusions + exclusions and zero lines: send works; vendor enters one lump sum; comparison shows one row.
- All three can coexist: attached/manual lines **plus** filled inclusions/exclusions.
- Editing takeoff after Send does not change the sent RFP lines.
- Award of an attached line updates the source takeoff Vendor Quote column.
- Public portal still closes after due date. Grok / ChatBot / DrawingViewer canvas untouched.
- Page does not regress to W3CRM cyan `#0D99FF` (pin `usis-ui.css` last).
- Send preview shows From `quotes@gousis.com`. Each vendor in the database with an email receives their own message; a vendor with no email is blocked with a link to the Company record.
- Two vendors never appear on the same To/CC line.
- Checked drawings appear as tokenized links on the email and the public form. Opt-in attaches are PDF only and stay under the MB cap; overflow sheets become links with a preview warning.
- After Send, replacing a drawing file on the project does not change the snapshot the vendor already received.
- Replies are not rendered as a staff chat thread.
