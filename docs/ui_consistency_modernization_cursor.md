# Cursor Implementation Brief — UI Consistency & Modern Look-and-Feel Pass

**Date:** 2026-08-27  
**Module:** Cross-cutting design system (theme, layout chrome, shared components)  
**Owner company:** Finish-work subcontractor, CA commercial + government work

The app currently reads as **cheap and inconsistent**: mixed spacing, mixed button variants, one-off colors, uneven AppBars, default MUI density, and pages that do not share a single visual language. This brief is a **visual + component-system pass only**. Do not rebuild modules. Do not change business logic.

Goal: one modern, quiet, construction-ops product — closer to Linear / Notion / Procore-clean than to a Bootstrap admin template.

---

## 0. Non-negotiable rules

- Keep xAI/Grok integration untouched.
- Do **not** regress RFP, DrawingViewer, ChatBot, `aiReviewBus.ts`, Estimating, CRM, Financials, Documents, Scheduling, workflow engine, POs, or Submittals.
- Prefer MUI. Do **not** add a second UI kit (Chakra, Ant, Tailwind component library, shadcn as a parallel system).
- No Jinja2 in `.tsx`. PDF / email templates stay Flask.
- Incremental. Search the repo first. Reuse existing filenames.
- Do **not** change API contracts, SQLAlchemy models, or workflow step data.
- Do **not** restyle the public vendor RFP form into a marketing site. Keep it clean and mobile-first, but it may stay slightly simpler than the authenticated app.
- Purple **“Review with Local AI”** remains the one accent action for AI. Do not recolor it to primary blue.
- Status colors already in use (Draft / Sent / Awarded / Critical / Major / Minor) stay semantically the same. Only the *chip treatment* is unified.
- This is **not** a dark-mode project unless a theme toggle already exists. Ship one light theme well.
- Do **not** introduce custom CSS frameworks or global `!important` overrides.

---

## 1. What “cheap and inconsistent” usually means in this codebase

Cursor: **audit first**, then fix. Before editing, inventory these files (names may differ — search):

- `src/theme.ts` / `src/theme/index.ts` / `src/App.tsx` ThemeProvider
- Shared layout: `AppShell`, `DashboardLayout`, `MainLayout`, `TopAppBar`, `BottomNav`
- Page roots: Dashboard, CRM, Estimating, RFP list/detail, DrawingViewer chrome, ChatBot drawer header
- Repeated primitives: buttons, chips, cards, page headers, empty states, dialogs

Typical defects to look for and kill:

| Defect | Why it looks cheap | Fix |
|---|---|---|
| Hard-coded hex in `.tsx` (`#1976d2`, `#9c27b0`, `orange`) | Every page invents a palette | Tokens only |
| Mix of `contained` / `outlined` / `text` / raw `<button>` for the same action | Visual noise | Action hierarchy (§4) |
| Different AppBar heights, titles, and right-action clusters per page | Feels like 6 products | Shared `PageHeader` |
| Default MUI rounded-4px + dense tables next to airy cards | Uneven density | One radius + one density scale |
| `elevation={8}` cards + flat tables on the same screen | Shadow soup | Almost no elevation; use border + surface |
| Inconsistent status chips (some filled, some outlined, some raw Typography) | Unreadable pipeline | One `StatusChip` |
| Page titles as raw `h4` / `h5` / `variant="h6"` mix | No type ramp | Theme typography only |
| Icon sizes 16 / 18 / 20 / 24 / 28 mixed | Amateur | 18 default, 20 in AppBar, 24 in empty states |
| Purple AI button sometimes `secondary`, sometimes custom sx | Brand leak | Shared `AiReviewButton` |
| Dialogs with different paddings and no sticky footer | Forms feel unfinished | Shared `AppDialog` |
| Tables without sticky header / first-column treatment | Spreadsheet-unfriendly | Keep AutoFilter brief; only restyle chrome |

Write a short audit comment at the top of the PR / commit message listing the worst 8 offenders you actually found. Do not invent pages that are not in the repo.

---

## 2. Design intent (what “modern” means here)

This is a **field + office operations tool**, used on 13" laptops and tablets on jobsites. It should feel:

- Quiet surfaces, strong type hierarchy, one accent
- Dense where data lives (grids), generous where decisions live (headers, dialogs)
- Construction-credible: not playful, not consumer-fintech neon
- California commercial / government: readable, high contrast, no tiny gray-on-gray labels

Visual references (do not copy branding; copy *discipline*):

- Procore / Autodesk Build for information density
- Linear for header + command density
- Notion for empty states and secondary text
- Not: colorful SaaS landing pages, glassmorphism, gradients behind every card

