"""Binary storage for project PDFs and HR document photos.

When ``B2_APPLICATION_KEY_ID``, ``B2_APPLICATION_KEY``, ``B2_BUCKET_NAME``, and
``B2_ENDPOINT`` are all set, the website and API read and write Backblaze B2
only (S3-compatible ``boto3``). Local ``instance/`` and ``B2_MIRROR_ROOT`` (NAS)
are not used as a read fallback in that mode.

Without those four vars, objects live under Flask ``instance/`` (or per-category
env folders). ``B2_MIRROR_ROOT`` is then an optional local/NAS read path for
office PCs that do not have B2 credentials.
"""

from __future__ import annotations

import base64
import hashlib
import json
import threading
import time
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from flask import Response, current_app, send_file

if TYPE_CHECKING:
    from werkzeug.datastructures import FileStorage


class StorageError(Exception):
    """B2/local persist failed. ``status`` is the HTTP code callers should return."""

    def __init__(self, message: str, status: int = 500):
        super().__init__(message)
        self.message = message
        self.status = status


# Keep S3 attempts inside gunicorn --timeout (see render.yaml). SSL drops usually
# fail fast; a hung put must not run past the worker timeout or the client sees 502.
_PUT_ATTEMPTS = 3
_S3_CONNECT_TIMEOUT = 15
_S3_READ_TIMEOUT = 40
_NATIVE_TRANSFER_TIMEOUT = 120
_AUTH_TTL_SEC = 50 * 60
_auth_cache: dict = {"at": 0.0, "key_id": "", "data": None}
_cors_applied = {"ok": False, "at": 0.0}
_CORS_TTL_SEC = 6 * 60 * 60
_DEFAULT_BROWSER_ORIGINS = (
    "https://www.usiscm.com",
    "https://usiscm.onrender.com",
)


class UploadCategory(StrEnum):
    DRAWINGS = "drawings"
    DOCUMENTS = "documents"
    SPEC_SECTIONS = "spec_sections"
    RFI_ATTACHMENTS = "rfi_attachments"
    HR_I9 = "hr_i9"
    HR_W4 = "hr_w4"
    HR_UNION = "hr_union"
    HR_HIRE_OFFER = "hr_hire_offer"
    HR_HIRE = "hr_hire"
    HR_EXPENSE_RECEIPT = "hr_expense_receipt"
    AP_INVOICE = "ap_invoice"
    FIELD_PHOTOS = "field_photos"


_CATEGORY_CONFIG_KEY: dict[UploadCategory, str] = {
    UploadCategory.DRAWINGS: "DRAWING_UPLOAD_FOLDER",
    UploadCategory.DOCUMENTS: "DOCUMENT_UPLOAD_FOLDER",
    UploadCategory.SPEC_SECTIONS: "SPEC_SECTION_UPLOAD_FOLDER",
    UploadCategory.RFI_ATTACHMENTS: "RFI_ATTACHMENT_UPLOAD_FOLDER",
    UploadCategory.HR_I9: "HR_I9_DOCUMENT_UPLOAD_FOLDER",
    UploadCategory.HR_W4: "HR_W4_DOCUMENT_UPLOAD_FOLDER",
    UploadCategory.HR_UNION: "HR_UNION_DOCUMENT_UPLOAD_FOLDER",
    UploadCategory.HR_HIRE_OFFER: "HR_HIRE_OFFER_UPLOAD_FOLDER",
    UploadCategory.HR_HIRE: "HR_HIRE_UPLOAD_FOLDER",
    UploadCategory.HR_EXPENSE_RECEIPT: "HR_EXPENSE_RECEIPT_UPLOAD_FOLDER",
    UploadCategory.AP_INVOICE: "AP_INVOICE_UPLOAD_FOLDER",
    UploadCategory.FIELD_PHOTOS: "FIELD_PHOTO_UPLOAD_FOLDER",
}

