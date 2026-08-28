# Cursor Implementation Brief — Submittal QC Gate

**Date:** 2026-08-27  
**Module:** Documents Hub / Quality — Submittal Register + Internal QC  
**CSI context:** 01 33 00 Submittal Procedures + finish-trade sections (09 / 10)  
**Owner company:** Finish-work subcontractor, CA commercial + government work

Employees are not QCing incoming submittals. This module makes QC a **hard gate**, not a reminder.

**Rule:** no completeness check + no AI pass + no human checklist + no stamp → cannot buy, cannot receive, cannot install.

This is **internal contractor QC** before anything goes to the GC / A/E, and before Procurement releases material. It is not a replacement for architect approval.

---

## 0. Non-negotiable rules

- Keep xAI/Grok integration untouched.
- Do not regress RFP, DrawingViewer, ChatBot core, `aiReviewBus.ts`, Estimating, Financials, or Purchase Orders.
- Reuse: `Company`, `Project`, `Document`, `Drawing`, `DrawingAnnotation`, `EstimateLineItem`, `RFP` / `RFPResponse`, `PurchaseOrder` (see `purchase_order_material_tracking_cursor.md`), Documents Hub upload, SMTP + Celery, audit logging, auth, toasts, MUI.
- Embed existing `ChatBot.tsx`. Add a **mode only** (`submittal_review`). Do not fork ChatBot.
- Fire reviews through existing `aiReviewBus.ts`.
- No Jinja2 inside `.tsx`. Transmittal / stamp PDF stay in Flask.
- Prefer MUI. Mobile-first. Incremental.
- Ask before inventing filenames if a close equivalent already exists.
- Do **not** store every catalog SKU. For configurable Div 10 items use Product Family + frozen snapshot (PENCO pattern in `penco_locker_configurator_import.md`).
- **Workflows are data.** Who is in the QC queue and which steps exist must be amendable later without a code deploy. Use the shared engine in `artifacts/workflow_engine_cursor.md`. Do not hardcode a stepper or `if role ==` approval chain in this module.

---

## 1. What to build (scope)

One new module: **Submittals**, living under Documents Hub.

**Default** lifecycle (seed of process_key `submittal_qc` — amendable):

`Draft Package → Received / Incomplete → In QC → Internally Approved | Approved as Noted | Revise & Resubmit | Rejected | For Information Only → Submitted to GC/AE → AE Action → Released`

Also allow `Cancelled` / `Superseded` on a revision.

This sequence is the **published default definition**, not a hardcoded machine. Admins may add/remove/reorder steps and change queue membership (see §3b and `workflow_engine_cursor.md`). UI steppers must render the workflow **instance snapshot**, never a const array.

Must-have in v1:

1. Submittal register per project (CSI, trade, type, revision, owner, dates, status).
2. Intake from Documents Hub upload **and** vendor portal file upload (reuse public-token pattern from RFP; do not clone RFP).
3. Completeness checklist generated from CSI / trade template. Incomplete packages cannot be stamped.
4. Mandatory Local AI first pass (`submittal_review`) via existing ChatBot + `aiReviewBus`.
5. Human QC checklist (Pass / Fail / N/A + comment). Stamp disabled until required rows + AI dispositions are done.
6. Digital internal review stamp + audit trail (reviewer, timestamp, duration).
7. Hard holds:
   - Purchase Order issue / receive blocked unless linked submittal is Internally Approved or Approved as Noted (or explicitly marked “informational / no action”).
   - Field receiving cannot accept that product without approved submittal id.
8. Aging + rubber-stamp metrics on list + Dashboard hook.
9. Revision control. Only current stamped rev is controlled copy; prior revs watermark SUPERSEDED.

Out of v1 (do not build unless already trivial):

- Full A/E workflow hosted for the architect (we only log *their* returned stamp).
- Physical sample chain-of-custody lab.
- Auto-OCR of every PDF into structured spec tables (AI vision on attached pages is enough).
- New notification stack. Reuse SMTP + Celery + existing notification center.

---

## 2. Why this exists (product intent)

Typical failure: PDF lands in email → PM forwards to GC → wrong product shows up → field installs it.

This module forces:

1. One intake path (no email-as-system-of-record).
2. Completeness before review.
3. AI catches model / color / fire / VOC / dimension misses against spec + drawings + material family libraries.
4. Named human reviewer completes a short trade checklist and dispositions every Critical/Major AI finding.
5. Stamp duration + checklist completeness make rubber-stamps visible.
6. Procurement (`PurchaseOrder`) and field receive honor the gate.

