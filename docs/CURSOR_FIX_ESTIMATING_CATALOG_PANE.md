# Cursor — Fix Estimating catalog (right) pane chrome

**Date:** 2026-09-06  
**Spec (locked chrome):** `docs/ESTIMATING_CATALOG_PANE.md`  
**Keep plan:** `docs/ESTIMATING_WORKSPACE_LAYOUT.md` — three panes; this is the RIGHT column only.  
**Office editors stay put:** `docs/OFFICE_CHROME_AND_MODE_UX.md` (Materials / Assemblies New · Import).  
**Why:** Live right rail says **Materials**, then another **Materials** pill next to **Import / New / Export**. Filters is a full-width expander. Buttons are uneven pills. This pane is a **picker**.

**Stack:** WPF .NET 8 at `D:\USISPdfApp`. Chat A dark density.

**How to run:** New Cursor Agent chat. Paste **CP0 first** (preferred one pass). If CP0 is too large, use CP1 → CP3. After each paste: `dotnet build` and `dotnet test`, fix failures, one line in `docs/STATUS.md`.

Do not rebuild Estimating left/center chrome. Do not change drag-drop apply math, waste, Rigid Sheet, catalog records, Ingest, OCR, File Access, or Velopack. Do not delete New / Import from the **Office Materials** page.

---

## What Cursor must build

Live pane (screenshot class):

```
┌─ Materials ──────── Hide ──┐
│ [Materials] [Import] [New] [Export]
│ [ Search material               ]
│ ▾ Filters
│ ▾ Baby Changing Station
│   ┌ BCS-3                           ┐
│   │ Baby Changing Station Horizonta │
│   └─────────────────────────────────┘
│ Drag a part or assembly
└─────────────────────────────────────┘
```

After:

```
┌─ Catalog ────────────────── ⋯ Hide ┐
│ [ Search                    ] [Y]  │
│ ▾ Baby Changing Station            │
│   BCS-3                            │
│   Baby Changing Station Horizontal │
│   BCS-4                            │
│   Baby Changing Station Horizontal │
│ Drag a part or assembly onto a     │
│ takeoff                            │
└────────────────────────────────────┘
```

| Before | After |
|---|---|
| Title **Materials** + pill **Materials** | Title **Catalog** once. No Materials pill |
| Import, New, Export as fat pills | Import + New **gone from this pane**. Export in **⋯** |
| “Filters” expander row | Funnel **icon on the search row**. Flyout, not a band |
| “Search material” | Placeholder **Search** |
| Bordered cards, clipped names | Two-line SKU rows, ellipsis + tooltip |

---

## Locked rules (do not invent others)

1. This pane is a **picker**. Drag a part or assembly onto a Takeoff Summary parent or selected measurement. Authoring is Office.
2. Header title string is **Catalog**. Not “Materials”. Not “Templates, Parts, Inputs”. Not a long “Parts & Assemblies” sentence.
3. **Delete from this pane:** Materials pill/tab, Import, New. Do not hide them in a collapsed panel — remove the controls.
4. **Keep Hide.** Add **⋯** to the left of Hide (22×22).
5. ⋯ menu, in this order, only if the command already exists (disable Export if there is no exporter yet; omit Office links if those views cannot be opened):
   - Export CSV…
   - Export Excel…
   - Refresh
   - Open Office Materials…
   - Open Office Assemblies…
6. Do **not** add Save, New folder, Add, or Delete on this rail.
7. Search + funnel share **one 24 px row**. Closed filter occupies **zero** extra band.
8. Parts | Assemblies text segments (20 px, underline selected, no pills) **only** if the pane already hosts two catalogs and they are not already one mixed tree. Never label a segment “Materials”.
9. List rows are not cards. SKU 12 px + name 11 px muted, one line, `TextTrimming=CharacterEllipsis`, ToolTip = full name. Row height 36–38 px.
10. Footer stays a muted hint: `Drag a part or assembly onto a takeoff`. No buttons in the footer.
11. Drag-drop source, apply, bindings, and catalog IDs **unchanged**.
12. Theme tokens = Estimating workspace. If the live app is still light, rebuild **structure** only. Do not invent a third palette. Do not restyle the whole shell.

---

## FIND FIRST (every prompt)

Search the live repo before writing. Name the files you will edit. Extend them. Do not create a second right pane.

Look for strings from the screenshot:

