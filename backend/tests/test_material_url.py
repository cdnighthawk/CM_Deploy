"""Manufacturer catalog URL parsing."""
from __future__ import annotations

import pytest

from app.catalog_product_url import infer_catalog_product_url
from app.material_url import normalize_manufacturer_url, split_description_url


def test_normalize_adds_https_and_rejects_scripts():
    assert normalize_manufacturer_url("www.bobrick.com") == "https://www.bobrick.com"
    assert (
        normalize_manufacturer_url("https://asi-accuratepartitions.com/products/alpaco/")
        == "https://asi-accuratepartitions.com/products/alpaco/"
    )
    assert normalize_manufacturer_url("") is None
    with pytest.raises(ValueError):
        normalize_manufacturer_url("javascript:alert(1)")


def test_split_description_url_pipe_and_trailing():
    desc, url = split_description_url(
        "Inpro Extension Roller 333 | https://www.inprocorp.com/products/extension-roller-333"
    )
    assert desc == "Inpro Extension Roller 333"
    assert url == "https://www.inprocorp.com/products/extension-roller-333"

    desc, url = split_description_url(
        "Alpaco Classic Collection. https://asi-accuratepartitions.com/products/alpaco-classic-collection/"
    )
    assert desc == "Alpaco Classic Collection."
    assert url == "https://asi-accuratepartitions.com/products/alpaco-classic-collection/"

    desc, url = split_description_url(
        "Ambassador surface cabinet",
        "https://www.activarcpg.com/product/ambassador-series-steel/",
    )
    assert desc == "Ambassador surface cabinet"
    assert url == "https://www.activarcpg.com/product/ambassador-series-steel/"

    desc, url = split_description_url(
        'Phenolic partitions. | https://www.hadrian-inc.com/us/en/products/toilet-partitions/phenolic.html | profile_height=58"'
    )
    assert desc == 'Phenolic partitions. | profile_height=58"'
    assert url == "https://www.hadrian-inc.com/us/en/products/toilet-partitions/phenolic.html"


def test_infer_catalog_product_url_known_manufacturers():
    assert (
        infer_catalog_product_url(manufacturer="Bobrick", item="253")
        == "https://www.bobrick.com/products/b-253"
    )
    assert (
        infer_catalog_product_url(manufacturer="Bobrick", item="150CX18.MBLK")
        == "https://www.bobrick.com/products/b-150cx18"
    )
    assert (
        infer_catalog_product_url(manufacturer="Bobrick", item="104 2448.MBLK")
        == "https://www.bobrick.com/products/b-104"
    )
    assert (
        infer_catalog_product_url(manufacturer="Bobrick", item="207x36")
        == "https://www.bobrick.com/products/b-207"
    )
    assert (
        infer_catalog_product_url(manufacturer="Koala Kare", item="KB112-01CT")
        == "https://www.koalabear.com/product-catalog/kb112-01ct/"
    )
    assert (
        infer_catalog_product_url(manufacturer="Gamco", item="G-16AP")
        == "https://gamcousa.com/products/product/g-16ap/"
    )
    assert "arise-whiteboard" in (
        infer_catalog_product_url(manufacturer="Claridge", item="CLAR-ARISE") or ""
    )
    assert "vanguard" in (
        infer_catalog_product_url(
            manufacturer="Penco",
            item="PENCO-6001V",
            description="Penco Vanguard. Locker.",
        )
        or ""
    )
    assert infer_catalog_product_url(manufacturer="Inpro", item="INPRO-333") is None
    assert (
        infer_catalog_product_url(manufacturer="Larsen", item="LARS-2409-R")
        == "https://www.larsensmfg.com/products/cabinets"
    )
