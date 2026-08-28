# Cursor Implementation Brief — Plan Room–style Filters + Saved Filters on Leads Table

**Date:** 2026-08-27  
**Module:** CRM Leads / Bid Opportunities table  
**Reference UX:** BuildingConnected Plan Room filter drawer (Filter + Saved filters tabs, Reset all, Apply, Save filter)  
**Owner company:** Finish-work subcontractor, CA commercial + government work

This ticket adds a **filter drawer + named saved filters** to the **Leads / Bids table**. It is the power-filter surface. Column header sort/filter (see `table_autofilter_leads_estimates_cursor.md`) stays as the Excel-style path. Both can be active.

Do **not** rebuild CRM, Kanban, Estimating, or RFP.

---

## 0. Non-negotiable rules

- Keep xAI/Grok integration untouched.
- Do not regress RFP, DrawingViewer, ChatBot, `aiReviewBus.ts`, Estimating, Financials, Documents, Scheduling, workflow engine, POs, or Submittals.
- **Staff UI stack is W3CRM (DexignZone) + Bootstrap 5 + SCSS + vanilla JS / jQuery.** Do not scaffold React / MUI DataGrid pages to satisfy older briefs. See `ui_consistency_modernization_cursor.md`.
- If a React island already exists for CRM, restyle chrome to company tokens. Still do not introduce MUI for this ticket.
- Search the repo first. Reuse the real leads list template / DataTable. Do not invent a second CRM.
- Incremental. Ask before inventing a filename if a close equivalent exists.
- Kanban stays. Filters apply to the **table view**. Kanban may honor the same filter query so the two views do not lie to each other; do not put the drawer inside Kanban cards.
- No map / “search area / map boundaries” in v1. We are not BuildingConnected Plan Room. Drop geo UI.
- Purple “Review with Local AI” is unchanged.
- Company SCSS tokens (`$company-primary`, `$company-border`, `$company-ai`, …) — no DexignZone gradient carnival on the drawer.

---

## 1. What to build

On the CRM **Leads / Bids table** toolbar:

1. **Filter** button (funnel icon + label). Badge count = number of active criteria.
2. Off-canvas / right drawer titled **Filter**.
3. Two tabs inside the drawer: **Filter** | **Saved filters**.
4. **Reset all** (header, next to close).
5. Footer: **Save filter** (secondary) + **Apply** (primary).
6. After Apply: drawer closes (or stays open on desktop if already pinned — default close), table refreshes, active chips appear above the table.
7. Named saved filters: create, apply, rename, overwrite, delete, optional “default for me”.

Out of v1:

- Map boundaries / “Go to map view”
- Sharing a saved filter with the whole company (personal only)
- Saved filters on Estimating takeoff (leave that on localStorage AutoFilter)
- New AI modes

---

## 2. Find the real page first

Search before writing files. Likely names (use what exists):

```
templates/crm/
templates/leads/
templates/bids/
leads.html, bid_board.html, opportunities.html
static/js/crm-leads.js
DataTable #leads-table / #bid-table
Flask blueprint /crm or /bids
```

If the table view does not exist and only Kanban exists: add a **Table** toggle that uses the existing W3CRM DataTables skin (or the company table class from the UI brief). Do not remove Kanban.

Toolbar cluster (left → right):

```
[Search] [Stage chips] [Filter ▾ badge] [Saved ▾] [Reset view]     [New Lead]
```

`Saved ▾` is a shortcut menu of the user’s saved filters so they do not have to open the drawer every time. The drawer **Saved filters** tab is the manage surface.

---

## 3. Drawer UX (match the screenshot, mapped to our domain)

Bootstrap 5 offcanvas, `offcanvas-end`, width ~360–400px.

