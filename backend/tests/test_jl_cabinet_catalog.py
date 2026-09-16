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
_PRODUCT_TAG_EXTRAS = {"C1015W10", "C1023F10", "C1025F10", "C5614S21"}
_HERO_SKUS = {"C1085V10", "C1017P42", "C2119F10"}
_DROPPED_CONSTRUCTED = {
    "C1013C70",
    "C1015C70",
    "C1015C71",
    "C1017C70",
    "C1043F10",
    "C1045F10",
    "C1047F10",
    "C1055F10",
    "C8115F10",
    "C2115F10",
    "C2115F10FX2",
    "C2119G10",
}
_EXACT_SUBMITTAL_SKUS = {
    # Ambassador Exact Submittals
    "C1013F10",
    "C1013G10",
    "C1013S21",
    "C1013V10",
    "C1015F10",
    "C1015F10FX2",
    "C1015V10",
    "C1015V10FX2",
    "C1016F10",
    "C1016F10FX2",
    "C1016V10",
    "C1016W17FX2",
    "C1017F10",
    "C1017F10FX2",
    "C1017F17",
    "C1017F17FX2",
    "C1017G10",
    "C1017G10FX2",
    "C1017S21",
    "C1017V10",
    "C1017V10FX2",
    "C1017V17FX2",
    "C1017W10",
    "C1017W10FX2",
    "C1017W17FX2",
    "C1816F10",
    "C1816G10",
    "C1816G10FX2",
    # Academy Exact Submittals
    "C1026L24",
    "C1027F10",
    "C1027F10FX2",
    "C1027V10",
    "C1027V10FX2",
    "C1027W17",
    # Cosmopolitan Exact Submittals
    "C1033F10",
    "C1033F17",
    "C1033V10",
    "C1033W17",
    "C1035V10",
    "C1037F10",
    "C1037F10FX2",
    "C1037F17",
    "C1037G10",
    "C1037L22",
    "C1037S21",
    "C1037V10",
    "C1037V10FX2",
    "C1037V17",
    "C1037W10",
    "C1037W17",
    "C2033F10",
    # Clear Vu Exact Submittals
    "C1515G25",
    "C1516F25",
    "C1516F25FX2",
    # Embassy Exact Submittals
    "C5614V10",
    "C5614V17",
    "C5614V17FX2",
    "C5634S21",
}
_SKIPPED_SERIES_SKUS = {"9163Z30", "SERIES-CLASSIC", "SERIES-CATO-CHIEF", "Classic", "Cato Chief"}
_MOUNTS = {"Surface", "Recessed", "Semi-recessed"}


def test_repo_catalog_includes_jl_seed():
    assert _SEED.is_file()
    assert _SEED.resolve() in {p.resolve() for p in repo_catalog_seed_csvs()}


def test_jl_seed_parses_to_real_skus():
    rows = read_material_csv(_SEED)
    items = [r["item"] for r in rows]
    item_set = set(items)
    assert len(rows) == 73
    assert len(items) == len(set(items))
    assert _SERIES.issubset(item_set)
    assert _BEST_SELLERS.issubset(item_set)
    assert _PRODUCT_TAG_EXTRAS.issubset(item_set)
    assert _HERO_SKUS.issubset(item_set)
    assert _EXACT_SUBMITTAL_SKUS.issubset(item_set)
    assert item_set.isdisjoint(_DROPPED_CONSTRUCTED)
    assert item_set.isdisjoint(_SKIPPED_SERIES_SKUS)
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
            assert not str(row["item"]).startswith("SERIES-")


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
    assert "FE10V" in (by_item["C2119F10"]["description"] or "")
    assert by_item["C2119F10"]["mounting_type"] == "Surface"
    assert by_item["C1085V10"]["mounting_type"] == "Recessed"
    assert "frameless" in (by_item["C1017P42"]["description"] or "").lower()


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
    assert _EXACT_SUBMITTAL_SKUS.issubset(skus)
    assert skus.isdisjoint(_DROPPED_CONSTRUCTED)
    assert all(x.get("csi_spec_section") == "104400" for x in items)
    assert all(x.get("unit_of_measure") == "EA" for x in items)
