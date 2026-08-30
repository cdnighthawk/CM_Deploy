/**
 * Estimate board — Will-bid queue and Submitted list.
 * GET /api/v1/lead-estimates?submission_state=will_submit|submitted
 */
(function () {
	"use strict";

	var API = typeof window.usisApiBase === "function" ? window.usisApiBase() : "";
	var tbody = document.getElementById("usis-estimate-tbody");
	var filterInput = document.getElementById("usis-est-table-filter");
	var filterBtn = document.getElementById("usis-est-table-filter-btn");
	var filterCount = document.getElementById("usis-est-filter-count");
	var bulkBar = document.getElementById("usis-est-bulk-bar");

	var allItems = [];
	var isFetching = false;
	var loadError = null;
	var autoFilter = null;

	var EMPTY_WILL_BID =
		'<tr><td colspan="10" class="text-muted">No matching <code>lead_estimates</code> (will submit a bid, not yet submitted, not archived). Click <strong>Reload from API</strong> or check the Flask log.</td></tr>';
	var EMPTY_SUBMITTED =
		'<tr><td colspan="10" class="text-muted">No submitted estimates yet. Bids marked submitted in BuildingConnected will appear here.</td></tr>';

	function currentBoard() {
		var tab = "";
		try {
			tab = new URLSearchParams(window.location.search).get("tab") || "";
		} catch (e) {
			tab = "";
		}
		return String(tab).toLowerCase() === "submitted" ? "submitted" : "will_submit";
	}

	function emptyMessage() {
		return currentBoard() === "submitted" ? EMPTY_SUBMITTED : EMPTY_WILL_BID;
	}

	function esc(s) {
		return String(s == null ? "" : s)
			.replace(/&/g, "&amp;")
			.replace(/</g, "&lt;")
			.replace(/>/g, "&gt;")
			.replace(/"/g, "&quot;");
	}

	function escAttr(s) {
		return String(s == null ? "" : s)
			.replace(/&/g, "&amp;")
			.replace(/"/g, "&quot;")
			.replace(/</g, "&lt;");
	}

	function formatBidDueDate(iso) {
		if (!iso) return '<span class="text-muted">—</span>';
		try {
			var d = new Date(iso);
			if (isNaN(d.getTime())) return esc(String(iso));
			return esc(d.toLocaleDateString());
		} catch (e) {
			return esc(String(iso));
		}
	}

	function renderRow(row) {
		var num = esc(row.number || "—");
		var name = row.name || "";
		var trade = row.trade_name || "";
		var lid = row.external_id != null && row.external_id !== "" ? row.external_id : row.id;
		var lidEnc = lid != null && lid !== "" ? encodeURIComponent(String(lid)) : "";
		var estimateId = row.current_estimate_id || row.primary_estimate_id || "";
		var detailHref = estimateId
			? "construction/estimate-detail.html?id=" + encodeURIComponent(estimateId)
			: lidEnc
				? "construction/estimate-detail.html?id=" + lidEnc
				: "javascript:void(0);";
		var jobHref = lidEnc ? "construction/lead-detail.html?id=" + lidEnc : "";
		var numInner = lidEnc
			? '<a class="link-primary text-decoration-none" href="' + detailHref + '">' + num + "</a>"
			: num;
		var leadCell = lidEnc
			? '<a class="fw-semibold text-black text-decoration-none" href="' + detailHref + '">' + esc(name || "—") + "</a>"
			: '<span class="fw-semibold text-black">' + esc(name) + "</span>";
		var tradeCell = trade
			? '<span class="text-muted">' + esc(trade) + "</span>"
			: '<span class="text-muted">—</span>';
		var company = esc(row.company_name || "—");
		var city = esc(row.city || "—");
		var state = esc(row.state || "—");
		var bidDue = formatBidDueDate(row.due_at);
		var jobBtn = jobHref
			? '<a class="btn btn-square btn-sm btn-outline-primary rounded" href="' +
				jobHref +
				'" title="Building Connected job info"><i class="fa fa-briefcase"></i></a>'
			: "";
		var actions =
			'<div class="d-inline-flex align-items-center gap-1 justify-content-end">' +
			jobBtn +
			'<div class="dropdown custom-dropdown mb-0 tbl-orders-style">' +
			'<div class="btn btn-square btn-sm rounded" data-bs-toggle="dropdown"><i class="fa-solid fa-ellipsis-vertical"></i></div>' +
			'<div class="dropdown-menu dropdown-menu-end">' +
			(jobHref
				? '<a class="dropdown-item" href="' + jobHref + '">Job info (BC)</a>'
				: "") +
			'<a class="dropdown-item" href="' + (lidEnc ? detailHref : "javascript:void(0);") + '">Takeoff / estimate</a>' +
			(lidEnc
				? '<button type="button" class="dropdown-item usis-est-row-create" data-lead-id="' +
					esc(String(row.id || row.external_id || "")) +
					'">New estimate</button>'
				: "") +
			'<span class="dropdown-item-text small text-muted">id: ' + esc(row.external_id || row.id) + "</span>" +
			"</div></div></div>";
		var bulk = window.USISListBulk && window.USISListBulk.checkboxHtml
			? window.USISListBulk.checkboxHtml(row.id)
			: '<td class="usis-bulk-col"></td>';
		return (
			'<tr data-id="' + escAttr(row.id) + '">' +
			bulk +
			'<td class="text-nowrap">' + numInner + "</td>" +
			"<td class=\"usis-est-col-lead\">" + leadCell + "</td>" +
			"<td class=\"usis-est-col-trade\">" + tradeCell + "</td>" +
			'<td class="usis-est-col-company" title="' + company + '">' + company + "</td>" +
			'<td class="usis-est-col-city" title="' + city + '">' + city + "</td>" +
			'<td class="text-nowrap">' + state + "</td>" +
			'<td class="text-nowrap">' + bidDue + "</td>" +
			'<td class="text-center">—</td>' +
			'<td class="text-end">' + actions + "</td>" +
			"</tr>"
		);
	}

	function rowFilterText(row) {
		return [
			row.number,
			row.name,
			row.trade_name,
			row.company_name,
			row.city,
			row.state,
			row.due_at,
			row.external_id,
			row.id,
		]
			.filter(Boolean)
			.join(" ")
			.toLowerCase();
	}

	function applyTableFilter() {
		if (!tbody || isFetching) return;
		var q = filterInput && filterInput.value ? String(filterInput.value).trim().toLowerCase() : "";
		if (!allItems.length && !q && loadError) return;
		if (!allItems.length) {
			if (filterCount) filterCount.textContent = "";
			if (q) {
				tbody.innerHTML =
					'<tr><td colspan="10" class="text-muted">No rows match your filter. Clear the search box to see all loaded estimates (or reload if the list is empty).</td></tr>';
			} else {
				tbody.innerHTML = emptyMessage();
			}
			if (autoFilter) autoFilter.paint();
			return;
		}
		var filtered = autoFilter ? autoFilter.filter(allItems) : allItems.slice();
		if (q) {
			filtered = filtered.filter(function (row) {
				return rowFilterText(row).indexOf(q) !== -1;
			});
		}
		if (!filtered.length) {
			tbody.innerHTML =
				'<tr><td colspan="10" class="text-muted">No rows match your column filters and/or search. Clear a column filter or the search box.</td></tr>';
		} else {
			var rows = autoFilter ? autoFilter.sort(filtered) : filtered;
			tbody.innerHTML = rows.map(renderRow).join("");
			if (window.USISListBulk && window.USISListBulk.afterRender) window.USISListBulk.afterRender();
		}
		if (autoFilter) autoFilter.paint();
		if (currentBoard() === "submitted" && bulkBar) bulkBar.classList.add("d-none");
		if (filterCount) {
			var labels = autoFilter ? autoFilter.getActiveLabels() : [];
			var parts = [];
			if (filtered.length !== allItems.length || labels.length || q) {
				parts.push("Showing " + filtered.length + " of " + allItems.length);
			} else {
				parts.push(allItems.length + " loaded");
			}
			if (labels.length) parts.push("Filters on: " + labels.join(", "));
			filterCount.textContent = parts.join(" · ");
		}
	}

	function keepBoardRow(x) {
		var b = String((x && x.workflow_bucket) || "").toUpperCase();
		if (b.indexOf("CHILD") >= 0) return false;
		if (x && x.is_parent === false && x.external_parent_id) return false;
		if (currentBoard() === "submitted") return true;
		if (!x.due_at || isNaN(new Date(x.due_at).getTime()) || new Date(x.due_at).getTime() < Date.now()) {
			return false;
		}
		return true;
	}

	function loadEstimates() {
		if (!tbody) return;
		isFetching = true;
		loadError = null;
		allItems = [];
		if (filterCount) filterCount.textContent = "";
		if (window.USISListBulk && window.USISListBulk.clear) window.USISListBulk.clear();
		tbody.innerHTML = '<tr><td colspan="10" class="text-muted">Loading…</td></tr>';
		var state = currentBoard() === "submitted" ? "submitted" : "will_submit";
		fetch(
			API.replace(/\/$/, "") +
				"/api/v1/lead-estimates?limit=500&submission_state=" +
				encodeURIComponent(state),
			{ credentials: "include", headers: { Accept: "application/json" } }
		)
			.then(function (r) {
				if (!r.ok) throw new Error("HTTP " + r.status);
				return r.json();
			})
			.then(function (data) {
				var items = (data.items || []).filter(keepBoardRow);
				allItems = items;
				window.__USIS_ESTIMATE_LEADS = items;
				isFetching = false;
				loadError = null;
				if (!items.length) {
					tbody.innerHTML = emptyMessage();
				} else {
					applyTableFilter();
				}
			})
			.catch(function (err) {
				allItems = [];
				isFetching = false;
				loadError = err.message;
				tbody.innerHTML =
					'<tr><td colspan="10" class="text-danger">Could not load estimates: ' +
					esc(err.message) +
					".</td></tr>";
			});
	}

	function syncChrome() {
		var submitted = currentBoard() === "submitted";
		document.querySelectorAll("[data-usis-est-tab]").forEach(function (el) {
			var on = el.getAttribute("data-usis-est-tab") === (submitted ? "submitted" : "will_submit");
			el.classList.toggle("active", on);
			el.setAttribute("aria-selected", on ? "true" : "false");
		});
		var title = document.getElementById("usis-est-page-title");
		if (title) {
			var label = submitted ? "Construction — Submitted" : "Construction — Estimate";
			title.textContent = label;
			title.setAttribute("data-i18n", label);
		}
		if (bulkBar) {
			if (submitted) bulkBar.classList.add("d-none");
		}
		document.querySelectorAll('.deznav a[href*="estimate.html"]').forEach(function (a) {
			var href = a.getAttribute("href") || "";
			var isSubmittedLink = /[?&]tab=submitted\b/i.test(href);
			var on = submitted ? isSubmittedLink : !isSubmittedLink && /estimate\.html/i.test(href);
			var li = a.closest("li");
			if (li) li.classList.toggle("mm-active", on);
			a.classList.toggle("mm-active", on);
		});
	}

	function bindAutoFilter() {
		if (!window.USIS_TABLE_AUTOFILTER) return null;
		var submitted = currentBoard() === "submitted";
		return window.USIS_TABLE_AUTOFILTER.bind({
			table: "#usis-estimate-table",
			tableId: submitted ? "estimating.submitted" : "estimating.list",
			defaultSort: { key: "due_at", dir: submitted ? "desc" : "asc" },
			getRows: function () {
				return allItems;
			},
			resetButton: "#usis-est-reset-view",
			mobileButton: "#usis-est-sort-filter",
			columns: [
				{ key: "number", label: "Project #", type: "text", sortable: true, filterable: true },
				{ key: "name", label: "Lead", type: "text", sortable: true, filterable: true },
				{ key: "trade_name", label: "Trade invited", type: "singleSelect", sortable: true, filterable: true },
				{ key: "company_name", label: "Company", type: "text", sortable: true, filterable: true },
				{ key: "city", label: "City", type: "text", sortable: true, filterable: true },
				{ key: "state", label: "State", type: "singleSelect", sortable: true, filterable: true },
				{ key: "due_at", label: "Bid due date", type: "date", sortable: true, filterable: true },
				{
					key: "estimator",
					label: "Estimator",
					type: "singleSelect",
					sortable: true,
					filterable: true,
					getValue: function (row) {
						return row.estimator_name || row.estimator || "";
					},
				},
			],
			onChange: function () {
				applyTableFilter();
			},
		});
	}

	if (!tbody) return;

	autoFilter = bindAutoFilter();

	if (window.USISListBulk) {
		window.USISListBulk.attach({
			tbodyId: "usis-estimate-tbody",
			checkAllId: "usis-est-check-all",
			barId: "usis-est-bulk-bar",
			countId: "usis-est-bulk-count",
			clearId: "usis-est-bulk-clear",
		});
	}

	syncChrome();
	if (document.readyState === "loading") {
		document.addEventListener("DOMContentLoaded", function () {
			syncChrome();
			loadEstimates();
		});
	} else {
		loadEstimates();
	}

	var btn = document.getElementById("usis-estimate-sync-stub");
	if (btn) btn.addEventListener("click", loadEstimates);
	window.usisBcPullOnDone = loadEstimates;
	var pullBtn = document.getElementById("usis-est-bc-pull");
	if (pullBtn) {
		pullBtn.addEventListener("click", function () {
			if (typeof window.usisPullBuildingConnected === "function") {
				window.usisPullBuildingConnected({ button: pullBtn, onDone: loadEstimates });
			}
		});
	}
	if (filterInput) {
		filterInput.addEventListener("input", applyTableFilter);
		filterInput.addEventListener("keydown", function (e) {
			if (e.key === "Enter") {
				e.preventDefault();
				applyTableFilter();
			}
		});
	}
	if (filterBtn) filterBtn.addEventListener("click", applyTableFilter);

	var addEst = document.getElementById("usis-est-add-estimate");
	if (addEst) {
		addEst.addEventListener("click", function () {
			if (!window.USISEstimateCreate) return;
			window.USISEstimateCreate.open(null, { leadOptions: window.__USIS_ESTIMATE_LEADS || allItems || [] });
		});
	}
	tbody.addEventListener("click", function (e) {
		var createBtn = e.target.closest(".usis-est-row-create");
		if (!createBtn) return;
		e.preventDefault();
		if (!window.USISEstimateCreate) return;
		window.USISEstimateCreate.open(createBtn.getAttribute("data-lead-id"), {
			leadOptions: window.__USIS_ESTIMATE_LEADS || allItems || [],
		});
	});
})();