```
┌─────────────────────────────────────┐
│ Filter                    Reset all ×│
│ [ Filter ]  [ Saved filters ]       │
├─────────────────────────────────────┤
│ Search                              │
│  [ job name, GC, city, bid #     ]  │
│                                     │
│ Work performed                      │
│  [ Specialties / trades          ▾] │   multi-select chips
│                                     │
│ Companies                           │
│  [ GC / Owner / Architect        ▾] │   typeahead on Company
│                                     │
│ Sector                              │
│  ☐ Commercial  ☐ Government         │
│                                     │
│ Pipeline stage                      │
│  [ New, Invited, Estimating, …   ▾] │
│                                     │
│ Date filters                        │
│  Bid due date                       │
│  [ from ] → [ to ]                  │
│  Expected start date                │
│  [ from ] → [ to ]                  │
│  ▾ View all date filters            │
│     Award / decision date           │
│     Last activity date              │
│                                     │
│ Value                               │
│  [ min $ ] – [ max $ ]              │
│                                     │
│ Owner / estimator                   │
│  [ users                         ▾] │
│                                     │
│ AI risk                             │
│  ☐ Critical ☐ Major ☐ Minor ☐ None  │
│                                     │
│ Existing on board                   │
│  ☐ Hide bids already on my pipeline │
│    (inverse of BC “Show projects    │
│     already on my Bid Board”)       │
│  Default UNCHECKED = show everything│
├─────────────────────────────────────┤
│ How can we improve filters?         │   optional link, can omit
│                                     │
│ [ Save filter ]           [ Apply ] │
└─────────────────────────────────────┘
```

### 3.1 Control mapping from BuildingConnected → us

| Plan Room control | Our control | Notes |
|---|---|---|
| Search area / map | **Omit** | No geo index |
| Work performed / Specialties | Trade focus multi-select | Drywall, Paint, Flooring, Ceilings, Trim, Specialties, Multi |
| Companies | GC / Owner / Architect | Reuse `Company` model; filter `company_type` |
| Bid due date | Bid due date range | Default operator: between; allow open-ended |
| Expected start date | Expected start range | Same date widget |
| View all date filters | Collapse extra dates | Award date, last activity |
| Existing invites checkbox | “Hide already on pipeline” | See §3.2 |
| Saved filters tab | Same | Personal named presets |
| Reset all | Clears draft criteria in the drawer **and** applied query | Does not delete saved presets |
| Save filter | Opens name modal, then writes preset | |
| Apply | Commits draft → query | |

Section labels use the company overline style (11px, letter-spacing, muted). Select2 / Tom Select if already in `vendor/`; do not add a new picker library.

### 3.2 “Existing invites” semantics

BuildingConnected is a marketplace: the box shows jobs already on *their* Bid Board.

Our board **is** the pipeline. Useful invert:

- Unchecked (default): list every matching lead.
- Checked **Hide bids already on my pipeline**: only show inbound invitations / plan-room imports that are **not** yet a `BidOpportunity` in New/Invited/Estimating. Only enable this checkbox if Autodesk / BuildingConnected / email ingest already creates a “not yet claimed” row. If that ingest does not exist, **omit the checkbox** rather than shipping a dead control.

If ingest exists (`autodesk_ingestion/` or similar), label:

`Hide jobs already on my Bid Board`

### 3.3 Active chips above the table

After Apply, render chips:

`Trade: Specialties ×`  `Due: 8/25/2026 → … ×`  `GC: Acme ×`

Clicking × removes that criterion and re-applies. **Clear all** next to the chip row.

Status line under the table (same idea as the AutoFilter brief):

`Showing 12 of 84 leads · Filters on: Trade, Bid due` + Clear

---

## 4. Saved filters tab

List the current user’s presets.

Each row:

```
[name]                         [Apply]
  Bid due · Trade · GC          ⋯  Rename / Overwrite with current / Make default / Delete
```

Empty state: “No saved filters yet. Set criteria on the Filter tab, then Save filter.”

**Save filter** flow:

1. User has at least one criterion (else toast: “Add a filter before saving”).
2. Modal: Name (required), ☐ Set as my default view.
3. If name collides, confirm overwrite.
4. Persist and switch to Saved filters tab with the new row selected.

**Default filter:** applied on first load of the leads table for that user. If none, default remains “soonest bid due, hide Lost/Dead if that chip already exists.”

Do not auto-apply a saved filter when the user already has an explicit query in the URL.

---

## 5. Query contract

Reuse the existing list endpoint. Do **not** invent a second leads API.

Preferred params on `GET /api/bids` or `/crm/leads` (adapt to real names):

| Param | Type | Example |
|---|---|---|
| `q` | string | job / GC search |
| `trade` | csv | `drywall,paint,specialties` |
| `company_id` | csv of UUIDs | |
| `sector` | csv | `commercial,government` |
| `stage` | csv | `invited,estimating` |
| `due_from` / `due_to` | ISO date | |
| `start_from` / `start_to` | ISO date | |
| `value_min` / `value_max` | number | |
| `owner_id` | csv | |
| `ai_risk` | csv | `critical,major` |
| `hide_on_board` | bool | only if ingest exists |
| `sort` | string | `due_date.asc` (default) |
| `saved_filter_id` | uuid optional | analytics only; still send explicit params |

Server filter if the list is already paginated. Client filter only if the page already loads the full pipeline for the user (typical < a few hundred).

Column AutoFilter (`table_autofilter_leads_estimates_cursor.md`) is **in-grid refinement**. Drawer filters are the **list query**. On Apply from the drawer, reset in-grid column filters so the two systems do not stack invisibly. Document that in a one-line comment on the table init.

If AutoFilter is not built yet, ship the drawer first. Do not block this ticket on MUI DataGrid work.

---

## 6. Persistence

### 6.1 Applied query

- Mirror applied filters in the URL query string so a PM can copy a link.
- Also write `localStorage` key `crm.leads.query` as a fallback when the list is opened with no params.

### 6.2 Named saved filters (required for “Saved filters”)

localStorage-only is **not** enough — estimators switch machines.

Add a thin model. Do not overload `BidOpportunity`.

```python
class SavedListFilter(db.Model):
    id = db.Column(UUID, primary_key=True)
    user_id = db.Column(FK User, nullable=False, index=True)
    table_key = db.Column(String(64), nullable=False)  # 'crm.leads'
    name = db.Column(String(80), nullable=False)
    query_json = db.Column(JSONB, nullable=False)      # same shape as query params
    is_default = db.Column(Boolean, default=False)
    created_at / updated_at
```

Unique `(user_id, table_key, name)`.  
At most one `is_default=True` per `(user_id, table_key)`.

Endpoints (under existing CRM blueprint):

- `GET    /api/saved-filters?table_key=crm.leads`
- `POST   /api/saved-filters`
- `PATCH  /api/saved-filters/<id>`
- `DELETE /api/saved-filters/<id>`

Audit log create/update/delete. No new AI calls.

`table_key` is forward-compatible (`estimating.list` later) but **only implement `crm.leads` now**.

---

## 7. Front-end implementation (W3CRM)

Preferred files (search first):

- `templates/crm/_leads_filter_drawer.html` — offcanvas markup
- `templates/crm/_leads_filter_chips.html` — chip row
- `static/js/crm-leads-filters.js` — draft state, apply, save, URL sync
- `static/scss/_company-overrides.scss` — drawer + chip styles only
- Flask routes on the existing CRM / bids blueprint

Vanilla JS module pattern already used on staff pages (jQuery is fine if the page already loads it).

Draft state lives in JS until Apply. Typing in the drawer must not hit the API on every keystroke. Debounce search inside the drawer only for typeahead options (companies), not for the leads list.

DataTables (if that is the table):

- On Apply, set `ajax.data` / reload, **or**
- If client-side rows: use `$.fn.dataTable.ext.search` plus a custom filter function that reads the applied query.

Do not initialize a second DataTable.

Select2 multi-selects: reuse vendor build. Placeholder copy:

- Work performed: `Specialties`
- Companies: `Company`

Date inputs: existing daterangepicker / flatpickr / `<input type="date">` — whichever the repo already uses. Match Bid due widget to the screenshot pattern: start → end with a shared “Bid due date” label.

---

