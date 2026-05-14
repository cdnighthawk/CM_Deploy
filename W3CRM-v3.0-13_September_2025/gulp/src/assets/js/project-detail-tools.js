/**
 * Project detail: Procore-style Submittals / RFIs / Drawings tables (API-backed).
 * Expects Bootstrap 5 tabs; reads project id from ?id= (UUID).
 */
(function () {
	"use strict";

	var cache = { drawingSheets: [], rfis: [], submittals: [] };
	var filtersWired = false;
	var drawingsTabulator = null;
	var activeProjectId = null;

	function apiBase() {
		var loc = window.location;
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

		if (typeof window.USIS_API_BASE === "string" && window.USIS_API_BASE.trim()) {
			var s = window.USIS_API_BASE.trim().replace(/\/$/, "");
			try {
				var u = new URL(s);
				if (u.origin === loc.origin) {
					return flaskDevBase();
				}
				/* e.g. meta says http://localhost:3000 but page is http://127.0.0.1:3000 — still the static dev server, not Flask */
				if (isLoopbackHost(u.hostname) && devPorts[String(u.port || "")]) {
					var p = loc.protocol || "http:";
					return p + "//" + (loc.hostname || u.hostname) + ":5000";
				}
				return s;
			} catch (e) {
				if (s) return s;
			}
		}
		return flaskDevBase();
	}

	function actorHeaders() {
		var id = null;
		try {
			id = window.localStorage.getItem("usisActorUserId");
		} catch (e) {}
		if (id && id.trim()) {
			return { "X-Usis-User-Id": id.trim() };
		}
		return {};
	}

	function resolveAssetUrl(u) {
		if (u == null || u === "") return "";
		var s = String(u).trim();
		if (!s) return "";
		if (/^https?:\/\//i.test(s)) return s;
		var b = apiBase();
		return b + (s.charAt(0) === "/" ? s : "/" + s);
	}

	function projectIdFromQuery() {
		var id = new URLSearchParams(window.location.search).get("id");
		return id && id.trim() ? id.trim() : null;
	}

	function esc(s) {
		if (s == null || s === "") return "";
		var d = document.createElement("div");
		d.textContent = String(s);
		return d.innerHTML;
	}

	function fetchJson(path) {
		var base = apiBase();
		var url = base + path;
		return fetch(url, {
			credentials: "include",
			headers: Object.assign({ Accept: "application/json" }, actorHeaders()),
		}).then(function (res) {
			if (!res.ok) {
				return res.text().then(function (t) {
					throw new Error(res.status + " " + (t || res.statusText));
				});
			}
			return res.json();
		});
	}

	function fetchJsonBody(method, path, bodyObj) {
		var base = apiBase();
		var url = base + path;
		var opts = {
			method: method,
			credentials: "include",
			headers: Object.assign(
				{ "Content-Type": "application/json", Accept: "application/json" },
				actorHeaders()
			),
		};
		if (bodyObj !== undefined && bodyObj !== null) {
			opts.body = JSON.stringify(bodyObj);
		}
		return fetch(url, opts).then(function (res) {
			if (!res.ok) {
				return res.text().then(function (t) {
					throw new Error(res.status + " " + (t || res.statusText));
				});
			}
			return res.json();
		});
	}

	function isoFromDateInput(el) {
		if (!el || !el.value) return null;
		return el.value + "T00:00:00+00:00";
	}

	function fmtDate(iso) {
		if (!iso) return "—";
		try {
			return new Date(iso).toLocaleDateString();
		} catch (e) {
			return "—";
		}
	}

	function setPaneLoading(paneId, loading) {
		var el = document.getElementById(paneId);
		if (!el) return;
		var n = el.querySelector("[data-usis-loading]");
		if (n) n.classList.toggle("d-none", !loading);
	}

	function setPaneError(paneId, msg) {
		var el = document.getElementById(paneId);
		if (!el) return;
		var n = el.querySelector("[data-usis-error]");
		if (!n) return;
		if (msg) {
			n.textContent = msg;
			n.classList.remove("d-none");
		} else {
			n.textContent = "";
			n.classList.add("d-none");
		}
	}

	function filterRows(rows, q, statusVal, getStatus) {
		var qq = (q || "").trim().toLowerCase();
		var st = (statusVal || "").trim().toLowerCase();
		return rows.filter(function (r) {
			if (st && String(getStatus(r)).toLowerCase() !== st) return false;
			if (!qq) return true;
			return JSON.stringify(r).toLowerCase().indexOf(qq) !== -1;
		});
	}

	function repopulateDrawingFacetSelects(items) {
		var discSel = document.getElementById("usis-filter-drawing-discipline");
		var setSel = document.getElementById("usis-filter-drawing-set");
		var discSet = {};
		var setSet = {};
		(items || []).forEach(function (s) {
			if (s.discipline) discSet[s.discipline] = 1;
			if (s.drawing_set) setSet[s.drawing_set] = 1;
		});
		if (discSel) {
			var curD = discSel.value;
			discSel.innerHTML = '<option value="">All disciplines</option>';
			Object.keys(discSet)
				.sort(function (a, b) {
					return a.localeCompare(b);
				})
				.forEach(function (k) {
					var o = document.createElement("option");
					o.value = k;
					o.textContent = k;
					discSel.appendChild(o);
				});
			if (curD && discSet[curD]) discSel.value = curD;
		}
		if (setSel) {
			var curS = setSel.value;
			setSel.innerHTML = '<option value="">All sets</option>';
			Object.keys(setSet)
				.sort(function (a, b) {
					return a.localeCompare(b);
				})
				.forEach(function (k) {
					var o = document.createElement("option");
					o.value = k;
					o.textContent = k;
					setSel.appendChild(o);
				});
			if (curS && setSet[curS]) setSel.value = curS;
		}
	}

	function filterDrawingSheetsClient(items) {
		var inp = document.getElementById("usis-search-drawings");
		var discSel = document.getElementById("usis-filter-drawing-discipline");
		var setSel = document.getElementById("usis-filter-drawing-set");
		var q = (inp && inp.value) ? inp.value.trim().toLowerCase() : "";
		var disc = discSel ? discSel.value : "";
		var setv = setSel ? setSel.value : "";
		return (items || []).filter(function (s) {
			if (disc && (s.discipline || "") !== disc) return false;
			if (setv && (s.drawing_set || "") !== setv) return false;
			if (!q) return true;
			var blob = JSON.stringify(s).toLowerCase();
			return blob.indexOf(q) !== -1;
		});
	}

	function buildOrRefreshDrawingsTabulator() {
		var el = document.getElementById("usis-grid-drawings");
		if (!el) return;
		var rows = filterDrawingSheetsClient(cache.drawingSheets);
		if (typeof Tabulator === "undefined") {
			el.innerHTML =
				'<div class="alert alert-warning mb-0">Drawing grid requires Tabulator (CDN). Check your network or CSP.</div>';
			return;
		}
		var pid = activeProjectId || "";
		var cols = [
			{ title: "Sheet #", field: "sheet_number", headerFilter: "input", minWidth: 100, widthGrow: 1 },
			{ title: "Title", field: "sheet_title", headerFilter: "input", minWidth: 160, widthGrow: 2 },
			{ title: "Discipline", field: "discipline", headerFilter: "input", minWidth: 100, widthGrow: 1 },
			{ title: "Set", field: "drawing_set", headerFilter: "input", minWidth: 90, widthGrow: 1 },
			{
				title: "Current rev",
				field: "current_revision",
				minWidth: 110,
				formatter: function (cell) {
					var cr = cell.getValue();
					if (!cr) return "";
					var r = cr.revision != null ? String(cr.revision) : "";
					var v = cr.version != null ? String(cr.version) : "";
					return esc(r) + (v ? " · v" + esc(v) : "");
				},
			},
			{ title: "Revisions", field: "revision_count", hozAlign: "right", width: 100 },
			{
				title: "Updated",
				field: "current_revision",
				width: 170,
				formatter: function (cell) {
					var cr = cell.getValue();
					if (!cr || !cr.updated_at) return "—";
					try {
						return esc(new Date(cr.updated_at).toLocaleString());
					} catch (e) {
						return esc(cr.updated_at);
					}
				},
			},
			{
				title: "",
				hozAlign: "right",
				headerSort: false,
				width: 150,
				formatter: function (cell) {
					var wrap = document.createElement("div");
					wrap.className = "d-flex gap-1 flex-wrap justify-content-end";
					var data = cell.getRow().getData();
					var cr = data.current_revision;
					if (cr && cr.id && pid) {
						var a = document.createElement("a");
						a.href =
							"drawing-viewer.html?project_id=" +
							encodeURIComponent(pid) +
							"&drawing_id=" +
							encodeURIComponent(cr.id);
						a.className = "btn btn-primary btn-sm py-0";
						a.textContent = "View";
						wrap.appendChild(a);
					}
					if (cr && cr.file_url) {
						var p = document.createElement("a");
						p.href = resolveAssetUrl(cr.file_url);
						p.target = "_blank";
						p.rel = "noopener noreferrer";
						p.className = "btn btn-outline-secondary btn-sm py-0";
						p.textContent = "PDF";
						wrap.appendChild(p);
					}
					if (!wrap.childNodes.length) {
						wrap.textContent = "—";
					}
					return wrap;
				},
			},
		];
		if (drawingsTabulator) {
			drawingsTabulator.setData(rows);
			return;
		}
		drawingsTabulator = new Tabulator(el, {
			data: rows,
			layout: "fitColumns",
			pagination: "local",
			paginationSize: 25,
			paginationSizeSelector: [10, 25, 50, 100],
			movableColumns: true,
			placeholder: "No drawings for this project yet.",
			columns: cols,
		});
	}

	function renderRfiTable(tbody, items) {
		if (!tbody) return;
		tbody.innerHTML = "";
		if (!items.length) {
			tbody.innerHTML =
				'<tr><td colspan="8" class="text-muted text-center py-4">No RFIs yet. Use "+ Create RFI" to start the log.</td></tr>';
			return;
		}
		items.forEach(function (row) {
			var tr = document.createElement("tr");
			var num = row.display_number || ("RFI-" + row.number);
			var detail = "construction/rfi-detail.html?id=" + encodeURIComponent(row.id);
			var assignees = (row.assignees || []).map(function (a) {
				return esc(a.user ? a.user.name : "");
			}).filter(Boolean).join(", ") || "—";
			var mgr = row.rfi_manager ? esc(row.rfi_manager.name) : "—";
			var status = '<span class="text-uppercase small fw-semibold">' + esc(row.status) + "</span>";
			var due = row.due_at ? esc(new Date(row.due_at).toLocaleDateString()) : "—";
			tr.innerHTML =
				'<td><a class="link-primary text-decoration-none" href="' + detail + '">' + esc(num) + "</a></td>" +
				'<td><a class="text-decoration-none text-black fw-semibold" href="' + detail + '">' + esc(row.subject) + "</a></td>" +
				"<td>" + status + "</td>" +
				"<td>" + esc(row.ball_in_court || "—") + "</td>" +
				"<td>" + assignees + "</td>" +
				"<td>" + mgr + "</td>" +
				"<td>" + due + "</td>" +
				'<td class="text-end"><a class="btn btn-link btn-sm" href="' + detail + '">Open</a></td>';
			tbody.appendChild(tr);
		});
	}

	function renderSubmittalTable(tbody, items) {
		if (!tbody) return;
		tbody.innerHTML = "";
		if (!items.length) {
			tbody.innerHTML =
				'<tr><td colspan="16" class="text-muted text-center py-4">No submittals yet. Create one to start the log.</td></tr>';
			return;
		}
		var pid = activeProjectId || projectIdFromQuery() || "";
		items.forEach(function (row) {
			var tr = document.createElement("tr");
			var detail =
				"construction/submittal-detail.html?id=" +
				encodeURIComponent(pid) +
				"&submittal=" +
				encodeURIComponent(row.id);
			var att = row.current_attachment;
			var fileCell =
				att && att.file_url
					? '<a href="' +
					  esc(att.file_url) +
					  '" target="_blank" rel="noopener">v' +
					  esc(String(att.version || "")) +
					  "</a>"
					: "—";
			var titleCell =
				'<a class="fw-semibold text-decoration-none" href="' +
				detail +
				'">' +
				esc(row.title) +
				"</a>";
			tr.innerHTML =
				"<td>" +
				esc(row.number) +
				"</td><td>" +
				titleCell +
				"</td><td>" +
				esc(row.spec_section) +
				"</td><td>" +
				esc(row.submittal_type) +
				"</td><td>" +
				esc(row.status) +
				"</td><td>" +
				esc(row.responsible_contractor) +
				"</td><td>" +
				fmtDate(row.submit_by_at) +
				"</td><td>" +
				fmtDate(row.received_at) +
				"</td><td>" +
				fmtDate(row.sent_at) +
				"</td><td>" +
				fmtDate(row.returned_at) +
				"</td><td>" +
				esc(row.ball_in_court) +
				"</td><td>" +
				fmtDate(row.due_at) +
				"</td><td>" +
				esc(row.revision) +
				"</td><td>" +
				esc(row.response ? String(row.response).slice(0, 80) : "") +
				'</td><td class="text-end">' +
				fileCell +
				'</td><td class="text-end"><a class="btn btn-link btn-sm py-0" href="' +
				detail +
				'">Open</a></td>';
			tbody.appendChild(tr);
		});
	}

	function applyDrawingFilter() {
		buildOrRefreshDrawingsTabulator();
	}

	function applyRfiFilter() {
		var inp = document.getElementById("usis-search-rfis");
		var sel = document.getElementById("usis-filter-rfi-status");
		var q = inp ? inp.value : "";
		var st = sel ? sel.value : "";
		var rows = filterRows(cache.rfis, q, st, function (r) {
			return r.status;
		});
		renderRfiTable(document.getElementById("usis-tbody-rfis"), rows);
	}

	function applySubmittalFilter() {
		var inp = document.getElementById("usis-search-submittals");
		var sel = document.getElementById("usis-filter-submittal-status");
		var q = inp ? inp.value : "";
		var st = sel ? sel.value : "";
		var rows = filterRows(cache.submittals, q, st, function (r) {
			return r.status;
		});
		renderSubmittalTable(document.getElementById("usis-tbody-submittals"), rows);
	}

	function wireFiltersOnce() {
		if (filtersWired) return;
		filtersWired = true;
		var d = document.getElementById("usis-search-drawings");
		if (d) d.addEventListener("input", applyDrawingFilter);
		var dd = document.getElementById("usis-filter-drawing-discipline");
		var ds = document.getElementById("usis-filter-drawing-set");
		if (dd) dd.addEventListener("change", applyDrawingFilter);
		if (ds) ds.addEventListener("change", applyDrawingFilter);
		var r1 = document.getElementById("usis-search-rfis");
		var r2 = document.getElementById("usis-filter-rfi-status");
		if (r1) r1.addEventListener("input", applyRfiFilter);
		if (r2) r2.addEventListener("change", applyRfiFilter);
		var s1 = document.getElementById("usis-search-submittals");
		var s2 = document.getElementById("usis-filter-submittal-status");
		if (s1) s1.addEventListener("input", applySubmittalFilter);
		if (s2) s2.addEventListener("change", applySubmittalFilter);

		var drawUp = document.getElementById("usis-drawing-upload-submit");
		if (drawUp && !drawUp.dataset.usisWired) {
			drawUp.dataset.usisWired = "1";
			drawUp.addEventListener("click", function () {
				var pid = activeProjectId || projectIdFromQuery();
				if (!pid) return;
				var err = document.getElementById("usis-drawing-upload-err");
				var fileEl = document.getElementById("usis-drawing-file");
				if (err) {
					err.classList.add("d-none");
					err.textContent = "";
				}
				if (!fileEl || !fileEl.files || !fileEl.files[0]) {
					if (err) {
						err.textContent = "Choose a PDF file.";
						err.classList.remove("d-none");
					}
					return;
				}
				var fd = new FormData();
				fd.append("file", fileEl.files[0]);
				var sn = document.getElementById("usis-drawing-sheetno");
				var st = document.getElementById("usis-drawing-title");
				var dc = document.getElementById("usis-drawing-disc");
				var ds = document.getElementById("usis-drawing-set");
				var rv = document.getElementById("usis-drawing-rev");
				if (sn && sn.value) fd.append("sheet_number", sn.value);
				if (st && st.value) fd.append("sheet_title", st.value);
				if (dc && dc.value) fd.append("discipline", dc.value);
				if (ds && ds.value) fd.append("drawing_set", ds.value);
				if (rv && rv.value) fd.append("revision", rv.value);
				var url = apiBase() + "/api/v1/projects/" + encodeURIComponent(pid) + "/drawings";
				fetch(url, {
					method: "POST",
					body: fd,
					credentials: "include",
					headers: actorHeaders(),
				})
					.then(function (res) {
						if (!res.ok) {
							return res.text().then(function (t) {
								throw new Error(res.status + " " + (t || res.statusText));
							});
						}
						return res.json();
					})
					.then(function () {
						var modalEl = document.getElementById("usis-modal-drawing-create");
						if (modalEl && window.bootstrap && window.bootstrap.Modal) {
							var inst = window.bootstrap.Modal.getInstance(modalEl);
							if (inst) inst.hide();
						}
						if (fileEl) fileEl.value = "";
						return loadAll(pid);
					})
					.catch(function (e) {
						if (err) {
							err.textContent = e.message || String(e);
							err.classList.remove("d-none");
						}
					});
			});
		}

		var subBtn = document.getElementById("usis-submittal-create-submit");
		if (subBtn) {
			subBtn.addEventListener("click", function () {
				var pid = activeProjectId || projectIdFromQuery();
				if (!pid) return;
				var err = document.getElementById("usis-submittal-create-err");
				if (err) {
					err.classList.add("d-none");
					err.textContent = "";
				}
				var titleEl = document.getElementById("usis-submittal-c-title");
				var title = titleEl && titleEl.value ? titleEl.value.trim() : "";
				if (!title) {
					if (err) {
						err.textContent = "Title is required.";
						err.classList.remove("d-none");
					}
					return;
				}
				var payload = {
					title: title,
					spec_section: (document.getElementById("usis-submittal-c-spec") || {}).value || null,
					submittal_type: (document.getElementById("usis-submittal-c-type") || {}).value || null,
					status: (document.getElementById("usis-submittal-c-status") || {}).value || "draft",
					ball_in_court: (document.getElementById("usis-submittal-c-bic") || {}).value || null,
					responsible_contractor: (document.getElementById("usis-submittal-c-contractor") || {}).value || null,
					revision: (document.getElementById("usis-submittal-c-rev") || {}).value || null,
					due_at: isoFromDateInput(document.getElementById("usis-submittal-c-due")),
					submit_by_at: isoFromDateInput(document.getElementById("usis-submittal-c-submitby")),
					received_at: isoFromDateInput(document.getElementById("usis-submittal-c-received")),
					received_from: (document.getElementById("usis-submittal-c-receivedfrom") || {}).value || null,
				};
				fetchJsonBody("POST", "/api/v1/projects/" + encodeURIComponent(pid) + "/submittals", payload)
					.then(function () {
						var modalEl = document.getElementById("usis-modal-submittal-create");
						if (modalEl && window.bootstrap && window.bootstrap.Modal) {
							var inst = window.bootstrap.Modal.getInstance(modalEl);
							if (inst) inst.hide();
						}
						if (titleEl) titleEl.value = "";
						return loadAll(pid);
					})
					.catch(function (e) {
						if (err) {
							err.textContent = e.message || String(e);
							err.classList.remove("d-none");
						}
					});
			});
		}
	}

	function loadAll(projectId) {
		wireFiltersOnce();
		var pathD =
			"/api/v1/projects/" + encodeURIComponent(projectId) + "/drawings?limit=2000&offset=0";
		var pathR = "/api/v1/projects/" + encodeURIComponent(projectId) + "/rfis";
		var pathS = "/api/v1/projects/" + encodeURIComponent(projectId) + "/submittals";

		setPaneLoading("proj-pane-drawings", true);
		setPaneLoading("proj-pane-rfi", true);
		setPaneLoading("proj-pane-submittals", true);
		setPaneError("proj-pane-drawings", "");
		setPaneError("proj-pane-rfi", "");
		setPaneError("proj-pane-submittals", "");

		return Promise.all([
			fetchJson(pathD)
				.then(function (d) {
					cache.drawingSheets = d.items || [];
					repopulateDrawingFacetSelects(cache.drawingSheets);
					setPaneLoading("proj-pane-drawings", false);
					if (drawingsTabulator) {
						drawingsTabulator.destroy();
						drawingsTabulator = null;
					}
					applyDrawingFilter();
				})
				.catch(function (err) {
					cache.drawingSheets = [];
					setPaneLoading("proj-pane-drawings", false);
					setPaneError("proj-pane-drawings", err.message || String(err));
					if (drawingsTabulator) {
						drawingsTabulator.destroy();
						drawingsTabulator = null;
					}
					applyDrawingFilter();
				}),
			fetchJson(pathR)
				.then(function (d) {
					cache.rfis = d.items || [];
					setPaneLoading("proj-pane-rfi", false);
					applyRfiFilter();
				})
				.catch(function (err) {
					cache.rfis = [];
					setPaneLoading("proj-pane-rfi", false);
					setPaneError("proj-pane-rfi", err.message || String(err));
					applyRfiFilter();
				}),
			fetchJson(pathS)
				.then(function (d) {
					cache.submittals = d.items || [];
					setPaneLoading("proj-pane-submittals", false);
					applySubmittalFilter();
				})
				.catch(function (err) {
					cache.submittals = [];
					setPaneLoading("proj-pane-submittals", false);
					setPaneError("proj-pane-submittals", err.message || String(err));
					applySubmittalFilter();
				}),
		]);
	}

	function updateRfiLinks(pid) {
		var open = document.getElementById("usis-rfi-open-log");
		var create = document.getElementById("usis-rfi-open-create");
		if (open) open.setAttribute("href", "construction/rfis.html?project_id=" + encodeURIComponent(pid));
		if (create) create.setAttribute("href", "construction/rfi-create.html?project_id=" + encodeURIComponent(pid));
	}

	function init() {
		var pid = projectIdFromQuery();
		if (!pid) return;
		activeProjectId = pid;
		updateRfiLinks(pid);
		loadAll(pid);
	}

	if (document.readyState === "loading") {
		document.addEventListener("DOMContentLoaded", init);
	} else {
		init();
	}
})();
