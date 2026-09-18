"""Copy SaaS admin HTML/JS into gulp/dist without a gulp-clean."""
from __future__ import annotations

from pathlib import Path

GULP = Path(__file__).resolve().parents[2] / "W3CRM-v3.0-13_September_2025" / "gulp"
SRC = GULP / "src"
DIST = GULP / "dist"

SETTINGS_MAIN = """<main class="content-body">
			<div class="page-title">
				<div class="row">
					<div class="col-auto me-auto">
						<ul class="breadcrumbs">
							<li><a href="usis-dashboard-dark.html">Home</a></li>
							<li><h1 data-i18n="Settings">Settings</h1></li>
						</ul>
					</div>
				</div>
			</div>
			<div class="container-fluid">
				<div class="usis-page-header mb-3">
					<div class="usis-page-header__text">
						<span class="usis-overline">Settings</span>
						<h1 class="h5 mb-1" id="usis-set-title">Settings</h1>
						<p class="text-muted small mb-0" id="usis-set-lead">Company controls for this tenant. Each topic opens one form.</p>
					</div>
					<div class="usis-page-header__actions" id="usis-set-actions"></div>
				</div>
				<div class="alert d-none py-2 px-3 mb-3" id="usis-set-flash" role="status"></div>
				<div id="usis-set-root"><p class="text-muted">Loading…</p></div>
			</div>
		</main>"""

ADMIN_MAIN = """<main class="content-body">
			<div class="page-title">
				<div class="row">
					<div class="col-auto me-auto">
						<ul class="breadcrumbs">
							<li><a href="usis-dashboard-dark.html">Home</a></li>
							<li><h1 data-i18n="Admin">Admin</h1></li>
						</ul>
					</div>
				</div>
			</div>
			<div class="container-fluid">
				<div class="alert alert-warning d-none py-2 px-3 mb-3" id="usis-adm-forbidden" role="alert">
					Platform operator required.
				</div>
				<div class="usis-page-header mb-3" id="usis-adm-header">
					<div class="usis-page-header__text">
						<span class="usis-overline">Admin</span>
						<h1 class="h5 mb-1" id="usis-adm-title">Admin</h1>
						<p class="text-muted small mb-0" id="usis-adm-lead">Tenants, plans, seats, flags, and impersonation.</p>
					</div>
					<div class="usis-page-header__actions" id="usis-adm-actions"></div>
				</div>
				<div class="alert d-none py-2 px-3 mb-3" id="usis-adm-flash" role="status"></div>
				<div id="usis-adm-kpis" class="row g-2 mb-3 d-none"></div>
				<div id="usis-adm-root"><p class="text-muted">Loading…</p></div>
			</div>
		</main>
	<div class="modal fade" id="usis-adm-reason-modal" tabindex="-1" aria-hidden="true">
		<div class="modal-dialog modal-dialog-centered">
			<div class="modal-content">
				<div class="modal-header">
					<h5 class="modal-title" id="usis-adm-reason-title">Confirm</h5>
					<button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
				</div>
				<div class="modal-body">
					<label class="form-label small" for="usis-adm-reason">Reason (required, at least 12 characters)</label>
					<textarea class="form-control form-control-sm" id="usis-adm-reason" rows="3"></textarea>
				</div>
				<div class="modal-footer">
					<button type="button" class="btn btn-sm btn-light" data-bs-dismiss="modal">Cancel</button>
					<button type="button" class="btn btn-sm btn-primary" id="usis-adm-reason-ok">Continue</button>
				</div>
			</div>
		</div>
	</div>"""

NAV_NEEDLE = """					<li>
						<a class="has-arrow" href="javascript:void(0);" aria-expanded="false">
							<i class="icon feather icon-settings"></i>
							<span class="nav-text" data-i18n="Admin">Admin</span>
						</a>"""

NAV_INSERT = """					<li data-usis-module="user_admin" id="usis-settings-nav">
						<a href="usis-settings.html">
							<i class="icon feather icon-sliders"></i>
							<span class="nav-text" data-i18n="Settings">Settings</span>
						</a>
					</li>
					<li data-usis-module="platform" id="usis-platform-admin-nav">
						<a href="usis-admin.html">
							<i class="icon feather icon-shield"></i>
							<span class="nav-text" data-i18n="Admin">Admin</span>
						</a>
					</li>
""" + NAV_NEEDLE


def swap_main(html: str, filename: str, script: str, main: str) -> str:
    html = html.replace("usis-platform-contractors.html", filename)
    start = html.find('<main class="content-body">')
    end = html.find("</main>")
    if start < 0 or end < 0:
        raise SystemExit("contractors dist html missing main")
    html = html[:start] + main + html[end + len("</main>") :]
    html = html.replace("assets/js/usis-platform-contractors.js", "assets/js/" + script)
    m0 = html.find('<div class="modal fade" id="usis-pc-modal"')
    marker = '<script src="assets/js/usis-auth-links.js">'
    m1 = html.find(marker)
    if m0 >= 0 and m1 > m0:
        html = html[:m0] + html[m1:]
    return html


def main() -> None:
    base = (DIST / "usis-platform-contractors.html").read_text(encoding="utf-8")
    (DIST / "usis-settings.html").write_text(
        swap_main(base, "usis-settings.html", "usis-settings.js", SETTINGS_MAIN),
        encoding="utf-8",
    )
    (DIST / "usis-admin.html").write_text(
        swap_main(base, "usis-admin.html", "usis-admin.js", ADMIN_MAIN),
        encoding="utf-8",
    )
    patched = 0
    for path in DIST.rglob("*.html"):
        text = path.read_text(encoding="utf-8")
        if 'id="usis-settings-nav"' in text:
            continue
        if NAV_NEEDLE not in text:
            continue
        path.write_text(text.replace(NAV_NEEDLE, NAV_INSERT, 1), encoding="utf-8")
        patched += 1
    idx = DIST / "usis-all-pages-index.html"
    if idx.is_file():
        text = idx.read_text(encoding="utf-8")
        old = '<li class="mb-2"><a href="usis-platform-contractors.html"><strong>USIS Contractors</strong></a>'
        new = (
            '<li class="mb-2"><a href="usis-settings.html"><strong>USIS Settings</strong></a> '
            '<span class="text-muted small">— Company topic list (logo, senders, PO bands).</span></li>\n'
            "\t\t\t\t\t<li class=\"mb-2\"><a href=\"usis-admin.html\"><strong>USIS Admin</strong></a> "
            '<span class="text-muted small">— Platform tenants, flags, impersonate.</span></li>\n'
            "\t\t\t\t\t" + old
        )
        if "usis-settings.html\"><strong>USIS Settings" not in text and old in text:
            idx.write_text(text.replace(old, new, 1), encoding="utf-8")
    print("dist html written, nav patched", patched)


if __name__ == "__main__":
    main()
