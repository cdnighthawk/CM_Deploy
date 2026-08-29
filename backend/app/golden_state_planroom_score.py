"""Rank Golden State planroom jobs against the USIS submitted-bid profile.

The weekly listing has name, county, and advertised construction estimate — not
trade, GC, or building sf. Scores therefore use the checklist signals we *can*
see: building type from the job name, CA market from location, and estimate as
a stand-in for a 20k–120k sf school / civic / healthcare job.

Source: submitted BuildingConnected lead_estimates, 28 Aug 2026 (709 invites).
"""
from __future__ import annotations

import re
from decimal import Decimal
from typing import Any

_WORD = r"(?:^|[^a-z0-9])(?:{pat})(?:[^a-z0-9]|$)"


def _compile(patterns: tuple[str, ...]) -> re.Pattern[str]:
    return re.compile("|".join(_WORD.format(pat=p) for p in patterns), re.I)


# Warehouse before infra so a Costco depot is not scored like a sewer or bridge.
_BUILDING_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "warehouse",
        _compile(
            (
                r"warehouse",
                r"distribution\s+center",
                r"distribution\s+facility",
                r"fulfillment",
                r"cold\s+storage",
                r"logistics",
                r"\bdepot\b",
                r"costco",
                r"industrial\s+(?:park|building|warehouse|facility|center)",
            )
        ),
    ),
    (
        "infra",
        _compile(
            (
                r"sewer",
                r"waste\s*water",
                r"water\s+treatment",
                r"water\s+reclamation",
                r"water\s+main",
                r"pipeline",
                r"pump\s+station",
                r"reservoir",
                r"storm\s+drain",
                r"flood\s+control",
                r"levee",
                r"bridge",
                r"highway",
                r"freeway",
                r"interchange",
                r"asphalt",
                r"street\s+rehab",
                r"street\s+improvement",
                r"roadway",
                r"railroad",
                r"railway",
                r"double\s+track",
                r"light\s+rail",
                r"rail\s+trail",
                r"\brail\b",
                r"transit\s+center",
                r"substation",
                r"landfill",
                r"paving",
                r"overlay",
                r"culvert",
                r"widening",
            )
        ),
    ),
    ("aviation", _compile((r"airport", r"concourse", r"hangar", r"airfield", r"runway"))),
    (
        "healthcare",
        _compile(
            (
                r"hospital",
                r"medical\s+center",
                r"health\s+center",
                r"clinic",
                r"urgent\s+care",
                r"surgery",
                r"behavioral\s+health",
                r"nursing",
                r"patient\s+tower",
            )
        ),
    ),
    (
        "k12",
        _compile(
            (
                r"elementary",
                r"middle\s+school",
                r"high\s+school",
                r"k-?8",
                r"k-?12",
                r"unified\s+school",
                r"school\s+district",
                r"\busd\b",
                r"kindergarten",
                r"preschool",
                r"classroom",
                r"grade\s+school",
                r"\bhs\b",
                r"\bes\b",
            )
        ),
    ),
    (
        "higher_ed",
        _compile(
            (
                r"university",
                r"community\s+college",
                r"\bcollege\b",
                r"\buc\b",
                r"\bcsu\b",
                r"campus",
            )
        ),
    ),
    (
        "civic",
        _compile(
            (
                r"fire\s+station",
                r"fire[- ]?ems",
                r"fire\s+dept",
                r"police",
                r"sheriff",
                r"library",
                r"city\s+hall",
                r"civic\s+center",
                r"municipal",
                r"courthouse",
                r"community\s+center",
                r"animal\s+shelter",
                r"public\s+safety",
            )
        ),
    ),
    (
        "federal",
        _compile(
            (
                r"navy",
                r"army",
                r"marine\s+corps",
                r"air\s+force",
                r"veterans",
                r"\bva\b",
                r"federal",
                r"barracks",
                r"camp\s+pendleton",
                r"nmc",
                r"naval",
            )
        ),
    ),
    ("lab", _compile((r"laborator(?:y|ies)", r"research\s+center", r"\blab\b"))),
    (
        "arts",
        _compile((r"museum", r"theat(?:er|re)", r"performing\s+arts", r"gallery", r"concert")),
    ),
    (
        "recreation",
        _compile(
            (
                r"gymnasium",
                r"aquatics",
                r"recreation",
                r"stadium",
                r"athletic",
                r"golf",
                r"\bpool\b",
                r"\bpark\b",
            )
        ),
    ),
    ("hospitality", _compile((r"hotel", r"resort", r"hospitality"))),
    ("housing", _compile((r"apartment", r"housing", r"residence\s+hall", r"dormitor", r"senior\s+living"))),
    ("retail", _compile((r"retail", r"shopping", r"storefront"))),
    ("office", _compile((r"office\s+building", r"office\s+park", r"corporate\s+headquarters"))),
)

_BUILDING_LABELS = {
    "k12": "K-12",
    "higher_ed": "Higher education",
    "civic": "Civic / public safety",
    "healthcare": "Healthcare",
    "federal": "Federal / military",
    "lab": "Lab / research",
    "arts": "Arts / cultural",
    "recreation": "Recreation / athletic",
    "housing": "Housing",
    "hospitality": "Hospitality",
    "aviation": "Aviation",
    "retail": "Retail",
    "office": "Office",
    "warehouse": "Warehouse / distribution",
    "infra": "Infra / civil",
    "unknown": "Unclassified",
}

# Checklist: strong yes / soft / almost never.
_BUILDING_POINTS = {
    "k12": 45,
    "higher_ed": 45,
    "civic": 45,
    "healthcare": 45,
    "warehouse": 45,
    "federal": 22,
    "lab": 22,
    "arts": 22,
    "recreation": 22,
    "housing": 22,
    "hospitality": 12,
    "aviation": 12,
    "retail": 12,
    "office": 6,
    "infra": 0,
    "unknown": 18,
}

_STRONG_PLACES = {
    "san diego",
    "los angeles",
    "orange",
    "riverside",
    "san bernardino",
    "sacramento",
    "alameda",
    "santa clara",
    "san francisco",
    "contra costa",
    "san mateo",
    "marin",
}
_SOFT_PLACES = {
    "imperial",
    "ventura",
    "santa barbara",
    "kern",
    "fresno",
    "san joaquin",
    "stanislaus",
    "monterey",
    "sonoma",
}

_SCOPE_STRONG = _compile(
    (
        r"restroom",
        r"toilet",
        r"locker",
        r"partition",
        r"specialt",
        r"signage",
        r"tackboard",
        r"markerboard",
        r"visual\s+display",
        r"wall\s+protection",
        r"fire\s+extinguisher",
    )
)
_SCOPE_SOFT = _compile((r"modernization", r"renovation", r"remodel", r"interior", r"classroom"))

_STRONG_MIN = 70
_POSSIBLE_MIN = 45


def classify_building(name: str | None) -> str:
    text = (name or "").strip()
    if not text:
        return "unknown"
    for label, pattern in _BUILDING_RULES:
        if pattern.search(text):
            return label
    return "unknown"


def _place_key(location: str | None) -> str:
    return re.sub(r"\s+", " ", (location or "").strip().lower())


def _place_points(location: str | None) -> tuple[int, str]:
    key = _place_key(location)
    if not key:
        return 12, "Location blank — do not treat as a no"
    if key in _STRONG_PLACES or any(key.startswith(p) for p in _STRONG_PLACES):
        return 25, f"{location.strip()} — CA home market"
    if key in _SOFT_PLACES or any(key.startswith(p) for p in _SOFT_PLACES):
        return 15, f"{location.strip()} — other CA (softer)"
    return 15, f"{location.strip()} — California listing"


def _estimate_number(value: Any) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, Decimal):
        n = float(value)
    else:
        try:
            n = float(value)
        except (TypeError, ValueError):
            return None
    if n <= 0:
        return None
    return n


def _estimate_points(value: Any) -> tuple[int, str]:
    n = _estimate_number(value)
    if n is None:
        return 10, "Estimate unknown — common on this listing"
    pretty = f"${n:,.0f}"
    # Advertised construction total, not the USIS bid. $8–80M ≈ 20k–120k sf civic/school.
    if 8_000_000 <= n <= 80_000_000:
        return 20, f"Estimate {pretty} — typical school / civic size"
    if 3_000_000 <= n < 8_000_000 or 80_000_000 < n <= 150_000_000:
        return 12, f"Estimate {pretty} — soft size band"
    if 1_000_000 <= n < 3_000_000 or 150_000_000 < n <= 300_000_000:
        return 6, f"Estimate {pretty} — outside the usual package size"
    return 2, f"Estimate {pretty} — rarely a Division 10 package"


_SCOPE_BUILDINGS = {"k12", "higher_ed", "civic", "healthcare", "warehouse"}


def _scope_points(name: str | None, building: str) -> tuple[int, str | None]:
    text = name or ""
    if _SCOPE_STRONG.search(text):
        return 10, "Name mentions a Division 10 scope"
    if building in _SCOPE_BUILDINGS and _SCOPE_SOFT.search(text):
        return 5, "Modernization / interiors — often a specialties package"
    return 0, None


def _band(score: int) -> str:
    if score >= _STRONG_MIN:
        return "strong"
    if score >= _POSSIBLE_MIN:
        return "possible"
    return "weak"


def score_planroom_lead(
    *,
    name: str | None,
    location: str | None = None,
    estimate_high: Any = None,
) -> dict[str, Any]:
    building = classify_building(name)
    b_pts = _BUILDING_POINTS[building]
    p_pts, p_reason = _place_points(location)
    e_pts, e_reason = _estimate_points(estimate_high)
    s_pts, s_reason = _scope_points(name, building)
    score = min(100, b_pts + p_pts + e_pts + s_pts)
    reasons = [
        f"{_BUILDING_LABELS[building]} — "
        + (
            "core building type"
            if b_pts >= 45
            else "soft / less common"
            if b_pts >= 12
            else "almost never a USIS bid"
            if building == "infra"
            else "name did not classify cleanly"
        ),
        p_reason,
        e_reason,
    ]
    if s_reason:
        reasons.append(s_reason)
    return {
        "score": score,
        "band": _band(score),
        "building": _BUILDING_LABELS[building],
        "building_key": building,
        "reasons": reasons,
    }


def sort_key_fit(item: dict[str, Any]) -> tuple[int, str, str]:
    fit = item.get("fit") or {}
    score = int(fit.get("score") or 0)
    bid = str(item.get("bid_date") or "9999-99-99")
    name = str(item.get("name") or "")
    return (-score, bid, name)
