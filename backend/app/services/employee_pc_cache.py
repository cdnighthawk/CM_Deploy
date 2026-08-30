"""Shared employee-PC cache matching USISPdfApp ``UsisSharedCache``.

Layout::

    %LOCALAPPDATA%\\USISCM\\
      company\\material_pricing.json, catalog.json, wage_rates.json, assemblies.json
      {projectId}\\takeoff.json
      {projectId}\\{drawingId}\\{fileName}
      unscoped\\{drawingId}\\{fileName}     # drawings only, when there is no project

``{projectId}`` / ``{drawingId}`` are database GUIDs in .NET ``N`` format
(32 lowercase hex, no dashes). Job workspace, auth, prefs, and ``job.json``
stay out of this tree.

Browser JS cannot write this folder. Flask on the employee PC reads and writes
it. Override roots with ``USIS_DRAWING_CACHE_ROOT`` / ``USIS_DRAWING_CACHE_LEGACY_ROOT``.
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable

from flask import Response, send_file

from .object_storage import UploadCategory, read_stored_bytes

COMPANY_FOLDER = "USISCM"
LEGACY_APP_FOLDER = "USISPdfApp"
COMPANY_DIR = "company"
UNSCOPED = "unscoped"
DRAWINGS_DIR = "drawings"
TAKEOFF_FILE = "takeoff.json"
MATERIAL_PRICING_FILE = "material_pricing.json"
CATALOG_FILE = "catalog.json"
WAGE_RATES_FILE = "wage_rates.json"
ASSEMBLIES_FILE = "assemblies.json"

# Desktop CatalogSeed has 20 starter SKUs. Company catalog is larger.
STARTER_MAX = 20

_INVALID_FILENAME = frozenset(chr(i) for i in range(32)) | set('<>:"/\\|?*')

_JSON_DUMP = {"indent": 2, "ensure_ascii": False}


def _env_path(name: str) -> Path | None:
    raw = (os.environ.get(name) or "").strip()
    return Path(raw) if raw else None


def cache_enabled() -> bool:
    flag = (os.environ.get("USIS_DRAWING_CACHE") or os.environ.get("USIS_PC_CACHE") or "").strip().lower()
    if flag in ("0", "false", "off", "no"):
        return False
    if _env_path("USIS_DRAWING_CACHE_ROOT") is not None:
        return True
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return False
    return local_app_data() is not None


def local_app_data() -> Path | None:
    raw = (os.environ.get("LOCALAPPDATA") or "").strip()
    if raw:
        return Path(raw)
    if os.name == "nt":
        candidate = Path.home() / "AppData" / "Local"
        if candidate.is_dir():
            return candidate
    return None


def company_root() -> Path | None:
    override = _env_path("USIS_DRAWING_CACHE_ROOT")
    if override is not None:
        return override
    if not cache_enabled():
        return None
    base = local_app_data()
    if base is None:
        return None
    return base / COMPANY_FOLDER


def legacy_app_root() -> Path | None:
    override = _env_path("USIS_DRAWING_CACHE_LEGACY_ROOT")
    if override is not None:
        return override
    if not cache_enabled():
        return None
    base = local_app_data()
    if base is None:
        return None
    return base / LEGACY_APP_FOLDER


def company_json_root() -> Path | None:
    root = company_root()
    return None if root is None else root / COMPANY_DIR


def folder_key(value: uuid.UUID | str | None) -> str:
    if value is None or value == "":
        return UNSCOPED
    try:
        uid = value if isinstance(value, uuid.UUID) else uuid.UUID(str(value).strip())
    except (ValueError, AttributeError, TypeError):
        return UNSCOPED
    if uid.int == 0:
        return UNSCOPED
    return uid.hex


def drawing_id_n(drawing_id: uuid.UUID | str) -> str:
    if isinstance(drawing_id, uuid.UUID):
        return drawing_id.hex
    return uuid.UUID(str(drawing_id).strip()).hex


def sanitize_file_name(file_name: str | None) -> str | None:
    if file_name is None or not str(file_name).strip():
        return None
    name = Path(str(file_name).strip()).name
    name = "".join("_" if ch in _INVALID_FILENAME else ch for ch in name)
    return name if name.strip() else None


def preferred_file_name(drawing_id: uuid.UUID | str, file_name: str | None) -> str:
    return sanitize_file_name(file_name) or f"{drawing_id_n(drawing_id)}.pdf"


def project_directory(project_id: uuid.UUID | str | None) -> Path | None:
    root = company_root()
    if root is None:
        return None
    return root / folder_key(project_id)


def drawing_directory(project_id: uuid.UUID | str | None, drawing_id: uuid.UUID | str) -> Path | None:
    proj = project_directory(project_id)
    if proj is None:
        return None
    return proj / drawing_id_n(drawing_id)


def cache_path(
    drawing_id: uuid.UUID | str,
    file_name: str | None,
    project_id: uuid.UUID | str | None = None,
) -> Path | None:
    folder = drawing_directory(project_id, drawing_id)
    if folder is None:
        return None
    return folder / preferred_file_name(drawing_id, file_name)


def takeoff_path(project_id: uuid.UUID | str) -> Path | None:
    if folder_key(project_id) == UNSCOPED:
        return None
    proj = project_directory(project_id)
    if proj is None:
        return None
    return proj / TAKEOFF_FILE


def is_usable(path: Path | None) -> bool:
    if path is None:
        return False
    try:
        return path.is_file() and path.stat().st_size > 0
    except OSError:
        return False


def is_company_sized(count: int) -> bool:
    return count > STARTER_MAX


def is_starter_sized(count: int) -> bool:
    return count <= STARTER_MAX


def _first_usable_in(folder: Path | None, file_name: str | None) -> Path | None:
    if folder is None:
        return None
    safe = sanitize_file_name(file_name)
    if safe:
        preferred = folder / safe
        if is_usable(preferred):
            return preferred
    if not folder.is_dir():
        return None
    match: Path | None = None
    try:
        for entry in folder.iterdir():
            if not entry.is_file() or not is_usable(entry):
                continue
            if safe and entry.name.lower() == safe.lower():
                return entry
            if match is None or entry.suffix.lower() == ".pdf":
                match = entry
    except OSError:
        return match
    return match


def _candidate_drawing_folders(
    drawing_id: uuid.UUID | str,
    project_id: uuid.UUID | str | None,
) -> list[Path]:
    key = drawing_id_n(drawing_id)
    seen: set[str] = set()
    out: list[Path] = []

    def add(path: Path | None) -> None:
        if path is None:
            return
        try:
            full = str(path.resolve()) if path.exists() else str(path)
        except OSError:
            full = str(path)
        norm = os.path.normcase(full)
        if norm in seen:
            return
        seen.add(norm)
        out.append(path)

    add(drawing_directory(project_id, drawing_id))
    if folder_key(project_id) != UNSCOPED:
        add(drawing_directory(None, drawing_id))

    root = company_root()
    if root is not None and root.is_dir():
        try:
            for project_dir in root.iterdir():
                if not project_dir.is_dir():
                    continue
                if project_dir.name.lower() == COMPANY_DIR:
                    continue
                add(project_dir / key)
        except OSError:
            pass

    legacy = legacy_app_root()
    if legacy is not None:
        add(legacy / DRAWINGS_DIR / key)
    if root is not None:
        add(root / DRAWINGS_DIR / key)
    return out


def find_cached(
    drawing_id: uuid.UUID | str,
    file_name: str | None = None,
    project_id: uuid.UUID | str | None = None,
) -> Path | None:
    """First usable PDF: preferred project folder, any name, unscoped, other projects, then legacy."""
    try:
        drawing_id_n(drawing_id)
    except (ValueError, AttributeError, TypeError):
        return None
    for folder in _candidate_drawing_folders(drawing_id, project_id):
        hit = _first_usable_in(folder, file_name)
        if hit is not None:
            return hit
    return None


def write_cached(
    drawing_id: uuid.UUID | str,
    file_name: str | None,
    data: bytes,
    project_id: uuid.UUID | str | None = None,
) -> Path | None:
    """Write a new download into the project (or unscoped) folder. Never write legacy paths."""
    if not data or not cache_enabled():
        return None
    existing = find_cached(drawing_id, file_name, project_id)
    if existing is not None:
        return existing
    dest = cache_path(drawing_id, file_name, project_id)
    if dest is None:
        return None
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".part")
    try:
        tmp.write_bytes(data)
        tmp.replace(dest)
    except OSError:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        return None
    return dest if is_usable(dest) else None


def download_name_for(row) -> str:
    dl = (getattr(row, "original_filename", None) or "drawing.pdf").replace('"', "")
    if not dl.lower().endswith(".pdf"):
        dl = dl + ".pdf"
    return dl[:200]


def respond_drawing_pdf(row, object_name: str) -> Response | None:
    """Serve from the employee-PC cache when present; otherwise storage, then cache."""
    dl = download_name_for(row)
    project_id = getattr(row, "project_id", None)
    cached = find_cached(row.id, dl, project_id)
    if cached is not None:
        return send_file(
            cached,
            mimetype="application/pdf",
            as_attachment=False,
            download_name=dl,
        )

    data = read_stored_bytes(UploadCategory.DRAWINGS, object_name)
    if data is None:
        from .project_file_keys import drawing_object_candidates

        for cand in drawing_object_candidates(row):
            if cand == object_name:
                continue
            data = read_stored_bytes(UploadCategory.DRAWINGS, cand)
            if data is not None:
                break
    if data is None:
        return None
    written = write_cached(row.id, dl, data, project_id)
    if written is not None:
        return send_file(
            written,
            mimetype="application/pdf",
            as_attachment=False,
            download_name=dl,
        )
    safe_name = dl.replace('"', "")
    return Response(
        data,
        mimetype="application/pdf",
        headers={
            "Content-Length": str(len(data)),
            "Content-Disposition": f'inline; filename="{safe_name}"',
        },
    )


def _json_default(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, datetime):
        dt = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    raise TypeError(f"not JSON serializable: {type(value)!r}")


def _write_json(path: Path, payload: Any) -> Path | None:
    tmp = path.with_name(path.name + ".part")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(
            json.dumps(payload, default=_json_default, **_JSON_DUMP),
            encoding="utf-8",
        )
        tmp.replace(path)
        return path
    except OSError:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        return None


def _read_json(path: Path | None) -> Any | None:
    if path is None or not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _ci_get(mapping: Any, *names: str) -> Any:
    if not isinstance(mapping, dict):
        return None
    lower = {str(k).lower(): v for k, v in mapping.items()}
    for name in names:
        if name.lower() in lower:
            return lower[name.lower()]
    return None


def company_read_paths(file_name: str) -> list[Path]:
    out: list[Path] = []
    root = company_json_root()
    if root is not None:
        out.append(root / file_name)
    legacy = legacy_app_root()
    if legacy is not None:
        out.append(legacy / file_name)
    return out


def first_existing_company_file(file_name: str) -> Path | None:
    for path in company_read_paths(file_name):
        if is_usable(path):
            return path
    return None


def _company_write_path(file_name: str) -> Path | None:
    root = company_json_root()
    if root is None:
        return None
    return root / file_name


def write_company_json(file_name: str, payload: Any) -> Path | None:
    dest = _company_write_path(file_name)
    if dest is None or not cache_enabled():
        return None
    return _write_json(dest, payload)


def _num(value: Any) -> float:
    if value is None:
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return str(value)


def material_pricing_cache_row(m) -> dict[str, Any]:
    return {
        "id": str(m.id),
        "manufacturer": m.manufacturer or "",
        "item": m.item or "",
        "category": m.category,
        "csiSpecSection": m.csi_spec_section,
        "description": m.description,
        "mountingType": m.mounting_type,
        "cost": _num(m.cost),
        "laborPer": _num(m.labor_per),
        "currency": m.currency or "USD",
        "unitOfMeasure": m.unit_of_measure or "EA",
        "createdAt": _iso(getattr(m, "created_at", None)),
        "updatedAt": _iso(getattr(m, "updated_at", None)),
        "kind": "Material",
        "defaultWastePct": 0,
        "defaultMarkupPct": 0,
        "productKind": "sku",
        "configuratorKey": None,
    }


def catalog_item_cache_row(m) -> dict[str, Any]:
    item = m.item or ""
    return {
        "id": str(m.id),
        "name": item,
        "manufacturer": m.manufacturer or "",
        "item": item,
        "category": m.category or "",
        "csiSpecSection": m.csi_spec_section,
        "description": m.description,
        "mountingType": m.mounting_type,
        "kind": "Material",
        "unit": m.unit_of_measure or "EA",
        "currency": m.currency or "USD",
        "unitCost": _num(m.cost),
        "laborCostPerUnit": 0,
        "laborHoursPerUnit": _num(m.labor_per),
        "defaultWastePct": 0,
        "defaultMarkupPct": 0,
        "productKind": "sku",
        "createdAt": _iso(getattr(m, "created_at", None)),
        "updatedAt": _iso(getattr(m, "updated_at", None)),
    }


def wage_rate_cache_row(w) -> dict[str, Any]:
    return {
        "id": str(w.id),
        "state": w.state,
        "subArea": w.sub_area or "",
        "year": w.year,
        "trade": w.trade,
        "basicHourlyRate": _num(w.basic_hourly_rate),
        "healthWelfare": _num(w.health_welfare),
        "pension": _num(w.pension),
        "vacationHoliday": _num(w.vacation_holiday),
        "otherPayments": _num(w.other_payments),
        "training": _num(w.training),
        "notes": w.notes,
        "isAssumed": bool(w.is_assumed),
    }


def _local_catalog_count() -> int:
    payload = _read_json(first_existing_company_file(MATERIAL_PRICING_FILE))
    if payload is None:
        payload = _read_json(first_existing_company_file(CATALOG_FILE))
    if isinstance(payload, list):
        return len(payload)
    if isinstance(payload, dict):
        items = payload.get("items") or payload.get("Items")
        if isinstance(items, list):
            return len(items)
    return 0


def write_company_catalog(rows: Iterable[Any]) -> Path | None:
    """Overwrite company catalog files only when the payload is company-sized."""
    items = list(rows)
    if not is_company_sized(len(items)):
        if is_company_sized(_local_catalog_count()):
            return first_existing_company_file(MATERIAL_PRICING_FILE)
        return None
    written = write_company_json(MATERIAL_PRICING_FILE, [material_pricing_cache_row(m) for m in items])
    write_company_json(CATALOG_FILE, [catalog_item_cache_row(m) for m in items])
    return written


def write_company_wages(rows: Iterable[Any]) -> Path | None:
    items = list(rows)
    if not items:
        return None
    return write_company_json(WAGE_RATES_FILE, [wage_rate_cache_row(w) for w in items])


def refresh_company_from_db() -> dict[str, Any]:
    """Pull live company lists and refresh USISCM\\company\\ when the payload is usable."""
    from sqlalchemy import select

    from ..extensions import db
    from ..models import MaterialPrice, WageRate

    materials = db.session.scalars(
        select(MaterialPrice).order_by(MaterialPrice.manufacturer.asc(), MaterialPrice.item.asc())
    ).all()
    wages = db.session.scalars(
        select(WageRate).order_by(WageRate.state.asc(), WageRate.year.desc(), WageRate.trade.asc())
    ).all()
    mat_path = write_company_catalog(materials)
    wage_path = write_company_wages(wages)
    return {
        "materials": len(materials),
        "materialsWritten": mat_path is not None and is_company_sized(len(materials)),
        "wages": len(wages),
        "wagesWritten": wage_path is not None,
    }


def takeoff_line_cache_row(t) -> dict[str, Any]:
    mat_name = None
    mp = getattr(t, "material_price", None)
    if mp is not None:
        mat_name = getattr(mp, "item", None)
    mid = getattr(t, "material_pricing_id", None)
    drawing_id = getattr(t, "drawing_id", None)
    return {
        "id": str(t.id),
        "markupId": str(drawing_id) if drawing_id else "",
        "description": t.description or "",
        "quantity": _num(t.quantity),
        "unit": t.unit or "EA",
        "unitCost": _num(t.unit_cost),
        "laborCostPerUnit": 0,
        "wastePct": 0,
        "costType": t.cost_type or "M",
        "jobCostCode": t.job_cost_code,
        "jobCostCodeDescription": t.job_cost_code_description,
        "section": t.section,
        "sortOrder": int(t.sort_order or 0),
        "materialPricingId": str(mid) if mid else None,
        "materialName": mat_name,
        "measurementData": t.measurement_data,
        "extendedTotalLocal": _num(t.extended_total),
        "catalogNumber": None,
        "notes": t.notes,
        "configurationJson": None,
        "cloudTakeoffLineId": str(t.id),
        "dirty": False,
        "deletedAt": None,
    }


def _parse_dt(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def try_read_takeoff(project_id: uuid.UUID | str) -> dict[str, Any] | None:
    path = takeoff_path(project_id)
    payload = _read_json(path)
    if not isinstance(payload, dict):
        return None
    lines = _ci_get(payload, "lines") or []
    items = _ci_get(payload, "items") or []
    if not isinstance(lines, list):
        lines = []
    if not isinstance(items, list):
        items = []
    if not lines and not items:
        return None
    payload = dict(payload)
    payload["lines"] = lines
    payload["items"] = items
    return payload


def write_takeoff(
    project_id: uuid.UUID | str,
    lines: Iterable[Any],
    *,
    cloud_estimate_id: uuid.UUID | str | None = None,
    lead_estimate_id: uuid.UUID | str | None = None,
    items: Iterable[Any] | None = None,
    updated_at: datetime | None = None,
) -> Path | None:
    if folder_key(project_id) == UNSCOPED:
        return None
    dest = takeoff_path(project_id)
    if dest is None or not cache_enabled():
        return None
    line_rows = [takeoff_line_cache_row(t) for t in lines]
    item_rows = list(items) if items is not None else []
    pid = project_id if isinstance(project_id, uuid.UUID) else uuid.UUID(str(project_id))
    envelope = {
        "projectId": str(pid),
        "cloudEstimateId": str(cloud_estimate_id) if cloud_estimate_id else None,
        "leadEstimateId": str(lead_estimate_id) if lead_estimate_id else None,
        "updatedAt": updated_at or datetime.now(timezone.utc),
        "lines": line_rows,
        "items": item_rows,
    }
    return _write_json(dest, envelope)


def maybe_write_takeoff(
    project_id: uuid.UUID | str | None,
    lines: Iterable[Any],
    *,
    cloud_estimate_id: uuid.UUID | str | None = None,
    lead_estimate_id: uuid.UUID | str | None = None,
) -> Path | None:
    """Write takeoff.json when the server snapshot is newer than the local file."""
    if project_id is None or folder_key(project_id) == UNSCOPED:
        return None
    line_list = list(lines)
    existing = try_read_takeoff(project_id)
    if existing and not line_list:
        return None
    server_times = [_parse_dt(getattr(t, "updated_at", None)) for t in line_list]
    server_times = [t for t in server_times if t is not None]
    server_updated = max(server_times) if server_times else datetime.now(timezone.utc)
    if existing:
        local_updated = _parse_dt(_ci_get(existing, "updatedAt", "updated_at"))
        if local_updated is not None and local_updated >= server_updated:
            return None
    return write_takeoff(
        project_id,
        line_list,
        cloud_estimate_id=cloud_estimate_id,
        lead_estimate_id=lead_estimate_id,
        updated_at=server_updated,
    )


def cache_project_takeoff(project_id: uuid.UUID | str | None) -> Path | None:
    if project_id is None or folder_key(project_id) == UNSCOPED:
        return None
    from sqlalchemy import select
    from sqlalchemy.orm import joinedload

    from ..extensions import db
    from ..models import TakeoffLineItem

    lines = db.session.scalars(
        select(TakeoffLineItem)
        .where(TakeoffLineItem.project_id == project_id)
        .options(joinedload(TakeoffLineItem.material_price))
        .order_by(TakeoffLineItem.sort_order.asc(), TakeoffLineItem.created_at.asc())
    ).all()
    cloud = lines[0].estimate_id if lines else None
    lead = lines[0].lead_estimate_id if lines else None
    return maybe_write_takeoff(project_id, lines, cloud_estimate_id=cloud, lead_estimate_id=lead)


def project_id_for_takeoff_line(t) -> uuid.UUID | None:
    pid = getattr(t, "project_id", None)
    if pid:
        return pid
    from ..extensions import db
    from ..models import Estimate, LeadEstimate

    eid = getattr(t, "estimate_id", None)
    if eid:
        est = db.session.get(Estimate, eid)
        if est is not None and est.project_id:
            return est.project_id
    lid = getattr(t, "lead_estimate_id", None)
    if lid:
        lead = db.session.get(LeadEstimate, lid)
        if lead is not None and lead.project_id:
            return lead.project_id
    return None


def cache_takeoff_for_line(t) -> Path | None:
    return cache_project_takeoff(project_id_for_takeoff_line(t))


def refresh_pc_cache(project_id: uuid.UUID | str | None = None) -> dict[str, Any]:
    company = refresh_company_from_db()
    takeoff = cache_project_takeoff(project_id) if project_id else None
    return {
        "ok": True,
        "company": company,
        "takeoffWritten": takeoff is not None,
    }
