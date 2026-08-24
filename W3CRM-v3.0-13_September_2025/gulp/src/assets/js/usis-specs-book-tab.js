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
			'<div class="d-flex flex-wrap gap-1 align-items-center mb-2">' +
			'<button type="button" class="btn btn-sm btn-primary usis-specs-add">Add from CSI catalog</button>' +
			'<button type="button" class="btn btn-sm btn-outline-primary usis-specs-import-book">Import spec book PDF</button>' +
			'<input type="file" class="d-none usis-specs-book-file" accept="application/pdf,.pdf">' +
			"</div>" +
			'<label class="form-label small text-muted mb-1">Find on this project</label>' +
			'<input type="search" class="form-control form-control-sm usis-specs-q" placeholder="CSI code or title…" autocomplete="off">' +
			'<div class="usis-specs-book-msg small mt-1 d-none"></div>' +
			"</div>" +
			'<div class="usis-specs-tree flex-grow-1 overflow-auto small p-2"></div>' +
			"</div>" +
			'<div class="col-12 col-md-8 col-lg-9 d-flex flex-column" style="max-height:72vh;">' +
			'<div class="p-2 border-bottom d-flex flex-wrap gap-2 align-items-center justify-content-between">' +
			'<div class="usis-specs-head text-muted small">Select a section on the left.</div>' +
			'<div class="d-flex flex-wrap gap-1">' +
			'<button type="button" class="btn btn-sm btn-outline-danger usis-specs-delete d-none">Delete section</button>' +
			'<a class="btn btn-sm btn-outline-secondary usis-specs-openfull d-none" target="_blank" rel="noopener">Open PDF in new tab</a>' +
			"</div>" +
			"</div>" +
			'<div class="usis-specs-pdf flex-grow-1 bg-secondary bg-opacity-10 position-relative">' +
			'<div class="usis-specs-empty p-4 text-muted">No section selected.</div>' +
			'<iframe class="usis-specs-iframe w-100 h-100 border-0 d-none" title="Specification PDF"></iframe>' +
			"</div>" +
			'<div class="p-2 border-top bg-white usis-specs-linkpanel d-none">' +
			'<label class="form-label small mb-0">PDF for this section (optional)</label>' +
			'<div class="input-group input-group-sm">' +
			'<input type="url" class="form-control usis-specs-pdfurl" placeholder="https://… or /api/v1/…">' +
			'<button type="button" class="btn btn-primary usis-specs-saveurl">Save URL</button>' +
			"</div>" +
			'<div class="d-flex flex-wrap gap-2 align-items-center mt-2">' +
			'<input type="file" class="d-none usis-specs-file" accept="application/pdf,.pdf">' +
			'<button type="button" class="btn btn-sm btn-outline-secondary usis-specs-import">Attach PDF to this section</button>' +
			"</div>" +
			'<div class="usis-specs-link-err text-danger small mt-1 d-none"></div>' +
			"</div>" +
			"</div>" +
			"</div>" +
			'<div class="usis-specs-modal d-none" style="position:fixed;inset:0;z-index:1080;background:rgba(15,23,42,.45);">' +
			'<div class="bg-white rounded shadow-lg m-3 mx-auto p-3" style="max-width:720px;max-height:calc(100vh - 2rem);display:flex;flex-direction:column;">' +
			'<div class="d-flex justify-content-between align-items-start gap-2 mb-2">' +
			"<div><h5 class=\"mb-1\">CSI MasterFormat catalog</h5>" +
			'<p class="text-muted small mb-0">Check the sections used on this job. You can also type a custom code.</p></div>' +
			'<button type="button" class="btn-close usis-specs-modal-close" aria-label="Close"></button>' +
			"</div>" +
			'<input type="search" class="form-control form-control-sm mb-2 usis-specs-cat-q" placeholder="Search CSI code or title…" autocomplete="off">' +
			'<div class="usis-specs-cat-list border rounded overflow-auto small mb-2" style="min-height:220px;max-height:42vh;"></div>' +
			'<div class="row g-2 align-items-end mb-2">' +
			'<div class="col-sm-4"><label class="form-label small mb-0">Custom code</label>' +
			'<input class="form-control form-control-sm usis-specs-custom-code" placeholder="10 44 16"></div>' +
			'<div class="col-sm-8"><label class="form-label small mb-0">Custom title</label>' +
			'<input class="form-control form-control-sm usis-specs-custom-title" placeholder="Fire Extinguishers"></div>' +
			"</div>" +
			'<div class="d-flex flex-wrap gap-2 justify-content-end">' +
			'<button type="button" class="btn btn-sm btn-outline-secondary usis-specs-modal-close">Cancel</button>' +
			'<button type="button" class="btn btn-sm btn-primary usis-specs-cat-add">Add selected</button>' +
			"</div>" +
			'<div class="usis-specs-cat-err text-danger small mt-2 d-none"></div>' +
			"</div></div>";

		var treeEl = container.querySelector(".usis-specs-tree");
		var qEl = container.querySelector(".usis-specs-q");
		var headEl = container.querySelector(".usis-specs-head");
		var openFull = container.querySelector(".usis-specs-openfull");
		var deleteBtn = container.querySelector(".usis-specs-delete");
		var emptyEl = container.querySelector(".usis-specs-empty");
		var iframe = container.querySelector(".usis-specs-iframe");
		var linkPanel = container.querySelector(".usis-specs-linkpanel");
		var urlInput = container.querySelector(".usis-specs-pdfurl");
		var saveBtn = container.querySelector(".usis-specs-saveurl");
		var importBtn = container.querySelector(".usis-specs-import");
		var fileInput = container.querySelector(".usis-specs-file");
		var linkErr = container.querySelector(".usis-specs-link-err");
		var addBtn = container.querySelector(".usis-specs-add");
		var importBookBtn = container.querySelector(".usis-specs-import-book");
		var bookFileInput = container.querySelector(".usis-specs-book-file");
		var bookMsg = container.querySelector(".usis-specs-book-msg");
		var modalEl = container.querySelector(".usis-specs-modal");
		var catList = container.querySelector(".usis-specs-cat-list");
		var catQ = container.querySelector(".usis-specs-cat-q");
		var catAdd = container.querySelector(".usis-specs-cat-add");
		var catErr = container.querySelector(".usis-specs-cat-err");
		var customCode = container.querySelector(".usis-specs-custom-code");
		var customTitle = container.querySelector(".usis-specs-custom-title");
		var catalogItems = [];
		var catalogTimer = null;

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
			if (deleteBtn) deleteBtn.classList.remove("d-none");
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
					(sections.length
						? "No sections match your search."
						: "No CSI sections on this project yet. Add them from the CSI catalog, or import a spec-book PDF.") +
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

		function setBookMsg(text, isError) {
			if (!bookMsg) return;
			if (!text) {
				bookMsg.className = "usis-specs-book-msg small mt-1 d-none";
				bookMsg.textContent = "";
				return;
			}
			bookMsg.className = "usis-specs-book-msg small mt-1 " + (isError ? "text-danger" : "text-success");
			bookMsg.textContent = text;
		}

		function setCatErr(text) {
			if (!catErr) return;
			if (!text) {
				catErr.classList.add("d-none");
				catErr.textContent = "";
				return;
			}
			catErr.textContent = text;
			catErr.classList.remove("d-none");
		}

		function renderCatalog(items) {
			catalogItems = items || [];
			if (!catList) return;
			if (!catalogItems.length) {
				catList.innerHTML = '<p class="text-muted px-2 py-3 mb-0">No CSI sections match that search.</p>';
				return;
			}
			var html = '<div class="list-group list-group-flush">';
			catalogItems.forEach(function (item) {
				html +=
					'<label class="list-group-item list-group-item-action py-2 px-2 d-flex gap-2 align-items-start">' +
					'<input type="checkbox" class="form-check-input mt-1 usis-specs-cat-check" value="' +
					esc(item.code) +
					'" data-title="' +
					esc(item.title) +
					'">' +
					"<div><div class=\"fw-medium\">" +
					esc(item.code) +
					" · " +
					esc(item.title) +
					"</div>" +
					'<div class="text-muted" style="font-size:0.7rem;">Division ' +
					esc(item.division) +
					" · " +
					esc(item.division_name) +
					"</div></div></label>";
			});
			html += "</div>";
			catList.innerHTML = html;
		}

		function loadCatalog(q) {
			if (!catList) return;
			catList.innerHTML = '<p class="text-muted px-2 py-3 mb-0">Loading CSI catalog…</p>';
			var base = apiBase();
			var url = base + "/api/v1/csi-sections?limit=400";
			if (q) url += "&q=" + encodeURIComponent(q);
			fetch(url, {
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
					renderCatalog(data.items || []);
				})
				.catch(function (e) {
					catList.innerHTML =
						'<p class="text-danger small px-2">' + esc(e.message || String(e)) + "</p>";
				});
		}

		function openModal() {
			if (!modalEl) return;
			setCatErr("");
			modalEl.classList.remove("d-none");
			if (catQ) catQ.value = "";
			if (customCode) customCode.value = "";
			if (customTitle) customTitle.value = "";
			loadCatalog("");
			if (catQ) catQ.focus();
		}

		function closeModal() {
			if (modalEl) modalEl.classList.add("d-none");
		}

		function addFromCatalog() {
			var items = [];
			Array.prototype.forEach.call(container.querySelectorAll(".usis-specs-cat-check:checked"), function (box) {
				items.push({ code: box.value, title: box.getAttribute("data-title") || "" });
			});
			if (customCode && customCode.value.trim()) {
				items.push({
					code: customCode.value.trim(),
					title: customTitle && customTitle.value.trim() ? customTitle.value.trim() : "",
				});
			}
			if (!items.length) {
				setCatErr("Check at least one CSI section, or type a custom code.");
				return;
			}
			setCatErr("");
			var base = apiBase();
			fetch(base + "/api/v1/projects/" + encodeURIComponent(projectId) + "/spec-sections/from-catalog", {
				method: "POST",
				credentials: "include",
				headers: jsonFetchHeaders(),
				body: JSON.stringify({ items: items }),
			})
				.then(function (res) {
					if (!res.ok) return res.text().then(function (t) {
						throw new Error(res.status + " " + (t || res.statusText));
					});
					return res.json();
				})
				.then(function (data) {
					closeModal();
					load();
					var created = data.items || [];
					if (created.length) selectSection(created[0]);
					setBookMsg(
						created.length
							? "Added " + created.length + " CSI section" + (created.length === 1 ? "" : "s") + "."
							: "Those sections were already on this project."
					);
				})
				.catch(function (e) {
					setCatErr(e.message || String(e));
				});
		}

		if (addBtn) addBtn.addEventListener("click", openModal);
		Array.prototype.forEach.call(container.querySelectorAll(".usis-specs-modal-close"), function (btn) {
			btn.addEventListener("click", closeModal);
		});
		if (modalEl) {
			modalEl.addEventListener("click", function (ev) {
				if (ev.target === modalEl) closeModal();
			});
		}
		if (catAdd) catAdd.addEventListener("click", addFromCatalog);
		if (catQ) {
			catQ.addEventListener("input", function () {
				if (catalogTimer) global.clearTimeout(catalogTimer);
				catalogTimer = global.setTimeout(function () {
					loadCatalog(catQ.value);
				}, 220);
			});
		}

		if (deleteBtn) {
			deleteBtn.addEventListener("click", function () {
				if (!selectedId) return;
				var row = sections.find(function (x) {
					return String(x.id) === String(selectedId);
				});
				var label = row ? row.code + " " + row.title : "this section";
				if (!window.confirm("Delete " + label + " from this project?")) return;
				var base = apiBase();
				fetch(
					base +
						"/api/v1/projects/" +
						encodeURIComponent(projectId) +
						"/rfi-lookups/spec_sections/" +
						encodeURIComponent(selectedId),
					{
						method: "DELETE",
						credentials: "include",
						headers: Object.assign({ Accept: "application/json" }, actorHeaders()),
					}
				)
					.then(function (res) {
						if (!res.ok) return res.text().then(function (t) {
							throw new Error(res.status + " " + (t || res.statusText));
						});
						return res.json();
					})
					.then(function () {
						selectedId = null;
						if (deleteBtn) deleteBtn.classList.add("d-none");
						linkPanel.classList.add("d-none");
						headEl.textContent = "Select a section on the left.";
						showPdf("");
						setBookMsg("Section deleted.");
						load();
					})
					.catch(function (e) {
						linkErr.textContent = e.message || String(e);
						linkErr.classList.remove("d-none");
					});
			});
		}

		if (importBookBtn && bookFileInput) {
			importBookBtn.addEventListener("click", function () {
				bookFileInput.click();
			});
			bookFileInput.addEventListener("change", function () {
				var f = bookFileInput.files && bookFileInput.files[0];
				bookFileInput.value = "";
				if (!f) return;
				setBookMsg("Reading spec book…");
				var base = apiBase();
				var fd = new FormData();
				fd.append("file", f, f.name || "spec-book.pdf");
				fetch(base + "/api/v1/projects/" + encodeURIComponent(projectId) + "/spec-book/import", {
					method: "POST",
					credentials: "include",
					headers: Object.assign({}, actorHeaders()),
					body: fd,
				})
					.then(function (res) {
						if (!res.ok) return res.text().then(function (t) {
							throw new Error(res.status + " " + (t || res.statusText));
						});
						return res.json();
					})
					.then(function (data) {
						load();
						var created = data.items || [];
						if (created.length) selectSection(created[0]);
						setBookMsg(
							"Found " +
								(data.found || 0) +
								" CSI section" +
								((data.found || 0) === 1 ? "" : "s") +
								", added " +
								(data.created || 0) +
								((data.skipped || 0) ? ", skipped " + data.skipped + " already on the project" : "") +
								"."
						);
					})
					.catch(function (e) {
						setBookMsg(e.message || String(e), true);
					});
			});
		}

		load();
	}

	global.USISSpecsBook = { mount: mount, resolveAssetUrl: resolveUrl };
})(typeof window !== "undefined" ? window : globalThis);
