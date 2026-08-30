"""Merge company + project JSON into the Handlebars token context."""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Mapping


def _blank(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and not value.strip():
        return True
    return False


def format_address(addr: Mapping[str, Any] | None) -> str:
    a = addr or {}
    city_state = ", ".join(p for p in (str(a.get("city") or "").strip(), str(a.get("state") or "").strip()) if p)
    parts = [
        str(a.get("line1") or "").strip(),
        str(a.get("line2") or "").strip(),
        city_state,
        str(a.get("zip") or a.get("postal_code") or "").strip(),
    ]
    return ", ".join(p for p in parts if p)


def missing_fields(project: Mapping[str, Any] | None) -> list[str]:
    """Required fields that block Publish (tokens.md incomplete-field rule)."""
    p = project or {}
    miss: list[str] = []
    superint = p.get("superintendent") if isinstance(p.get("superintendent"), Mapping) else {}
    emergency = p.get("emergency") if isinstance(p.get("emergency"), Mapping) else {}
    hospital = emergency.get("hospital") if isinstance(emergency.get("hospital"), Mapping) else {}
    address = p.get("address") if isinstance(p.get("address"), Mapping) else {}
    if _blank(superint.get("name")):
        miss.append("superintendent.name")
    if _blank(superint.get("phone")):
        miss.append("superintendent.phone")
    if _blank(emergency.get("musterPoint")):
        miss.append("emergency.musterPoint")
    if _blank(hospital.get("name")):
        miss.append("emergency.hospital.name")
    if _blank(hospital.get("phone")):
        miss.append("emergency.hospital.phone")
    if _blank(emergency.get("whoCalls911")):
        miss.append("emergency.whoCalls911")
    if _blank(emergency.get("directionsFor911")):
        miss.append("emergency.directions911")
    if _blank(address.get("line1")) and _blank(address.get("city")):
        miss.append("project.address")
    return miss


def _yes_no(flag: Any) -> str:
    return "Yes" if bool(flag) else "No"


def _as_map(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def build_context(
    company: Mapping[str, Any] | None,
    project: Mapping[str, Any] | None,
    *,
    version: str | int = "0.1.0-draft",
    generated_at: datetime | None = None,
    title: str | None = None,
) -> dict[str, Any]:
    company = company or {}
    project = project or {}
    miss = missing_fields(project)
    now = generated_at or datetime.now(timezone.utc)
    start = project.get("startDate") or ""
    effective = str(start).strip()[:10] if start else now.date().isoformat()
    admin = _as_map(company.get("iippAdministrator"))
    phones = _as_map(company.get("phones"))
    addresses = _as_map(company.get("addresses"))
    climate_raw = _as_map(project.get("climate"))
    emergency = _as_map(project.get("emergency"))
    legal = str(company.get("legalName") or "").strip()
    dba = str(company.get("dba") or "").strip()
    display = f"{legal} dba {dba}".strip() if legal or dba else "—"
    if legal and not dba:
        display = legal
    ppe = project.get("ppeRequired") if isinstance(project.get("ppeRequired"), list) else []
    languages_co = company.get("languages") if isinstance(company.get("languages"), list) else []
    languages_pj = project.get("languagesOnSite") if isinstance(project.get("languagesOnSite"), list) else []
    cal = _as_map(company.get("calOsha"))
    review = _as_map(company.get("documentReview"))
    months = review.get("iippMonths") or 12
    return {
        "company": {
            "legalName": legal or "—",
            "dba": dba or "—",
            "shortName": company.get("shortName") or "DOCON",
            "displayName": display,
            "admin": admin,
            "phone": phones,
            "afterHoursPhone": company.get("afterHoursPhone") or "—",
            "address": {"block": format_address(_as_map(addresses.get("primary")))},
            "languages": " and ".join(str(x) for x in languages_co if x) or "English",
        },
        "project": {
            "name": project.get("projectName") or "—",
            "number": project.get("projectNumber") or "—",
            "client": project.get("clientName") or "—",
            "gc": project.get("gcName") or "—",
            "role": project.get("roleOnSite") or "—",
            "address": {
                "block": format_address(_as_map(project.get("address"))),
                "city": (_as_map(project.get("address")).get("city") or ""),
            },
            "accessNotes": project.get("accessNotes") or "—",
            "startDate": project.get("startDate") or "—",
            "endDate": project.get("endDate") or "—",
            "crewSize": project.get("crewSizeTypical") if project.get("crewSizeTypical") is not None else "—",
            "languages": ", ".join(str(x) for x in languages_pj if x),
            "superintendent": _as_map(project.get("superintendent")),
            "pm": _as_map(project.get("projectManager")),
            "ppeList": "\n".join(f"- {p}" for p in ppe if p),
            "gcRules": project.get("gcRulesStricter") or "—",
            "notes": project.get("notes") or "",
        },
        "emergency": {
            "muster": emergency.get("musterPoint"),
            "muster2": emergency.get("secondaryMuster") or "—",
            "who911": emergency.get("whoCalls911"),
            "whoCalOsha": emergency.get("whoCallsCalOsha") or admin.get("name"),
            "hospital": _as_map(emergency.get("hospital")),
            "clinic": _as_map(emergency.get("clinic")),
            "fire": emergency.get("fireDept") or "911",
            "police": emergency.get("police") or "911",
            "calOsha": _as_map(emergency.get("calOshaDistrictOffice")),
            "cellOk": "Yes" if emergency.get("cellCoverageReliable") else "No — use radio or runner",
            "radio": emergency.get("radioChannel") or "—",
            "directions911": emergency.get("directionsFor911"),
        },
        "climate": {
            "outdoor": _yes_no(climate_raw.get("outdoorWork")),
            "indoor": _yes_no(climate_raw.get("indoorWork")),
            "outdoorWork": bool(climate_raw.get("outdoorWork")),
            "indoorWork": bool(climate_raw.get("indoorWork")),
            "elevation": climate_raw.get("elevationFt") if climate_raw.get("elevationFt") is not None else "—",
            "heatRisk": climate_raw.get("heatRisk") or "—",
            "cold": _yes_no(climate_raw.get("coldIceSnow")),
            "smoke": _yes_no(climate_raw.get("wildfireSmokePossible")),
            "coldIceSnow": bool(climate_raw.get("coldIceSnow")),
            "wildfireSmokePossible": bool(climate_raw.get("wildfireSmokePossible")),
            "notes": climate_raw.get("notes") or "",
        },
        "scope": _as_map(project.get("scope")),
        "cp": _as_map(project.get("competentPersons")),
        "chemicals": list(project.get("chemicals") or []) if isinstance(project.get("chemicals"), list) else [],
        "calOsha": {"342Text": cal.get("seriousInjuryRule") or ""},
        "heat": {
            "shadeTrigger": "80°F",
            "highHeatTrigger": "95°F",
            "indoorTrigger": "82°F",
            "indoorControlTrigger": "87°F",
        },
        "doc": {
            "title": title or "",
            "version": str(version),
            "generatedAt": now.isoformat(),
            "effectiveDate": effective,
            "nextReview": f"{months} months from effective date (heat: each April)",
            "missingFields": ", ".join(miss),
        },
    }


def overlay_project_identity(payload: Mapping[str, Any] | None, project: Any) -> dict[str, Any]:
    """Copy authoritative Project columns into the safety payload for merge tokens."""
    out = dict(payload or {})
    if project is None:
        return out
    name = getattr(project, "name", None)
    number = getattr(project, "number", None)
    if name and not str(out.get("projectName") or "").strip():
        out["projectName"] = name
    if number and not str(out.get("projectNumber") or "").strip():
        out["projectNumber"] = number
    addr = dict(out.get("address") or {}) if isinstance(out.get("address"), Mapping) else {}
    line1 = getattr(project, "address_line1", None)
    city = getattr(project, "city", None)
    if line1 and not str(addr.get("line1") or "").strip():
        addr["line1"] = line1
    line2 = getattr(project, "address_line2", None)
    if line2 and not str(addr.get("line2") or "").strip():
        addr["line2"] = line2
    if city and not str(addr.get("city") or "").strip():
        addr["city"] = city
    state = getattr(project, "state", None)
    if state and not str(addr.get("state") or "").strip():
        addr["state"] = state
    postal = getattr(project, "postal_code", None)
    if postal and not str(addr.get("zip") or "").strip():
        addr["zip"] = postal
    if addr:
        out["address"] = addr
    start = getattr(project, "start_date", None)
    if start and not str(out.get("startDate") or "").strip():
        out["startDate"] = start.isoformat() if isinstance(start, date) else str(start)
    end = getattr(project, "substantial_completion_date", None)
    if end and not str(out.get("endDate") or "").strip():
        out["endDate"] = end.isoformat() if isinstance(end, date) else str(end)
    return out
