#!/usr/bin/env python3
"""
Inject idempotent USIS site guide bars into first-party W3CRM HTML under gulp/src.

  python tools/apply_usis_site_guides.py --write-manifest   # (re)build tools/usis-site-pages.json
  python tools/apply_usis_site_guides.py --dry-run
  python tools/apply_usis_site_guides.py --apply

Regenerates `gulp/src/usis-all-pages-index.html` when using `--apply` or `--write-index` (not during `--dry-run`).
"""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
GULP_SRC = REPO_ROOT / "W3CRM-v3.0-13_September_2025" / "gulp" / "src"
MANIFEST_PATH = REPO_ROOT / "tools" / "usis-site-pages.json"
INDEX_REL = "usis-all-pages-index.html"
MARKER = 'id="usis-site-guide-root"'

# Optional per-page injection hint in manifest: try this strategy first.
# Values: page_title | content_body | auth_wrapper | body
INJECT_STRATEGIES = ("page_title", "content_body", "auth_wrapper", "body")

SUMMARY_BY_CATEGORY = {
    "usis": "USIS product or hub page. Use as a shell for live data and workflows; see Plan 20 for navigation.",
    "construction_demo": "Construction vertical demo from the W3CRM template. USIS may reuse layout patterns for jobs, RFIs, and estimates.",
    "auth": "Authentication or lock-screen template. USIS may replace branding and wire to your identity provider.",
    "ecom": "E-commerce demo template. Reference for catalog and checkout UI patterns.",
    "cms": "CMS / blog admin template. Reference for content editing shells.",
    "aikit": "AI kit demo pages. Reference for AI-related settings and prompts.",
    "account": "End-user account settings template (billing, security, API keys).",
    "profile": "User profile and social-style profile template.",
    "essentials": "Essentials / transaction partial or page from the template pack.",
    "template": "General W3CRM dashboard or utility page. Use as a layout reference or retire if unused.",
}


def discover_raw_paths() -> list[str]:
    """Paths relative to gulp/src per plan scope (before full-page filter)."""
    g = GULP_SRC
    out: list[str] = []
    out += sorted(p.relative_to(g).as_posix() for p in g.glob("*.html"))
    out += sorted(p.relative_to(g).as_posix() for p in (g / "construction").glob("*.html"))
    out += sorted(p.relative_to(g).as_posix() for p in (g / "profile").glob("*.html"))
    out += sorted(p.relative_to(g).as_posix() for p in (g / "account").glob("*.html"))
    out += sorted(p.relative_to(g).as_posix() for p in (g / "cms").glob("*.html"))
    out += sorted(p.relative_to(g).as_posix() for p in (g / "aikit").glob("*.html"))
    out += sorted(p.relative_to(g).as_posix() for p in g.glob("essentials/**/*.html"))
    return out


def is_full_html_file(abs_path: Path) -> bool:
    try:
        head = abs_path.read_text(encoding="utf-8", errors="replace")[:12000]
    except OSError:
        return False
    if "<!DOCTYPE" in head:
        return True
    return bool(re.search(r"<html[\s>]", head, re.I))


def discover_paths() -> list[str]:
    raw = discover_raw_paths()
    return [rel for rel in raw if is_full_html_file(GULP_SRC / rel)]


def order_paths(paths: list[str]) -> list[str]:
    """USIS root pages, then construction, then remainder; index page last."""
    usis = sorted(p for p in paths if "/" not in p and p.startswith("usis-"))
    con = sorted(p for p in paths if p.startswith("construction/"))
    rest = sorted(p for p in paths if p not in usis and p not in con)
    tail = [p for p in rest if p == INDEX_REL]
    rest = [p for p in rest if p != INDEX_REL]
    ordered = usis + con + rest + tail
    # Ensure index is present once at end when we add it to manifest without file yet
    if INDEX_REL not in ordered:
        ordered.append(INDEX_REL)
    return ordered


def human_title(rel: str) -> str:
    base = Path(rel).stem.replace("_", "-")
    parts = base.split("-")
    words: list[str] = []
    for w in parts:
        wl = w.lower()
        if wl in ("usis", "rfi", "rfis", "crm", "hr", "api", "bc", "rfp"):
            words.append(w.upper() if len(w) <= 4 else w.upper())
        elif wl == "ecom":
            words.append("E-commerce")
        else:
            words.append(w.capitalize())
    # Fix doubled casing
    t = " ".join(words)
    t = re.sub(r"\bUsis\b", "USIS", t)
    t = re.sub(r"\bRfi\b", "RFI", t)
    t = re.sub(r"\bRfis\b", "RFIs", t)
    t = re.sub(r"\bCrm\b", "CRM", t)
    t = re.sub(r"\bHr\b", "HR", t)
    t = re.sub(r"\bApi\b", "API", t)
    if rel.startswith("construction/"):
        return f"Construction — {t}"
    return t


def infer_category(rel: str) -> str:
    if rel == INDEX_REL or (rel.startswith("usis-") and "/" not in rel):
        return "usis"
    if rel.startswith("construction/"):
        return "construction_demo"
    if rel.startswith("cms/"):
        return "cms"
    if rel.startswith("aikit/"):
        return "aikit"
    if rel.startswith("account/"):
        return "account"
    if rel.startswith("profile/"):
        return "profile"
    if rel.startswith("essentials/"):
        return "essentials"
    base = Path(rel).name.lower()
    if base.startswith("page-") or "forgot-password" in base or "lock-screen" in base or "register" in base:
        return "auth"
    if base.startswith("ecom-"):
        return "ecom"
    return "template"


def default_summary(rel: str, category: str) -> str:
    extra = SUMMARY_BY_CATEGORY.get(category, SUMMARY_BY_CATEGORY["template"])
    if rel == INDEX_REL:
        return "Alphabetical tour of all first-party pages in this tree with one-line descriptions. Regenerate via tools/apply_usis_site_guides.py after adding pages."
    return extra


def build_default_manifest() -> dict[str, Any]:
    paths = discover_paths()
    # Per-file overrides for odd shells (error pages, auth).
    inject_hints: dict[str, str] = {}
    for rel in paths:
        base = Path(rel).name.lower()
        if base.startswith("page-error-"):
            inject_hints[rel] = "body"
    for rel in paths:
        p = GULP_SRC / rel
        text = p.read_text(encoding="utf-8", errors="replace")
        if "page-title" not in text and "content-body" not in text and "auth-wrapper" in text:
            inject_hints[rel] = "auth_wrapper"
        elif "page-title" not in text and "content-body" in text:
            inject_hints[rel] = "content_body"
        elif "page-title" not in text and "content-body" not in text and "auth-wrapper" not in text:
            if rel not in inject_hints:
                inject_hints[rel] = "body"

    ordered = order_paths(paths)
    # De-dupe while preserving order
    seen: set[str] = set()
    unique_ordered: list[str] = []
    for p in ordered:
        if p not in seen:
            seen.add(p)
            unique_ordered.append(p)

    entries: list[dict[str, Any]] = []
    for i, rel in enumerate(unique_ordered, start=1):
        cat = infer_category(rel)
        entry: dict[str, Any] = {
            "path": rel,
            "order": i,
            "title": human_title(rel),
            "summary": default_summary(rel, cat),
            "category": cat,
        }
        if rel in inject_hints:
            entry["injectAfter"] = inject_hints[rel]
        entries.append(entry)

    return {"version": 1, "indexPage": INDEX_REL, "pages": entries}


def load_manifest() -> dict[str, Any]:
    if not MANIFEST_PATH.is_file():
        print(f"Manifest missing: {MANIFEST_PATH}\nRun: python tools/apply_usis_site_guides.py --write-manifest", file=sys.stderr)
        sys.exit(1)
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def ordered_pages(data: dict[str, Any]) -> list[dict[str, Any]]:
    pages = list(data.get("pages", []))
    pages.sort(key=lambda x: (x.get("order", 0), x.get("path", "")))
    return pages


