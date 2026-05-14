/**
 * Procore-parity RFI Log page.
 *
 * Renders:
 *  - Project picker (from /api/v1/projects)
 *  - Saved views, status filter, search, recycle-bin toggle
 *  - Sortable, customizable column set with drag-to-reorder + show/hide
 *  - Bulk-action toolbar (close / delete / restore / patch)
 *  - CSV + JSON export
 *  - Inline editing for key fields (Due Date, Manager, Private)
 */
(function () {
	"use strict";

	var U = window.USIS_RFI;
	var prefsStore = U.localStore("usis_rfi_log_prefs");

	var DEFAULT_COLUMNS = [
		{ key: "display_number", label: "#", visible: true, sortable: true, sortKey: "number_asc:number_desc" },
		{ key: "subject", label: "Subject", visible: true, sortable: true, sortKey: "subject_asc:subject_asc" },
		{ key: "status", label: "Status", visible: true, sortable: false },
		{ key: "ball_in_court", label: "Ball in Court", visible: true, sortable: false },
		{ key: "assignees", label: "Assignees", visible: true, sortable: false },
		{ key: "rfi_manager", label: "RFI Manager", visible: true, sortable: false },
		{ key: "received_from", label: "Received From", visible: false, sortable: false },
		{ key: "responsible_contractor", label: "Responsible Contractor", visible: false, sortable: false },
		{ key: "date_initiated_at", label: "Date Initiated", visible: false, sortable: false },
		{ key: "due_at", label: "Due Date", visible: true, sortable: true, sortKey: "due_asc:due_desc" },
		{ key: "closed_at", label: "Closed Date", visible: false, sortable: false },
		{ key: "schedule_impact_choice", label: "Schedule Impact", visible: false, sortable: false },
		{ key: "cost_impact_choice", label: "Cost Impact", visible: false, sortable: false },
		{ key: "cost_impact", label: "Cost $", visible: false, sortable: false },
		{ key: "cost_code", label: "Cost Code", visible: false, sortable: false },
		{ key: "location", label: "Location", visible: false, sortable: false },
		{ key: "spec_section", label: "Spec Section", visible: false, sortable: false },
		{ key: "is_private", label: "Private", visible: false, sortable: false },
		{ key: "reference_text", label: "Reference", visible: false, sortable: false },
	];

	var state = {
		projectId: null,
		columns: DEFAULT_COLUMNS.map(function (c) { return Object.assign({}, c); }),
		rowHeight: "default",
		filters: { status: "", q: "", in_recycle_bin: false },
		sort: "number_asc",
		page: { limit: 100, offset: 0, total: 0 },
		items: [],
		selection: new Set(),
		lookups: {},
	};

	function loadPrefs() {
		var p = prefsStore.get();
		if (p && Array.isArray(p.columns)) {
			// Merge stored visibility/order with current defaults.
			var byKey = {};
			DEFAULT_COLUMNS.forEach(function (c) { byKey[c.key] = c; });
			var merged = [];
			var seen = {};
			p.columns.forEach(function (c) {
				if (byKey[c.key]) {
					merged.push(Object.assign({}, byKey[c.key], { visible: c.visible !== false }));
					seen[c.key] = true;
				}
			});
			DEFAULT_COLUMNS.forEach(function (c) {
				if (!seen[c.key]) merged.push(Object.assign({}, c));
			});
			state.columns = merged;
		}
		if (p && p.rowHeight) state.rowHeight = p.rowHeight;
		if (p && p.projectId) state.projectId = p.projectId;
	}

	function savePrefs() {
		prefsStore.set({
			columns: state.columns.map(function (c) { return { key: c.key, visible: c.visible }; }),
			rowHeight: state.rowHeight,
			projectId: state.projectId,
		});
		// Best-effort server sync
		U.putColumnPrefs("rfi_log", {
			columns: state.columns.map(function (c) { return { key: c.key, visible: c.visible }; }),
			row_height: state.rowHeight,
		}).catch(function () {});
	}

	function renderHeader() {
		var thr = document.getElementById("usis-rfi-thead-row");
		if (!thr) return;
		// Clear except the first checkbox column
		while (thr.children.length > 1) thr.removeChild(thr.lastChild);

		state.columns.forEach(function (c) {
			if (!c.visible) return;
			var th = document.createElement("th");
			th.scope = "col";
			th.dataset.colKey = c.key;
			th.style.cursor = c.sortable ? "pointer" : "";
			if (c.sortable && c.sortKey) {
				var parts = c.sortKey.split(":");
				var cur = state.sort === parts[0] ? parts[1] : parts[0];
				th.innerHTML = U.esc(c.label) + ' <span class="text-muted small">' +
					(state.sort === parts[0] ? "↑" : state.sort === parts[1] ? "↓" : "") + "</span>";
				th.addEventListener("click", function () {
					state.sort = state.sort === parts[0] ? parts[1] : parts[0];
					reload();
				});
			} else {
				th.textContent = c.label;
			}
			thr.appendChild(th);
		});
		// Actions column
		var act = document.createElement("th");
		act.className = "text-end";
		act.textContent = "";
		thr.appendChild(act);
	}

	function statusPill(s) {
		var cls = "usis-rfi-status usis-rfi-status-" + (s || "draft");
		return '<span class="' + cls + '">' + U.esc(U.statusLabel(s)) + "</span>";
	}

	function userLabel(u) {
		if (!u) return "—";
		return U.esc(u.name || u.email || "");
	}

	function userList(arr) {
		if (!arr || !arr.length) return "—";
		return arr.map(function (a) {
			var u = a.user || a;
			var dot = a.ball_in_court ? '<span title="Ball in Court">●</span> ' : "";
			return dot + U.esc(u.name || u.email || "");
		}).join(", ");
	}

	function cellValue(row, key) {
		switch (key) {
			case "display_number":
				return '<a href="construction/rfi-detail.html?id=' + U.escAttr(row.id) + '">' + U.esc(row.display_number) + "</a>";
			case "subject":
				return '<a href="construction/rfi-detail.html?id=' + U.escAttr(row.id) + '" class="text-decoration-none text-black fw-semibold">' + U.esc(row.subject) + "</a>";
			case "status":
				return statusPill(row.status);
			case "ball_in_court":
				return U.esc(row.ball_in_court || "—");
			case "assignees":
				return userList(row.assignees || []);
			case "rfi_manager":
				return userLabel(row.rfi_manager);
			case "received_from":
				return userLabel(row.received_from);
			case "responsible_contractor":
				return row.responsible_contractor ? U.esc(row.responsible_contractor.name) : "—";
			case "date_initiated_at":
				return row.date_initiated_at ? U.esc(U.fmtDate(row.date_initiated_at)) : "—";
			case "due_at":
				if (!row.due_at) return "—";
				var d = new Date(row.due_at);
				var overdue = row.status === "open" && d < new Date();
				return '<span ' + (overdue ? 'class="usis-rfi-overdue"' : "") + '>' + U.esc(U.fmtDate(row.due_at)) + "</span>";
			case "closed_at":
				return row.closed_at ? U.esc(U.fmtDate(row.closed_at)) : "—";
			case "schedule_impact_choice":
				return U.esc(U.impactLabel(row.schedule_impact_choice));
			case "cost_impact_choice":
				return U.esc(U.impactLabel(row.cost_impact_choice));
			case "cost_impact":
				return row.cost_impact != null ? U.esc(U.fmtMoney(row.cost_impact)) : "—";
			case "cost_code":
				return U.esc((state.lookups.cost_codes || {})[row.cost_code_id] || "—");
			case "location":
				return U.esc((state.lookups.locations || {})[row.location_id] || "—");
			case "spec_section":
				return U.esc((state.lookups.spec_sections || {})[row.spec_section_id] || "—");
			case "is_private":
				return row.is_private ? "Yes" : "No";
			case "reference_text":
				return U.esc(row.reference_text || "—");
			default:
				return "—";
		}
	}

	function rowActions(row) {
		var opts = [];
		opts.push('<a class="dropdown-item" href="construction/rfi-detail.html?id=' + U.escAttr(row.id) + '">Open</a>');
		opts.push('<a class="dropdown-item" href="javascript:void(0);" data-act="inline-edit-due" data-id="' + U.escAttr(row.id) + '">Inline edit Due Date</a>');
		if (row.status === "open" || row.status === "draft") {
			opts.push('<a class="dropdown-item" href="javascript:void(0);" data-act="close" data-id="' + U.escAttr(row.id) + '">Close</a>');
		}
		if (row.status === "closed" || row.status === "closed_draft") {
			opts.push('<a class="dropdown-item" href="javascript:void(0);" data-act="reopen" data-id="' + U.escAttr(row.id) + '">Reopen</a>');
		}
		if (!row.is_deleted) {
			opts.push('<a class="dropdown-item text-danger" href="javascript:void(0);" data-act="delete" data-id="' + U.escAttr(row.id) + '">Recycle</a>');
		} else {
			opts.push('<a class="dropdown-item text-primary" href="javascript:void(0);" data-act="restore" data-id="' + U.escAttr(row.id) + '">Restore</a>');
		}
		return (
			'<div class="dropdown custom-dropdown mb-0 tbl-orders-style">' +
			'<div class="btn btn-square btn-sm rounded" data-bs-toggle="dropdown"><i class="fa-solid fa-ellipsis-vertical"></i></div>' +
			'<div class="dropdown-menu dropdown-menu-end">' + opts.join("") + "</div></div>"
		);
	}

	function renderBody() {
		var tbody = document.getElementById("usis-rfi-tbody");
		if (!tbody) return;
		var visible = state.columns.filter(function (c) { return c.visible; });
		var colSpan = visible.length + 2; // checkbox + actions
		if (!state.items.length) {
			tbody.innerHTML = '<tr><td colspan="' + colSpan + '" class="text-muted text-center py-4">No RFIs match the current filters.</td></tr>';
			updateCounter();
			return;
		}
		var rowsHtml = state.items.map(function (row) {
			var checked = state.selection.has(row.id) ? " checked" : "";
			var cells = visible.map(function (c) {
				return "<td>" + cellValue(row, c.key) + "</td>";
			}).join("");
			return '<tr data-id="' + U.escAttr(row.id) + '">' +
				'<td><input type="checkbox" class="usis-rfi-row-cb"' + checked + '></td>' +
				cells +
				'<td class="text-end">' + rowActions(row) + "</td>" +
			"</tr>";
		}).join("");
		tbody.innerHTML = rowsHtml;
		updateCounter();
		wireRowEvents();
		applyRowHeight();
	}

	function applyRowHeight() {
		var tbl = document.getElementById("usis-rfi-table");
		if (!tbl) return;
		tbl.classList.remove("table-sm");
		if (state.rowHeight === "compact") tbl.classList.add("table-sm");
	}

	function updateCounter() {
		var el = document.getElementById("usis-rfi-counter");
		if (!el) return;
		var total = state.page.total || state.items.length;
		var from = state.items.length ? state.page.offset + 1 : 0;
		var to = state.page.offset + state.items.length;
		el.textContent = total ? from + "–" + to + " of " + total : "0 of 0";
	}

	function wireRowEvents() {
		var tbody = document.getElementById("usis-rfi-tbody");
		if (!tbody) return;
		Array.prototype.forEach.call(tbody.querySelectorAll(".usis-rfi-row-cb"), function (cb) {
			cb.addEventListener("change", function () {
				var tr = cb.closest("tr");
				var id = tr && tr.dataset ? tr.dataset.id : "";
				if (!id) return;
				if (cb.checked) state.selection.add(id);
				else state.selection.delete(id);
				updateBulkBar();
			});
		});
		Array.prototype.forEach.call(tbody.querySelectorAll("[data-act]"), function (a) {
			a.addEventListener("click", function () {
				var id = a.dataset.id, act = a.dataset.act;
				if (!id || !act) return;
				handleRowAction(id, act);
			});
		});
	}

	function handleRowAction(id, act) {
		var path = "/api/v1/rfis/" + encodeURIComponent(id);
		var promise = null;
		if (act === "close") promise = U.fetchJson(path + "/close", { method: "POST" });
		else if (act === "reopen") promise = U.fetchJson(path + "/reopen", { method: "POST" });
		else if (act === "delete") promise = U.fetchJson(path, { method: "DELETE" });
		else if (act === "restore") promise = U.fetchJson(path + "/restore", { method: "POST" });
		else if (act === "inline-edit-due") {
			var current = (state.items.find(function (r) { return r.id === id; }) || {}).due_at;
			var next = window.prompt("New due date (YYYY-MM-DD):", current ? current.slice(0, 10) : "");
			if (next === null) return;
			promise = U.patchRfi(id, { due_at: next || null });
		}
		if (!promise) return;
		promise.then(reload).catch(function (err) { alert(err.message || String(err)); });
	}

	function updateBulkBar() {
		var bar = document.getElementById("usis-rfi-bulk-bar");
		var cnt = document.getElementById("usis-rfi-bulk-count");
		if (!bar) return;
		if (state.selection.size > 0) {
			bar.classList.remove("d-none");
			if (cnt) cnt.textContent = state.selection.size + " selected";
		} else {
			bar.classList.add("d-none");
		}
	}

	function bulkDispatch(op, payload) {
		if (state.selection.size === 0) return Promise.resolve();
		return U.fetchJson("/api/v1/rfis/bulk", {
			method: "POST",
			body: { rfi_ids: Array.from(state.selection), op: op, payload: payload || {} },
		}).then(function () {
			state.selection.clear();
			updateBulkBar();
			reload();
		}).catch(function (err) { alert(err.message || String(err)); });
	}

	function populateProjectSelect() {
		var sel = document.getElementById("usis-rfi-project");
		if (!sel) return Promise.resolve();
		return U.loadProjects().then(function (rows) {
			sel.innerHTML = "";
			rows.forEach(function (p) {
				var label = (p.number ? p.number + " · " : "") + (p.name || "(no name)");
				var opt = document.createElement("option");
				opt.value = p.id;
				opt.textContent = label;
				sel.appendChild(opt);
			});
			var hint = U.queryParam("project_id") || state.projectId;
			if (hint && Array.prototype.some.call(sel.options, function (o) { return o.value === hint; })) {
				sel.value = hint;
				state.projectId = hint;
			} else if (sel.options.length) {
				sel.selectedIndex = 0;
				state.projectId = sel.value;
			}
			updateCreateLink();
		});
	}

	function updateCreateLink() {
		var a = document.getElementById("usis-rfi-create-link");
		if (!a) return;
		var href = "construction/rfi-create.html";
		if (state.projectId) href += "?project_id=" + encodeURIComponent(state.projectId);
		a.setAttribute("href", href);
	}

	function loadLookupsForProject(projectId) {
		state.lookups = { locations: {}, spec_sections: {}, cost_codes: {} };
		var kinds = [
			["locations", "name"],
			["spec_sections", "code"],
			["cost_codes", "code"],
		];
		return Promise.all(kinds.map(function (k) {
			return U.loadLookup(projectId, k[0]).then(function (rows) {
				var map = {};
				rows.forEach(function (r) {
					map[r.id] = r[k[1]] || r.code || r.name || "";
				});
				state.lookups[k[0]] = map;
			}).catch(function () {});
		}));
	}

	function reload() {
		renderHeader();
		var params = {
			status: state.filters.status || undefined,
			q: state.filters.q || undefined,
			in_recycle_bin: state.filters.in_recycle_bin ? "1" : undefined,
			sort: state.sort,
			limit: state.page.limit,
			offset: state.page.offset,
		};
		var tbody = document.getElementById("usis-rfi-tbody");
		if (tbody) tbody.innerHTML = '<tr><td colspan="20" class="text-muted text-center py-3">Loading RFIs…</td></tr>';

		var pid = state.projectId;
		if (!pid) {
			if (tbody) tbody.innerHTML = '<tr><td colspan="20" class="text-muted text-center py-4">Select a project to see its RFIs.</td></tr>';
			return Promise.resolve();
		}
		return Promise.all([
			U.listRfis(pid, params),
			loadLookupsForProject(pid),
		]).then(function (results) {
			var data = results[0] || {};
			state.items = data.items || [];
			state.page.total = data.total || 0;
			renderBody();
		}).catch(function (err) {
			if (tbody) tbody.innerHTML = '<tr><td colspan="20" class="text-danger text-center py-3">' + U.esc(err.message || err) + "</td></tr>";
		});
	}

	function wireFilters() {
		var qInput = document.getElementById("usis-rfi-search");
		var stSel = document.getElementById("usis-rfi-status");
		var rbSel = document.getElementById("usis-rfi-recycle");
		var projSel = document.getElementById("usis-rfi-project");

		if (qInput) qInput.addEventListener("input", U.debounce(function () {
			state.filters.q = qInput.value || "";
			state.page.offset = 0;
			reload();
		}, 250));
		if (stSel) stSel.addEventListener("change", function () {
			state.filters.status = stSel.value || "";
			state.page.offset = 0;
			reload();
		});
		if (rbSel) rbSel.addEventListener("change", function () {
			state.filters.in_recycle_bin = rbSel.value === "1";
			state.page.offset = 0;
			reload();
		});
		if (projSel) projSel.addEventListener("change", function () {
			state.projectId = projSel.value;
			state.page.offset = 0;
			state.selection.clear();
			updateBulkBar();
			updateCreateLink();
			savePrefs();
			reload();
		});
	}

	function wirePager() {
		var prev = document.getElementById("usis-rfi-prev");
		var next = document.getElementById("usis-rfi-next");
		if (prev) prev.addEventListener("click", function () {
			if (state.page.offset <= 0) return;
			state.page.offset = Math.max(0, state.page.offset - state.page.limit);
			reload();
		});
		if (next) next.addEventListener("click", function () {
			if (state.page.offset + state.page.limit >= state.page.total) return;
			state.page.offset += state.page.limit;
			reload();
		});
	}

	function wireCheckAll() {
		var all = document.getElementById("usis-rfi-check-all");
		if (!all) return;
		all.addEventListener("change", function () {
			if (all.checked) {
				state.items.forEach(function (r) { state.selection.add(r.id); });
			} else {
				state.selection.clear();
			}
			renderBody();
			updateBulkBar();
		});
	}

	function wireBulk() {
		var bar = document.getElementById("usis-rfi-bulk-bar");
		if (!bar) return;
		Array.prototype.forEach.call(bar.querySelectorAll("[data-bulk]"), function (btn) {
			btn.addEventListener("click", function () {
				var op = btn.dataset.bulk;
				if (op === "patch") {
					var modal = document.getElementById("usis-rfi-bulkedit-modal");
					if (modal && window.bootstrap) bootstrap.Modal.getOrCreateInstance(modal).show();
					return;
				}
				if (!window.confirm("Apply '" + op + "' to " + state.selection.size + " RFI(s)?")) return;
				bulkDispatch(op);
			});
		});
		var clr = document.getElementById("usis-rfi-bulk-clear");
		if (clr) clr.addEventListener("click", function () { state.selection.clear(); renderBody(); updateBulkBar(); });
		var apply = document.getElementById("usis-rfi-bulkedit-apply");
		if (apply) apply.addEventListener("click", function () {
			var payload = {};
			var due = document.getElementById("usis-rfi-bulkedit-due").value;
			var mgr = document.getElementById("usis-rfi-bulkedit-manager").value.trim();
			var priv = document.getElementById("usis-rfi-bulkedit-private").value;
			if (due) payload.due_at = due;
			if (mgr) payload.rfi_manager_user_id = mgr;
			if (priv) payload.is_private = priv === "true";
			bulkDispatch("patch", payload).then(function () {
				var modal = document.getElementById("usis-rfi-bulkedit-modal");
				if (modal && window.bootstrap) bootstrap.Modal.getInstance(modal).hide();
			});
		});
	}

	function wireExport() {
		var csv = document.getElementById("usis-rfi-export-csv");
		var pdf = document.getElementById("usis-rfi-export-pdf");
		if (csv) csv.addEventListener("click", function () {
			if (!state.projectId) return;
			var url = U.buildUrl(
				"/api/v1/projects/" + encodeURIComponent(state.projectId) + "/rfis/export",
				{
					format: "csv",
					status: state.filters.status || undefined,
					q: state.filters.q || undefined,
					in_recycle_bin: state.filters.in_recycle_bin ? "1" : undefined,
					sort: state.sort,
				}
			);
			window.location.href = url;
		});
		if (pdf) pdf.addEventListener("click", function () {
			alert("PDF export is rendered client-side from the current rows. Use your browser's Print → Save as PDF for now.");
			window.print();
		});
	}

	function renderColumnList() {
		var list = document.getElementById("usis-rfi-col-list");
		if (!list) return;
		list.innerHTML = state.columns.map(function (c, i) {
			return (
				'<div class="usis-col-row" draggable="true" data-ix="' + i + '">' +
				'<i class="fa fa-grip-vertical text-muted"></i>' +
				'<input type="checkbox" class="form-check-input" ' + (c.visible ? "checked" : "") + ' data-vis="' + i + '">' +
				'<span>' + U.esc(c.label) + '</span>' +
				'</div>'
			);
		}).join("");

		// Drag-and-drop reorder
		var dragIx = null;
		Array.prototype.forEach.call(list.querySelectorAll(".usis-col-row"), function (row) {
			row.addEventListener("dragstart", function () { dragIx = parseInt(row.dataset.ix, 10); });
			row.addEventListener("dragover", function (e) { e.preventDefault(); });
			row.addEventListener("drop", function (e) {
				e.preventDefault();
				var targetIx = parseInt(row.dataset.ix, 10);
				if (dragIx == null || dragIx === targetIx) return;
				var moved = state.columns.splice(dragIx, 1)[0];
				state.columns.splice(targetIx, 0, moved);
				dragIx = null;
				renderColumnList();
			});
		});
		Array.prototype.forEach.call(list.querySelectorAll('[data-vis]'), function (cb) {
			cb.addEventListener("change", function () {
				var ix = parseInt(cb.dataset.vis, 10);
				if (state.columns[ix]) state.columns[ix].visible = cb.checked;
			});
		});
	}

	function wireColumns() {
		var btn = document.getElementById("usis-rfi-customize");
		var apply = document.getElementById("usis-rfi-cols-apply");
		var reset = document.getElementById("usis-rfi-cols-reset");
		var rh = document.getElementById("usis-rfi-row-height");
		var modal = document.getElementById("usis-rfi-cols-modal");
		if (btn) btn.addEventListener("click", function () {
			renderColumnList();
			if (rh) rh.value = state.rowHeight;
			if (modal && window.bootstrap) bootstrap.Modal.getOrCreateInstance(modal).show();
		});
		if (apply) apply.addEventListener("click", function () {
			if (rh) state.rowHeight = rh.value || "default";
			savePrefs();
			renderHeader();
			renderBody();
			if (modal && window.bootstrap) bootstrap.Modal.getInstance(modal).hide();
		});
		if (reset) reset.addEventListener("click", function () {
			state.columns = DEFAULT_COLUMNS.map(function (c) { return Object.assign({}, c); });
			state.rowHeight = "default";
			renderColumnList();
			if (rh) rh.value = state.rowHeight;
		});
	}

	function reloadSavedViews() {
		var sel = document.getElementById("usis-rfi-saved-view");
		if (!sel) return Promise.resolve();
		return U.listSavedViews(state.projectId).then(function (rows) {
			sel.innerHTML = '<option value="">Default (all)</option>';
			rows.forEach(function (v) {
				var opt = document.createElement("option");
				opt.value = v.id;
				opt.textContent = v.name + (v.scope === "project" ? " (project)" : v.scope === "company" ? " (company)" : "");
				sel.appendChild(opt);
			});
		});
	}

	function wireSavedViews() {
		var sel = document.getElementById("usis-rfi-saved-view");
		var btn = document.getElementById("usis-rfi-save-view");
		var apply = document.getElementById("usis-rfi-saveview-apply");
		var modal = document.getElementById("usis-rfi-saveview-modal");
		if (sel) sel.addEventListener("change", function () {
			if (!sel.value) return;
			U.fetchJson("/api/v1/rfi-saved-views?project_id=" + encodeURIComponent(state.projectId || "")).then(function (data) {
				var match = (data.items || []).find(function (v) { return v.id === sel.value; });
				if (!match) return;
				var f = match.filters || {};
				if (f.status) document.getElementById("usis-rfi-status").value = f.status;
				if (f.q != null) document.getElementById("usis-rfi-search").value = f.q;
				if (f.in_recycle_bin) document.getElementById("usis-rfi-recycle").value = "1";
				state.filters = {
					status: f.status || "",
					q: f.q || "",
					in_recycle_bin: !!f.in_recycle_bin,
				};
				if (match.columns && Array.isArray(match.columns)) {
					match.columns.forEach(function (vc) {
						var existing = state.columns.find(function (c) { return c.key === vc.key; });
						if (existing) existing.visible = vc.visible !== false;
					});
					renderHeader();
				}
				reload();
			});
		});
		if (btn) btn.addEventListener("click", function () {
			if (modal && window.bootstrap) bootstrap.Modal.getOrCreateInstance(modal).show();
		});
		if (apply) apply.addEventListener("click", function () {
			var name = document.getElementById("usis-rfi-saveview-name").value.trim();
			var scope = document.getElementById("usis-rfi-saveview-scope").value;
			var def = document.getElementById("usis-rfi-saveview-default").checked;
			if (!name) { alert("Name is required"); return; }
			U.createSavedView({
				name: name,
				scope: scope,
				project_id: scope !== "company" ? state.projectId : null,
				filters: state.filters,
				sort: state.sort,
				columns: state.columns.map(function (c) { return { key: c.key, visible: c.visible }; }),
				is_default: def,
			}).then(function () {
				reloadSavedViews();
				if (modal && window.bootstrap) bootstrap.Modal.getInstance(modal).hide();
			}).catch(function (err) { alert(err.message || String(err)); });
		});
	}

	function init() {
		loadPrefs();
		renderHeader();
		populateProjectSelect()
			.then(reloadSavedViews)
			.then(reload);
		wireFilters();
		wirePager();
		wireCheckAll();
		wireBulk();
		wireExport();
		wireColumns();
		wireSavedViews();
	}

	if (document.readyState === "loading") {
		document.addEventListener("DOMContentLoaded", init);
	} else {
		init();
	}
})();
