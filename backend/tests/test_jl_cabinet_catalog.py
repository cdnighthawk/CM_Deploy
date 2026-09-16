"""JL Industries fire-extinguisher-cabinet seed for material_pricing."""
from __future__ import annotations

from scripts.db_csv_paths import repo_catalog_dir, repo_catalog_seed_csvs
from scripts.load_material_pricing import should_truncate_catalog_file
from scripts.material_csv_row import read_material_csv

_SEED = repo_catalog_dir() / "jl_industries_fire_extinguisher_cabinets.csv"

_SERIES = {
    "Ambassador",
    "Academy",
    "Cosmopolitan",
    "Cavalier",
    "Panorama",
    "Clear Vu",
    "Embassy",
    "Orbit",
}
_BEST_SELLERS = {"C1013F10", "C1015W10"}
_MOUNTS = {"Surface", "Recessed", "Semi-recessed"}


def test_repo_catalog_includes_jl_seed():
    assert _SEED.is_file()
    assert _SEED.resolve() in {p.resolve() for p in repo_catalog_seed_csvs()}


def test_jl_seed_parses_to_real_skus():
    rows = read_material_csv(_SEED)
    items = [r["item"] for r in rows]
    assert len(rows) >= 40
    assert len(items) == len(set(items))
    assert _SERIES.issubset(set(items))
    assert _BEST_SELLERS.issubset(set(items))
    for row in rows:
        assert row["manufacturer"] == "JL Industries"
        assert row["category"] == "Fire Extinguisher Cabinet"
        assert row["csi_spec_section"] == "104400"
        assert row["unit_of_measure"] == "EA"
        assert row["currency"] == "USD"
        desc = row["description"] or ""
        assert len(desc) > 40
        assert "activarcpg.com" in desc
        mount = row["mounting_type"] or ""
        assert mount
        if row["item"] not in _SERIES:
            assert any(token in mount for token in _MOUNTS)
            assert str(row["item"]).startswith("C")


def test_jl_seed_covers_mounts_and_materials():
    rows = read_material_csv(_SEED)
    by_item = {r["item"]: r for r in rows}
    assert by_item["C1013F10"]["mounting_type"] == "Surface"
    assert "full-view" in (by_item["C1013F10"]["description"] or "").lower()
    assert "10 lb" in (by_item["C1013F10"]["description"] or "").lower() or "10lb" in (
        by_item["C1013F10"]["description"] or ""
    ).lower()
    assert by_item["C1015W10"]["mounting_type"] == "Recessed"
    assert "saf-t-lok" in (by_item["C1015W10"]["description"] or "").lower()
    assert by_item["C1017F10"]["mounting_type"] == "Semi-recessed"
    assert "aluminum" in (by_item["Academy"]["description"] or "").lower()
    assert "stainless" in (by_item["Cosmopolitan"]["description"] or "").lower()
    assert "bronze" in (by_item["Cavalier"]["description"] or "").lower()
    assert "FE10V" in (by_item["C2115F10"]["description"] or "")


def test_repo_seeds_never_truncate_by_default():
    assert (
        should_truncate_catalog_file(
            index=0,
            is_repo_seed=True,
            truncate_flag=None,
            all_defaults=True,
            repo_seeds_only=False,
            path_count=3,
        )
        is False
    )
    assert (
        should_truncate_catalog_file(
            index=0,
            is_repo_seed=True,
            truncate_flag=None,
            all_defaults=False,
            repo_seeds_only=True,
            path_count=1,
        )
        is False
    )
    assert (
        should_truncate_catalog_file(
            index=0,
            is_repo_seed=False,
            truncate_flag=None,
            all_defaults=True,
            repo_seeds_only=False,
            path_count=3,
        )
        is True
    )


def test_jl_seed_upsert_is_idempotent(client):
    from sqlalchemy import func, select

    from app.extensions import db
    from app.models.material_pricing import MaterialPrice
    from scripts.load_material_pricing import _upsert_payloads

    rows = read_material_csv(_SEED)
    with client.application.app_context():
        _upsert_payloads(db, MaterialPrice, rows)
        first = db.session.scalar(
            select(func.count())
            .select_from(MaterialPrice)
            .where(MaterialPrice.manufacturer == "JL Industries")
        )
        _upsert_payloads(db, MaterialPrice, rows)
        second = db.session.scalar(
            select(func.count())
            .select_from(MaterialPrice)
            .where(MaterialPrice.manufacturer == "JL Industries")
        )
        assert first == second
        assert first >= len(rows)

    r = client.get(
        "/api/v1/material-prices?manufacturer=JL%20Industries&csi_spec_section=10%2044%2000&limit=200"
    )
    assert r.status_code == 200
    items = r.get_json()["items"]
    skus = {x["item"] for x in items}
    assert _BEST_SELLERS.issubset(skus)
    assert _SERIES.issubset(skus)
    assert all(x.get("csi_spec_section") == "104400" for x in items)
    assert all(x.get("unit_of_measure") == "EA" for x in items)