def rel_href(from_rel: str, to_rel: str) -> str:
    a = (GULP_SRC / from_rel).resolve().parent
    b = (GULP_SRC / to_rel).resolve()
    return Path(os.path.relpath(b, a)).as_posix()


def _inject_page_title(s: str, block: str) -> str | None:
    m = re.search(r'(?s)(<div\s+class=["\']page-title["\'][^>]*>.*?</div>)', s)
    if not m:
        return None
    i = m.end()
    return s[:i] + "\n\n" + block + s[i:]


def _inject_content_body(s: str, block: str) -> str | None:
    m = re.search(r'(<main\b[^>]*\bclass="[^"]*content-body[^"]*"[^>]*>)(\s*)', s)
    if not m:
        return None
    return s[: m.end()] + "\n" + block + s[m.end() :]


def _inject_auth_wrapper(s: str, block: str) -> str | None:
    m = re.search(r'(<div\s+class="auth-wrapper"[^>]*>)(\s*)', s)
    if not m:
        return None
    return s[: m.end()] + "\n" + block + s[m.end() :]


def _inject_body(s: str, block: str) -> str | None:
    m = re.search(r"(<body[^>]*>)(\s*)", s, re.I)
    if not m:
        return None
    return s[: m.end()] + "\n" + block + s[m.end() :]


_STRATEGY_FNS = {
    "page_title": _inject_page_title,
    "content_body": _inject_content_body,
    "auth_wrapper": _inject_auth_wrapper,
    "body": _inject_body,
}


def inject_block(html: str, block: str, preferred: str | None) -> tuple[str | None, str]:
    """Return (new_html, strategy_used) or (None, reason)."""
    order = list(INJECT_STRATEGIES)
    if preferred in _STRATEGY_FNS:
        order = [preferred] + [x for x in order if x != preferred]
    # Never insert at top of <main> if a page-title block exists (would render above the title).
    has_page_title = re.search(r'<div\s+class=["\']page-title["\']', html) is not None
    if has_page_title:
        order = [x for x in order if x != "content_body"]
    for name in order:
        fn = _STRATEGY_FNS[name]
        out = fn(html, block)
        if out is not None:
            return out, name
    return None, "no_anchor"


def build_guide_block(
    *,
    title: str,
    summary: str,
    href_prev: str,
    href_index: str,
    href_next: str,
) -> str:
    te = html.escape(title)
    se = html.escape(summary)
    return f'''\t\t\t<div {MARKER} class="container-fluid mb-3 px-0">
\t\t\t\t<div class="card border-info shadow-none mb-0">
\t\t\t\t\t<div class="card-body py-2">
\t\t\t\t\t\t<div class="d-flex flex-wrap justify-content-between align-items-start gap-2">
\t\t\t\t\t\t\t<div class="me-2">
\t\t\t\t\t\t\t\t<h6 class="mb-1">{te}</h6>
\t\t\t\t\t\t\t\t<p class="text-muted small mb-0">{se}</p>
\t\t\t\t\t\t\t</div>
\t\t\t\t\t\t\t<div class="text-nowrap small">
\t\t\t\t\t\t\t\t<a href="{html.escape(href_prev, quote=True)}">Prev</a><span class="text-muted mx-1">|</span><a href="{html.escape(href_index, quote=True)}">Index</a><span class="text-muted mx-1">|</span><a href="{html.escape(href_next, quote=True)}">Next</a>
\t\t\t\t\t\t\t</div>
\t\t\t\t\t\t</div>
\t\t\t\t\t\t<p class="text-muted small mt-2 mb-0">Plan reference: USIS Plan 20 — Site map and navigation (repository documentation).</p>
\t\t\t\t\t</div>
\t\t\t\t</div>
\t\t\t</div>'''


