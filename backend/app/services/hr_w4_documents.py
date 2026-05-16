"""W-4 supporting document photo storage (hire wizard)."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from flask import current_app

from ..models import HrHireW4DocumentFile

W4_DOC_SLOTS = frozenset({"supporting"})
W4_DOC_EXT = frozenset({".jpg", ".jpeg", ".png", ".webp", ".gif", ".heic"})
W4_DOC_MAX_PER_SLOT = 3
W4_DOC_MAX_BYTES = 10_485_760  # 10 MB


def w4_document_upload_dir() -> Path:
    cfg = (current_app.config.get("HR_W4_DOCUMENT_UPLOAD_FOLDER") or "").strip()
    if cfg:
        return Path(cfg).expanduser().resolve()
    return Path(current_app.instance_path).resolve() / "hr_w4_document_uploads"


def disk_path(file_id: uuid.UUID, ext: str) -> Path:
    return w4_document_upload_dir() / f"{file_id}{ext}"


def serialize_w4_document(row: HrHireW4DocumentFile) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "slot": row.slot,
        "sort_order": row.sort_order,
        "original_filename": row.original_filename,
        "mime_type": row.mime_type,
        "file_size_bytes": row.file_size_bytes,
        "file_url": f"/api/v1/hr/me/w4/documents/{row.id}/file",
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }
