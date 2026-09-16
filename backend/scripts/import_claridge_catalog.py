"""Crawl Claridge All Products and write USIS_CM catalog seed files.

Usage (from backend/):

    python scripts/import_claridge_catalog.py --crawl
    python scripts/import_claridge_catalog.py --from-source

``--crawl`` fetches manufacturer pages and writes source JSON plus the
material_pricing CSV. ``--from-source`` rebuilds the CSV from the last crawl
without hitting the network.

Claridge HTML, sitemaps, and downloadable PDFs are treated as data only.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS = Path(__file__).resolve().parent
for _p in (_BACKEND_ROOT, _SCRIPTS):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from claridge_catalog import (  # noqa: E402
    DOWNLOADS_SITEMAP,
    PRODUCT_SITEMAP,
    SOURCE_INDEX,
    USER_AGENT,
    build_catalog_rows,
    canonicalize_url,
    dedupe_catalog_rows,
    extract_index_tiles,
    extract_pagination_urls,
    extract_product_page,
    extract_sitemap_locs,
    is_index_url,
    is_product_url,
)
from db_csv_paths import repo_catalog_dir  # noqa: E402

CSV_NAME = "claridge_visual_display.csv"
SOURCE_DIRNAME = "claridge_source"


def source_dir() -> Path:
    return repo_catalog_dir() / SOURCE_DIRNAME


def catalog_csv_path() -> Path:
    return repo_catalog_dir() / CSV_NAME


def _http_get(url: str, timeout: int = 45) -> tuple[int, str, str]:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xml;q=0.9,*/*;q=0.8",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            charset = resp.headers.get_content_charset() or "utf-8"
            return int(resp.status), resp.geturl(), raw.decode(charset, "replace")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace") if exc.fp else ""
        return int(exc.code), url, body


def crawl(delay_s: float = 0.25) -> dict:
    scanned: list[dict] = []
    pages: dict[str, str] = {}
    errors: list[dict[str, str]] = []

    def fetch(url: str, role: str) -> str | None:
        url = canonicalize_url(url) or url
        if url in pages:
            return pages[url]
        status, final, body = _http_get(url)
        scanned.append({"url": final or url, "requested": url, "status": status, "role": role})
        if status >= 400 or not body:
            errors.append({"url": url, "status": str(status), "role": role})
            return None
        pages[url] = body
        if delay_s:
            time.sleep(delay_s)
        return body

    index_urls = [SOURCE_INDEX]
    html = fetch(SOURCE_INDEX, "index")
    if html:
        for extra in extract_pagination_urls(html, SOURCE_INDEX):
            if extra not in index_urls:
                index_urls.append(extra)

    tiles_by_url: dict[str, dict] = {}
    index_pages_fetched = []
    for index_url in index_urls:
        page_html = html if index_url == SOURCE_INDEX else fetch(index_url, "index")
        if not page_html:
            continue
        index_pages_fetched.append(index_url)
        for tile in extract_index_tiles(page_html, index_url):
            tiles_by_url.setdefault(tile["url"], tile)
        for extra in extract_pagination_urls(page_html, index_url):
            if extra not in index_urls and is_index_url(extra) and len(index_urls) < 12:
                index_urls.append(extra)

    sitemap_products: list[str] = []
    sitemap_xml = fetch(PRODUCT_SITEMAP, "sitemap")
    if sitemap_xml:
        sitemap_products = [u for u in extract_sitemap_locs(sitemap_xml) if is_product_url(u)]

    download_urls: list[str] = []
    downloads_xml = fetch(DOWNLOADS_SITEMAP, "sitemap")
    if downloads_xml:
        download_urls = extract_sitemap_locs(downloads_xml)

    product_urls = list(tiles_by_url)
    for url in sitemap_products:
        if url not in tiles_by_url:
            product_urls.append(url)

    products: list[dict] = []
    for url in product_urls:
        page_html = fetch(url, "product")
        if not page_html:
            continue
        parsed = extract_product_page(page_html, url)
        parsed["on_all_products_index"] = url in tiles_by_url
        parsed["tile"] = tiles_by_url.get(url)
        products.append(parsed)

    # Follow product-linked resource/document pages once (not the generic
    # downloads archive disallowed by robots.txt).
    resource_pages = []
    seen_resources: set[str] = set()
    for product in products:
        for link in product.get("resource_links") or []:
            if link in seen_resources:
                continue
            path = link.lower()
            if "/downloads-claridge/" in path or "/resources-download/" in path:
                continue
            if link.endswith(".pdf") or any(link.lower().endswith(ext) for ext in (".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg")):
                continue
            seen_resources.add(link)
            res_html = fetch(link, "resource")
            if not res_html:
                continue
            pdfs = []
            for raw in re.findall(r'href="([^"]+\.pdf[^"]*)"', res_html, flags=re.I):
                pdf = canonicalize_url(raw, link)
                if pdf:
                    pdfs.append(pdf)
            resource_pages.append({"url": link, "pdfs": sorted(set(pdfs))[:40]})

    report = {
        "crawled_at": datetime.now(tz=timezone.utc).isoformat(),
        "source_index": SOURCE_INDEX,
        "index_pagination_note": (
            "Claridge All Products is a filterable archive: each /page/N/ HTML "
            "document repeats the same product-tile-container cards. Pagination "
            "was followed; unique products are de-duplicated by URL."
        ),
        "index_pages": index_pages_fetched,
        "index_pages_scanned": len(index_pages_fetched),
        "unique_index_tiles": len(tiles_by_url),
        "sitemap_product_urls": len(sitemap_products),
        "product_pages_ok": len(products),
        "download_sitemap_urls": len(download_urls),
        "resource_pages_followed": len(resource_pages),
        "http_requests": len(scanned),
        "http_errors": errors,
        "scanned_pages": scanned,
    }
    return {
        "report": report,
        "tiles": list(tiles_by_url.values()),
        "sitemap_products": sitemap_products,
        "download_urls": download_urls,
        "products": products,
        "resource_pages": resource_pages,
    }


def rows_from_source(source: dict) -> tuple[list[dict[str, str]], list[dict[str, str]], dict]:
    tiles = {t["url"]: t for t in source.get("tiles") or []}
    all_rows: list[dict[str, str]] = []
    skipped: list[dict[str, str]] = []
    families = 0
    exact_skus = 0
    for product in source.get("products") or []:
        rows, skip = build_catalog_rows(product, tiles.get(product["url"]) or product.get("tile"))
        all_rows.extend(rows)
        skipped.extend(skip)
        families += sum(1 for r in rows if r.get("row_kind") == "family")
        exact_skus += sum(1 for r in rows if r.get("row_kind") == "sku")
    catalog, dupes = dedupe_catalog_rows(all_rows)
    skipped.extend(dupes)
    stats = {
        "unique_products_or_families": families,
        "exact_skus_or_models": exact_skus,
        "catalog_rows_after_dedupe": len(catalog),
        "skipped_or_ambiguous": len(skipped),
        "family_rows": sum(1 for r in catalog if r.get("row_kind") == "family"),
        "sku_rows": sum(1 for r in catalog if r.get("row_kind") == "sku"),
    }
    return catalog, skipped, stats


def write_csv(rows: list[dict[str, str]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "Manufacturer",
        "Item",
        "Category",
        "CSI Spec Section",
        "Description",
        "Mounting Type",
        "Unit of Measure",
        "Currency",
        "URL",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for row in rows:
            w.writerow(
                {
                    "Manufacturer": row["manufacturer"],
                    "Item": row["item"],
                    "Category": row["category"],
                    "CSI Spec Section": row["csi_spec_section"],
                    "Description": row["description"],
                    "Mounting Type": row.get("mounting_type") or "",
                    "Unit of Measure": row.get("unit_of_measure") or "EA",
                    "Currency": row.get("currency") or "USD",
                    "URL": row.get("url") or "",
                }
            )


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def persist(source: dict, catalog: list[dict[str, str]], skipped: list[dict[str, str]], stats: dict) -> None:
    src = source_dir()
    src.mkdir(parents=True, exist_ok=True)
    write_json(src / "index_tiles.json", source.get("tiles") or [])
    write_json(src / "products.json", source.get("products") or [])
    write_json(
        src / "report.json",
        {
            **(source.get("report") or {}),
            "counts": stats,
            "skipped": skipped,
            "sitemap_products": source.get("sitemap_products") or [],
            "download_urls": source.get("download_urls") or [],
            "resource_pages": source.get("resource_pages") or [],
        },
    )
    write_csv(catalog, catalog_csv_path())


def load_source() -> dict:
    src = source_dir()
    products = json.loads((src / "products.json").read_text(encoding="utf-8"))
    tiles = json.loads((src / "index_tiles.json").read_text(encoding="utf-8"))
    report = {}
    report_path = src / "report.json"
    if report_path.is_file():
        report = json.loads(report_path.read_text(encoding="utf-8"))
    return {"products": products, "tiles": tiles, "report": report}


def main() -> int:
    parser = argparse.ArgumentParser(description="Import Claridge All Products into data/catalog.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--crawl", action="store_true", help="Fetch Claridge pages and write source + CSV.")
    mode.add_argument("--from-source", action="store_true", help="Rebuild CSV from claridge_source JSON.")
    parser.add_argument("--delay", type=float, default=0.25, help="Delay between HTTP requests (crawl).")
    args = parser.parse_args()

    if args.crawl:
        source = crawl(delay_s=args.delay)
    else:
        source = load_source()

    catalog, skipped, stats = rows_from_source(source)
    persist(source, catalog, skipped, stats)

    report = source.get("report") or {}
    print("Claridge catalog import")
    print(f"  index pages scanned:     {report.get('index_pages_scanned', '?')}")
    print(f"  unique All Products:     {report.get('unique_index_tiles', '?')}")
    print(f"  sitemap product URLs:    {report.get('sitemap_product_urls', '?')}")
    print(f"  product pages parsed:    {report.get('product_pages_ok', '?')}")
    print(f"  HTTP requests:           {report.get('http_requests', '?')}")
    print(f"  families / products:     {stats['unique_products_or_families']}")
    print(f"  exact SKUs / models:     {stats['exact_skus_or_models']}")
    print(f"  catalog rows (deduped):  {stats['catalog_rows_after_dedupe']}")
    print(f"  skipped / ambiguous:     {stats['skipped_or_ambiguous']}")
    print(f"  CSV: {catalog_csv_path()}")
    print(f"  source: {source_dir()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
