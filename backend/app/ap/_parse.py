"""Heuristic extraction of invoice fields from email subject/body and PDF text."""
from __future__ import annotations

import html as html_lib
import io
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

_INVOICE_NO_RE = re.compile(
    r"(?:invoice|inv)\b(?:\s*(?:number|no|#|num))?\s*[:#-]?\s*([A-Z0-9][-A-Z0-9/]{1,30})",
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
_INVOICE_DATE_RE = re.compile(
    r"(?:invoice\s*date|date\s*of\s*invoice|inv(?:oice)?\s*date)\s*[:#-]?\s*"
    r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}[-/]\d{1,2}[-/]\d{1,2}|"
    r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|"
    r"Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
    r"\s+\d{1,2},?\s+\d{4})",
    re.IGNORECASE,
)
_DUE_DATE_RE = re.compile(
    r"(?:due\s*date|payment\s*due|pay\s*by)\s*[:#-]?\s*"
    r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}[-/]\d{1,2}[-/]\d{1,2}|"
    r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|"
    r"Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
    r"\s+\d{1,2},?\s+\d{4})",
    re.IGNORECASE,
)
_FILE_INV_RE = re.compile(
    r"(?:invoice|inv|bill)[-_ ]+#?([A-Z0-9][-A-Z0-9]{1,30})",
    re.IGNORECASE,
)
_EMAIL = r"[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}"
_FW_PREFIX_RE = re.compile(r"(?i)^(?:(?:fwd?|fw)\s*:\s*)+")
_FORWARDED_BLOCK_RE = re.compile(r"(?i)forwarded message")
_FW_FROM_ANGLE_RE = re.compile(
    rf"(?is)\bFrom:\s*(?P<name>[^<\n\[]{{0,80}}?)\s*(?:<|&lt;)\s*(?P<email>{_EMAIL})\s*(?:>|&gt;)"
)
_FW_FROM_MAILTO_RE = re.compile(
    rf"(?is)\bFrom:\s*(?P<name>[^\[\n<]{{0,80}}?)\s*\[mailto:\s*(?P<email>{_EMAIL})\s*\]"
)
_FW_FROM_BARE_RE = re.compile(rf"(?im)^From:\s*(?P<email>{_EMAIL})\s*$")
_SUBJECT_COMPANY_RE = re.compile(r"(?i)\bfrom\s+(.+)$")
_ORG_SUFFIX_RE = re.compile(r"\b(inc|llc|ltd|corp|co|incorporated|company|llp)\b", re.IGNORECASE)


def _plain_text(html_or_text: str) -> str:
    raw = html_or_text or ""
    raw = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", raw)
    raw = re.sub(r"(?i)<br\s*/?>", "\n", raw)
    raw = re.sub(r"(?i)</p>", "\n", raw)
    # Real HTML tags only — do not strip ``<vendor@example.com>`` from forwarded headers.
    raw = re.sub(r"(?i)</?[a-zA-Z][a-zA-Z0-9:]*(?:\s[^>]*)?>", " ", raw)
    raw = html_lib.unescape(raw)
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


def strip_forward_prefix(subject: str | None) -> str:
    return _FW_PREFIX_RE.sub("", (subject or "").strip()).strip()


def looks_like_forward(subject: str | None, body: str | None = None) -> bool:
    if _FW_PREFIX_RE.match((subject or "").strip()):
        return True
    text = _plain_text(body or "")
    if _FORWARDED_BLOCK_RE.search(text):
        return True
    return bool(
        _FW_FROM_ANGLE_RE.search(text)
        or _FW_FROM_MAILTO_RE.search(text)
        or _FW_FROM_BARE_RE.search(text)
    )


def normalize_org_name(name: str | None) -> str:
    s = re.sub(r"[^\w\s]", " ", name or "", flags=re.UNICODE)
    s = _ORG_SUFFIX_RE.sub(" ", s)
    return " ".join(s.lower().split())