- `"Materials"` as a panel/header title on the Estimating right column
- Button content `Import`, `New`, `Export` in that same view
- Placeholder `"Search material"`
- Expander / group header `"Filters"`
- Footer `"Drag a part or assembly"`
- Category header like `"Baby Changing Station"`

Likely names: `CatalogPanel`, `MaterialsPanel`, `PartsAssemblies`, `EstimatingRight`, `MaterialPicker`, `CatalogView`.

Also find:

- The **Office** Materials page (must keep its New / Import — different view)
- Existing Export command for the catalog
- Existing filter VM properties (category / manufacturer / unit / folder)
- Drag-drop handler from this list onto Takeoff Summary
- Panel Hide / collapse command already used by this column

If the control lives under a different name, use that name everywhere below.

---

## PROMPT CP0 — Paste this to implement it (preferred)

```
We are building USISPdfApp (WPF .NET 8, Chat A dark professional density).

GOAL
Rebuild the Estimating RIGHT catalog pane chrome. Live screenshot:
title "Materials", then a second Materials pill beside Import / New /
Export, a full-width Filters expander, fat uneven pills, card rows
that clip names. This pane is a PICKER. Authoring stays in Office
Materials / Assemblies.
Spec: docs/ESTIMATING_CATALOG_PANE.md
This prompt pack: docs/CURSOR_FIX_ESTIMATING_CATALOG_PANE.md
Keep plan: docs/ESTIMATING_WORKSPACE_LAYOUT.md (right column only).

FIND THE UI FIRST
Search the repo for:
- panel/header "Materials" on the Estimating right column
- buttons Import, New, Export in that view
- placeholder "Search material"
- expander "Filters"
- footer "Drag a part or assembly"
Likely CatalogPanel / MaterialsPanel / PartsAssemblies /
EstimatingRight / MaterialPicker. Name the XAML + VM you will edit.
Do not create a second pane.
Do not edit the Office Materials page except a ⋯ navigation command
if that navigation already exists.

TASK

1. Header (28px)
   - Title text = "Catalog" (one word).
   - Keep Hide on the header right.
   - Add a 22×22 ⋯ overflow immediately left of Hide.
   - ⋯ menu:
       Export CSV…
       Export Excel…          (existing Export command; disable if none)
       Refresh                (omit if no refresh command)
       Open Office Materials… (omit if that navigation does not exist)
       Open Office Assemblies…(omit if that navigation does not exist)
   - DELETE from this pane: the Materials pill/tab, Import, New.
     Remove the controls. Do not Collapsed-hide them.
   - Do not add Save, New folder, Add, or Delete on this rail.

2. Search + filter — ONE 24px row under the header
   - Placeholder = "Search" (not "Search material").
   - Funnel icon 22×22 on the SAME row. Click opens a Popup/flyout
     bound to the filter fields that already exist (category /
     manufacturer / unit / folder — use today's bindings).
   - DELETE the "Filters" Expander/row. A closed filter must not
     consume a band.
   - Live-filter the grouped list as the user types. Escape clears
     the search box.
   - Optional muted match count in the search row when query is
     non-empty. Badge the funnel when any filter is active.
   - Optional one-line chip row under search when filters are on.
     Still no expander.

3. Parts | Assemblies
   - If this pane already switches two catalogs, put a 20px text
     segment row under search: "Parts" | "Assemblies".
     Selected = medium weight + 2px accent underline.
     No pills, no large corner radius, do NOT label one "Materials".
   - If the list is already one mixed tree, OMIT the segment row.

4. List density
   - Group header: chevron + category name (keep Baby Changing
     Station etc.). 22px. No card.
   - Item rows are NOT bordered tiles.
   - Two lines, NoWrap:
       SKU / item code     12px
       display name        11px muted, CharacterEllipsis,
                           ToolTip = full name
   - Row height 36–38px.
   - Selected row = accent fill, not an outline card.
   - Drag-drop source and apply behavior UNCHANGED. Same bindings,
     same catalog ids.

5. Footer
   - Muted 11px: "Drag a part or assembly onto a takeoff"
   - No buttons in the footer.

6. Rules
   - Tokens = Estimating workspace (Chat A dark + steel/teal).
     If the live app is still light, rebuild STRUCTURE only.
     Do not invent a third palette. Do not restyle the whole shell.
   - Do not change catalog data, waste, Rigid Sheet math, or E2 apply.
   - Do not delete New / Import from Office Materials.
   - Find the existing XAML. Rebuild the header/tool strip.
     Do not wrap the four pills in a Viewbox.
   - dotnet build && dotnet test. Fix failures you cause.

When done, append to docs/STATUS.md:
"Estimating catalog pane cleaned: title Catalog once, no Import/New
on the picker, filter icon on the search row, Export in ⋯, two-line
SKU rows."
```

