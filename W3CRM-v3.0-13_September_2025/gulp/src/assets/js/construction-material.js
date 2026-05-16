/**
 * Construction — Material catalog (material_pricing via GET /api/v1/material-prices).
 */
(function () {
	"use strict";

	var catalogTable = null;
	var searchTimer = null;
	var state = { q: "", manufacturer: "", offset: 0, limit: 100, total: 0 };

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

	function fmtMoney(cell) {
		var v = cell.getValue();
		if (v == null || v === "") return "—";
		var n = Number(v);
		return isNaN(n) ? String(v) : "$" + n.toFixed(2);
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

	function catalogUrl() {
		var p = new URLSearchParams();
		p.set("limit", String(state.limit));
		p.set("offset", String(state.offset));
		if (state.q) p.set("q", state.q);
		if (state.manufacturer) p.set("manufacturer", state.manufacturer);
		return apiBase() + "/api/v1/material-prices?" + p.toString();
	}

	function fetchCatalog() {
		return fetch(catalogUrl(), { credentials: "include", headers: { Accept: "application/json" } }).then(function (res) {
			return res.json().then(function (j) {
				if (!res.ok) throw new Error(j.error || res.status);
				return j;
			});
		});
	}

	function loadManufacturers() {
		var sel = document.getElementById("usis-mat-mfg-filter");
		if (!sel) return Promise.resolve();
		return fetch(apiBase() + "/api/v1/material-prices/manufacturers?limit=300", {
			credentials: "include",
			headers: { Accept: "application/json" },
		})
			.then(function (res) {
				return res.json().then(function (j) {
					if (!res.ok) throw new Error(j.error || res.status);
					return j;
				});
			})
			.then(function (d) {
				var cur = sel.value;
				sel.innerHTML = '<option value="">All manufacturers</option>';
				(d.items || []).forEach(function (name) {
					var o = document.createElement("option");
					o.value = name;
					o.textContent = name;
					sel.appendChild(o);
				});
				if (cur) sel.value = cur;
			})
			.catch(function () {
				/* non-fatal */
			});
	}

	function refreshCatalog() {
		setStatus("Loading…");
		return fetchCatalog()
			.then(function (d) {
				state.total = d.total != null ? Number(d.total) : (d.items || []).length;
				var rows = d.items || [];
				var empty = state.total === 0 && !state.q && !state.manufacturer;
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
		catalogTable = new Tabulator(el, {
			layout: "fitColumns",
			height: "min(520px, 60vh)",
			placeholder: "No rows match your filters.",
			columns: [
				{ title: "Manufacturer", field: "manufacturer", width: 130 },
				{ title: "Item", field: "item", width: 120 },
				{ title: "Category", field: "category", width: 110 },
				{ title: "Description", field: "description", minWidth: 160, widthGrow: 2 },
				{ title: "Mounting", field: "mounting_type", width: 100 },
				{ title: "Cost", field: "cost", width: 90, hozAlign: "right", formatter: fmtMoney },
				{ title: "Labor", field: "labor_per", width: 90, hozAlign: "right", formatter: fmtMoney },
				{ title: "UOM", field: "unit_of_measure", width: 64 },
			],
		});
	}

	function scheduleSearch() {
		if (searchTimer) clearTimeout(searchTimer);
		searchTimer = setTimeout(function () {
			state.offset = 0;
			refreshCatalog();
		}, 300);
	}

	function wireUi() {
		var search = document.getElementById("usis-mat-search");
		var mfg = document.getElementById("usis-mat-mfg-filter");
		var refreshBtn = document.getElementById("usis-mat-refresh");
		var prev = document.getElementById("usis-mat-prev");
		var next = document.getElementById("usis-mat-next");

		if (search) {
			search.addEventListener("input", function () {
				state.q = (search.value || "").trim();
				scheduleSearch();
			});
		}
		if (mfg) {
			mfg.addEventListener("change", function () {
				state.manufacturer = mfg.value || "";
				state.offset = 0;
				refreshCatalog();
			});
		}
		if (refreshBtn) refreshBtn.addEventListener("click", function () {
			loadManufacturers().then(refreshCatalog);
		});
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
	}

	function init() {
		if (!document.getElementById("usis-mat-tabulator")) return;
		buildTable();
		wireUi();
		loadManufacturers().then(refreshCatalog);
	}

	if (document.readyState === "loading") {
		document.addEventListener("DOMContentLoaded", init);
	} else {
		init();
	}
})();