---

## 3. Data model (SQLAlchemy)

Do not overload `RFP`, `Document`, or `PurchaseOrder`. New tables; FKs into existing ones.

### `Submittal`

| Field | Type | Notes |
|---|---|---|
| id | UUID PK | |
| project_id | FK Project | required |
| submittal_number | String | `SUB-{projectCode}-{####}` server-generated |
| spec_section | String | e.g. `09 91 00`, `10 51 13` |
| trade | Enum / String | drywall, paint, flooring, ceilings, trim, specialties, other |
| title | String | |
| submittal_type | Enum | `product_data`, `shop_drawing`, `sample`, `certification`, `test_report`, `delegated_design`, `closeout`, `other` |
| action_type | Enum | `action` (needs approval) \| `informational` |
| vendor_id | FK Company nullable | who prepared it |
| assigned_reviewer_id | FK User nullable | denormalized current assignee; source of truth is WorkflowInstanceStep |
| workflow_instance_id | FK WorkflowInstance nullable | required once process started |
| status | Enum | denormalized from current workflow step / outcomes — see default lifecycle |
| current_revision_id | FK SubmittalRevision nullable | |
| spec_requirements | JSONB | required artifact list from template |
| linked_drawing_ids | JSONB / association | DrawingViewer sheets |
| estimate_line_item_ids | association | |
| rfp_id / rfp_response_id | FK nullable | |
| needed_by_date | Date nullable | before buy / install |
| received_at | DateTime nullable | |
| internally_reviewed_at | DateTime nullable | |
| submitted_to_ae_at | DateTime nullable | |
| ae_action | String nullable | their stamp, logged only |
| ae_action_at | DateTime nullable | |
| released_at | DateTime nullable | buy/install allowed |
| notes | Text | |
| created_by / updated_by / timestamps | | reuse audit columns |

### `SubmittalRevision`

| Field | Type | Notes |
|---|---|---|
| id | UUID PK | |
| submittal_id | FK | |
| revision | String | `0`, `A`, `B` or `00`, `01` |
| is_current | Boolean | only one current |
| document_ids | association | Documents Hub files |
| package_complete | Boolean default false | |
| completeness_score | Numeric | 0–100 |
| ai_review_annotation_id | FK DrawingAnnotation nullable | type=`ai_review`, mode stored in payload |
| ai_status | Enum | `not_run`, `queued`, `complete`, `failed`, `overridden` |
| ai_overridden_reason | Text nullable | required if AI skipped |
| human_stamp | Enum nullable | `no_exceptions`, `make_corrections_noted`, `revise_resubmit`, `rejected`, `for_info_only` |
| stamp_comments | Text | |
| reviewed_by | FK User nullable | |
| review_started_at / review_completed_at | DateTime | duration = rubber-stamp signal |
| review_duration_seconds | Integer nullable | computed |
| checklist_complete | Boolean default false | |
| created_at | | |

### `SubmittalChecklistItem`

| Field | Type | Notes |
|---|---|---|
| id | UUID PK | |
| revision_id | FK | |
| template_key | String | e.g. `paint.mpi_system` |
| sort_order | Integer | |
| label | String | |
| required | Boolean | |
| result | Enum nullable | `pass`, `fail`, `na`, `blank` |
| comment | Text | required if fail |
| source | Enum | `template`, `ai_finding`, `custom` |
| ai_finding_ref | String nullable | |
| disposition | Enum nullable | `accepted`, `overridden`, `converted_to_comment` |
| completed_by / completed_at | | |

### `SubmittalHold` (optional thin table if you do not want to scatter flags)

Used by PO + receiving checks.

| Field | Type | Notes |
|---|---|---|
| submittal_id | FK | |
| hold_type | Enum | `procurement`, `receive`, `install` |
| is_active | Boolean | active until Released (or informational) |
| reason | String | |

Indexes: `project_id`, `status`, `spec_section`, `trade`, `assigned_reviewer_id`, `needed_by_date`, `vendor_id`.

Audit: every intake, assignment, AI run, checklist change, stamp, revision, hold release, and AE action write to the existing audit log.

---

## 3b. Amendable workflow (required)

Read and follow `artifacts/workflow_engine_cursor.md`.

