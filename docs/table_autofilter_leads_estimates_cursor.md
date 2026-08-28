# Cursor Implementation Brief — Excel-style AutoFilter on Leads + Estimate Tables

**Date:** 2026-08-27  
**Module:** Shared table UX (CRM Leads/Bids + Estimating)  
**Owner company:** Finish-work subcontractor, CA commercial + government work

Excel AutoFilter = sort + filter controls **nested in the column header** (dropdown / funnel), not a separate filter bar only. Implement that pattern on the **Leads/Bids table** and the **Estimate tables**. Do not rebuild those modules.

---

## 0. Non-negotiable rules

- Keep xAI/Grok integration untouched.
- Do not regress RFP, DrawingViewer, ChatBot, `aiReviewBus.ts`, Financials, Documents, Scheduling, workflow engine, POs, or Submittals.
- Prefer MUI. Reuse the existing **RFP list DataGrid pattern** (see `purchase_order_material_tracking_cursor.md` and `submittal_qc_process_cursor.md`).
- No Jinja2 in `.tsx`.
- Incremental. Ask before inventing a filename if a close equivalent already exists.
- Do **not** replace MUI DataGrid with AG Grid or Handsontable in this pass.
- Do **not** add AutoFilter to every grid in the app. Scope is **Leads/Bids table views** and **Estimate tables only**.
- Kanban on CRM stays. AutoFilter is for the **table toggle**, not the Kanban board.
- Do not change Estimating AI sidebar, Cost Library, markup sliders, or “Pull from Drawing” behavior.

---

## 1. What to build

Add Excel-like **header AutoFilter** to these tables:

### A. Leads / Bids table (CRM)

Target pages / components (use existing names if they differ — search first):

- `src/pages/CRM/LeadBidManagement.tsx` (or equivalent CRM list)
- Table view inside the existing Kanban / Table toggle
- Any standalone `BidTable.tsx` / `LeadTable.tsx` / `BidOpportunityDataGrid.tsx`

If the table view does not exist yet and only Kanban exists: add a **Table** toggle that uses MUI DataGrid with AutoFilter. Do not remove Kanban.

### B. Estimate tables

1. **Estimate list** (all estimates / bids-with-estimates) if a list page exists  
   e.g. `src/pages/Estimating/EstimatingPage.tsx` list mode, `EstimateList.tsx`
2. **Takeoff / line-items table** (the working estimate)  
   e.g. `src/components/Estimating/TakeoffTable.tsx`

If the takeoff table is a custom `<Table>` instead of DataGrid: migrate **that table only** to MUI DataGrid (Community is fine; Pro if already in package.json). Do not migrate unrelated tables.

---

## 2. UX — what “AutoFilter” means here

Each eligible column header must offer, in one nested control:

1. Sort A→Z / Z→A (or smallest→largest)
2. Clear sort
3. Filter by value / text / number / date (operators depend on column type)
4. Clear filter on that column
5. Visual state:
   - Default: sort indicator only when sorted
   - Filtered column: funnel / filter icon in the header (Excel behavior)
   - Tooltip on hover: current filter summary, e.g. `Trade = Drywall` or `Due date before 2026-09-15`

Keep any existing **toolbar chip filters** (Status, Trade, Gov/Commercial, Due Date). Those are quick views. Header AutoFilter is the power tool. Both can be active; header filters refine the current chip set.

**Do not** put a permanent Excel-style second header row of empty filter boxes on mobile.

### Desktop / tablet

- Column menu (MUI default `⋮`) **or** a compact filter icon in the header — either is fine.
- Prefer showing the filter icon when `filterable: true` so users discover it without opening the menu.
- Horizontal scroll with **sticky first column** on wide takeoff tables (CSI / Description stays visible).

### Mobile

- Do **not** rely on tiny header menus as the only path.
- Keep DataGrid if it already works on tablet.
- On narrow screens: “Sort & Filter” button opens a bottom sheet listing filterable columns.
- Leads on mobile may stay card/Kanban-first; table AutoFilter is required at `md+`.

---

## 3. Shared implementation (do this once)

Create a small shared helper so Leads and Estimating do not copy-paste grid props.

**Preferred files** (search first; reuse if present):

- `src/components/Tables/useAutoFilterGrid.ts`
- `src/components/Tables/autoFilterColumnDefaults.ts`
- `src/components/Tables/FilterActiveHeaderIcon.tsx` (optional; only if default DataGrid icon is insufficient)

