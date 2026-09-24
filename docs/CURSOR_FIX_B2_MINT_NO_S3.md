# Cursor — Kill S3 mint (website first, then desktop 0.1.163)

**Date:** 2026-09-06 17:10  
**Spec:** `docs/DRAWING_FILE_STORE.md`  
**Also:** `docs/JOB_SYNC_STATUS.md` (the 306 still show as Failed)  
**App that failed the 17:02–17:10 retry:** desktop **0.1.162**. Live Flask still serves S3.

How to run:

1. **New Cursor Agent chat on the usiscm / website repo.** Paste **WEB0**. Deploy that before another office Retry.
2. **New Cursor Agent chat on `D:\USISPdfApp`.** Paste **D163**. Ship as **0.1.163**.
3. Then Retry failed on the office job. Expect codes to move toward Synced, or stay `B2_UPLOAD_URL_UNAVAILABLE` if Render still cannot call `b2_get_upload_url` — **never** `B2_HTTP_403` / `InvalidAccessKeyId`.

Do not re-ingest. Do not delete the 306 rows. Do not rebuild Ingest UI.

---

## What the 17:10 retry proved

Same 306 drawings. Local PDFs still on this PC. Nothing deleted.

| Count | Code | What the live stack did |
|---|---|---|
| 201 | `B2_UPLOAD_URL_UNAVAILABLE` | Flask could not mint native B2. Desktop skipped the file. Correct *reaction*, wrong *cause* (Render never reached `b2_get_upload_url`). |
| 105 | `B2_HTTP_403` | Flask fell back to S3 presigned PUT. Desktop **0.1.162 PUT that URL**. B2 XML: `InvalidAccessKeyId` / `Malformed Access Key Id`. |

Live names (do not invent new ones):

| Place | Symbol |
|---|---|
| Flask | `native_upload_hint_for_drawing` |
| Route the desktop calls | `POST /api/v1/drawings/{id}/upload-session` |
| S3 payload kind | `s3_presigned_put` |
| Locked native route (not on live Flask) | `POST /api/v1/drawings/{id}/b2-upload-url` + `protocol: "b2-native"` |

0.1.162 still **accepts** S3 instead of `S3_FALLBACK_FORBIDDEN`. That is why 105 files hit B2 with a broken key.

---

## Locked rules

1. Website never returns an S3 upload URL. `native_upload_hint_for_drawing` is native B2 or 503 `B2_UPLOAD_URL_UNAVAILABLE`.
2. Desktop never PUTs a URL that contains `X-Amz-`, `amazonaws`, `s3.`, or kind/protocol `s3_presigned_put`. Record `S3_FALLBACK_FORBIDDEN`, next file.
3. Desktop POSTs bytes only to a native `b2_upload_file` URL with B2 headers (`Authorization` = mint token, `X-Bz-File-Name`, `X-Bz-Content-Sha1`). `ExpectContinue = false`.
4. Keep calling `upload-session` if that is what 0.1.162 uses — but only after WEB0 makes that session native-only. Also accept / add `b2-upload-url` as the same handler.
5. Cache-first ingest is unchanged. Retry failed only.

---

## FIND FIRST

Website repo:

- `native_upload_hint_for_drawing`
- `upload-session` / `s3_presigned_put` / `b2_get_upload_url` / `generate_presigned`
- `ack-file` / `file_pending`

Desktop (`D:\USISPdfApp`):

- `upload-session` / `s3_presigned_put` / `B2_HTTP_403` / `B2_UPLOAD_URL_UNAVAILABLE`
- `S3_FALLBACK_FORBIDDEN` (should exist as a code; 0.1.162 does not use it)
- ObjectStore / ExpectContinue / ingest-upload-queue

---

## PROMPT WEB0 — Paste into the website / usiscm repo first

