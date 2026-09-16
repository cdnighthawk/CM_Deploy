"""Claridge All Products crawl/parse helpers for the USIS_CM material catalog.

Website HTML and manufacturer PDFs are treated as data sources only. This module
never invents SKUs: only product codes published in Claridge spec tables (or
explicit comma-separated code cells) are imported as exact models.
"""
from __future__ import annotations

import html as html_lib
import re
from typing import Any
from urllib.parse import urljoin, urlparse

MANUFACTURER = "Claridge"
SOURCE_INDEX = "https://claridgeproducts.com/products/all-products/"
PRODUCT_SITEMAP = "https://claridgeproducts.com/product-sitemap.xml"
DOWNLOADS_SITEMAP = "https://claridgeproducts.com/downloads-claridge-sitemap.xml"
USER_AGENT = "USIS-CM-catalog-import/1.0 (+https://www.usiscm.com)"

# Configurable families that publish size/surface tables rather than a single SKU.
FAMILY_ONLY_NOTES = (
    "Claridge lists this as a configurable family. Exact finish/color/custom-size "
    "combinations are not published as individual SKUs on the product page."
)

_SKU_TOKEN_RE = re.compile(
    r"^[A-Z0-9][A-Z0-9._/-]{1,39}$",
    re.IGNORECASE,
)
_HAS_DIGIT_RE = re.compile(r"\d")
_TEMPLATE_RE = re.compile(r"XxX|X×X|GBXxX", re.IGNORECASE)
_NOTE_RE = re.compile(r"[=:]|hardboard|available upon|add to the product|number of tracks", re.I)

_SKIP_IMAGE_HINTS = (
    "downloads-icons",
    "3d-file",
    "guarantee-for-product",
    "glassguarantee",
    "favicon",
    "logo",
)

MARKER_HINTS = (
    "whiteboard",
    "markerboard",
    "marker board",
    "chalkboard",
    "chalk board",
    "marker wall",
    "graphic board",
    "glass",
    "lcs",
    "arise",
    "aspire",
    "porcelain",
    "ez fit",
    "wall-write",
    "wall write",
)
TACK_HINTS = ("tackboard", "tack board", "tack wall", "cork", "fabricork", "nucork", "bulletin board")
CASE_HINTS = ("display case", "bulletin board cabinet", "cabinet")
ACCESSORY_HINTS = (
    "tray",
    "marker",
    "eraser",
    "cleaner",
    "magnet",
    "cloth",
    "clip",
    "caddy",
    "accessory",
)
RAIL_HINTS = ("rail",)
SLIDING_HINTS = ("sliding",)


