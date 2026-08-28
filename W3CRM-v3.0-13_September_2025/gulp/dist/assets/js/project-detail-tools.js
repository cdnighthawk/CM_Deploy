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
	var submittalCreateLines = [];
	var submittalSpecOptions = [];

	function specLineId(line) {
		return line && line.spec_section_id != null ? String(line.spec_section_id) : "";
	}

	function renderSubmittalCreateLines() {
		var tb = document.getElementById("usis-submittal-c-lines-tbody");
		if (!tb) return;
		tb.innerHTML = "";
		if (!submittalCreateLines.length) {
			tb.innerHTML =
				'<tr><td colspan="5" class="text-muted small">No line items — check spec sections above.</td></tr>';
			return;
		}
		submittalCreateLines.forEach(function (line, idx) {
			var tr = document.createElement("tr");
			tr.innerHTML =
				"<td class=\"small\">" +
				esc(line.spec_section_code || "—") +
				"</td><td class=\"small\">" +
				esc(line.description || "—") +
				"</td><td><input type=\"text\" class=\"form-control form-control-sm usis-sub-line-mfr\" data-idx=\"" +
				idx +
				'" maxlength="200" placeholder="Optional" value="' +
				esc(line.manufacturer || "") +
				'"></td><td><input type="text" class="form-control form-control-sm usis-sub-line-model" data-idx="' +
				idx +
				'" maxlength="200" placeholder="Optional" value="' +
				esc(line.model || "") +
				'"></td><td class="text-end"><button type="button" class="btn btn-link btn-sm p-0 text-danger usis-sub-line-rm" data-idx="' +
				idx +
				'">Remove</button></td>';
			tb.appendChild(tr);
		});
		tb.querySelectorAll(".usis-sub-line-mfr").forEach(function (inp) {
			inp.addEventListener("input", function () {
				var i = parseInt(inp.getAttribute("data-idx"), 10);
				if (!isNaN(i) && submittalCreateLines[i]) {
					submittalCreateLines[i].manufacturer = inp.value.trim() || null;
				}
			});
		});
		tb.querySelectorAll(".usis-sub-line-model").forEach(function (inp) {
			inp.addEventListener("input", function () {
				var i = parseInt(inp.getAttribute("data-idx"), 10);
				if (!isNaN(i) && submittalCreateLines[i]) {
					submittalCreateLines[i].model = inp.value.trim() || null;
				}
			});
		});
		tb.querySelectorAll(".usis-sub-line-rm").forEach(function (btn) {
			btn.addEventListener("click", function () {
				var i = parseInt(btn.getAttribute("data-idx"), 10);
				if (isNaN(i)) return;
				var removed = submittalCreateLines.splice(i, 1)[0];
				var box = document.querySelector(
					'#usis-submittal-c-spec-list input[data-spec-id="' + specLineId(removed) + '"]'
				);
				if (box) box.checked = false;
				renderSubmittalCreateLines();
			});
		});
	}

	function activeSpecOptions() {
		return submittalSpecOptions.filter(function (s) {
			return s && s.is_active !== false;
		});
	}

	function setSpecChecked(spec, checked) {
		var id = spec && spec.id != null ? String(spec.id) : "";
		var idx = submittalCreateLines.findIndex(function (line) {
			return specLineId(line) === id;
		});
		if (checked && idx < 0) {
			submittalCreateLines.push({
				spec_section_id: spec.id,
				spec_section_code: spec.code,
				description: spec.title,
				manufacturer: null,
				model: null,
				save_to_catalog: true,
			});
			var titleEl = document.getElementById("usis-submittal-c-title");
			if (titleEl && !titleEl.value.trim()) {
				titleEl.value = spec.title || spec.code || "";
			}
			var specEl = document.getElementById("usis-submittal-c-spec");
			if (specEl && !specEl.value.trim()) {
				specEl.value = spec.code || "";
			}
		} else if (!checked && idx >= 0) {
			submittalCreateLines.splice(idx, 1);
		}
		renderSubmittalCreateLines();
	}

	function renderSubmittalSpecPicker() {
		var list = document.getElementById("usis-submittal-c-spec-list");
		var empty = document.getElementById("usis-submittal-c-spec-empty");
		var qEl = document.getElementById("usis-submittal-c-spec-q");
		if (!list) return;
		var q = qEl && qEl.value ? qEl.value.trim().toLowerCase() : "";
		var items = activeSpecOptions().filter(function (s) {
			if (!q) return true;
			var hay = ((s.code || "") + " " + (s.title || "")).toLowerCase();
			return hay.indexOf(q) !== -1;
		});
		if (empty) empty.classList.toggle("d-none", activeSpecOptions().length > 0);
		list.innerHTML = "";
		if (!activeSpecOptions().length) {
			return;
		}
		if (!items.length) {
			list.innerHTML = '<p class="text-muted small mb-0 py-1">No sections match that search.</p>';
			return;
		}
		items.forEach(function (spec) {
			var id = String(spec.id);
			var checked = submittalCreateLines.some(function (line) {
				return specLineId(line) === id;
			});
			var boxId = "usis-submittal-c-spec-cb-" + id;
			var row = document.createElement("div");
			row.className = "form-check d-flex align-items-start gap-2 py-1 mb-0";
			row.innerHTML =
				'<input class="form-check-input mt-1" type="checkbox" id="' +
				esc(boxId) +
				'" data-spec-id="' +
				esc(id) +
				'"' +
				(checked ? " checked" : "") +
				'><label class="form-check-label small" for="' +
				esc(boxId) +
				'">' +
				esc(spec.code || "—") +
				(spec.title ? " — " + esc(spec.title) : "") +
				"</label>";
			var box = row.querySelector("input");
			row.addEventListener("pointerdown", function (e) {
				e.stopPropagation();
			});
			box.addEventListener("change", function () {
				setSpecChecked(spec, box.checked);
			});
			list.appendChild(row);
		});
	}

	function loadSubmittalSpecOptions(projectId) {
		var empty = document.getElementById("usis-submittal-c-spec-empty");
		var list = document.getElementById("usis-submittal-c-spec-list");
		if (list) list.innerHTML = '<p class="text-muted small mb-0 py-1">Loading spec sections…</p>';
		if (empty) empty.classList.add("d-none");
		return fetchJson("/api/v1/projects/" + encodeURIComponent(projectId) + "/rfi-lookups/spec_sections")
			.then(function (data) {
				submittalSpecOptions = data.items || [];
				renderSubmittalSpecPicker();
			})
			.catch(function (e) {
				submittalSpecOptions = [];
				if (list) {
					list.innerHTML =
						'<p class="text-danger small mb-0 py-1">' +
						esc(e.message || "Could not load spec sections.") +
						"</p>";
				}
			});
	}

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

	function isoFromDateInput(el) {
		if (!el || !el.value) return null;
		var v = String(el.value).trim();
		if (!/^\d{4}-\d{2}-\d{2}$/.test(v)) return null;
		return v + "T00:00:00+00:00";
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
							"construction/drawing-viewer.html?project_id=" +
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

		var specSearch = document.getElementById("usis-submittal-c-spec-q");
		if (specSearch) {
			specSearch.addEventListener("input", renderSubmittalSpecPicker);
		}
		var subModal = document.getElementById("usis-modal-submittal-create");
		if (subModal) {
			subModal.addEventListener("show.bs.modal", function () {
				submittalCreateLines = [];
				submittalSpecOptions = [];
				var qEl = document.getElementById("usis-submittal-c-spec-q");
				if (qEl) qEl.value = "";
				renderSubmittalCreateLines();
				var pid = activeProjectId || projectIdFromQuery();
				if (pid) loadSubmittalSpecOptions(pid);
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
					line_items: submittalCreateLines.slice(),
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
