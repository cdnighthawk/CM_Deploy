/**
 * Shared Drawings / Specs / RFI panels for lead-detail, estimate-detail (project-linked).
 * USISProjectDocPanels.init(config) — optional config.event to auto-listen.
 */
(function (global) {
	"use strict";

	function explicitWindowApiBase() {
		if (typeof global.USIS_API_BASE !== "string") return null;
		var s = global.USIS_API_BASE.trim().replace(/\/$/, "");
		if (!s) return null;
		try {
			if (new URL(s).origin === global.location.origin) return null;
		} catch (e) {}
		return s;
	}

	function metaApiBase() {
		if (typeof document === "undefined" || !document.querySelector) return null;
		var m = document.querySelector('meta[name="usis-api-base"]');
		if (!m) return null;
		var c = (m.getAttribute("content") || "").trim().replace(/\/$/, "");
		return c || null;
	}

	function apiBase() {
		if (typeof global.usisApiBase === "function") return global.usisApiBase();
		var fromWin = explicitWindowApiBase();
		if (fromWin) return fromWin;
		var fromMeta = metaApiBase();
		if (fromMeta) return fromMeta;
		var loc = global.location;
		if (loc.protocol === "file:") return "http://127.0.0.1:5000";
		var host = loc.hostname || "";
		var proto = loc.protocol || "http:";
		var port = String(loc.port || "");
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
		if (devPorts[port]) return "";
		var loopback = host === "localhost" || host === "127.0.0.1" || host === "::1";
		if (loopback) {
			if (port === "5000") return "";
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

	function actorHeaders() {
		var id = null;
		try {
			id = global.localStorage.getItem("usisActorUserId");
		} catch (e) {}
		if (id && id.trim()) return { "X-Usis-User-Id": id.trim() };
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

	function esc(s) {
		if (s == null) return "";
		var d = document.createElement("div");
		d.textContent = String(s);
		return d.innerHTML;
	}

	function el(id) {
		return id ? document.getElementById(id) : null;
	}

	function init(userConfig) {
		var cfg = userConfig || {};
		var ids = cfg.ids || {};
		var panes = cfg.panes || {};
		var cache = { drawingSheets: [], rfis: [] };
		var filtersWired = false;
		var drawingsTabulator = null;
		var activeProjectId = null;

		function viewerHref(pid, drawingRevId) {
			var q =
				"construction/drawing-viewer.html?project_id=" +
				encodeURIComponent(pid) +
				"&drawing_id=" +
				encodeURIComponent(drawingRevId);
			if (cfg.returnUrl) {
				q += "&return_url=" + encodeURIComponent(global.location.href);
			}
			return q;
		}

		function setPaneLoading(paneId, loading) {
			var pane = el(paneId);
			if (!pane) return;
			var n = pane.querySelector("[data-usis-loading]");
			if (n) n.classList.toggle("d-none", !loading);
		}

		function setPaneError(paneId, msg) {
			var pane = el(paneId);
			if (!pane) return;
			var n = pane.querySelector("[data-usis-error]");
			if (!n) return;
			if (msg) {
				n.textContent = msg;
				n.classList.remove("d-none");
			} else {
				n.textContent = "";
				n.classList.add("d-none");
			}
		}

		function fetchJson(path) {
			var url = apiBase() + path;
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

		function showNoProject() {
			var nd = el(ids.drawingsNoProject);
			var nr = el(ids.rfiNoProject);
			var td = el(ids.drawingsTools);
			var tr = el(ids.rfiTools);
			var upb = el(ids.drawingUploadOpen);
			var snp = el(ids.specsNoProject);
			var sroot = el(ids.specsRoot);
			var sfull = el(ids.specsOpenFull);
			if (nd) nd.classList.remove("d-none");
			if (nr) nr.classList.remove("d-none");
			if (td) td.classList.add("d-none");
			if (tr) tr.classList.add("d-none");
			if (upb) upb.classList.add("d-none");
			if (snp) snp.classList.remove("d-none");
			if (sroot) {
				sroot.classList.add("d-none");
				sroot.innerHTML = "";
			}
			if (sfull) sfull.classList.add("d-none");
			if (panes.drawings) setPaneLoading(panes.drawings, false);
			if (panes.rfi) setPaneLoading(panes.rfi, false);
		}

		function showProject() {
			var nd = el(ids.drawingsNoProject);
			var nr = el(ids.rfiNoProject);
			var td = el(ids.drawingsTools);
			var tr = el(ids.rfiTools);
			var upb = el(ids.drawingUploadOpen);
			var snp = el(ids.specsNoProject);
			var sroot = el(ids.specsRoot);
			var sfull = el(ids.specsOpenFull);
			if (nd) nd.classList.add("d-none");
			if (nr) nr.classList.add("d-none");
			if (td) td.classList.remove("d-none");
			if (tr) tr.classList.remove("d-none");
			if (upb) upb.classList.remove("d-none");
			if (snp) snp.classList.add("d-none");
			if (sroot) sroot.classList.remove("d-none");
			if (sfull) sfull.classList.remove("d-none");
		}

		function updateRfiLinks(pid) {
			var open = el(ids.rfiOpenLog);
			var create = el(ids.rfiOpenCreate);
			if (open) open.setAttribute("href", "construction/rfis.html?project_id=" + encodeURIComponent(pid));
			if (create) create.setAttribute("href", "construction/rfi-create.html?project_id=" + encodeURIComponent(pid));
		}

		function repopulateDrawingFacetSelects(items) {
			var discSel = el(ids.filterDrawingDiscipline);
			var setSel = el(ids.filterDrawingSet);
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
			var inp = el(ids.searchDrawings);
			var discSel = el(ids.filterDrawingDiscipline);
			var setSel = el(ids.filterDrawingSet);
			var q = inp && inp.value ? inp.value.trim().toLowerCase() : "";
			var disc = discSel ? discSel.value : "";
			var setv = setSel ? setSel.value : "";
			return (items || []).filter(function (s) {
				if (disc && (s.discipline || "") !== disc) return false;
				if (setv && (s.drawing_set || "") !== setv) return false;
				if (!q) return true;
				return JSON.stringify(s).toLowerCase().indexOf(q) !== -1;
			});
		}

		function buildOrRefreshDrawingsTabulator() {
			var grid = el(ids.gridDrawings);
			if (!grid) return;
			var rows = filterDrawingSheetsClient(cache.drawingSheets);
			if (typeof Tabulator === "undefined") {
				grid.innerHTML =
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
							a.href = viewerHref(pid, cr.id);
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
						if (!wrap.childNodes.length) wrap.textContent = "—";
						return wrap;
					},
				},
			];
			if (drawingsTabulator) {
				drawingsTabulator.setData(rows);
				return;
			}
			drawingsTabulator = new Tabulator(grid, {
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

		function applyDrawingFilter() {
			buildOrRefreshDrawingsTabulator();
		}

		function filterRows(rows, q, statusVal, getStatus) {
			var qq = (q || "").trim().toLowerCase();
			var st = (statusVal || "").trim().toLowerCase();
			return rows.filter(function (r) {
				if (st && String(getStatus(r) || "").toLowerCase() !== st) return false;
				if (!qq) return true;
				return JSON.stringify(r).toLowerCase().indexOf(qq) !== -1;
			});
		}

		function renderRfiTable(items) {
			var tbody = el(ids.tbodyRfis);
			if (!tbody) return;
			tbody.innerHTML = "";
			if (!items.length) {
				tbody.innerHTML =
					'<tr><td colspan="8" class="text-muted text-center py-4">No RFIs yet. Use "+ Create RFI" to start the log.</td></tr>';
				return;
			}
			items.forEach(function (row) {
				var tr = document.createElement("tr");
				var num = row.display_number || "RFI-" + row.number;
				var detail = "construction/rfi-detail.html?id=" + encodeURIComponent(row.id);
				var assignees = (row.assignees || [])
					.map(function (a) {
						return esc(a.user ? a.user.name : "");
					})
					.filter(Boolean)
					.join(", ") || "—";
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

		function applyRfiFilter() {
			var inp = el(ids.searchRfis);
			var sel = el(ids.filterRfiStatus);
			var q = inp ? inp.value : "";
			var st = sel ? sel.value : "";
			var rows = filterRows(cache.rfis, q, st, function (r) {
				return r.status;
			});
			renderRfiTable(rows);
		}

		function wireFiltersOnce() {
			if (filtersWired) return;
			filtersWired = true;
			var d = el(ids.searchDrawings);
			if (d) d.addEventListener("input", applyDrawingFilter);
			var dd = el(ids.filterDrawingDiscipline);
			var ds = el(ids.filterDrawingSet);
			if (dd) dd.addEventListener("change", applyDrawingFilter);
			if (ds) ds.addEventListener("change", applyDrawingFilter);
			var r1 = el(ids.searchRfis);
			var r2 = el(ids.filterRfiStatus);
			if (r1) r1.addEventListener("input", applyRfiFilter);
			if (r2) r2.addEventListener("change", applyRfiFilter);

			var upBtn = el(ids.drawingUploadSubmit);
			if (upBtn && !upBtn.dataset.usisWired) {
				upBtn.dataset.usisWired = "1";
				upBtn.addEventListener("click", function () {
					var pid = activeProjectId;
					if (!pid) return;
					var err = el(ids.drawingUploadErr);
					var fileEl = el(ids.drawingFile);
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
					fd.append("split_pages", "true");
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
									var msg = res.status + " " + (t || res.statusText);
									try {
										var j = JSON.parse(t);
										if (j && (j.error || j.detail)) {
											msg = [j.error, j.detail].filter(Boolean).join(": ");
										}
									} catch (parseErr) {
										/* not JSON */
									}
									throw new Error(msg);
								});
							}
							return res.json();
						})
						.then(function () {
							var modalEl = el(ids.modalDrawingCreate);
							if (modalEl && global.bootstrap && global.bootstrap.Modal) {
								var inst = global.bootstrap.Modal.getInstance(modalEl);
								if (inst) inst.hide();
							}
							if (fileEl) fileEl.value = "";
							return loadProject(pid);
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

		function mountSpecs(projectId) {
			var sroot = el(ids.specsRoot);
			var sfull = el(ids.specsOpenFull);
			if (sfull && projectId) {
				sfull.setAttribute("href", "construction/specs-viewer.html?project_id=" + encodeURIComponent(projectId));
			}
			if (!sroot || !projectId || typeof global.USISSpecsBook === "undefined") return;
			sroot.innerHTML = "";
			global.USISSpecsBook.mount(sroot, projectId);
		}

		function loadDrawingsAndRfis(projectId) {
			wireFiltersOnce();
			var pathD = "/api/v1/projects/" + encodeURIComponent(projectId) + "/drawings?limit=2000&offset=0";
			var pathR = "/api/v1/projects/" + encodeURIComponent(projectId) + "/rfis";

			if (panes.drawings) setPaneLoading(panes.drawings, true);
			if (panes.rfi) setPaneLoading(panes.rfi, true);
			if (panes.drawings) setPaneError(panes.drawings, "");
			if (panes.rfi) setPaneError(panes.rfi, "");

			return Promise.all([
				fetchJson(pathD)
					.then(function (d) {
						cache.drawingSheets = d.items || [];
						repopulateDrawingFacetSelects(cache.drawingSheets);
						if (panes.drawings) setPaneLoading(panes.drawings, false);
						if (drawingsTabulator) {
							drawingsTabulator.destroy();
							drawingsTabulator = null;
						}
						applyDrawingFilter();
					})
					.catch(function (err) {
						cache.drawingSheets = [];
						if (panes.drawings) setPaneLoading(panes.drawings, false);
						if (panes.drawings) setPaneError(panes.drawings, err.message || String(err));
						if (drawingsTabulator) {
							drawingsTabulator.destroy();
							drawingsTabulator = null;
						}
						applyDrawingFilter();
					}),
				fetchJson(pathR)
					.then(function (d) {
						cache.rfis = d.items || [];
						if (panes.rfi) setPaneLoading(panes.rfi, false);
						applyRfiFilter();
					})
					.catch(function (err) {
						cache.rfis = [];
						if (panes.rfi) setPaneLoading(panes.rfi, false);
						if (panes.rfi) setPaneError(panes.rfi, err.message || String(err));
						applyRfiFilter();
					}),
			]);
		}

		function resetCache() {
			activeProjectId = null;
			if (cfg.projectIdGlobalKey) global[cfg.projectIdGlobalKey] = null;
			cache.drawingSheets = [];
			cache.rfis = [];
			if (drawingsTabulator) {
				try {
					drawingsTabulator.destroy();
				} catch (e) {}
				drawingsTabulator = null;
			}
		}

		function loadProject(projectId) {
			if (!projectId) {
				resetCache();
				showNoProject();
				return Promise.resolve();
			}
			activeProjectId = projectId;
			if (cfg.projectIdGlobalKey) global[cfg.projectIdGlobalKey] = projectId;
			showProject();
			updateRfiLinks(projectId);
			return loadDrawingsAndRfis(projectId).then(function () {
				mountSpecs(projectId);
			});
		}

		function onItemLoaded(item) {
			var getPid = cfg.getProjectId || function (it) {
				return it && it.project_id;
			};
			var pid = item ? getPid(item) : null;
			if (pid) return loadProject(pid);
			resetCache();
			showNoProject();
			return Promise.resolve();
		}

		if (cfg.event) {
			document.addEventListener(cfg.event, function (ev) {
				var d = ev.detail || {};
				if (d.error || !d.item) {
					resetCache();
					showNoProject();
					return;
				}
				onItemLoaded(d.item);
			});
		}

		return {
			loadProject: loadProject,
			showNoProject: function () {
				resetCache();
				showNoProject();
			},
			reset: resetCache,
			onItemLoaded: onItemLoaded,
		};
	}

	global.USISProjectDocPanels = { init: init };
})(typeof window !== "undefined" ? window : this);