def write_all_pages_index(pages: list[dict[str, Any]]) -> None:
    """Write gulp/src/usis-all-pages-index.html (construction shell)."""
    by_cat: dict[str, list[dict[str, Any]]] = {}
    for p in pages:
        if p.get("path") == INDEX_REL:
            continue
        c = p.get("category") or "template"
        by_cat.setdefault(c, []).append(p)
    for c in by_cat:
        by_cat[c].sort(key=lambda x: (x.get("order", 0), x.get("path", "")))

    cat_order = ["usis", "construction_demo", "auth", "ecom", "cms", "aikit", "account", "profile", "essentials", "template"]
    cat_labels = {
        "usis": "USIS product & hubs",
        "construction_demo": "Construction demos",
        "auth": "Authentication",
        "ecom": "E-commerce demos",
        "cms": "CMS",
        "aikit": "AI kit",
        "account": "Account",
        "profile": "Profile",
        "essentials": "Essentials",
        "template": "Other template pages",
    }

    body_parts: list[str] = []
    body_parts.append(
        '\t\t\t<div class="page-title">\n'
        '\t\t\t\t@@include("elements/breadcrumb.html", {\n'
        '\t\t\t\t\t"fileName": "All pages (tour)",\n'
        '\t\t\t\t})\n'
        "\t\t\t</div>\n"
        '\t\t\t<div class="container-fluid">\n'
        '\t\t\t\t<div class="card mb-3">\n'
        '\t\t\t\t\t<div class="card-body">\n'
        '\t\t\t\t\t\t<h5 class="card-title">First-party HTML index</h5>\n'
        '\t\t\t\t\t\t<p class="text-muted small mb-0">Each in-scope page under <code>gulp/src</code> has a site guide bar with Prev / Index / Next. Regenerate this file with '
        "<code>python tools/apply_usis_site_guides.py --apply</code> or <code>--write-index</code> after editing <code>tools/usis-site-pages.json</code>.</p>\n"
        "\t\t\t\t\t</div>\n"
        "\t\t\t\t</div>\n"
    )

    for cat in cat_order:
        items = by_cat.get(cat) or []
        if not items:
            continue
        label = cat_labels.get(cat, cat)
        body_parts.append(f'\t\t\t\t<h5 class="mt-2">{html.escape(label)}</h5>\n')
        body_parts.append('\t\t\t\t<ul class="list-unstyled">\n')
        for ent in items:
            path = ent["path"]
            title = html.escape(ent.get("title") or path)
            summary = html.escape(ent.get("summary") or "")
            href = html.escape(path, quote=True)
            body_parts.append(
                f'\t\t\t\t\t<li class="mb-2"><a href="{href}"><strong>{title}</strong></a>'
                f' <span class="text-muted small">— {summary}</span></li>\n'
            )
        body_parts.append("\t\t\t\t</ul>\n")

    body_parts.append("\t\t\t</div>\n")

    content = "".join(body_parts)

    doc = f"""<!DOCTYPE html>
<html lang="en">
<head>

\t@@include("elements/meta.html", {{
\t\t"fileName": "{INDEX_REL}",
\t}})

\t<link class="main-plugins" href="assets/css/plugins.css" rel="stylesheet">
\t<link class="main-css" href="assets/css/style.css" rel="stylesheet">

</head>
<body>

\t@@include("elements/preloader.html")

\t<div id="main-wrapper">

\t\t@@include("elements/nav-header-construction.html")

\t\t@@include("elements/chatbox-construction.html")

\t\t@@include("elements/header-construction.html")

\t\t@@include("elements/deznav-construction.html")

\t\t<main class="content-body">

{content}
\t\t</main>

\t\t@@include("elements/footer.html")

\t</div>

\t@@include("elements/script.html")

\t<script src="assets/vendor/i18n/i18n.js"></script>
\t<script src="assets/js/translator.js"></script>
\t<script src="assets/js/aiReviewBus.js"></script>
\t<script src="assets/js/usis-notify.js"></script>
\t<script src="assets/js/usis-project-context.js"></script>
\t<script src="assets/js/usis-command-palette.js"></script>
\t<script src="assets/js/deznav-init-construction.js"></script>
\t<script src="assets/js/custom.js"></script>
\t<script src="assets/js/construction.js"></script>

</body>
</html>
"""
    out_path = GULP_SRC / INDEX_REL
    out_path.write_text(doc, encoding="utf-8", newline="\n")
    print(f"Wrote {out_path.relative_to(REPO_ROOT)}")


