"""Union card / dispatch photo storage (hire wizard)."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from ..models import HrHireUnionDocumentFile
from .object_storage import UploadCategory, local_path, local_root

UNION_DOC_KINDS = frozenset({"union_card", "union_dispatch"})
UNION_DOC_EXT = frozenset({".jpg", ".jpeg", ".png", ".webp", ".gif", ".heic"})
UNION_DOC_MAX_PER_KIND = 3
UNION_DOC_MAX_BYTES = 10_485_760  # 10 MB


def union_document_upload_dir() -> Path:
    return local_root(UploadCategory.HR_UNION)


def disk_path(file_id: uuid.UUID, ext: str) -> Path:
    return local_path(UploadCategory.HR_UNION, f"{file_id}{ext}")


def serialize_union_document(row: HrHireUnionDocumentFile) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "document_kind": row.document_kind,
        "sort_order": row.sort_order,
        "original_filename": row.original_filename,
        "mime_type": row.mime_type,
        "file_size_bytes": row.file_size_bytes,
        "file_url": f"/api/v1/hr/me/hire-wizard/union-documents/{row.id}/file",
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }
