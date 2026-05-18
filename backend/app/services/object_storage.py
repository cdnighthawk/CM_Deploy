"""Binary storage for project PDFs and HR document photos.

Uses the local filesystem under Flask ``instance/`` (or per-category env folders)
when Backblaze B2 is not configured. When ``B2_APPLICATION_KEY_ID``, ``B2_APPLICATION_KEY``,
``B2_BUCKET_NAME``, and ``B2_ENDPOINT`` are all set, objects are stored in B2 via the
S3-compatible API (``boto3``).
"""

from __future__ import annotations

import io
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING

from flask import Response, current_app, send_file

if TYPE_CHECKING:
    from werkzeug.datastructures import FileStorage


class UploadCategory(StrEnum):
    DRAWINGS = "drawings"
    SPEC_SECTIONS = "spec_sections"
    RFI_ATTACHMENTS = "rfi_attachments"
    HR_I9 = "hr_i9"
    HR_W4 = "hr_w4"
    HR_UNION = "hr_union"


_CATEGORY_CONFIG_KEY: dict[UploadCategory, str] = {
    UploadCategory.DRAWINGS: "DRAWING_UPLOAD_FOLDER",
    UploadCategory.SPEC_SECTIONS: "SPEC_SECTION_UPLOAD_FOLDER",
    UploadCategory.RFI_ATTACHMENTS: "RFI_ATTACHMENT_UPLOAD_FOLDER",
    UploadCategory.HR_I9: "HR_I9_DOCUMENT_UPLOAD_FOLDER",
    UploadCategory.HR_W4: "HR_W4_DOCUMENT_UPLOAD_FOLDER",
    UploadCategory.HR_UNION: "HR_UNION_DOCUMENT_UPLOAD_FOLDER",
}

_CATEGORY_INSTANCE_SUBDIR: dict[UploadCategory, str] = {
    UploadCategory.DRAWINGS: "drawing_uploads",
    UploadCategory.SPEC_SECTIONS: "spec_section_uploads",
    UploadCategory.RFI_ATTACHMENTS: "rfi_attachment_uploads",
    UploadCategory.HR_I9: "hr_i9_document_uploads",
    UploadCategory.HR_W4: "hr_w4_document_uploads",
    UploadCategory.HR_UNION: "hr_union_document_uploads",
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


def stored_exists(category: UploadCategory, object_name: str) -> bool:
    if b2_enabled():
        return _head_object(object_key(category, object_name)) is not None
    return local_path(category, object_name).is_file()


def stored_size(category: UploadCategory, object_name: str) -> int | None:
    if b2_enabled():
        meta = _head_object(object_key(category, object_name))
        if meta is None:
            return None
        return int(meta.get("ContentLength") or 0)
    path = local_path(category, object_name)
    try:
        return path.stat().st_size if path.is_file() else None
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


def save_upload(category: UploadCategory, object_name: str, file) -> int:
    """Persist a multipart upload or in-memory PDF bytes; return byte size."""
    if b2_enabled():
        payload = _read_binary_payload(file)
        content_type = None
        if hasattr(file, "mimetype"):
            content_type = (getattr(file, "mimetype", None) or "").strip() or None
        _put_bytes(object_key(category, object_name), payload, content_type=content_type)
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
        return send_file(
            io.BytesIO(data),
            mimetype=mimetype,
            as_attachment=False,
            download_name=download_name,
        )
    path = local_path(category, object_name)
    if not path.is_file():
        return None
    return send_file(
        path,
        mimetype=mimetype,
        as_attachment=False,
        download_name=download_name,
    )


def _s3_client():
    import boto3

    endpoint = (current_app.config.get("B2_ENDPOINT") or "").strip()
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=current_app.config["B2_APPLICATION_KEY_ID"],
        aws_secret_access_key=current_app.config["B2_APPLICATION_KEY"],
        region_name="us-east-1",
    )


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
        raise


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
        raise


def _put_bytes(key: str, payload: bytes, *, content_type: str | None) -> None:
    extra: dict = {}
    if content_type:
        extra["ContentType"] = content_type
    _s3_client().put_object(
        Bucket=current_app.config["B2_BUCKET_NAME"],
        Key=key,
        Body=payload,
        **extra,
    )