## 8. Visual rules (company layer)

- Drawer background `$company-paper`, header border-bottom `$company-border`
- Tab underline = `$company-primary` (not W3CRM orange)
- Primary footer button = `btn btn-primary` → Apply
- Save filter = `btn btn-outline-primary`
- Reset all = `btn btn-link`
- Active Filter button on the toolbar: outline + badge
- Chips: 1px border, 16px height-ish, × target ≥ 24px
- No gradient header on the offcanvas
- No “Give feedback” footer unless a feedback endpoint already exists — omit rather than dead-end

Mobile: offcanvas is full-width. Apply stays sticky at the bottom. Table remains the `md+` power view; Kanban / cards stay the phone default.

---

## 9. What not to touch

- ChatBot modes and `aiReviewBus.ts`
- RFP comparison table
- Estimating takeoff totals logic
- Kanban drag-and-drop, win-probability scoring, proposal PDF
- Theme switcher / DexignZone demo panel (owned by the UI consistency brief)
- Building a fake map
- Company-wide shared filter marketplace

---

## 10. Implementation order

1. Find the real leads list template + list endpoint + JS init. Note filenames in the commit message.
2. Add query-param parsing on that endpoint for the fields in §5 (only fields the model already has).
3. Drawer partial + toolbar Filter button + Apply / Reset.
4. Chip row + showing-X-of-Y line.
5. `SavedListFilter` model + four endpoints.
6. Saved filters tab + toolbar Saved ▾ shortcut + default-on-load.
7. URL sync + `crm.leads.query` localStorage fallback.
8. Wire Kanban to the **same query** if both views share a page (optional but preferred).
9. Manual pass on tablet + 13" laptop.

---

## 11. Acceptance checks

- [ ] Filter button opens a right drawer with Filter | Saved filters tabs
- [ ] Reset all clears drawer + applied query + chips; saved presets remain
- [ ] Apply filters the leads table; badge count matches active criteria
- [ ] Trade, company, sector, stage, bid due, expected start, value, owner, AI risk work when those columns exist
- [ ] No map control shipped
- [ ] “Already on board” checkbox only appears if ingest exists
- [ ] Save filter stores a named preset for the current user and survives reload on another browser session
- [ ] Saved ▾ applies a preset without opening the drawer
- [ ] Default preset runs on first visit with an empty URL
- [ ] Copied URL reproduces the filter
- [ ] Kanban toggle still works
- [ ] Column AutoFilter brief not blocked; if both exist, drawer Apply clears in-grid filters
- [ ] No React/MUI scaffolding added for this ticket
- [ ] xAI/Grok + ChatBot + RFP untouched
- [ ] Lost/Dead default hide behavior (if it already exists) is unchanged unless the user filters Stage to include them

---

## 12. Suggested copy

| UI | Copy |
|---|---|
| Toolbar button | Filter |
| Drawer title | Filter |
| Tabs | Filter · Saved filters |
| Header action | Reset all |
| Footer | Save filter · Apply |
| Save modal title | Save filter |
| Save modal field | Filter name |
| Save modal check | Set as my default view |
| Empty saved | No saved filters yet. Set criteria, then Save filter. |
| Chips clear | Clear all |
| Status | Showing {n} of {total} leads |
| Hide-on-board | Hide jobs already on my Bid Board |

Do not label the feature “BuildingConnected” or “Plan Room” in the product UI. Those names are the reference only.

---

## 13. Relationship to other briefs

| Brief | Relationship |
|---|---|
| `table_autofilter_leads_estimates_cursor.md` | Column header sort/filter. Complementary. Drawer is the list query. |
| `ui_consistency_modernization_cursor.md` | Stack + tokens. This drawer uses those tokens. |
| Page 7 CRM module notes | Pipeline stages, trades, AI reviewer — do not restyle the AI sidebar here. |

If Cursor has already started a MUI DataGrid AutoFilter on a fictional `LeadBidManagement.tsx`, **stop and retarget** the real Flask/Jinja leads table. Do not keep both UIs.
