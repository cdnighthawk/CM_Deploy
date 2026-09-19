"""Manufacturer catalog URL parsing."""
from __future__ import annotations

import pytest

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
