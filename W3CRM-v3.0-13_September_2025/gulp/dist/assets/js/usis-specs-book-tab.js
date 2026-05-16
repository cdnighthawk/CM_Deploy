/**
 * Procore-style specs book: division tree (CSI codes), PDF pane, link PDF URL per section.
 * Mount with USISSpecsBook.mount(containerElement, projectId).
 */
(function (global) {
	"use strict";

	function metaApiBase() {
		var m = document.querySelector('meta[name="usis-api-base"]');
		if (!m) return null;
		var c = (m.getAttribute("content") || "").trim().replace(/\/$/, "");
		return c || null;
	}

	function apiBase() {
		var loc = global.location;
		var devPorts = {
			3000: 1,
			3001: 1,
			3002: 1,
			4173: 1,
			5173: 1,
			5174: 1,
			5500: 1,
			5501: 1,
			8080: 1,
			4200: 1,
			4321: 1,
			9630: 1,
			1234: 1,
		};

		function isLoopbackHost(h) {
			return h === "localhost" || h === "127.0.0.1" || h === "[::1]" || h === "::1";
		}

		function flaskDevBase() {
			if (loc.protocol === "file:") {
				return "http://127.0.0.1:5000";
			}
			var host = loc.hostname || "";
			var proto = loc.protocol || "http:";
			var port = String(loc.port || "");
			if (devPorts[port]) {
				return proto + "//" + host + ":5000";
			}
			var loopback = host === "localhost" || host === "127.0.0.1" || host === "::1";
			if (loopback) {
				if (port === "5000") {
					return "";
				}
				return proto + "//" + host + ":5000";
			}
			var ipv4 = /^\d{1,3}(\.\d{1,3}){3}$/.test(host);
			if (ipv4 && port && port !== "5000" && port !== "80" && port !== "443") {
				return proto + "//" + host + ":5000";
			}
			if ((host === "host.docker.internal" || host.endsWith(".local")) && port && port !== "5000") {
				return proto + "//" + host + ":5000";
			}
			return "";
		}

		function resolveOverride(s) {
			if (!s || !String(s).trim()) return null;
			var t = String(s).trim().replace(/\/$/, "");
			try {
				var u = new URL(t);
				if (u.origin === loc.origin) {
					return flaskDevBase();
				}
				if (isLoopbackHost(u.hostname) && devPorts[String(u.port || "")]) {
					var p = loc.protocol || "http:";
					return p + "//" + (loc.hostname || u.hostname) + ":5000";
				}
				return t;
			} catch (e) {
				return t;
			}
		}

		if (typeof global.USIS_API_BASE === "string" && global.USIS_API_BASE.trim()) {
			var w = resolveOverride(global.USIS_API_BASE);
			if (w !== null) return w;
		}
		var fromMeta = metaApiBase();
		if (fromMeta) {
			var m = resolveOverride(fromMeta);
			if (m !== null) return m;
		}
		return flaskDevBase();
	}

	function actorHeaders() {
		var id = null;
		try {
			id = global.localStorage.getItem("usisActorUserId");
		} catch (e) {}
		if (id && id.trim()) {
			return { "X-Usis-User-Id": id.trim() };
		}
		return {};
	}

	function jsonFetchHeaders() {
		return Object.assign(
			{ "Content-Type": "application/json", Accept: "application/json" },
			actorHeaders()
		);
	}

	function resolveUrl(u) {
		if (!u) return "";
		var s = String(u).trim();
		if (!s) return "";
		if (/^https?:\/\//i.test(s)) return s;
		var b = apiBase();
		return b + (s.charAt(0) === "/" ? s : "/" + s);
	}

	function esc(s) {
		if (s == null) return "";
		var d = document.createElement("div");
		d.textContent = String(s);
		return d.innerHTML;
	}

	function csiDivision(code) {
		var c = String(code || "").trim();
		if (!c) return "Other";
		var m = c.match(/^(\d{2})/);
		return m ? "Division " + m[1] : "Other";
	}

	function mount(container, projectId) {
		if (!container || !projectId) return;
		var selectedId = null;
		var sections = [];

		container.innerHTML =
			'<div class="usis-specs-book row g-0 border rounded overflow-hidden bg-white" style="min-height:420px;">' +
			'<div class="col-12 col-md-4 col-lg-3 border-end bg-light d-flex flex-column" style="max-height:72vh;">' +
			'<div class="p-2 border-bottom bg-white">' +
			'<label class="form-label small text-muted mb-0">Find spec section</label>' +
			'<input type="search" class="form-control form-control-sm usis-specs-q" placeholder="CSI code or title…" autocomplete="off">' +
			"</div>" +
			'<div class="usis-specs-tree flex-grow-1 overflow-auto small p-2"></div>' +
			"</div>" +
			'<div class="col-12 col-md-8 col-lg-9 d-flex flex-column" style="max-height:72vh;">' +
			'<div class="p-2 border-bottom d-flex flex-wrap gap-2 align-items-center justify-content-between">' +
			'<div class="usis-specs-head text-muted small">Select a section on the left.</div>' +
			'<a class="btn btn-sm btn-outline-secondary usis-specs-openfull d-none" target="_blank" rel="noopener">Open PDF in new tab</a>' +
			"</div>" +
			'<div class="usis-specs-pdf flex-grow-1 bg-secondary bg-opacity-10 position-relative">' +
			'<div class="usis-specs-empty p-4 text-muted">No section selected.</div>' +
			'<iframe class="usis-specs-iframe w-100 h-100 border-0 d-none" title="Specification PDF"></iframe>' +
			"</div>" +
			'<div class="p-2 border-top bg-white usis-specs-linkpanel d-none">' +
			'<label class="form-label small mb-0">PDF URL for this section (optional), or import a PDF below</label>' +
			'<div class="input-group input-group-sm">' +
			'<input type="url" class="form-control usis-specs-pdfurl" placeholder="https://… or /api/v1/…">' +
			'<button type="button" class="btn btn-primary usis-specs-saveurl">Save</button>' +
			"</div>" +
			'<div class="d-flex flex-wrap gap-2 align-items-center mt-2">' +
			'<input type="file" class="d-none usis-specs-file" accept="application/pdf,.pdf">' +
			'<button type="button" class="btn btn-sm btn-outline-secondary usis-specs-import">Import PDF</button>' +
			"</div>" +
			'<div class="usis-specs-link-err text-danger small mt-1 d-none"></div>' +
			"</div>" +
			"</div>" +
			"</div>";

		var treeEl = container.querySelector(".usis-specs-tree");
		var qEl = container.querySelector(".usis-specs-q");
		var headEl = container.querySelector(".usis-specs-head");
		var openFull = container.querySelector(".usis-specs-openfull");
		var emptyEl = container.querySelector(".usis-specs-empty");
		var iframe = container.querySelector(".usis-specs-iframe");
		var linkPanel = container.querySelector(".usis-specs-linkpanel");
		var urlInput = container.querySelector(".usis-specs-pdfurl");
		var saveBtn = container.querySelector(".usis-specs-saveurl");
		var importBtn = container.querySelector(".usis-specs-import");
		var fileInput = container.querySelector(".usis-specs-file");
		var linkErr = container.querySelector(".usis-specs-link-err");

		function showPdf(url) {
			var full = resolveUrl(url);
			if (!full) {
				emptyEl.classList.remove("d-none");
				iframe.classList.add("d-none");
				iframe.removeAttribute("src");
				openFull.classList.add("d-none");
				return;
			}
			emptyEl.classList.add("d-none");
			iframe.classList.remove("d-none");
			iframe.setAttribute("src", full);
			openFull.href = full;
			openFull.classList.remove("d-none");
		}

		function selectSection(row) {
			selectedId = row.id;
			headEl.innerHTML =
				"<strong>" +
				esc(row.code) +
				"</strong> · " +
				esc(row.title) +
				(row.is_active === false ? ' <span class="badge bg-warning text-dark">Inactive</span>' : "");
			urlInput.value = row.pdf_url || "";
			linkPanel.classList.remove("d-none");
			linkErr.classList.add("d-none");
			linkErr.textContent = "";
			showPdf(row.pdf_url || "");
			Array.prototype.forEach.call(treeEl.querySelectorAll(".list-group-item"), function (n) {
				n.classList.toggle("active", n.getAttribute("data-id") === String(row.id));
			});
		}

		function renderTree(items, q) {
			sections = items || [];
			var qq = (q || "").trim().toLowerCase();
			var filtered = sections.filter(function (r) {
				if (!qq) return true;
				var blob = (r.code || "") + " " + (r.title || "");
				return blob.toLowerCase().indexOf(qq) !== -1;
			});
			var byDiv = {};
			filtered.forEach(function (r) {
				var d = csiDivision(r.code);
				if (!byDiv[d]) byDiv[d] = [];
				byDiv[d].push(r);
			});
			var divKeys = Object.keys(byDiv).sort();
			var html = "";
			divKeys.forEach(function (dk) {
				html += '<div class="fw-semibold text-uppercase text-muted mt-2 mb-1 px-1" style="font-size:0.7rem;">' + esc(dk) + "</div>";
				html += '<div class="list-group list-group-flush">';
				byDiv[dk]
					.sort(function (a, b) {
						return String(a.code).localeCompare(String(b.code));
					})
					.forEach(function (r) {
						html +=
							'<button type="button" class="list-group-item list-group-item-action py-2 px-2 border-0 rounded mb-1' +
							(String(r.id) === String(selectedId) ? " active" : "") +
							'" data-id="' +
							esc(String(r.id)) +
							'">' +
							'<span class="fw-medium">' +
							esc(r.code) +
							"</span>" +
							'<div class="text-muted text-truncate" style="max-width:100%;">' +
							esc(r.title) +
							"</div>" +
							"</button>";
					});
				html += "</div>";
			});
			if (!html) {
				html =
					'<p class="text-muted px-2 py-3 mb-0">' +
					(sections.length ? "No sections match your search." : "No spec sections yet. Add them under RFI lookups (spec_sections) or seed data.") +
					"</p>";
			}
			treeEl.innerHTML = html;
			Array.prototype.forEach.call(treeEl.querySelectorAll("button[data-id]"), function (btn) {
				btn.addEventListener("click", function () {
					var id = btn.getAttribute("data-id");
					var row = sections.find(function (x) {
						return String(x.id) === id;
					});
					if (row) selectSection(row);
				});
			});
		}

		function load() {
			var base = apiBase();
			fetch(base + "/api/v1/projects/" + encodeURIComponent(projectId) + "/rfi-lookups/spec_sections", {
				credentials: "include",
				headers: Object.assign({ Accept: "application/json" }, actorHeaders()),
			})
				.then(function (res) {
					if (!res.ok) return res.text().then(function (t) {
						throw new Error(res.status + " " + (t || res.statusText));
					});
					return res.json();
				})
				.then(function (data) {
					renderTree(data.items || [], qEl ? qEl.value : "");
				})
				.catch(function (e) {
					treeEl.innerHTML =
						'<p class="text-danger small px-2">' + esc(e.message || String(e)) + "</p>";
				});
		}

		if (qEl) {
			qEl.addEventListener("input", function () {
				renderTree(sections, qEl.value);
			});
		}

		if (saveBtn && urlInput) {
			saveBtn.addEventListener("click", function () {
				if (!selectedId) return;
				linkErr.classList.add("d-none");
				var body = { pdf_url: urlInput.value.trim() || null };
				var base = apiBase();
				fetch(
					base +
						"/api/v1/projects/" +
						encodeURIComponent(projectId) +
						"/rfi-lookups/spec_sections/" +
						encodeURIComponent(selectedId),
					{
						method: "PATCH",
						credentials: "include",
						headers: jsonFetchHeaders(),
						body: JSON.stringify(body),
					}
				)
					.then(function (res) {
						if (!res.ok) return res.text().then(function (t) {
							throw new Error(res.status + " " + (t || res.statusText));
						});
						return res.json();
					})
					.then(function (data) {
						var it = data.item;
						if (it) {
							var idx = sections.findIndex(function (x) {
								return String(x.id) === String(it.id);
							});
							if (idx >= 0) sections[idx] = it;
							selectSection(it);
						}
					})
					.catch(function (e) {
						linkErr.textContent = e.message || String(e);
						linkErr.classList.remove("d-none");
					});
			});
		}

		if (importBtn && fileInput) {
			importBtn.addEventListener("click", function () {
				if (!selectedId) return;
				fileInput.click();
			});
			fileInput.addEventListener("change", function () {
				if (!selectedId) return;
				var f = fileInput.files && fileInput.files[0];
				fileInput.value = "";
				if (!f) return;
				linkErr.classList.add("d-none");
				var base = apiBase();
				var fd = new FormData();
				fd.append("file", f, f.name || "spec.pdf");
				fetch(
					base +
						"/api/v1/projects/" +
						encodeURIComponent(projectId) +
						"/rfi-lookups/spec_sections/" +
						encodeURIComponent(selectedId) +
						"/file",
					{
						method: "POST",
						credentials: "include",
						headers: Object.assign({}, actorHeaders()),
						body: fd,
					}
				)
					.then(function (res) {
						if (!res.ok) return res.text().then(function (t) {
							throw new Error(res.status + " " + (t || res.statusText));
						});
						return res.json();
					})
					.then(function (data) {
						var it = data.item;
						if (it) {
							var idx = sections.findIndex(function (x) {
								return String(x.id) === String(it.id);
							});
							if (idx >= 0) sections[idx] = it;
							selectSection(it);
						}
					})
					.catch(function (e) {
						linkErr.textContent = e.message || String(e);
						linkErr.classList.remove("d-none");
					});
			});
		}

		load();
	}

	global.USISSpecsBook = { mount: mount, resolveAssetUrl: resolveUrl };
})(typeof window !== "undefined" ? window : globalThis);
