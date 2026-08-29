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

	function drawingDisciplineGroup(data) {
		var d = data && data.discipline != null ? String(data.discipline).trim() : "";
		return d || "Unassigned";
	}

	function drawingGroupStorageKey(pid) {
		return "usis-draw-groups-collapsed:" + String(pid || "");
	}

	function readDrawingGroupCollapsed(pid) {
		try {
			var raw = sessionStorage.getItem(drawingGroupStorageKey(pid));
			return raw ? JSON.parse(raw) : {};
		} catch (e) {
			return {};
		}
	}

	function writeDrawingGroupCollapsed(pid, map) {
		try {
			sessionStorage.setItem(drawingGroupStorageKey(pid), JSON.stringify(map || {}));
		} catch (e) {}
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
		var activeLeadId = null;

		function setDrawingGroupsOpen(table, pid, open) {
			if (!table || typeof table.getGroups !== "function") return;
			var map = {};
			table.getGroups().forEach(function (g) {
				if (open) g.show();
				else {
					g.hide();
					map[g.getKey()] = 1;
				}
			});
			writeDrawingGroupCollapsed(pid, open ? {} : map);
		}

		function bindDrawingGroupPersistence(table) {
			if (!table || table._usisGroupBound) return;
			table._usisGroupBound = true;
			table.on("groupVisibilityChanged", function (group, visible) {
				var pid = activeProjectId || "";
				var map = readDrawingGroupCollapsed(pid);
				var key = group.getKey();
				if (visible) delete map[key];
				else map[key] = 1;
				writeDrawingGroupCollapsed(pid, map);
			});
		}

		var drawingSelected = new Set();

		function drawingRowId(data) {
			return data && data.series_id ? String(data.series_id) : "";
		}

		function drawingDownloadBtn() {
			var grid = el(ids.gridDrawings);
			var bar = grid && grid.previousElementSibling;
			return bar && bar.classList.contains("usis-draw-group-toolbar")
				? bar.querySelector(".usis-draw-download")
				: null;
		}

		function updateDrawingDownloadBtn() {
			var btn = drawingDownloadBtn();
			if (!btn) return;
			var n = drawingSelected.size;
			btn.classList.toggle("d-none", n === 0);
			btn.disabled = n === 0;
			btn.textContent = n <= 1 ? "Download" : "Download (" + n + ")";
		}

		function drawingFileJob(sheet) {
			var cr = (sheet && sheet.current_revision) || {};
			var raw = cr.file_url || "";
			var url = raw ? resolveAssetUrl(raw) : "";
			if (!url && cr.id) {
				url = apiBase() + "/api/v1/drawings/" + encodeURIComponent(cr.id) + "/file";
			}
			if (!url) return null;
			var label = ((sheet.sheet_number || "drawing") + " " + (sheet.sheet_title || "")).trim();
			var name = (global.USISUi && USISUi.safeFilename ? USISUi.safeFilename(label) : label) + ".pdf";
			return { url: url, name: name };
		}

		function downloadSelectedDrawings() {
			var jobs = (cache.drawingSheets || [])
				.filter(function (s) {
					return drawingSelected.has(drawingRowId(s));
				})
				.map(drawingFileJob)
				.filter(Boolean);
			if (global.USISUi && typeof USISUi.downloadFiles === "function") {
				USISUi.downloadFiles(jobs, { emptyMsg: "Selected drawings have no file to download." });
				return;
			}
			jobs.forEach(function (job) {
				global.open(job.url, "_blank", "noopener");
			});
		}

		function drawingCheckboxColumn() {
			return {
				title: "",
				field: "_sel",
				cssClass: "usis-doc-check-col",
				width: 44,
				minWidth: 44,
				hozAlign: "center",
				headerHozAlign: "center",
				headerSort: false,
				resizable: false,
				frozen: true,
				titleFormatter: function () {
					var cb = document.createElement("input");
					cb.type = "checkbox";
					cb.className = "form-check-input m-0";
					cb.setAttribute("aria-label", "Select all drawings");
					cb.addEventListener("click", function (e) {
						e.stopPropagation();
					});
					cb.addEventListener("change", function () {
						if (!drawingsTabulator) return;
						drawingsTabulator.getRows().forEach(function (row) {
							var id = drawingRowId(row.getData());
							if (!id) return;
							if (cb.checked) drawingSelected.add(id);
							else drawingSelected.delete(id);
							var cell = row.getCell("_sel");
							var box = cell && cell.getElement() && cell.getElement().querySelector("input[type=checkbox]");
							if (box) box.checked = cb.checked;
						});
						updateDrawingDownloadBtn();
					});
					return cb;
				},
				formatter: function (cell) {
					var data = cell.getRow().getData();
					var id = drawingRowId(data);
					var cb = document.createElement("input");
					cb.type = "checkbox";
					cb.className = "form-check-input m-0";
					cb.checked = !!(id && drawingSelected.has(id));
					cb.setAttribute("aria-label", "Select drawing");
					cb.addEventListener("click", function (e) {
						e.stopPropagation();
					});
					cb.addEventListener("change", function () {
						if (!id) return;
						if (cb.checked) drawingSelected.add(id);
						else drawingSelected.delete(id);
						updateDrawingDownloadBtn();
					});
					return cb;
				},
			};
		}

		function ensureDrawingGroupToolbar(gridEl) {
			if (!gridEl || !gridEl.parentNode) return;
			var bar = gridEl.previousElementSibling;
			if (!bar || !bar.classList.contains("usis-draw-group-toolbar")) {
				bar = document.createElement("div");
				bar.className = "usis-draw-group-toolbar d-flex flex-wrap align-items-center gap-2 mb-2";
				bar.innerHTML =
					'<button type="button" class="btn btn-link btn-sm p-0 usis-draw-expand-all">Expand all</button>' +
					'<span class="text-muted">·</span>' +
					'<button type="button" class="btn btn-link btn-sm p-0 usis-draw-collapse-all">Collapse all</button>';
				gridEl.parentNode.insertBefore(bar, gridEl);
				bar.querySelector(".usis-draw-expand-all").addEventListener("click", function () {
					if (drawingsTabulator) setDrawingGroupsOpen(drawingsTabulator, activeProjectId || "", true);
				});
				bar.querySelector(".usis-draw-collapse-all").addEventListener("click", function () {
					if (drawingsTabulator) setDrawingGroupsOpen(drawingsTabulator, activeProjectId || "", false);
				});
			}
			if (!bar.querySelector(".usis-draw-download")) {
				var dl = document.createElement("button");
				dl.type = "button";
				dl.className = "btn btn-sm btn-primary usis-draw-download d-none";
				dl.textContent = "Download";
				bar.appendChild(dl);
				dl.addEventListener("click", downloadSelectedDrawings);
			}
			updateDrawingDownloadBtn();
		}

		function drawingNameLinkFormatter(field, pid) {
			return function (cell) {
				var data = cell.getRow().getData();
				var text = data[field];
				if (text == null || String(text).trim() === "") text = "—";
				else text = String(text);
				var cr = data.current_revision;
				var href = cr && cr.id ? viewerHref(pid, cr.id) : "";
				if (!href) return text;
				var a = document.createElement("a");
				a.href = href;
				a.className = "usis-drawing-name-link";
				a.textContent = text;
				return a;
			};
		}

		function viewerHref(pid, drawingRevId) {
			var parts = [];
			if (pid) parts.push("project_id=" + encodeURIComponent(pid));
			if (drawingRevId) parts.push("drawing_id=" + encodeURIComponent(drawingRevId));
			if (activeLeadId) parts.push("lead_id=" + encodeURIComponent(activeLeadId));
			if (cfg.fromPage) parts.push("from=" + encodeURIComponent(cfg.fromPage));
			if (cfg.returnUrl) {
				parts.push("return_url=" + encodeURIComponent(global.location.href));
			}
			return "construction/drawing-viewer.html" + (parts.length ? "?" + parts.join("&") : "");
		}

		function updateOpenViewer(pid) {
			var btn = el(ids.openViewer);
			if (!btn) return;
			if (pid || activeLeadId) {
				btn.classList.remove("d-none");
				btn.setAttribute("href", viewerHref(pid, null));
			} else {
				btn.classList.add("d-none");
			}
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

		function fetchJson(path, options) {
			var opts = options || {};
			var url = apiBase() + path;
			var headers = Object.assign({ Accept: "application/json" }, actorHeaders(), opts.headers || {});
			return fetch(url, {
				method: opts.method || "GET",
				credentials: "include",
				headers: headers,
				body: opts.body,
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
			if (cfg.allowDrawingsWithoutProject && upb) upb.classList.remove("d-none");
			updateOpenViewer(null);
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
			updateOpenViewer(activeProjectId);
		}

		function updateRfiLinks(pid) {
			var open = el(ids.rfiOpenLog);
			var create = el(ids.rfiOpenCreate);
			var qs = [];
			if (pid) qs.push("project_id=" + encodeURIComponent(pid));
			if (activeLeadId) qs.push("lead_id=" + encodeURIComponent(activeLeadId));
			var q = qs.length ? "?" + qs.join("&") : "";
			if (open) {
				open.setAttribute("href", "construction/rfis.html" + q);
				open.classList.remove("d-none");
			}
			if (create) {
				create.setAttribute("href", "construction/rfi-create.html" + q);
				create.classList.remove("d-none");
			}
			if (pid && global.USISProjectContext && typeof global.USISProjectContext.setProjectId === "function") {
				global.USISProjectContext.setProjectId(pid);
			}
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
				drawingCheckboxColumn(),
				{
					title: "Sheet #",
					field: "sheet_number",
					headerFilter: "input",
					minWidth: 100,
					widthGrow: 1,
					formatter: drawingNameLinkFormatter("sheet_number", pid),
				},
				{
					title: "Title",
					field: "sheet_title",
					headerFilter: "input",
					minWidth: 160,
					widthGrow: 2,
					formatter: drawingNameLinkFormatter("sheet_title", pid),
				},
				{ title: "Discipline", field: "discipline", visible: false },
				{ title: "Set", field: "drawing_set", headerFilter: "input", minWidth: 140, widthGrow: 1 },
				{ title: "Issues", field: "revision_count", hozAlign: "right", width: 90 },
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
			];
			rows.sort(function (a, b) {
				var da = drawingDisciplineGroup(a).toLowerCase();
				var db = drawingDisciplineGroup(b).toLowerCase();
				if (da !== db) return da.localeCompare(db);
				return String(a.sheet_number || "").localeCompare(String(b.sheet_number || ""), undefined, {
					numeric: true,
				});
			});
			ensureDrawingGroupToolbar(grid);
			if (drawingsTabulator) {
				drawingsTabulator.setData(rows);
				return;
			}
			drawingsTabulator = new Tabulator(grid, {
				data: rows,
				layout: "fitColumns",
				pagination: false,
				movableColumns: true,
				placeholder: "No drawings for this project yet.",
				columns: cols,
				groupBy: drawingDisciplineGroup,
				groupToggleElement: "header",
				groupStartOpen: function (value) {
					return !readDrawingGroupCollapsed(activeProjectId || "")[value];
				},
				groupHeader: function (value, count) {
					return (
						'<span class="usis-doc-group-label">' +
						esc(value || "Unassigned") +
						'</span> <span class="usis-doc-group-count">(' +
						count +
						")</span>"
					);
				},
			});
			bindDrawingGroupPersistence(drawingsTabulator);
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
				sfull.classList.remove("d-none");
			}
			if (!sroot || !projectId) return;
			sroot.classList.remove("d-none");
			if (typeof global.USISSpecsBook === "undefined") {
				sroot.innerHTML = '<div class="alert alert-danger">Spec book script failed to load.</div>';
				return;
			}
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
			mountSpecs(projectId);
			return loadDrawingsAndRfis(projectId);
		}

		function leadIdentifier(item) {
			if (typeof cfg.getLeadId === "function") return cfg.getLeadId(item);
			if (!item) return null;
			return (
				item.lead_id ||
				item.lead_estimate_id ||
				(item.lead && (item.lead.id || item.lead.external_id)) ||
				item.external_id ||
				item.id ||
				null
			);
		}

		function projectIdFromItem(item) {
			if (typeof cfg.getProjectId === "function") return cfg.getProjectId(item);
			if (!item) return null;
			return item.drawing_project_id || item.project_id || null;
		}

		function postEnsureProject(lid) {
			return fetchJson("/api/v1/lead-estimates/" + encodeURIComponent(lid) + "/ensure-project", {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: "{}",
			});
		}

		function applyEnsuredProject(item, data) {
			var next = (data && data.item) || {};
			var newPid = (data && data.project_id) || next.project_id || next.drawing_project_id;
			if (item && newPid) {
				item.project_id = newPid;
				item.drawing_project_id = next.drawing_project_id || newPid;
			}
			return newPid || null;
		}

		function showRfiEnsureError(err) {
			if (panes.rfi) {
				setPaneLoading(panes.rfi, false);
				setPaneError(panes.rfi, err && (err.message || String(err)) ? (err.message || String(err)) : "Could not open the RFI log.");
			}
			var sroot = el(ids.specsRoot);
			var snp = el(ids.specsNoProject);
			if (snp && err) {
				snp.textContent = err.message || String(err);
				snp.classList.remove("d-none");
			}
			if (sroot) sroot.classList.add("d-none");
		}

		function ensureProjectThenLoad(item) {
			activeLeadId = leadIdentifier(item);
			var pid = projectIdFromItem(item);
			updateOpenViewer(pid);
			updateRfiLinks(pid);
			var lid = cfg.ensureProjectFromLead ? activeLeadId : null;

			function loadOrHide(id) {
				if (id) return loadProject(id);
				resetCache();
				showNoProject();
				return Promise.resolve();
			}

			if (pid && !lid) return loadOrHide(pid);

			if (!lid) {
				return loadOrHide(pid);
			}

			if (pid) {
				var loading = loadProject(pid);
				return postEnsureProject(lid)
					.then(function (data) {
						var newPid = applyEnsuredProject(item, data);
						if (newPid && newPid !== pid) return loadProject(newPid);
						return loading;
					})
					.catch(function () {
						return loading;
					});
			}

			return postEnsureProject(lid)
				.then(function (data) {
					var newPid = applyEnsuredProject(item, data);
					if (!newPid) {
						resetCache();
						showNoProject();
						return;
					}
					return loadProject(newPid);
				})
				.catch(function (err) {
					resetCache();
					showNoProject();
					showRfiEnsureError(err);
				});
		}

		function onItemLoaded(item) {
			return ensureProjectThenLoad(item);
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