```
We are changing live Flask usiscm so drawing upload sessions are native
Backblaze only. Desktop 0.1.162 still calls POST /api/v1/drawings/{id}/upload-session.

READ docs/DRAWING_FILE_STORE.md (USISPdfApp) if that file is in this workspace;
otherwise follow this prompt exactly.

BUG (office retry 2026-09-06 17:02–17:10)
306 drawings still failed.
201 B2_UPLOAD_URL_UNAVAILABLE — native mint missed.
105 B2_HTTP_403 InvalidAccessKeyId — this server returned an S3 presigned PUT
from native_upload_hint_for_drawing; desktop PUT it; B2 rejected the
slash-encoded X-Amz-Credential.

TASK
Stop the S3 fallback. Mint native B2 or return 503. Do not delete drawing rows.

FIND FIRST
Grep native_upload_hint_for_drawing, upload-session, s3_presigned_put,
b2_get_upload_url, generate_presigned, PutObject, ack-file.
Edit those functions. Do not add a second mint next to them.

IMPLEMENT

1. native_upload_hint_for_drawing
   Call cached b2_authorize_account → b2_get_upload_url only.
   DELETE / never take the branch that builds s3_presigned_put,
   presigned PUT, or any X-Amz- query string.

   Success JSON (keep { "item": ... } envelope if that is the house style):
     protocol: "b2-native"
     uploadUrl: exact URL from B2 (must contain b2_upload_file, not X-Amz-)
     authorizationToken: B2 token
     bucketId, fileName, expiresAt
   If you currently use different keys (url / token / kind), keep the old
   keys ALSO set to the native values so 0.1.162 can read them, but
   kind/protocol MUST be b2-native, never s3_presigned_put.

   Failure: HTTP 503
     { "error": { "code": "B2_UPLOAD_URL_UNAVAILABLE",
       "message": "The website could not mint a Backblaze upload URL. The drawing row is on usiscm, but the PDF was not stored." } }
   Do not 200 an S3 body when B2 mint fails.

2. POST /api/v1/drawings/{id}/upload-session
   Must use the function above. Same for documents if they share it.

3. Add alias POST /api/v1/drawings/{id}/b2-upload-url
   Same handler, same body. Desktop 0.1.163 may call either.

4. PUT /api/v1/drawings/{id}/content stays 410 if it exists.
   GET /file on file_pending stays 409, never 200 empty.

5. Log when mint fails (drawing id + B2 error). Do not log the S3 path
   as a successful hint.

TESTS
- Fixture: b2_get_upload_url raises → response 503, body has no X-Amz-
  and no s3_presigned_put
- Fixture: B2 returns uploadUrl + token → protocol/kind is b2-native,
  URL contains b2_upload_file
- No test may expect an S3 fallback

Deploy to Render before another office Retry failed.
```

---

## PROMPT D163 — Paste into D:\USISPdfApp after WEB0 is on Render

```
We are building USISPdfApp (WPF .NET 8) at D:\USISPdfApp. Ship as 0.1.163.

READ
- docs/DRAWING_FILE_STORE.md
- docs/CURSOR_FIX_B2_MINT_NO_S3.md (this file)

BUG
0.1.162 called POST /api/v1/drawings/{id}/upload-session and PUT the
result even when it was s3_presigned_put. 105 sheets got B2_HTTP_403
InvalidAccessKeyId. 201 mint misses were recorded correctly as
B2_UPLOAD_URL_UNAVAILABLE but the app still accepted S3 when a session
came back.

TASK
Refuse every S3 session. Upload bytes only to a native b2_upload_file URL.
Do not rebuild Ingest. Do not re-ingest the 306.

FIND FIRST
Grep upload-session, s3_presigned_put, B2_HTTP_403, B2_UPLOAD_URL_UNAVAILABLE,
S3_FALLBACK_FORBIDDEN, X-Amz-, ObjectStore, ExpectContinue, ingest-upload-queue.
Edit the existing worker. No third uploader.

IMPLEMENT

1. Session guard (run before any PUT/POST of PDF bytes)
   Reject and set S3_FALLBACK_FORBIDDEN (do not touch B2) when ANY of:
   - protocol or kind == s3_presigned_put / s3 / presigned
   - uploadUrl / url contains X-Amz- or X-Amz-Credential or amazonaws or "s3."
   - URL does not look like native B2 (no b2_upload_file / no B2 host)
   Accept only protocol/kind b2-native (or missing kind BUT url is clearly
   b2_upload_file and has no X-Amz-).

2. HTTP
   POST the PDF to the mint uploadUrl with B2 headers only
   (Authorization = session token, X-Bz-File-Name, X-Bz-Content-Sha1,
   Content-Type application/pdf). ExpectContinue = false.
   Dedicated client — no site Bearer.
   Do not PUT an S3 URL "to keep compatibility."

3. Prefer POST /api/v1/drawings/{id}/b2-upload-url when the server
   advertises it; otherwise keep upload-session. Both must pass the guard.

4. 503 / empty session → B2_UPLOAD_URL_UNAVAILABLE, next file.
   Do not fall back to S3.
   B2 403 + URL had X-Amz- → S3_FALLBACK_FORBIDDEN (not a retryable 403).

5. Version banner / about = 0.1.163.

TESTS
- upload-session JSON with s3_presigned_put → no HTTP to that URL,
  lastErrorCode S3_FALLBACK_FORBIDDEN
- JSON with X-Amz-Credential in the URL → same
- JSON protocol b2-native + b2_upload_file URL → ObjectStore POST fired,
  ExpectContinue false, no Bearer
- 503 B2_UPLOAD_URL_UNAVAILABLE → no S3 attempt

Build + test. STATUS: "0.1.163 refuses S3 upload-session; native B2 only."
```

---

## After both are live

Retry failed on the office job (Job → Sync Status).

| If you see | Meaning |
|---|---|
| Rows moving Queued → Uploading → Synced | Path works |
| Only `B2_UPLOAD_URL_UNAVAILABLE` | Website still cannot reach `b2_get_upload_url` (Render → B2 auth). Fix keys / network on Flask. Do not turn S3 back on. |
| Any new `B2_HTTP_403` + InvalidAccessKeyId | Desktop still accepted S3, or Flask still emitted it. Stop and re-check WEB0 + D163. |

Local files stay. Website placeholders clear only after ack.
