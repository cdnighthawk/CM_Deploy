"""CPU first-pass: does the GC want this bid broken down by floor, area, or building?"""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Any, Iterable

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from ..extensions import db
from ..models import Document, Drawing, Estimate, EstimateBidScope, LeadEstimate, Location, Rfp, SpecSection
from ._rfi_service import ApiError

REQ_REQUIRED = "required"
REQ_NOT_FOUND = "not_found"
REQ_UNCLEAR = "unclear"

_GRAIN_FLOOR = "floor"
_GRAIN_AREA = "area"
_GRAIN_BUILDING = "building"
_GRAIN_MIXED = "mixed"
_GRAIN_NONE = "none"

_STRONG: tuple[tuple[str, str], ...] = (
    ("bid by floor", _GRAIN_FLOOR),
    ("bid per floor", _GRAIN_FLOOR),
    ("per floor bid", _GRAIN_FLOOR),
    ("floor by floor", _GRAIN_FLOOR),
    ("floor-by-floor", _GRAIN_FLOOR),
    ("breakdown by floor", _GRAIN_FLOOR),
    ("breakout by floor", _GRAIN_FLOOR),
    ("break out by floor", _GRAIN_FLOOR),
    ("separate price per floor", _GRAIN_FLOOR),
    ("price each floor", _GRAIN_FLOOR),
    ("prices by floor", _GRAIN_FLOOR),
    ("unit price per floor", _GRAIN_FLOOR),
    ("sov by floor", _GRAIN_FLOOR),
    ("schedule of values by floor", _GRAIN_FLOOR),
    ("bid each floor", _GRAIN_FLOOR),
    ("bid by level", _GRAIN_FLOOR),
    ("bid per level", _GRAIN_FLOOR),
    ("breakdown by level", _GRAIN_FLOOR),
    ("bid by building", _GRAIN_BUILDING),
    ("bid per building", _GRAIN_BUILDING),
    ("per building bid", _GRAIN_BUILDING),
    ("building by building", _GRAIN_BUILDING),
    ("building-by-building", _GRAIN_BUILDING),
    ("breakdown by building", _GRAIN_BUILDING),
    ("breakout by building", _GRAIN_BUILDING),
    ("separate price per building", _GRAIN_BUILDING),
    ("sov by building", _GRAIN_BUILDING),
    ("bid by area", _GRAIN_AREA),
    ("bid per area", _GRAIN_AREA),
    ("per area bid", _GRAIN_AREA),
    ("breakdown by area", _GRAIN_AREA),
    ("breakout by area", _GRAIN_AREA),
    ("separate price per area", _GRAIN_AREA),
    ("bid by wing", _GRAIN_AREA),
    ("breakdown by wing", _GRAIN_AREA),
)

_WEAK_NEAR = ("bid", "price", "pricing", "breakdown", "breakout", "sov", "schedule of values", "proposal")
_WEAK: tuple[tuple[str, str], ...] = (
    ("per floor", _GRAIN_FLOOR),
    ("by floor", _GRAIN_FLOOR),
    ("each floor", _GRAIN_FLOOR),
    ("per level", _GRAIN_FLOOR),
    ("by building", _GRAIN_BUILDING),
    ("per building", _GRAIN_BUILDING),
    ("each building", _GRAIN_BUILDING),
    ("per area", _GRAIN_AREA),
    ("by area", _GRAIN_AREA),
)

_BID_DOC_HINTS = (
    "invitation to bid",
    "instructions to bidders",
    "instruction to bidders",
    "bid form",
    "bid package",
    "bid invitation",
    "addendum",
    "addenda",
    "proposal form",
    "pricing sheet",
    "schedule of values",
    " itb ",
    "itb-",
    "itb_",
)

_FLOOR_ORD = {
    "1": "Level 1",
    "2": "Level 2",
    "3": "Level 3",
    "4": "Level 4",
    "5": "Level 5",
    "6": "Level 6",
    "7": "Level 7",
    "8": "Level 8",
    "9": "Level 9",
    "10": "Level 10",
    "11": "Level 11",
    "12": "Level 12",
    "one": "Level 1",
    "two": "Level 2",
    "three": "Level 3",
    "four": "Level 4",
    "five": "Level 5",
    "first": "Level 1",
    "second": "Level 2",
    "third": "Level 3",
    "fourth": "Level 4",
    "fifth": "Level 5",
    "ground": "Level 1",
}

_FLOOR_NAMED = {
    "basement": "Basement",
    "mezzanine": "Mezzanine",
    "penthouse": "Penthouse",
}

_FLOOR_RE = re.compile(
    r"\b(?:level|lvl|floor|flr)\s*[-.]?\s*(ground|[0-9]{1,2}|one|two|three|four|five|first|second|third|fourth|fifth)\b",
    re.IGNORECASE,
)
_ORDINAL_FLOOR_RE = re.compile(
    r"\b(first|second|third|fourth|fifth|ground)\s+floor\b",
    re.IGNORECASE,
)
_BUILDING_RE = re.compile(r"\b(?:building|bldg\.?|bld\.?|tower)\s+([a-z0-9]{1,8})\b", re.IGNORECASE)
_AREA_RE = re.compile(r"\b(?:area|wing|zone)\s+([a-z0-9]{1,12})\b", re.IGNORECASE)
_SKIP_PLACE = frozenset(
    {"section", "elevation", "plan", "detail", "type", "of", "the", "and", "for", "to"}
)


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


