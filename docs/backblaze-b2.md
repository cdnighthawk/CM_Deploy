# Backblaze B2 object storage (USIS CM uploads)

Production on Render can store **project PDFs** (drawings, spec sections, RFI attachments) and **HR hire-wizard photos** (I-9, W-4, union documents) in [Backblaze B2](https://www.backblaze.com/b2/cloud-storage.html) instead of the Render persistent disk. The Flask app uses B2’s **S3-compatible API** via `boto3` when all required environment variables are set.

Local development without B2 vars continues to use `backend/instance/` (same as before).

## What is stored in B2

| Category | API examples | Object key pattern |
|----------|--------------|-------------------|
| Drawings | `POST /api/v1/projects/<id>/drawings` | `{prefix}/drawings/<uuid>.pdf` |
| Spec sections | `POST .../spec_sections/<id>/file` | `{prefix}/spec_sections/<uuid>.pdf` |
| RFI attachments | `POST /api/v1/rfis/<id>/attachments/upload` | `{prefix}/rfi_attachments/<uuid><ext>` |
| HR I-9 photos | `POST /api/v1/hr/me/i9-section1/documents` | `{prefix}/hr_i9/<uuid><ext>` |
| HR W-4 photos | `POST /api/v1/hr/me/w4/documents` | `{prefix}/hr_w4/<uuid><ext>` |
| HR union photos | `POST /api/v1/hr/me/hire-wizard/union-documents` | `{prefix}/hr_union/<uuid><ext>` |

`{prefix}` is optional (`B2_PREFIX`, e.g. `prod/usis-cm`). The Gulp static UI is **not** stored in B2.

## 1. Create a B2 bucket

1. Sign in to [Backblaze](https://www.backblaze.com/) → **B2 Cloud Storage** → **Buckets** → **Create a Bucket**.
2. **Bucket name**: e.g. `usis-cm-uploads` (globally unique in your account).
3. **Files in bucket are**: **Private** (the app serves downloads through Flask with session auth).
4. Note the **S3 endpoint** for your region (B2 bucket → **Bucket Settings** → **S3 Endpoint**), e.g. `https://s3.us-west-004.backblazeb2.com`.

## 2. Application key

1. **App Keys** → **Add a New Application Key**.
2. Name: e.g. `usis-cm-render`.
3. **Allow access to Bucket(s)**: restrict to the upload bucket.
4. Capabilities: at least **readFiles**, **writeFiles**, **deleteFiles**, **listBuckets** (or use a template that includes object read/write/delete).
5. Save **keyID** → `B2_APPLICATION_KEY_ID` and **applicationKey** → `B2_APPLICATION_KEY` (shown once).

## 3. CORS (browser uploads)

Uploads go through the Flask API (`multipart/form-data` to same origin on Render), not direct browser → B2 PUT. **CORS on the bucket is usually not required** for the current UI.

If you later add direct-to-B2 uploads from the browser, configure CORS on the bucket to allow your Render origin, e.g.:

```json
[
  {
    "corsRuleName": "usis-cm-render",
    "allowedOrigins": ["https://your-service.onrender.com"],
    "allowedOperations": ["b2_upload_file", "s3_put", "s3_post"],
    "allowedHeaders": ["*"],
    "maxAgeSeconds": 3600
  }
]
```

## 4. Render environment variables

In **Dashboard → usis-cm → Environment**, add:

| Variable | Example | Required |
|----------|---------|----------|
| `B2_APPLICATION_KEY_ID` | `003...` | Yes (for B2) |
| `B2_APPLICATION_KEY` | (secret) | Yes |
| `B2_BUCKET_NAME` | `usis-cm-uploads` | Yes |
| `B2_ENDPOINT` | `https://s3.us-west-004.backblazeb2.com` | Yes |
| `B2_PREFIX` | `prod/usis-cm` | No |

All four required vars must be set or the app falls back to local `instance/` paths.

After deploy, new uploads go to B2. Existing files on the Render disk are **not** migrated automatically; copy them with the B2 CLI or a one-off sync script if needed.

## 5. Optional: shrink or remove Render disk

[`render.yaml`](../render.yaml) still mounts `backend/instance` for fallback and local-style paths. Once B2 is verified in production, you can reduce reliance on the 1 GB disk or remove the `disk:` block after confirming no needed files remain only on disk.

## 6. Migrate from Render disk

If you already have files under `backend/instance/` on Render:

```bash
# Example with AWS CLI pointed at B2 (install awscli, configure profile with B2 key + endpoint)
aws s3 sync ./instance/drawing_uploads s3://usis-cm-uploads/prod/usis-cm/drawings/ \
  --endpoint-url https://s3.us-west-004.backblazeb2.com
```

Repeat per subdirectory (`spec_section_uploads`, `rfi_attachment_uploads`, `hr_*_document_uploads`), matching the key layout in the table above.

See also [render-deploy.md](render-deploy.md).
