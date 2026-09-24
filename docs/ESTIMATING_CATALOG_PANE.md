# Estimating catalog pane — chrome lock

**Date:** 2026-09-06  
**Trigger:** Live screenshot of the Estimating **right** pane titled Materials. Header already says Materials; a second Materials pill sits under it next to Import / New / Export. Filters is a full-width expander. Buttons are uneven rounded pills.  
**Rule:** This pane is a **picker**. Drag a part or assembly onto a takeoff. Catalog authoring lives in Office → Materials / Assemblies, not here.

Related: `docs/ESTIMATING_WORKSPACE_LAYOUT.md` (three-pane keep plan), `docs/OFFICE_CHROME_AND_MODE_UX.md` (Office Materials / Assemblies editors), `docs/ESTIMATING_IMPLEMENTATION_PLAN.md` (E2 attach part).

This document is **chrome + chrome actions only**. Do not change catalog data, drag-drop apply math, or the Office Materials page.

---

## What is wrong in the screenshot

```
┌─ Materials ──────── Hide ──┐
│ [Materials] [Import] [New] [Export]   ← four fat pills
│ [ Search material               ]     ← tall field
│ ▾ Filters                             ← whole row for a closed expander
│ ▾ Baby Changing Station
│   ┌ BCS-3                           ┐
│   │ Baby Changing Station Horizonta │  ← card chrome, name wraps / clips
│   └─────────────────────────────────┘
│   …
│ Drag a part or assembly
└─────────────────────────────────────┘
```

| Defect | What the screenshot shows |
|---|---|
| Materials twice | Panel title **and** a selected **Materials** button |
| Authoring on a picker | **Import** and **New** on the takeoff rail. Those belong on Office Materials |
| Uneven pills | Materials / Import / New / Export are different widths, large corner radius, sit in a wrapping wrap-panel |
| Filters waste height | A closed “Filters” expander still costs a full row plus padding |
| Search is a second title | Placeholder “Search material” restates the panel name |
| Fat cards | Each SKU is a bordered tile. Name wraps under the SKU and still clips (`Horizonta`, `Changing S`) |
| Export stranded | Last pill on the row, visually equal to New even though it is a rare action |

Do not “shrink the padding” and leave Import / New / the second Materials button.

---

## Target pane

Default width 260–300 px (workspace lock). Header 28 px. Search row 24 px. Filter flyout is **not** a permanent band.

```
┌─ Catalog ────────────────── ⋯ Hide ┐
│ [ Search parts & assemblies ] [Y]  │   Y = filter icon
│ Parts    Assemblies                │   20 px text segments, optional
│                                    │
│ ▾ Baby Changing Station            │
│   BCS-3                            │
│   Baby Changing Station Horizontal │
│   BCS-4                            │
│   Baby Changing Station Horizontal │
│   KB112-01RE                       │
│   Countertop Recessed Changing St. │
│                                    │
│ Drag a part or assembly onto a     │
│ takeoff                            │
└────────────────────────────────────┘
```

When a filter is on, the funnel shows a small count badge. Active filter chips (one line, 18 px) may sit under search; they are not an expander.

---

## Header

- Title: **Catalog**. Not “Materials”, not “Templates, Parts, Inputs”, not “Parts & Assemblies” as a long sentence.
  - “Materials” as the title made the Materials button look like a duplicate.
  - Workspace keep-plan used “Parts & Assemblies” as the product name of this column. That name is the **job** of the pane, not the title string. Title stays short.
- Right of title, same 28 px bar:
  - **⋯** overflow (22×22)
  - **Hide** (already exists — keep; do not restyle into a second title)
- ⋯ menu:
  - Export CSV…
  - Export Excel…  (enable only if the existing Export command exists)
  - Refresh
  - Open Office Materials…   (navigates to Office Materials editor — does **not** open New/Import here)
  - Open Office Assemblies…  (same idea)
- **Delete from this pane:** Import, New, and the Materials pill.
- Do not add Save / New folder / Add / Delete on this rail. Those are Office catalog editor actions.

---

## Search + filter (one row)

- One search box. Placeholder: `Search` — not “Search material”.
- Height 22–24 px. Full remaining width.
- Filter control is a **22×22 icon** on the same row (funnel), not a “Filters” expander.
- Click funnel → flyout (not an in-pane accordion):
  - Category / folder
  - Manufacturer
  - Unit
  - Clear filters
- Flyout uses existing filter fields if they already exist. Do not invent a new query model.
- Match count may sit muted at the right of the search box (`24`) when the query is non-empty.
- Type-ahead filters the grouped list live. Escape clears search.

---

## Parts | Assemblies

Only if the pane already hosts both catalogs (footer already says “Drag a part or assembly”).

- Text segments under the search row, 20 px tall, no pill chrome, no large radius.
- Selected segment: medium weight + 2 px accent underline. Unselected: muted.
- Do **not** label a segment “Materials” if the other is “Assemblies” — use **Parts** and **Assemblies**.
- If the live list is already one mixed tree (folders of parts and assemblies together), **omit the segment row**. One list is better than a fake tab.

---

## List

- Group header: chevron + category name. 22 px. No card.
- Row: two lines, no tile border, no 8 px padding card.
  - Line 1: SKU / item code (`BCS-3`, `KB300-00`), 12 px
  - Line 2: display name, 11 px muted, **one line**, `TextTrimming=CharacterEllipsis`, ToolTip = full name
- Row height 36–38 px for two-line rows (not 56+ card).
- Selected row: accent fill, not a second outline card.
- Drag source unchanged: drag row onto a Takeoff Summary parent or selected measurement.
- Double-click: same as today’s apply-or-preview if one exists; do not invent a New dialog.

---

## Footer

Keep the hint, one or two lines, muted 11 px:

`Drag a part or assembly onto a takeoff`

Do not put Import / New / Export down here either.

---

## What stays in Office

| Action | Where |
|---|---|
| New material / New assembly | Office → Materials / Assemblies |
| Import catalog | Office → Materials |
| Full catalog editor, prices, sheet W×L | Office → Materials |
| Assembly formula editor | Office → Assemblies |

Estimating right pane may **deep-link** to those Office views from the ⋯ menu. It must not grow authoring buttons.

---

## Theme

Same tokens as Estimating workspace (Chat A dark charcoal + steel/teal). If the live app is still the rejected light list, rebuild the **structure** in this pass; do not invent a third palette and do not restyle the whole shell.

---

## Do not

- Keep a Materials button under a Materials (or Catalog) title
- Put New or Import on this pane
- Leave Filters as a full-width expander
- Wrap four commands in Auto-width pills
- Clone PlanSwift Templates / Parts / Inputs tab art
- Change drag-drop apply, waste, or Rigid Sheet math
- Touch the Office Materials page in this pass except the ⋯ deep-link if the navigation command already exists

---

## Acceptance

1. Right pane header shows **Catalog** once. No Materials pill.
2. Import and New are gone from this pane.
3. Export (if it still exists) lives in ⋯, not a fat pill.
4. Search and filter share one 24 px row. Closed filter does not occupy a band.
5. Grouped SKU list is two-line rows; long names ellipsize with a tooltip.
6. Drag a part onto a takeoff parent still works.
7. Office Materials still has New / Import. Those commands were not deleted from the product — only removed from this picker.
