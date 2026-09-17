/**
 * Construction — Material catalog (material_pricing via GET /api/v1/material-prices).
 */
(function () {
	"use strict";

	var catalogTable = null;
	var searchTimer = null;
	var BULK_CHUNK = 2000;
	var headerFilterFillers = [];
	var facetLists = {
		manufacturers: [],
		categories: [],
		csi_sections: [],
		sizes: [],
		mounting_types: [],
		units: [],
		labor: [],
	};
	var state = {
		q: "",
		manufacturer: "",
		item: "",
		csi: "",
		category: "",
		description: "",
		mounting: "",
		cost: "",
		labor: "",
		uom: "",
		size: "",
		offset: 0,
		limit: 100,
		total: 0,
	};

	function apiBase() {
		if (typeof window.USIS_API_BASE === "string" && window.USIS_API_BASE.trim()) {
			var s = window.USIS_API_BASE.trim().replace(/\/$/, "");
			try {
				if (s && new URL(s).origin !== window.location.origin) return s;
			} catch (e) {
				if (s) return s;
			}
		}
		var loc = window.location;
		if (loc.protocol === "file:") return "http://127.0.0.1:5000";
		var host = loc.hostname || "";
		var proto = loc.protocol || "http:";
		var port = String(loc.port || "");
		if (["3000", "3001", "5173", "8080"].indexOf(port) >= 0) return proto + "//" + host + ":5000";
		if ((host === "localhost" || host === "127.0.0.1") && port && port !== "5000") return proto + "//" + host + ":5000";
		return "";
	}

	function notifyErr(msg) {
		if (window.USISNotify) window.USISNotify.error(String(msg));
		else alert(String(msg));
	}

	function notifyOk(msg) {
		if (window.USISNotify && window.USISNotify.success) window.USISNotify.success(String(msg));
	}

	function jsonFetch(url, opts) {
		var headers = Object.assign({ Accept: "application/json" }, (opts && opts.headers) || {});
		if (opts && opts.body && !headers["Content-Type"]) headers["Content-Type"] = "application/json";
		return fetch(url, Object.assign({ credentials: "include" }, opts || {}, { headers: headers })).then(function (res) {
			return res.json().then(function (j) {
				if (!res.ok) throw new Error(j.error || res.status);
				return j;
			});
		});
	}

	function fmtMoney(cell) {
		var v = cell.getValue();
		if (v == null || v === "") return "—";
		var n = Number(v);
		return isNaN(n) ? String(v) : "$" + n.toFixed(2);
	}

	function fmtHours(cell) {
		var v = cell.getValue();
		if (v == null || v === "") return "—";
		var n = Number(v);
		if (isNaN(n)) return String(v);
		var label = n === 1 ? " hr" : " hrs";
		return n.toLocaleString(undefined, { maximumFractionDigits: 4 }) + label;
	}

	function fmtCsi(cell) {
		var row = cell.getRow().getData() || {};
		return row.csi_display || row.csi_spec_section || "—";
	}

	function fmtSize(cell) {
		var row = cell.getRow().getData() || {};
		return row.size_display || "—";
	}

	var detailItem = null;
	var detailEditing = false;

	function escHtml(s) {
		return String(s == null ? "" : s)
			.replace(/&/g, "&amp;")
			.replace(/</g, "&lt;")
			.replace(/>/g, "&gt;")
			.replace(/"/g, "&quot;");
	}

	function dash(v) {
		if (v == null || v === "") return "—";
		return String(v);
	}

	function moneyText(v) {
		if (v == null || v === "") return "—";
		var n = Number(v);
		return isNaN(n) ? String(v) : "$" + n.toFixed(2);
	}

	function hoursText(v) {
		if (v == null || v === "") return "—";
		var n = Number(v);
		if (isNaN(n)) return String(v);
		return n.toLocaleString(undefined, { maximumFractionDigits: 4 }) + (n === 1 ? " hr" : " hrs");
	}

	function detailModal() {
		var el = document.getElementById("usis-mat-detail-modal");
		if (!el || typeof bootstrap === "undefined" || !bootstrap.Modal) return null;
		return bootstrap.Modal.getOrCreateInstance(el);
	}

	function setDetailMode(editing) {
		detailEditing = !!editing;
		var view = document.getElementById("usis-mat-detail-view");
		var form = document.getElementById("usis-mat-detail-form");
		var editBtn = document.getElementById("usis-mat-detail-edit");
		var saveBtn = document.getElementById("usis-mat-detail-save");
		var cancelBtn = document.getElementById("usis-mat-detail-cancel");
		var closeBtn = document.getElementById("usis-mat-detail-close");
		if (view) view.classList.toggle("d-none", detailEditing);
		if (form) form.classList.toggle("d-none", !detailEditing);
		if (editBtn) editBtn.classList.toggle("d-none", detailEditing);
		if (saveBtn) saveBtn.classList.toggle("d-none", !detailEditing);
		if (cancelBtn) cancelBtn.classList.toggle("d-none", !detailEditing);
		if (closeBtn) closeBtn.classList.toggle("d-none", detailEditing);
	}

	function inputVal(id) {
		var el = document.getElementById(id);
		return el ? el.value : "";
	}

	function fillDetailForm(item) {
		var map = {
			"usis-mat-edit-manufacturer": item.manufacturer,
			"usis-mat-edit-item": item.item,
			"usis-mat-edit-category": item.category,
			"usis-mat-edit-csi": item.csi_display || item.csi_spec_section,
			"usis-mat-edit-description": item.description,
			"usis-mat-edit-mounting": item.mounting_type,
			"usis-mat-edit-width": item.size_width_in,
			"usis-mat-edit-height": item.size_height_in,
			"usis-mat-edit-cost": item.cost,
			"usis-mat-edit-labor": item.labor_per,
			"usis-mat-edit-uom": item.unit_of_measure,
			"usis-mat-edit-currency": item.currency,
		};
		Object.keys(map).forEach(function (id) {
			var el = document.getElementById(id);
			if (el) el.value = map[id] == null ? "" : String(map[id]);
		});
	}

	function renderDetailView(item) {
		var view = document.getElementById("usis-mat-detail-view");
		var title = document.getElementById("usis-mat-detail-title");
		if (title) title.textContent = item.item ? String(item.item) : "Material";
		if (!view) return;
		var division = item.csi_display || item.csi_spec_section || "—";
		if (item.csi_title) division = division + " — " + item.csi_title;
		var rows = [
			["Item", dash(item.item)],
			["Manufacturer", dash(item.manufacturer)],
			["Category", dash(item.category)],
			["Division", division],
			["CSI section", dash(item.csi_spec_section)],
			["Size", dash(item.size_display)],
			["Width (in)", dash(item.size_width_in)],
			["Height (in)", dash(item.size_height_in)],
			["Sheet area (sf)", dash(item.sheet_area_sf)],
			["Description", dash(item.description)],
			["Mounting", dash(item.mounting_type)],
			["Cost", moneyText(item.cost)],
			["Labor", hoursText(item.labor_per)],
			["UOM", dash(item.unit_of_measure)],
			["Currency", dash(item.currency)],
			["Updated", dash(item.updated_at)],
			["Created", dash(item.created_at)],
		];
		view.innerHTML =
			'<dl class="row mb-0">' +
			rows
				.map(function (pair) {
					return (
						'<dt class="col-sm-4 col-lg-3 text-muted small">' +
						escHtml(pair[0]) +
						'</dt><dd class="col-sm-8 col-lg-9">' +
						escHtml(pair[1]) +
						"</dd>"
					);
				})
				.join("") +
			"</dl>";
		fillDetailForm(item);
	}

	function openDetail(row) {
		if (!row || !row.id) return;
		detailItem = row;
		setDetailMode(false);
		renderDetailView(row);
		var modal = detailModal();
		if (modal) modal.show();
		jsonFetch(apiBase() + "/api/v1/material-prices/" + encodeURIComponent(row.id))
			.then(function (d) {
				if (!d || !d.item || !detailItem || d.item.id !== String(detailItem.id)) return;
				detailItem = d.item;
				if (!detailEditing) renderDetailView(detailItem);
				else fillDetailForm(detailItem);
			})
			.catch(function () {});
	}

	function collectDetailEdits() {
		return {
			manufacturer: inputVal("usis-mat-edit-manufacturer"),
			item: inputVal("usis-mat-edit-item"),
			category: inputVal("usis-mat-edit-category"),
			csi_spec_section: inputVal("usis-mat-edit-csi"),
			description: inputVal("usis-mat-edit-description"),
			mounting_type: inputVal("usis-mat-edit-mounting"),
			size_width_in: inputVal("usis-mat-edit-width"),
			size_height_in: inputVal("usis-mat-edit-height"),
			cost: inputVal("usis-mat-edit-cost"),
			labor_per: inputVal("usis-mat-edit-labor"),
			unit_of_measure: inputVal("usis-mat-edit-uom"),
			currency: inputVal("usis-mat-edit-currency"),
		};
	}

	function saveDetail() {
		if (!detailItem || !detailItem.id) return;
		var saveBtn = document.getElementById("usis-mat-detail-save");
		if (saveBtn) saveBtn.disabled = true;
		jsonFetch(apiBase() + "/api/v1/material-prices/" + encodeURIComponent(detailItem.id), {
			method: "PATCH",
			body: JSON.stringify(collectDetailEdits()),
		})
			.then(function (d) {
				detailItem = d.item || detailItem;
				setDetailMode(false);
				renderDetailView(detailItem);
				notifyOk("Saved catalog item.");
				return loadFacets().then(refreshCatalog);
			})
			.catch(function (e) {
				notifyErr(String(e.message || e));
			})
			.then(function () {
				if (saveBtn) saveBtn.disabled = false;
			});
	}

	function setStatus(text) {
		var el = document.getElementById("usis-mat-status");
		if (el) el.textContent = text || "";
	}

	function setEmptyVisible(show) {
		var empty = document.getElementById("usis-mat-empty");
		var grid = document.getElementById("usis-mat-grid-wrap");
		if (empty) empty.classList.toggle("d-none", !show);
		if (grid) grid.classList.toggle("d-none", show);
	}

	function hasActiveFilters() {
		return !!(
			state.q ||
			state.manufacturer ||
			state.item ||
			state.csi ||
			state.category ||
			state.description ||
			state.mounting ||
			state.cost ||
			state.labor ||
			state.uom ||
			state.size
		);
	}

	function filterParams() {
		var p = new URLSearchParams();
		if (state.q) p.set("q", state.q);
		if (state.manufacturer) p.set("manufacturer", state.manufacturer);
		if (state.item) p.set("item", state.item);
		if (state.csi) p.set("csi_spec_section", state.csi);
		if (state.category) p.set("category", state.category);
		if (state.description) p.set("description", state.description);
		if (state.mounting) p.set("mounting_type", state.mounting);
		if (state.cost) p.set("cost", state.cost);
		if (state.labor) p.set("labor_per", state.labor);
		if (state.uom) p.set("unit_of_measure", state.uom);
		if (state.size) p.set("size", state.size);
		return p;
	}

	function catalogUrl() {
		var p = filterParams();
		p.set("limit", String(state.limit));
		p.set("offset", String(state.offset));
		return apiBase() + "/api/v1/material-prices?" + p.toString();
	}

	function fetchCatalog() {
		return jsonFetch(catalogUrl());
	}

	function selectedCount() {
		if (!catalogTable) return 0;
		return catalogTable.getSelectedData().length;
	}

	function allMatchingChecked() {
		var allEl = document.getElementById("usis-mat-bulk-all-matching");
		return !!(allEl && allEl.checked);
	}

	function setAllMatching(on) {
		var allEl = document.getElementById("usis-mat-bulk-all-matching");
		if (allEl) allEl.checked = !!on;
	}

	function updateSelectionUi() {
		var n = selectedCount();
		var bulk = document.getElementById("usis-mat-bulk");
		if (bulk) bulk.disabled = n === 0 && state.total === 0;
		var countEl = document.getElementById("usis-mat-bulk-count");
		if (countEl) {
			if (allMatchingChecked() && state.total > 0) {
				countEl.textContent =
					"Bulk change will update all " +
					state.total +
					" row" +
					(state.total === 1 ? "" : "s") +
					" matching the current filters.";
			} else if (n) {
				countEl.textContent = n + " row" + (n === 1 ? "" : "s") + " selected on this page.";
			} else {
				countEl.textContent = "No rows selected on this page.";
			}
		}
		var allLabel = document.getElementById("usis-mat-bulk-all-label");
		if (allLabel) {
			allLabel.textContent =
				state.total > 0
					? "Apply to all " + state.total + " rows matching the current filters"
					: "Apply to all rows matching the current filters";
		}
	}

	function columnFilter(stateKey) {
		return function (cell, onRendered, success, cancel) {
			var input = document.createElement("input");
			input.type = "search";
			input.className = "form-control form-control-sm";
			input.placeholder = "Search";
			input.autocomplete = "off";
			var title = "";
			try {
				title = cell.getColumn().getDefinition().title || "";
			} catch (e) {
				title = "";
			}
			input.setAttribute("aria-label", (title || stateKey) + " search");
			input.value = state[stateKey] || "";
			input.addEventListener("input", function () {
				state[stateKey] = (input.value || "").trim();
				state.offset = 0;
				setAllMatching(false);
				scheduleSearch();
			});
			return input;
		};
	}

	function selectFilter(stateKey, facetKey, ariaLabel) {
		return function (cell, onRendered, success, cancel) {
			var select = document.createElement("select");
			select.className = "form-select form-select-sm";
			select.setAttribute("aria-label", ariaLabel || (stateKey + " filter"));
			function fill() {
				var current = state[stateKey] || "";
				select.innerHTML = "";
				var all = document.createElement("option");
				all.value = "";
				all.textContent = "All";
				select.appendChild(all);
				var hasCurrent = !current;
				(facetLists[facetKey] || []).forEach(function (entry) {
					var o = document.createElement("option");
					var value;
					if (entry && typeof entry === "object") {
						value = entry.value;
						o.value = value;
						o.textContent = entry.label;
					} else {
						value = entry;
						o.value = entry;
						o.textContent = entry;
					}
					if (String(value) === String(current)) hasCurrent = true;
					select.appendChild(o);
				});
				if (current && !hasCurrent) {
					var kept = document.createElement("option");
					kept.value = current;
					kept.textContent = current;
					select.appendChild(kept);
				}
				select.value = current;
			}
			fill();
			headerFilterFillers.push(fill);
			select.addEventListener("change", function () {
				state[stateKey] = (select.value || "").trim();
				state.offset = 0;
				setAllMatching(false);
				scheduleSearch();
			});
			onRendered(fill);
			return select;
		};
	}

	function refillHeaderFilters() {
		headerFilterFillers.forEach(function (fn) {
			try {
				fn();
			} catch (e) {}
		});
	}

	function loadFacets() {
		var qs = filterParams().toString();
		return jsonFetch(apiBase() + "/api/v1/material-prices/facets" + (qs ? "?" + qs : ""))
			.then(function (d) {
				facetLists.manufacturers = d.manufacturers || [];
				facetLists.categories = d.categories || [];
				facetLists.csi_sections = d.csi_sections || [];
				facetLists.sizes = d.sizes || [];
				facetLists.mounting_types = d.mounting_types || [];
				facetLists.units = d.units || [];
				facetLists.labor = d.labor || [];
				refillHeaderFilters();
			})
			.catch(function () {
				facetLists.manufacturers = [];
				facetLists.categories = [];
				facetLists.csi_sections = [];
				facetLists.sizes = [];
				facetLists.mounting_types = [];
				facetLists.units = [];
				facetLists.labor = [];
			});
	}

	function refreshCatalog() {
		setStatus("Loading…");
		return fetchCatalog()
			.then(function (d) {
				state.total = d.total != null ? Number(d.total) : (d.items || []).length;
				var rows = d.items || [];
				var empty = state.total === 0 && !hasActiveFilters();
				setEmptyVisible(empty);
				if (catalogTable) catalogTable.setData(rows);
				var from = state.total === 0 ? 0 : state.offset + 1;
				var to = Math.min(state.offset + rows.length, state.total);
				setStatus(
					state.total === 0
						? "No catalog rows"
						: "Showing " + from + "–" + to + " of " + state.total
				);
				updatePager();
				updateSelectionUi();
			})
			.catch(function (e) {
				setEmptyVisible(false);
				if (catalogTable) catalogTable.setData([]);
				setStatus("");
				notifyErr("Could not load material catalog. Sign in and run the CSV import. (" + String(e.message || e) + ")");
			});
	}

	function updatePager() {
		var prev = document.getElementById("usis-mat-prev");
		var next = document.getElementById("usis-mat-next");
		if (prev) prev.disabled = state.offset <= 0;
		if (next) next.disabled = state.offset + state.limit >= state.total;
	}

	var COL_LAYOUT_KEY = "usis-mat-col-layout-v1";

	function selectionColumnDef() {
		return {
			formatter: "rowSelection",
			titleFormatter: "rowSelection",
			cssClass: "usis-doc-check-col",
			hozAlign: "center",
			headerHozAlign: "center",
			headerSort: false,
			headerFilter: false,
			width: 52,
			minWidth: 52,
			frozen: true,
			resizable: false,
			download: false,
		};
	}

	function dataColumnDefs() {
		return [
			{
				title: "Manufacturer",
				field: "manufacturer",
				width: 128,
				headerFilter: selectFilter("manufacturer", "manufacturers", "Manufacturer filter"),
			},
			{
				title: "Item",
				field: "item",
				width: 110,
				headerFilter: columnFilter("item"),
				formatter: function (cell) {
					var v = cell.getValue();
					if (v == null || v === "") return "—";
					var btn = document.createElement("button");
					btn.type = "button";
					btn.className = "btn btn-link p-0 text-start usis-mat-item-open";
					btn.textContent = String(v);
					btn.addEventListener("mousedown", function (e) {
						e.stopPropagation();
					});
					btn.addEventListener("click", function (e) {
						e.stopPropagation();
						e.preventDefault();
						openDetail(cell.getRow().getData());
					});
					return btn;
				},
			},
			{
				title: "Division",
				field: "csi_display",
				width: 128,
				formatter: fmtCsi,
				hozAlign: "left",
				headerFilter: selectFilter("csi", "csi_sections", "Division filter"),
				tooltip: function (e, cell) {
					var row = cell.getRow().getData() || {};
					return row.csi_title || row.csi_display || row.csi_spec_section || "";
				},
			},
			{
				title: "Category",
				field: "category",
				width: 150,
				headerFilter: selectFilter("category", "categories", "Category filter"),
			},
			{
				title: "Size",
				field: "size_display",
				width: 96,
				formatter: fmtSize,
				headerFilter: selectFilter("size", "sizes", "Size filter"),
			},
			{
				title: "Description",
				field: "description",
				minWidth: 140,
				widthGrow: 2,
				headerFilter: columnFilter("description"),
			},
			{
				title: "Mounting",
				field: "mounting_type",
				width: 110,
				headerFilter: selectFilter("mounting", "mounting_types", "Mounting filter"),
			},
			{
				title: "Cost",
				field: "cost",
				width: 84,
				hozAlign: "right",
				formatter: fmtMoney,
				headerFilter: columnFilter("cost"),
			},
			{
				title: "Labor (hr)",
				field: "labor_per",
				width: 94,
				hozAlign: "right",
				formatter: fmtHours,
				headerFilter: selectFilter("labor", "labor", "Labor filter"),
			},
			{
				title: "UOM",
				field: "unit_of_measure",
				width: 72,
				headerFilter: selectFilter("uom", "units", "UOM filter"),
			},
		];
	}

	function loadColumnLayout() {
		try {
			var raw = localStorage.getItem(COL_LAYOUT_KEY);
			if (!raw) return null;
			var parsed = JSON.parse(raw);
			return Array.isArray(parsed) ? parsed : null;
		} catch (e) {
			return null;
		}
	}

	function saveColumnLayout() {
		if (!catalogTable) return;
		var layout = [];
		catalogTable.getColumns().forEach(function (col) {
			var def = col.getDefinition() || {};
			if (!def.field) return;
			layout.push({
				field: def.field,
				visible: col.isVisible(),
				width: col.getWidth(),
			});
		});
		try {
			localStorage.setItem(COL_LAYOUT_KEY, JSON.stringify(layout));
		} catch (e) {}
	}

	function applyColumnLayout(defs) {
		var layout = loadColumnLayout();
		var selection = defs[0];
		var byField = {};
		defs.slice(1).forEach(function (d) {
			if (d.field) byField[d.field] = d;
		});
		if (!layout || !layout.length) return defs;
		var ordered = [selection];
		var seen = {};
		layout.forEach(function (item) {
			if (!item || !item.field || !byField[item.field] || seen[item.field]) return;
			var d = Object.assign({}, byField[item.field]);
			d.visible = item.visible !== false;
			if (item.width) d.width = item.width;
			ordered.push(d);
			seen[item.field] = true;
		});
		defs.slice(1).forEach(function (d) {
			if (!d.field || seen[d.field]) return;
			ordered.push(d);
		});
		return ordered;
	}

	function fillColumnMenu() {
		var menu = document.getElementById("usis-mat-columns-menu");
		if (!menu || !catalogTable) return;
		menu.innerHTML = "";
		catalogTable.getColumns().forEach(function (col) {
			var def = col.getDefinition() || {};
			if (!def.field) return;
			var wrap = document.createElement("label");
			wrap.className = "dropdown-item d-flex align-items-center gap-2 mb-0";
			var box = document.createElement("input");
			box.type = "checkbox";
			box.className = "form-check-input mt-0";
			box.checked = col.isVisible();
			box.setAttribute("data-field", def.field);
			box.addEventListener("change", function () {
				if (!box.checked) {
					var visible = catalogTable.getColumns().filter(function (c) {
						var d = c.getDefinition() || {};
						return d.field && c.isVisible();
					});
					if (visible.length <= 1) {
						box.checked = true;
						notifyErr("Keep at least one column visible.");
						return;
					}
					col.hide();
				} else {
					col.show();
				}
				saveColumnLayout();
			});
			var label = document.createElement("span");
			label.textContent = def.title || def.field;
			wrap.appendChild(box);
			wrap.appendChild(label);
			menu.appendChild(wrap);
		});
		var divider = document.createElement("div");
		divider.className = "dropdown-divider";
		menu.appendChild(divider);
		var reset = document.createElement("button");
		reset.type = "button";
		reset.className = "dropdown-item";
		reset.textContent = "Reset column layout";
		reset.addEventListener("click", resetColumnLayout);
		menu.appendChild(reset);
	}

	function resetColumnLayout() {
		try {
			localStorage.removeItem(COL_LAYOUT_KEY);
		} catch (e) {}
		var rows = catalogTable ? catalogTable.getData() : [];
		buildTable();
		if (catalogTable) catalogTable.setData(rows);
		loadFacets();
	}

	function buildTable() {
		var el = document.getElementById("usis-mat-tabulator");
		if (!el || typeof Tabulator === "undefined") {
			var wrap = document.getElementById("usis-mat-grid-wrap");
			if (wrap) {
				wrap.innerHTML =
					'<div class="alert alert-warning mb-0">Material grid requires Tabulator (CDN). Check network or CSP.</div>';
			}
			return;
		}
		if (catalogTable) {
			try {
				catalogTable.destroy();
			} catch (e) {}
			catalogTable = null;
		}
		headerFilterFillers = [];
		catalogTable = new Tabulator(el, {
			layout: "fitDataStretch",
			height: "min(520px, 60vh)",
			headerFilterLiveFilter: false,
			movableColumns: true,
			resizableColumnFit: false,
			placeholder: "No rows match your filters.",
			selectableRows: true,
			selectableRowsRangeMode: "click",
			columnDefaults: {
				resizable: true,
				headerSort: true,
			},
			columns: applyColumnLayout([selectionColumnDef()].concat(dataColumnDefs())),
		});
		catalogTable.on("rowSelectionChanged", function () {
			var pageCount = catalogTable.getData().length;
			if (selectedCount() < pageCount) setAllMatching(false);
			updateSelectionUi();
		});
		catalogTable.on("columnMoved", function () {
			saveColumnLayout();
			fillColumnMenu();
		});
		catalogTable.on("columnResized", saveColumnLayout);
		catalogTable.on("tableBuilt", function () {
			var headerCb = el.querySelector(".usis-doc-check-col input[type=checkbox]");
			if (headerCb) {
				headerCb.classList.add("form-check-input", "m-0");
				headerCb.setAttribute("aria-label", "Select all rows on this page");
			}
			fillColumnMenu();
		});
		fillColumnMenu();
	}

	function scheduleSearch() {
		if (searchTimer) clearTimeout(searchTimer);
		searchTimer = setTimeout(function () {
			state.offset = 0;
			Promise.all([loadFacets(), refreshCatalog()]);
		}, 300);
	}

	function selectedIds() {
		return catalogTable
			? catalogTable.getSelectedData().map(function (row) {
					return row.id;
			  })
			: [];
	}

	function matchingIds() {
		return jsonFetch(apiBase() + "/api/v1/material-prices/ids?" + filterParams().toString()).then(function (d) {
			if (d.truncated) {
				throw new Error("Too many matching rows to bulk-change at once (cap 5000). Narrow the filter.");
			}
			return d.ids || [];
		});
	}

	function postBulkChunks(ids, field, value) {
		var updated = 0;
		var failed = 0;
		var chain = Promise.resolve();
		for (var i = 0; i < ids.length; i += BULK_CHUNK) {
			(function (chunk) {
				chain = chain.then(function () {
					return jsonFetch(apiBase() + "/api/v1/material-prices/bulk", {
						method: "POST",
						body: JSON.stringify({ ids: chunk, field: field, value: value }),
					}).then(function (d) {
						updated += d.updated_count || 0;
						failed += d.failed_count || 0;
					});
				});
			})(ids.slice(i, i + BULK_CHUNK));
		}
		return chain.then(function () {
			return { updated_count: updated, failed_count: failed };
		});
	}

	function hideActionsMenu() {
		var btn = document.getElementById("usis-mat-actions");
		if (!btn || typeof bootstrap === "undefined" || !bootstrap.Dropdown) return;
		var inst = bootstrap.Dropdown.getInstance(btn);
		if (inst) inst.hide();
	}

	function openBulkModal() {
		updateSelectionUi();
		hideActionsMenu();
		var modalEl = document.getElementById("usis-mat-bulk-modal");
		if (!modalEl) return;
		if (typeof bootstrap !== "undefined" && bootstrap.Modal) {
			bootstrap.Modal.getOrCreateInstance(modalEl).show();
		}
		var value = document.getElementById("usis-mat-bulk-value");
		if (value) {
			value.value = "";
			value.focus();
		}
	}

	function applyBulk() {
		var fieldEl = document.getElementById("usis-mat-bulk-field");
		var valueEl = document.getElementById("usis-mat-bulk-value");
		var allEl = document.getElementById("usis-mat-bulk-all-matching");
		var field = fieldEl ? fieldEl.value : "";
		var value = valueEl ? valueEl.value : "";
		var useAll = !!(allEl && allEl.checked);
		var applyBtn = document.getElementById("usis-mat-bulk-apply");
		if (!field) {
			notifyErr("Choose a field to change.");
			return;
		}
		var idsPromise = useAll ? matchingIds() : Promise.resolve(selectedIds());
		if (applyBtn) applyBtn.disabled = true;
		idsPromise
			.then(function (ids) {
				if (!ids.length) throw new Error("Select rows, or turn on “all matching filters”.");
				if (
					!window.confirm(
						"Change " +
							field.replace(/_/g, " ") +
							" on " +
							ids.length +
							" catalog row" +
							(ids.length === 1 ? "" : "s") +
							"?"
					)
				) {
					return null;
				}
				return postBulkChunks(ids, field, value);
			})
			.then(function (d) {
				if (!d) return;
				var modalEl = document.getElementById("usis-mat-bulk-modal");
				if (modalEl && typeof bootstrap !== "undefined" && bootstrap.Modal) {
					var inst = bootstrap.Modal.getInstance(modalEl);
					if (inst) inst.hide();
				}
				notifyOk("Updated " + (d.updated_count || 0) + " catalog row" + (d.updated_count === 1 ? "" : "s") + ".");
				return loadFacets().then(refreshCatalog);
			})
			.catch(function (e) {
				notifyErr(String(e.message || e));
			})
			.then(function () {
				if (applyBtn) applyBtn.disabled = false;
			});
	}

	function wireUi() {
		var search = document.getElementById("usis-mat-search");
		var refreshBtn = document.getElementById("usis-mat-refresh");
		var prev = document.getElementById("usis-mat-prev");
		var next = document.getElementById("usis-mat-next");
		var bulk = document.getElementById("usis-mat-bulk");
		var apply = document.getElementById("usis-mat-bulk-apply");

		if (search) {
			search.addEventListener("input", function () {
				state.q = (search.value || "").trim();
				setAllMatching(false);
				scheduleSearch();
			});
		}
		if (refreshBtn) {
			refreshBtn.addEventListener("click", function () {
				loadFacets().then(refreshCatalog);
			});
		}
		if (prev) {
			prev.addEventListener("click", function () {
				state.offset = Math.max(0, state.offset - state.limit);
				refreshCatalog();
			});
		}
		if (next) {
			next.addEventListener("click", function () {
				if (state.offset + state.limit < state.total) {
					state.offset += state.limit;
					refreshCatalog();
				}
			});
		}
		if (bulk) bulk.addEventListener("click", openBulkModal);
		if (apply) apply.addEventListener("click", applyBulk);
		var editBtn = document.getElementById("usis-mat-detail-edit");
		var saveBtn = document.getElementById("usis-mat-detail-save");
		var cancelBtn = document.getElementById("usis-mat-detail-cancel");
		if (editBtn) {
			editBtn.addEventListener("click", function () {
				if (!detailItem) return;
				fillDetailForm(detailItem);
				setDetailMode(true);
				var first = document.getElementById("usis-mat-edit-item");
				if (first) first.focus();
			});
		}
		if (saveBtn) saveBtn.addEventListener("click", saveDetail);
		var detailForm = document.getElementById("usis-mat-detail-form");
		if (detailForm) {
			detailForm.addEventListener("submit", function (ev) {
				ev.preventDefault();
				saveDetail();
			});
		}
		if (cancelBtn) {
			cancelBtn.addEventListener("click", function () {
				setDetailMode(false);
				if (detailItem) renderDetailView(detailItem);
			});
		}
		var allMatching = document.getElementById("usis-mat-bulk-all-matching");
		if (allMatching) allMatching.addEventListener("change", updateSelectionUi);
		var valueEl = document.getElementById("usis-mat-bulk-value");
		if (valueEl) {
			valueEl.addEventListener("keydown", function (ev) {
				if (ev.key === "Enter") {
					ev.preventDefault();
					applyBulk();
				}
			});
		}
	}

	function init() {
		if (!document.getElementById("usis-mat-tabulator")) return;
		wireUi();
		if (window.USISDrawingCache) window.USISDrawingCache.refresh();
		loadFacets().then(function () {
			buildTable();
			refreshCatalog();
		});
	}

	if (document.readyState === "loading") {
		document.addEventListener("DOMContentLoaded", init);
	} else {
		init();
	}
})();