def _norm(raw: str | None) -> str:
    return " " + " ".join(str(raw or "").replace("_", " ").replace("-", " ").lower().split()) + " "


def _flatten_json(val: Any, limit: int = 12) -> list[str]:
    out: list[str] = []

    def walk(node: Any) -> None:
        if len(out) >= limit:
            return
        if isinstance(node, str) and node.strip():
            out.append(node.strip())
        elif isinstance(node, dict):
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node[:20]:
                walk(v)

    walk(val)
    return out


def looks_like_bid_doc(title: str | None, filename: str | None = None) -> bool:
    blob = _norm(f"{title or ''} {filename or ''}")
    return any(h in blob for h in _BID_DOC_HINTS)


def detect_requirement(texts: Iterable[tuple[str, str]]) -> dict[str, Any]:
    """``texts`` is (source, raw_text). Strong phrase wins over weak."""
    evidence: list[dict[str, str]] = []
    grains: set[str] = set()
    for source, raw in texts:
        blob = _norm(raw)
        if blob.strip() == "":
            continue
        hit = False
        for phrase, grain in _STRONG:
            if phrase in blob:
                grains.add(grain)
                evidence.append({"source": source, "phrase": phrase, "snippet": str(raw).strip()[:240]})
                hit = True
        if hit:
            continue
        if any(w in blob for w in _WEAK_NEAR):
            for phrase, grain in _WEAK:
                if phrase in blob:
                    grains.add(grain)
                    evidence.append({"source": source, "phrase": phrase, "snippet": str(raw).strip()[:240]})
    if not evidence:
        return {"requirement": REQ_NOT_FOUND, "grain": _GRAIN_NONE, "evidence": []}
    grain = next(iter(grains)) if len(grains) == 1 else _GRAIN_MIXED
    return {"requirement": REQ_REQUIRED, "grain": grain, "evidence": evidence[:12]}


def extract_locations(texts: Iterable[tuple[str, str]]) -> list[dict[str, str]]:
    found: dict[tuple[str, str], dict[str, str]] = {}
    for source, raw in texts:
        blob = str(raw or "")
        for m in _FLOOR_RE.finditer(blob):
            key = _FLOOR_ORD.get(m.group(1).lower())
            if key:
                found[(_GRAIN_FLOOR, key)] = {"kind": _GRAIN_FLOOR, "label": key, "source": source}
        for m in _ORDINAL_FLOOR_RE.finditer(blob):
            key = _FLOOR_ORD.get(m.group(1).lower())
            if key:
                found[(_GRAIN_FLOOR, key)] = {"kind": _GRAIN_FLOOR, "label": key, "source": source}
        low = blob.lower()
        for token, label in _FLOOR_NAMED.items():
            if token in low:
                found[(_GRAIN_FLOOR, label)] = {"kind": _GRAIN_FLOOR, "label": label, "source": source}
        for m in _BUILDING_RE.finditer(blob):
            token = m.group(1).lower()
            if token in _SKIP_PLACE:
                continue
            label = f"Building {m.group(1).upper()}"
            found[(_GRAIN_BUILDING, label)] = {"kind": _GRAIN_BUILDING, "label": label, "source": source}
        for m in _AREA_RE.finditer(blob):
            token = m.group(1).lower()
            if token in _SKIP_PLACE:
                continue
            label = f"Area {m.group(1).upper()}"
            found[(_GRAIN_AREA, label)] = {"kind": _GRAIN_AREA, "label": label, "source": source}
    return sorted(found.values(), key=lambda x: (x["kind"], x["label"]))