- On create / first completeness pass, start a `WorkflowInstance` with `process_key = submittal_qc`.
- Subject adapter maps engine actions onto this module: `run_ai_review`, `complete_checklist`, `stamp`, `transmit`.
- `assigned_reviewer_id` always copies from the current ready instance step.
- Reassign and “who can act” come from **live queue membership**, not a fixed role check in `SubmittalReviewPage`.
- Adding a Superintendent co-sign (or removing Transmit to AE on small commercial jobs) is a published definition change. New submittals pick it up. Open ones keep their snapshot.
- Project override: gov jobs may publish a project-scoped definition with extra compliance / AE steps.

Default seeded steps (labels only — not frontend constants):

1. Log & completeness  
2. Local AI review  
3. Trade QC stamp  
4. Transmit to GC/AE (skippable via entry_condition)  
5. Log AE action (skippable)  
6. Release holds  

Do not implement a second state machine in `submittals_bp` that ignores the instance.

---

## 4. Status + stamp rules (implement exactly)

Default seed outcomes below. If a published definition uses different `on_approve_status` values, honor the snapshot.

### Status machine (default seed)

- `draft` — internal assembly, not received from vendor yet
- `incomplete` — logged, missing required artifacts
- `in_qc` — assigned + package complete enough to review
- `internally_approved` — stamp `no_exceptions`
- `approved_as_noted` — stamp `make_corrections_noted` (notes must be stored; work may proceed internally)
- `revise_resubmit` — new revision required; holds stay on
- `rejected`
- `for_info_only` — informational; no approval implied; procurement hold off unless PM sets one
- `submitted_to_ae` — transmitted upstream
- `ae_returned` — AE stamp logged
- `released` — buy / receive / install allowed
- `superseded` / `cancelled`

`released` is automatic when:

- action submittal is `internally_approved` or `approved_as_noted`, **and**
- project setting `require_ae_before_release` is false (default for most finish product data), **or** AE action is logged as approved / approved as noted

Government / specified projects may flip `require_ae_before_release` per project.

### Stamp button is disabled until all are true

1. Current revision `package_complete === true`
2. Every `required` checklist item has `pass` | `fail` | `na`
3. Every AI finding with severity Critical or Major has a disposition
4. `ai_status` is `complete` **or** `overridden` with a non-empty reason
5. Either `review_duration_seconds >= 180` **or** a superintendent / PM co-sign `rush_exception` is recorded

If stamp is `revise_resubmit` or `rejected`, create a new empty revision shell (next letter) and keep holds active.

### Rubber-stamp detection (do not block; flag)

Flag `rubber_stamp_suspect = true` on the revision when:

- duration < 180 seconds, or
- zero checklist comments and zero AI dispositions that are not auto-accepted, or
- stamp applied with AI still `not_run` (should be impossible; treat as defect)

Surface on register + reviewer scorecard. Do not auto-void the stamp in v1.

---

## 5. Completeness templates (seed)

Store as a static JSON seed (`submittal_checklist_templates`) keyed by spec section / trade. v1 seeds:

### Always (01 33 00)

- Project name / number matches
- Spec section correct
- Revision identified
- Manufacturer + exact model / family highlighted on cut sheet
- Required artifacts present for type (product data / shop drawing / sample / cert)
- Linked to at least one drawing **or** explicitly N/A

### 09 29 00 Gypsum

- Board type (X, C, abuse, MR)
- Thickness
- UL / rated assembly design vs drawing wall type
- Fastener / control joint notes if shop drawing

### 09 91 00 Paint

- MPI system number
- Sheen + color vs finish schedule
- Primer system vs substrate
- Title 24 VOC
- Manufacturer system not mixed

### 09 65 / 09 68 Flooring

- Exact product + wear layer
- Adhesive system
- Moisture test method + limits
- Transitions / attic stock if specified

### 09 51 Ceilings

- Grid type / duty
- Tile NRC / CAC
- Fire-rated assembly
- Seismic / hanger notes (CA commercial)

### Division 10 specialties

- Family + size + color + options vs frozen takeoff snapshot
- Compare against imported material libraries (ASI, Penco, Inpro, Bobrick, Claridge, JL, Larsen, CS CSVs already in artifacts)
- Do not invent extra catalog rows

Reviewer can add custom rows. Templates are starting points, not a second spec book.

---

## 6. AI mode: `submittal_review`

Extend existing ChatBot mode list + backend system-prompt map only.

**Default provider:** Local Llama 4 Scout  
**Grok:** remains available via existing toggle; do not change Grok code paths.

### Bus payload

```ts
aiReviewBus.emit('review-request', {
  mode: 'submittal_review',
  submittalId,
  revisionId,
  documentIds,
  drawingIds,
  imageDataUrl, // first-page / selected pages preview
  context: {
    projectId,
    specSection,
    trade,
    finishScheduleNotes,
    materialFamilySnapshot, // PENCO-style JSON if present
    californiaCodes: true
  }
});
```

