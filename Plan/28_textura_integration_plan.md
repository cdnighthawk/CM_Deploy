# Textura Payment Management — Integration Plan

**Status:** Phase 1 implemented (2026-05-16)  
**Last updated:** 2026-05-16  
**Owner:** USIS CM engineering  
**Reference:** [Oracle Textura REST API](https://docs.oracle.com/cd/E97085_01/English/api/index.html)

---

## 1. Goals

Integrate USIS CM with **Oracle Textura Payment Management (TPM)** so payment and contract data stays consistent between systems without duplicate entry.

| Goal | Success metric |
|------|----------------|
| Pull certified pay apps and SOV from Textura into USIS | Project Invoicing tab shows Textura-sourced apps within one sync cycle |
| Push subcontracts and change orders from USIS to Textura | New/updated `commitments` appear in TPM after import job completes |
| Auditable sync | Every run logged with counts, errors, and timestamps |
| Safe defaults | Read-only pull enabled first; push behind explicit config + UI confirm |

**Out of scope (v1):** Real-time webhooks (TPM is job-based), full document binary sync, TPA enrollment, supplier diversity.

---

## 2. Context — what exists today

| Area | State |
|------|--------|
| Pay applications (G702/G703) | Implemented — `pay_applications`, `pay_application_lines`, API + Invoicing UI (“Textura-like” layout only) |
| Prime contract SOV | `prime_contract_sov_lines` |
| Subcontracts | `commitments` where `commitment_kind = 'subcontract'` |
| Companies / subs | `companies` (`company_type` includes `subcontractor`) |
| External sync pattern | **BuildingConnected** — OAuth, encrypted tokens, `POST /integrations/buildingconnected/sync` |
| Textura API code | **None** — no client, env vars, or routes |

**Template to mirror:** `backend/app/integrations/buildingconnected_client.py`, `backend/app/api/_integration_bc.py`, `backend/tests/test_buildingconnected_api.py`.

---

## 3. Textura API characteristics

TPM exposes a **REST API** with async export/import jobs.

| Pattern | Behavior |
|---------|----------|
| Auth | HTTP header `Authentification: <base64 or basic credentials>` — TPM username + password (not OAuth) |
| Production base | `https://services.texturacorp.com/ebis/api/` |
| Test base | `https://usint1.textura.oraclecloud.com/ebis/api/` |
| Export | `POST` → response `URI` with `jobID` → poll `GET` until complete |
| Import | Same job pattern on `/api/v1/import/*` and `/api/v2/*` |

### Endpoints relevant to USIS (by phase)

| TPM category | Method / path | USIS use |
|--------------|---------------|----------|
| **E05** Projects | `GET /api/v2/owner/projects` | Link TPM projects → `projects` |
| **E01** Invoices | `POST /api/v1/export/invoices` + poll | Upsert `pay_applications` + lines |
| **E03** Payments | `POST /api/v1/export/payments` + poll | Update pay app `status` → `paid` |
| **E02** Invoice rejections | `POST /api/v1/export/invoice-rejections` + poll | Notes / status rollback |
| **E04** Documents | export + meta + file | Phase 3 — lien waivers, COI |
| **I01** Subcontracts | `POST /api/v1/import/insert-contracts` | Push `commitments` (subcontracts) |
| **I02** Change orders | `POST /api/v1/import/changeorders` | Push commitment COs |
| **I04** Projects | `POST /api/v1/import/projects` | Push new USIS projects to TPM |
| **I07** Owner invoices | `POST /api/v2/owner-invoices` | Push certified pay apps (Phase 2b) |

Full endpoint list: [All REST Endpoints](https://docs.oracle.com/cd/E97085_01/English/api/rest-endpoints.html).

---

## 4. Assumptions and prerequisites

Confirm with Textura account admin **before Phase 1 coding**:

1. **API access enabled** on the TPM tenant (separate from UI login).
2. **API user** with rights to export invoices/projects and (later) import contracts.
3. **USIS role in TPM** — plan below assumes **GC / contractor** pulling owner-side exports where applicable; adjust endpoints if USIS acts as **subcontractor** only.
4. **Project matching key** — agree whether to link on `projects.number`, contract ID, or a new `textura_project_id` column.
5. **Source of truth** — recommended: **Textura wins** for certified amounts and payment status; **USIS wins** for draft pay apps and internal SOV until submitted.

---

## 5. Architecture

```
┌─────────────────┐     session auth      ┌──────────────────────────────┐
│ W3CRM UI        │ ────────────────────► │ Flask /api/v1/integrations/  │
│ (Integrations   │                       │ textura/*                    │
│  settings +     │                       └──────────────┬───────────────┘
│  Sync button)   │                                      │
└─────────────────┘                                      ▼
                                              ┌──────────────────────┐
                                              │ textura_sync.py      │
                                              │ (map + upsert)       │
                                              └──────────┬───────────┘
                                                         │
                    ┌────────────────────────────────────┼────────────────────────┐
                    ▼                                    ▼                        ▼
         textura_client.py                    textura_credentials         PostgreSQL
         (httpx, job poll)                    (encrypted row)            pay_applications
                    │                                                      commitments
                    ▼                                                      projects + ids
         Oracle TPM REST API
```

### New modules

| File | Responsibility |
|------|----------------|
| `backend/app/integrations/textura_client.py` | Submit export/import jobs, poll until terminal state, parse JSON payloads |
| `backend/app/integrations/textura_sync.py` | Entity mappers: TPM ↔ SQLAlchemy |
| `backend/app/api/_integration_textura.py` | Routes, credential CRUD, sync orchestration |
| `backend/app/models/textura_credential.py` | Encrypted username/password (reuse Fernet from BC) |
| `backend/app/models/textura_sync_log.py` | Optional: per-run audit (or use generic `sync_queue` when built) |
| `backend/tests/test_textura_integration.py` | Mock httpx; no live TPM in CI |

Register in `backend/app/api/v1.py`:

```python
from . import _integration_textura
_integration_textura.register_textura_routes(bp)
```

### Configuration (`config.py` + `.env.example`)

| Variable | Purpose |
|----------|---------|
| `TEXTURA_API_BASE` | Default prod URL; override for test tenant |
| `TEXTURA_USERNAME` | API user (or store only in DB after setup UI) |
| `TEXTURA_PASSWORD` | API password (encrypted at rest if persisted) |
| `TEXTURA_SYNC_ENABLED` | Master switch (default off in production) |
| `TEXTURA_SYNC_PUSH_ENABLED` | Allow import/push operations (default off) |
| `TEXTURA_POLL_INTERVAL_SEC` | Job poll interval (default 2) |
| `TEXTURA_POLL_TIMEOUT_SEC` | Max wait per job (default 300) |
| `TOKEN_ENCRYPTION_KEY` | Reuse existing Fernet key for stored credentials |

---

## 6. Data model changes

### 6.1 Migration `00xx_textura_external_ids`

Add external linkage columns (nullable; backfill on first sync):

| Table | Column | Type | Notes |
|-------|--------|------|-------|
| `projects` | `textura_project_id` | `String(64)` | Unique where not null |
| `pay_applications` | `textura_invoice_id` | `String(64)` | Unique per project |
| `commitments` | `textura_contract_id` | `String(64)` | Subcontracts only |
| `companies` | `textura_vendor_id` | `String(64)` | Optional; vendor matching |

Indexes: `(textura_project_id)`, `(project_id, textura_invoice_id)`.

### 6.2 Optional — `textura_sync_logs`

| Column | Type |
|--------|------|
| `id` | UUID PK |
| `direction` | `export` \| `import` |
| `entity_type` | `projects`, `invoices`, `payments`, `subcontracts`, … |
| `project_id` | FK nullable |
| `started_at`, `finished_at` | timestamptz |
| `status` | `running`, `success`, `partial`, `failed` |
| `loaded`, `skipped`, `errors` | integers + JSON error list |
| `tpm_job_id` | string |

Aligns with roadmap `sync_queue` in `backend/README.md`; can merge later.

---

## 7. Field mapping (core entities)

### 7.1 Projects (export E05 → `projects`)

| Textura (typical) | USIS `projects` |
|-------------------|-----------------|
| Project ID | `textura_project_id` |
| Project number / code | `number` |
| Project name | `name` |
| Address fields | `address_line1`, `city`, `state`, `zip` |
| Status | Map to `project_status` enum |

**Matching order:** `textura_project_id` → `number` (case-insensitive) → create stub project (config flag `TEXTURA_AUTO_CREATE_PROJECTS`, default false).

### 7.2 Invoices (export E01 → `pay_applications` + lines)

| Textura invoice | USIS |
|-----------------|------|
| Invoice / app number | `application_number` |
| Period end | `period_to` |
| Original contract sum | `original_contract_sum` |
| Net change by COs | `net_change_by_change_orders` |
| Totals (completed, retainage, current due, …) | G702 summary fields on `PayApplication` |
| Line items (phase, description, scheduled value, work this period, …) | `PayApplicationLine` |

**Status mapping:**

| TPM state | `pay_application.status` |
|-----------|--------------------------|
| Draft / in progress | `draft` |
| Submitted | `submitted` |
| Approved / certified | `certified` |
| Paid (from E03 payments) | `paid` |

**Conflict rule:** If USIS row is `draft` and TPM has certified data, TPM overwrites amounts and sets `certified`. If USIS is `draft` and user edited locally after last sync, set `sync_conflict` flag in sync log (do not silently overwrite — Phase 1.1).

### 7.3 Subcontracts (USIS → import I01)

| USIS `commitments` | Textura import |
|--------------------|----------------|
| `commitment_kind = subcontract` | Contract type subcontract |
| `reference_number` | Contract number |
| `title` | Description |
| `vendor_company_id` → company | Vendor ID (requires `textura_vendor_id` or TPM vendor match) |
| Line items | SOV / contract value lines |
| `status = approved` | Only push approved commitments (configurable) |

### 7.4 Prime SOV

TPM does not expose a 1:1 “prime SOV only” export in the summary table; SOV often arrives **inside invoice line payloads**. Phase 1: populate `pay_application_lines` from invoices. Phase 2: if invoice export includes master SOV, optionally refresh `prime_contract_sov_lines` when `TEXTURA_SYNC_PRIME_SOV=1`.

---

## 8. API surface (USIS)

All routes require session auth (same as BC). Prefix: `/api/v1/integrations/textura`.

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/status` | Connection configured, last sync summary |
| `PUT` | `/credentials` | Save encrypted API credentials (admin) |
| `DELETE` | `/credentials` | Remove stored credentials |
| `POST` | `/sync` | Full sync: projects → invoices → payments |
| `POST` | `/sync/projects` | Projects only |
| `POST` | `/sync/invoices` | Invoices for all linked projects |
| `POST` | `/projects/<project_id>/sync` | Single-project pull |
| `POST` | `/push/subcontracts` | Import approved subs (requires `TEXTURA_SYNC_PUSH_ENABLED`) |
| `POST` | `/test-connection` | Lightweight auth check (no data mutation) |

**Response shape** (match BC):

```json
{
  "ok": true,
  "loaded": 12,
  "skipped": 3,
  "errors": 1,
  "error_details": [{ "entity": "pay_application", "external_id": "…", "message": "…" }],
  "entity": "textura_sync"
}
```

---

## 9. Client implementation notes

### 9.1 `TexturaClient`

```python
class TexturaClient:
    def __init__(self, base_url: str, username: str, password: str): ...
    def post_export_invoices(self) -> str: ...  # returns job URI or job_id
    def get_job(self, path: str) -> dict: ...
    def poll_job(self, path: str, *, timeout: float) -> dict: ...
    def get_owner_projects(self) -> list[dict]: ...
    def post_import_contracts(self, payload: list[dict]) -> str: ...
```

- Use `httpx` with 60s timeout on POST, shorter on poll GET.
- Parse `URI` from POST responses; extract `jobID` for polling.
- Handle TPM pagination if present in job result payload (loop until complete).

### 9.2 Idempotent upsert

- Upsert `pay_applications` on `(project_id, textura_invoice_id)`.
- Replace line items on sync (same as existing pay app PATCH behavior) **or** merge by `phase_code` + `description` hash if stable keys exist in TPM payload.
- Never delete USIS-only draft pay apps unless `TEXTURA_SYNC_PRUNE=1` (default false).

---

## 10. UI (W3CRM)

**Location:** Project detail → new **Integrations** sub-tab or Settings → Integrations (global).

| Element | Behavior |
|---------|----------|
| Connection status | Configured / not configured / last error |
| Credentials form | Admin-only; POST to `/credentials` |
| **Sync from Textura** button | `POST .../projects/<id>/sync` |
| Last sync time + counts | From `textura_sync_logs` or last API response |
| Pay app row badge | “Synced from Textura” when `textura_invoice_id` set |

Reuse patterns from any existing BC admin UI if present; otherwise minimal Bootstrap card in `gulp/src/construction/`.

---

## 11. Phased delivery

### Phase 0 — Discovery (1–2 days)

- [ ] Obtain TPM API credentials (test tenant preferred)
- [ ] Run manual `curl` against test base: export invoices POST + GET job
- [ ] Capture sample JSON for projects, invoice header, line items, payment
- [ ] Confirm USIS role (GC vs sub) and which export endpoints are licensed

**Deliverable:** `Plan/textura_samples/` JSON fixtures (sanitized) for tests.

---

### Phase 1 — Read path (MVP) — ~1.5 weeks

| Task | Est. |
|------|------|
| Migration: external ID columns | 0.5 d |
| `TexturaClient` + job polling | 1 d |
| `textura_sync` — projects + invoices | 2 d |
| `_integration_textura` routes + config | 1 d |
| Tests with fixtures | 1 d |
| UI: sync button + status on project detail | 1 d |

**Exit criteria:** One real project syncs certified pay apps into Invoicing tab; sync logged; tests green.

---

### Phase 1.1 — Payments + rejections — ~3 days

- Export payments (E03) → update `status = paid`
- Export invoice rejections (E02) → `notes` + status adjustment
- Conflict detection for dirty local drafts

---

### Phase 2 — Push path — ~1 week

| Task | Est. |
|------|------|
| Map `commitments` → I01 insert/update contracts | 2 d |
| Vendor resolution (`textura_vendor_id` or fuzzy name match) | 1 d |
| `TEXTURA_SYNC_PUSH_ENABLED` guard + admin confirm in UI | 0.5 d |
| Tests for import payload builder | 1 d |

**Exit criteria:** Approved subcontract in USIS appears in TPM after import job success.

---

### Phase 2b — Push pay apps — ~1 week

- Map certified USIS pay app → `POST /api/v2/owner-invoices`
- Only when status transitions to `submitted` / user clicks “Send to Textura”
- Store returned TPM invoice id on success

---

### Phase 3 — Documents & compliance — backlog

- E04 document export (metadata + file download to B2)
- I03 compliance requirements
- Link documents to `documents` polymorphic table

---

### Phase 4 — Operations — backlog

- Scheduled sync (Celery beat or Render cron hitting `POST /sync`)
- Implement `sync_queue` table from README roadmap for retries
- Email notification on sync failure (reuse RFI mail stack)

---

## 12. Testing strategy

| Layer | Approach |
|-------|----------|
| Unit | Mapper functions: TPM JSON fixture → ORM dict |
| API | Flask test client; mock `TexturaClient` |
| Integration (manual) | Test tenant credentials; one project end-to-end |
| Regression | Ensure existing `test_pay_applications_api.py` unchanged for non-synced rows |

Fixtures derived from Phase 0 samples; no secrets in repo.

---

## 13. Security and compliance

- Store TPM password **only** encrypted (`TOKEN_ENCRYPTION_KEY`); never log credentials.
- Restrict `/credentials` and `/push/*` to admin role when RBAC enforced.
- Audit log entry on each sync: user id, counts, timestamp (`audit_log` table).
- Use test base URL in dev; prod credentials only on Render/production env.

---

## 14. Deployment (Render)

Add to `render.yaml` / dashboard env:

```
TEXTURA_API_BASE=https://services.texturacorp.com/ebis/api
TEXTURA_SYNC_ENABLED=0
TEXTURA_SYNC_PUSH_ENABLED=0
```

Enable per environment after UAT. Document setup steps in `backend/README.md` (mirror BuildingConnected section).

---

## 15. Risks and mitigations

| Risk | Mitigation |
|------|------------|
| API access not provisioned on tenant | Phase 0 gate; contact Oracle/Textura support early |
| Async jobs timeout on large exports | Configurable poll timeout; project-scoped sync |
| Field mismatch TPM ↔ G702 model | Phase 0 samples; mapper unit tests; nullable fields |
| Duplicate projects | Strict `textura_project_id` unique; manual merge tool later |
| Overwriting user drafts | Conflict flag; TPM wins only when USIS status is `submitted`+ or user confirms |
| Sub role vs owner endpoints | Document role in config `TEXTURA_ACCOUNT_ROLE=gc|sub|owner` |

---

## 16. Open decisions (need product input)

1. **Primary sync direction for v1** — pull-only vs bidirectional?
2. **Auto-create projects** from TPM when no match?
3. **Who can run sync** — all project users or admins only?
4. **Corecon relationship** — should Textura invoice ids link to `corecon_transactions`?
5. **Scheduled sync frequency** — nightly vs on-demand only?

---

## 17. Implementation checklist (agent mode)

When ready to implement, switch to **Agent mode** and execute in order:

1. Phase 0 sample capture (or use provided fixtures)
2. `00xx_textura_external_ids` migration
3. `textura_client.py` + `textura_sync.py`
4. `textura_credential` model + `_integration_textura.py`
5. Register routes + `config.py` / `.env.example`
6. `test_textura_integration.py`
7. Gulp UI sync control
8. `backend/README.md` setup section
9. Manual UAT on test tenant → enable prod env vars

**Prompt for agent:** “Implement Textura integration Phase 1 per `Plan/28_textura_integration_plan.md`.”

---

## 18. References

- [Textura REST API — About](https://docs.oracle.com/cd/E97085_01/English/api/index.html)
- [All REST Endpoints](https://docs.oracle.com/cd/E97085_01/English/api/rest-endpoints.html)
- [E01 Invoices export (POST)](https://docs.oracle.com/cd/E97085_01/English/api/op-v1-export-invoices-post.html)
- USIS: `backend/app/api/_integration_bc.py` (sync pattern)
- USIS: `backend/app/models/pay_application.py` (target schema)
- USIS: `Plan/27_pay_applications_impl_payload.md` (invoicing UI)