---

## 3. Single source of truth — theme tokens

Create or replace **one** theme file. Preferred path (search first):

- `src/theme/theme.ts`
- `src/theme/tokens.ts`
- `src/theme/components.ts` (MUI component overrides only)

Export `appTheme` and wrap the authenticated app once in `ThemeProvider`. Do not create per-page themes.

### 3.1 Color tokens

Use a restrained industrial palette. Exact hex can be tuned, but **lock the roles**.

```ts
palette: {
  mode: 'light',
  primary: {
    main: '#1F4E5F',      // deep slate-teal — construction, not Material blue
    dark: '#163845',
    light: '#2E6B80',
    contrastText: '#FFFFFF',
  },
  secondary: {
    main: '#5B6570',      // neutral steel — never used as a loud accent
    contrastText: '#FFFFFF',
  },
  ai: {
    main: '#6D28D9',      // purple — Local AI ONLY
    dark: '#5B21B6',
    light: '#EDE9FE',
  },
  success: { main: '#2E7D4F' },
  warning: { main: '#C47B17' },
  error:   { main: '#B42318' },
  info:    { main: '#1F4E5F' },
  background: {
    default: '#F4F6F8',   // app canvas
    paper:   '#FFFFFF',
  },
  divider: '#E3E8EE',
  text: {
    primary:   '#1B242C',
    secondary: '#5C6B76',
    disabled:  '#98A4AE',
  },
}
```

If TypeScript complains about `ai`, put it on `theme.palette` via module augmentation **or** keep it as an exported constant `AI_PURPLE` used only by `AiReviewButton`. Do not sprinkle `#6D28D9` in 40 files.

**Do not** keep MUI default indigo `#1976d2` as primary. That is a large part of the “template” look.

Semantic status mapping (chips / dots only):

| Status family | Color role |
|---|---|
| Draft / New | `text.secondary` outlined |
| Sent / In progress / Estimating | `primary` outlined or soft tint |
| Awarded / Approved / Released | `success` |
| Lost / Rejected / Overdue | `error` |
| Warning / Due soon / Partial | `warning` |
| AI Critical | `error` filled |
| AI Major | `warning` filled |
| AI Minor | `info` outlined |
| Local AI action | `ai` / purple |

### 3.2 Shape, elevation, spacing

```ts
shape: { borderRadius: 10 }
spacing: 8
shadows: flatten most elevations
```

Overrides:

- `MuiPaper` default elevation **0**, border `1px solid divider`
- `MuiCard` elevation **0**, same border, no gradient
- `MuiAppBar` elevation **0**, background `paper`, bottom border divider
- `MuiButton` text transform **none**, fontWeight 600, borderRadius 8
- `MuiChip` height 24, fontSize 12, fontWeight 600
- `MuiDialog` paper borderRadius 12
- `MuiTooltip` fontSize 12

Spacing scale in layouts: **8 / 16 / 24**. Kill random `sx={{ p: 1.3, mt: 2.25 }}`.

### 3.3 Typography

Load **one** font. Preferred: **IBM Plex Sans** or **Source Sans 3** via `@fontsource` (already common). Fallback: Inter. Do not mix Roboto + Inter + system-ui across pages.

Ramp:

| Token | Size / weight | Use |
|---|---|---|
| `h4` | 28 / 650 | Rare marketing-style titles — almost unused |
| `h5` | 22 / 650 | Page title in `PageHeader` |
| `h6` | 18 / 650 | Section title, card title |
| `subtitle1` | 16 / 600 | Dialog titles, drawer headers |
| `subtitle2` | 14 / 600 | Table section labels |
| `body1` | 14 / 400 | Default app body (yes — 14, not 16, for ops density) |
| `body2` | 13 / 400 | Secondary / helper |
| `caption` | 12 / 500 | Meta, timestamps, chip-adjacent |
| `overline` | 11 / 650 / 0.06em | Section overlines (“PIPELINE”, “TAKEOFF”) |

No page may use raw `fontSize: 17` / `fontWeight: 800` in `sx`.

---

## 4. Action hierarchy (buttons)

Every page uses the same ladder. Implement as theme defaults + two wrappers.

| Rank | Component | Variant | When |
|---|---|---|---|
| 1 Primary | `Button` | `contained` `primary` | One per view: Save, Create RFP, Generate Proposal, Award |
| 2 AI | `AiReviewButton` | contained purple | Review with Local AI, Full Bid Scan |
| 3 Secondary | `Button` | `outlined` | Cancel sibling, Export, Send reminder |
| 4 Quiet | `Button` | `text` | Tertiary: Reset columns, View drawings |
| 5 Destructive | `Button` color=`error` outlined | Delete, Reject, Mark Lost |
| 6 Icon | `IconButton` size=`small` | Row actions only |

