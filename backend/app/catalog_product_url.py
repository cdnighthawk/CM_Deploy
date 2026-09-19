"""Infer official manufacturer product pages for catalog rows missing a URL."""
from __future__ import annotations

import re

from .material_url import normalize_manufacturer_url

_BOBRICK_COLOR = re.compile(r"\.[A-Z]{1,6}$", re.IGNORECASE)
_BOBRICK_VOLT = re.compile(r"(?:\s+|-)\d{2,3}V\b", re.IGNORECASE)
_SIZE_TAIL = re.compile(r"(?<=\d)x\d+(?:\.\d+)?$", re.IGNORECASE)

_CLARIDGE_PAGES = (
    ("arise", "https://claridgeproducts.com/product/arise-whiteboard/"),
    ("aspire", "https://claridgeproducts.com/product/aspire-whiteboard/"),
    ("grain", "https://claridgeproducts.com/product/grain-whiteboard/"),
    ("envision", "https://claridgeproducts.com/product/envision-graphic-board/"),
    ("concept", "https://claridgeproducts.com/product/lcs-deluxe-porcelain-whiteboards/"),
    ("lcs", "https://claridgeproducts.com/product/lcs-deluxe-porcelain-whiteboards/"),
    ("glass", "https://claridgeproducts.com/product/claridge-glass-whiteboard/"),
    ("tableau", "https://claridgeproducts.com/product/tableau/"),
    ("xchange", "https://claridgeproducts.com/product/xchange-graphic-board/"),
)

_ASI_PARTITION_PAGES = (
    ("alpaco-cl", "https://asi-accuratepartitions.com/products/alpaco-classic-collection/"),
    ("alpaco-el", "https://asi-accuratepartitions.com/products/alpaco-elegance-partitions/"),
    ("hdpe", "https://asi-accuratepartitions.com/products/solid-plastic-hdpe/"),
    ("us-hdpe", "https://asi-accuratepartitions.com/products/solid-plastic-hdpe/"),
    ("max-priv", "https://asi-accuratepartitions.com/products/maximum-privacy-phenolic/"),
    ("phen-bc", "https://asi-accuratepartitions.com/products/black-core-phenolic/"),
    ("phen-ct", "https://asi-accuratepartitions.com/products/color-thru-phenolic/"),
    ("pc-steel", "https://asi-accuratepartitions.com/products/powder-coated-steel/"),
    ("us-pc", "https://asi-accuratepartitions.com/products/powder-coated-steel/"),
    ("pl-mg", "https://asi-accuratepartitions.com/products/plastic-laminate/"),
    ("ss", "https://asi-accuratepartitions.com/products/stainless-steel/"),
    ("us-ss", "https://asi-accuratepartitions.com/products/stainless-steel/"),
    ("us-phen", "https://asi-accuratepartitions.com/products/black-core-phenolic/"),
)

_PENCO_SERIES = (
    ("vanguard", "https://www.pencoproducts.com/products/lockers/vanguard-metal-storage-lockers"),
    ("guardian", "https://www.pencoproducts.com/products/lockers/guardian-employee-lockers"),
    ("invincible", "https://www.pencoproducts.com/products/lockers/invincible-ii-metal-gym-lockers"),
    ("garment dispenser", "https://www.pencoproducts.com/products/garment-dispensers/garment-lockers"),
    ("garment locker", "https://www.pencoproducts.com/products/garment-dispensers/garment-lockers"),
    ("accessory", "https://www.pencoproducts.com/products/lockers"),
    ("bench", "https://www.pencoproducts.com/products/lockers"),
)


def infer_catalog_product_url(
    *,
    manufacturer: str | None,
    item: str | None,
    category: str | None = None,
    description: str | None = None,
) -> str | None:
    """Return an official product/series page when the catalog row has none."""
    mfr = (manufacturer or "").strip().lower()
    sku = (item or "").strip()
    if not mfr or not sku:
        return None
    blob = f"{sku} {category or ''} {description or ''}".lower()
    raw: str | None = None
    if mfr == "bobrick":
        raw = _bobrick_url(sku)
    elif mfr == "koala kare":
        raw = f"https://www.koalabear.com/product-catalog/{sku.lower()}/"
    elif mfr == "gamco":
        raw = f"https://gamcousa.com/products/product/{_slug(sku)}/"
    elif mfr == "claridge":
        raw = _first_match(blob, _CLARIDGE_PAGES) or "https://claridgeproducts.com/products/whiteboards/"
    elif mfr == "penco":
        raw = _first_match(blob, _PENCO_SERIES) or "https://www.pencoproducts.com/products/lockers"
    elif mfr == "hollman":
        raw = (
            "https://hollman.com/glass-lockers/"
            if "glass" in blob
            else "https://hollman.com/locker-models/"
        )
    elif mfr == "columbia":
        raw = (
            "https://psisc.com/sub.asp?pg=Lockers-Polylife"
            if "polylife" in blob or "hdpe" in blob
            else "https://psisc.com/sub.asp?pg=Lockers"
        )
    elif mfr == "asi":
        raw = _asi_url(sku, blob)
    elif mfr in ("larsen", "larsens", "larsen's"):
        raw = "https://www.larsensmfg.com/products/cabinets"
    if not raw:
        return None
    try:
        return normalize_manufacturer_url(raw)
    except ValueError:
        return None


def _slug(item: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", item.strip().lower()).strip("-")


def _first_match(blob: str, pairs: tuple[tuple[str, str], ...]) -> str | None:
    for key, url in pairs:
        if key in blob:
            return url
    return None


def _bobrick_url(item: str) -> str:
    upper = item.upper()
    if upper.startswith("BOB-") or "PARTITION" in upper:
        return "https://www.bobrick.com/products/toilet-partitions/"
    model = item.strip()
    head, _, tail = model.partition(" ")
    if tail and re.match(r"^\d", tail):
        model = head
    model = _BOBRICK_COLOR.sub("", model)
    model = _BOBRICK_VOLT.sub("", model)
    model = re.sub(r"\s+", "", model)
    if _SIZE_TAIL.search(model):
        model = _SIZE_TAIL.sub("", model)
    if not re.match(r"^B-?", model, re.IGNORECASE):
        model = "B-" + model
    elif model.upper().startswith("B") and not model.upper().startswith("B-"):
        model = "B-" + model[1:]
    return f"https://www.bobrick.com/products/{model.lower()}"


def _asi_url(item: str, blob: str) -> str:
    sku = item.lower()
    if "partition" in blob or sku.startswith("asi-us-") or sku.startswith("asi-alpaco"):
        key = sku.removeprefix("asi-")
        return _first_match(key, _ASI_PARTITION_PAGES) or (
            "https://asi-accuratepartitions.com/products/"
        )
    if "locker" in blob:
        return "https://americanspecialties.com/"
    return "https://asi-visualdisplayproducts.com/"