`useAutoFilterGrid` should return the common DataGrid props:

```ts
{
  sortingOrder: ['asc', 'desc', null],
  disableColumnFilter: false,
  disableColumnMenu: false,
  disableColumnSelector: false,
  filterDebounceMs: 150,
  slotProps: {
    columnMenu: { /* keep sort + filter + hide column */ },
  },
}
```

Also persist per-table UI state:

| Key | Persist |
|---|---|
| `sortModel` | `localStorage` key `grid:${tableId}:sort` |
| `filterModel` | `localStorage` key `grid:${tableId}:filter` |
| `columnVisibilityModel` | `localStorage` key `grid:${tableId}:cols` |

`tableId` examples:

- `crm.leads`
- `estimating.list`
- `estimating.takeoff:${estimateId}`

Restoring state on mount is required. A “Reset columns” action in the toolbar clears persistence for that `tableId`.

Do **not** persist filters in the URL unless the page already uses search params for list filters. If it does, keep chips in the URL and header AutoFilter in localStorage so shareable links stay simple.

---

## 4. Column matrix

Set `filterable` / `sortable` explicitly. Do not leave every column filterable (IDs, action buttons, AI dots-only columns can sort but usually should not filter).

### 4.1 Leads / Bids table

| Column | Sort | Filter | Operator style |
|---|---|---|---|
| Job / Bid name | Yes | Yes | text contains |
| GC / Client | Yes | Yes | text / value list if low cardinality |
| Stage | Yes | Yes | value list (New, Invited, Estimating, Submitted, Awarded, Lost) |
| Trade focus | Yes | Yes | value list (Drywall, Paint, Flooring, Ceilings, Trim, Multi) |
| Sector | Yes | Yes | value list (Commercial, Government) |
| Bid due date | Yes | Yes | date (on / before / after / between) |
| Value / range | Yes | Yes | number (greater than, less than, between) |
| Win probability % | Yes | Yes | number |
| Owner / estimator | Yes | Yes | value list |
| Status / urgency | Yes | Yes | value list |
| AI risk / severity | Yes | Yes | value list (Critical, Major, Minor, None) |
| Actions | No | No | — |

Default sort: bid due date ascending (soonest first). Hide expired Lost/Dead behind a chip by default if that chip already exists; do not invent a new pipeline.

### 4.2 Estimate list (if present)

| Column | Sort | Filter | Operator style |
|---|---|---|---|
| Estimate # / name | Yes | Yes | text |
| Project / Bid | Yes | Yes | text |
| GC | Yes | Yes | text / value list |
| Status | Yes | Yes | value list (Draft, Under Review, Submitted, Awarded, Lost) |
| Bid due | Yes | Yes | date |
| Grand total | Yes | Yes | number |
| Version | Yes | Yes | number or value list |
| Updated | Yes | Yes | date |
| Actions | No | No | — |

### 4.3 Takeoff / line-items table

| Column | Sort | Filter | Operator style |
|---|---|---|---|
| CSI / Division | Yes | Yes | text + value list if divisions are known |
| Trade | Yes | Yes | value list |
| Location / Room | Yes | Yes | text contains |
| Description | Yes | Yes | text contains |
| Qty | Yes | Yes | number |
| Unit | Yes | Yes | value list (SF, LF, EA, SQ, GAL, …) |
| Unit cost | Yes | Yes | number |
| Vendor quote | Yes | Yes | number; also “has vendor quote” / “empty” if easy |
| Extended total | Yes | Yes | number |
| Markup % | Yes | Yes | number |
| AI flag / severity | Yes | Yes | value list |
| Linked drawing | Yes | Yes | text / “has link” |
| Actions / pull-from-drawing | No | No | — |

Filtering rows must **not** destroy unsaved inline edits. If the takeoff grid autosaves per cell, keep that. Filtered-out rows stay in the estimate; they are only hidden in the view.

**Totals:** the summary panel (grand total, trade breakdown, markups) continues to use **all line items**, not only visible filtered rows — unless you add an explicit toggle “Totals follow filter” (off by default). Estimators must not think a filter deleted scope.

Show a small line under the grid when filters are active:

`Showing 18 of 64 lines · Filters on: Trade, AI flag` + Clear

---

## 5. Data / API

### Leads table