_CATEGORY_INSTANCE_SUBDIR: dict[UploadCategory, str] = {
    UploadCategory.DRAWINGS: "drawing_uploads",
    UploadCategory.DOCUMENTS: "document_uploads",
    UploadCategory.SPEC_SECTIONS: "spec_section_uploads",
    UploadCategory.RFI_ATTACHMENTS: "rfi_attachment_uploads",
    UploadCategory.HR_I9: "hr_i9_document_uploads",
    UploadCategory.HR_W4: "hr_w4_document_uploads",
    UploadCategory.HR_UNION: "hr_union_document_uploads",
    UploadCategory.HR_HIRE_OFFER: "hr_hire_offer_uploads",
    UploadCategory.HR_HIRE: "hr_hire_uploads",
    UploadCategory.HR_EXPENSE_RECEIPT: "hr_expense_receipt_uploads",
    UploadCategory.AP_INVOICE: "ap_invoice_uploads",
    UploadCategory.FIELD_PHOTOS: "field_photo_uploads",
}


def b2_enabled() -> bool:
    cfg = current_app.config
    return bool(
        (cfg.get("B2_APPLICATION_KEY_ID") or "").strip()
        and (cfg.get("B2_APPLICATION_KEY") or "").strip()
        and (cfg.get("B2_BUCKET_NAME") or "").strip()
        and (cfg.get("B2_ENDPOINT") or "").strip()
    )


