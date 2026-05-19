"""Delete drawing revisions or entire sheet series (metadata + stored PDF)."""
from __future__ import annotations

import uuid

from sqlalchemy import select, update

from ..extensions import db
from ..models import Drawing, TakeoffLineItem
from .object_storage import UploadCategory, delete_stored


def _clear_takeoff_refs(drawing_ids: list[uuid.UUID]) -> None:
    if not drawing_ids:
        return
    db.session.execute(
        update(TakeoffLineItem)
        .where(TakeoffLineItem.drawing_id.in_(drawing_ids))
        .values(drawing_id=None)
    )


def _delete_pdf(drawing_id: uuid.UUID) -> None:
    delete_stored(UploadCategory.DRAWINGS, f"{drawing_id}.pdf")


def delete_drawing_revision(drawing_id: uuid.UUID) -> bool:
    """Remove one revision row and its PDF. Returns False if not found."""
    row = db.session.get(Drawing, drawing_id)
    if row is None:
        return False
    _delete_pdf(row.id)
    _clear_takeoff_refs([row.id])
    db.session.delete(row)
    return True


def delete_drawing_series(
    series_id: uuid.UUID,
    *,
    project_id: uuid.UUID | None = None,
) -> int:
    """Remove every revision in a sheet series. Returns count deleted."""
    q = select(Drawing).where(Drawing.drawing_series_id == series_id)
    if project_id is not None:
        q = q.where(Drawing.project_id == project_id)
    rows = list(db.session.scalars(q).all())
    if not rows:
        return 0
    ids = [r.id for r in rows]
    for rid in ids:
        _delete_pdf(rid)
    _clear_takeoff_refs(ids)
    for row in rows:
        db.session.delete(row)
    return len(rows)