def extract_forwarded_origin(
    subject: str | None,
    body: str | None,
    *,
    skip_domains: set[str] | None = None,
) -> dict[str, Any]:
    """Original vendor From:/company on an Outlook or Gmail forward."""
    text = _plain_text(body or "")
    blob = f"{subject or ''}\n{text}"
    skip = {d.strip().lower() for d in (skip_domains or set()) if d and d.strip()}
    email = None
    name = None
    matches: list[re.Match[str]] = []
    matches.extend(_FW_FROM_ANGLE_RE.finditer(blob))
    matches.extend(_FW_FROM_MAILTO_RE.finditer(blob))
    matches.extend(_FW_FROM_BARE_RE.finditer(blob))
    matches.sort(key=lambda m: m.start())
    for m in matches:
        cand = (m.group("email") or "").strip().lower()
        if not cand or "@" not in cand:
            continue
        domain = cand.rsplit("@", 1)[-1]
        if domain in skip:
            continue
        email = cand
        raw_name = m.groupdict().get("name")
        name = (raw_name or "").strip() or None
        if name:
            name = html_lib.unescape(name)
        break
    company = None
    rest = strip_forward_prefix(subject)
    m = _SUBJECT_COMPANY_RE.search(rest)
    if m:
        company = m.group(1).strip().rstrip(",") or None
    return {
        "email": email,
        "name": name,
        "company": company,
        "is_forward": bool(
            _FW_PREFIX_RE.match((subject or "").strip())
            or _FORWARDED_BLOCK_RE.search(text)
            or email
        ),
    }


def normalize_invoice_number(raw: str | None) -> str:
    s = re.sub(r"[\s_]+", "", (raw or "").strip().upper())
    s = re.sub(r"^(INVOICE|INV|BILL)[-#]*", "", s)
    return s.strip("-#/")


def _parse_date_token(raw: str) -> str | None:
    token = (raw or "").strip()
    if not token:
        return None
    token = token.replace(".", "/")
    for fmt in (
        "%m/%d/%Y",
        "%m/%d/%y",
        "%d/%m/%Y",
        "%d/%m/%y",
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%B %d, %Y",
        "%B %d %Y",
        "%b %d, %Y",
        "%b %d %Y",
    ):
        try:
            return datetime.strptime(token, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def extract_pdf_text(data: bytes, *, max_pages: int = 8) -> str:
    """Best-effort text from an invoice PDF (native text; not OCR)."""
    if not data or data[:4] != b"%PDF":
        return ""
    try:
        import fitz

        doc = fitz.open(stream=data, filetype="pdf")
        try:
            n = min(max_pages, doc.page_count)
            parts = [doc[i].get_text() or "" for i in range(n)]
        finally:
            doc.close()
        text = "\n".join(parts).strip()
        if len(text) >= 12:
            return text
    except Exception:
        pass
    try:
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(data))
        parts = [(page.extract_text() or "") for page in reader.pages[:max_pages]]
        return "\n".join(parts).strip()
    except Exception:
        return ""


def merge_invoice_fields(email_fields: dict[str, Any], extra: dict[str, Any]) -> dict[str, Any]:
    """Overlay PDF (or filename) fields onto email-parsed fields. Extra wins when present."""
    out = dict(email_fields or {})
    for key in ("invoice_number", "po_number", "amount", "invoice_date", "due_date"):
        val = extra.get(key)
        if val:
            out[key] = val
    jobs = list(out.get("job_tokens") or [])
    seen = {t.lower() for t in jobs}
    for token in extra.get("job_tokens") or []:
        if token and token.lower() not in seen:
            jobs.append(token)
            seen.add(token.lower())
    out["job_tokens"] = jobs
    sample = extra.get("text_sample")
    if sample:
        out["pdf_sample"] = str(sample)[:800]
    return out


def extract_invoice_fields(subject: str | None, body: str | None, *, include_dates: bool = False) -> dict[str, Any]:
    """Pull invoice number, amount, PO, and job tokens from email or PDF text."""
    text = "\n".join(p for p in ((subject or "").strip(), _plain_text(body or "")) if p)
    invoice_number = None
    m = _INVOICE_NO_RE.search(text)
    if m:
        invoice_number = m.group(1).strip(" .-")
    if not invoice_number:
        m = _FILE_INV_RE.search(text)
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

    invoice_date = None
    due_date = None
    if include_dates:
        m = _INVOICE_DATE_RE.search(text)
        if m:
            invoice_date = _parse_date_token(m.group(1))
        m = _DUE_DATE_RE.search(text)
        if m:
            due_date = _parse_date_token(m.group(1))

    origin = extract_forwarded_origin(subject, body)
    return {
        "invoice_number": invoice_number,
        "po_number": po_number,
        "job_tokens": job_tokens,
        "amount": str(amount) if amount is not None else None,
        "invoice_date": invoice_date,
        "due_date": due_date,
        "text_sample": text[:800],
        "forwarded": origin,
    }
