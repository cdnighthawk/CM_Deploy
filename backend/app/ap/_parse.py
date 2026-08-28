"""Heuristic extraction of invoice fields from email subject/body."""
from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Any

_INVOICE_NO_RE = re.compile(
    r"(?:invoice|inv)(?:\s*(?:number|no|#|num))?\s*[:#-]?\s*([A-Z0-9][-A-Z0-9/]{1,30})",
    re.IGNORECASE,
)
_PO_RE = re.compile(
    r"(?:p\.?\s*o\.?|purchase\s+order)(?:\s*(?:number|no|#))?\s*[:#-]?\s*([A-Z0-9][-A-Z0-9/]{1,30})",
    re.IGNORECASE,
)
_JOB_RE = re.compile(
    r"(?:job|project|proj)(?:\s*(?:number|no|#))?\s*[:#-]?\s*([A-Z0-9][-A-Z0-9]{1,24})",
    re.IGNORECASE,
)
_AMOUNT_RE = re.compile(
    r"(?:\$|usd\s*)\s*([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]{2})|[0-9]+\.[0-9]{2})",
    re.IGNORECASE,
)
_TOTAL_AMOUNT_RE = re.compile(
    r"(?:total|amount\s+due|balance\s+due|invoice\s+total)\s*[:#-]?\s*\$?\s*"
    r"([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]{2})|[0-9]+\.[0-9]{2})",
    re.IGNORECASE,
)


def _plain_text(html_or_text: str) -> str:
    raw = html_or_text or ""
    raw = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", raw)
    raw = re.sub(r"(?i)<br\s*/?>", "\n", raw)
    raw = re.sub(r"(?i)</p>", "\n", raw)
    raw = re.sub(r"(?s)<[^>]+>", " ", raw)
    raw = re.sub(r"&nbsp;", " ", raw)
    raw = re.sub(r"&amp;", "&", raw)
    raw = re.sub(r"[ \t]+", " ", raw)
    return raw.strip()


def _parse_money(raw: str) -> Decimal | None:
    try:
        val = Decimal(raw.replace(",", "").replace("$", "").strip())
    except (InvalidOperation, ValueError):
        return None
    if val <= 0:
        return None
    return val.quantize(Decimal("0.01"))


def extract_invoice_fields(subject: str | None, body: str | None) -> dict[str, Any]:
    """Pull invoice number, amount, PO, and job tokens from email text."""
    text = "\n".join(p for p in ((subject or "").strip(), _plain_text(body or "")) if p)
    invoice_number = None
    m = _INVOICE_NO_RE.search(text)
    if m:
        invoice_number = m.group(1).strip(" .-")

    po_number = None
    m = _PO_RE.search(text)
    if m:
        po_number = m.group(1).strip(" .-")

    job_tokens: list[str] = []
    for m in _JOB_RE.finditer(text):
        token = m.group(1).strip(" .-")
        if token and token.lower() not in {t.lower() for t in job_tokens}:
            job_tokens.append(token)

    amount = None
    m = _TOTAL_AMOUNT_RE.search(text)
    if m:
        amount = _parse_money(m.group(1))
    if amount is None:
        amounts = [_parse_money(x.group(1)) for x in _AMOUNT_RE.finditer(text)]
        amounts = [a for a in amounts if a is not None]
        if amounts:
            amount = max(amounts)

    return {
        "invoice_number": invoice_number,
        "po_number": po_number,
        "job_tokens": job_tokens,
        "amount": str(amount) if amount is not None else None,
        "text_sample": text[:800],
    }
