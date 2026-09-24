# Drawing File Store — Cache first, trickle to B2, never through Render

**Date:** 2026-09-06  
**Status:** Locked — Ingest **saves every sheet to this PC first**. The estimator opens those cache files and starts takeoff immediately. Cloud upload is a **slow background queue** (one file at a time, desktop → native B2). Render never carries the PDF. That is how we keep Render alive.  
**Supersedes:** `docs/DRAWING_INGEST.md` Phase B byte path (`PUT /api/v1/drawings/{id}/content` through usiscm) and Cursor I6’s same PUT. Phase A in that spec stays and is the success path.  
**Related:** `docs/DRAWING_INGEST.md`, `docs/LOCAL_CACHE_JOB_OPEN_AND_CLEANUP.md`, `docs/OFFLINE_FIRST_AND_SYNC_DESIGN.md`, `docs/CURSOR_IMPLEMENT_DRAWING_FILE_STORE.md`

**Why this exists:** The estimator must work after ingest even if the website is down. The office failure was the opposite loop: create row on usiscm, push the PDF through Render, hammer retries, crash Render, leave placeholders. Local files were already on disk the whole time.

**Live as of 2026-09-06 17:10:** Retry of the same 306 left them all `failed`. 201 `B2_UPLOAD_URL_UNAVAILABLE`. 105 `B2_HTTP_403` (S3 XML `InvalidAccessKeyId`). usiscm function `native_upload_hint_for_drawing` still returns an S3 presigned PUT when `b2_get_upload_url` fails. Desktop 0.1.162 still calls `POST /api/v1/drawings/{id}/upload-session` and PUTs that URL. Locked route `POST /b2-upload-url` + `protocol: "b2-native"` is **not** on live Flask. 0.1.163 must refuse `s3_presigned_put` / `X-Amz-` as `S3_FALLBACK_FORBIDDEN`. Website ships first.

---

## Estimator loop (this is the product)

```
Ingest review
    │  user hits Upload
    ▼
Phase A — THIS PC (blocks the button only)
    copy each included sheet → %LocalAppData%\USISPdfApp\drawings\{id}\{file}
    copy same bytes → job.usisjob\files\
    write Sheet + SheetIssue on job.json
    button reports success
    ▼
Estimator opens a sheet from cache and takeoffs   ← does not wait on network
    │
    ▼
Phase B — background (never blocks takeoff)
    1 file at a time
    POST metadata to usiscm (tiny JSON)
    mint native B2 URL
    POST PDF to B2 from this PC
    ack
```

| After Phase A | Allowed |
|---|---|
| Open any committed sheet in Markup / Estimating | Yes — bytes come from the cache path |
| Drawings list shows the sheets | Yes — badge `on this PC` |
| Website / Android | Placeholder until that sheet’s Phase B ack |
| Unplug the network | Takeoff continues. Queue sits at `Queued` |

**Upload means “saved on this PC.”** Cloud is a status-bar count (`Uploading drawings 12 / 306`), not a gate.

Do not:

- Hold the Ingest success dialog on HTTP.
- Open the sheet by downloading from usiscm/`/file`.
- Upload 306 PDFs through Render in parallel.
- Treat a failed cloud write as a failed ingest.

---

## Cloud is complete only when

A drawing is **not in the cloud** until all three are true:

1. usiscm has the catalog row (`cloudDrawingId`).
2. B2 has the object (native `b2_upload_file` `fileId`).
3. usiscm has an **ack** that stored that `fileId` and cleared `file_pending`.

Local cache + the `.usisjob` copy are enough to takeoff. Cloud is eventual. Failed cloud write must not delete local files or extra-create rows.

---

## Locked path (every client)

```
┌─────────────┐   POST metadata          ┌─────────┐
│ Desktop /   │ ────────────────────────►│ usiscm  │  catalog row, file_pending
│ Website /   │                          │ (Render)│
│ Android     │   POST upload-session    │         │
│             │   or POST b2-upload-url  │         │
│             │ ────────────────────────►│         │  server calls b2_get_upload_url
│             │   { uploadUrl, token }   │         │
│             │◄──────────────────────── │         │
│             │                          └────┬────┘
│             │   POST PDF + B2 headers       │
│             │   (dedicated client)          │  no PDF on this hop
│             │───────────────────────► ┌─────▼─────┐
│             │   200 + fileId          │ Backblaze │
│             │◄─────────────────────── │    B2     │
│             │                          └─────┬────┘
│             │   POST ack-file               │
│             │ ────────────────────────►┌────▼────┐
│             │                          │ usiscm  │  store fileId, clear pending
└─────────────┘                          └─────────┘
```

