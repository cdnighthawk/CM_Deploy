/**
 * Construction — Material catalog (material_pricing via GET /api/v1/material-prices).
 */
(function () {
	"use strict";

	var catalogTable = null;
	var searchTimer = null;
	var BULK_CHUNK = 2000;
	var PAGE_SIZE = 100;
	var headerFilterFillers = [];
	var facetLists = {
		manufacturers: [],
		categories: [],
		csi_sections: [],
		sizes: [],
		mounting_types: [],
		units: [],
		labor: [],
		suppliers: [],
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
		supplier: "",
		offset: 0,
		limit: PAGE_SIZE,
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

	function fmtRate(cell) {
		var row = cell.getRow().getData() || {};
		return row.labor_production || "—";
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
	var supplierSearchTimer = null;
	var supplierPickerBound = false;

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

	function hoursFromRate(rate, unit) {
		var n = Number(rate);
		if (!n || n <= 0 || (unit !== "SF" && unit !== "LF")) return "";
		var hours = 1 / n;
		return String(Number(hours.toFixed(4)));
	}

	function syncLaborFromRate() {
		var rateEl = document.getElementById("usis-mat-edit-rate");
		var unitEl = document.getElementById("usis-mat-edit-rate-unit");
		var labor = document.getElementById("usis-mat-edit-labor");
		var uom = document.getElementById("usis-mat-edit-uom");
		var hint = document.getElementById("usis-mat-edit-labor-hint");
		if (!labor) return;
		var unit = unitEl ? unitEl.value : "";
		var hours = hoursFromRate(rateEl ? rateEl.value : "", unit);
		var currentUom = String((uom && uom.value) || "").toUpperCase();
		var isEa = !currentUom || currentUom === "EA" || currentUom === "EACH";
		var measuredLf = currentUom === "LF" || currentUom === "FT";
		var applySf = hours && unit === "SF" && (currentUom === "SF" || isEa);
		var applyLf = hours && unit === "LF" && measuredLf;
		if (applySf || applyLf) {
			labor.value = hours;
			labor.readOnly = true;
			if (uom) uom.value = unit;
			if (hint) {
				hint.textContent =
					unit === "SF"
						? "Hours = (length × height) ÷ " +
						  String(rateEl.value).trim() +
						  " SF/hr (" +
						  hours +
						  " hr per SF)."
						: "Hours = quantity ÷ " +
						  String(rateEl.value).trim() +
						  " LF/hr (" +
						  hours +
						  " hr per LF).";
			}
		} else {
			labor.readOnly = false;
			if (hint) {
				hint.textContent =
					"EA items use hours per each. Rigid sheet and FRP use SF/hour (length × height). Feet/hour only when UOM is LF.";
			}
		}
	}

	function supplierEmailHint(item) {
		var hint = document.getElementById("usis-mat-edit-supplier-email");
		if (!hint) return;
		if (item && item.supplier_email) {
			hint.innerHTML =
				'Email: <a href="mailto:' +
				escHtml(item.supplier_email) +
				'">' +
				escHtml(item.supplier_email) +
				"</a>";
		} else if (item && item.supplier_company_id) {
			hint.textContent = "No email on this company. Add one in Companies so supplier notices can send.";
		} else {
			hint.textContent = "Link the company you buy this item from. Their email is used for supplier notices.";
		}
	}

	function hideSupplierMenu() {
		var menu = document.getElementById("usis-mat-edit-supplier-menu");
		if (menu) menu.classList.add("d-none");
	}

	function searchSupplierCompanies(q) {
		return jsonFetch(apiBase() + "/api/v1/companies?limit=20&q=" + encodeURIComponent(q)).then(function (d) {
			return d.items || [];
		});
	}

	function renderSupplierMenu(items) {
		var menu = document.getElementById("usis-mat-edit-supplier-menu");
		if (!menu) return;
		menu.innerHTML = "";
		if (!items.length) {
			menu.innerHTML = '<div class="list-group-item small text-muted">No matching companies</div>';
			menu.classList.remove("d-none");
			return;
		}
		items.forEach(function (c) {
			var btn = document.createElement("button");
			btn.type = "button";
			btn.className = "list-group-item list-group-item-action py-1 small";
			btn.textContent = (c.name || "Company") + (c.email ? " · " + c.email : "");
			btn.addEventListener("mousedown", function (e) {
				e.preventDefault();
			});
			btn.addEventListener("click", function () {
				var idEl = document.getElementById("usis-mat-edit-supplier-id");
				var nameEl = document.getElementById("usis-mat-edit-supplier");
				if (idEl) idEl.value = c.id || "";
				if (nameEl) nameEl.value = c.name || "";
				supplierEmailHint({
					supplier_company_id: c.id,
					supplier_email: c.email || "",
				});
				hideSupplierMenu();
			});
			menu.appendChild(btn);
		});
		menu.classList.remove("d-none");
	}

	function bindSupplierPicker() {
		if (supplierPickerBound) return;
		var input = document.getElementById("usis-mat-edit-supplier");
		var hidden = document.getElementById("usis-mat-edit-supplier-id");
		if (!input) return;
		supplierPickerBound = true;
		input.addEventListener("input", function () {
			if (hidden) hidden.value = "";
			clearTimeout(supplierSearchTimer);
			var q = (input.value || "").trim();
			if (!q) {
				hideSupplierMenu();
				supplierEmailHint(null);
				return;
			}
			supplierSearchTimer = setTimeout(function () {
				searchSupplierCompanies(q)
					.then(renderSupplierMenu)
					.catch(function () {
						hideSupplierMenu();
					});
			}, 250);
		});
		input.addEventListener("blur", function () {
			setTimeout(hideSupplierMenu, 200);
		});
	}

	function fillDetailForm(item) {
		var map = {
			"usis-mat-edit-manufacturer": item.manufacturer,
			"usis-mat-edit-manufacturer-url": item.manufacturer_url,
			"usis-mat-edit-item": item.item,
			"usis-mat-edit-category": item.category,
			"usis-mat-edit-csi": item.csi_display || item.csi_spec_section,
			"usis-mat-edit-description": item.description,
			"usis-mat-edit-mounting": item.mounting_type,
			"usis-mat-edit-width": item.size_width_in,
			"usis-mat-edit-depth": item.size_depth_in,
			"usis-mat-edit-height": item.size_height_in,
			"usis-mat-edit-cost": item.cost,
			"usis-mat-edit-rate": item.labor_units_per_hour,
			"usis-mat-edit-labor": item.labor_per,
			"usis-mat-edit-uom": item.unit_of_measure,
			"usis-mat-edit-currency": item.currency,
		};
		Object.keys(map).forEach(function (id) {
			var el = document.getElementById(id);
			if (el) el.value = map[id] == null ? "" : String(map[id]);
		});
		var supplierId = document.getElementById("usis-mat-edit-supplier-id");
		var supplierName = document.getElementById("usis-mat-edit-supplier");
		if (supplierId) supplierId.value = item.supplier_company_id || "";
		if (supplierName) supplierName.value = item.supplier_name || "";
		supplierEmailHint(item);
		bindSupplierPicker();
		var unitEl = document.getElementById("usis-mat-edit-rate-unit");
		if (unitEl) unitEl.value = item.labor_rate_unit === "SF" || item.labor_rate_unit === "LF" ? item.labor_rate_unit : "";
		syncLaborFromRate();
	}

	function fmtUrlLink(url) {
		var href = String(url || "").trim();
		if (!href) return "—";
		if (!/^https?:\/\//i.test(href)) return escHtml(href);
		return (
			'<a href="' +
			escHtml(href) +
			'" target="_blank" rel="noopener noreferrer">' +
			escHtml(href) +
			"</a>"
		);
	}

	function formatConfigurator(item) {
		var cfg = item && item.configurator;
		if (!cfg || !cfg.groups || !cfg.groups.length) return "";
		return cfg.groups
			.map(function (g) {
				var names = (g.choices || [])
					.map(function (c) {
						return c.label;
					})
					.join(", ");
				return g.label + ": " + names;
			})
			.join(" | ");
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
			["Manufacturer URL", item.manufacturer_url],
			["Buy from", dash(item.supplier_name)],
			["Supplier email", dash(item.supplier_email)],
			["Category", dash(item.category)],
			["Division", division],
			["CSI section", dash(item.csi_spec_section)],
			["Size", dash(item.size_display)],
			["Width (in)", dash(item.size_width_in)],
			["Depth (in)", dash(item.size_depth_in)],
			["Height (in)", dash(item.size_height_in)],
			["Sheet area (sf)", dash(item.sheet_area_sf)],
			["Description", dash(item.description)],
			["Mounting", dash(item.mounting_type)],
			["Configurable options", formatConfigurator(item)],
			["Cost", moneyText(item.cost)],
			["Production rate", dash(item.labor_production)],
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
					var body = pair[0] === "Manufacturer URL" ? fmtUrlLink(pair[1]) : escHtml(pair[1]);
					return (
						'<dt class="col-sm-4 col-lg-3 text-muted small">' +
						escHtml(pair[0]) +
						'</dt><dd class="col-sm-8 col-lg-9">' +
						body +
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
			manufacturer_url: inputVal("usis-mat-edit-manufacturer-url"),
			item: inputVal("usis-mat-edit-item"),
			category: inputVal("usis-mat-edit-category"),
			csi_spec_section: inputVal("usis-mat-edit-csi"),
			description: inputVal("usis-mat-edit-description"),
			mounting_type: inputVal("usis-mat-edit-mounting"),
			size_width_in: inputVal("usis-mat-edit-width"),
			size_depth_in: inputVal("usis-mat-edit-depth"),
			size_height_in: inputVal("usis-mat-edit-height"),
			cost: inputVal("usis-mat-edit-cost"),
			labor_units_per_hour: inputVal("usis-mat-edit-rate"),
			labor_rate_unit: inputVal("usis-mat-edit-rate-unit"),
			labor_per: inputVal("usis-mat-edit-labor"),
			unit_of_measure: inputVal("usis-mat-edit-uom"),
			currency: inputVal("usis-mat-edit-currency"),
			supplier_company_id: inputVal("usis-mat-edit-supplier-id") || inputVal("usis-mat-edit-supplier"),
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
			state.size ||
			state.supplier
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
		if (state.supplier) p.set("supplier", state.supplier);
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
		var del = document.getElementById("usis-mat-delete");
		if (del) del.disabled = n === 0 && state.total === 0;
		var deleting = bulkModeIsDelete();
		var countEl = document.getElementById("usis-mat-bulk-count");
		if (countEl) {
			if (allMatchingChecked() && state.total > 0) {
				countEl.textContent =
					(deleting ? "Delete" : "Bulk change") +
					" will " +
					(deleting ? "remove" : "update") +
					" all " +
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
		syncBulkModeUi();
	}

	function bulkModeIsDelete() {
		var fieldEl = document.getElementById("usis-mat-bulk-field");
		return !!(fieldEl && fieldEl.value === "delete");
	}

	function syncBulkModeUi() {
		var deleting = bulkModeIsDelete();
		var title = document.getElementById("usis-mat-bulk-title");
		if (title) title.textContent = deleting ? "Delete catalog items" : "Bulk change";
		var wrap = document.getElementById("usis-mat-bulk-value-wrap");
		if (wrap) wrap.classList.toggle("d-none", deleting);
		var hint = document.getElementById("usis-mat-bulk-delete-hint");
		if (hint) hint.classList.toggle("d-none", !deleting);
		var applyBtn = document.getElementById("usis-mat-bulk-apply");
		if (applyBtn) {
			applyBtn.textContent = deleting ? "Delete" : "Apply";
			applyBtn.classList.toggle("btn-primary", !deleting);
			applyBtn.classList.toggle("btn-danger", deleting);
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
				facetLists.suppliers = d.suppliers || [];
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
				facetLists.suppliers = [];
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
						: "Showing " + from.toLocaleString() + "–" + to.toLocaleString() + " of " + state.total.toLocaleString()
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

	var COL_LAYOUT_KEY = "usis-mat-col-layout-v2";

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
				width: 170,
				minWidth: 148,
				tooltip: true,
				headerFilter: selectFilter("manufacturer", "manufacturers", "Manufacturer filter"),
			},
			{
				title: "Manufacturer URL",
				field: "manufacturer_url",
				width: 220,
				minWidth: 160,
				tooltip: true,
				formatter: function (cell) {
					var v = cell.getValue();
					if (v == null || v === "") return "—";
					var href = String(v).trim();
					if (!/^https?:\/\//i.test(href)) return href;
					var a = document.createElement("a");
					a.href = href;
					a.target = "_blank";
					a.rel = "noopener noreferrer";
					a.textContent = href;
					a.title = href;
					a.addEventListener("mousedown", function (e) {
						e.stopPropagation();
					});
					a.addEventListener("click", function (e) {
						e.stopPropagation();
					});
					return a;
				},
			},
			{
				title: "Buy from",
				field: "supplier_name",
				width: 170,
				minWidth: 140,
				tooltip: function (e, cell) {
					var row = cell.getRow().getData() || {};
					if (row.supplier_email) return row.supplier_name + " · " + row.supplier_email;
					return row.supplier_name || "";
				},
				headerFilter: selectFilter("supplier", "suppliers", "Supplier filter"),
				formatter: function (cell) {
					var row = cell.getRow().getData() || {};
					var name = row.supplier_name;
					if (!name) return "—";
					if (row.supplier_email) {
						var a = document.createElement("a");
						a.href = "mailto:" + String(row.supplier_email);
						a.textContent = String(name);
						a.title = String(row.supplier_email);
						a.addEventListener("mousedown", function (e) {
							e.stopPropagation();
						});
						a.addEventListener("click", function (e) {
							e.stopPropagation();
						});
						return a;
					}
					return String(name);
				},
			},
			{
				title: "Item",
				field: "item",
				width: 300,
				minWidth: 220,
				widthGrow: 1.5,
				headerFilter: columnFilter("item"),
				tooltip: function (e, cell) {
					var v = cell.getValue();
					return v == null || v === "" ? "" : String(v);
				},
				formatter: function (cell) {
					var v = cell.getValue();
					if (v == null || v === "") return "—";
					var btn = document.createElement("button");
					btn.type = "button";
					btn.className = "btn btn-link p-0 text-start usis-mat-item-open";
					btn.textContent = String(v);
					btn.title = String(v);
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
				width: 118,
				minWidth: 108,
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
				width: 160,
				minWidth: 128,
				tooltip: true,
				headerFilter: selectFilter("category", "categories", "Category filter"),
			},
			{
				title: "Size",
				field: "size_display",
				width: 96,
				minWidth: 88,
				formatter: fmtSize,
				headerFilter: selectFilter("size", "sizes", "Size filter"),
			},
			{
				title: "Description",
				field: "description",
				minWidth: 180,
				widthGrow: 2,
				tooltip: true,
				headerFilter: columnFilter("description"),
			},
			{
				title: "Mounting",
				field: "mounting_type",
				width: 120,
				minWidth: 118,
				tooltip: true,
				headerFilter: selectFilter("mounting", "mounting_types", "Mounting filter"),
			},
			{
				title: "Cost",
				field: "cost",
				width: 92,
				minWidth: 88,
				hozAlign: "right",
				formatter: fmtMoney,
				headerFilter: columnFilter("cost"),
			},
			{
				title: "Prod. rate",
				field: "labor_production",
				width: 118,
				minWidth: 110,
				formatter: fmtRate,
			},
			{
				title: "Labor (hr)",
				field: "labor_per",
				width: 114,
				minWidth: 110,
				hozAlign: "right",
				formatter: fmtHours,
				headerFilter: selectFilter("labor", "labor", "Labor filter"),
			},
			{
				title: "UOM",
				field: "unit_of_measure",
				width: 80,
				minWidth: 76,
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
			if (item.width) {
				var saved = Number(item.width) || 0;
				var floor = Number(d.minWidth) || 0;
				d.width = saved > floor ? saved : floor || saved;
			}
			ordered.push(d);
			seen[item.field] = true;
		});
		defs.slice(1).forEach(function (d) {
			if (!d.field || seen[d.field]) return;
			ordered.push(d);
		});
		return ordered;
	}

	var COLUMN_GROUPS = [
		{ title: "Catalog", fields: ["manufacturer", "manufacturer_url", "supplier_name", "item", "description"] },
		{ title: "Classification", fields: ["csi_display", "category", "size_display", "mounting_type"] },
		{ title: "Pricing", fields: ["cost", "labor_production", "labor_per", "unit_of_measure"] },
	];
	var columnDraft = { selected: [], baseline: "" };
	var columnDragField = null;

	function columnMeta() {
		var byField = {};
		dataColumnDefs().forEach(function (d) {
			if (d.field) byField[d.field] = { field: d.field, title: d.title || d.field };
		});
		return byField;
	}

	function allColumnFields() {
		return dataColumnDefs()
			.map(function (d) {
				return d.field;
			})
			.filter(Boolean);
	}

	function visibleColumnFields() {
		if (!catalogTable) return allColumnFields();
		var fields = [];
		catalogTable.getColumns().forEach(function (col) {
			var def = col.getDefinition() || {};
			if (!def.field) return;
			if (col.isVisible()) fields.push(def.field);
		});
		return fields.length ? fields : allColumnFields();
	}

	function draftKey(selected) {
		return (selected || []).join("|");
	}

	function setColumnApplyEnabled() {
		var apply = document.getElementById("usis-mat-cols-apply");
		if (!apply) return;
		apply.disabled = !columnDraft.selected.length || draftKey(columnDraft.selected) === columnDraft.baseline;
	}

	function toggleDraftColumn(field, on) {
		var ix = columnDraft.selected.indexOf(field);
		if (on && ix < 0) columnDraft.selected.push(field);
		if (!on && ix >= 0) {
			if (columnDraft.selected.length <= 1) {
				notifyErr("Keep at least one column visible.");
				renderColumnCustomizer();
				return;
			}
			columnDraft.selected.splice(ix, 1);
		}
		renderColumnCustomizer();
	}

	function moveDraftColumn(fromField, toField) {
		if (!fromField || fromField === toField) return;
		var from = columnDraft.selected.indexOf(fromField);
		var to = columnDraft.selected.indexOf(toField);
		if (from < 0 || to < 0) return;
		var moved = columnDraft.selected.splice(from, 1)[0];
		columnDraft.selected.splice(to, 0, moved);
		renderColumnCustomizer();
	}

	function gripHtml() {
		return (
			'<span class="usis-mat-col-grip" aria-hidden="true">' +
			"<span></span><span></span><span></span><span></span><span></span><span></span>" +
			"</span>"
		);
	}

	function groupedColumnFields() {
		var grouped = {};
		var leftover = [];
		COLUMN_GROUPS.forEach(function (group) {
			group.fields.forEach(function (field) {
				grouped[field] = true;
			});
		});
		allColumnFields().forEach(function (field) {
			if (!grouped[field]) leftover.push(field);
		});
		if (!leftover.length) return COLUMN_GROUPS;
		return COLUMN_GROUPS.concat([{ title: "Other", fields: leftover }]);
	}

	function renderColumnCustomizer() {
		var available = document.getElementById("usis-mat-cols-available");
		var selected = document.getElementById("usis-mat-cols-selected");
		var count = document.getElementById("usis-mat-cols-count");
		if (!available || !selected) return;
		var meta = columnMeta();
		var total = allColumnFields().length;
		var n = columnDraft.selected.length;
		if (count) count.textContent = n + " / " + total + " Selected Columns";

		var html = "";
		groupedColumnFields().forEach(function (group) {
			html += '<div class="usis-mat-cols-group">';
			html += '<div class="usis-mat-cols-group-title">' + escHtml(group.title) + "</div>";
			group.fields.forEach(function (field) {
				var info = meta[field];
				if (!info) return;
				var checked = columnDraft.selected.indexOf(field) >= 0;
				html +=
					'<label class="usis-mat-cols-check">' +
					'<input type="checkbox" class="form-check-input" data-col-field="' +
					escHtml(field) +
					'"' +
					(checked ? " checked" : "") +
					">" +
					"<span>" +
					escHtml(info.title) +
					"</span></label>";
			});
			html += "</div>";
		});
		available.innerHTML = html;
		selected.innerHTML = columnDraft.selected
			.map(function (field) {
				var info = meta[field] || { title: field };
				return (
					'<div class="usis-mat-col-chip" draggable="true" data-col-field="' +
					escHtml(field) +
					'">' +
					"<span>" +
					escHtml(info.title) +
					"</span>" +
					gripHtml() +
					"</div>"
				);
			})
			.join("");

		Array.prototype.forEach.call(available.querySelectorAll("[data-col-field]"), function (box) {
			box.addEventListener("change", function () {
				toggleDraftColumn(box.getAttribute("data-col-field"), box.checked);
			});
		});
		Array.prototype.forEach.call(selected.querySelectorAll(".usis-mat-col-chip"), function (chip) {
			chip.addEventListener("dragstart", function (e) {
				columnDragField = chip.getAttribute("data-col-field");
				chip.classList.add("is-dragging");
				if (e.dataTransfer) {
					e.dataTransfer.effectAllowed = "move";
					e.dataTransfer.setData("text/plain", columnDragField);
				}
			});
			chip.addEventListener("dragend", function () {
				columnDragField = null;
				chip.classList.remove("is-dragging");
				Array.prototype.forEach.call(selected.querySelectorAll(".usis-mat-col-chip"), function (el) {
					el.classList.remove("is-drop-target");
				});
			});
			chip.addEventListener("dragover", function (e) {
				e.preventDefault();
				if (e.dataTransfer) e.dataTransfer.dropEffect = "move";
				chip.classList.add("is-drop-target");
			});
			chip.addEventListener("dragleave", function () {
				chip.classList.remove("is-drop-target");
			});
			chip.addEventListener("drop", function (e) {
				e.preventDefault();
				chip.classList.remove("is-drop-target");
				moveDraftColumn(columnDragField, chip.getAttribute("data-col-field"));
			});
		});
		setColumnApplyEnabled();
	}

	function openColumnCustomizer() {
		hideActionsMenu();
		columnDraft.selected = visibleColumnFields().slice();
		columnDraft.baseline = draftKey(columnDraft.selected);
		renderColumnCustomizer();
		var modalEl = document.getElementById("usis-mat-cols-modal");
		if (!modalEl) return;
		if (typeof bootstrap !== "undefined" && bootstrap.Modal) {
			bootstrap.Modal.getOrCreateInstance(modalEl).show();
		}
	}

	function applyColumnDraft() {
		if (!columnDraft.selected.length) {
			notifyErr("Keep at least one column visible.");
			return;
		}
		var widths = {};
		if (catalogTable) {
			catalogTable.getColumns().forEach(function (col) {
				var def = col.getDefinition() || {};
				if (def.field) widths[def.field] = col.getWidth();
			});
		}
		var seen = {};
		var layout = [];
		columnDraft.selected.forEach(function (field) {
			if (!field || seen[field]) return;
			layout.push({ field: field, visible: true, width: widths[field] });
			seen[field] = true;
		});
		allColumnFields().forEach(function (field) {
			if (seen[field]) return;
			layout.push({ field: field, visible: false, width: widths[field] });
			seen[field] = true;
		});
		try {
			localStorage.setItem(COL_LAYOUT_KEY, JSON.stringify(layout));
		} catch (e) {}
		var rows = catalogTable ? catalogTable.getData() : [];
		buildTable();
		if (catalogTable) catalogTable.setData(rows);
		var modalEl = document.getElementById("usis-mat-cols-modal");
		if (modalEl && typeof bootstrap !== "undefined" && bootstrap.Modal) {
			var inst = bootstrap.Modal.getInstance(modalEl);
			if (inst) inst.hide();
		}
	}

	function resetColumnDraft() {
		columnDraft.selected = allColumnFields().slice();
		renderColumnCustomizer();
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
			layout: "fitDataFill",
			height: "min(720px, 70vh)",
			headerFilterLiveFilter: false,
			movableColumns: true,
			resizableColumnFit: false,
			placeholder: "No rows match your filters.",
			selectableRows: true,
			selectableRowsRangeMode: "click",
			columnDefaults: {
				resizable: true,
				headerSort: true,
				headerTooltip: true,
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
		});
		catalogTable.on("columnResized", saveColumnLayout);
		catalogTable.on("tableBuilt", function () {
			var headerCb = el.querySelector(".usis-doc-check-col input[type=checkbox]");
			if (headerCb) {
				headerCb.classList.add("form-check-input", "m-0");
				headerCb.setAttribute("aria-label", "Select all rows on this page");
			}
		});
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
		var deleting = field === "delete";
		var chain = Promise.resolve();
		for (var i = 0; i < ids.length; i += BULK_CHUNK) {
			(function (chunk) {
				chain = chain.then(function () {
					return jsonFetch(apiBase() + "/api/v1/material-prices/bulk", {
						method: "POST",
						body: JSON.stringify(
							deleting
								? { ids: chunk, action: "delete" }
								: { ids: chunk, field: field, value: value }
						),
					}).then(function (d) {
						updated += d.updated_count || d.deleted_count || 0;
						failed += d.failed_count || 0;
					});
				});
			})(ids.slice(i, i + BULK_CHUNK));
		}
		return chain.then(function () {
			return deleting
				? { action: "delete", deleted_count: updated, failed_count: failed }
				: { updated_count: updated, failed_count: failed };
		});
	}

	function hideActionsMenu() {
		var btn = document.getElementById("usis-mat-actions");
		if (!btn || typeof bootstrap === "undefined" || !bootstrap.Dropdown) return;
		var inst = bootstrap.Dropdown.getInstance(btn);
		if (inst) inst.hide();
	}

	function openBulkModal(mode) {
		var fieldEl = document.getElementById("usis-mat-bulk-field");
		if (fieldEl) {
			if (mode === "delete") fieldEl.value = "delete";
			else if (fieldEl.value === "delete") fieldEl.value = "csi_spec_section";
		}
		updateSelectionUi();
		hideActionsMenu();
		var modalEl = document.getElementById("usis-mat-bulk-modal");
		if (!modalEl) return;
		if (typeof bootstrap !== "undefined" && bootstrap.Modal) {
			bootstrap.Modal.getOrCreateInstance(modalEl).show();
		}
		var value = document.getElementById("usis-mat-bulk-value");
		if (value && mode !== "delete") {
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
		var deleting = field === "delete";
		if (!field) {
			notifyErr("Choose a field to change.");
			return;
		}
		var idsPromise = useAll ? matchingIds() : Promise.resolve(selectedIds());
		if (applyBtn) applyBtn.disabled = true;
		idsPromise
			.then(function (ids) {
				if (!ids.length) throw new Error("Select rows, or turn on “all matching filters”.");
				var msg = deleting
					? "Permanently delete " +
					  ids.length +
					  " catalog row" +
					  (ids.length === 1 ? "" : "s") +
					  "? This cannot be undone."
					: "Change " +
					  field.replace(/_/g, " ") +
					  " on " +
					  ids.length +
					  " catalog row" +
					  (ids.length === 1 ? "" : "s") +
					  "?";
				if (!window.confirm(msg)) return null;
				return postBulkChunks(ids, field, value);
			})
			.then(function (d) {
				if (!d) return;
				var modalEl = document.getElementById("usis-mat-bulk-modal");
				if (modalEl && typeof bootstrap !== "undefined" && bootstrap.Modal) {
					var inst = bootstrap.Modal.getInstance(modalEl);
					if (inst) inst.hide();
				}
				if (d.action === "delete") {
					notifyOk(
						"Deleted " +
							(d.deleted_count || 0) +
							" catalog row" +
							(d.deleted_count === 1 ? "" : "s") +
							"."
					);
				} else {
					notifyOk(
						"Updated " +
							(d.updated_count || 0) +
							" catalog row" +
							(d.updated_count === 1 ? "" : "s") +
							"."
					);
				}
				setAllMatching(false);
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
		var bulk = document.getElementById("usis-mat-bulk");
		var delBtn = document.getElementById("usis-mat-delete");
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
				hideActionsMenu();
				loadFacets().then(refreshCatalog);
			});
		}
		var prev = document.getElementById("usis-mat-prev");
		var next = document.getElementById("usis-mat-next");
		if (prev) {
			prev.addEventListener("click", function () {
				hideActionsMenu();
				state.offset = Math.max(0, state.offset - state.limit);
				refreshCatalog();
			});
		}
		if (next) {
			next.addEventListener("click", function () {
				hideActionsMenu();
				if (state.offset + state.limit < state.total) {
					state.offset += state.limit;
					refreshCatalog();
				}
			});
		}
		var selectAll = document.getElementById("usis-mat-select-all");
		if (selectAll) {
			selectAll.addEventListener("click", function () {
				if (!catalogTable) return;
				hideActionsMenu();
				catalogTable.selectRow();
				if (state.total > 0) setAllMatching(true);
				updateSelectionUi();
			});
		}
		if (bulk) bulk.addEventListener("click", function () {
			openBulkModal("change");
		});
		if (delBtn) delBtn.addEventListener("click", function () {
			openBulkModal("delete");
		});
		var colsBtn = document.getElementById("usis-mat-columns");
		if (colsBtn) {
			colsBtn.addEventListener("click", function (e) {
				e.preventDefault();
				e.stopPropagation();
				openColumnCustomizer();
			});
		}
		var colsApply = document.getElementById("usis-mat-cols-apply");
		if (colsApply) colsApply.addEventListener("click", applyColumnDraft);
		var colsReset = document.getElementById("usis-mat-cols-reset");
		if (colsReset) colsReset.addEventListener("click", resetColumnDraft);
		if (apply) apply.addEventListener("click", applyBulk);
		var fieldEl = document.getElementById("usis-mat-bulk-field");
		if (fieldEl) fieldEl.addEventListener("change", updateSelectionUi);
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
		["usis-mat-edit-rate", "usis-mat-edit-rate-unit", "usis-mat-edit-uom"].forEach(function (id) {
			var el = document.getElementById(id);
			if (!el) return;
			el.addEventListener("input", syncLaborFromRate);
			el.addEventListener("change", syncLaborFromRate);
		});
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
