"""Estimating spec-package pipeline: detect CSI, extract BOD, match vendors, draft RFPs."""
from __future__ import annotations

import json
import re
import secrets
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Mapping

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from ..csi_catalog import title_for_code
from ..csi_spec import CSI_CODE_RE, digits_from_csi, format_csi_display
from ..extensions import db
from ..models import (
    AuditLog,
    Company,
    Document,
    Drawing,
    Estimate,
    EstimateBidScope,
    EstimateBidScopeItem,
    EstimateSpecMention,
    EstimateSpecScan,
    EstimateSpecSection,
    EstimateSpecVendor,
    MaterialPrice,
    Project,
    Rfp,
    RfpLineItem,
    SpecSection,
    SpecTradeMap,
    TakeoffLineItem,
)
from ..models.rfp import RfpVendorQuote
from ..services.spec_book_import import extract_csi_sections_from_pdf, parse_codes_from_text
from ._perms import CurrentUser
from ._rfi_service import ApiError, _parse_uuid

SCAN_STATUSES = (
    "detecting",
    "review_sections",
    "extracting",
    "review_products",
    "vendors_ready",
    "rfp_drafted",
    "cancelled",
)
MENTION_ROLES = frozenset(
    {"basis_of_design", "listed_alternate", "or_equal", "prohibited", "schedule_item"}
)
DRAFT_SCAN_STATUSES = frozenset(
    {"detecting", "review_sections", "extracting", "review_products", "vendors_ready"}
)

TRADE_SEEDS: tuple[tuple[str, str, bool, int], ...] = (
    ("06 20", "Finish carpentry / trim", True, 10),
    ("06 41", "Finish carpentry / trim", True, 11),
    ("06 46", "Finish carpentry / trim", True, 12),
    ("09 21", "Gypsum board / metal framing", True, 20),
    ("09 22", "Gypsum board / metal framing", True, 21),
    ("09 29", "Gypsum board / metal framing", True, 22),
    ("09 51", "Acoustical ceilings", True, 30),
    ("09 53", "Acoustical ceilings", True, 31),
    ("09 65", "Flooring (resilient / carpet / access)", True, 40),
    ("09 68", "Flooring (resilient / carpet / access)", True, 41),
    ("09 69", "Flooring (resilient / carpet / access)", True, 42),
    ("09 72", "Wall coverings", True, 50),
    ("09 77", "Wall coverings", True, 51),
    ("09 91", "Painting / staining / high-performance coatings", True, 60),
    ("09 93", "Painting / staining / high-performance coatings", True, 61),
    ("09 94", "Painting / staining / high-performance coatings", True, 62),
    ("10 11", "Visual display boards", True, 70),
    ("10 14", "Signage", False, 71),
    ("10 21", "Toilet compartments / urinal screens", True, 80),
    ("10 26", "Wall / door protection, corner guards, handrails", True, 81),
    ("10 28", "Toilet accessories", False, 82),
    ("10 44", "Fire extinguisher cabinets", True, 90),
    ("10 51", "Lockers", True, 91),
)

MANUFACTURER_ALIASES: dict[str, str] = {
    "inpro": "Inpro",
    "inpro corporation": "Inpro",
    "inpro corp": "Inpro",
    "ipc": "Inpro",
    "construction specialties": "Construction Specialties",
    "cs": "Construction Specialties",
    "acrovyn": "Construction Specialties",
    "penco": "Penco",
    "asi": "ASI",
    "american specialties": "ASI",
    "bobrick": "Bobrick",
    "claridge": "Claridge",
    "jl industries": "JL Industries",
    "jl": "JL Industries",
    "larsen": "Larsen",
    "potter roemer": "Potter Roemer",
    "sherwin": "Sherwin-Williams",
    "sherwin-williams": "Sherwin-Williams",
    "sherwin williams": "Sherwin-Williams",
    "ppg": "PPG",
    "dunn-edwards": "Dunn-Edwards",
    "dunn edwards": "Dunn-Edwards",
    "armstrong": "Armstrong",
    "usg": "USG",
    "united states gypsum": "USG",
    "certainteed": "CertainTeed",
    "national gypsum": "National Gypsum",
    "clarkdietrich": "ClarkDietrich",
    "clark dietrich": "ClarkDietrich",
    "scranton": "Scranton",
    "bradley": "Bradley",
    "lyon": "Lyon",
    "platinum": "Platinum",
}

CONFIGURATOR_PREFIXES: dict[str, str] = {"1051": "penco_locker"}

FINISH_TITLE_RE = re.compile(
    r"finish|interior|spec|schedule|door|toilet|locker|ceiling|paint|floor|"
    r"wall protect|signage|casework|gypsum|drywall|partition",
    re.I,
)
CIVIL_STRUCT_RE = re.compile(r"\b(civil|structur|site|civil)\b", re.I)
BOD_RE = re.compile(
    r"(?:basis of design|as manufactured by|manufactured by)[:\s]+(.{3,160})",
    re.I,
)
ALT_RE = re.compile(
    r"(?:acceptable manufacturers?|listed manufacturers?|approved manufacturers?)[:\s]+(.{5,240})",
    re.I,
)
OR_EQUAL_RE = re.compile(r"\bor[\s\-]?equal\b|\bapproved equal\b", re.I)
PROHIBITED_RE = re.compile(r"\b(?:not acceptable|prohibited|not permitted)\b[:\s]+(.{3,160})", re.I)
SCHEDULE_RE = re.compile(r"\b((?:PT|ACT|WP|WD|PLAM|EP|P)-\d+)\b")
SUB_RE = re.compile(r"(prior approval[^.]{0,80}|substitutions?[^.]{0,80})", re.I)

DEFAULT_SCOPE = (
    "Quote material for the in-scope sections listed below per the attached specifications\n"
    "and drawings. Install is by US Interior Specialties unless noted."
)
DEFAULT_INCLUSIONS = (
    "- Basis of Design products as specified\n"
    "- Listed acceptable alternates (price separately if different from BOD)\n"
    "- Freight to job / shop as requested on the form"
)
DEFAULT_EXCLUSIONS = (
    "- Installation\n"
    "- Products marked prohibited\n"
    "- Substitution packages that miss the spec’s prior-approval window"
)
DEFAULT_CLARIFICATIONS = (
    "- Identify BOD vs alternate on each price\n"
    "- Note lead time and any color / finish assumptions"
)

