"""Map Textura TPM export payloads into USIS CM projects and pay applications."""
from __future__ import annotations

import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..api._pay_application_service import _recalculate_application
from ..models import PayApplication, PayApplicationLine, Project
from .textura_client import TexturaClient


@dataclass
class SyncCounts:
    loaded: int = 0
    skipped: int = 0
    errors: int = 0
    error_details: list[dict[str, str]] = field(default_factory=list)

    def merge(self, other: SyncCounts) -> None:
        self.loaded += other.loaded
        self.skipped += other.skipped
        self.errors += other.errors
        self.error_details.extend(other.error_details)


def sync_projects(
    session: Session,
    client: TexturaClient,
    *,
    auto_create: bool = False,
) -> SyncCounts:
    counts = SyncCounts()
    try:
        rows = client.get_owner_projects()
    except Exception as exc:
        counts.errors += 1
        counts.error_details.append({"entity": "project", "message": str(exc)})
        return counts

    for row in rows:
        try:
            _upsert_project_from_textura(session, row, auto_create=auto_create, counts=counts)
        except Exception as exc:
            counts.errors += 1
            tid = str(row.get("id") or "")
            counts.error_details.append({"entity": "project", "external_id": tid, "message": str(exc)})
    return counts


def sync_invoices(
    session: Session,
    client: TexturaClient,
    *,
    project_id: uuid.UUID | None = None,
) -> SyncCounts:
    counts = SyncCounts()
    try:
        rows = client.export_invoices()
    except Exception as exc:
        counts.errors += 1
        counts.error_details.append({"entity": "invoice", "message": str(exc)})
        return counts

    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        key = _invoice_group_key(row)
        if not key:
            counts.skipped += 1
            continue
        groups[key].append(row)

    for inv_key, line_rows in groups.items():
        try:
            _upsert_invoice_group(session, inv_key, line_rows, project_id_filter=project_id, counts=counts)
        except Exception as exc:
            counts.errors += 1
            counts.error_details.append(
                {"entity": "pay_application", "external_id": inv_key, "message": str(exc)}
            )
    return counts


def sync_all(
    session: Session,
    client: TexturaClient,
    *,
    auto_create_projects: bool = False,
    project_id: uuid.UUID | None = None,
) -> SyncCounts:
    total = SyncCounts()
    p = sync_projects(session, client, auto_create=auto_create_projects)
    total.merge(p)
    inv = sync_invoices(session, client, project_id=project_id)
    total.merge(inv)
    return total


def _upsert_project_from_textura(
    session: Session,
    row: Mapping[str, Any],
    *,
    auto_create: bool,
    counts: SyncCounts,
) -> None:
    tid = str(row.get("id") or "").strip()
    if not tid:
        counts.skipped += 1
        return

    proj = session.scalar(select(Project).where(Project.textura_project_id == tid))
    if proj is None:
        name = str(row.get("projectName") or "").strip()
        if name:
            proj = session.scalar(
                select(Project).where(
                    Project.deleted_at.is_(None),
                    func.lower(Project.name) == name.lower(),
                )
            )
    if proj is None and not auto_create:
        counts.skipped += 1
        return
    if proj is None:
        proj = Project(
            name=str(row.get("projectName") or f"Textura project {tid}"),
            status="active",
            project_type="commercial",
        )
        session.add(proj)
        session.flush()

    proj.textura_project_id = tid
    if row.get("projectName"):
        proj.name = str(row["projectName"]).strip()[:255]
    if row.get("address1"):
        proj.address_line1 = str(row["address1"]).strip()[:255] or None
    if row.get("address2"):
        proj.address_line2 = str(row["address2"]).strip()[:255] or None
    if row.get("city"):
        proj.city = str(row["city"]).strip()[:120] or None
    if row.get("state"):
        proj.state = str(row["state"]).strip()[:50] or None
    if row.get("zipCode"):
        proj.postal_code = str(row["zipCode"]).strip()[:20] or None
    if row.get("countryCode"):
        proj.country = str(row["countryCode"]).strip()[:2] or None
    counts.loaded += 1


def _resolve_project_for_invoice(
    session: Session,
    header: Mapping[str, Any],
    project_id_filter: uuid.UUID | None,
) -> Project | None:
    main_job = str(header.get("MainJobNumber") or "").strip()
    project_name = str(header.get("ProjectName") or "").strip()

    proj: Project | None = None
    if main_job:
        proj = session.scalar(
            select(Project).where(
                Project.deleted_at.is_(None),
                func.lower(Project.number) == main_job.lower(),
            )
        )
    if proj is None and main_job:
        proj = session.scalar(
            select(Project).where(Project.deleted_at.is_(None), Project.textura_project_id == main_job)
        )
    if proj is None and project_name:
        proj = session.scalar(
            select(Project).where(
                Project.deleted_at.is_(None),
                func.lower(Project.name) == project_name.lower(),
            )
        )
    if proj is None:
        return None
    if project_id_filter is not None and proj.id != project_id_filter:
        return None
    return proj


def _upsert_invoice_group(
    session: Session,
    inv_key: str,
    line_rows: list[dict[str, Any]],
    *,
    project_id_filter: uuid.UUID | None,
    counts: SyncCounts,
) -> None:
    header = line_rows[0]
    proj = _resolve_project_for_invoice(session, header, project_id_filter)
    if proj is None:
        counts.skipped += 1
        return

    pa = session.scalar(
        select(PayApplication).where(
            PayApplication.project_id == proj.id,
            PayApplication.textura_invoice_id == inv_key,
        )
    )
    if pa is None:
        pa = session.scalar(
            select(PayApplication).where(
                PayApplication.project_id == proj.id,
                PayApplication.textura_invoice_id.is_(None),
                PayApplication.status == "draft",
                PayApplication.application_number == _draw_application_number(header),
            )
        )

    if pa is not None and pa.status == "draft" and not pa.textura_invoice_id:
        pass
    elif pa is not None and pa.status == "draft" and pa.textura_invoice_id != inv_key:
        counts.skipped += 1
        return
    elif pa is None:
        app_no = _draw_application_number(header)
        max_no = session.scalar(
            select(func.max(PayApplication.application_number)).where(
                PayApplication.project_id == proj.id
            )
        )
        if max_no is not None and app_no <= int(max_no):
            app_no = int(max_no) + 1
        pa = PayApplication(
            project_id=proj.id,
            application_number=app_no,
            status="draft",
            net_change_by_change_orders=Decimal("0"),
        )
        session.add(pa)
        session.flush()
    elif pa.status == "draft":
        pass
    else:
        counts.skipped += 1
        return

    pa.textura_invoice_id = inv_key
    pa.period_to = _parse_textura_date(header.get("InvoiceDate"))
    pa.status = _map_invoice_status(header.get("InvoiceStatus"))
    pa.current_payment_due = _dec_optional(header.get("InvoiceGrossAmount"))
    pa.retainage_total = _dec_optional(header.get("InvoiceRetentionHeld"))
    if header.get("ApprovalDate"):
        pa.architect_certified_at = _parse_textura_datetime(header.get("ApprovalDate"))
    if pa.current_payment_due is not None:
        pa.architect_certified_amount = pa.current_payment_due

    for li in list(pa.lines):
        session.delete(li)
    session.flush()

    for idx, row in enumerate(line_rows):
        li = PayApplicationLine(
            pay_application_id=pa.id,
            sort_order=idx,
            phase_code=_str_or_none(row.get("ItemPhaseCode"), 40),
            description=_str_or_none(row.get("ItemPhaseCodeDescription"), 500) or "",
            scheduled_value=_dec(row.get("Quantity")) or _dec(row.get("ItemGrossAmount")),
            work_this_period=_dec(row.get("ItemGrossAmount")),
            materials_stored=_dec(row.get("ItemMaterialStored")),
            retention_to_date=_dec(row.get("ItemRetentionHeld")),
        )
        session.add(li)

    _recalculate_application(pa)
    counts.loaded += 1


def _invoice_group_key(row: Mapping[str, Any]) -> str:
    main = str(row.get("MainJobNumber") or row.get("ProjectName") or "").strip()
    draw = str(row.get("DrawNumber") or "").strip()
    inv = str(row.get("ModifiedInvoiceNumber") or row.get("SubInvoiceNumber") or "").strip()
    rev = str(row.get("RevisionNumber") or "").strip()
    sub = str(row.get("SubcontractNumber") or "").strip()
    if not main or not draw:
        return ""
    parts = [main, draw, inv or "0", rev or "0"]
    if sub:
        parts.append(sub)
    return "|".join(parts)


def _draw_application_number(row: Mapping[str, Any]) -> int:
    raw = row.get("DrawNumber") or row.get("ModifiedInvoiceNumber") or row.get("SubInvoiceNumber")
    try:
        return max(1, int(str(raw).strip()))
    except (TypeError, ValueError):
        return 1


def _map_invoice_status(raw: Any) -> str:
    s = str(raw or "").strip().lower()
    if s in ("1", "approved", "certified"):
        return "certified"
    if s in ("paid", "2"):
        return "paid"
    if s in ("submitted", "pending"):
        return "submitted"
    return "draft"


def _dec(v: Any) -> Decimal:
    if v is None or v == "" or str(v).lower() == "null":
        return Decimal("0")
    try:
        return Decimal(str(v).replace(",", "")).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        return Decimal("0")


def _dec_optional(v: Any) -> Decimal | None:
    if v is None or v == "" or str(v).lower() == "null":
        return None
    d = _dec(v)
    return d


def _str_or_none(v: Any, max_len: int) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    if not s:
        return None
    return s[:max_len]


def _parse_textura_date(raw: Any) -> date | None:
    if raw is None:
        return None
    s = str(raw).strip()
    if not s or s.lower() == "null":
        return None
    if len(s) == 8 and s.isdigit():
        try:
            return date(int(s[4:8]), int(s[0:2]), int(s[2:4]))
        except ValueError:
            return None
    try:
        return date.fromisoformat(s[:10])
    except ValueError:
        return None


def _parse_textura_datetime(raw: Any) -> datetime | None:
    d = _parse_textura_date(raw)
    if d is None:
        return None
    return datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