Download is the reverse of the same idea: usiscm returns a **native B2 authorized download URL** (302 or JSON). Clients pull bytes from B2. Render must not GET the object through the S3 gateway.

---

## What is forbidden

| Do not | Why it already failed |
|---|---|
| PUT/POST PDF bytes to Render, then Render → B2 S3 | Socket died (`SSLEOFError`, `ConnectionClosedError`, connect/read timeout). Row saved as `file_pending`. No object. |
| Fall back to an S3 presigned PUT when native mint fails | Live `native_upload_hint_for_drawing` still does this. Desktop PUTs `upload-session`. .NET encodes `X-Amz-Credential` slashes. B2 403. 105 of 306 on the 17:10 retry (201 never got a URL at all). |
| Send `Expect: 100-continue` to B2 | B2 often rejects the handshake; the POST never completes. |
| Reuse the usiscm `HttpClient` (Microsoft 365 / API `Authorization`) for B2 | B2 rejects the write. |
| Re-POST `/drawings` when `cloudDrawingId` is already set | Duplicate catalog rows. |
| Retry the same sheet 140–349 times before moving on | Knocked Render over; left ~152 sheets queued. |
| Treat `GET /file` through Render S3 as source of truth | Empty / not-found even after a later native write. |
| Return HTTP 200 with an empty body for a pending file | Website and Android show a placeholder that looks like a file. |
| Browser CORS preset that only allows download, or `allowedHeaders: ["*"]` | Website POST blocked; Firefox still blocks `Authorization`. |

There is **no S3 fallback**. If native mint fails, the queue item is `Failed` with `B2_UPLOAD_URL_UNAVAILABLE`. Next sheet. Operator retries mint later.

---

## usiscm API (desktop-facing)

Envelopes stay `{ "item": ... }` / `{ "items": [...] }`.

### Mint — native only

Live Flask today:

```
POST /api/v1/drawings/{drawingId}/upload-session
```

implemented by `native_upload_hint_for_drawing`. That function **must stop** returning `s3_presigned_put`. Same handler (or an alias) may also be exposed as:

```
POST /api/v1/drawings/{drawingId}/b2-upload-url
```

Both must call `b2_authorize_account` (cached) → `b2_get_upload_url` only.

Success:

```json
{
  "item": {
    "protocol": "b2-native",
    "uploadUrl": "https://pod-000-1001-00.backblaze.com/b2api/v2/b2_upload_file/...",
    "authorizationToken": "...",
    "bucketId": "...",
    "fileName": "jobs/{jobId}/drawings/{drawingId}/{fileName}.pdf",
    "expiresAt": "2026-09-06T22:10:00Z"
  }
}
```

`protocol` is always `b2-native`. Do not return `s3_presigned_put`, `presignedPut`, `s3Url`, or `contentPut`. If `b2_get_upload_url` fails, 503 — not an S3 URL.

Mint failure: **503**

```json
{
  "error": {
    "code": "B2_UPLOAD_URL_UNAVAILABLE",
    "message": "The website could not mint a Backblaze upload URL. The drawing row is on usiscm, but the PDF was not stored."
  }
}
```

That is GI101. Do not invent a second URL.

### Ack — only after B2 200

```
POST /api/v1/drawings/{drawingId}/ack-file
body: {
  "item": {
    "b2FileId": "...",
    "b2FileName": "...",
    "contentSha1": "...",
    "contentLength": 1234567,
    "sha256": "...",
    "contentType": "application/pdf"
  }
}
```

Server stores the B2 ids + hashes, clears `file_pending`. Idempotent on the same `b2FileId`.

Do not ack from the desktop until B2 returned 200 with that `fileId`.

### Download

```
GET /api/v1/drawings/{drawingId}/file
```

| Row state | Response |
|---|---|
| Acked, object in B2 | **302** `Location` = native B2 authorized download URL, or `200` JSON `{ "item": { "downloadUrl", "expiresAt", "sha256", "byteSize" } }`. Pick one and keep it. Prefer 302 for browsers; JSON is fine for the desktop. |
| `file_pending` / never acked | **409** `{ "error": { "code": "FILE_PENDING" } }`. Not 200 empty. |
| Row missing | **404** |

