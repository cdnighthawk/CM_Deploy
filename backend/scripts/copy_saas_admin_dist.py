"""Copy SaaS admin HTML/JS into gulp/dist without a gulp-clean."""
from __future__ import annotations

import shutil
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
				<div class="usis-console">
					<nav class="usis-console-rail" id="usis-set-rail" aria-label="Settings"></nav>
					<div class="usis-console-main">
						<div class="usis-page-header mb-3">
							<div class="usis-page-header__text">
								<span class="usis-overline">Settings</span>
								<h1 class="h5 mb-1" id="usis-set-title">Settings</h1>
								<p class="text-muted small mb-0" id="usis-set-lead">Company admin for this organization.</p>
							</div>
							<div class="usis-page-header__actions" id="usis-set-actions"></div>
						</div>
						<div class="alert d-none py-2 px-3 mb-3" id="usis-set-flash" role="status"></div>
						<div id="usis-set-root"><p class="text-muted">Loading…</p></div>
					</div>
				</div>
			</div>
		</main>
	<div class="modal fade" id="usis-set-invite-modal" tabindex="-1" aria-hidden="true">
		<div class="modal-dialog modal-dialog-centered">
			<div class="modal-content">
				<div class="modal-header">
					<h5 class="modal-title">Invite user</h5>
					<button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
				</div>
				<div class="modal-body">
					<div class="mb-3">
						<label class="form-label small" for="usis-set-inv-email">Email</label>
						<input class="form-control form-control-sm" id="usis-set-inv-email" type="email" autocomplete="off">
					</div>
					<div class="row g-2 mb-3">
						<div class="col-md-6">
							<label class="form-label small" for="usis-set-inv-first">First</label>
							<input class="form-control form-control-sm" id="usis-set-inv-first">
						</div>
						<div class="col-md-6">
							<label class="form-label small" for="usis-set-inv-last">Last</label>
							<input class="form-control form-control-sm" id="usis-set-inv-last">
						</div>
					</div>
					<div class="mb-3">
						<label class="form-label small" for="usis-set-inv-role">Role template</label>
						<select class="form-select form-select-sm" id="usis-set-inv-role"></select>
					</div>
					<div class="mb-0">
						<label class="form-label small" for="usis-set-inv-seat">Seat</label>
						<select class="form-select form-select-sm" id="usis-set-inv-seat">
							<option value="office">Office</option>
							<option value="field">Field</option>
						</select>
					</div>
				</div>
				<div class="modal-footer">
					<button type="button" class="btn btn-sm btn-light" data-bs-dismiss="modal">Cancel</button>
					<button type="button" class="btn btn-sm btn-primary" id="usis-set-inv">Send invite</button>
				</div>
			</div>
		</div>
	</div>
	<div class="modal fade" id="usis-set-roles-modal" tabindex="-1" aria-hidden="true">
		<div class="modal-dialog modal-dialog-centered">
			<div class="modal-content">
				<div class="modal-header">
					<h5 class="modal-title" id="usis-set-roles-title">Assign roles</h5>
					<button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
				</div>
				<div class="modal-body" id="usis-set-roles-body"></div>
				<div class="modal-footer">
					<button type="button" class="btn btn-sm btn-light" data-bs-dismiss="modal">Cancel</button>
					<button type="button" class="btn btn-sm btn-primary" id="usis-set-roles-ok">Save</button>
				</div>
			</div>
		</div>
	</div>"""

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
				<div class="usis-console">
					<nav class="usis-console-rail" id="usis-adm-rail" aria-label="Admin"></nav>
					<div class="usis-console-main">
						<div class="usis-page-header mb-3" id="usis-adm-header">
							<div class="usis-page-header__text">
								<span class="usis-overline">Admin</span>
								<h1 class="h5 mb-1" id="usis-adm-title">Admin</h1>
								<p class="text-muted small mb-0" id="usis-adm-lead">Platform operations for every organization.</p>
							</div>
							<div class="usis-page-header__actions" id="usis-adm-actions"></div>
						</div>
						<div class="alert d-none py-2 px-3 mb-3" id="usis-adm-flash" role="status"></div>
						<div id="usis-adm-kpis" class="row g-2 mb-3 d-none"></div>
						<div id="usis-adm-root"><p class="text-muted">Loading…</p></div>
					</div>
				</div>
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
						<a href="/settings">
							<i class="icon feather icon-sliders"></i>
							<span class="nav-text" data-i18n="Settings">Settings</span>
						</a>
					</li>
					<li data-usis-module="platform" id="usis-platform-admin-nav">
						<a href="/admin">
							<i class="icon feather icon-shield"></i>
							<span class="nav-text" data-i18n="Admin">Admin</span>
						</a>
					</li>
""" + NAV_NEEDLE


