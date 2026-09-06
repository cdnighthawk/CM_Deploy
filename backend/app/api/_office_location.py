"""Company office origin used by the leads distance filter, plus named offices for ship-to."""
from __future__ import annotations

import json
import logging
import urllib.error
import urllib.parse
import urllib.request
import uuid
from decimal import Decimal
from typing import Any, Mapping

from flask import Blueprint
from sqlalchemy import select

from ..extensions import db
from ..models import AuditLog, Company, CompanyOffice, Project
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


def viewer_office_row(company: Company | None = None) -> CompanyOffice | None:
    """Office the signed-in user belongs to, else the company default."""
    company = company or select_self_company()
    user = current_user().user
    oid = getattr(user, "office_id", None) if user is not None else None
    if oid is not None:
        row = db.session.get(CompanyOffice, oid)
        if row is not None:
            return row
    return default_office_row(company)


def viewer_office_source(office: CompanyOffice | None) -> str:
    user = current_user().user
    if office is not None and user is not None and getattr(user, "office_id", None) == office.id:
        return "user"
    return "default"


def resolve_office_origin() -> tuple[float, float] | None:
    office = viewer_office_row()
    if office is not None:
        coords = parse_lat_lng(office.latitude, office.longitude)
        if coords:
            return coords
    return company_coords(select_self_company())


def office_origin_public() -> dict[str, Any] | None:
    office = viewer_office_row()
    origin = resolve_office_origin()
    if origin is None and office is None:
        return None
    company = select_self_company()
    return {
        "id": str(office.id) if office is not None else None,
        "label": office_row_label(office) if office is not None else office_label(company),
        "latitude": origin[0] if origin else None,
        "longitude": origin[1] if origin else None,
        "source": viewer_office_source(office),
    }


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
    _sync_default_office_from_company(row)
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


def format_us_address(
    *,
    address_line1: str | None = None,
    address_line2: str | None = None,
    city: str | None = None,
    state: str | None = None,
    postal_code: str | None = None,
    country: str | None = None,
) -> str:
    street = ", ".join(x.strip() for x in (address_line1, address_line2) if x and str(x).strip())
    city_state = " ".join(
        p
        for p in (
            (city or "").strip(),
            " ".join(x for x in ((state or "").strip(), (postal_code or "").strip()) if x).strip(),
        )
        if p
    )
    parts = [p for p in (street, city_state) if p]
    country_s = (country or "").strip().upper()
    if country_s and country_s not in ("US", "USA", "UNITED STATES"):
        parts.append(country_s)
    return ", ".join(parts)


def _addr_from_obj(row: Any) -> str:
    if row is None:
        return ""
    return format_us_address(
        address_line1=getattr(row, "address_line1", None),
        address_line2=getattr(row, "address_line2", None),
        city=getattr(row, "city", None),
        state=getattr(row, "state", None),
        postal_code=getattr(row, "postal_code", None),
        country=getattr(row, "country", None),
    )


def office_row_label(row: CompanyOffice | None) -> str:
    if row is None:
        return ""
    if (row.name or "").strip():
        return row.name.strip()
    city_bits = [x.strip() for x in (row.city, row.state) if x and str(x).strip()]
    if city_bits:
        return ", ".join(city_bits)
    return _addr_from_obj(row) or "Office"


def office_row_public(row: CompanyOffice) -> dict[str, Any]:
    coords = parse_lat_lng(row.latitude, row.longitude)
    return {
        "id": str(row.id),
        "name": (row.name or "").strip() or "Office",
        "label": office_row_label(row),
        "address": _addr_from_obj(row),
        "address_line1": (row.address_line1 or "").strip(),
        "address_line2": (row.address_line2 or "").strip(),
        "city": (row.city or "").strip(),
        "state": (row.state or "").strip(),
        "postal_code": (row.postal_code or "").strip(),
        "country": (row.country or "US").strip() or "US",
        "is_default": bool(row.is_default),
        "sort_order": int(row.sort_order or 0),
        "configured": coords is not None,
        "latitude": coords[0] if coords else None,
        "longitude": coords[1] if coords else None,
        "notes": (row.notes or "").strip() or None,
    }


def list_office_rows(company: Company | None = None) -> list[CompanyOffice]:
    company = company or select_self_company()
    if company is None:
        return []
    return list(
        db.session.scalars(
            select(CompanyOffice)
            .where(CompanyOffice.company_id == company.id)
            .order_by(CompanyOffice.sort_order.asc(), CompanyOffice.created_at.asc())
        ).all()
    )


