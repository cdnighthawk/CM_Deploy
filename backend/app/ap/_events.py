"""Invoice audit events."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from ..extensions import db
from ..models.vendor_invoice import VendorInvoice, VendorInvoiceEvent


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def record_event(
    invoice: VendorInvoice,
    actor_user_id: uuid.UUID | None,
    action: str,
    details: dict[str, Any] | None = None,
) -> None:
    db.session.add(
        VendorInvoiceEvent(
            invoice_id=invoice.id,
            actor_user_id=actor_user_id,
            action=action,
            details=details or {},
            created_at=utc_now(),
        )
    )