def swap_main(html: str, filename: str, script: str, main: str) -> str:
    html = html.replace("usis-platform-contractors.html", filename)
    html = html.replace(
        f'href="{filename}" data-i18n="Contractors">Contractors',
        'href="usis-platform-contractors.html" data-i18n="Contractors">Contractors',
    )
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


def ensure_root_asset_base(html: str) -> str:
    """Console shells are served under /settings/* and /admin/*; relative assets 404."""
    if '<base href="/">' not in html and "<base href='/'>" not in html:
        html = html.replace("<head>", '<head>\n\t<base href="/">', 1)
    html = html.replace('href="assets/css/style.css"', 'href="/assets/css/style.css"')
    html = html.replace('href="assets/css/usis-ui.css"', 'href="/assets/css/usis-ui.css"')
    html = html.replace('src="assets/js/usis-theme-boot.js"', 'src="/assets/js/usis-theme-boot.js"')
    html = html.replace('src="assets/js/usis-theme-boot.js?', 'src="/assets/js/usis-theme-boot.js?')
    style_tag = '<link class="main-css" href="/assets/css/style.css" rel="stylesheet">'
    ui_after_style = style_tag + '\n\t<link href="/assets/css/usis-ui.css" rel="stylesheet">'
    if style_tag in html and ui_after_style not in html:
        html = html.replace(style_tag, ui_after_style, 1)
    return html


def _copy_assets() -> None:
    for rel in (
        "assets/js/usis-settings.js",
        "assets/js/usis-admin.js",
        "assets/js/usis-auth-links.js",
        "assets/js/usis-nav-access.js",
        "assets/js/usis-theme-boot.js",
        "assets/css/usis-ui.css",
        "elements/deznav-construction.html",
    ):
        src = SRC / rel
        dest = DIST / rel
        if src.is_file() and dest.parent.is_dir():
            dest.parent.mkdir(parents=True, exist_ok=True)
            if rel.startswith("assets/"):
                shutil.copyfile(src, dest)


def main() -> None:
    _copy_assets()
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
        orig = text
        if 'id="usis-settings-nav"' not in text and NAV_NEEDLE in text:
            text = text.replace(NAV_NEEDLE, NAV_INSERT, 1)
        text = text.replace(
            'id="usis-settings-nav">\n\t\t\t\t\t\t<a href="usis-settings.html">',
            'id="usis-settings-nav">\n\t\t\t\t\t\t<a href="/settings">',
        )
        text = text.replace(
            'id="usis-platform-admin-nav">\n\t\t\t\t\t\t<a href="usis-admin.html">',
            'id="usis-platform-admin-nav">\n\t\t\t\t\t\t<a href="/admin">',
        )
        text = text.replace(
            'href="usis-user-directory.html" data-i18n="User admin">User admin',
            'href="/settings/people" data-i18n="People & access">People & access',
        )
        if text != orig:
            path.write_text(text, encoding="utf-8")
            patched += 1
    idx = DIST / "usis-all-pages-index.html"
    if idx.is_file():
        text = idx.read_text(encoding="utf-8")
        old = '<li class="mb-2"><a href="usis-platform-contractors.html"><strong>USIS Contractors</strong></a>'
        new = (
            '<li class="mb-2"><a href="usis-settings.html"><strong>USIS Settings</strong></a> '
            '<span class="text-muted small">— Contractor console (14 sections).</span></li>\n'
            "\t\t\t\t\t<li class=\"mb-2\"><a href=\"usis-admin.html\"><strong>USIS Admin</strong></a> "
            '<span class="text-muted small">— Platform tenants, flags, impersonate.</span></li>\n'
            "\t\t\t\t\t" + old
        )
        if "usis-settings.html\"><strong>USIS Settings" not in text and old in text:
            idx.write_text(text.replace(old, new, 1), encoding="utf-8")
    for name in ("usis-settings.html", "usis-admin.html", "usis-profile.html"):
        page = DIST / name
        if page.is_file():
            page.write_text(ensure_root_asset_base(page.read_text(encoding="utf-8")), encoding="utf-8")
    print("dist html written, nav patched", patched)


if __name__ == "__main__":
    main()