def default_office_row(company: Company | None = None) -> CompanyOffice | None:
    rows = list_office_rows(company)
    for row in rows:
        if row.is_default:
            return row
    return rows[0] if rows else None


def _copy_company_address_to_office(office: CompanyOffice, company: Company) -> None:
    office.address_line1 = company.address_line1
    office.address_line2 = company.address_line2
    office.city = company.city
    office.state = company.state
    office.postal_code = company.postal_code
    office.country = company.country or "US"
    office.latitude = company.latitude
    office.longitude = company.longitude


def ensure_offices_from_company(company: Company | None = None) -> list[CompanyOffice]:
    company = company or select_self_company()
    if company is None:
        return []
    rows = list_office_rows(company)
    if rows:
        return rows
    has_addr = any(
        getattr(company, k) not in (None, "")
        for k in ("address_line1", "city", "postal_code", "latitude")
    )
    if not has_addr:
        return []
    name = (company.city or "").strip() or (company.name or "").strip() or "Main office"
    office = CompanyOffice(
        company_id=company.id,
        name=name[:120],
        is_default=True,
        sort_order=0,
    )
    _copy_company_address_to_office(office, company)
    db.session.add(office)
    db.session.flush()
    return [office]


def _sync_default_office_from_company(company: Company) -> CompanyOffice:
    office = default_office_row(company)
    if office is None:
        office = CompanyOffice(
            company_id=company.id,
            name=((company.city or "").strip() or "Main office")[:120],
            is_default=True,
            sort_order=0,
        )
        db.session.add(office)
    _copy_company_address_to_office(office, company)
    if not (office.name or "").strip():
        office.name = ((company.city or "").strip() or "Main office")[:120]
    db.session.flush()
    return office


def _sync_company_from_default_office(office: CompanyOffice) -> None:
    company = db.session.get(Company, office.company_id)
    if company is None or not office.is_default:
        return
    company.address_line1 = office.address_line1
    company.address_line2 = office.address_line2
    company.city = office.city
    company.state = office.state
    company.postal_code = office.postal_code
    if office.country:
        company.country = office.country
    company.latitude = office.latitude
    company.longitude = office.longitude


def _clear_other_defaults(company_id: uuid.UUID, keep_id: uuid.UUID) -> None:
    for row in db.session.scalars(select(CompanyOffice).where(CompanyOffice.company_id == company_id)).all():
        if row.id != keep_id and row.is_default:
            row.is_default = False


def _apply_office_fields(row: CompanyOffice, data: Mapping[str, Any], *, require_geocode: bool) -> None:
    if "name" in data:
        row.name = (_clean_text(data.get("name"), 120) or "Office")
    for key, limit in (
        ("address_line1", 255),
        ("address_line2", 255),
        ("city", 120),
        ("postal_code", 20),
    ):
        if key in data or (key == "postal_code" and "zip" in data):
            raw = data.get(key) if key in data else data.get("zip")
            setattr(row, key, _clean_text(raw, limit))
    if "state" in data:
        state = _clean_text(data.get("state"), 50)
        row.state = state.upper() if state and len(state) <= 2 else state
    if "country" in data:
        row.country = (_clean_text(data.get("country"), 2) or "US")
        if row.country:
            row.country = row.country.upper()
    if "notes" in data:
        row.notes = _clean_text(data.get("notes"), 2000)
    if "sort_order" in data:
        try:
            row.sort_order = int(data.get("sort_order") or 0)
        except (TypeError, ValueError) as exc:
            raise OfficeLocationError("sort_order must be an integer") from exc
    if "is_default" in data:
        row.is_default = bool(data.get("is_default"))

    explicit = parse_lat_lng(data.get("latitude"), data.get("longitude"))
    addr_changed = any(k in data for k in ("address_line1", "city", "state", "postal_code", "zip"))
    if explicit:
        row.latitude = Decimal(str(round(explicit[0], 6)))
        row.longitude = Decimal(str(round(explicit[1], 6)))
    elif addr_changed or (require_geocode and parse_lat_lng(row.latitude, row.longitude) is None):
        found = geocode_us_address(_addr_from_obj(row))
        if found is None:
            if require_geocode:
                raise OfficeLocationError(
                    "Could not map that office address. Try a street address or ZIP in the United States.",
                    422,
                )
        else:
            row.latitude = Decimal(str(round(found[0], 6)))
            row.longitude = Decimal(str(round(found[1], 6)))


def create_office(data: Mapping[str, Any]) -> dict[str, Any]:
    company = select_self_company()
    if company is None:
        company = Company(name="US Interior Specialties", company_type="self", country="US")
        db.session.add(company)
        db.session.flush()
    existing = list_office_rows(company)
    row = CompanyOffice(company_id=company.id, name="Office", country="US", sort_order=len(existing))
    make_default = bool(data.get("is_default")) or not existing
    _apply_office_fields(row, data, require_geocode=make_default)
    row.is_default = make_default
    if not _addr_from_obj(row) and parse_lat_lng(row.latitude, row.longitude) is None:
        raise OfficeLocationError("office needs a street, city, ZIP, or coordinates", 400)
    db.session.add(row)
    db.session.flush()
    if row.is_default:
        _clear_other_defaults(company.id, row.id)
        _sync_company_from_default_office(row)
    _audit_office("office.create", row)
    db.session.commit()
    return office_row_public(row)


def patch_office(office_id: uuid.UUID, data: Mapping[str, Any]) -> dict[str, Any]:
    row = db.session.get(CompanyOffice, office_id)
    if row is None:
        raise OfficeLocationError("office not found", 404)
    will_be_default = bool(data["is_default"]) if "is_default" in data else bool(row.is_default)
    _apply_office_fields(row, data, require_geocode=will_be_default)
    if will_be_default:
        row.is_default = True
        _clear_other_defaults(row.company_id, row.id)
        _sync_company_from_default_office(row)
    db.session.flush()
    _audit_office("office.patch", row)
    db.session.commit()
    return office_row_public(row)


def delete_office(office_id: uuid.UUID) -> dict[str, Any]:
    row = db.session.get(CompanyOffice, office_id)
    if row is None:
        raise OfficeLocationError("office not found", 404)
    company_id = row.company_id
    was_default = bool(row.is_default)
    db.session.delete(row)
    db.session.flush()
    remaining = list(
        db.session.scalars(
            select(CompanyOffice)
            .where(CompanyOffice.company_id == company_id)
            .order_by(CompanyOffice.sort_order.asc(), CompanyOffice.created_at.asc())
        ).all()
    )
    if was_default and remaining:
        remaining[0].is_default = True
        _sync_company_from_default_office(remaining[0])
    db.session.commit()
    return {"ok": True, "id": str(office_id)}


def _audit_office(action: str, row: CompanyOffice) -> None:
    cu = current_user()
    if cu.user is None:
        return
    db.session.add(
        AuditLog(
            user_id=cu.user.id,
            entity_type="company_office",
            entity_id=row.id,
            action=action,
            changes={"name": row.name, "is_default": row.is_default},
            message=f"{action} ({office_row_label(row)})",
        )
    )


def jobsite_address(project: Project | None) -> str:
    if project is None:
        return ""
    return _addr_from_obj(project)


def resolve_job_shipping(project: Project | None) -> dict[str, Any]:
    offices = [office_row_public(x) for x in ensure_offices_from_company()]
    kind = ((project.ship_to_kind if project is not None else None) or "jobsite").strip().lower()
    if kind not in ("jobsite", "office"):
        kind = "jobsite"
    office_id = str(project.ship_to_office_id) if project is not None and project.ship_to_office_id else None
    chosen = None
    if kind == "office":
        if office_id:
            chosen = next((o for o in offices if o["id"] == office_id), None)
        if chosen is None:
            chosen = next((o for o in offices if o.get("is_default")), None) or (offices[0] if offices else None)
            office_id = chosen["id"] if chosen else None
    jobsite = jobsite_address(project)
    shipping = jobsite if kind == "jobsite" else ((chosen or {}).get("address") or "")
    label = "Jobsite" if kind == "jobsite" else ((chosen or {}).get("label") or "Office")
    install = None
    if project is not None:
        install = project.expected_install_date.isoformat() if project.expected_install_date else None
        if not install and project.start_date:
            install = project.start_date.isoformat()
    return {
        "ship_to_kind": kind,
        "ship_to_office_id": office_id if kind == "office" else None,
        "shipping_address": shipping,
        "shipping_label": label,
        "jobsite_address": jobsite,
        "expected_install_date": install,
        "expected_install_date_explicit": (
            project.expected_install_date.isoformat() if project is not None and project.expected_install_date else None
        ),
        "offices": offices,
        "settings_url": "usis-company-settings.html",
    }


