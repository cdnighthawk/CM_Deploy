# Cursor Implementation Brief — Project Details Toolbar (Grouped Split Buttons)

**Date:** 2026-08-30  
**Repo:** `CM_Deploy`  
**Website product:** **USIS CM** (not FinishWorks)  
**Scope:** **Project-details page chrome only.** The horizontal project tool strip.  
**Status:** Authoritative for this strip. Do not expand into site nav, field app, or module rebuilds.

---

## 0. What this ticket is

Replace the busy single-row project tool strip:

`Job information · Schedule · Tasks · Drawings · Specs · Takeoff · Estimate · RFIs · Submittals · Procurement · Invoicing · Contract admin · Job costing · Safety · Correspondence` + right-side **Contract admin hub**

with **six split parents**. Clicking the parent label opens a **default child page**. The caret opens the other children.

This is **navigation chrome**. Existing pages, routes, APIs, and modules stay. You are regrouping links, not building new tools.

---

## 1. Hard scope

**In scope**

- The project-details page header / tool strip only (the bar in the screenshot).
- Markup + a small amount of JS for active-parent state.
- Remove the separate **Contract admin hub** control on that same bar.

**Out of scope — do not touch**

- Left W3CRM sidebar / deznav
- Dashboard, CRM leads list, RFP list (except linking to the existing RFP page from this menu)
- DrawingViewer canvas / calibration
- ChatBot, Grok, `aiReviewBus`, Local AI button internals
- Estimating takeoff math, sliders, cost library
- RFP quote math, public portal, comparison table
- Submittal QC engine, PO workflow, correspondence ingest
- Field app / bottom nav
- React / MUI / new page trees
- New “hub” landing pages for Files / Estimate / Field / Buyout / Contract

If a parent has no dedicated hub route today, **do not create one**. Parent click goes to the default child URL that already exists.

---

## 2. Stack

Staff UI is **W3CRM + Bootstrap 5 + gulp file-includes + `usis-ui.css` LAST + `window.USISUi`**.

- Use Bootstrap 5 `btn-group` + `dropdown-toggle-split` (or the existing W3CRM dropdown used on construction headers). Do not invent a React tab bar.
- Tokens: active parent = primary `#1F4E5F`. Do not use AI purple `#6D28D9` on these tabs.
- One contained primary on the whole bar = the **active parent**. Children in the menu are plain links.
- Do not rewrite `style.css`. If the bar goes cyan `#0D99FF`, the pin order is wrong — fix pin, do not retheme.

---

## 3. Find the real file first

Search the repo before adding a sibling template. Likely names (use what exists):

```
gulp/src/**/project*.html
gulp/src/construction/*
header-construction.html
usis-project*.html
project-detail / project-details / project.html
any include that renders the tool strip labels
  "Job information", "Contract admin", "Takeoff"
```

Edit **src** and copy the same HTML/JS into **dist** if this repo patches dist HTML directly. Do not `gulp-clean` dist.

Do **not** change a global header include if that include is shared with pages that are not project-details. If the strip lives in a shared partial used everywhere, either:

1. Gate the new markup with a project-details body class / page id, or
2. Split a `project-tools.html` include and attach it only on project-details.

Default: only the project-details page receives the grouped bar.

---

## 4. Information architecture (locked)

Seven parents, left to right: **Contract · Files · Submittals · RFIs · Preconstruction · Buyout · Field**. Label click = default child. **Submittals** and **RFIs** sit on the parent row so they are one click. Children of the active parent render as a **visible row** (not a caret dropdown). On Submittals or RFIs, the Buyout child row still shows.

| Parent | Label click opens | Children (order) |
|---|---|---|
| **Contract** | Job information | Job information · Open items · Contract admin · Job costing · Invoicing |
| **Files** | Drawings | Drawings · Specs · Documents |
| **Submittals** | Submittals | Same Buyout child row |
| **RFIs** | RFIs | Same Buyout child row |
| **Preconstruction** | Estimate | Estimate · Takeoff · RFP |
| **Buyout** | Procurement | Procurement · Submittals · RFIs · Correspondence · Transmittals · Anticipated costs · PO change orders · Sub invoices |
| **Field** | Schedule | Schedule · Tasks · Photos · Daily log · Meetings · Work orders · QC checklists · Punchlist · Incidents · Safety |