```
GET /api/v1/drawings/{drawingId}/file-status
→ { "item": { "filePending": true|false, "byteSize", "sha256", "b2FileId" } }
```

```
HEAD /api/v1/drawings/{drawingId}/file
```

Same pending/acked rules. Used by Open Job freshness. Must not hit the S3 gateway.

### Dead endpoints

| Path | Now |
|---|---|
| `PUT /api/v1/drawings/{id}/content` | **410**. Desktop must stop calling it. |
| Any Render-side S3 `PutObject` / `GetObject` for drawings | Removed. |

Metadata create is unchanged:

```
POST /api/v1/jobs/{jobId}/drawings
```

Create may leave `file_pending`. That is expected. Bytes are a later step.

Documents (spec books, bid forms) use the same mint / upload / ack pattern on `/api/v1/documents/{id}/…`. Same client, same bans.

---

## Desktop client rules

Two HTTP clients. Never one.

| Client | Talks to | Headers |
|---|---|---|
| `UsiscmClient` | `https://www.usiscm.com` (or the live API host) | Microsoft 365 / API `Authorization` |
| `ObjectStoreClient` | B2 upload and download hosts only | B2 `Authorization` token from the mint. **No** usiscm bearer. **No** default headers copied from the other client. |

`ObjectStoreClient`:

1. `ExpectContinue = false` on the handler and on every request (`0.1.154` already tried this — keep it).
2. Build `HttpRequestMessage` with `RequestUri = new Uri(uploadUrl, UriKind.Absolute)` from the **exact mint string**. Do not reconstruct, sort, or encode the query.
3. Headers on the B2 POST:
   - `Authorization: {authorizationToken}`
   - `X-Bz-File-Name: {url-encoded fileName from mint}`
   - `X-Bz-Content-Sha1: {hex sha1 of the file}`
   - `Content-Type: application/pdf`
   - `Content-Length`
4. Body = raw PDF bytes from local cache (`drawings/{drawingId}/{fileName}` or the job `files/` copy). Same `sha256` already on the SheetIssue.
5. Timeout sized for a large sheet (minutes), not the usiscm JSON timeout.
6. 401/403 from B2 → discard this mint, request a **new** upload URL, retry that sheet once. Do not reuse a spent B2 upload URL.
7. After 200, parse `fileId` / `contentSha1` / `fileName` and ack.

SHA-1 is what B2 checks. SHA-256 stays on the SheetIssue and in the ack for our records.

---

## Queue + retries

Persist: `%LocalAppData%\USISPdfApp\cache\ingest-upload-queue.json`.

Per item:

```
jobId, drawingId, cloudDrawingId?, localPath, contentHash, byteSize,
sheetNumber, fileName, state, attemptCount, lastErrorCode, lastErrorAt
```

States: `Queued → CreatingRow → Minting → Uploading → Acking → Synced | Failed`.

Worker rules:

1. **One file at a time** for this repair pack (1 is safer than 2 until Render is calm).
2. If `cloudDrawingId` is set, **skip create**.
3. Cap: **3 attempts per item per worker session**, then `Failed`, next item. Hard cap across launches: 8. Never 140.
4. Backoff 2s / 8s / 30s. After a mint 503, wait 30s before the next mint (any item).
5. A 403 `InvalidAccessKeyId` is **not** retried with the same URL kind. That code means someone handed us an S3 URL. Treat as a product bug: log the full URL host + whether the query contains `X-Amz-Credential`. Fail the item with `S3_FALLBACK_FORBIDDEN`. Do not hammer.
6. Failure never deletes local bytes, SheetIssues, or the usiscm row.
7. Status bar: `Uploading drawings {n} / {total}` and `306 failed — Retry cloud files`. Click opens the queue list.

`0.1.154` retry cap + skip-create stay. This pack makes them the only path.

---

## Repair the office set that is already stuck

The 306 failed items are the current job. Local PDFs exist. usiscm rows exist. B2 objects do not (except any later native write that downloads still miss).

**Retry failed cloud files** (Queue banner + Ingest session + File menu):

