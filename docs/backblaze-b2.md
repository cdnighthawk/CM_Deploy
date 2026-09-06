# Backblaze B2 object storage (USIS CM uploads)

Production on Render can store **project PDFs** (drawings, spec sections, RFI attachments) and **HR hire-wizard photos** (I-9, W-4, union documents) in [Backblaze B2](https://www.backblaze.com/b2/cloud-storage.html) instead of the Render persistent disk. The Flask app uses B2’s **S3-compatible API** via `boto3` when all required environment variables are set.

The website and API **read drawings from B2**, not from the office NAS. Local development without B2 vars continues to use `backend/instance/` (same as before).

## What is stored in B2

| Category | API examples | Object key pattern |
|----------|--------------|-------------------|
| Drawings | `POST /api/v1/projects/<id>/drawings` | `{prefix}/drawings/{job}/{discipline}/{set}/{filename}.pdf` (legacy `{uuid}.pdf` still served) |
| Project documents | `POST /api/documents` | `{prefix}/documents/{job}/{type}/{filename}` (legacy `{uuid}_{filename}` still served) |
| Spec sections | `POST .../spec_sections/<id>/file` | `{prefix}/spec_sections/{job}/specifications/{code}_{filename}.pdf` (legacy `{uuid}.pdf` still served) |
| RFI attachments | `POST /api/v1/rfis/<id>/attachments/upload` | `{prefix}/rfi_attachments/<uuid><ext>` |
| HR I-9 photos | `POST /api/v1/hr/me/i9-section1/documents` | `{prefix}/hr_i9/<uuid><ext>` |
| HR W-4 photos | `POST /api/v1/hr/me/w4/documents` | `{prefix}/hr_w4/<uuid><ext>` |
| HR union photos | `POST /api/v1/hr/me/hire-wizard/union-documents` | `{prefix}/hr_union/<uuid><ext>` |

`{prefix}` is optional (`B2_PREFIX`, e.g. `prod/usis-cm`). The Gulp static UI is **not** stored in B2.

## 1. Create a B2 bucket

1. Sign in to [Backblaze](https://www.backblaze.com/) → **B2 Cloud Storage** → **Buckets** → **Create a Bucket**.
2. **Bucket Unique Name**: `USIS-construction-docs` (globally unique in your account).
3. **Files in bucket are**: **Private** (the app serves downloads through Flask with session auth).
4. Note the **S3 endpoint** for your region (B2 bucket → **Bucket Settings** → **S3 Endpoint**), e.g. `https://s3.us-west-004.backblazeb2.com`.

## 2. Application key

1. **App Keys** → **Add a New Application Key**.
2. Name: e.g. `usis-cm-render`.
3. **Allow access to Bucket(s)**: restrict to the upload bucket.
4. Capabilities: at least **readFiles**, **writeFiles**, **deleteFiles**, **listBuckets** (or use a template that includes object read/write/delete).
5. Save **keyID** → `B2_APPLICATION_KEY_ID` and **applicationKey** → `B2_APPLICATION_KEY` (shown once).

Backblaze shows **two** values when you create an application key. They are not interchangeable:

| B2 UI label | Render / `.env` variable | Notes |
|-------------|--------------------------|--------|
| **keyID** | `B2_APPLICATION_KEY_ID` | Public identifier (often starts with `003`) |
| **applicationKey** | `B2_APPLICATION_KEY` | Secret; shown **once** at creation |

The app does **not** read a single `back_blaze` (or similar) variable. If you only stored one value on Render, delete that variable and add both rows above. Putting the application key secret in the wrong variable (e.g. only `B2_APPLICATION_KEY_ID`) will fail S3 auth.

**Private bucket:** files are not served from a public B2 URL. Uploads and downloads go through the Flask API (`save_upload` / `send_stored_file`), which uses your session after login. Do not set the bucket to Public unless you intentionally want objects reachable without the app.

## 3. CORS — not a key, and it does not go on Render

There is **no CORS key**. Do **not** add `CORS`, `CORS_KEY`, or anything like that under Render → Environment. That list is only for the two Backblaze **application key** values (see §2 and §4).

CORS is a **rule on the B2 bucket**, not a Render variable. Employees never see it.

The Backblaze bucket screen **“Share everything in this bucket with this one origin”** only allows the website to **read** files. It does **not** allow the browser to **upload**. That preset is why a drawing upload can still fail after you pick `https://www.usiscm.com`.

The website now writes the **upload** CORS rule itself on deploy (and again when it hands the browser a B2 upload URL). You do not need to use that Backblaze preset.

| What people confuse | Where it actually goes |
|---------------------|------------------------|
| B2 **keyID** | Render → **usis-cm** → **Environment** → `B2_APPLICATION_KEY_ID` |
| B2 **applicationKey** | Render → **usis-cm** → **Environment** → `B2_APPLICATION_KEY` |
| CORS | Written by the app onto bucket **USIS-construction-docs** (upload + download). Optional JSON below if you set it by hand. |

### Where to click in Backblaze

1. Sign in at [https://secure.backblaze.com](https://secure.backblaze.com) (the same account that owns the bucket).
2. Open **B2 Cloud Storage** → **Buckets**.
3. Open the bucket **USIS-construction-docs** (not App Keys).
4. Open **Bucket Settings** (or **Settings** → **CORS Rules** if you have the newer console).
5. Add **one** CORS rule. If the UI has a “share with exactly one origin” preset, use that and enter `https://www.usiscm.com`, API = **Both** (B2 Native and S3). Then add a second origin `https://usiscm.onrender.com` the same way, or paste the JSON below.

If the classic console has no CORS editor, leave the bucket open and run the one-time script in the next subsection (it writes the same rule using the keys already on your PC).

### JSON to paste on the bucket (not on Render)

```json
[
  {
    "corsRuleName": "usis-cm-browser-upload",
    "allowedOrigins": [
      "https://www.usiscm.com",
      "https://usiscm.onrender.com"
    ],
    "allowedOperations": ["b2_upload_file", "b2_upload_part"],
    "allowedHeaders": [
      "authorization",
      "content-type",
      "x-bz-file-name",
      "x-bz-content-sha1",
      "x-bz-info-*",
      "range",
      "x-amz-*"
    ],
    "exposeHeaders": ["x-bz-file-id", "x-bz-file-name", "x-bz-content-sha1"],
    "maxAgeSeconds": 3600
  },
  {
    "corsRuleName": "usis-cm-browser",
    "allowedOrigins": [
      "https://www.usiscm.com",
      "https://usiscm.onrender.com"
    ],
    "allowedOperations": [
      "b2_download_file_by_name",
      "b2_download_file_by_id",
      "s3_put",
      "s3_head",
      "s3_get"
    ],
    "allowedHeaders": [
      "authorization",
      "content-type",
      "x-bz-file-name",
      "x-bz-content-sha1",
      "x-bz-info-*",
      "range",
      "x-amz-*"
    ],
    "exposeHeaders": [
      "x-bz-file-id",
      "x-bz-file-name",
      "x-bz-content-sha1",
      "etag"
    ],
    "maxAgeSeconds": 3600
  }
]
```

List `authorization` by name. A lone `"*"` does **not** allow that header, so Firefox blocks the browser POST even when the origin looks right.

`allowedOrigins` must be the website origin only — scheme + host, **no path**. `https://www.usiscm.com/construction/project-detail.html` is wrong. `https://www.usiscm.com` is right.

### One-time script (same rule, no typing)

From `backend/` on a machine that already has `B2_APPLICATION_KEY_ID` and `B2_APPLICATION_KEY` in `.env` (or in the environment). This does **not** add a Render variable.

```bash
python scripts/apply_b2_cors.py --dry-run
python scripts/apply_b2_cors.py
```

Without this bucket rule, a browser fallback upload creates a placeholder row and the PDF never lands in B2.

## 3.1 Placeholders with no PDF

A drawing row with `file_pending` is only the catalog line. The PDF is missing when:

1. Render could not write to B2 **and** could not keep a copy on the Render disk.
2. Upload Desktop created `POST /api/v1/jobs/{id}/drawings` (metadata only) and did not POST the bytes to B2, then `POST /api/v1/drawings/{id}/ack-file`.

Website uploads no longer POST from the browser to B2. If the B2 write drops, the PDF is kept on the Render disk, served from the website, and copied to B2 when the upload pods answer again.

Re-upload the PDF from the website after deploy. Existing placeholder rows are reused for the same sheet/set/revision.

## 4. Render environment variables

In **Dashboard → usis-cm → Environment**, add:

| Variable | Example | Required |
|----------|---------|----------|
| `B2_APPLICATION_KEY_ID` | `003...` | Yes (for B2) |
| `B2_APPLICATION_KEY` | (secret) | Yes |
| `B2_BUCKET_NAME` | `USIS-construction-docs` | Yes |
| `B2_ENDPOINT` | From bucket **S3 Endpoint** (region-specific) | Yes |
| `B2_PREFIX` | `prod/usis-cm` | No |

**Remove** any unused custom name such as `back_blaze` — the app ignores it.

All four required vars must be set or the app falls back to local `instance/` paths.

After deploy, new uploads go to B2. Existing files on the Render disk are **not** migrated automatically; copy them with the B2 CLI or a one-off sync script if needed.

## 5. Optional: shrink or remove Render disk

[`render.yaml`](../render.yaml) still mounts `backend/instance` for fallback and local-style paths. Once B2 is verified in production, you can reduce reliance on the 1 GB disk or remove the `disk:` block after confirming no needed files remain only on disk.

## 6. Migrate from Render disk

If you already have files under `backend/instance/` on Render:

```bash
# Example with AWS CLI pointed at B2 (install awscli, configure profile with B2 key + endpoint)
aws s3 sync ./instance/drawing_uploads s3://USIS-construction-docs/prod/usis-cm/drawings/ \
  --endpoint-url https://s3.us-west-004.backblazeb2.com
```

Repeat per subdirectory (`spec_section_uploads`, `rfi_attachment_uploads`, `hr_*_document_uploads`), matching the key layout in the table above.

See also [render-deploy.md](render-deploy.md).

## 7. NAS / local mirror

B2 is the live store. The website never reads the NAS when B2 credentials are set. To keep a second copy on an office NAS (or a local disk), run [`backend/scripts/mirror_b2.py`](../backend/scripts/mirror_b2.py) **on a PC that can see the share**. New uploads may also write-through to `B2_MIRROR_ROOT` when that path is mounted. Render cannot mount your NAS, and its 1 GB disk cannot hold project drawings.

Set `B2_MIRROR_ROOT` in **local** `backend/.env` only — **do not add it on Render**. Do not point `DRAWING_UPLOAD_FOLDER` at the NAS on the website.

```bash
# from backend/
python scripts/mirror_b2.py
python scripts/mirror_b2.py --dry-run
python scripts/mirror_b2.py --root "\\\\Usisserver\\usiscm"
```

The script lists the bucket prefix (`B2_PREFIX`) and writes missing objects to `{B2_MIRROR_ROOT}/{key}` using the **same key as B2**. New drawings use a human-readable path:

`{prefix}/drawings/{project_number}/{discipline}/{set}/{original_filename}.pdf`

Example: `prod/usis-cm/drawings/24060/Architectural/Permit-Set/A7.31_…_Permit-Set.pdf`

Older drawings may still be stored as `{uuid}.pdf`; the app falls back to that name when serving. Files that already exist with the same size are skipped. Deletes on B2 are not removed from the NAS.

To copy a human-readable folder you already have (no B2 download):

```bash
python scripts/mirror_b2.py --skip-b2 --copy-source "C:\\Users\\CharlesDossett\\Downloads\\UCMMEB\\A-G-Revisions"
```

That lands at `{B2_MIRROR_ROOT}/UCMEB/A-G-Revisions`.