---

## PROMPT CP1 — Header and actions only

Use if CP0 is too large. Leaves search expander and list cards for CP2/CP3.

```
We are building USISPdfApp (WPF .NET 8, Chat A dark professional density).

GOAL
CP1 only: header + which buttons appear on the Estimating RIGHT
catalog picker. Spec: docs/ESTIMATING_CATALOG_PANE.md
Pack: docs/CURSOR_FIX_ESTIMATING_CATALOG_PANE.md

FIND
Estimating right pane with title "Materials" and pills Materials /
Import / New / Export. Name the view. Do not create a second pane.
Do not touch Office Materials New/Import.

TASK
1. Header title = "Catalog".
2. Keep Hide. Add ⋯ (22×22) left of Hide.
3. ⋯ menu: Export CSV…, Export Excel… (existing command or disable),
   Refresh if it exists, Open Office Materials… / Assemblies… only
   if those navigations already exist.
4. DELETE Materials pill, Import, New from this pane (remove controls).
5. Do not add Save / New folder / Add / Delete.
6. Do not change search, Filters expander, or list rows in this pass.
7. dotnet build && dotnet test.

When done, append to docs/STATUS.md:
"CP1 Estimating catalog header: Catalog + ⋯ + Hide; Import/New/Materials
pill removed from the picker."
```

---

## PROMPT CP2 — Search + filter on one row

Depends on CP1.

```
We are building USISPdfApp (WPF .NET 8).

GOAL
CP2: collapse search + filter on the Estimating RIGHT catalog pane
to one 24px row. Spec: docs/ESTIMATING_CATALOG_PANE.md

FIND
The pane CP1 just retitled Catalog. Placeholder "Search material"
and expander "Filters".

TASK
1. Placeholder = "Search".
2. Funnel 22×22 on the same row as search. Click = Popup flyout of
   existing filter fields (category / manufacturer / unit / folder).
3. DELETE the Filters expander/row. Closed filter = zero extra band.
4. Type-ahead filters the list. Escape clears search.
5. Badge the funnel when filters are active. Optional match count
   in the search row. Optional chip line when filters are on.
6. Parts | Assemblies 20px underline segments ONLY if two catalogs
   are already hosted and not one mixed tree. Never say "Materials".
7. Do not change list card chrome in this pass.
8. dotnet build && dotnet test.

When done, append to docs/STATUS.md:
"CP2 Estimating catalog search+funnel share one row; Filters expander
removed."
```

---

## PROMPT CP3 — List density + footer

Depends on CP1 (CP2 preferred).

```
We are building USISPdfApp (WPF .NET 8).

GOAL
CP3: dense two-line SKU rows on the Estimating RIGHT catalog picker.
Spec: docs/ESTIMATING_CATALOG_PANE.md

FIND
The Catalog pane list. Group headers like "Baby Changing Station".
Card-like items with SKU + wrapped/clipped name. Footer "Drag a part
or assembly".

TASK
1. Group header stays chevron + category, 22px, no card.
2. Item = two lines, no tile border:
     SKU 12px
     name 11px muted, one line, CharacterEllipsis, ToolTip=full name
   Row height 36–38px.
3. Selected row = accent fill, not an outline card.
4. Drag-drop apply UNCHANGED.
5. Footer muted: "Drag a part or assembly onto a takeoff". No buttons.
6. dotnet build && dotnet test.

When done, append to docs/STATUS.md:
"CP3 Estimating catalog rows are two-line SKU+name, no card chrome."
```

---

## Acceptance

1. Right pane header shows **Catalog** once. No Materials pill.
2. Import and New are not on this pane. They still exist on Office Materials.
3. Export (if it exists) is in ⋯, not a pill.
4. Search and filter share one 24 px row. Closed filter is not a band.
5. Grouped SKU list is two-line rows; long names ellipsize with a tooltip.
6. Drag a part onto a takeoff parent still works.
7. `dotnet build` and `dotnet test` pass.

---

## Out of scope

- Office Materials / Assemblies editor layout
- Takeoff item dialog (`docs/TAKEOFF_ITEM_DIALOG.md`)
- Rigid Sheet math (`docs/RIGID_SHEET_TAKEOFF.md`)
- Takeoff Summary left tree
- New catalog fields, prices, or import pipeline