Rules:

- Never two contained primary buttons side by side. If two exist, the lesser becomes outlined.
- Never use `color="secondary"` contained for a real CTA. Secondary is steel, not a second brand.
- FAB / SpeedDial stays for field camera + global create. Style it primary, 56px, no rainbow.
- Public RFP submit button = primary contained, full width on mobile.

Create:

- `src/components/Common/AiReviewButton.tsx`  
  Label default `"Review with Local AI"`. StartIcon = AutoAwesome or existing icon. Uses AI purple. Size `small` in tables, `medium` in headers.

If an `AiReviewButton` already exists, restyle it. Do not fork.

---

## 5. Shared chrome components (build once, swap in)

Search first. Create only what is missing.

### 5.1 `PageHeader`

`src/components/Layout/PageHeader.tsx`

```
[overline]           [optional project chip]
[Title]              [primary action] [AI button] [more menu]
[subtitle / meta]    [tabs or filter chips]
```

Props: `overline?`, `title`, `subtitle?`, `meta?: ReactNode`, `actions?: ReactNode`, `tabs?: ReactNode`.

Use on: CRM, Estimating, RFP list, RFP detail, Submittals, POs, Documents, Dashboard section heads.

AppBar itself should **not** restyle per page (no random color AppBars). AppBar = logo + global search + project switcher + notifications + user. Page identity lives in `PageHeader` below the AppBar.

### 5.2 `StatusChip`

`src/components/Common/StatusChip.tsx`

Maps known status strings to the semantic colors in §3.1. Size small. No random `Chip color="secondary"`. Pipeline stages, RFP statuses, PO statuses, submittal stamps, AI severity all go through this (or a thin wrapper per domain that calls it).

### 5.3 `AppCard`

Thin wrapper over `Card`: no elevation, divider border, standardized `CardHeader` title=`subtitle1`, content padding 16.

### 5.4 `AppDialog`

Sticky header + scroll body + sticky footer actions. Primary action right. Destructive left or in footer as error outlined. Used for RFP send preview chrome, award confirm, CO create, filter sheets.

### 5.5 `EmptyState`

Icon 40, title `h6`, body `body2` secondary, one primary or outlined action. Replace “No rows” raw text in lists.

### 5.6 `SectionOverline`

`Typography variant="overline" color="text.secondary"` — used above sidebars and summary panels.

### 5.7 Bottom nav + AppBar

- AppBar height 56 desktop / 48 compact if already dense.
- Bottom nav: existing routes. Badge colors use `error` for Critical AI, `primary` for counts.
- Offline / AI status dots already specified elsewhere: keep 🟢🟡🔴 but size 8px, aligned to caption.

---

## 6. Page-by-page pass (visual only)

Do this **in order**. Stop after each area compiles. Do not rewrite data hooks.

### Pass A — Theme + shell (do first)

1. Tokens + component overrides.
2. AppBar, BottomNav, main content background `#F4F6F8`.
3. `PageHeader`, `StatusChip`, `AiReviewButton`, `EmptyState`.
4. Global font load.

### Pass B — Dashboard

- KPI cards: same height, same `AppCard`, number `h5`, label `caption`.
- No four different card styles.
- “Open RFPs / Critical AI / Due bids” use `StatusChip` + one sparkline max if already present. Do not add new charts in this brief.

### Pass C — CRM (Leads / Bids)

- Kanban column headers: overline + count chip. Column background canvas, cards white.
- Bid cards: one shadow-less border, trade pills via `StatusChip` / small chips, due-date caption, AI severity dot.
- Table view: honor `table_autofilter_leads_estimates_cursor.md`. This pass only restyles header height, row height (52 desktop), and chip cells.
- Detail tabs: MUI `Tabs` standard, not a custom underline invented per page.

### Pass D — Estimating

- Takeoff grid: header bg `#EEF2F5`, font 13, row 48–52. AI flag column uses severity dots, not emoji.
- Right sidebar: ChatBot header must match drawer header elsewhere (title + mode badge + provider toggle).
- Bottom summary: sliders stay; typography and spacing only.

### Pass E — RFP (do not touch quote math)

- List: same DataGrid chrome as CRM table.
- Detail split pane: equal card treatments left/right.
- Comparison table: keep green lowest-price highlight, but use `success.light` cell background at 16% opacity instead of neon.
- Email preview modal: `AppDialog`.

### Pass F — DrawingViewer chrome only

- Toolbars, purple review button, side panels.
- **Do not** restyle canvas measurements, calibration UX, or annotation drawing tools beyond toolbar button consistency.