def unescape(text: str | None) -> str:
    if not text:
        return ""
    cleaned = html_lib.unescape(text)
    cleaned = re.sub(r"<[^>]+>", " ", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


def canonicalize_url(url: str | None, base: str | None = None) -> str | None:
    if not url:
        return None
    raw = html_lib.unescape(url.strip())
    if raw.startswith("//"):
        raw = "https:" + raw
    if base:
        raw = urljoin(base, raw)
    parsed = urlparse(raw)
    if parsed.scheme not in {"http", "https"}:
        return None
    path = parsed.path or "/"
    if path != "/" and path.endswith("/"):
        path = path
    query = f"?{parsed.query}" if parsed.query else ""
    return f"{parsed.scheme}://{parsed.netloc}{path}{query}"


def is_product_url(url: str | None) -> bool:
    if not url:
        return False
    parsed = urlparse(url)
    return parsed.netloc.endswith("claridgeproducts.com") and parsed.path.startswith("/product/")


def is_index_url(url: str | None) -> bool:
    if not url:
        return False
    parsed = urlparse(url)
    return parsed.netloc.endswith("claridgeproducts.com") and "/products/all-products" in parsed.path


def split_published_codes(raw: str | None) -> list[str]:
    """Split a spec-table Product Code cell into concrete published codes.

    Rejects sentences, templates (GBXxX…), and configuration notes. Does not
    expand undocumented suffix patterns such as Horizontal Sliding ``-2/-3/-4``.
    """
    text = unescape(raw)
    if not text or _NOTE_RE.search(text) or _TEMPLATE_RE.search(text):
        return []
    parts = re.split(r"\s*,\s*", text)
    out: list[str] = []
    seen: set[str] = set()
    for part in parts:
        token = part.strip().strip("\"'“”")
        if not token or " " in token:
            continue
        if not _SKU_TOKEN_RE.match(token):
            continue
        if not _HAS_DIGIT_RE.search(token):
            continue
        if _TEMPLATE_RE.search(token):
            continue
        key = token.upper()
        if key in seen:
            continue
        seen.add(key)
        out.append(token)
    return out


def classify_product(name: str, slug: str, option_group: str | None = None) -> tuple[str, str]:
    """Return (category, CSI 6-digit) from published names — no invented types."""
    blob = " ".join(x for x in (name, slug.replace("-", " "), option_group or "") if x).lower()
    option = (option_group or "").lower()

    if any(h in option for h in ("markerboard", "whiteboard", "chalkboard", "glass marker")):
        return "Markerboard", "101116"
    if any(h in option for h in ("tackboard", "cork", "fabric", "nucork")):
        return "Tackboard", "101123"

    if any(h in blob for h in CASE_HINTS) and "tackboard" not in blob:
        if "cabinet" in blob or "display case" in blob:
            return "Display Case", "101200"
    if any(h in blob for h in ACCESSORY_HINTS) and not any(
        h in blob for h in ("whiteboard", "markerboard", "marker wall", "graphic board")
    ):
        if any(h in blob for h in RAIL_HINTS):
            return "Visual Display Accessory", "101100"
        return "Markerboard Accessory", "101116"
    if any(h in blob for h in RAIL_HINTS) and "exhibit" in blob:
        return "Visual Display Accessory", "101100"
    if any(h in blob for h in TACK_HINTS) and not any(
        h in blob for h in ("markerboard", "whiteboard", "chalkboard", "series ")
    ):
        return "Tackboard", "101123"
    if any(h in blob for h in SLIDING_HINTS):
        return "Visual Display Board", "101100"
    if any(h in blob for h in MARKER_HINTS):
        return "Markerboard", "101116"
    if slug.startswith("series-") or "series " in blob:
        return "Visual Display Board", "101100"
    return "Visual Display Board", "101100"


def infer_mounting(*texts: str | None) -> str | None:
    """Mounting from product title/slug/codes only — not marketing phrases like 'writing surface'."""
    blob = " ".join(unescape(t) for t in texts if t).lower()
    mounts: list[str] = []
    checks = (
        ("invisi-mount", "Invisi-Mount"),
        ("invisimount", "Invisi-Mount"),
        ("mgmi", "Invisi-Mount"),
        ("through-glass", "Through-Glass Standoff"),
        ("through glass", "Through-Glass Standoff"),
        ("mgm-tg", "Through-Glass Standoff"),
        ("pgb-tg", "Through-Glass Standoff"),
        ("standoff edge", "Standoff"),
        ("stand-off", "Standoff"),
        ("freestanding", "Freestanding"),
        ("free-standing", "Freestanding"),
        ("semi-recessed", "Semi-recessed"),
        ("recessed", "Recessed"),
        ("surface-mount", "Surface"),
        ("surface mount", "Surface"),
        ("wall-mounted", "Wall-mounted"),
        ("wall mounted", "Wall-mounted"),
        ("z-bar", "Z-bar"),
    )
    for needle, label in checks:
        if needle in blob and label not in mounts:
            mounts.append(label)
    if "sliding" in blob and "Sliding" not in mounts:
        mounts.append("Sliding")
    if any(x in blob for x in ("map & display rail", "map and display rail", "exhibit rail", "hang-tight")):
        if "Map-rail" not in mounts:
            mounts.append("Map-rail")
    if any(x in blob for x in ("edge wrapped", "edge-wrapped", "frameless", "lcs elite")):
        if "Frameless" not in mounts:
            mounts.append("Frameless")
    if not mounts:
        return None
    return " / ".join(mounts[:4])


def family_item_name(title: str, slug: str) -> str:
    name = unescape(title) or slug.replace("-", " ").title()
    return name[:120]


def looks_like_product_image(url: str) -> bool:
    lower = url.lower()
    if not any(lower.endswith(ext) or f"{ext}?" in lower for ext in (".jpg", ".jpeg", ".png", ".webp", ".gif")):
        return False
    return not any(hint in lower for hint in _SKIP_IMAGE_HINTS)


def extract_index_tiles(html: str, page_url: str) -> list[dict[str, Any]]:
    tiles: list[dict[str, Any]] = []
    blocks = re.findall(
        r'<div class="col-sm-12 col-lg-4 product-tile-container[^"]*"[^>]*>.*?</a>\s*</div>',
        html,
        flags=re.S,
    )
    for block in blocks:
        href_m = re.search(r'href="([^"]+)"', block)
        href = canonicalize_url(href_m.group(1) if href_m else None, page_url)
        if not is_product_url(href):
            continue
        img_m = re.search(r'<img[^>]+src="([^"]+)"', block)
        alt_m = re.search(r'alt="([^"]*)"', block)
        name_m = re.search(r'<div class="product-name">\s*(.*?)\s*</div>', block, flags=re.S)
        desc_m = re.search(r'<div class="product-short-description">\s*(.*?)\s*</div>', block, flags=re.S)
        tiles.append(
            {
                "url": href,
                "name": unescape(name_m.group(1) if name_m else (alt_m.group(1) if alt_m else "")),
                "short_description": unescape(desc_m.group(1) if desc_m else ""),
                "image_url": canonicalize_url(img_m.group(1) if img_m else None, page_url),
                "type_ids": re.findall(r"product-type-(\d+)", block),
                "index_url": page_url,
            }
        )
    return tiles


def extract_pagination_urls(html: str, page_url: str) -> list[str]:
    found: list[str] = []
    for raw in re.findall(r'href="([^"]*all-products/page/\d+/[^"]*)"', html):
        url = canonicalize_url(raw, page_url)
        if url:
            found.append(url)
    if is_index_url(page_url):
        found.append(canonicalize_url("https://claridgeproducts.com/products/all-products/") or SOURCE_INDEX)
    # de-dupe preserve order
    out: list[str] = []
    seen: set[str] = set()
    for url in found:
        key = url.rstrip("/")
        if key in seen:
            continue
        seen.add(key)
        out.append(url)
    return out


def extract_sitemap_locs(xml: str) -> list[str]:
    return [html_lib.unescape(u) for u in re.findall(r"<loc>(https?://[^<]+)</loc>", xml)]


def extract_product_page(html: str, url: str) -> dict[str, Any]:
    title_m = re.search(r"<h1[^>]*>(.*?)</h1>", html, flags=re.S)
    title = unescape(title_m.group(1) if title_m else "")
    desc = ""
    body_m = re.search(r'<div class="product-description"[^>]*>(.*?)</div>', html, flags=re.S | re.I)
    if body_m:
        desc = unescape(body_m.group(1))
    if not desc:
        for pat in (
            r'<meta[^>]+property="og:description"[^>]+content="([^"]+)"',
            r'<meta[^>]+name="description"[^>]+content="([^"]+)"',
        ):
            m = re.search(pat, html, flags=re.I)
            if m:
                candidate = unescape(m.group(1))
                if candidate and "calyx" not in candidate.lower():
                    desc = candidate
                    break

    og_img = re.search(r'<meta[^>]+property="og:image"[^>]+content="([^"]+)"', html, flags=re.I)
    images: list[str] = []
    if og_img:
        img = canonicalize_url(og_img.group(1), url)
        if img and looks_like_product_image(img):
            images.append(img)
    for raw in re.findall(r'<img[^>]+src="([^"]+)"', html, flags=re.I):
        img = canonicalize_url(raw, url)
        if img and looks_like_product_image(img) and img not in images:
            images.append(img)

    documents: list[dict[str, str]] = []
    for raw in re.findall(r'href="([^"]+\.pdf[^"]*)"', html, flags=re.I):
        pdf = canonicalize_url(raw, url)
        if not pdf:
            continue
        label = "Spec sheet"
        if "tech" in pdf.lower() or "tech-data" in pdf.lower() or "tech_data" in pdf.lower():
            label = "Tech data"
        documents.append({"url": pdf, "label": label, "kind": "pdf"})
    # de-dupe docs
    seen_docs: set[str] = set()
    uniq_docs: list[dict[str, str]] = []
    for doc in documents:
        if doc["url"] in seen_docs:
            continue
        seen_docs.add(doc["url"])
        uniq_docs.append(doc)

    resource_links = []
    for raw in re.findall(r'href="(https://claridgeproducts.com/[^"]+)"', html):
        link = canonicalize_url(raw, url)
        if not link or is_product_url(link) or is_index_url(link):
            continue
        path = urlparse(link).path.lower()
        if any(x in path for x in ("/resources", "/download", "/3d-flip", "/wp-content/uploads")):
            resource_links.append(link)

    spec_rows, option_labels = _extract_spec_rows(html)
    bullets = []
    if body_m:
        bullets = [unescape(b) for b in re.findall(r"<li>(.*?)</li>", body_m.group(1), flags=re.S)]
    feature_bullets = [
        b
        for b in bullets
        if 12 < len(b) < 240
        and "cookie" not in b.lower()
        and "color_name_array" not in b
        and "how to specify" not in b.lower()
    ][:8]

    return {
        "url": url,
        "title": title,
        "description": desc,
        "images": images[:8],
        "documents": uniq_docs,
        "resource_links": sorted(set(resource_links)),
        "spec_rows": spec_rows,
        "option_labels": option_labels,
        "feature_bullets": feature_bullets,
        "published_skus": [row["sku"] for row in spec_rows],
    }


def _extract_spec_rows(html: str) -> tuple[list[dict[str, str]], list[str]]:
    rows: list[dict[str, str]] = []
    option_labels: list[str] = []
    current_option = ""
    pending: dict[str, str] = {"code": "", "size": "", "weight": ""}

    def flush() -> None:
        raw = pending["code"]
        if raw:
            for sku in split_published_codes(raw):
                rows.append(
                    {
                        "sku": sku,
                        "option_group": current_option,
                        "size": pending["size"],
                        "weight": pending["weight"],
                    }
                )
        pending["code"] = ""
        pending["size"] = ""
        pending["weight"] = ""

    for m in re.finditer(
        r'<div class="product-specs-(option|code|size|weight)[^"]*"[^>]*>\s*(.*?)\s*</div>',
        html,
        flags=re.S,
    ):
        kind = m.group(1)
        value = m.group(2)
        if kind == "option":
            flush()
            label = unescape(value)
            if label and len(label) < 200:
                option_labels.append(label)
            if label and len(label) < 160 and "=" not in label and "add to the product" not in label.lower():
                current_option = label
        elif kind == "code":
            flush()
            pending["code"] = value
        elif kind == "size":
            pending["size"] = unescape(value)
        elif kind == "weight":
            pending["weight"] = unescape(value)
    flush()

    out: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for row in rows:
        key = (row["sku"].upper(), row["option_group"])
        if key in seen:
            continue
        seen.add(key)
        out.append(row)
    seen_labels: set[str] = set()
    labels: list[str] = []
    for label in option_labels:
        if label in seen_labels:
            continue
        seen_labels.add(label)
        labels.append(label)
    return out, labels


def build_catalog_rows(product: dict[str, Any], tile: dict[str, Any] | None = None) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """Return (import rows, skipped/ambiguous records) for one product page."""
    title = product.get("title") or (tile or {}).get("name") or ""
    slug = urlparse(product["url"]).path.rstrip("/").split("/")[-1]
    family = family_item_name(title, slug)
    short = (tile or {}).get("short_description") or product.get("description") or ""
    bullets = product.get("feature_bullets") or []
    docs = product.get("documents") or []
    images = product.get("images") or []
    if tile and tile.get("image_url") and tile["image_url"] not in images:
        images = [tile["image_url"], *images]
    spec_pdf = next((d["url"] for d in docs if d.get("kind") == "pdf"), None)
    image_url = next((u for u in images if looks_like_product_image(u)), None)
    family_cat, family_csi = classify_product(title, slug)
    option_labels = product.get("option_labels") or [s.get("option_group") or "" for s in product.get("spec_rows") or []]
    mount = infer_mounting(title, short, slug.replace("-", " "))
    spec_rows: list[dict[str, str]] = product.get("spec_rows") or []
    skipped: list[dict[str, str]] = []

    def describe(extra: str = "") -> str:
        parts = [f"{family} (Claridge)."]
        if short:
            parts.append(short.rstrip(".") + ".")
        if extra:
            parts.append(extra.rstrip(".") + ".")
        if spec_pdf:
            parts.append(f"Spec sheet: {spec_pdf}.")
        if image_url:
            parts.append(f"Image: {image_url}.")
        if not spec_rows:
            parts.append(FAMILY_ONLY_NOTES)
        text = " ".join(parts)
        return text[:4000]

    rows: list[dict[str, str]] = [
        {
            "manufacturer": MANUFACTURER,
            "item": family,
            "category": family_cat,
            "csi_spec_section": family_csi,
            "description": describe("Product family / series listing from Claridge All Products."),
            "mounting_type": mount or "",
            "unit_of_measure": "EA",
            "currency": "USD",
            "url": product["url"],
            "row_kind": "family",
        }
    ]

    seen_skus: set[str] = {family.upper()}
    for spec in spec_rows:
        sku = spec["sku"]
        if sku.upper() in seen_skus:
            skipped.append(
                {
                    "sku": sku,
                    "url": product["url"],
                    "reason": "duplicate SKU on same or family name",
                }
            )
            continue
        seen_skus.add(sku.upper())
        cat, csi = classify_product(title, slug, spec.get("option_group"))
        extras = []
        if spec.get("option_group"):
            extras.append(spec["option_group"])
        if spec.get("size"):
            extras.append(f"Size {spec['size']}")
        if spec.get("weight"):
            extras.append(f"Weight {spec['weight']}")
        sku_mount = infer_mounting(mount, spec.get("sku"), slug.replace("-", " ")) or mount
        rows.append(
            {
                "manufacturer": MANUFACTURER,
                "item": sku[:120],
                "category": cat,
                "csi_spec_section": csi,
                "description": describe(" ".join(extras)),
                "mounting_type": sku_mount or "",
                "unit_of_measure": "EA",
                "currency": "USD",
                "url": product["url"],
                "row_kind": "sku",
            }
        )

    # Horizontal sliding publishes base codes plus a track-count note. Keep the
    # note as family documentation; do not synthesize HS46-2 / HS46-3 / HS46-4.
    page_text = " ".join(
        [
            product.get("description") or "",
            " ".join(option_labels),
            " ".join(s.get("option_group") or "" for s in spec_rows),
        ]
    )
    if re.search(r"-\s*2,\s*-\s*3,\s*or\s*-\s*4", page_text, flags=re.I):
        skipped.append(
            {
                "sku": "",
                "url": product["url"],
                "reason": "track-count suffixes -2/-3/-4 are documented as options, not explicit SKUs",
            }
        )
    if not spec_rows:
        skipped.append(
            {
                "sku": "",
                "url": product["url"],
                "reason": "configurable family or accessory with no published Product Code table",
            }
        )

    return rows, skipped


def dedupe_catalog_rows(rows: list[dict[str, str]]) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """Keep first (manufacturer, item); later collisions are skipped."""
    out: list[dict[str, str]] = []
    skipped: list[dict[str, str]] = []
    seen: set[str] = set()
    for row in rows:
        key = f"{row['manufacturer'].casefold()}::{row['item'].casefold()}"
        if key in seen:
            skipped.append(
                {
                    "sku": row["item"],
                    "url": row.get("url") or "",
                    "reason": "duplicate manufacturer+item after cross-product merge",
                }
            )
            continue
        seen.add(key)
        out.append(row)
    return out, skipped