On completion:

```ts
aiReviewBus.emit('review-complete', {
  submittalId,
  revisionId,
  annotationId,
  severity,
  findings
});
```

Save using existing `DrawingAnnotation` (type=`ai_review`) when a drawing is attached. If no drawing, store `raw_response` + structured findings JSON on the revision and still emit the bus event so Dashboard / Estimating can refresh.

### Expected structured findings

Each finding: `severity` (Critical / Major / Minor / Info), `title`, `detail`, `spec_citation`, `drawing_ref`, `suggested_checklist_item`, `cost_impact`, `delay_impact_days`.

Critical/Major auto-insert checklist rows with `source=ai_finding`.

System prompt focus: CBC 2025/2026, Title 24 VOC, ADA where relevant, fire-rated assemblies, finish-trade product data vs spec, substitution detection, color/finish mismatch, family/config snapshot mismatch.

Timeouts, multimodal fallback, `/api/ai/status`, and Grok fallback stay as already implemented.

---

## 7. Holds into Purchase Orders + field receive

Read `artifacts/purchase_order_material_tracking_cursor.md` and add **hooks only** — do not rebuild PO.

On `PurchaseOrder` / `PurchaseOrderLine` add nullable:

- `submittal_id`
- `submittal_release_required` (default true for action product data)

Rules:

- `POST /api/purchase-orders/:id/issue` returns 409 if any line with `submittal_release_required` points at a submittal that is not `released` / `internally_approved` / `approved_as_noted` / `for_info_only`.
- `POST /api/purchase-orders/:id/receipts` same check unless condition is `held_unapproved` (quarantine receive — allowed, does not count as accepted).
- Field material-accept UI (when built) must select `submittal_id`.

If a PO line has no submittal linked, project setting `allow_po_without_submittal` default **false** for Div 09/10 action items; PM can override with reason (audit).

---

## 8. API (Flask blueprint)

New blueprint: `submittals_bp` mounted at `/api/submittals`.

Do not hang these off `/api/rfps` or `/api/documents` beyond file attach.

```
GET    /api/submittals
       query: project_id, status, trade, spec_section, reviewer_id, overdue=1, rubber_stamp=1
POST   /api/submittals
GET    /api/submittals/:id
PATCH  /api/submittals/:id
POST   /api/submittals/:id/revisions
POST   /api/submittals/:id/revisions/:revId/documents
POST   /api/submittals/:id/revisions/:revId/completeness   # recompute from template + files
POST   /api/submittals/:id/revisions/:revId/ai-review      # emits bus; uses existing /api/ai/review under the hood
PATCH  /api/submittals/:id/revisions/:revId/checklist
POST   /api/submittals/:id/revisions/:revId/stamp
POST   /api/submittals/:id/assign            # wraps POST /api/workflows/instances/:id/assign
POST   /api/submittals/:id/transmit-to-ae    # logs + email; completes transmit step; no AE portal
POST   /api/submittals/:id/ae-action
GET    /api/submittals/templates?spec_section=&trade=
```

Vendor intake (reuse RFP public-token pattern, new route):

```
POST   /api/public/submittals/:token
```

List payload must include aging + QC signals so the grid does not N+1:

```json
{
  "id": "...",
  "submittalNumber": "SUB-0142-0018",
  "title": "MPI 143 eggshell — corridors",
  "specSection": "09 91 00",
  "trade": "paint",
  "status": "in_qc",
  "revision": "A",
  "vendorName": "Sherwin-Williams",
  "reviewerName": "J. Ortiz",
  "neededByDate": "2026-09-05",
  "isOverdue": false,
  "packageComplete": true,
  "aiStatus": "complete",
  "aiMaxSeverity": "major",
  "checklistComplete": false,
  "rubberStampSuspect": false,
  "released": false
}
```

Reuse existing auth, pagination, error handlers, audit helper.

Emails (Jinja2, Flask only): assigned, due in 48h, overdue, rejected / revise, stamped + released. Copy RFP email pattern; do not edit RFP templates.

---

## 9. Frontend

Routes:

- `/submittals` — portfolio register
- `/projects/:projectId/submittals` — project register
- `/submittals/:id` — review workspace

Files to create (adjust only if a Documents folder already exists):

```
src/pages/Documents/SubmittalRegisterPage.tsx
src/pages/Documents/SubmittalReviewPage.tsx
src/components/Documents/SubmittalStatusChip.tsx
src/components/Documents/SubmittalChecklist.tsx
src/components/Documents/SubmittalStampDialog.tsx
src/components/Documents/SubmittalHoldsBanner.tsx
src/hooks/useSubmittals.ts
```

Use shared `WorkflowStepper` from the workflow engine brief. Do not declare local step arrays.

Add **Submittals** to existing nav / bottom nav if those files already list Dashboard, RFP, Estimating, Financials, Purchase Orders. Do not invent a new shell.

### Register

MUI DataGrid (RFP list pattern):

- Number, Title, Spec, Trade, Vendor, Status, Rev, Needed by, Reviewer, AI severity dot, Complete?, Overdue chip
- Filters: status, trade, reviewer, overdue, rubber-stamp suspect
- “Log submittal” button

### Review workspace (desktop split, mobile tabs)

**Left 60%:** PDF / image from Documents Hub; “Open in DrawingViewer” if shop drawing or sheet-linked; overlays stay in DrawingViewer.

**Right 40%:**

- Completeness list
- Embedded `ChatBot.tsx` with `mode="submittal_review"`, default Local Llama
- Purple “Review this package with Local AI”
- Human checklist
- Stamp button (disabled with tooltip listing unmet gates)

**Header:** number, `WorkflowStepper` (instance snapshot), needed-by countdown, holds banner (“Procurement hold ON”), current queue + assignee.

Mobile: tabs Package | Checklist | AI | Stamp. Chat full-screen when opened.

---

## 10. Dashboard + CRM hooks

Reuse existing KPI card pattern:

- Open submittals past `needed_by_date`
- In QC > 48 hours
- Rubber-stamp suspect count this week
- Unreleased action submittals blocking POs

CRM Bid / Project detail: tab or link “Submittals” once a project exists. Do not block Bid Kanban work.

Estimating: AI flags from submittal reviews can highlight related line items via `aiReviewBus` `review-complete` the same way drawing reviews already do.

Financials / CO: Critical findings may use existing “Create CO from AI Finding” later; not required in v1.

---

## 11. Security + government

- Vendor public token: time-limited, project-scoped, upload + metadata only. No register visibility across vendors.
- Audit trail retained for prevailing wage / DBE / closeout packs.
- Local-only AI option already exists — use it on sensitive gov packages; do not add a second switch.
- Controlled copy: download of current rev includes stamp overlay generated in Flask (PDF), not in TSX.

---

## 12. Implementation order for Cursor

1. Models + migrations + `/api/submittals` CRUD + register page (no AI, no holds).
2. Attach `WorkflowInstance` using seeded `submittal_qc` definition (`workflow_engine_cursor.md`). Stepper reads instance.
3. Completeness templates + recompute endpoint + Incomplete vs In QC.
4. Documents Hub attach + vendor public upload token.
5. `submittal_review` mode + purple button + bus + annotation/revision persist.
6. Checklist UI + stamp rules + duration + rubber-stamp flag (these are `required_actions` on the trade_qc step, still enforced in the adapter).
7. PO issue/receive 409 hooks + holds banner.
8. Emails (assign / 48h / overdue / stamped).
9. Dashboard widgets.
10. Settings UI to amend queues and steps (may follow PO wiring).

Do not start at step 6. The gate is useless without a register people actually use.

---

## 13. Acceptance checks

- Incomplete package cannot stamp.
- Stamp without AI complete requires written override.
- Critical AI finding without disposition cannot stamp.
- 20-second approve is saved but flagged `rubberStampSuspect`.
- Revise & Resubmit creates rev B; rev A is superseded; holds stay on.
- PO issue against unreleased action submittal returns 409 with submittal number in the error.
- ChatBot Grok toggle still works on the same review page.
- Existing RFP send / public quote / comparison table unchanged.
- DrawingViewer “Review with Local AI” (`construction_review`) unchanged.
- Publishing a new `submittal_qc` definition with an extra step changes **new** packages; in-flight packages keep the old snapshot.
- Removing a user from the Trade QC queue stops new assignments to them.

---

## 14. Related artifacts

- `artifacts/workflow_engine_cursor.md` — shared amendable steps + queues. Required reading.
- `artifacts/purchase_order_material_tracking_cursor.md` — consume holds; do not duplicate PO.
- `artifacts/penco_locker_configurator_import.md` — frozen snapshot compare on Div 10 lockers.
- Material CSVs in `artifacts/` — family/color checks for specialties, not new pricing tables.
