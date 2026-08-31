# Cursor — Estimate Status Tracker (DB snapshot → app)

**Date:** 2026-08-30  
**Design source of truth:** `docs/ESTIMATE_STATUS_TRACKER.md`  
**Related:** `docs/OFFLINE_FIRST_AND_SYNC_DESIGN.md`, `docs/LOCAL_CACHE_JOB_OPEN_AND_CLEANUP.md`, `docs/OFFICE_CHROME_AND_MODE_UX.md`, `docs/JOB_REVISION_AND_ADDENDUM_DESIGN.md`, `docs/REPORT_WRITER_IMPLEMENTATION.md`

**How to run:** New Cursor Agent chat. Copy **one prompt at a time** (S1 → S6). After each: build/test (and migrate if you are in the CM backend repo), append a line to `docs/STATUS.md`.

This feature is **processed in the database**, then **loaded** into USISPdfApp. Do not invent a desktop-only status enum that never hits PostgreSQL.

Two repos may be in play:

| Prompt | Repo |
|---|---|
| S1 | **USIS Construction Management backend** (PostgreSQL + `/api/v1`) |
| S2–S6 | **USISPdfApp** (WPF .NET 8) |

If only the desktop repo is open, still do S1 as SQL + contract files under `docs/sql/` and `docs/api/`, then implement S2–S6 against that contract through `ISyncService`.

---

## Global rules (every prompt)

1. Queue pills display **server snapshot** fields. Local `.usisjob` only mirrors them.  
2. API envelopes stay `{ "item": ... }` / `{ "items": [...] }`.  
3. UUID keys, soft delete, NUMERIC money — same methodology as takeoff_line_items.  
4. Network only through `ISyncService` / `HttpSyncService`. No stray HttpClient.  
5. Offline-first: Queue paints from `cache/estimate-queue.json` even if the GET fails.  
6. Do not merge Awarded/Lost into the seven-step pipeline.  
7. Do not use Revu markup review status for this.  
8. Chat A dark density on any new UI. Status pills on Queue (Office spec).  
9. CommunityToolkit.Mvvm patterns already in use.

---

## What “done” means

User can:

1. Open Queue and see each job’s pipeline pill from the last successful queue fetch (or cache).  
2. First synced takeoff line moves the job to **Takeoff begun** on the next load (server recompute).  
3. Mark **Takeoff finished** / **RFPs received** / **Final pricing** / **Awaiting approval** — values persist in the DB and survive app restart.  
4. Create vendor RFP packages; sent/received counts show on the Queue row (`3 / 7 RFPs`).  
5. Set outcome Awarded/Lost/No bid/On hold without changing the pipeline pill.  
6. Work offline on a cached Queue; pending transitions upload later; server snapshot wins.

Not required in this pack: full RFQ PDF composer, approval workflow inbox, automatic addendum quantity rewrite.

---

## PROMPT S1 — Database + recompute + API (system of record)

```
We are implementing the estimate production pipeline for USIS.
Read docs/ESTIMATE_STATUS_TRACKER.md end to end before writing code.

GOAL
Pipeline status is stored and computed in PostgreSQL. HTTP API returns
snapshots the desktop will load. Do not put business rules only in WPF.

TASK

1. If this workspace is the CM backend:
   - Migration adding columns on lead_estimates (or the live equivalent
     job/estimate table — USE THE EXISTING TABLE, do not create a second
     jobs table) exactly as docs/ESTIMATE_STATUS_TRACKER.md § Database.
   - Tables estimate_rfp_packages and estimate_status_events.
   - Function recompute_estimate_status(p_lead_estimate_id uuid) that:
       a) writes snapshot counts from drawings + takeoff_line_items
          + rfp packages (deleted_at is null)
       b) auto-advances ONLY:
            unset/null → files_ingested when files_ready
            files_ingested → takeoff_begun when takeoff_line_count > 0
       c) inserts estimate_status_events when status changes
       d) never auto-sets takeoff_finished, rfps_received,
          final_pricing, or awaiting_approval
   - Call recompute after ingest, takeoff line write, and rfp write.
   - Endpoints from the spec:
       GET  /api/v1/estimate-queue
       GET  /api/v1/lead-estimates/{id}/status
       POST /api/v1/lead-estimates/{id}/status/transition
       GET/POST /api/v1/lead-estimates/{id}/rfp-packages
       PATCH /api/v1/lead-estimates/{id}/rfp-packages/{pkgId}
       POST /api/v1/lead-estimates/{id}/status/recompute
   - Transition validates legal order. 400 + current snapshot on illegal jump.
   - Envelopes: { "item": ... } / { "items": [...] }.
   - Auth same as existing lead/job routes.

2. If this workspace is USISPdfApp only:
   - Write the migration SQL to docs/sql/estimate_status.sql
   - Write the JSON contracts + example payloads to
     docs/api/estimate-status.json
   - Do not fake a local PostgreSQL.
   - Still add C# DTOs that match the JSON (next prompt owns services).

3. Seed/backfill: existing leads with drawings → files_ingested;
   those with takeoff lines → takeoff_begun. Do not mark finished.

4. Tests (backend): recompute auto-advance; illegal transition 400;
   RFP sent increments rfp_sent_count; soft-deleted packages excluded.

When done, append to docs/STATUS.md:
"S1 — Estimate pipeline columns + recompute + queue/status API contract (DB is source of truth)."
```

