"""I-9 supporting document photo storage (hire wizard)."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from ..models import HrHireI9DocumentFile
from .object_storage import UploadCategory, local_path, local_root

I9_DOC_SLOTS = frozenset({"list_a", "list_b", "list_c"})
I9_DOC_EXT = frozenset({".jpg", ".jpeg", ".png", ".webp", ".gif", ".heic"})
I9_DOC_MAX_PER_SLOT = 3
I9_DOC_MAX_BYTES = 10_485_760  # 10 MB


def i9_document_upload_dir() -> Path:
    return local_root(UploadCategory.HR_I9)


def disk_path(file_id: uuid.UUID, ext: str) -> Path:
    return local_path(UploadCategory.HR_I9, f"{file_id}{ext}")


def serialize_i9_document(row: HrHireI9DocumentFile) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "slot": row.slot,
        "sort_order": row.sort_order,
        "original_filename": row.original_filename,
        "mime_type": row.mime_type,
        "file_size_bytes": row.file_size_bytes,
        "file_url": f"/api/v1/hr/me/i9-section1/documents/{row.id}/file",
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }
