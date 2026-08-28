"""Company office origin used by the leads distance filter."""
from __future__ import annotations

import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from decimal import Decimal
from typing import Any, Mapping

from flask import Blueprint
from sqlalchemy import select

from ..extensions import db
from ..models import AuditLog, Company
from ._perms import current_user, is_company_readonly

log = logging.getLogger(__name__)

CENSUS_GEOCODER = "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress"
USER_AGENT = "USIS-CM/1.0 (leads-office-geocode)"


class OfficeLocationError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message = message
        self.status = status


def _jsonify(obj: Any):
    from flask import jsonify

    return jsonify(obj)


def _num(v: Any) -> float | None:
    if v is None or v == "":
        return None
    try:
        n = float(v)
    except (TypeError, ValueError):
        return None
    if n != n:  # NaN
        return None
    return n


def parse_lat_lng(lat_raw: Any, lng_raw: Any) -> tuple[float, float] | None:
    lat = _num(lat_raw)
    lng = _num(lng_raw)
    if lat is None or lng is None:
        return None
    if not (-90.0 <= lat <= 90.0 and -180.0 <= lng <= 180.0):
        return None
    return (lat, lng)


def company_coords(row: Company | None) -> tuple[float, float] | None:
    if row is None:
        return None
    return parse_lat_lng(row.latitude, row.longitude)


def select_self_company() -> Company | None:
    cid = db.session.scalar(
        select(Company.id)
        .where(Company.company_type == "self", Company.deleted_at.is_(None))
        .order_by(Company.created_at.asc())
        .limit(1)
    )
    if cid is None:
        return None
    return db.session.get(Company, cid)


def resolve_office_origin() -> tuple[float, float] | None:
    return company_coords(select_self_company())


def office_label(row: Company | None) -> str:
    if row is None:
        return ""
    city_bits = [x.strip() for x in (row.city, row.state) if x and str(x).strip()]
    if city_bits:
        return ", ".join(city_bits)
    if row.postal_code and str(row.postal_code).strip():
        return str(row.postal_code).strip()
    if row.address_line1 and str(row.address_line1).strip():
        return str(row.address_line1).strip()
    return (row.name or "").strip()


def address_line(row: Company | None) -> str:
    if row is None:
        return ""
    parts = [
        x.strip()
        for x in (row.address_line1, row.address_line2, row.city, row.state, row.postal_code)
        if x and str(x).strip()
    ]
    return ", ".join(parts)


def office_public(row: Company | None) -> dict[str, Any]:
    coords = company_coords(row)
    return {
        "configured": coords is not None,
        "name": (row.name or "").strip() if row else "",
        "label": office_label(row),
        "address_line1": (row.address_line1 or "").strip() if row else "",
        "address_line2": (row.address_line2 or "").strip() if row else "",
        "city": (row.city or "").strip() if row else "",
        "state": (row.state or "").strip() if row else "",
        "postal_code": (row.postal_code or "").strip() if row else "",
        "latitude": coords[0] if coords else None,
        "longitude": coords[1] if coords else None,
    }


def geocode_us_address(query: str) -> tuple[float, float] | None:
    """US Census geocoder. Returns (lat, lng) or None. Safe to monkeypatch in tests."""
    q = (query or "").strip()
    if not q:
        return None
    params = urllib.parse.urlencode(
        {
            "address": q,
            "benchmark": "Public_AR_Current",
            "vintage": "Current_Current",
            "format": "json",
        }
    )
    req = urllib.request.Request(
        f"{CENSUS_GEOCODER}?{params}",
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        log.warning("office geocode failed for %r: %s", q, exc)
        return None
    matches = (
        payload.get("result", {}).get("addressMatches")
        if isinstance(payload, Mapping)
        else None
    )
    if not isinstance(matches, list) or not matches:
        return None
    first = matches[0] if isinstance(matches[0], Mapping) else None
    coords = first.get("coordinates") if first else None
    if not isinstance(coords, Mapping):
        return None
    # Census uses x=lng, y=lat
    return parse_lat_lng(coords.get("y"), coords.get("x"))


def _clean_text(raw: Any, limit: int) -> str | None:
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    return text[:limit]


def _set_if_provided(row: Company, field: str, raw: Any, limit: int) -> None:
    if raw is None:
        return
    setattr(row, field, _clean_text(raw, limit))


def _geocode_row(row: Company) -> tuple[float, float] | None:
    line = address_line(row)
    if not line:
        return None
    return geocode_us_address(line)


def upsert_office_location(data: Mapping[str, Any]) -> dict[str, Any]:
    row = select_self_company()
    created = False
    if row is None:
        name = _clean_text(data.get("name"), 255) or "US Interior Specialties"
        row = Company(name=name, company_type="self", country="US")
        db.session.add(row)
        created = True

    _set_if_provided(row, "name", data.get("name"), 255)
    _set_if_provided(row, "address_line1", data.get("address_line1"), 255)
    _set_if_provided(row, "address_line2", data.get("address_line2"), 255)
    _set_if_provided(row, "city", data.get("city"), 120)
    state = _clean_text(data.get("state"), 50) if data.get("state") is not None else None
    if state is not None:
        row.state = state.upper() if len(state) <= 2 else state
    _set_if_provided(row, "postal_code", data.get("postal_code") or data.get("zip"), 20)

    explicit = parse_lat_lng(data.get("latitude"), data.get("longitude"))
    if explicit:
        row.latitude = Decimal(str(round(explicit[0], 6)))
        row.longitude = Decimal(str(round(explicit[1], 6)))
    elif company_coords(row) is None or any(
        k in data for k in ("address_line1", "city", "state", "postal_code", "zip")
    ):
        found = _geocode_row(row)
        if found is None:
            raise OfficeLocationError(
                "Could not map that office address. Try a street address or ZIP in the United States.",
                422,
            )
        row.latitude = Decimal(str(round(found[0], 6)))
        row.longitude = Decimal(str(round(found[1], 6)))

    if company_coords(row) is None:
        raise OfficeLocationError("office location needs a city, ZIP, or coordinates", 400)

    db.session.flush()
    cu = current_user()
    if cu.user is not None:
        db.session.add(
            AuditLog(
                user_id=cu.user.id if cu.user else None,
                entity_type="company",
                entity_id=row.id,
                action="office_location.upsert",
                changes={"created": created, "label": office_label(row)},
                message=f"Updated office location ({office_label(row) or row.name})",
            )
        )
    db.session.commit()
    return office_public(row)


def register_office_location_routes(bp: Blueprint) -> None:
    @bp.get("/office-location")
    def get_office_location_route():
        return _jsonify(office_public(select_self_company()))

    @bp.patch("/office-location")
    def patch_office_location_route():
        from flask import request

        cu = current_user()
        if is_company_readonly(cu) and not cu.is_dev_admin:
            return _jsonify({"error": "read-only role cannot update office location"}), 403
        data = request.get_json(silent=True) or {}
        if not isinstance(data, Mapping):
            return _jsonify({"error": "JSON object required"}), 400
        try:
            return _jsonify(upsert_office_location(data))
        except OfficeLocationError as exc:
            return _jsonify({"error": exc.message}), exc.status