1. Load the persisted queue. Do not rebuild from usiscm.
2. Keep items whose `localPath` still exists and `contentHash` matches.
3. Reset `Failed` → `Queued`. Leave `Synced` alone.
4. Run the worker. Skip create when `cloudDrawingId` is present (almost every row).
5. Mint native → POST B2 → ack.
6. After ack, website / Android `GET /file` must 302 to B2, not empty.

GI101 (no mint): leave `Failed` / `B2_UPLOAD_URL_UNAVAILABLE` after 3 mint tries. Do not block the other 305.

Do **not** delete the placeholder rows and re-ingest. That would split and classify again. This is bytes + ack only.

---

## Website / Android (same bytes rule)

Desktop is the office uploader for this set. Website and Android must still:

- Call the same mint. Never POST the PDF to Render.
- Use a request that does not attach the site session cookie as `Authorization` in a way B2 will see — B2 header is only the mint token.
- CORS on the drawings bucket (website path):

  | Need | Value |
  |---|---|
  | Origins | `https://www.usiscm.com` and the live app origin |
  | Allowed operations | upload **and** download (the share-download preset is not enough) |
  | Allowed headers | named list: `Authorization`, `Content-Type`, `X-Bz-File-Name`, `X-Bz-Content-Sha1`, `X-Bz-Info-*` |
  | `allowedHeaders: ["*"]` | **Does not** authorize `Authorization` in Firefox. Do not rely on it. |

Android uses the JSON download URL or 302. It must surface `FILE_PENDING` as “file not on cloud yet,” not a blank viewer.

---

## Mapping of the twelve failures

| # | What happened | Lock |
|---|---|---|
| 1 | Render S3 PUT dropped the PDF | Bytes never touch Render |
| 2 | `b2_get_upload_url` failed (GI101) | 503 `B2_UPLOAD_URL_UNAVAILABLE`; no S3 stand-in |
| 3 | `Expect: 100-continue` | Off on `ObjectStoreClient` |
| 4 | 403 `InvalidAccessKeyId` from encoded S3 credential | No presigned S3. Exact mint URI |
| 5 | Retry storm | 3 / session, 8 lifetime, one-at-a-time |
| 6 | Shared `HttpClient` sent site auth to B2 | Two clients |
| 7 | Bucket CORS | Named headers + upload origin |
| 8 | Download via S3 GET | Native B2 download URL |
| 9 | PDFium FailFast on the VA bulletin | Already 0.1.153; out of this pack |
| 10 | `session.json` locked | Already 0.1.152; out of this pack |
| 11 | Duplicate create on retry | Skip create when `cloudDrawingId` set |
| 12 | Ack never ran | Ack only after B2 200 |

9–10 stay owned by ingest/PDFium. This pack does not reopen classify or split.

---

## Tests that must exist

Desktop:

- `ObjectStoreClient` requests to a fake B2 host have no `Bearer` and `ExpectContinue = false`.
- Given a mint JSON with `protocol: "s3"` or a URL containing `X-Amz-Credential`, the worker **refuses** and records `S3_FALLBACK_FORBIDDEN`.
- Create is not called when `cloudDrawingId` is set.
- Ack is not called on B2 403 / timeout.
- Attempt 4 in one session is not sent.
- Queue reload after crash resumes un-acked items only.

usiscm (wherever that repo lives):

- Mint handler never returns an S3 URL.
- `GET /file` on `file_pending` is 409, not 200 empty.
- Ack stores `b2FileId` and clears pending.
- `PUT /content` is 410.

---

## Non-goals

- Reclassify, resplit, or rebuild Ingest UI.
- Delete and recreate the 306 usiscm rows.
- Title-block AI, OCR, Velopack.
- Multipart / large-file B2 chunked upload (single `b2_upload_file` is enough for one sheet).
- Changing bucket names or account keys from the desktop. Keys stay on usiscm.

---

## Done when

1. One stuck sheet (not GI101) goes `Queued → Minting → Uploading → Acking → Synced`.
2. `GET /api/v1/drawings/{id}/file` for that id is a real PDF (302/JSON → B2), not empty.
3. Website and Android open that sheet.
4. The other failed items drain one-at-a-time without a Render outage.
5. GI101 either mints on retry or stays failed without S3.
6. New ingest after this build never calls `PUT /content` and never builds an S3 query string.
