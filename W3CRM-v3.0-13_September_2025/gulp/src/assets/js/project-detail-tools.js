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

	function setSubmittalCreateVisible(canCreate) {
		var btn = document.getElementById("usis-submittal-open-create");
		if (!btn) return;
		btn.classList.toggle("d-none", canCreate === false);
	}

	function apiBase() {
		return window.USIS_API.apiBase();
	}

	function actorHeaders() {
		return window.USIS_API.actorHeaders();
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
		if (window.USISProjectContext && typeof window.USISProjectContext.projectIdFromQuery === "function") {
			return window.USISProjectContext.projectIdFromQuery();
		}
		var p = new URLSearchParams(window.location.search);
		var id = (p.get("id") || p.get("project_id") || p.get("projectId") || "").trim();
		return id || null;
	}

	function esc(s) {
		if (s == null || s === "") return "";
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

	function setDrawingGroupsOpen(table, pid, open) {
		if (!table || typeof table.getGroups !== "function") return;
		var map = {};
		var canBlock = typeof table.blockRedraw === "function" && typeof table.restoreRedraw === "function";
		if (canBlock) table.blockRedraw();
		try {
			var n = (table.getGroups() || []).length;
			for (var i = 0; i < n; i++) {
				var g = (table.getGroups() || [])[i];
				if (!g) continue;
				var key = typeof g.getKey === "function" ? g.getKey() : "";
				if (open) {
					if (typeof g.show === "function") g.show();
				} else {
					if (key) map[key] = 1;
					if (typeof g.hide === "function") g.hide();
				}
			}
		} finally {
			if (canBlock) table.restoreRedraw();
		}
		writeDrawingGroupCollapsed(pid, open ? {} : map);
		var leftover = (table.getGroups() || []).some(function (g) {
			return typeof g.isVisible === "function" && (open ? !g.isVisible() : g.isVisible());
		});
		if (leftover && typeof table.setGroupBy === "function" && table.options && table.options.groupBy) {
			table.setGroupBy(table.options.groupBy);
		}
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
		var grid = document.getElementById("usis-grid-drawings");
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
		var url = "";
		if (raw) {
			url = /^https?:\/\//i.test(raw)
				? raw
				: (typeof window.usisApiBase === "function" ? window.usisApiBase() : "") +
				  (raw.charAt(0) === "/" ? raw : "/" + raw);
		} else if (cr.id) {
			url =
				(typeof window.usisApiBase === "function" ? window.usisApiBase() : "") +
				"/api/v1/drawings/" +
				encodeURIComponent(cr.id) +
				"/file";
		}
		if (!url) return null;
		var label = ((sheet.sheet_number || "drawing") + " " + (sheet.sheet_title || "")).trim();
		var name = (window.USISUi && USISUi.safeFilename ? USISUi.safeFilename(label) : label) + ".pdf";
		return { url: url, name: name };
	}

	function downloadSelectedDrawings() {
		var jobs = filterDrawingSheetsClient(cache.drawingSheets)
			.filter(function (s) {
				return drawingSelected.has(drawingRowId(s));
			})
			.map(drawingFileJob)
			.filter(Boolean);
		if (window.USISUi && typeof USISUi.downloadFiles === "function") {
			USISUi.downloadFiles(jobs, { emptyMsg: "Selected drawings have no file to download." });
			return;
		}
		jobs.forEach(function (job) {
			window.open(job.url, "_blank", "noopener");
		});
	}

	function drawingCheckboxColumn() {
		return {
			title: "",
			field: "_sel",
			cssClass: "usis-doc-check-col",
			width: 52,
			minWidth: 52,
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

	function drawingViewerHref(pid, drawingRevId) {
		if (!pid || !drawingRevId) return "";
		var href =
			"construction/drawing-viewer.html?project_id=" +
			encodeURIComponent(pid) +
			"&drawing_id=" +
			encodeURIComponent(drawingRevId);
		var setv = selectedDrawingSet();
		if (setv) href += "&drawing_set=" + encodeURIComponent(setv);
		return href;
	}

	function drawingNameLinkFormatter(field, pid) {
		return function (cell) {
			var data = cell.getRow().getData();
			var text = data[field];
			if (text == null || String(text).trim() === "") text = "—";
			else text = String(text);
			var cr = data.current_revision;
			var href = cr && cr.id ? drawingViewerHref(pid, cr.id) : "";
			var wrap = document.createElement("span");
			wrap.className = "usis-drawing-cell";
			if (href) {
				var a = document.createElement("a");
				a.href = href;
				a.className = "usis-drawing-name-link";
				a.textContent = text;
				wrap.appendChild(a);
			} else {
				wrap.appendChild(document.createTextNode(text));
			}
			var btn = document.createElement("button");
			btn.type = "button";
			btn.className = "btn btn-link btn-sm p-0 usis-drawing-rename";
			btn.textContent = "Edit";
			btn.title = field === "sheet_number" ? "Change drawing #" : "Change drawing name";
			btn.addEventListener("click", function (ev) {
				ev.preventDefault();
				ev.stopPropagation();
				cell.edit(true);
			});
			wrap.appendChild(btn);
			return wrap;
		};
	}

	function applySheetIdentityToCache(seriesId, fields) {
		(cache.drawingSheets || []).forEach(function (sheet) {
			if (!sheet || sheet.series_id !== seriesId) return;
			if (fields.sheet_number !== undefined) sheet.sheet_number = fields.sheet_number;
			if (fields.sheet_title !== undefined) sheet.sheet_title = fields.sheet_title;
			if (sheet.current_revision) {
				if (fields.sheet_number !== undefined) sheet.current_revision.sheet_number = fields.sheet_number;
				if (fields.sheet_title !== undefined) sheet.current_revision.sheet_title = fields.sheet_title;
			}
			(sheet.revisions || []).forEach(function (rev) {
				if (fields.sheet_number !== undefined) rev.sheet_number = fields.sheet_number;
				if (fields.sheet_title !== undefined) rev.sheet_title = fields.sheet_title;
			});
		});
	}

	function saveDrawingIdentity(cell) {
		var field = cell.getField();
		if (field !== "sheet_number" && field !== "sheet_title") return;
		var row = cell.getRow();
		var data = row.getData();
		var cr = data.current_revision;
		var oldVal = cell.getOldValue();
		if (!cr || !cr.id) {
			cell.setValue(oldVal, true);
			return;
		}
		var payload = { scope: "series" };
		payload[field] = cell.getValue() == null ? "" : String(cell.getValue()).trim();
		fetchJsonBody("PATCH", "/api/v1/drawings/" + encodeURIComponent(cr.id), payload)
			.then(function (body) {
				var fields = {};
				fields[field] = payload[field] || null;
				if (body && body.item) {
					if (body.item.sheet_number !== undefined) fields.sheet_number = body.item.sheet_number;
					if (body.item.sheet_title !== undefined) fields.sheet_title = body.item.sheet_title;
				}
				applySheetIdentityToCache(data.series_id, fields);
				row.update(fields);
				if (window.USISNotify) window.USISNotify.success("Drawing saved.");
			})
			.catch(function (err) {
				cell.setValue(oldVal, true);
				if (window.USISNotify) window.USISNotify.error(String((err && err.message) || err || "Save failed."));
			});
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
					throw new Error(apiErrorMessage(res.status, t || res.statusText));
				});
			}
			return res.json();
		});
	}

	function apiErrorMessage(status, text) {
		var raw = String(text || "").trim();
		try {
			var j = JSON.parse(raw);
			if (j && j.error) raw = String(j.error);
		} catch (e) {
			/* keep raw */
		}
		if (status === 403 && /not allowed to create submittals/i.test(raw)) {
			return "Your role cannot create submittals.";
		}
		if (status === 403) return raw || "You do not have permission to do that.";
		return raw || String(status);
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

	function ensureCurrentDrawingsButton(setSel) {
		if (!setSel) return;
		var toolbar = setSel.closest(".usis-tool-toolbar");
		var btn = toolbar && toolbar.querySelector(".usis-drawing-set-current");
		if (!btn) {
			btn = document.createElement("button");
			btn.type = "button";
			btn.className = "btn btn-sm btn-outline-primary usis-drawing-set-current text-nowrap";
			btn.textContent = "Current";
			btn.title = "Latest revision of each sheet";
			var host = setSel.closest(".usis-sheet-filter") || setSel.parentNode;
			if (!host || !host.parentNode) return;
			host.insertAdjacentElement("afterend", btn);
		}
		if (btn.dataset.usisBound === "1") return;
		btn.dataset.usisBound = "1";
		btn.addEventListener("click", function () {
			setSel.value = "";
			applyDrawingFilter();
		});
	}

	function sheetSetNames(s) {
		var out = {};
		if (s && s.drawing_set) out[s.drawing_set] = 1;
		(s && s.sets ? s.sets : []).forEach(function (name) {
			if (name) out[name] = 1;
		});
		(s && s.revisions ? s.revisions : []).forEach(function (r) {
			if (r && r.drawing_set) out[r.drawing_set] = 1;
		});
		return Object.keys(out);
	}

	function setNameKey(name) {
		return String(name || "").trim().toLowerCase();
	}

	function revisionForSet(s, setv) {
		var want = setNameKey(setv);
		if (!want || !s) return null;
		var revs = s.revisions || [];
		for (var i = 0; i < revs.length; i++) {
			if (setNameKey(revs[i] && revs[i].drawing_set) === want) return revs[i];
		}
		if (setNameKey(s.drawing_set) === want) return s.current_revision || null;
		return null;
	}

	function pinSheetToSet(s, setv) {
		var rev = revisionForSet(s, setv);
		if (!rev) return null;
		var pinned = Object.assign({}, s);
		pinned.drawing_set = rev.drawing_set;
		pinned.sheet_number = rev.sheet_number || s.sheet_number;
		pinned.sheet_title = rev.sheet_title || rev.title || s.sheet_title;
		pinned.discipline = rev.discipline || s.discipline;
		pinned.current_revision = rev;
		return pinned;
	}

	function selectedDrawingSet() {
		var setSel = document.getElementById("usis-filter-drawing-set");
		return setSel && setSel.value ? setSel.value : "";
	}

	function repopulateDrawingFacetSelects(items) {
		var discSel = document.getElementById("usis-filter-drawing-discipline");
		var setSel = document.getElementById("usis-filter-drawing-set");
		var discSet = {};
		var setSet = {};
		(items || []).forEach(function (s) {
			if (s.discipline) discSet[s.discipline] = 1;
			sheetSetNames(s).forEach(function (name) {
				setSet[name] = 1;
			});
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
				setSel.innerHTML = '<option value="">Current</option>';
				Object.keys(setSet)
					.sort(function (a, b) {
						return a.localeCompare(b, undefined, { numeric: true });
					})
					.forEach(function (k) {
						var o = document.createElement("option");
						o.value = k;
						o.textContent = k;
						setSel.appendChild(o);
					});
				if (curS && setSet[curS]) setSel.value = curS;
				else setSel.value = "";
				ensureCurrentDrawingsButton(setSel);
			}
	}

	function filterDrawingSheetsClient(items) {
		var inp = document.getElementById("usis-search-drawings");
		var discSel = document.getElementById("usis-filter-drawing-discipline");
		var q = (inp && inp.value) ? inp.value.trim().toLowerCase() : "";
		var disc = discSel ? discSel.value : "";
		var setv = selectedDrawingSet();
		var out = [];
		(items || []).forEach(function (s) {
			var row = setv ? pinSheetToSet(s, setv) : s;
			if (!row) return;
			if (disc && (row.discipline || "") !== disc) return;
			if (q && JSON.stringify(row).toLowerCase().indexOf(q) === -1) return;
			out.push(row);
		});
		return out;
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
			drawingCheckboxColumn(),
			{
				title: "Sheet #",
				field: "sheet_number",
				headerFilter: "input",
				minWidth: 100,
				widthGrow: 1,
				editor: "input",
				formatter: drawingNameLinkFormatter("sheet_number", pid),
			},
			{
				title: "Title",
				field: "sheet_title",
				headerFilter: "input",
				minWidth: 160,
				widthGrow: 2,
				editor: "input",
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
		ensureDrawingGroupToolbar(el);
		if (drawingsTabulator) {
			drawingsTabulator.setData(rows);
			return;
		}
		drawingsTabulator = new Tabulator(el, {
			data: rows,
			layout: "fitColumns",
			pagination: false,
			movableColumns: true,
			placeholder: "No drawings for this project yet.",
			columns: cols,
			cellEdited: saveDrawingIdentity,
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
				fd.append("split_pages", "true");
				var discEl = document.getElementById("usis-drawing-discipline");
				var setEl = document.getElementById("usis-drawing-set");
				if (discEl && discEl.value) fd.append("discipline", discEl.value);
				if (setEl && setEl.value) fd.append("drawing_set", setEl.value.trim());
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
									/* not JSON — keep raw text */
								}
								throw new Error(msg);
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
					if (window.USISDrawingCache) window.USISDrawingCache.prefetchSheets(cache.drawingSheets);
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
					setSubmittalCreateVisible(!(d.permissions && d.permissions.can_create === false));
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
		var subCreate = document.getElementById("usis-submittal-open-create");
		if (subCreate) {
			subCreate.setAttribute("href", "construction/submittal-create.html?project_id=" + encodeURIComponent(pid));
		}
		var poCreate = document.getElementById("usis-po-open-create");
		if (poCreate) {
			poCreate.setAttribute("href", "construction/purchase-order-create.html?project_id=" + encodeURIComponent(pid));
		}
		var pricing = document.getElementById("usis-pricing-open");
		if (pricing)
			pricing.setAttribute(
				"href",
				"construction/construction-pricing.html?project_id=" + encodeURIComponent(pid)
			);
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