def local_root(category: UploadCategory) -> Path:
    """Directory for on-disk storage of a category (ignored when B2 is active)."""
    key = _CATEGORY_CONFIG_KEY[category]
    raw = (current_app.config.get(key) or "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    sub = _CATEGORY_INSTANCE_SUBDIR[category]
    return Path(current_app.instance_path).resolve() / sub


def local_path(category: UploadCategory, object_name: str) -> Path:
    return local_root(category) / object_name


def object_key(category: UploadCategory, object_name: str) -> str:
    """Full B2/S3 object key (category segment + optional env prefix)."""
    prefix = (current_app.config.get("B2_PREFIX") or "").strip().strip("/")
    parts = [p for p in (prefix, category.value, object_name) if p]
    return "/".join(parts)


def _mirror_file(category: UploadCategory, object_name: str) -> Path | None:
    """NAS/local mirror of the B2 key when ``B2_MIRROR_ROOT`` is set."""
    root = (current_app.config.get("B2_MIRROR_ROOT") or "").strip()
    if not root:
        return None
    parts = [p for p in object_key(category, object_name).replace("\\", "/").split("/") if p and p not in (".", "..")]
    path = Path(root).joinpath(*parts)
    try:
        return path if path.is_file() else None
    except OSError:
        return None


def stored_exists(category: UploadCategory, object_name: str) -> bool:
    if b2_enabled():
        return _head_object(object_key(category, object_name)) is not None
    if local_path(category, object_name).is_file():
        return True
    return _mirror_file(category, object_name) is not None


def read_first_stored(category: UploadCategory, object_names: list[str]) -> tuple[str, bytes] | None:
    """Return ``(object_name, bytes)`` for the first name that exists (old or new key)."""
    for name in object_names:
        n = (name or "").strip()
        if not n:
            continue
        data = read_stored_bytes(category, n)
        if data:
            return n, data
    return None


def stored_size(category: UploadCategory, object_name: str) -> int | None:
    if b2_enabled():
        meta = _head_object(object_key(category, object_name))
        if meta is None:
            return None
        return int(meta.get("ContentLength") or 0)
    path = local_path(category, object_name)
    try:
        if path.is_file():
            return path.stat().st_size
    except OSError:
        pass
    mirrored = _mirror_file(category, object_name)
    if mirrored is None:
        return None
    try:
        return mirrored.stat().st_size
    except OSError:
        return None


def _read_binary_payload(file) -> bytes:
    """Read bytes from Werkzeug ``FileStorage``, ``BytesIO``, or raw ``bytes``."""
    if isinstance(file, (bytes, bytearray)):
        return bytes(file)
    payload = file.read()
    if not payload and hasattr(file, "stream"):
        payload = file.stream.read()
    if hasattr(file, "seek"):
        try:
            file.seek(0)
        except (OSError, ValueError, TypeError):
            pass
    return payload or b""


def _mirror_to_nas(key: str, payload: bytes) -> None:
    """Write the same B2 key onto B2_MIRROR_ROOT when that path is mounted locally."""
    root = (current_app.config.get("B2_MIRROR_ROOT") or "").strip()
    if not root or not payload:
        return
    parts = [p for p in key.replace("\\", "/").split("/") if p and p not in (".", "..")]
    dest = Path(root).joinpath(*parts)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(payload)


def save_upload(category: UploadCategory, object_name: str, file) -> int:
    """Persist a multipart upload or in-memory PDF bytes; return byte size."""
    if b2_enabled():
        payload = _read_binary_payload(file)
        content_type = None
        if hasattr(file, "mimetype"):
            content_type = (getattr(file, "mimetype", None) or "").strip() or None
        key = object_key(category, object_name)
        try:
            _put_bytes(key, payload, content_type=content_type)
        except StorageError:
            raise
        except Exception as exc:
            raise StorageError(f"could not save file: {exc}", 500) from exc
        try:
            _mirror_to_nas(key, payload)
        except OSError:
            # NAS is optional; B2 write already succeeded.
            pass
        return len(payload)
    path = local_path(category, object_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    if hasattr(file, "save") and callable(getattr(file, "save", None)):
        file.save(str(path))
        return path.stat().st_size
    payload = _read_binary_payload(file)
    path.write_bytes(payload)
    return len(payload)


def delete_stored(category: UploadCategory, object_name: str) -> None:
    if b2_enabled():
        try:
            _s3_client().delete_object(
                Bucket=current_app.config["B2_BUCKET_NAME"],
                Key=object_key(category, object_name),
            )
        except Exception:
            pass
        return
    try:
        local_path(category, object_name).unlink(missing_ok=True)
    except OSError:
        pass


def read_stored_bytes(category: UploadCategory, object_name: str) -> bytes | None:
    """Load a stored object into memory, or ``None`` when missing."""
    if b2_enabled():
        return _get_bytes(object_key(category, object_name))
    path = local_path(category, object_name)
    if path.is_file():
        return path.read_bytes()
    mirrored = _mirror_file(category, object_name)
    if mirrored is None:
        return None
    return mirrored.read_bytes()


def prefixed_key(rel: str) -> str:
    """B2 key for a path that is not under a category prefix (RFP snapshots)."""
    prefix = (current_app.config.get("B2_PREFIX") or "").strip().strip("/")
    rel = (rel or "").strip().strip("/").replace("\\", "/")
    parts = [p for p in rel.split("/") if p and p not in (".", "..")]
    if prefix:
        return "/".join([prefix, *parts])
    return "/".join(parts)


def local_raw_path(rel: str) -> Path:
    """On-disk path for a raw (non-category) object when B2 is off."""
    root = (current_app.config.get("DOCUMENT_ROOT") or "").strip()
    if root:
        base = Path(root).expanduser().resolve()
    else:
        base = Path(current_app.instance_path).resolve() / "rfp_snaps"
    parts = [p for p in prefixed_key(rel).replace("\\", "/").split("/") if p and p not in (".", "..")]
    return base.joinpath(*parts)


def put_raw_bytes(rel: str, payload: bytes, *, content_type: str | None = None) -> str:
    """Write bytes to a raw key. Returns the relative key (no bucket prefix)."""
    rel = (rel or "").strip().strip("/")
    if b2_enabled():
        key = prefixed_key(rel)
        _put_bytes(key, payload, content_type=content_type)
        try:
            _mirror_to_nas(key, payload)
        except OSError:
            pass
        return rel
    path = local_raw_path(rel)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return rel


def read_raw_bytes(rel: str) -> bytes | None:
    if b2_enabled():
        return _get_bytes(prefixed_key(rel))
    path = local_raw_path(rel)
    if path.is_file():
        return path.read_bytes()
    return None


def copy_b2_object(src_key: str, dest_key: str) -> bool:
    """Server-side copy inside the private bucket. Returns False if src is missing."""
    if not b2_enabled():
        return False
    bucket = current_app.config["B2_BUCKET_NAME"]
    try:
        _s3_client().copy_object(
            Bucket=bucket,
            Key=dest_key,
            CopySource={"Bucket": bucket, "Key": src_key},
        )
        return True
    except Exception as exc:
        if _is_not_found(exc):
            return False
        current_app.logger.warning("b2 copy failed src=%s dest=%s err=%s", src_key, dest_key, exc)
        return False


def presigned_put_url(
    category: UploadCategory,
    object_name: str,
    *,
    ttl: int = 3600,
    content_type: str | None = None,
) -> str | None:
    """Short-lived PUT URL so a client can write the object without Render proxying bytes."""
    if not b2_enabled():
        return None
    params: dict = {
        "Bucket": current_app.config["B2_BUCKET_NAME"],
        "Key": object_key(category, object_name),
    }
    if content_type:
        params["ContentType"] = content_type
    try:
        return _s3_client().generate_presigned_url(
            "put_object",
            Params=params,
            ExpiresIn=max(30, int(ttl or 3600)),
            HttpMethod="PUT",
        )
    except Exception as exc:
        current_app.logger.warning("b2 presign put failed key=%s err=%s", object_name, exc)
        return None


def native_upload_session(category: UploadCategory, object_name: str) -> dict | None:
    """One-shot native B2 upload URL (b2_get_upload_url) for a client POST of the file bytes.

    Retry a few times: Render's S3 gateway is the flaky door, but ``b2_get_upload_url``
    can still 5xx under load. The desktop needs this URL more than Render needs to
    PUT the bytes itself.
    """
    if not b2_enabled():
        return None
    ensure_browser_cors()
    key = object_key(category, object_name)
    last: BaseException | None = None
    for attempt in range(3):
        try:
            info = _b2_get_upload_url()
            return {
                "mode": "b2_native",
                "url": info["uploadUrl"],
                "authorization": info["authorizationToken"],
                "file_name": key,
                "sha1_header": "X-Bz-Content-Sha1",
            }
        except Exception as exc:
            last = exc
            if attempt + 1 < 3:
                time.sleep(0.4 * (2**attempt))
    current_app.logger.warning("b2 native upload url failed key=%s err=%s", key, last)
    return None


def browser_cors_origins() -> list[str]:
    """Website origins that may POST a one-shot B2 upload from the browser."""
    out: list[str] = []
    seen: set[str] = set()

    def add(raw: str | None) -> None:
        s = (raw or "").strip().rstrip("/")
        if not s.startswith("http://") and not s.startswith("https://"):
            return
        key = s.lower()
        if key in seen:
            return
        seen.add(key)
        out.append(s)

    add(current_app.config.get("USIS_APP_PUBLIC_URL"))
    for origin in current_app.config.get("CORS_ORIGINS") or ():
        add(str(origin))
    for origin in _DEFAULT_BROWSER_ORIGINS:
        add(origin)
    return out


def browser_cors_rules(origins: list[str] | None = None) -> list[dict]:
    """Native B2 CORS that allows browser upload, not only download/share."""
    allowed = [o for o in (origins or browser_cors_origins()) if o]
    return [
        {
            "corsRuleName": "usis-cm-browser",
            "allowedOrigins": allowed,
            "allowedOperations": [
                "b2_upload_file",
                "b2_download_file_by_name",
                "b2_download_file_by_id",
                "s3_put",
                "s3_head",
                "s3_get",
            ],
            "allowedHeaders": ["*"],
            "exposeHeaders": [
                "x-bz-file-id",
                "x-bz-file-name",
                "x-bz-content-sha1",
                "etag",
            ],
            "maxAgeSeconds": 3600,
        }
    ]


def ensure_browser_cors() -> bool:
    """Write upload-capable CORS onto the bucket. The B2 'share with this origin' UI is download-only."""
    if not b2_enabled():
        return False
    now = time.time()
    if _cors_applied.get("ok") and now - float(_cors_applied.get("at") or 0) < _CORS_TTL_SEC:
        return True
    origins = browser_cors_origins()
    if not origins:
        return False
    try:
        auth = _b2_authorize()
        bucket_id = _b2_bucket_id(auth)
        body = json.dumps(
            {
                "accountId": auth.get("accountId"),
                "bucketId": bucket_id,
                "corsRules": browser_cors_rules(origins),
            }
        ).encode()
        req = Request(
            f"{auth['apiUrl']}/b2api/v2/b2_update_bucket",
            data=body,
            headers={
                "Authorization": auth["authorizationToken"],
                "Content-Type": "application/json",
            },
            method="POST",
        )
        _b2_http_json(req, _S3_CONNECT_TIMEOUT)
        _cors_applied["ok"] = True
        _cors_applied["at"] = now
        current_app.logger.info("b2 browser upload CORS applied origins=%s", ",".join(origins))
        return True
    except Exception as exc:
        current_app.logger.warning("b2 browser upload CORS apply failed err=%s", exc)
        return False


def start_b2_cors_ensure(app) -> None:
    """Apply upload CORS once after boot so the first drawing upload is not blocked."""
    import os
    import sys

    if "pytest" in sys.modules or os.environ.get("PYTEST_CURRENT_TEST"):
        return

    def _run() -> None:
        time.sleep(2)
        try:
            with app.app_context():
                ensure_browser_cors()
        except Exception:
            app.logger.warning("b2 cors ensure thread failed", exc_info=True)

    threading.Thread(target=_run, name="b2-cors-ensure", daemon=True).start()


def presigned_get_url(
    rel: str,
    *,
    ttl: int,
    filename: str,
    content_type: str | None = None,
) -> str | None:
    """Short-lived GET URL for a private B2 object, or None when B2 is off."""
    if not b2_enabled():
        return None
    safe = (filename or "download.bin").replace('"', "")
    params: dict = {
        "Bucket": current_app.config["B2_BUCKET_NAME"],
        "Key": prefixed_key(rel),
        "ResponseContentDisposition": f'attachment; filename="{safe}"',
    }
    if content_type:
        params["ResponseContentType"] = content_type
    try:
        return _s3_client().generate_presigned_url(
            "get_object",
            Params=params,
            ExpiresIn=max(30, int(ttl or 600)),
        )
    except Exception as exc:
        current_app.logger.warning("b2 presign failed key=%s err=%s", rel, exc)
        return None


def send_stored_file(
    category: UploadCategory,
    object_name: str,
    *,
    mimetype: str,
    download_name: str,
) -> Response | None:
    """Stream a stored object, or ``None`` when missing."""
    if b2_enabled():
        data = _get_bytes(object_key(category, object_name))
        if data is None:
            return None
        # Explicit body + Content-Length avoids proxy/browser mismatches with BytesIO send_file.
        safe_name = download_name.replace('"', "")
        return Response(
            data,
            mimetype=mimetype,
            headers={
                "Content-Length": str(len(data)),
                "Content-Disposition": f'inline; filename="{safe_name}"',
            },
        )
    path = local_path(category, object_name)
    if not path.is_file():
        path = _mirror_file(category, object_name)
    if path is None or not path.is_file():
        return None
    return send_file(
        path,
        mimetype=mimetype,
        as_attachment=False,
        download_name=download_name,
    )


def _s3_client():
    import boto3
    from botocore.config import Config

    endpoint = (current_app.config.get("B2_ENDPOINT") or "").strip()
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=current_app.config["B2_APPLICATION_KEY_ID"],
        aws_secret_access_key=current_app.config["B2_APPLICATION_KEY"],
        region_name="us-east-1",
        config=Config(
            signature_version="s3v4",
            s3={"addressing_style": "path"},
            retries={"max_attempts": 2, "mode": "standard"},
            connect_timeout=_S3_CONNECT_TIMEOUT,
            read_timeout=_S3_READ_TIMEOUT,
        ),
    )


def _is_s3_compat_drop(exc: BaseException) -> bool:
    """B2's S3 gateway dropped the socket. Native B2 (api.backblazeb2.com) may still work.

    Covers SSL EOF, boto ``ConnectionClosedError``, and connect/read timeouts.
    Those are different doors than native B2.
    """
    name = type(exc).__name__
    if name in {
        "SSLError",
        "SSLEOFError",
        "ConnectionClosedError",
        "ReadTimeoutError",
        "ConnectTimeoutError",
        "EndpointConnectionError",
        "ConnectionError",
    }:
        return True
    text = str(exc).lower()
    return (
        "eof occurred in violation" in text
        or "ssl validation failed" in text
        or "connection was closed before we received a valid response" in text
        or "read timeout" in text
        or "connect timeout" in text
        or "timed out" in text
    )


def _is_storage_cap(exc: BaseException) -> bool:
    from botocore.exceptions import ClientError

    if not isinstance(exc, ClientError):
        return False
    err = exc.response.get("Error") or {}
    blob = f"{err.get('Code', '')} {err.get('Message', '')}".lower()
    return "storage_cap" in blob or "cap exceeded" in blob or "cap_exceeded" in blob


def _is_not_found(exc: BaseException) -> bool:
    from botocore.exceptions import ClientError

    if not isinstance(exc, ClientError):
        return False
    code = exc.response.get("Error", {}).get("Code", "")
    return code in ("404", "NoSuchKey", "NotFound")


def _head_object(key: str) -> dict | None:
    try:
        return _s3_client().head_object(
            Bucket=current_app.config["B2_BUCKET_NAME"],
            Key=key,
        )
    except Exception as exc:
        if _is_not_found(exc):
            return None
        current_app.logger.warning("b2 s3 head failed key=%s err=%s", key, exc)
    try:
        return _head_native_b2(key)
    except Exception as exc:
        current_app.logger.warning("b2 native head failed key=%s err=%s", key, exc)
        return None


def _get_bytes(key: str) -> bytes | None:
    try:
        resp = _s3_client().get_object(
            Bucket=current_app.config["B2_BUCKET_NAME"],
            Key=key,
        )
        return resp["Body"].read()
    except Exception as exc:
        if _is_not_found(exc):
            return None
        current_app.logger.warning("b2 s3 get failed key=%s err=%s", key, exc)
    try:
        return _get_native_b2(key)
    except Exception as exc:
        current_app.logger.warning("b2 native get failed key=%s err=%s", key, exc)
        return None


def _put_bytes(key: str, payload: bytes, *, content_type: str | None) -> None:
    """Write via native B2 first. Render's S3-compatible gateway often drops the socket."""
    extra: dict = {}
    if content_type:
        extra["ContentType"] = content_type
    native_err: BaseException | None = None
    try:
        _put_native_b2(key, payload, content_type=content_type)
        return
    except StorageError as exc:
        if "storage cap" in (exc.message or "").lower() or "cap exceeded" in (exc.message or "").lower():
            raise
        native_err = exc
        current_app.logger.warning("b2 native put failed; trying S3 key=%s err=%s", key, exc)
    except Exception as exc:
        native_err = exc
        current_app.logger.warning("b2 native put failed; trying S3 key=%s err=%s", key, exc)

    last: BaseException | None = None
    for _attempt in range(_PUT_ATTEMPTS):
        try:
            _s3_client().put_object(
                Bucket=current_app.config["B2_BUCKET_NAME"],
                Key=key,
                Body=payload,
                **extra,
            )
            current_app.logger.warning("b2 s3 put succeeded after native failure key=%s", key)
            return
        except Exception as exc:
            last = exc
            if _is_storage_cap(exc):
                raise StorageError(
                    "Backblaze B2 storage cap exceeded. "
                    "In B2, open Caps & Alerts and raise or remove the daily storage cap.",
                    503,
                ) from exc
            if _is_s3_compat_drop(exc):
                break
            break
    raise StorageError(
        "Could not write the file to Backblaze B2. "
        "Render could not finish the upload via native B2 or S3.",
        503,
    ) from (native_err or last)


def _b2_http_json(req: Request, timeout: int) -> dict:
    try:
        with urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")[:240]
        raise StorageError(f"B2 HTTP {exc.code}: {raw}", 503) from exc


def _b2_authorize() -> dict:
    key_id = (current_app.config.get("B2_APPLICATION_KEY_ID") or "").strip()
    secret = (current_app.config.get("B2_APPLICATION_KEY") or "").strip()
    now = time.time()
    cached = _auth_cache.get("data")
    if (
        cached
        and _auth_cache.get("key_id") == key_id
        and now - float(_auth_cache.get("at") or 0) < _AUTH_TTL_SEC
    ):
        return cached
    token = base64.b64encode(f"{key_id}:{secret}".encode()).decode()
    req = Request(
        "https://api.backblazeb2.com/b2api/v2/b2_authorize_account",
        headers={"Authorization": f"Basic {token}"},
        method="GET",
    )
    data = _b2_http_json(req, _S3_CONNECT_TIMEOUT)
    _auth_cache["at"] = now
    _auth_cache["key_id"] = key_id
    _auth_cache["data"] = data
    return data


def _b2_bucket_id(auth: dict) -> str:
    allowed = auth.get("allowed") or {}
    bucket_id = (allowed.get("bucketId") or "").strip()
    if bucket_id:
        return bucket_id
    want = (current_app.config.get("B2_BUCKET_NAME") or "").strip()
    body = json.dumps({"accountId": auth.get("accountId")}).encode()
    req = Request(
        f"{auth['apiUrl']}/b2api/v2/b2_list_buckets",
        data=body,
        headers={
            "Authorization": auth["authorizationToken"],
            "Content-Type": "application/json",
        },
        method="POST",
    )
    payload = _b2_http_json(req, _S3_CONNECT_TIMEOUT)
    for bucket in payload.get("buckets") or []:
        if bucket.get("bucketName") == want:
            return str(bucket.get("bucketId") or "")
    raise StorageError("Backblaze B2 bucket was not found for this application key.", 500)


def _b2_get_upload_url() -> dict:
    auth = _b2_authorize()
    bucket_id = _b2_bucket_id(auth)
    body = json.dumps({"bucketId": bucket_id}).encode()
    req = Request(
        f"{auth['apiUrl']}/b2api/v2/b2_get_upload_url",
        data=body,
        headers={
            "Authorization": auth["authorizationToken"],
            "Content-Type": "application/json",
        },
        method="POST",
    )
    return _b2_http_json(req, _S3_CONNECT_TIMEOUT)


def _b2_file_url(auth: dict, key: str) -> str:
    bucket = quote((current_app.config.get("B2_BUCKET_NAME") or "").strip(), safe="")
    encoded = quote(key, safe="/")
    return f"{auth['downloadUrl']}/file/{bucket}/{encoded}"


def _head_native_b2(key: str) -> dict | None:
    """Size/exists via native list (avoids the S3 gateway)."""
    auth = _b2_authorize()
    bucket_id = _b2_bucket_id(auth)
    body = json.dumps(
        {
            "bucketId": bucket_id,
            "prefix": key,
            "maxFileCount": 10,
        }
    ).encode()
    req = Request(
        f"{auth['apiUrl']}/b2api/v2/b2_list_file_names",
        data=body,
        headers={
            "Authorization": auth["authorizationToken"],
            "Content-Type": "application/json",
        },
        method="POST",
    )
    payload = _b2_http_json(req, _S3_CONNECT_TIMEOUT)
    for row in payload.get("files") or []:
        if row.get("fileName") == key and row.get("action") in (None, "upload"):
            return {"ContentLength": int(row.get("contentLength") or 0)}
    return None


def _get_native_b2(key: str) -> bytes | None:
    auth = _b2_authorize()
    req = Request(
        _b2_file_url(auth, key),
        headers={"Authorization": auth["authorizationToken"]},
        method="GET",
    )
    try:
        with urlopen(req, timeout=_NATIVE_TRANSFER_TIMEOUT) as resp:
            return resp.read()
    except HTTPError as exc:
        if exc.code == 404:
            return None
        raw = exc.read().decode("utf-8", "replace")[:240]
        raise StorageError(f"B2 HTTP {exc.code}: {raw}", 503) from exc
    except URLError as exc:
        raise StorageError("Backblaze B2 native download connection failed.", 503) from exc


def _put_native_b2(key: str, payload: bytes, *, content_type: str | None) -> None:
    info = _b2_get_upload_url()
    sha1 = hashlib.sha1(payload).hexdigest()
    headers = {
        "Authorization": info["authorizationToken"],
        "X-Bz-File-Name": quote(key, safe="/"),
        "Content-Type": (content_type or "application/octet-stream"),
        "X-Bz-Content-Sha1": sha1,
    }
    req = Request(info["uploadUrl"], data=payload, headers=headers, method="POST")
    try:
        with urlopen(req, timeout=_NATIVE_TRANSFER_TIMEOUT) as resp:
            resp.read()
    except HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")[:240]
        blob = raw.lower()
        if "storage_cap" in blob or "cap exceeded" in blob or "cap_exceeded" in blob:
            raise StorageError(
                "Backblaze B2 storage cap exceeded. "
                "In B2, open Caps & Alerts and raise or remove the daily storage cap.",
                503,
            ) from exc
        raise StorageError(f"Backblaze B2 native upload failed ({exc.code}).", 503) from exc
    except URLError as exc:
        raise StorageError("Backblaze B2 native upload connection failed.", 503) from exc