Do not add remaining Sage leftovers (directory, journals, bills, permits, ITB, timecards, …) until they have a real page. Do not put these children on the left sidebar **Projects** link — that stays the job list.

### Routing rules

- Reuse **existing** project-scoped URLs. Do not invent `/files` or `/buyout` hubs.
- **Documents** = existing Documents Hub for this project, not a new library.
- **RFP** = existing RFP list/detail **filtered or scoped to this project** if that query already exists. If RFP is only a global list, link to the existing RFP list with `project_id` (or current query param the list already understands). Do not clone RFP.
- **Correspondence** = existing project correspondence file register. Do not build chat.
- **Submittals** = existing submittal register for the project.
- **RFIs** = existing RFI page for the project. If RFIs are not built yet, still add the menu item and point at the current placeholder / 404-free existing route. Do not scaffold a new RFI module in this ticket.

### Removed from the strip

- Flat peers: Takeoff, Specs, Drawings, Schedule, Tasks, Safety, RFIs, Submittals, Invoicing, Job costing, Correspondence (they become children).
- Right-side button **Contract admin hub**. Contract parent *is* that page.

---

## 5. Interaction

### Split control

Each parent is a split button:

```
[  Files  | ▾ ]
```

- Click **Files** → navigate to Drawings for the current project.
- Click **▾** → open dropdown; do not navigate until a child is chosen.
- Click a child → navigate to that child.
- Dropdown is **click**, not hover (tablet in the trailer).
- `data-bs-auto-close="true"`. Only one dropdown open at a time.

### Active state

- If the current route is any child of a parent, that **parent** is active (filled primary pill, same treatment Contract admin has today).
- In the open menu, the current child gets `active` / `aria-current="page"`.
- Do not highlight two parents at once.

### Defaults are fixed

Parent click **always** goes to the default in the table above.

Do **not** persist “last child” in localStorage for this ticket. Files always opens Drawings. Estimate always opens Estimate.

### Right side of the bar

After removing Contract admin hub, leave that slot empty **or** use it only for a page-level action that already exists on the child view (do not add a new CTA in this ticket). Never two solid primaries in the strip.

### Responsive

- Target: one row, six parents, no wrap at ≥1280px.
- At narrower widths the strip may scroll horizontally inside the bar (`overflow-x: auto`). Do not wrap to two rows. Do not add a website bottom nav.

---

## 6. Markup sketch (adapt to the real classes)

Use the existing nav/pills classes on that bar. Shape only:

```html
<nav class="usis-project-tools" aria-label="Project tools">
  <!-- repeat per parent; Files example -->
  <div class="btn-group usis-project-tool">
    <a class="btn usis-project-tool__label"
       href="{projectDrawingsUrl}">Files</a>
    <button type="button"
            class="btn dropdown-toggle dropdown-toggle-split usis-project-tool__caret"
            data-bs-toggle="dropdown"
            data-bs-auto-close="true"
            aria-expanded="false"
            aria-label="Files pages">
      <span class="visually-hidden">Files pages</span>
    </button>
    <ul class="dropdown-menu">
      <li><a class="dropdown-item" href="{projectDrawingsUrl}">Drawings</a></li>
      <li><a class="dropdown-item" href="{projectSpecsUrl}">Specs</a></li>
      <li><a class="dropdown-item" href="{projectDocumentsUrl}">Documents</a></li>
    </ul>
  </div>
  <!-- Job, Estimate, Field, Buyout, Contract -->
</nav>
```

Wire `href`s from the same helpers / template vars the flat links use today. Do not hard-code a second set of paths.

Mark the active parent with a class already used on the strip (e.g. the filled Contract admin pill). Prefer adding `usis-project-tool--active` in the include if JS is easier than server-side path matching.

Small JS is allowed on this page only:

- Compare `location.pathname` (or existing project-tab key) to a child→parent map.
- Toggle `--active` on the matching parent and `active` on the matching dropdown item.