- If the current CRM list already loads the full pipeline for the user: **client** filter + sort is acceptable (typical < a few hundred bids).
- If the API is already paginated: switch that grid to `sortingMode="server"` and `filterMode="server"`. Map DataGrid `filterModel` / `sortModel` to existing query params. Do not invent a second list endpoint if `/api/bids` (or equivalent) can take `q`, `stage`, `trade`, `due_before`, `sort`.

### Estimate list

Same rule: client if small; server if paginated.

### Takeoff table

**Client filter + sort only** for v1. One estimate’s lines stay in memory. Do not send every keystroke to Flask.

Do **not** add new SQLAlchemy models for this feature.

Optional later (out of scope unless already trivial): save a named filter preset on the Estimate (`view_prefs` JSON). Skip in v1; localStorage is enough.

---

## 6. MUI DataGrid specifics

Use the grid already in the project (`DataGrid` or `DataGridPro`). Detect from `package.json`.

Required column fields for filterable columns:

```ts
{
  field: 'trade',
  headerName: 'Trade',
  flex: 1,
  minWidth: 120,
  sortable: true,
  filterable: true,
  type: 'singleSelect', // when value list
  valueOptions: ['Drywall', 'Paint', 'Flooring', 'Ceilings', 'Trim', 'Other'],
}
```

Type mapping:

- text → `type: 'string'`
- money / qty / % → `type: 'number'`
- dates → `type: 'date'` (store real `Date` objects in the row model, not raw strings)
- chips / stages / trades → `type: 'singleSelect'` + `valueOptions`
- AI severity → `singleSelect`

For currency columns keep existing formatters (`valueFormatter`) so filter still uses the numeric value.

If Pro is installed, you may use the quick filter in the toolbar **in addition to** column AutoFilter. Do not make quick filter the only filter.

Header height: keep current density. Estimating takeoff should stay compact (`density="compact"` if already used).

---

## 7. What not to touch

- ChatBot modes (`construction_review`, `estimating_review`, `bid_feasibility_review`)
- `aiReviewBus.ts`
- RFP comparison table (out of scope this ticket — even though it would benefit later)
- PO register, Submittal register (already have chip filters; do not expand scope)
- Kanban drag-and-drop, win probability scoring, proposal PDF generation
- Cost library panel
- Offline / Dexie work unless the table already hydrates from IndexedDB — then persist filter state the same as other UI state

---

## 8. Implementation order

1. Search repo for existing CRM table and `TakeoffTable` / estimate DataGrid. Reuse filenames.
2. Add `useAutoFilterGrid` + persistence helper.
3. Wire Leads/Bids **table view**.
4. Wire Estimate list if it exists.
5. Wire TakeoffTable. Preserve inline edit, vendor quote column, AI flag column, “Pull from Drawing”.
6. Add “filters active” status line + Clear on takeoff.
7. Mobile bottom sheet for Leads table and takeoff at `sm` breakpoint.
8. Manual pass: sort, filter, clear, persist reload, totals ignore takeoff filter, Kanban still works.

---

## 9. Acceptance checks

- [ ] Leads table headers open sort + filter without leaving the page
- [ ] Filtered lead columns show a funnel / active-filter affordance
- [ ] Stage / trade / sector filters are value lists, not free-text only
- [ ] CRM Kanban toggle still works; AutoFilter is not required on cards
- [ ] Takeoff columns sort and filter; action columns do not
- [ ] Filtering takeoff lines does not change saved estimate totals
- [ ] Status line shows “Showing X of Y lines” when takeoff filters are on
- [ ] Reload restores last sort/filter for that table
- [ ] “Reset columns” clears saved sort/filter/visibility
- [ ] Inline takeoff edits still save
- [ ] Purple AI review / ChatBot sidebar unchanged
- [ ] No new backend models
- [ ] MUI only; no AG Grid introduced

---

## 10. Suggested copy (toolbar)

On both tables, if a toolbar exists, add:

- **Reset view** — clears header filters, sort, hidden columns for this table
- Existing chip filters stay where they are

Do not label the feature “AutoFilter” in the UI. Users know it as filter/sort on the column. Internal comments / this brief may say AutoFilter.

---

## 11. If files are missing

If `TakeoffTable.tsx` or the CRM table view does not exist yet:

- Create the thinnest DataGrid wrapper that matches Page 2 (Estimating) and Page 7 (CRM) layouts in the attached module notes.
- Still embed existing `ChatBot.tsx` in the estimating sidebar and CRM AI panel. Do not fork ChatBot.

If you are unsure whether a page is “the leads table,” prefer the CRM pipeline table toggle over contacts-only directories.
