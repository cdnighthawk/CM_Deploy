"""Match a newly ingested vendor invoice against bills already in the tracker."""
from __future__ import annotations

import hashlib
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID

from sqlalchemy import select

from ..extensions import db
from ..models.vendor_invoice import VendorInvoice
from ._parse import extract_invoice_fields, extract_pdf_text, merge_invoice_fields, normalize_invoice_number

_DUP_THRESHOLD = 70
_SEEN_CAP = 50
_REMINDER_CAP = 20
_VOID = "void"


def file_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _is_deleted(invoice: VendorInvoice) -> bool:
    meta = invoice.parse_meta if isinstance(invoice.parse_meta, dict) else {}
    return bool(meta.get("deleted"))


def _as_decimal(raw: Any) -> Decimal | None:
    if raw is None or raw == "":
        return None
    if isinstance(raw, Decimal):
        return raw
    try:
        return Decimal(str(raw).replace(",", "").replace("$", "")).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError, TypeError):
        return None


def parse_attachments(files: list[dict[str, Any]]) -> dict[str, Any]:
    """Pull invoice fields from PDF text and attachment filenames."""
    merged: dict[str, Any] = {}
    for item in files:
        name = str(item.get("name") or "")
        data = item.get("data") or b""
        if name:
            merged = merge_invoice_fields(merged, extract_invoice_fields(name, None, include_dates=False))
        if isinstance(data, (bytes, bytearray)) and data[:4] == b"%PDF":
            text = extract_pdf_text(bytes(data))
            if text:
                merged = merge_invoice_fields(
                    merged, extract_invoice_fields(None, text, include_dates=True)
                )
    return merged


def message_already_recorded(mid: str) -> bool:
    if not mid:
        return False
    row = db.session.scalar(
        select(VendorInvoice.id)
        .where(VendorInvoice.parse_meta.contains({"seen_message_ids": [mid]}))
        .limit(1)
    )
    return row is not None


def _hash_hits(digests: set[str]) -> list[VendorInvoice]:
    hits: list[VendorInvoice] = []
    seen: set[UUID] = set()
    for digest in digests:
        if len(digest) < 16:
            continue
        rows = db.session.scalars(
            select(VendorInvoice).where(VendorInvoice.parse_meta.contains({"attachment_sha256": [digest]}))
        ).all()
        for row in rows:
            if row.id in seen or row.status == _VOID or _is_deleted(row):
                continue
            seen.add(row.id)
            hits.append(row)
    return hits


def _number_candidates(invoice_number: str) -> list[VendorInvoice]:
    needle = normalize_invoice_number(invoice_number)
    if len(needle) < 2:
        return []
    rows = db.session.scalars(
        select(VendorInvoice).where(
            VendorInvoice.status != _VOID,
            VendorInvoice.invoice_number.is_not(None),
        ).limit(2000)
    ).all()
    return [
        row
        for row in rows
        if not _is_deleted(row) and normalize_invoice_number(row.invoice_number) == needle
    ]


def score_duplicate(
    candidate: VendorInvoice,
    *,
    invoice_number: str | None,
    vendor_id: UUID | None,
    from_email: str | None,
    amount: Decimal | None,
    hashes: set[str],
) -> tuple[int, list[str]]:
    score = 0
    reasons: list[str] = []
    meta = candidate.parse_meta if isinstance(candidate.parse_meta, dict) else {}
    stored = {str(h) for h in (meta.get("attachment_sha256") or []) if h}
    if hashes and stored and hashes & stored:
        score += 100
        reasons.append("same_pdf")
    needle = normalize_invoice_number(invoice_number)
    cand_num = normalize_invoice_number(candidate.invoice_number)
    if needle and cand_num and needle == cand_num:
        score += 40
        reasons.append("invoice_number")
        if vendor_id is not None and candidate.vendor_company_id == vendor_id:
            score += 40
            reasons.append("vendor")
        elif from_email and candidate.from_email and from_email.strip().lower() == candidate.from_email.strip().lower():
            score += 35
            reasons.append("sender")
        cand_amt = _as_decimal(candidate.amount)
        if amount is not None and cand_amt is not None and amount == cand_amt:
            score += 25
            reasons.append("amount")
    return score, reasons


def find_duplicate_invoice(
    *,
    invoice_number: str | None,
    vendor_id: UUID | None,
    from_email: str | None,
    amount: Decimal | None,
    hashes: list[str],
) -> tuple[VendorInvoice | None, list[str]]:
    digest_set = {h for h in hashes if h}
    candidates: dict[UUID, VendorInvoice] = {}
    for row in _hash_hits(digest_set):
        candidates[row.id] = row
    if invoice_number:
        for row in _number_candidates(invoice_number):
            candidates[row.id] = row
    if not candidates:
        return None, []
    ranked: list[tuple[int, list[str], VendorInvoice]] = []
    for row in candidates.values():
        score, reasons = score_duplicate(
            row,
            invoice_number=invoice_number,
            vendor_id=vendor_id,
            from_email=from_email,
            amount=amount,
            hashes=digest_set,
        )
        if score >= _DUP_THRESHOLD:
            ranked.append((score, reasons, row))
    if not ranked:
        return None, []
    ranked.sort(key=lambda t: (-t[0], t[2].received_at or datetime.min.replace(tzinfo=timezone.utc)))
    _score, reasons, winner = ranked[0]
    return winner, reasons


def remember_attachment_hashes(invoice: VendorInvoice, hashes: list[str]) -> None:
    meta = dict(invoice.parse_meta or {})
    stored = [str(h) for h in (meta.get("attachment_sha256") or []) if h]
    for digest in hashes:
        if digest and digest not in stored:
            stored.append(digest)
    meta["attachment_sha256"] = stored
    invoice.parse_meta = meta


def record_duplicate_email(
    invoice: VendorInvoice,
    *,
    graph_message_id: str,
    subject: str | None,
    from_email: str | None,
    received_at: datetime | None,
    match_reasons: list[str],
    parsed: dict[str, Any] | None = None,
) -> None:
    meta = dict(invoice.parse_meta or {})
    seen = [str(x) for x in (meta.get("seen_message_ids") or []) if x]
    if graph_message_id and graph_message_id not in seen:
        seen.append(graph_message_id)
    meta["seen_message_ids"] = seen[-_SEEN_CAP:]
    reminders = list(meta.get("reminders") or [])
    stamp = (received_at or datetime.now(timezone.utc)).isoformat()
    reminders.append(
        {
            "graph_message_id": graph_message_id,
            "subject": subject,
            "from_email": from_email,
            "received_at": stamp,
            "match": match_reasons,
        }
    )
    meta["reminders"] = reminders[-_REMINDER_CAP:]
    meta["reminder_count"] = int(meta.get("reminder_count") or 0) + 1
    meta["last_reminder_at"] = stamp
    if parsed:
        if not invoice.invoice_number and parsed.get("invoice_number"):
            invoice.invoice_number = str(parsed["invoice_number"])[:80]
        if invoice.amount is None and parsed.get("amount"):
            invoice.amount = _as_decimal(parsed.get("amount"))
        if invoice.po_number is None and parsed.get("po_number"):
            invoice.po_number = str(parsed["po_number"])[:80]
        if invoice.invoice_date is None and parsed.get("invoice_date"):
            try:
                invoice.invoice_date = date.fromisoformat(str(parsed["invoice_date"])[:10])
            except ValueError:
                pass
        if invoice.due_date is None and parsed.get("due_date"):
            try:
                invoice.due_date = date.fromisoformat(str(parsed["due_date"])[:10])
            except ValueError:
                pass
    invoice.parse_meta = meta