### Pass G — ChatBot drawer

- Header aligned with §5.
- Provider toggle: segmented control or quiet toggle, not two competing contained buttons.
- Mode badge = `StatusChip`.
- Message bubbles: user = primary-tint, assistant = paper + border. Keep streaming behavior.

### Pass H — Forms (RFP form, vendor select, PO, submittal intake)

- `TextField` size=`small` everywhere in tool pages.
- Labels above or standard MUI outlined — pick **outlined small** and stick to it.
- Helper text `caption`. No mix of standard + filled + naked inputs on one form.

### Pass I — Public pages

- `/public/rfp/:token` and vendor portal: same font + primary + radius. Simpler header (logo + RFP title + due chip). Still mobile-first.

---

## 7. DataGrid visual standard (shared with AutoFilter brief)

When touching grids in this pass, apply:

```ts
sx={{
  border: 1,
  borderColor: 'divider',
  borderRadius: 1,
  bgcolor: 'background.paper',
  '& .MuiDataGrid-columnHeaders': {
    bgcolor: '#EEF2F5',
    fontSize: 12,
    fontWeight: 650,
    textTransform: 'none',
  },
  '& .MuiDataGrid-cell': { fontSize: 13 },
  '& .MuiDataGrid-row:hover': { bgcolor: 'rgba(31,78,95,0.04)' },
}}
```

Row height 52. Header height 48. Do not change column models except to plug `StatusChip` into renderCell where status is plain text today.

Persist / filter behavior stays in `table_autofilter_leads_estimates_cursor.md`. This brief does not reopen that scope.

---

## 8. Iconography

- One set: **MUI Icons** (`@mui/icons-material`). Do not mix Lucide + FontAwesome + MUI.
- Stroke-looking icons at 20px in headers, 18px in buttons, 16px inside chips/tables.
- Filled icons only for active nav and Critical severity.
- Replace emoji status (🔥 ⚠️ ✅) with chips/dots if they exist in UI strings.

---

## 9. Motion

- Keep it almost still. 120–180ms ease-out on drawers and dialogs.
- No bounce, no page-load fade walls, no skeleton shimmer in five different styles.
- One skeleton pattern: MUI `Skeleton` rounded 8, used on list first paint only if already present.

---

## 10. Accessibility (minimum while restyling)

- Contrast: text.primary on paper and primary.contrastText on primary.main must pass AA.
- Buttons have visible focus ring (`theme.palette.primary.main` 2px offset).
- Do not rely on color alone for AI severity — keep the label or tooltip.
- Touch targets on BottomNav and primary header actions ≥ 40px.

---

## 11. Out of scope

- New features, new pages, new charts, new onboarding.
- Dark mode (unless toggle already exists — then tokens must work in both).
- Replacing DataGrid, ChatBot internals, DrawingViewer canvas, RFP email HTML.
- Custom illustration library or lottie.
- Marketing landing page.
- Renaming routes or information architecture.

---

## 12. Implementation order for Cursor

1. Audit existing theme + list of hardcoded colors / one-off headers (comment in PR).
2. Tokens + MUI overrides + font.
3. Shared: `PageHeader`, `StatusChip`, `AiReviewButton`, `EmptyState`, `AppDialog`.
4. Shell (AppBar, BottomNav, canvas background).
5. Passes B → I above.
6. Grep the repo for leftover `#1976d2`, `#9c27b0`, `color="secondary"` contained CTAs, `elevation={3,4,6,8}`, `textTransform: 'uppercase'` on buttons, emoji status.
7. Visual smoke: Dashboard, CRM kanban + table, one Estimate, RFP list + comparison, DrawingViewer toolbar, ChatBot drawer, public RFP form — desktop and a 390px width.

---

## 13. Acceptance criteria

Done when:

- One ThemeProvider drives color, type, radius, button shape.
- Page titles all come from `PageHeader` (or a documented exception: DrawingViewer canvas, public form).
- Primary / AI / secondary / quiet / destructive buttons are visually distinct and reused.
- Status is always a chip from one mapper.
- Cards and AppBars have no drop-shadow stack.
- No page still uses default MUI indigo as brand.
- ChatBot, RFP send/compare/award, DrawingViewer review flow, and Grok toggle still work.
- Mobile bottom nav and public quote form still usable with one hand.

Not done if you only wrapped the app in a new primary color and left every page’s local `sx` intact.

---

## 14. Suggested commit / PR title

`style: unify MUI theme, page header, chips, and AI button across app chrome`

Keep functional files out of the diff unless a swap to `PageHeader` / `StatusChip` requires it.
