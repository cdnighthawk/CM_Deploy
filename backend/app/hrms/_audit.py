"""Append-only HRMS audit trail."""
from __future__ import annotations

import uuid
from typing import Any, Optional

from flask import has_request_context, request

from ..extensions import db
from ..models.hrms_core import HrmsAuditLog


def write_hrms_audit(
    *,
    actor_user_id: Optional[uuid.UUID],
    action: str,
    entity_type: str,
    entity_id: Optional[uuid.UUID] = None,
    details: Optional[dict[str, Any]] = None,
) -> None:
    ip: str | None = None
    if has_request_context() and request.remote_addr:
        ip = str(request.remote_addr)[:64]
    row = HrmsAuditLog(
        actor_user_id=actor_user_id,
        action=action[:80],
        entity_type=entity_type[:80],
        entity_id=entity_id,
        details=details or {},
        ip_address=ip,
    )
    db.session.add(row)