def apply_job_shipping(project: Project, data: Mapping[str, Any]) -> dict[str, Any]:
    if "expected_install_date" in data:
        raw = data.get("expected_install_date")
        if raw in (None, ""):
            project.expected_install_date = None
        else:
            from datetime import date as date_cls

            try:
                project.expected_install_date = date_cls.fromisoformat(str(raw).strip()[:10])
            except ValueError as exc:
                raise OfficeLocationError("invalid expected_install_date") from exc
    if "ship_to_kind" in data or "ship_to_office_id" in data:
        kind = str(data.get("ship_to_kind") or project.ship_to_kind or "jobsite").strip().lower()
        if kind not in ("jobsite", "office"):
            raise OfficeLocationError("ship_to_kind must be jobsite or office")
        office_id = data.get("ship_to_office_id") if "ship_to_office_id" in data else project.ship_to_office_id
        oid: uuid.UUID | None = None
        if office_id not in (None, ""):
            try:
                oid = uuid.UUID(str(office_id))
            except (ValueError, TypeError, AttributeError) as exc:
                raise OfficeLocationError("invalid ship_to_office_id") from exc
            office = db.session.get(CompanyOffice, oid)
            if office is None:
                raise OfficeLocationError("office not found", 404)
        if kind == "office" and oid is None:
            fallback = default_office_row()
            if fallback is None:
                raise OfficeLocationError("Add an office in company settings before shipping to an office.")
            oid = fallback.id
        project.ship_to_kind = kind
        project.ship_to_office_id = oid if kind == "office" else None
    db.session.flush()
    return resolve_job_shipping(project)


def register_office_location_routes(bp: Blueprint) -> None:
    @bp.get("/office-location")
    def get_office_location_route():
        company = select_self_company()
        office = viewer_office_row(company)
        if office is not None:
            pub = office_row_public(office)
            coords = parse_lat_lng(office.latitude, office.longitude) or company_coords(company)
            return _jsonify(
                {
                    "configured": coords is not None,
                    "id": pub["id"],
                    "source": viewer_office_source(office),
                    "name": pub["name"] or ((company.name or "").strip() if company else ""),
                    "label": pub["label"] or office_label(company),
                    "address_line1": pub["address_line1"] or ((company.address_line1 or "").strip() if company else ""),
                    "address_line2": pub["address_line2"] or ((company.address_line2 or "").strip() if company else ""),
                    "city": pub["city"] or ((company.city or "").strip() if company else ""),
                    "state": pub["state"] or ((company.state or "").strip() if company else ""),
                    "postal_code": pub["postal_code"]
                    or ((company.postal_code or "").strip() if company else ""),
                    "latitude": coords[0] if coords else None,
                    "longitude": coords[1] if coords else None,
                }
            )
        pub = office_public(company)
        pub["id"] = None
        pub["source"] = "default"
        return _jsonify(pub)

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

    @bp.get("/office-locations")
    def list_office_locations_route():
        items = [office_row_public(x) for x in ensure_offices_from_company()]
        db.session.commit()
        return _jsonify({"items": items, "entity": "company_offices"})

    @bp.post("/office-locations")
    def create_office_location_route():
        from flask import request

        cu = current_user()
        if is_company_readonly(cu) and not cu.is_dev_admin:
            return _jsonify({"error": "read-only role cannot update office location"}), 403
        data = request.get_json(silent=True) or {}
        if not isinstance(data, Mapping):
            return _jsonify({"error": "JSON object required"}), 400
        try:
            return _jsonify({"item": create_office(data), "entity": "company_office"}), 201
        except OfficeLocationError as exc:
            return _jsonify({"error": exc.message}), exc.status

    @bp.patch("/office-locations/<office_id>")
    def patch_office_location_id_route(office_id: str):
        from flask import request

        cu = current_user()
        if is_company_readonly(cu) and not cu.is_dev_admin:
            return _jsonify({"error": "read-only role cannot update office location"}), 403
        try:
            oid = uuid.UUID(str(office_id))
        except (ValueError, TypeError, AttributeError):
            return _jsonify({"error": "invalid office id"}), 400
        data = request.get_json(silent=True) or {}
        if not isinstance(data, Mapping):
            return _jsonify({"error": "JSON object required"}), 400
        try:
            return _jsonify({"item": patch_office(oid, data), "entity": "company_office"})
        except OfficeLocationError as exc:
            return _jsonify({"error": exc.message}), exc.status

    @bp.delete("/office-locations/<office_id>")
    def delete_office_location_id_route(office_id: str):
        cu = current_user()
        if is_company_readonly(cu) and not cu.is_dev_admin:
            return _jsonify({"error": "read-only role cannot update office location"}), 403
        try:
            oid = uuid.UUID(str(office_id))
        except (ValueError, TypeError, AttributeError):
            return _jsonify({"error": "invalid office id"}), 400
        try:
            return _jsonify(delete_office(oid))
        except OfficeLocationError as exc:
            return _jsonify({"error": exc.message}), exc.status