def process_pages(*, apply: bool, write_index: bool) -> int:
    data = load_manifest()
    pages = ordered_pages(data)
    paths = [p["path"] for p in pages]
    if not paths:
        print("Manifest has no pages.", file=sys.stderr)
        return 2

    if write_index:
        write_all_pages_index(pages)

    n_skip_marker = 0
    n_skip_missing = 0
    n_inject = 0
    n_fail = 0

    for i, ent in enumerate(pages):
        rel = ent["path"]
        abs_path = GULP_SRC / rel
        if not abs_path.is_file():
            print(f"SKIP missing file: {rel}")
            n_skip_missing += 1
            continue
        text = abs_path.read_text(encoding="utf-8", errors="replace")
        if MARKER in text:
            n_skip_marker += 1
            continue

        prev_rel = paths[(i - 1) % len(paths)]
        next_rel = paths[(i + 1) % len(paths)]
        idx_rel = data.get("indexPage") or INDEX_REL
        href_prev = rel_href(rel, prev_rel)
        href_next = rel_href(rel, next_rel)
        href_index = rel_href(rel, idx_rel)

        block = build_guide_block(
            title=str(ent.get("title") or human_title(rel)),
            summary=str(ent.get("summary") or default_summary(rel, str(ent.get("category") or "template"))),
            href_prev=href_prev,
            href_index=href_index,
            href_next=href_next,
        )
        preferred = ent.get("injectAfter")
        if preferred not in (None, *INJECT_STRATEGIES):
            print(f"WARN {rel}: unknown injectAfter {preferred!r}, using defaults", file=sys.stderr)
            preferred = None

        new_text, strat = inject_block(text, block, preferred)
        if new_text is None:
            print(f"FAIL no anchor: {rel}")
            n_fail += 1
            continue
        n_inject += 1
        action = "would inject" if not apply else "injected"
        print(f"{action}: {rel} (via {strat})")
        if apply:
            abs_path.write_text(new_text, encoding="utf-8", newline="\n")

    print(
        f"\nSummary: inject={n_inject}, skip_marker={n_skip_marker}, "
        f"missing={n_skip_missing}, fail={n_fail}, apply={apply}"
    )
    return 1 if n_fail else 0


def cmd_write_manifest(_: argparse.Namespace) -> int:
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    blob = build_default_manifest()
    MANIFEST_PATH.write_text(json.dumps(blob, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {MANIFEST_PATH} ({len(blob['pages'])} pages)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="USIS site guide bar injector")
    ap.add_argument("--write-manifest", action="store_true", help="Rebuild tools/usis-site-pages.json from gulp/src scan")
    ap.add_argument("--dry-run", action="store_true", help="Show injections without writing")
    ap.add_argument("--apply", action="store_true", help="Write injections and regenerate index HTML")
    ap.add_argument("--write-index", action="store_true", help="Only rewrite usis-all-pages-index.html from manifest")
    args = ap.parse_args()

    if args.write_manifest:
        return cmd_write_manifest(args)

    if args.write_index:
        data = load_manifest()
        write_all_pages_index(ordered_pages(data))
        return 0

    if args.dry_run or args.apply:
        return process_pages(apply=args.apply, write_index=args.apply)

    ap.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