def classify_bid_locations(
    texts: list[tuple[str, str]],
    *,
    bid_doc_count: int = 0,
    catalog_locations: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    req = detect_requirement(texts)
    locations = extract_locations(texts)
    catalog = catalog_locations or []
    seen = {(x["kind"], x["label"]) for x in locations}
    for loc in catalog:
        key = (loc.get("kind") or "area", loc.get("label") or "")
        if key[1] and key not in seen:
            locations.append({"kind": key[0], "label": key[1], "source": loc.get("source") or "project_locations"})
            seen.add(key)

    kinds = {x["kind"] for x in locations}
    requirement = req["requirement"]
    grain = req["grain"]
    if grain == _GRAIN_NONE and len(kinds) == 1:
        grain = next(iter(kinds))
    elif grain == _GRAIN_NONE and len(kinds) > 1:
        grain = _GRAIN_MIXED

    needs_ai = False
    reason = "no bid-by-location language in titles or notes"
    if requirement == REQ_REQUIRED and not locations:
        needs_ai = True
        reason = "bid docs ask for a location breakdown, but no floors/areas/buildings were named"
    elif requirement == REQ_NOT_FOUND and bid_doc_count:
        requirement = REQ_UNCLEAR
        needs_ai = True
        reason = "bid-looking files are present; CPU only read titles — open them if a location breakdown is required"
    elif requirement == REQ_NOT_FOUND and len(locations) >= 2:
        requirement = REQ_UNCLEAR
        needs_ai = True
        reason = "drawings name multiple locations, but no bid instruction to break the price that way"
    elif requirement == REQ_REQUIRED:
        reason = "bid instruction asks for a location breakdown"

    return {
        "requirement": requirement,
        "grain": grain,
        "locations": locations,
        "evidence": req["evidence"],
        "bidDocCount": bid_doc_count,
        "needsAi": needs_ai,
        "reason": reason,
        "classifiedBy": "cpu",
        "classifiedAt": _utcnow().isoformat(),
    }


def bid_location_public(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict) or not raw:
        return None
    return {
        "requirement": raw.get("requirement"),
        "grain": raw.get("grain"),
        "locations": raw.get("locations") or [],
        "evidence": raw.get("evidence") or [],
        "bidDocCount": raw.get("bidDocCount") or 0,
        "needsAi": bool(raw.get("needsAi")),
        "reason": raw.get("reason"),
        "classifiedBy": raw.get("classifiedBy") or "cpu",
    }


def _lead_texts(lead: LeadEstimate | None) -> list[tuple[str, str]]:
    if lead is None:
        return []
    blobs = [
        ("lead.name", lead.name or ""),
        ("lead.project_information", lead.project_information or ""),
        ("lead.trade_specific_instructions", lead.trade_specific_instructions or ""),
    ]
    for i, chunk in enumerate(_flatten_json(lead.additional_info)):
        blobs.append((f"lead.additional_info.{i}", chunk))
    for i, chunk in enumerate(_flatten_json(lead.bid)):
        blobs.append((f"lead.bid.{i}", chunk))
    return blobs


def collect_estimate_texts(est: Estimate) -> tuple[list[tuple[str, str]], int, list[dict[str, str]]]:
    texts: list[tuple[str, str]] = [
        ("estimate.name", est.name or ""),
        ("estimate.notes", est.notes or ""),
        ("estimate.title", est.title or ""),
    ]
    bid_docs = 0
    catalog: list[dict[str, str]] = []

    if est.lead_estimate_id:
        lead = db.session.get(LeadEstimate, est.lead_estimate_id)
        texts.extend(_lead_texts(lead))

    scope = db.session.scalar(select(EstimateBidScope).where(EstimateBidScope.estimate_id == est.id))
    if scope is not None:
        texts.append(("bid_scope.package", scope.bid_package_label or ""))
        texts.append(("bid_scope.notes", scope.notes or ""))

    pid = est.project_id
    if pid is None:
        return texts, bid_docs, catalog

    drawings = db.session.scalars(select(Drawing).where(Drawing.project_id == pid)).all()
    for d in drawings:
        texts.append(("drawing.title", " ".join(x for x in (d.sheet_number, d.sheet_title or d.title) if x)))

    docs = db.session.scalars(select(Document).where(Document.project_id == pid)).all()
    for doc in docs:
        if getattr(doc, "document_type", None) == "drawing":
            continue
        title = " ".join(x for x in (doc.title, doc.original_filename, doc.description) if x)
        texts.append(("document", title))
        if looks_like_bid_doc(doc.title, doc.original_filename):
            bid_docs += 1

    specs = db.session.scalars(select(SpecSection).where(SpecSection.project_id == pid)).all()
    for spec in specs:
        texts.append(("spec", f"{spec.code} {spec.title}"))

    rfps = db.session.scalars(
        select(Rfp).options(selectinload(Rfp.line_items)).where(Rfp.project_id == pid)
    ).all()
    for rfp in rfps:
        texts.append(("rfp.title", rfp.title or ""))
        if looks_like_bid_doc(rfp.title):
            bid_docs += 1
        for line in rfp.line_items or []:
            texts.append(("rfp.line", f"{line.description} {line.notes or ''}"))

    locs = db.session.scalars(
        select(Location).where(Location.project_id == pid, Location.is_active.is_(True))
    ).all()
    for loc in locs:
        catalog.append({"kind": "area", "label": loc.name, "source": "project_locations"})
        texts.append(("project_location", f"{loc.path} {loc.name}"))

    return texts, bid_docs, catalog


def apply_estimate_bid_locations(est: Estimate) -> dict[str, Any]:
    texts, bid_docs, catalog = collect_estimate_texts(est)
    result = classify_bid_locations(texts, bid_doc_count=bid_docs, catalog_locations=catalog)
    est.bid_location = result
    return result


def run_estimate_bid_locations(estimate_id: uuid.UUID) -> dict[str, Any]:
    est = db.session.get(Estimate, estimate_id)
    if est is None:
        raise ApiError("estimate not found", 404)
    result = apply_estimate_bid_locations(est)
    db.session.flush()
    return {"entity": "bid_location", "estimateId": str(est.id), **bid_location_public(result)}