Do not put this map in a global `usis-ui.js` unless the file is already the home for page chrome. Prefer a page script next to the existing project-details JS.

---

## 7. Child → parent map (for active state)

```
job information, job overview, project overview  → Job
open items, openitems                             → Job
contract admin, contract-admin, contract hub      → Job
job costing, costing, job-cost                    → Job
invoicing, invoices, billing                      → Job

drawings, drawing-viewer, sheets                  → Files
specs, specifications                             → Files
documents, documents hub, files register          → Files

estimate, estimating                              → Preconstruction
takeoff                                           → Preconstruction
rfp, rfps                                         → Preconstruction

procurement, purchase orders, pos                 → Buyout
submittals, submittal-qc, submittal register      → Buyout
rfis, rfi                                         → Buyout
correspondence, teams archive, email register     → Buyout
transmittals                                      → Buyout
anticipated costs, anticipated                    → Buyout
po change orders, poco                            → Buyout
sub invoices, subinv                              → Buyout

schedule, calendar (project)                      → Field
tasks, task list                                  → Field
safety                                            → Field
daily log, dailylog, daily reports                → Field
photos                                            → Field
meetings                                          → Field
work orders, wo                                   → Field
punchlist, punch                                  → Field
incidents, safety incidents                       → Field
qc checklists, qc                                 → Field
```

Match on the **real** path segments in this repo. Adjust the map after you search; do not invent URLs to satisfy the names above.

---

## 8. Visual / a11y

- Parent labels: existing strip font size and padding. Do not shrink to cram six + carets.
- Caret hit target ≥ 32px wide.
- Dropdown width ≥ 160px, left-aligned to the parent.
- `aria-label` on each caret (`Files pages`, `Estimate pages`, …).
- Keyboard: Tab to label (Enter = default child), Tab to caret (Enter / Space = menu), Esc closes.
- Do not use hover-only open.

Style leftovers with `usis-ui.css` page-scoped rules if the default Bootstrap split looks wrong next to the old pills. Keep radius / divider tokens. No new design system.

---

## 9. Do not regress

- Every old strip target must still be reachable in one caret click + one child click.
- Deep links to Takeoff, Drawings, Submittals, etc. still work. Only the bar changes.
- DrawingViewer, Estimate workspace, RFP module, Submittal QC, POs, Correspondence register — unchanged internally.
- xAI / Grok untouched.
- Purple “Review with Local AI” on child pages stays purple and stays off this strip unless it was already there as a page action.

---

## 10. Acceptance

1. Project-details bar shows seven parents: Contract, Files, Submittals, RFIs, Preconstruction, Buyout, Field. No Daily row.
2. Files label opens Drawings. Preconstruction label opens Estimate. Contract → Job information. Field → Schedule. Buyout → Procurement. Submittals and RFIs open those pages in one click.
3. The child row lists only the children in §4, in that order, for the active parent.
4. On Drawings / Specs / Documents, **Files** is the active parent.
5. On Takeoff / Estimate / RFP, **Preconstruction** is the active parent. On Submittals, **Submittals** is the active parent (Buyout child row still shows). On RFIs, **RFIs** is the active parent (Buyout child row still shows). On Daily log / Photos / Meetings / Work orders / Punchlist / Incidents / QC, **Field** is the active parent. On Anticipated costs / PO COs / Sub invoices, **Buyout** is the active parent. On Contract admin / Job costing / Invoicing / Open items, **Contract** is the active parent.
6. **Contract admin hub** is gone from this page.
7. Left sidebar, CRM, dashboard, public portal, field app — unchanged.
8. No new React/MUI files. No new hub routes. No gulp-clean of dist.

---

## 11. Suggested commit

`fix(ui): group project-details tools into six split parents`

---

## 12. Cursor guardrails (copy)

```
Only the project-details tool strip.
W3CRM + Bootstrap 5 split dropdowns. No React/MUI.
No new hub pages. Parent click = default child URL that already exists.
Files → Drawings. Estimate → Estimate. Contract → Contract admin.
Remove Contract admin hub button.
Do not change sidebar, Grok, DrawingViewer canvas, RFP math, or field app.
If primary goes cyan #0D99FF, fix usis-ui.css pin order.
```
