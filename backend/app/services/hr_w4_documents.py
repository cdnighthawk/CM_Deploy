"""W-4 supporting document photo storage (hire wizard)."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from ..models import HrHireW4DocumentFile
from .hr_hire_upload import HR_HIRE_DOC_EXT
from .object_storage import UploadCategory, local_path, local_root

W4_DOC_SLOTS = frozenset({"supporting"})
W4_DOC_EXT = HR_HIRE_DOC_EXT
W4_DOC_MAX_PER_SLOT = 3
W4_DOC_MAX_BYTES = 10_485_760  # 10 MB


def w4_document_upload_dir() -> Path:
    return local_root(UploadCategory.HR_W4)


def disk_path(file_id: uuid.UUID, ext: str) -> Path:
    return local_path(UploadCategory.HR_W4, f"{file_id}{ext}")


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