---

## PROMPT S2 — Desktop DTOs + queue load + cache file

```
We are building USISPdfApp (WPF .NET 8).
Read docs/ESTIMATE_STATUS_TRACKER.md and docs/LOCAL_CACHE_JOB_OPEN_AND_CLEANUP.md.

GOAL
Desktop loads estimate status from the API (or cache). It does not
compute the Queue pill from local markups.

TASK

1. DTOs (sealed / existing style), e.g. Models/Jobs/ or Models/Queue/:

EstimatePipelineStatus enum matching the seven snake_case API values
  (FilesIngested … AwaitingApproval). JSON converter to/from API strings.

EstimateOutcome enum: Awarded, Lost, NoBid, OnHold.

EstimateQueueItem — fields from the spec Queue item JSON
  (id, name, number, customer, bidDueAt, estimateStatus, outcome,
   sheet/measured/takeoff/unpriced counts, rfp sent/received,
   addendumUnverifiedCount, filesReady, grandTotal, snapshotComputedAt).

EstimateStatusSnapshot — same snapshot fields for a single job.

EstimateStatusEvent — fromStatus, toStatus, reason, actor, createdAt.

RfpPackage — id, vendorName, trade, status, sentAt, dueAt, receivedAt,
  quoteAmount, notes.

2. Extend ISyncService (do not scatter HttpClient):

Task<IReadOnlyList<EstimateQueueItem>> GetEstimateQueueAsync(ct)
Task<EstimateStatusSnapshot> GetEstimateStatusAsync(Guid leadEstimateId, ct)
Task<EstimateStatusSnapshot> TransitionEstimateStatusAsync(
    Guid leadEstimateId, string toStatus, string? reason, bool force, ct)
Task<IReadOnlyList<RfpPackage>> GetRfpPackagesAsync(Guid leadEstimateId, ct)
Task<RfpPackage> UpsertRfpPackageAsync(Guid leadEstimateId, RfpPackage package, ct)

HttpSyncService: GET/POST/PATCH as spec. Parse { item } / { items }.
OfflineSyncService / NoOp: return cached queue if present; otherwise
empty list / clear "sync not configured" result — must not throw.

3. Queue cache
   - Path already specified: %LocalAppData%\USISPdfApp\cache\estimate-queue.json
   - On successful GetEstimateQueueAsync, overwrite that file.
   - IEstimateQueueService (or extend existing Queue VM service):
       LoadCache() → list
       RefreshAsync() → network then cache
       GetCached() instant

4. Mirror onto open JobDocument / job.json as estimatePipeline
   (status + snapshot + lastLoadedAt + pendingTransition=null).
   This is a COPY of the server snapshot.

5. Unit tests: JSON round-trip of queue cache; enum converter;
   OfflineSyncService does not throw; Transition does not write a
   second local-only source of truth that disagrees with the DTO.

6. dotnet build && dotnet test. Fix failures.

When done, append to docs/STATUS.md:
"S2 — Estimate queue/status DTOs + ISyncService fetch + estimate-queue.json cache."
```

---

## PROMPT S3 — Queue pills from loaded snapshot

```
We are building USISPdfApp (WPF .NET 8).
Read docs/ESTIMATE_STATUS_TRACKER.md § Desktop and
docs/OFFICE_CHROME_AND_MODE_UX.md § Queue.

GOAL
Queue shows the seven-step pipeline as pills from the loaded snapshot.
No markup chrome on this view.

TASK

1. On Queue open:
   - Bind the grid immediately to cached estimate-queue.json.
   - Fire RefreshAsync in the background. On success, rebind.
   - On failure, keep cache and a quiet status hint
     ("Offline — showing last queue").

2. Columns / row content (dense, 22–24px rows, Chat A dark tokens):
   - Name + number
   - Customer
   - Pipeline pill (human labels from the spec table)
   - Outcome pill only if outcome != null
   - Bid due (overdue / this week / later emphasis already specified)
   - Secondary text: "12 / 40 sheets" when measured/sheet counts exist;
     "3 / 7 RFPs" when rfpSentCount > 0;
     "8 unpriced" when unpricedLineCount > 0
   - Addendum badge when addendumUnverifiedCount > 0
   Do not show raw GUIDs as the title.

3. Pill colors: one accent for in-progress steps (takeoff_begun,
   rfps_sent, rfps_received), a stronger accent or filled for
   final_pricing / awaiting_approval, muted for files_ingested,
   muted separate color for outcome. Do not copy Bluebeam blue.

4. Context menu on a row:
   - Open
   - Set step… (the seven steps; disabled ones illegal — still send
     through Transition API in S4; for this prompt the menu can
     call the service and refresh on success)
   - Set outcome…
   Existing Open / Remove from this PC stay.

5. Do not add Estimate/Reports as Queue sibling tabs.
   Double-click / Enter opens the job (existing behavior).

6. dotnet build && dotnet test. Fix failures.

When done, append to docs/STATUS.md:
"S3 — Queue pipeline pills + counts loaded from estimate-queue snapshot."
```

---

## PROMPT S4 — Transitions + offline pending + lock flags

```
We are building USISPdfApp (WPF .NET 8).
Read docs/ESTIMATE_STATUS_TRACKER.md § Stored vs derived and § Desktop.

GOAL
Manual steps write to the database via the transition API. Offline
queues one pending transition. Server snapshot wins after sync.

TASK

1. Transition UI (Queue menu already started in S3; also add a compact
   pipeline chip on the open Job — Estimating context bar right side
   OR job chip — showing current pill). Actions:
   - Takeoff finished
   - RFPs received
   - Final pricing (confirm; if unpricedLineCount > 0 require Force
     + reason)
   - Awaiting approval
   - Reopen takeoff (to takeoff_begun + reason)
   - Unlock pricing (from final_pricing / awaiting_approval)

2. Online: call TransitionEstimateStatusAsync. Replace local
   estimatePipeline with returned snapshot. Refresh queue cache
   entry for that id.

3. Offline: write job.json estimatePipeline.pendingTransition
   { toStatus, reason, force, queuedAt }. Show pill as the pending
   target with a small pending hint. Do not invent a second status
   field. On next successful sync, POST the pending transition,
   clear pending, store server snapshot.

4. When status == awaiting_approval (and no pending unlock):
   treat estimate line edits as locked in the Estimate grid
   (read-only + banner). Do not implement a full approval inbox.

5. Outcome setter: PATCH or reuse transition endpoint if backend
   exposes outcome on the same resource; otherwise add
   SetEstimateOutcomeAsync on ISyncService. Outcome must not change
   estimateStatus.

6. Tests: pendingTransition serializes; successful sync clears it;
   force required path is explicit in the method signature.

7. dotnet build && dotnet test. Fix failures.

When done, append to docs/STATUS.md:
"S4 — Status transitions POST to API; offline pendingTransition; approval lock."
```

---

## PROMPT S5 — RFP packages (DB-backed list)

```
We are building USISPdfApp (WPF .NET 8).
Read docs/ESTIMATE_STATUS_TRACKER.md § estimate_rfp_packages and
docs/REPORT_WRITER_IMPLEMENTATION.md (Request for Quote).

GOAL
Vendor RFPs are rows in the database. The app lists and updates them.
Counts on Queue come from the server snapshot after those writes.

TASK

1. UI: a dense list reachable from Estimating → Reports (RFQ selected)
   and/or a "RFPs" flyout from the pipeline chip. Not a new Office
   module tab. Not a PlanSwift ribbon.

   Columns: Vendor, Trade, Status (Draft/Sent/Received/Void), Sent,
   Due, Received, Quote amount.

2. Actions: Add, Mark sent, Mark received (quote amount optional),
   Void. Each action calls UpsertRfpPackageAsync then
   GetEstimateStatusAsync (or use API response if PATCH returns
   snapshot) and refresh the Job chip + Queue cache row.

3. Mark sent on the first package may move pipeline to rfps_sent
   on the server. Desktop must display whatever the snapshot says.
   Do not locally force rfps_sent if the server did not.

4. Empty state: "No vendor RFPs yet" + Add.

5. Offline: queue package mutations next to pendingTransition
   (small list pendingRfpEdits). Same sync rule: server wins.

6. dotnet build && dotnet test. Fix failures.

When done, append to docs/STATUS.md:
"S5 — RFP packages CRUD via API; Queue shows sent/received counts from snapshot."
```

---

## PROMPT S6 — Wire recompute triggers on desktop save + harden

```
We are building USISPdfApp (WPF .NET 8).
Read docs/ESTIMATE_STATUS_TRACKER.md acceptance list.

GOAL
After local takeoff/ingest work uploads, the next status load reflects
server recompute (files ingested / takeoff begun). No extra manual step.

TASK

1. After a successful UploadPendingAsync (or existing job upload)
   for a linked leadEstimateId, call GetEstimateStatusAsync and
   replace estimatePipeline on the open job + the matching
   estimate-queue.json row.

2. If the backend exposes POST .../status/recompute, call it once
   after upload then GET status. If 404, skip — rely on server
   triggers from S1.

3. Unlinked / pure offline jobs: do not fake pipeline auto-advance
   on the client. Leave status unloaded or last snapshot.

4. Smoke through the acceptance list in the spec. Add tests where
   cheap (cache merge of one queue row; no UI tests required).

5. dotnet build && dotnet test. Fix failures.

When done, append to docs/STATUS.md:
"S6 — Post-upload status reload from DB snapshot; tracker load path complete."
```

---

## Order vs other packs

- Office chrome U6 (Queue pills) can land on empty/unknown status until S3. S3 replaces placeholder pills.  
- Job package J1 is independent; `estimatePipeline` is a new object on `job.json`.  
- Do not block this pack on E3 assemblies. Unpriced counts work on E2 lines or markup cost fields if that is what the server already stores.
