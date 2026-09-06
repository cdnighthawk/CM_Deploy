/**
 * Estimate board — Lead / Estimate / Submitted / GS Plan.
 * GET /api/v1/lead-estimates?submission_state=undecided|will_submit|submitted
 * Tab switches update the query only (pushState); no full page reload.
 * GS Plan navigates to the Golden State planroom page.
 */
(function () {
	"use strict";

	var API = typeof window.usisApiBase === "function" ? window.usisApiBase() : "";
	var tbody = document.getElementById("usis-estimate-tbody");
	var filterInput = document.getElementById("usis-est-table-filter");
	var filterCount = document.getElementById("usis-est-filter-count");
	var bulkBar = document.getElementById("usis-est-bulk-bar");
	var COLSPAN = 7;

	var allItems = [];
	var isFetching = false;
	var loadError = null;
	var autoFilter = null;
	var parkedMenu = null;
	var parkedMenuParent = null;
	var fetchGen = 0;
	var tabCountsPrefetched = false;

	var EMPTY = {
		lead:
			'<tr><td colspan="' +
			COLSPAN +
			'" class="text-muted">No matching leads (undecided, not archived, still due). Click <strong>Reload from API</strong> or check the Flask log.</td></tr>',
		will_submit:
			'<tr><td colspan="' +
			COLSPAN +
			'" class="text-muted">No matching <code>lead_estimates</code> (will submit a bid, not yet submitted, not archived). Click <strong>Reload from API</strong> or check the Flask log.</td></tr>',
		submitted:
			'<tr><td colspan="' +
			COLSPAN +
			'" class="text-muted">No submitted estimates yet. Bids marked submitted in BuildingConnected will appear here.</td></tr>',
	};

	function boardFromSearch(search) {
		var tab = "";
		try {
			tab = new URLSearchParams(search || window.location.search).get("tab") || "";
		} catch (e) {
			tab = "";
		}
		tab = String(tab).toLowerCase();
		if (tab === "submitted") return "submitted";
		if (tab === "lead" || tab === "leads" || tab === "undecided") return "lead";
		if (tab === "gs_plan" || tab === "gs-plan" || tab === "gsplan") return "gs_plan";
		return "will_submit";
	}

	function currentBoard() {
		return boardFromSearch(window.location.search);
	}

	function submissionStateFor(board) {
		if (board === "submitted") return "submitted";
		if (board === "lead") return "undecided";
		return "will_submit";
	}

	function urlForBoard(board) {
		var path = window.location.pathname;
		if (board === "submitted") return path + "?tab=submitted";
		if (board === "lead") return path + "?tab=lead";
		if (board === "gs_plan") {
			return path.replace(/estimate\.html$/i, "lead-goldenstate-planroom.html");
		}
		return path;
	}

	function isGsPlanHref(href) {
		return !!(href && /lead-goldenstate-planroom\.html/i.test(href));
	}

	function boardFromHref(href) {
		if (!href) return null;
		if (isGsPlanHref(href)) return "gs_plan";
		if (!/estimate\.html/i.test(href)) return null;
		if (/[?&]tab=submitted\b/i.test(href)) return "submitted";
		if (/[?&]tab=lead\b/i.test(href) || /[?&]tab=leads\b/i.test(href)) return "lead";
		if (/[?&]tab=gs[_-]?plan\b/i.test(href)) return "gs_plan";
		return "will_submit";
	}

	function emptyMessage() {
		return EMPTY[currentBoard()] || EMPTY.will_submit;
	}

	function pageTitleFor(board) {
		if (board === "submitted") return "Construction — Submitted";
		if (board === "lead") return "Construction — Lead";
		if (board === "gs_plan") return "Construction — GS Plan";
		return "Construction — Estimate";
	}

	function markEstimateNavActive() {
		document.querySelectorAll('.deznav .metismenu > li > a[href*="estimate.html"]').forEach(function (a) {
			var li = a.closest("li");
			if (li) {
				li.classList.add("mm-active", "active-no-child");
			}
			a.classList.add("mm-active");
		});
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

	function locationLine(row) {
		return [row.city, row.state, row.zip || row.postal_code || row.site_zip]
			.filter(function (p) {
				return p != null && String(p).trim() !== "";
			})
			.join(", ");
	}

	function formatDueDate(iso) {
		if (!iso) return '<span class="text-muted">—</span>';
		try {
			var d = new Date(iso);
			if (isNaN(d.getTime())) return esc(String(iso));
			var datePart = d.toLocaleDateString(undefined, {
				month: "short",
				day: "numeric",
				year: "numeric",
			});
			if (d.getHours() === 0 && d.getMinutes() === 0 && d.getSeconds() === 0) {
				return '<span class="usis-est-due">' + esc(datePart) + "</span>";
			}
			var timePart = d.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
			return '<span class="usis-est-due">' + esc(datePart + ", " + timePart) + "</span>";
		} catch (e) {
			return esc(String(iso));
		}
	}

	function rowKind(row) {
		if (row && row.is_parent === true) return "GROUP";
		if (currentBoard() === "lead") return "LEAD";
		return "ESTIMATE";
	}

	function setTabCount(board, n) {
		var el = document.querySelector('[data-usis-est-count="' + board + '"]');
		if (!el) return;
		if (n == null || n === "") {
			el.textContent = "";
			return;
		}
		el.textContent = String(n);
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
		var titleHref = currentBoard() === "lead" && jobHref ? jobHref : detailHref;
		var numInner = lidEnc
			? '<a class="text-decoration-none" href="' + titleHref + '">' + num + "</a>"
			: num;
		var titleInner = lidEnc
			? '<a class="usis-est-name__title" href="' + titleHref + '">' + esc(name || "—") + "</a>"
			: '<span class="usis-est-name__title">' + esc(name || "—") + "</span>";
		var nameCell =
			'<div class="usis-est-name">' +
			'<div class="usis-est-name__kind">' +
			esc(rowKind(row)) +
			"</div>" +
			titleInner +
			(trade ? '<div class="usis-est-name__trade">' + esc(trade) + "</div>" : "") +
			"</div>";
		var company = row.company_name || "";
		var clientCell = company
			? '<span class="usis-est-client"><i class="fa fa-building" aria-hidden="true"></i><span>' +
				esc(company) +
				"</span></span>"
			: '<span class="text-muted">—</span>';
		var loc = locationLine(row);
		var locCell = loc ? '<span class="usis-est-location">' + esc(loc) + "</span>" : '<span class="text-muted">—</span>';
		var jobBtn = jobHref
			? '<a class="btn btn-square btn-sm btn-outline-primary rounded" href="' +
				jobHref +
				'" title="Building Connected job info"><i class="fa fa-briefcase"></i></a>'
			: "";
		var actions =
			'<div class="d-inline-flex align-items-center gap-1 justify-content-end">' +
			jobBtn +
			'<div class="dropdown custom-dropdown mb-0 tbl-orders-style">' +
			'<div class="btn btn-square btn-sm rounded" data-bs-toggle="dropdown" data-bs-boundary="viewport" data-bs-popper-config=\'{"strategy":"fixed"}\'><i class="fa-solid fa-ellipsis-vertical"></i></div>' +
			'<div class="dropdown-menu dropdown-menu-end">' +
			(jobHref ? '<a class="dropdown-item" href="' + jobHref + '">Job info (BC)</a>' : "") +
			'<a class="dropdown-item" href="' +
			(lidEnc ? detailHref : "javascript:void(0);") +
			'">Takeoff / estimate</a>' +
			(lidEnc
				? '<button type="button" class="dropdown-item usis-est-row-create" data-lead-id="' +
					esc(String(row.id || row.external_id || "")) +
					'">New estimate</button>'
				: "") +
			(window.USISAdminDelete && window.USISAdminDelete.menuItemHtml
				? window.USISAdminDelete.menuItemHtml(
						row.id,
						"/api/v1/lead-estimates/" + encodeURIComponent(row.id),
						{ label: "this estimate" }
					)
				: "") +
			'<span class="dropdown-item-text small text-muted">id: ' +
			esc(row.external_id || row.id) +
			"</span>" +
			"</div></div></div>";
		var bulk =
			window.USISListBulk && window.USISListBulk.checkboxHtml
				? window.USISListBulk.checkboxHtml(row.id)
				: '<td class="usis-bulk-col"></td>';
		return (
			'<tr data-id="' +
			escAttr(row.id) +
			'">' +
			bulk +
			'<td class="usis-est-col-name">' +
			nameCell +
			"</td>" +
			'<td class="text-nowrap">' +
			numInner +
			"</td>" +
			"<td>" +
			formatDueDate(row.due_at) +
			"</td>" +
			"<td>" +
			clientCell +
			"</td>" +
			"<td>" +
			locCell +
			"</td>" +
			'<td class="text-end">' +
			actions +
			"</td>" +
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
			row.zip,
			row.due_at,
			row.external_id,
			row.id,
		]
			.filter(Boolean)
			.join(" ")
			.toLowerCase();
	}

	function restoreParkedMenu() {
		if (!parkedMenu) return;
		if (parkedMenuParent && parkedMenuParent.isConnected) {
			parkedMenuParent.appendChild(parkedMenu);
		} else if (parkedMenu.parentNode) {
			parkedMenu.parentNode.removeChild(parkedMenu);
		}
		parkedMenu = null;
		parkedMenuParent = null;
	}

	function parkDropdownMenu(toggle) {
		var wrap = toggle.closest(".dropdown");
		var menu = wrap ? wrap.querySelector(".dropdown-menu") : null;
		if (!menu) return;
		restoreParkedMenu();
		parkedMenu = menu;
		parkedMenuParent = menu.parentNode;
		document.body.appendChild(menu);
	}

	function applyTableFilter() {
		restoreParkedMenu();
		if (!tbody || isFetching) return;
		var q = filterInput && filterInput.value ? String(filterInput.value).trim().toLowerCase() : "";
		if (!allItems.length && !q && loadError) return;
		if (!allItems.length) {
			if (filterCount) filterCount.textContent = "";
			if (q) {
				tbody.innerHTML =
					'<tr><td colspan="' +
					COLSPAN +
					'" class="text-muted">No rows match your filter. Clear the search box to see all loaded estimates (or reload if the list is empty).</td></tr>';
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
				'<tr><td colspan="' +
				COLSPAN +
				'" class="text-muted">No rows match your column filters and/or search. Clear a column filter or the search box.</td></tr>';
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
		var board = currentBoard();
		var gen = ++fetchGen;
		isFetching = true;
		loadError = null;
		allItems = [];
		if (filterCount) filterCount.textContent = "";
		if (window.USISListBulk && window.USISListBulk.clear) window.USISListBulk.clear();
		restoreParkedMenu();
		tbody.innerHTML = '<tr><td colspan="' + COLSPAN + '" class="text-muted">Loading…</td></tr>';
		var state = submissionStateFor(board);
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
				if (gen !== fetchGen) return;
				var items = (data.items || []).filter(keepBoardRow);
				allItems = items;
				window.__USIS_ESTIMATE_LEADS = items;
				isFetching = false;
				loadError = null;
				setTabCount(board, data.total != null ? data.total : items.length);
				if (!items.length) {
					tbody.innerHTML = emptyMessage();
					if (filterCount) filterCount.textContent = "";
				} else {
					applyTableFilter();
				}
			})
			.catch(function (err) {
				if (gen !== fetchGen) return;
				allItems = [];
				isFetching = false;
				loadError = err.message;
				tbody.innerHTML =
					'<tr><td colspan="' +
					COLSPAN +
					'" class="text-danger">Could not load estimates: ' +
					esc(err.message) +
					".</td></tr>";
			});
	}

	function prefetchOtherCounts() {
		["lead", "will_submit", "submitted"].forEach(function (board) {
			if (board === currentBoard()) return;
			fetch(
				API.replace(/\/$/, "") +
					"/api/v1/lead-estimates?limit=1&submission_state=" +
					encodeURIComponent(submissionStateFor(board)),
				{ credentials: "include", headers: { Accept: "application/json" } }
			)
				.then(function (r) {
					if (!r.ok) throw new Error("HTTP " + r.status);
					return r.json();
				})
				.then(function (data) {
					if (data && data.total != null) setTabCount(board, data.total);
				})
				.catch(function () {});
		});
		fetch(API.replace(/\/$/, "") + "/api/v1/golden-state-planroom/leads?limit=1", {
			credentials: "include",
			headers: { Accept: "application/json" },
		})
			.then(function (r) {
				if (!r.ok) throw new Error("HTTP " + r.status);
				return r.json();
			})
			.then(function (data) {
				if (data && data.total != null) setTabCount("gs_plan", data.total);
			})
			.catch(function () {});
		tabCountsPrefetched = true;
	}

	function syncChrome() {
		var board = currentBoard();
		document.querySelectorAll("[data-usis-est-tab]").forEach(function (el) {
			var on = el.getAttribute("data-usis-est-tab") === board;
			el.classList.toggle("active", on);
			el.setAttribute("aria-selected", on ? "true" : "false");
		});
		var title = document.getElementById("usis-est-page-title");
		if (title) {
			var label = pageTitleFor(board);
			title.textContent = label;
			title.setAttribute("data-i18n", label);
		}
		if (bulkBar && board === "submitted") {
			bulkBar.classList.add("d-none");
		}
		markEstimateNavActive();
	}

	function switchBoard(board, replace) {
		if (!board) return;
		if (board === currentBoard()) return;
		var url = urlForBoard(board);
		try {
			if (replace) {
				history.replaceState({ usisEstBoard: board }, "", url);
			} else {
				history.pushState({ usisEstBoard: board }, "", url);
			}
		} catch (e) {}
		syncChrome();
		loadEstimates();
	}

	function bindAutoFilter() {
		if (!window.USIS_TABLE_AUTOFILTER) return null;
		return window.USIS_TABLE_AUTOFILTER.bind({
			table: "#usis-estimate-table",
			tableId: "estimating.board",
			defaultSort: { key: "due_at", dir: currentBoard() === "submitted" ? "desc" : "asc" },
			getRows: function () {
				return allItems;
			},
			resetButton: "#usis-est-reset-view",
			mobileButton: "#usis-est-sort-filter",
			columns: [
				{ key: "name", label: "Name", type: "text", sortable: true, filterable: true },
				{ key: "number", label: "Number", type: "text", sortable: true, filterable: true },
				{ key: "due_at", label: "Due date", type: "date", sortable: true, filterable: true },
				{ key: "company_name", label: "Client", type: "text", sortable: true, filterable: true },
				{
					key: "location",
					label: "Location",
					type: "text",
					sortable: true,
					filterable: true,
					getValue: function (row) {
						return locationLine(row);
					},
				},
			],
			onChange: function () {
				applyTableFilter();
			},
		});
	}

	function isModifiedClick(e) {
		return !!(e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button === 1);
	}

	if (!tbody) return;

	if (currentBoard() === "gs_plan") {
		window.location.replace(urlForBoard("gs_plan"));
		return;
	}

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
			prefetchOtherCounts();
		});
	} else {
		loadEstimates();
		prefetchOtherCounts();
	}

	var btn = document.getElementById("usis-estimate-sync-stub");
	if (btn) {
		btn.addEventListener("click", function () {
			tabCountsPrefetched = false;
			loadEstimates();
			prefetchOtherCounts();
		});
	}
	window.addEventListener("usis:admin-deleted", function () {
		tabCountsPrefetched = false;
		loadEstimates();
		prefetchOtherCounts();
	});
	window.usisBcPullOnDone = function () {
		tabCountsPrefetched = false;
		loadEstimates();
		prefetchOtherCounts();
	};
	var pullBtn = document.getElementById("usis-est-bc-pull");
	if (pullBtn) {
		pullBtn.addEventListener("click", function () {
			if (typeof window.usisPullBuildingConnected === "function") {
				window.usisPullBuildingConnected({
					button: pullBtn,
					onDone: window.usisBcPullOnDone,
				});
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

	var addEst = document.getElementById("usis-est-add-estimate");
	if (addEst) {
		addEst.addEventListener("click", function () {
			if (!window.USISEstimateCreate) return;
			window.USISEstimateCreate.open(null, { leadOptions: window.__USIS_ESTIMATE_LEADS || allItems || [] });
		});
	}
	tbody.addEventListener("show.bs.dropdown", function (e) {
		var toggle = e.target.closest('[data-bs-toggle="dropdown"]');
		if (toggle) parkDropdownMenu(toggle);
	});
	tbody.addEventListener("hidden.bs.dropdown", restoreParkedMenu);

	document.addEventListener("click", function (e) {
		var createBtn = e.target.closest(".usis-est-row-create");
		if (createBtn) {
			e.preventDefault();
			if (!window.USISEstimateCreate) return;
			window.USISEstimateCreate.open(createBtn.getAttribute("data-lead-id"), {
				leadOptions: window.__USIS_ESTIMATE_LEADS || allItems || [],
			});
			return;
		}
		if (isModifiedClick(e)) return;
		var tabLink = e.target.closest("[data-usis-est-tab]");
		if (tabLink) {
			var tab = tabLink.getAttribute("data-usis-est-tab");
			if (tab === "gs_plan") return;
			e.preventDefault();
			switchBoard(tab);
			return;
		}
		var navLink = e.target.closest('a[href*="estimate.html"]');
		if (!navLink) return;
		if (navLink.closest("[data-usis-est-tab]")) return;
		var board = navLink.closest(".deznav")
			? "will_submit"
			: boardFromHref(navLink.getAttribute("href") || "");
		if (!board || board === "gs_plan") return;
		e.preventDefault();
		switchBoard(board);
	});

	window.addEventListener("popstate", function () {
		syncChrome();
		loadEstimates();
	});
})();
