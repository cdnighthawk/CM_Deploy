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

import time
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING

from flask import Response, current_app, send_file

if TYPE_CHECKING:
    from werkzeug.datastructures import FileStorage


class StorageError(Exception):
    """B2/local persist failed. ``status`` is the HTTP code callers should return."""

    def __init__(self, message: str, status: int = 500):
        super().__init__(message)
        self.message = message
        self.status = status


_PUT_ATTEMPTS = 4


class UploadCategory(StrEnum):
    DRAWINGS = "drawings"
    DOCUMENTS = "documents"
    SPEC_SECTIONS = "spec_sections"
    RFI_ATTACHMENTS = "rfi_attachments"
    HR_I9 = "hr_i9"
    HR_W4 = "hr_w4"
    HR_UNION = "hr_union"
    HR_HIRE_OFFER = "hr_hire_offer"
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
            retries={"max_attempts": 4, "mode": "standard"},
            connect_timeout=30,
            read_timeout=180,
        ),
    )


def _is_ssl_drop(exc: BaseException) -> bool:
    text = str(exc).lower()
    return (
        "eof occurred in violation" in text
        or "ssl validation failed" in text
        or type(exc).__name__ in {"SSLError", "SSLEOFError"}
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
        current_app.logger.warning("b2 head failed key=%s err=%s", key, exc)
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
        current_app.logger.warning("b2 get failed key=%s err=%s", key, exc)
        return None


def _put_bytes(key: str, payload: bytes, *, content_type: str | None) -> None:
    extra: dict = {}
    if content_type:
        extra["ContentType"] = content_type
    last: BaseException | None = None
    for attempt in range(_PUT_ATTEMPTS):
        try:
            _s3_client().put_object(
                Bucket=current_app.config["B2_BUCKET_NAME"],
                Key=key,
                Body=payload,
                **extra,
            )
            return
        except Exception as exc:
            last = exc
            if _is_storage_cap(exc):
                raise StorageError(
                    "Backblaze B2 storage cap exceeded. "
                    "In B2, open Caps & Alerts and raise or remove the daily storage cap.",
                    503,
                ) from exc
            if _is_ssl_drop(exc) and attempt + 1 < _PUT_ATTEMPTS:
                time.sleep(1.5 * (2**attempt))
                continue
            if _is_ssl_drop(exc):
                raise StorageError(
                    "Backblaze B2 closed the upload connection (SSL EOF). "
                    "Usually a full 10 GB free-tier cap or a dropped Render-to-B2 link.",
                    503,
                ) from exc
            raise
    if last is not None:
        raise last