_ROLE_LABEL = {
    "basis_of_design": "BOD",
    "listed_alternate": "Alternate",
    "or_equal": "Or equal",
    "prohibited": "Prohibited",
    "schedule_item": "Schedule",
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _digits(raw: str | None) -> str:
    return re.sub(r"\D", "", str(raw or ""))


def _prefix_digits(prefix: str) -> str:
    return _digits(prefix)[:6]


def prefix_matches(prefix: str, spec_code: str) -> bool:
    p = _prefix_digits(prefix)
    s = _digits(spec_code)
    return bool(p) and bool(s) and s.startswith(p)


def display_csi(raw: str | None) -> str:
    return format_csi_display(raw) or str(raw or "").strip()


def canonicalize_manufacturer(raw: str | None) -> str:
    s = re.sub(r"\s+", " ", (raw or "").strip())
    if not s:
        return ""
    key = s.lower().rstrip(".")
    if key in MANUFACTURER_ALIASES:
        return MANUFACTURER_ALIASES[key]
    for alias, canon in MANUFACTURER_ALIASES.items():
        if alias in key or key in alias:
            return canon
    return s[:200]


def configurator_key_for(csi: str, manufacturer: str) -> str | None:
    digits = _digits(csi)
    key = CONFIGURATOR_PREFIXES.get(digits[:4])
    if not key:
        return None
    mfr = canonicalize_manufacturer(manufacturer).lower()
    if key == "penco_locker" and mfr in ("penco", "asi", "lyon"):
        return key
    if key:
        return key
    return None


def parse_model_json(raw: str | None) -> dict[str, Any]:
    """Repair markdown-wrapped JSON from the model."""
    s = (raw or "").strip()
    if not s:
        raise ApiError("empty model output")
    if s.startswith("```"):
        s = re.sub(r"^```(?:json)?\s*", "", s, flags=re.I)
        s = re.sub(r"\s*```$", "", s)
    start = s.find("{")
    end = s.rfind("}")
    if start >= 0 and end > start:
        s = s[start : end + 1]
    try:
        data = json.loads(s)
    except json.JSONDecodeError as exc:
        raise ApiError(f"model output is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ApiError("model output must be a JSON object")
    sections = data.get("sections")
    if sections is None:
        data["sections"] = []
    elif not isinstance(sections, list):
        raise ApiError("sections must be a list")
    warnings = data.get("warnings")
    if warnings is None:
        data["warnings"] = []
    elif not isinstance(warnings, list):
        data["warnings"] = [str(warnings)]
    return data


def heuristic_mentions_from_text(text: str, *, page_cite: str = "") -> list[dict[str, Any]]:
    """Assistive regex extract of BOD / alternates / or-equal from spec text."""
    out: list[dict[str, Any]] = []
    blob = text or ""
    or_eq = bool(OR_EQUAL_RE.search(blob))
    sub = ""
    sm = SUB_RE.search(blob)
    if sm:
        sub = sm.group(0).strip()[:240]

    def _add(role: str, manufacturer: str, excerpt: str, extra: dict[str, Any] | None = None) -> None:
        mfr = canonicalize_manufacturer(manufacturer)
        if not mfr:
            return
        row = {
            "role": role,
            "manufacturer": mfr,
            "product_line": None,
            "model_no": None,
            "finish_note": None,
            "or_equal": or_eq and role in ("basis_of_design", "or_equal"),
            "substitution_note": sub or None,
            "page_cite": page_cite or "",
            "excerpt": (excerpt or "")[:400],
        }
        if extra:
            row.update(extra)
        key = (row["role"], row["manufacturer"].lower(), row.get("model_no") or "")
        if any((x["role"], x["manufacturer"].lower(), x.get("model_no") or "") == key for x in out):
            return
        out.append(row)

    for m in BOD_RE.finditer(blob):
        chunk = re.split(r"[.;\n]", m.group(1), maxsplit=1)[0].strip(" ,;")
        _add("basis_of_design", chunk.split(",")[0], m.group(0)[:240])
    for m in ALT_RE.finditer(blob):
        names = re.split(r",|;| and ", m.group(1))
        for name in names:
            name = name.strip(" .;")
            if len(name) < 2:
                continue
            _add("listed_alternate", name, m.group(0)[:240])
    if or_eq and not any(x["role"] == "or_equal" for x in out):
        _add("or_equal", "or equal", "Spec allows or-equal / approved equal.")
    for m in PROHIBITED_RE.finditer(blob):
        _add("prohibited", m.group(1).split(",")[0], m.group(0)[:240])
    for m in SCHEDULE_RE.finditer(blob):
        _add("schedule_item", m.group(1), m.group(0), {"product_line": m.group(1)})
    return out


def ensure_trade_map() -> list[SpecTradeMap]:
    existing = {r.csi_prefix: r for r in db.session.scalars(select(SpecTradeMap)).all()}
    if not existing:
        for prefix, label, default_on, order in TRADE_SEEDS:
            db.session.add(
                SpecTradeMap(
                    csi_prefix=prefix,
                    trade_label=label,
                    enabled=True,
                    default_in_scope=default_on,
                    sort_order=order,
                )
            )
        db.session.flush()
        existing = {r.csi_prefix: r for r in db.session.scalars(select(SpecTradeMap)).all()}
    return [existing[k] for k in sorted(existing, key=lambda x: existing[x].sort_order)]


def match_trade(csi: str) -> SpecTradeMap | None:
    rows = [r for r in ensure_trade_map() if r.enabled]
    digits = _digits(csi)
    best: SpecTradeMap | None = None
    best_len = -1
    for row in rows:
        p = _prefix_digits(row.csi_prefix)
        if p and digits.startswith(p) and len(p) >= best_len:
            best = row
            best_len = len(p)
    return best


def _audit(cu: CurrentUser | None, entity_id: uuid.UUID | None, action: str, changes: dict[str, Any] | None = None) -> None:
    db.session.add(
        AuditLog(
            user_id=cu.user.id if cu and cu.user else None,
            entity_type="estimate_spec_scan",
            entity_id=entity_id,
            action=action,
            changes=changes,
        )
    )


def _load_estimate(estimate_id: uuid.UUID) -> Estimate:
    est = db.session.get(Estimate, estimate_id)
    if est is None:
        raise ApiError("estimate not found", 404)
    return est


def latest_scan(estimate_id: uuid.UUID) -> EstimateSpecScan | None:
    return db.session.scalar(
        select(EstimateSpecScan)
        .where(EstimateSpecScan.estimate_id == estimate_id)
        .order_by(EstimateSpecScan.created_at.desc())
        .limit(1)
    )


def _scan_with_children(scan_id: uuid.UUID) -> EstimateSpecScan | None:
    return db.session.scalar(
        select(EstimateSpecScan)
        .options(
            selectinload(EstimateSpecScan.sections).selectinload(EstimateSpecSection.mentions),
            selectinload(EstimateSpecScan.vendors),
        )
        .where(EstimateSpecScan.id == scan_id)
    )


def _project_id_for(est: Estimate) -> uuid.UUID | None:
    if est.project_id:
        return est.project_id
    lead = est.lead_estimate
    if lead is not None:
        return lead.project_id
    return None


def list_spec_documents(project_id: uuid.UUID) -> list[Any]:
    """Return spec-like document rows without polymorphic Document loading.

    `document_type=specification` is a valid enum value but has no SQLAlchemy
    subclass, so ORM load of those rows raises. Read the table instead.
    """
    import types as _types

    t = Document.__table__
    rows = db.session.execute(
        select(t).where(
            t.c.project_id == project_id,
            t.c.document_type.in_(("specification", "other", "contract")),
        ).order_by(t.c.created_at.desc())
    ).mappings().all()
    out: list[Any] = []
    for row in rows:
        d = _types.SimpleNamespace(**dict(row))
        title = f"{getattr(d, 'title', '') or ''} {getattr(d, 'original_filename', '') or ''} {d.document_type or ''}".lower()
        tags = d.tags if isinstance(getattr(d, "tags", None), dict) else {}
        kind = str(tags.get("doc_kind") or tags.get("kind") or "").lower()
        if d.document_type == "specification" or kind in (
            "spec",
            "project_manual",
            "addendum",
            "spec_section",
        ):
            out.append(d)
            continue
        if any(tok in title for tok in ("spec", "manual", "addend", "project manual")):
            out.append(d)
    return out


def list_drawings(project_id: uuid.UUID) -> list[Drawing]:
    return list(
        db.session.scalars(
            select(Drawing).where(Drawing.project_id == project_id).order_by(Drawing.sheet_number)
        ).all()
    )


def sources_for_estimate(est: Estimate) -> dict[str, Any]:
    pid = _project_id_for(est)
    docs: list[Document] = []
    drawings: list[Drawing] = []
    spec_sections: list[SpecSection] = []
    if pid:
        docs = list_spec_documents(pid)
        drawings = list_drawings(pid)
        spec_sections = list(
            db.session.scalars(select(SpecSection).where(SpecSection.project_id == pid, SpecSection.is_active.is_(True))).all()
        )
    return {
        "project_id": str(pid) if pid else None,
        "has_specs": bool(docs) or bool(spec_sections),
        "has_drawings": bool(drawings),
        "analyze_enabled": bool(docs) or bool(drawings) or bool(spec_sections),
        "spec_files": [
            {
                "id": str(d.id),
                "title": d.title or d.original_filename,
                "filename": d.original_filename,
                "document_type": d.document_type,
            }
            for d in docs
        ],
        "spec_sections": [{"id": str(s.id), "code": s.code, "title": s.title} for s in spec_sections[:200]],
        "sheet_index": [
            {
                "id": str(d.id),
                "sheet_number": d.sheet_number,
                "sheet_title": d.sheet_title or d.title,
                "discipline": d.discipline,
            }
            for d in drawings[:400]
        ],
        "government": _is_government(pid),
    }


def _is_government(project_id: uuid.UUID | None) -> bool:
    if not project_id:
        return False
    p = db.session.get(Project, project_id)
    return bool(p is not None and (p.project_type or "") == "government")


def grok_allowed(project_id: uuid.UUID | None) -> bool:
    """Do not dump spec books to Grok on government jobs."""
    return not _is_government(project_id)


def _doc_ns(doc_id: uuid.UUID | None) -> Any | None:
    if not doc_id:
        return None
    import types as _types

    t = Document.__table__
    row = db.session.execute(select(t).where(t.c.id == doc_id)).mappings().first()
    if not row:
        return None
    return _types.SimpleNamespace(**dict(row))


def _document_pdf_bytes(doc: Any) -> bytes | None:
    from ..services.object_storage import UploadCategory, read_stored_bytes
    from ..services.project_file_keys import document_object_candidates

    for name in document_object_candidates(doc):
        data = read_stored_bytes(UploadCategory.DOCUMENTS, name)
        if data:
            return data
    return None


def _pdf_page_texts(data: bytes) -> list[tuple[int, str]]:
    pages: list[tuple[int, str]] = []
    try:
        import fitz
    except ImportError:
        fitz = None  # type: ignore
    if fitz is not None:
        try:
            doc = fitz.open(stream=data, filetype="pdf")
        except Exception:
            doc = None
        if doc is not None:
            try:
                for i, page in enumerate(doc, start=1):
                    pages.append((i, page.get_text() or ""))
            finally:
                doc.close()
            return pages
    try:
        from pypdf import PdfReader
        import io

        reader = PdfReader(io.BytesIO(data))
        for i, page in enumerate(reader.pages, start=1):
            pages.append((i, page.extract_text() or ""))
    except Exception:
        pass
    return pages


def _page_range_for_csi(pages: list[tuple[int, str]], csi: str) -> tuple[int | None, int | None, str | None]:
    digits = _digits(csi)
    disp = display_csi(csi)
    hits: list[int] = []
    for num, text in pages:
        blob = text or ""
        if digits and digits in re.sub(r"\D", "", blob[:800]):
            hits.append(num)
            continue
        if disp and disp in blob:
            hits.append(num)
    if not hits:
        return None, None, None
    start, end = min(hits), max(hits)
    return start, end, f"pp. {disp}-{start}–{end}" if disp else f"pp. {start}–{end}"


def _included_bid_codes(estimate_id: uuid.UUID) -> set[str]:
    scope = db.session.scalar(select(EstimateBidScope).where(EstimateBidScope.estimate_id == estimate_id))
    if scope is None:
        return set()
    return {
        _digits(it.spec_code)
        for it in db.session.scalars(
            select(EstimateBidScopeItem).where(
                EstimateBidScopeItem.scope_id == scope.id, EstimateBidScopeItem.included.is_(True)
            )
        ).all()
        if _digits(it.spec_code)
    }


def _default_in_scope(csi: str, trade: SpecTradeMap | None, bid_codes: set[str], confidence: float) -> bool:
    if trade is None or not trade.enabled:
        return False
    if confidence < 0.6:
        return False
    digits = _digits(csi)
    if bid_codes:
        if not any(digits.startswith(code[: len(code)]) or code.startswith(digits[:4]) for code in bid_codes if code):
            if not trade.default_in_scope:
                return False
            # Bid scope exists but this prefix was not tagged — keep default_in_scope.
            if not any(prefix_matches(trade.csi_prefix, code) or prefix_matches(code, csi) for code in bid_codes):
                return bool(trade.default_in_scope)
    return bool(trade.default_in_scope)


def _has_sent_rfps(scan: EstimateSpecScan) -> bool:
    rows = db.session.scalars(select(Rfp).where(Rfp.source_spec_scan_id == scan.id)).all()
    return any((r.status or "") != "Draft" or r.sent_at is not None for r in rows)


def _delete_unconfirmed(scan: EstimateSpecScan) -> None:
    for sec in list(scan.sections):
        confirmed_mentions = [m for m in sec.mentions if m.confirmed]
        if sec.confirmed_at is not None:
            for m in list(sec.mentions):
                if not m.confirmed:
                    db.session.delete(m)
            continue
        if confirmed_mentions:
            for m in list(sec.mentions):
                if not m.confirmed:
                    db.session.delete(m)
            continue
        db.session.delete(sec)
    db.session.flush()


def _upsert_section(
    scan: EstimateSpecScan,
    *,
    csi: str,
    title: str,
    out_of_trade: bool,
    confidence: Decimal,
    document_id: uuid.UUID | None,
    page_start: int | None,
    page_end: int | None,
    page_label: str | None,
    in_scope: bool,
    notes: str | None = None,
) -> EstimateSpecSection:
    disp = display_csi(csi) or csi
    existing = next((s for s in scan.sections if _digits(s.csi_code) == _digits(disp)), None)
    if existing is not None and existing.confirmed_at is not None:
        return existing
    if existing is None:
        existing = EstimateSpecSection(scan_id=scan.id, csi_code=disp)
        db.session.add(existing)
        scan.sections.append(existing)
    existing.title = (title or title_for_code(disp) or disp)[:300]
    existing.out_of_trade = out_of_trade
    existing.confidence = confidence
    existing.document_id = document_id or existing.document_id
    existing.page_start = page_start
    existing.page_end = page_end
    existing.page_label = page_label
    existing.in_scope = in_scope if existing.confirmed_at is None else existing.in_scope
    if notes:
        existing.estimator_notes = notes
    return existing


def _upsert_mention(section: EstimateSpecSection, payload: Mapping[str, Any], *, confirmed: bool = False) -> EstimateSpecMention:
    role = str(payload.get("role") or payload.get("mention_role") or "listed_alternate").strip().lower()
    if role not in MENTION_ROLES:
        role = "listed_alternate"
    mfr = canonicalize_manufacturer(str(payload.get("manufacturer") or ""))
    model = (str(payload.get("model_no") or payload.get("model") or "").strip() or None)
    existing = next(
        (
            m
            for m in section.mentions
            if m.mention_role == role
            and (m.manufacturer or "").lower() == mfr.lower()
            and (m.model_no or None) == model
        ),
        None,
    )
    if existing is not None and existing.confirmed:
        return existing
    row = existing or EstimateSpecMention(section_id=section.id)
    if existing is None:
        db.session.add(row)
        section.mentions.append(row)
    row.mention_role = role
    row.manufacturer = mfr[:200]
    row.product_line = (str(payload.get("product_line") or "").strip() or None)
    row.model_no = model[:120] if model else None
    row.finish_note = (str(payload.get("finish_note") or "").strip() or None)
    row.or_equal = bool(payload.get("or_equal"))
    row.substitution_note = (str(payload.get("substitution_note") or "").strip() or None)
    row.page_cite = str(payload.get("page_cite") or payload.get("pages") or "")[:80]
    excerpt = str(payload.get("excerpt") or "").strip()
    row.excerpt = excerpt[:800] if excerpt else None
    row.confirmed = bool(confirmed) or bool(row.confirmed)
    apply_catalog_match(row, section.csi_code)
    return row


def apply_catalog_match(mention: EstimateSpecMention, csi: str) -> None:
    cfg = configurator_key_for(csi, mention.manufacturer)
    if cfg:
        mention.configurator_key = cfg
        mention.match_status = "needs_configurator"
        mention.material_pricing_id = None
        return
    mfr = canonicalize_manufacturer(mention.manufacturer)
    if not mfr:
        mention.match_status = "unmatched"
        return
    q = select(MaterialPrice).where(func.lower(MaterialPrice.manufacturer) == mfr.lower())
    csi_digits = _digits(csi)
    rows = list(db.session.scalars(q.limit(40)).all())
    if csi_digits:
        tighter = [
            r
            for r in rows
            if _digits(r.csi_spec_section or "").startswith(csi_digits[:4])
            or not r.csi_spec_section
        ]
        if tighter:
            rows = tighter
    if not rows:
        mention.match_status = "unmatched"
        mention.material_pricing_id = None
        return
    model = (mention.model_no or "").strip().lower()
    sku = None
    if model:
        sku = next((r for r in rows if model and model in (r.item or "").lower()), None)
    if sku is not None:
        mention.material_pricing_id = sku.id
        mention.match_status = "sku_matched"
        return
    mention.material_pricing_id = rows[0].id
    mention.match_status = "family_matched"


def apply_model_output(
    scan: EstimateSpecScan, payload: Mapping[str, Any] | str, *, cu: CurrentUser | None = None
) -> EstimateSpecScan:
    if isinstance(payload, str):
        data = parse_model_json(payload)
    elif isinstance(payload, Mapping) and "sections" in payload:
        data = payload
    else:
        data = parse_model_json(json.dumps(payload))
    sections = data.get("sections") if isinstance(data, dict) else None
    if not isinstance(sections, list):
        raise ApiError("sections must be a list")
    bid_codes = _included_bid_codes(scan.estimate_id)
    warnings = data.get("warnings") if isinstance(data, dict) else None
    note = None
    if isinstance(warnings, list) and warnings:
        note = "; ".join(str(w) for w in warnings if w)[:2000]
    scan.raw_response = json.dumps(data)[:20000]
    for raw in sections:
        if not isinstance(raw, Mapping):
            continue
        csi = display_csi(str(raw.get("csi") or raw.get("csi_code") or "")) or ""
        if not _digits(csi):
            continue
        trade = match_trade(csi)
        try:
            conf = float(raw.get("confidence") if raw.get("confidence") is not None else 0.7)
        except (TypeError, ValueError):
            conf = 0.7
        conf = max(0.0, min(1.0, conf))
        out_of_trade = trade is None
        suggested = raw.get("in_scope_suggestion")
        in_scope = bool(suggested) if suggested is not None else _default_in_scope(csi, trade, bid_codes, conf)
        if out_of_trade:
            in_scope = False
        doc_id = _parse_uuid(raw.get("document_id"))
        sec = _upsert_section(
            scan,
            csi=csi,
            title=str(raw.get("title") or ""),
            out_of_trade=out_of_trade,
            confidence=Decimal(str(round(conf, 4))),
            document_id=doc_id,
            page_start=None,
            page_end=None,
            page_label=str(raw.get("pages") or "")[:80] or None,
            in_scope=in_scope,
            notes=note,
        )
        mentions = raw.get("mentions") or []
        if isinstance(mentions, list):
            for m in mentions:
                if isinstance(m, Mapping):
                    _upsert_mention(sec, m)
    scan.status = "review_sections"
    scan.progress_text = None
    db.session.flush()
    _audit(cu, scan.id, "apply_model", {"sections": len(scan.sections)})
    return scan


def detect_from_text(scan: EstimateSpecScan, text: str, *, document_id: uuid.UUID | None = None) -> None:
    bid_codes = _included_bid_codes(scan.estimate_id)
    found = parse_codes_from_text(text or "")
    for row in found:
        csi = row.get("code") or display_csi(row.get("digits")) or ""
        trade = match_trade(csi)
        out_of_trade = trade is None
        conf = 0.75 if trade is not None else 0.4
        in_scope = _default_in_scope(csi, trade, bid_codes, conf) and not out_of_trade
        sec = _upsert_section(
            scan,
            csi=csi,
            title=row.get("title") or "",
            out_of_trade=out_of_trade,
            confidence=Decimal(str(conf)),
            document_id=document_id,
            page_start=None,
            page_end=None,
            page_label=None,
            in_scope=in_scope,
        )
        for m in heuristic_mentions_from_text(text, page_cite=display_csi(csi) or ""):
            _upsert_mention(sec, m)


def _detect_from_document(scan: EstimateSpecScan, doc: Any) -> int:
    data = _document_pdf_bytes(doc)
    found_n = 0
    pages: list[tuple[int, str]] = []
    codes: list[dict[str, str]] = []
    if data:
        codes = extract_csi_sections_from_pdf(data)
        pages = _pdf_page_texts(data)
    bid_codes = _included_bid_codes(scan.estimate_id)
    if not codes and pages:
        blob = "\n".join(t for _, t in pages)
        codes = parse_codes_from_text(blob)
    for row in codes:
        csi = row.get("code") or display_csi(row.get("digits")) or ""
        if not _digits(csi):
            continue
        trade = match_trade(csi)
        out_of_trade = trade is None
        conf = 0.8 if trade is not None else 0.35
        in_scope = _default_in_scope(csi, trade, bid_codes, conf) and not out_of_trade
        start, end, label = _page_range_for_csi(pages, csi)
        sec = _upsert_section(
            scan,
            csi=csi,
            title=row.get("title") or "",
            out_of_trade=out_of_trade,
            confidence=Decimal(str(conf)),
            document_id=doc.id,
            page_start=start,
            page_end=end,
            page_label=label,
            in_scope=in_scope,
        )
        section_text = ""
        if pages and start and end:
            section_text = "\n".join(t for n, t in pages if start <= n <= end)
        elif pages:
            section_text = "\n".join(t for _, t in pages[:8])
        if section_text:
            cite = label or display_csi(csi) or ""
            for m in heuristic_mentions_from_text(section_text, page_cite=cite):
                _upsert_mention(sec, m)
        found_n += 1
    return found_n


def analyze_estimate(
    est: Estimate,
    *,
    cu: CurrentUser,
    provider: str = "llama4-scout",
    text: str | None = None,
    model_output: Mapping[str, Any] | str | None = None,
) -> EstimateSpecScan:
    pid = _project_id_for(est)
    sources = sources_for_estimate(est)
    if not sources["analyze_enabled"] and not text and not model_output:
        raise ApiError(
            "No specification files on this job yet. Upload a project manual under Files → Specs, then analyze.",
            400,
        )
    scan = latest_scan(est.id)
    if scan is not None and _has_sent_rfps(scan):
        scan = None
    if scan is None or scan.status == "cancelled":
        scan = EstimateSpecScan(
            estimate_id=est.id,
            project_id=pid,
            status="detecting",
            provider=(provider or "llama4-scout")[:40],
            created_by_id=cu.id,
            started_at=_utcnow(),
        )
        db.session.add(scan)
        db.session.flush()
    else:
        if (est.status or "").lower() not in ("draft", "open", "in_progress", "pricing", ""):
            if (est.status or "").lower() in ("locked", "awarded", "sent"):
                raise ApiError("Analyze specs is available on draft estimates only", 400)
        scan.status = "detecting"
        scan.provider = (provider or scan.provider or "llama4-scout")[:40]
        scan.started_at = _utcnow()
        scan.error_text = None
        _delete_unconfirmed(scan)
    _audit(cu, scan.id, "start", {"provider": scan.provider})

    if model_output:
        apply_model_output(scan, model_output if isinstance(model_output, Mapping) else parse_model_json(str(model_output)), cu=cu)
        return scan

    total = 0
    if text:
        detect_from_text(scan, text)
        total += 1
    if pid:
        docs = list_spec_documents(pid)
        for i, doc in enumerate(docs, start=1):
            scan.progress_text = f"Section file {i} of {len(docs)}"
            db.session.flush()
            total += _detect_from_document(scan, doc)
        if not docs:
            for sec in db.session.scalars(
                select(SpecSection).where(SpecSection.project_id == pid, SpecSection.is_active.is_(True))
            ).all():
                csi = display_csi(sec.code) or sec.code
                trade = match_trade(csi)
                out_of_trade = trade is None
                conf = 0.7 if trade is not None else 0.3
                bid_codes = _included_bid_codes(est.id)
                _upsert_section(
                    scan,
                    csi=csi,
                    title=sec.title or "",
                    out_of_trade=out_of_trade,
                    confidence=Decimal(str(conf)),
                    document_id=None,
                    page_start=None,
                    page_end=None,
                    page_label=None,
                    in_scope=_default_in_scope(csi, trade, bid_codes, conf) and not out_of_trade,
                )
                total += 1
    scan.status = "review_sections"
    scan.progress_text = None
    scan.completed_at = _utcnow()
    if total == 0 and not scan.sections:
        scan.error_text = "No CSI sections found in the uploaded files."
    db.session.flush()
    return scan


def patch_sections(scan: EstimateSpecScan, items: list[Mapping[str, Any]]) -> EstimateSpecScan:
    by_id = {str(s.id): s for s in scan.sections}
    for raw in items:
        if not isinstance(raw, Mapping):
            continue
        row = by_id.get(str(raw.get("id") or ""))
        if row is None:
            continue
        if "in_scope" in raw:
            row.in_scope = bool(raw.get("in_scope"))
        if "shop_alternates" in raw:
            row.shop_alternates = bool(raw.get("shop_alternates"))
        if "estimator_notes" in raw:
            row.estimator_notes = (str(raw.get("estimator_notes") or "").strip() or None)
        if "title" in raw:
            row.title = str(raw.get("title") or row.title)[:300]
    db.session.flush()
    return scan


def confirm_sections(scan: EstimateSpecScan, *, cu: CurrentUser) -> EstimateSpecScan:
    now = _utcnow()
    n = 0
    for sec in scan.sections:
        if sec.in_scope:
            sec.confirmed_at = now
            sec.confirmed_by_id = cu.id
            n += 1
        else:
            sec.confirmed_at = now
            sec.confirmed_by_id = cu.id
    if n == 0:
        raise ApiError("Confirm at least one in-scope section")
    scan.status = "extracting"
    # Mentions may already exist from analyze; extract leftovers from stored page labels.
    for sec in scan.sections:
        if not sec.in_scope:
            continue
        if sec.mentions:
            continue
        if sec.document_id:
            doc = _doc_ns(sec.document_id)
            if doc is not None:
                _detect_from_document(scan, doc)
    scan.status = "review_products"
    db.session.flush()
    _audit(cu, scan.id, "confirm_sections", {"in_scope": n})
    return scan


def patch_mentions(scan: EstimateSpecScan, items: list[Mapping[str, Any]]) -> EstimateSpecScan:
    by_id = {str(m.id): m for sec in scan.sections for m in sec.mentions}
    for raw in items:
        if not isinstance(raw, Mapping):
            continue
        mid = str(raw.get("id") or "")
        if mid == "new" or raw.get("create"):
            sid = _parse_uuid(raw.get("section_id"))
            sec = next((s for s in scan.sections if s.id == sid), None)
            if sec is None:
                continue
            _upsert_mention(sec, raw)
            continue
        row = by_id.get(mid)
        if row is None:
            continue
        if "manufacturer" in raw:
            row.manufacturer = canonicalize_manufacturer(str(raw.get("manufacturer") or ""))[:200]
        if "product_line" in raw:
            row.product_line = (str(raw.get("product_line") or "").strip() or None)
        if "model_no" in raw:
            row.model_no = (str(raw.get("model_no") or "").strip() or None)
        if "finish_note" in raw:
            row.finish_note = (str(raw.get("finish_note") or "").strip() or None)
        if "or_equal" in raw:
            row.or_equal = bool(raw.get("or_equal"))
        if "substitution_note" in raw:
            row.substitution_note = (str(raw.get("substitution_note") or "").strip() or None)
        if "page_cite" in raw:
            row.page_cite = str(raw.get("page_cite") or "")[:80]
        if "excerpt" in raw:
            row.excerpt = (str(raw.get("excerpt") or "").strip() or None)
        if "mention_role" in raw or "role" in raw:
            role = str(raw.get("mention_role") or raw.get("role") or row.mention_role).lower()
            if role in MENTION_ROLES:
                row.mention_role = role
        if "confirmed" in raw:
            row.confirmed = bool(raw.get("confirmed"))
        apply_catalog_match(row, row.section.csi_code if row.section else "")
    db.session.flush()
    return scan


def confirm_products(scan: EstimateSpecScan, *, cu: CurrentUser) -> EstimateSpecScan:
    n = 0
    for sec in scan.sections:
        if not sec.in_scope:
            continue
        for m in sec.mentions:
            if m.mention_role == "prohibited":
                m.confirmed = True
                continue
            m.confirmed = True
            n += 1
    if n == 0:
        raise ApiError("No product mentions to confirm. Add a BOD row or re-run extract.")
    scan.status = "review_products"
    db.session.flush()
    _audit(cu, scan.id, "confirm_products", {"mentions": n})
    suggest_vendors(scan)
    return scan


def _company_blob(c: Company) -> str:
    specs = c.trade_specialties
    extra = ""
    if isinstance(specs, dict):
        extra = " ".join(str(v) for v in specs.values())
    elif isinstance(specs, list):
        extra = " ".join(str(v) for v in specs)
    return f"{c.name or ''} {extra}".lower()


def _vendor_companies() -> list[Company]:
    types = ("vendor", "subcontractor", "other")
    return list(
        db.session.scalars(
            select(Company).where(Company.deleted_at.is_(None), Company.company_type.in_(types))
        ).all()
    )


def _past_award_company_ids(manufacturer: str) -> set[uuid.UUID]:
    from ..models import RfpVendorQuote as Quote

    if not manufacturer:
        return set()
    q = (
        select(Quote.vendor_company_id)
        .join(Rfp, Quote.rfp_id == Rfp.id)
        .where(Rfp.status == "Awarded", Quote.vendor_company_id.is_not(None))
        .limit(200)
    )
    ids = {x for x in db.session.scalars(q).all() if x}
    # Prefer companies whose name matches the manufacturer.
    if not ids:
        return set()
    mfr = manufacturer.lower()
    keep: set[uuid.UUID] = set()
    for cid in ids:
        c = db.session.get(Company, cid)
        if c is not None and mfr in (c.name or "").lower():
            keep.add(cid)
    return keep or ids


def suggest_vendors(scan: EstimateSpecScan) -> EstimateSpecScan:
    companies = _vendor_companies()
    existing = {str(v.company_id): v for v in scan.vendors}
    in_scope = [s for s in scan.sections if s.in_scope]
    ranked: dict[uuid.UUID, dict[str, Any]] = {}

    def _touch(company: Company, reason: str, csi: str, score: int) -> None:
        rec = ranked.setdefault(
            company.id,
            {"company": company, "reason": reason, "score": 0, "sections": set()},
        )
        rec["score"] += score
        rec["sections"].add(display_csi(csi) or csi)
        order = ("bod_house", "listed_alternate", "past_award", "trade_tag", "manual")
        if order.index(reason) < order.index(rec["reason"]):
            rec["reason"] = reason

    for sec in in_scope:
        mentions = list(sec.mentions)
        if not sec.shop_alternates:
            mentions = [m for m in mentions if m.mention_role == "basis_of_design"]
        for m in mentions:
            if m.mention_role == "prohibited":
                continue
            mfr = canonicalize_manufacturer(m.manufacturer)
            if not mfr:
                continue
            house = next((c for c in companies if mfr.lower() in (c.name or "").lower()), None)
            if house is not None:
                reason = "bod_house" if m.mention_role == "basis_of_design" else "listed_alternate"
                _touch(house, reason, sec.csi_code, 50 if reason == "bod_house" else 35)
            for cid in _past_award_company_ids(mfr):
                c = db.session.get(Company, cid)
                if c is not None:
                    _touch(c, "past_award", sec.csi_code, 20)
            label = (match_trade(sec.csi_code).trade_label if match_trade(sec.csi_code) else "") or ""
            tokens = [t for t in re.split(r"[/,]", label.lower()) if len(t.strip()) > 3]
            for c in companies:
                blob = _company_blob(c)
                if mfr.lower() in blob or any(tok.strip() in blob for tok in tokens):
                    _touch(c, "trade_tag", sec.csi_code, 10)

    # Keep existing manual rows.
    for vid, row in existing.items():
        cid = _parse_uuid(vid)
        if cid and cid not in ranked:
            ranked[cid] = {
                "company": db.session.get(Company, cid),
                "reason": row.suggested_reason or "manual",
                "score": 1,
                "sections": set(row.sections or []),
            }

    keep_ids = set(ranked)
    for row in list(scan.vendors):
        if row.company_id not in keep_ids and row.suggested_reason != "manual":
            db.session.delete(row)
    db.session.flush()

    for cid, rec in ranked.items():
        company = rec["company"]
        if company is None:
            continue
        row = existing.get(str(cid))
        if row is None:
            row = EstimateSpecVendor(scan_id=scan.id, company_id=cid)
            db.session.add(row)
            scan.vendors.append(row)
        row.suggested_reason = rec["reason"]
        row.sections = sorted(str(x) for x in rec["sections"] if x)
        if not row.selected and rec["reason"] in ("bod_house", "listed_alternate"):
            row.selected = True
    scan.status = "vendors_ready"
    db.session.flush()
    return scan


def patch_vendors(scan: EstimateSpecScan, items: list[Mapping[str, Any]]) -> EstimateSpecScan:
    by_id = {str(v.id): v for v in scan.vendors}
    by_co = {str(v.company_id): v for v in scan.vendors}
    for raw in items:
        if not isinstance(raw, Mapping):
            continue
        row = by_id.get(str(raw.get("id") or "")) or by_co.get(str(raw.get("company_id") or ""))
        cid = _parse_uuid(raw.get("company_id"))
        if row is None and cid:
            row = EstimateSpecVendor(
                scan_id=scan.id,
                company_id=cid,
                suggested_reason="manual",
                selected=True,
                sections=raw.get("sections") if isinstance(raw.get("sections"), list) else [],
            )
            db.session.add(row)
            scan.vendors.append(row)
            continue
        if row is None:
            continue
        if "selected" in raw:
            row.selected = bool(raw.get("selected"))
        if isinstance(raw.get("sections"), list):
            row.sections = [str(x) for x in raw.get("sections") or []]
    db.session.flush()
    return scan


def _finish_drawings(project_id: uuid.UUID | None, takeoff_ids: set[uuid.UUID]) -> list[uuid.UUID]:
    if not project_id:
        return []
    out: list[uuid.UUID] = []
    for d in list_drawings(project_id):
        disc = (d.discipline or "").lower()
        title = f"{d.sheet_title or ''} {d.title or ''} {d.sheet_number or ''}"
        if CIVIL_STRUCT_RE.search(disc) or CIVIL_STRUCT_RE.search(title):
            continue
        if d.id in takeoff_ids or FINISH_TITLE_RE.search(title) or disc in ("a", "arch", "architectural", "i", "int"):
            out.append(d.id)
    return out


def _line_description(mention: EstimateSpecMention) -> str:
    role = _ROLE_LABEL.get(mention.mention_role, mention.mention_role)
    parts = [p for p in (mention.manufacturer, mention.product_line, mention.model_no) if p]
    body = " ".join(parts).strip() or "As specified"
    return f"{role}: {body}"[:500]


def _seedable_mentions(sec: EstimateSpecSection) -> list[EstimateSpecMention]:
    rows = []
    for m in sec.mentions:
        if not m.confirmed:
            continue
        if m.mention_role == "prohibited":
            continue
        if not sec.shop_alternates and m.mention_role == "listed_alternate":
            continue
        rows.append(m)
    return rows


def create_draft_rfps(
    scan: EstimateSpecScan,
    *,
    cu: CurrentUser,
    grouping: str = "per_vendor",
    takeoff_line_ids: list[str] | None = None,
) -> list[Rfp]:
    from ._rfp_body_service import attach_takeoff, replace_drawings, upsert_line
    from ._rfp_quotes_service import _upsert_bidder, new_mail_tag

    est = _load_estimate(scan.estimate_id)
    in_scope = [s for s in scan.sections if s.in_scope and s.confirmed_at]
    if not in_scope:
        raise ApiError("Confirm in-scope sections first")
    seedable = [(s, m) for s in in_scope for m in _seedable_mentions(s)]
    if not seedable:
        # narrative-only is allowed if estimator confirmed sections
        pass
    selected = [v for v in scan.vendors if v.selected]
    if not selected:
        raise ApiError("Select at least one vendor")
    grouping = (grouping or "per_vendor").strip().lower()
    if grouping not in ("per_vendor", "per_section"):
        grouping = "per_vendor"

    takeoff_ids = [_parse_uuid(x) for x in (takeoff_line_ids or [])]
    takeoff_ids = [x for x in takeoff_ids if x]
    if not takeoff_ids:
        # Prefer matching takeoff rows by CSI prefix when qty exists.
        for tl in db.session.scalars(
            select(TakeoffLineItem).where(TakeoffLineItem.estimate_id == est.id)
        ).all():
            sec_digits = _digits(tl.section or "")
            if any(sec_digits.startswith(_digits(s.csi_code)[:4]) for s in in_scope if _digits(s.csi_code)):
                takeoff_ids.append(tl.id)

    drawing_ids = _finish_drawings(scan.project_id, set())
    # Drawings linked on takeoff lines.
    if takeoff_ids:
        for tl in db.session.scalars(
            select(TakeoffLineItem).where(TakeoffLineItem.id.in_(tuple(takeoff_ids)))
        ).all():
            if tl.drawing_id:
                drawing_ids.append(tl.drawing_id)
    spec_doc_ids = list({s.document_id for s in in_scope if s.document_id})
    if scan.project_id:
        for d in list_spec_documents(scan.project_id):
            title = f"{d.title or ''} {d.original_filename or ''}".lower()
            if "addend" in title and d.id not in spec_doc_ids:
                spec_doc_ids.append(d.id)

    created: list[Rfp] = []

    def _new_rfp(title: str, vendor: EstimateSpecVendor, sections: list[EstimateSpecSection]) -> Rfp:
        token = secrets.token_urlsafe(32)[:64]
        has_takeoff = bool(takeoff_ids)
        has_mentions = any(_seedable_mentions(s) for s in sections)
        if has_takeoff:
            line_source = "takeoff"
        elif has_mentions:
            line_source = "manual"
        else:
            line_source = "narrative"
        r = Rfp(
            lead_estimate_id=est.lead_estimate_id,
            project_id=scan.project_id or est.project_id,
            title=title[:500],
            public_token=token,
            mail_tag=new_mail_tag(),
            status="Draft",
            line_source=line_source,
            source_estimate_id=est.id,
            source_spec_scan_id=scan.id,
            show_line_table=line_source != "narrative",
            scope_of_work=DEFAULT_SCOPE,
            inclusions=DEFAULT_INCLUSIONS,
            exclusions=DEFAULT_EXCLUSIONS,
            clarifications=DEFAULT_CLARIFICATIONS,
        )
        db.session.add(r)
        db.session.flush()
        if has_takeoff:
            try:
                attach_takeoff(r, {"estimate_id": str(est.id), "takeoff_line_ids": [str(x) for x in takeoff_ids]})
            except ApiError:
                pass
        sort = len(list(r.line_items or []))
        for sec in sections:
            for m in _seedable_mentions(sec):
                notes_parts = [p for p in (m.page_cite, m.excerpt, m.substitution_note) if p]
                upsert_line(
                    r,
                    {
                        "description": _line_description(m),
                        "unit": "LS",
                        "quantity": None,
                        "csi_division": sec.csi_code,
                        "trade": (match_trade(sec.csi_code).trade_label if match_trade(sec.csi_code) else None),
                        "notes": " · ".join(notes_parts)[:2000] or None,
                        "sort_order": sort,
                    },
                )
                sort += 1
        drawings_payload = [{"drawing_id": str(did), "include_on_portal": True} for did in dict.fromkeys(drawing_ids)]
        drawings_payload.extend(
            {"document_id": str(did), "include_on_portal": True} for did in spec_doc_ids
        )
        if drawings_payload:
            replace_drawings(r, {"drawings": drawings_payload})
        try:
            _upsert_bidder(r, {"company_id": str(vendor.company_id)})
        except ApiError:
            db.session.add(
                RfpVendorQuote(
                    rfp_id=r.id,
                    vendor_company_id=vendor.company_id,
                    vendor_label="Vendor",
                    source="invited",
                )
            )
        vendor.rfp_id = r.id
        return r

    if grouping == "per_section":
        for sec in in_scope:
            for v in selected:
                wanted = {display_csi(x) or x for x in (v.sections or [])}
                if wanted and (display_csi(sec.csi_code) or sec.csi_code) not in wanted:
                    continue
                company = db.session.get(Company, v.company_id)
                title = f"{sec.csi_code} {sec.title} — {(company.name if company else 'Vendor')}"
                created.append(_new_rfp(title, v, [sec]))
    else:
        for v in selected:
            wanted = {display_csi(x) or x for x in (v.sections or [])}
            secs = [s for s in in_scope if not wanted or (display_csi(s.csi_code) or s.csi_code) in wanted]
            if not secs:
                secs = in_scope
            company = db.session.get(Company, v.company_id)
            title = f"Spec package — {(company.name if company else 'Vendor')}"
            created.append(_new_rfp(title, v, secs))

    scan.status = "rfp_drafted"
    db.session.flush()
    _audit(cu, scan.id, "draft_rfp", {"rfp_ids": [str(r.id) for r in created], "count": len(created)})
    return created


def mention_public(m: EstimateSpecMention) -> dict[str, Any]:
    return {
        "id": str(m.id),
        "section_id": str(m.section_id),
        "mention_role": m.mention_role,
        "manufacturer": m.manufacturer,
        "product_line": m.product_line,
        "model_no": m.model_no,
        "finish_note": m.finish_note,
        "or_equal": bool(m.or_equal),
        "substitution_note": m.substitution_note,
        "page_cite": m.page_cite,
        "excerpt": m.excerpt,
        "material_pricing_id": str(m.material_pricing_id) if m.material_pricing_id else None,
        "configurator_key": m.configurator_key,
        "match_status": m.match_status,
        "confirmed": bool(m.confirmed),
        "product_snapshot": m.product_snapshot,
    }


def section_public(s: EstimateSpecSection, *, show_out_of_trade: bool = False) -> dict[str, Any] | None:
    if s.out_of_trade and not show_out_of_trade:
        return None
    mentions = list(s.mentions)
    mentions.sort(key=lambda m: (0 if m.mention_role == "basis_of_design" else 1, m.manufacturer or ""))
    conf = float(s.confidence) if s.confidence is not None else None
    if conf is not None:
        conf = round(conf, 1)
    return {
        "id": str(s.id),
        "csi_code": s.csi_code,
        "title": s.title,
        "in_scope": bool(s.in_scope),
        "out_of_trade": bool(s.out_of_trade),
        "shop_alternates": bool(s.shop_alternates),
        "confidence": conf,
        "document_id": str(s.document_id) if s.document_id else None,
        "page_start": s.page_start,
        "page_end": s.page_end,
        "pages": s.page_label,
        "estimator_notes": s.estimator_notes,
        "confirmed_at": s.confirmed_at.isoformat() if s.confirmed_at else None,
        "mentions": [mention_public(m) for m in mentions],
    }


def vendor_public(v: EstimateSpecVendor) -> dict[str, Any]:
    c = db.session.get(Company, v.company_id)
    return {
        "id": str(v.id),
        "company_id": str(v.company_id),
        "name": c.name if c is not None else "Vendor",
        "company_type": c.company_type if c is not None else None,
        "email": c.email if c is not None else None,
        "suggested_reason": v.suggested_reason,
        "selected": bool(v.selected),
        "rfp_id": str(v.rfp_id) if v.rfp_id else None,
        "sections": list(v.sections or []),
    }


def status_chip(status: str | None) -> str:
    return {
        None: "No scan",
        "": "No scan",
        "detecting": "No scan",
        "cancelled": "No scan",
        "review_sections": "Review sections",
        "extracting": "Review products",
        "review_products": "Review products",
        "vendors_ready": "Vendors ready",
        "rfp_drafted": "RFP drafted",
    }.get(status or "", status or "No scan")


def scan_public(scan: EstimateSpecScan | None, *, show_out_of_trade: bool = False, sources: dict[str, Any] | None = None) -> dict[str, Any]:
    if scan is None:
        return {
            "item": None,
            "status": None,
            "status_label": "No scan",
            "sources": sources or {},
            "sections": [],
            "vendors": [],
            "out_of_trade_count": 0,
        }
    sections = []
    hidden = 0
    for s in scan.sections:
        pub = section_public(s, show_out_of_trade=show_out_of_trade)
        if pub is None:
            hidden += 1
            continue
        sections.append(pub)
    rfp_ids = [str(v.rfp_id) for v in scan.vendors if v.rfp_id]
    return {
        "item": {
            "id": str(scan.id),
            "estimate_id": str(scan.estimate_id),
            "project_id": str(scan.project_id) if scan.project_id else None,
            "status": scan.status,
            "status_label": status_chip(scan.status),
            "provider": scan.provider,
            "model_version": scan.model_version,
            "progress_text": scan.progress_text,
            "error_text": scan.error_text,
            "started_at": scan.started_at.isoformat() if scan.started_at else None,
            "completed_at": scan.completed_at.isoformat() if scan.completed_at else None,
        },
        "status": scan.status,
        "status_label": status_chip(scan.status),
        "sources": sources or {},
        "sections": sections,
        "vendors": [vendor_public(v) for v in scan.vendors],
        "out_of_trade_count": hidden,
        "rfp_ids": rfp_ids,
        "warnings": [],
    }


def get_scan_payload(est: Estimate, *, show_out_of_trade: bool = False) -> dict[str, Any]:
    scan = latest_scan(est.id)
    if scan is not None:
        scan = _scan_with_children(scan.id) or scan
    return scan_public(scan, show_out_of_trade=show_out_of_trade, sources=sources_for_estimate(est))
