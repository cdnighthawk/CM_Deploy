"""Shared employee-PC cache: USISCM project/drawing layout, company JSON, takeoff."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

from app.services import employee_pc_cache as pc_cache


def test_drawing_id_n_strips_dashes_and_lowercases():
    uid = uuid.UUID("007c8e1f-361c-4b9f-a6fa-f99aa0b2d638")
    assert pc_cache.drawing_id_n(uid) == "007c8e1f361c4b9fa6faf99aa0b2d638"
    assert pc_cache.drawing_id_n(str(uid).upper()) == "007c8e1f361c4b9fa6faf99aa0b2d638"
    assert pc_cache.folder_key(uid) == "007c8e1f361c4b9fa6faf99aa0b2d638"
    assert pc_cache.folder_key(None) == "unscoped"


def test_sanitize_file_name_matches_dotnet():
    assert pc_cache.sanitize_file_name(None) is None
    assert pc_cache.sanitize_file_name("  ") is None
    assert pc_cache.sanitize_file_name(r"C:\plans\A1:00*.pdf") == "A1_00_.pdf"
    assert pc_cache.sanitize_file_name("folder/A-101.pdf") == "A-101.pdf"


def test_find_cached_project_unscoped_other_project_then_legacy(tmp_path: Path, monkeypatch):
    company = tmp_path / "USISCM"
    legacy = tmp_path / "USISPdfApp"
    monkeypatch.setenv("USIS_DRAWING_CACHE_ROOT", str(company))
    monkeypatch.setenv("USIS_DRAWING_CACHE_LEGACY_ROOT", str(legacy))

    did = uuid.UUID("007c8e1f-361c-4b9f-a6fa-f99aa0b2d638")
    pid = uuid.UUID("11111111-1111-4111-8111-111111111111")
    other = uuid.UUID("22222222-2222-4222-8222-222222222222")
    key = "007c8e1f361c4b9fa6faf99aa0b2d638"

    assert pc_cache.find_cached(did, "sheet.pdf", pid) is None

    legacy_file = legacy / "drawings" / key / "old-name.pdf"
    legacy_file.parent.mkdir(parents=True)
    legacy_file.write_bytes(b"%PDF-1.4 leftover")
    assert pc_cache.find_cached(did, "sheet.pdf", pid) == legacy_file

    flat = company / "drawings" / key / "flat.pdf"
    flat.parent.mkdir(parents=True)
    flat.write_bytes(b"%PDF-1.4 flat")
    assert pc_cache.find_cached(did, "sheet.pdf", pid) == flat

    other_file = company / other.hex / key / "other.pdf"
    other_file.parent.mkdir(parents=True)
    other_file.write_bytes(b"%PDF-1.4 other-project")
    assert pc_cache.find_cached(did, "sheet.pdf", pid) == other_file

    unscoped = company / "unscoped" / key / "loose.pdf"
    unscoped.parent.mkdir(parents=True)
    unscoped.write_bytes(b"%PDF-1.4 unscoped")
    assert pc_cache.find_cached(did, "sheet.pdf", pid) == unscoped

    dest = pc_cache.write_cached(did, "sheet.pdf", b"%PDF-1.4 new", pid)
    assert dest == unscoped
    preferred = company / pid.hex / key / "sheet.pdf"
    assert not preferred.exists()

    unscoped.unlink()
    other_file.unlink()
    flat.unlink()
    legacy_file.unlink()
    dest = pc_cache.write_cached(did, "A1:00*.pdf", b"%PDF-1.4 named", pid)
    assert dest == company / pid.hex / key / "A1_00_.pdf"
    assert dest.read_bytes() == b"%PDF-1.4 named"

    renamed = dest.with_name("renamed.pdf")
    dest.rename(renamed)
    assert pc_cache.find_cached(did, "A1_00_.pdf", pid) == renamed

    dest.write_bytes(b"%PDF-1.4 preferred")
    assert pc_cache.find_cached(did, "A1_00_.pdf", pid) == dest

    again = pc_cache.write_cached(did, "A1_00_.pdf", b"%PDF-1.4 should-not-overwrite", pid)
    assert again == dest
    assert dest.read_bytes() == b"%PDF-1.4 preferred"


def test_empty_file_is_not_a_hit(tmp_path: Path, monkeypatch):
    company = tmp_path / "USISCM"
    monkeypatch.setenv("USIS_DRAWING_CACHE_ROOT", str(company))
    monkeypatch.delenv("USIS_DRAWING_CACHE_LEGACY_ROOT", raising=False)
    did = uuid.uuid4()
    empty = pc_cache.cache_path(did, "x.pdf", None)
    assert empty is not None
    empty.parent.mkdir(parents=True)
    empty.write_bytes(b"")
    assert pc_cache.find_cached(did, "x.pdf") is None
    written = pc_cache.write_cached(did, "x.pdf", b"%PDF-1.4 ok")
    assert written == empty
    assert empty.read_bytes() == b"%PDF-1.4 ok"


def test_write_cached_never_uses_legacy_or_company(tmp_path: Path, monkeypatch):
    company = tmp_path / "USISCM"
    legacy = tmp_path / "USISPdfApp"
    monkeypatch.setenv("USIS_DRAWING_CACHE_ROOT", str(company))
    monkeypatch.setenv("USIS_DRAWING_CACHE_LEGACY_ROOT", str(legacy))
    did = uuid.uuid4()
    pid = uuid.uuid4()
    written = pc_cache.write_cached(did, "a.pdf", b"%PDF-1.4 x", pid)
    assert written is not None
    assert written.parent == company / pid.hex / did.hex
    assert not (legacy / "drawings").exists()
    assert not (company / "drawings").exists()
    assert (company / "company").exists() is False


def test_company_catalog_skips_starter_and_writes_camelcase(tmp_path: Path, monkeypatch):
    company = tmp_path / "USISCM"
    monkeypatch.setenv("USIS_DRAWING_CACHE_ROOT", str(company))
    monkeypatch.setenv("USIS_DRAWING_CACHE_LEGACY_ROOT", str(tmp_path / "legacy"))

    starter = [
        SimpleNamespace(
            id=uuid.uuid4(),
            manufacturer="Hub",
            item=f"SKU-{i}",
            category="Misc",
            csi_spec_section=None,
            description=None,
            mounting_type=None,
            cost=1,
            labor_per=0,
            currency="USD",
            unit_of_measure="EA",
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        for i in range(20)
    ]
    assert pc_cache.write_company_catalog(starter) is None
    assert not (company / "company" / "material_pricing.json").exists()

    large_local = company / "company" / "material_pricing.json"
    large_local.parent.mkdir(parents=True)
    large_local.write_text(json.dumps([{"id": str(uuid.uuid4())} for _ in range(50)]), encoding="utf-8")
    assert pc_cache.write_company_catalog(starter) == large_local
    assert len(json.loads(large_local.read_text(encoding="utf-8"))) == 50

    company_rows = [
        SimpleNamespace(
            id=uuid.uuid4(),
            manufacturer="Penco",
            item=f"Part-{i}",
            category="Lockers",
            csi_spec_section="10 51 13",
            description="Locker",
            mounting_type="Floor",
            cost=12.5,
            labor_per=0.25,
            currency="USD",
            unit_of_measure="EA",
            created_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
            updated_at=datetime(2026, 8, 2, tzinfo=timezone.utc),
        )
        for i in range(21)
    ]
    written = pc_cache.write_company_catalog(company_rows)
    assert written == company / "company" / "material_pricing.json"
    payload = json.loads(written.read_text(encoding="utf-8"))
    assert len(payload) == 21
    assert payload[0]["unitOfMeasure"] == "EA"
    assert payload[0]["csiSpecSection"] == "10 51 13"
    catalog = json.loads((company / "company" / "catalog.json").read_text(encoding="utf-8"))
    assert catalog[0]["unitCost"] == 12.5
    assert catalog[0]["laborHoursPerUnit"] == 0.25


def test_company_wages_write_nonempty(tmp_path: Path, monkeypatch):
    company = tmp_path / "USISCM"
    monkeypatch.setenv("USIS_DRAWING_CACHE_ROOT", str(company))
    assert pc_cache.write_company_wages([]) is None
    row = SimpleNamespace(
        id=uuid.uuid4(),
        state="CA",
        sub_area="LA",
        year=2026,
        trade="Carpenter",
        basic_hourly_rate=40,
        health_welfare=1,
        pension=2,
        vacation_holiday=3,
        other_payments=0,
        training=0.5,
        notes=None,
        is_assumed=False,
    )
    dest = pc_cache.write_company_wages([row])
    assert dest == company / "company" / "wage_rates.json"
    payload = json.loads(dest.read_text(encoding="utf-8"))
    assert payload[0]["basicHourlyRate"] == 40
    assert payload[0]["subArea"] == "LA"


def test_takeoff_write_and_skip_when_local_newer(tmp_path: Path, monkeypatch):
    company = tmp_path / "USISCM"
    monkeypatch.setenv("USIS_DRAWING_CACHE_ROOT", str(company))
    pid = uuid.UUID("007c8e1f-361c-4b9f-a6fa-f99aa0b2d638")
    now = datetime(2026, 8, 30, 14, 0, tzinfo=timezone.utc)
    older = SimpleNamespace(
        id=uuid.uuid4(),
        drawing_id=None,
        description="Studs",
        quantity=10,
        unit="LF",
        unit_cost=1.5,
        cost_type="M",
        job_cost_code="06",
        job_cost_code_description="Wood",
        section="Framing",
        sort_order=1,
        material_pricing_id=None,
        material_price=None,
        measurement_data={"kind": "count"},
        extended_total=15,
        notes=None,
        updated_at=now - timedelta(days=2),
    )
    dest = pc_cache.write_takeoff(pid, [older], updated_at=now)
    assert dest == company / pid.hex / "takeoff.json"
    envelope = json.loads(dest.read_text(encoding="utf-8"))
    assert envelope["projectId"] == str(pid)
    assert envelope["items"] == []
    assert envelope["lines"][0]["unitCost"] == 1.5
    assert envelope["lines"][0]["cloudTakeoffLineId"] == str(older.id)

    assert pc_cache.maybe_write_takeoff(pid, [older]) is None
    newer = SimpleNamespace(**{**older.__dict__, "updated_at": now + timedelta(minutes=1), "description": "Newer"})
    written = pc_cache.maybe_write_takeoff(pid, [newer])
    assert written == dest
    assert json.loads(dest.read_text(encoding="utf-8"))["lines"][0]["description"] == "Newer"

    assert pc_cache.maybe_write_takeoff(pid, []) is None
    assert json.loads(dest.read_text(encoding="utf-8"))["lines"][0]["description"] == "Newer"
    assert pc_cache.maybe_write_takeoff(None, [newer]) is None
    assert pc_cache.takeoff_path(None) is None
