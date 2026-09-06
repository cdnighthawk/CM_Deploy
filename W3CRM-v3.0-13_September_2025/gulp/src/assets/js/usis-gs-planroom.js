/**
 * Golden State / AGC San Diego weekly planroom lead list + HTML/CSV import.
 */
(function () {
	var API = typeof window.usisApiBase === "function" ? window.usisApiBase() : "";
	var tbody = document.getElementById("usis-gs-leads-tbody");
	var filterInput = document.getElementById("usis-gs-table-filter");
	var filterCount = document.getElementById("usis-gs-filter-count");
	var locationSel = document.getElementById("usis-gs-location");
	var newOnly = document.getElementById("usis-gs-new-only");
	var strongOnly = document.getElementById("usis-gs-strong-only");
	var importInput = document.getElementById("usis-gs-import-file");
	var importBtn = document.getElementById("usis-gs-import-btn");
	var reloadBtn = document.getElementById("usis-gs-reload");
	var allItems = [];
	var isFetching = false;
	var loadError = null;
	var autoFilter = null;

	function setTabCount(board, n) {
		var el = document.querySelector('[data-usis-est-count="' + board + '"]');
		if (!el) return;
		if (n == null || n === "") {
			el.textContent = "";
			return;
		}
		el.textContent = String(n);
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

	function syncEstimateTabs() {
		document.querySelectorAll("[data-usis-est-tab]").forEach(function (el) {
			var on = el.getAttribute("data-usis-est-tab") === "gs_plan";
			el.classList.toggle("active", on);
			el.setAttribute("aria-selected", on ? "true" : "false");
		});
		markEstimateNavActive();
	}

	function prefetchBoardCounts() {
		var api = (API || "").replace(/\/$/, "");
		[
			{ board: "lead", state: "undecided" },
			{ board: "will_submit", state: "will_submit" },
			{ board: "submitted", state: "submitted" },
		].forEach(function (row) {
			fetch(api + "/api/v1/lead-estimates?limit=1&submission_state=" + encodeURIComponent(row.state), {
				credentials: "include",
				headers: { Accept: "application/json" },
			})
				.then(function (r) {
					if (!r.ok) throw new Error("HTTP " + r.status);
					return r.json();
				})
				.then(function (data) {
					if (data && data.total != null) setTabCount(row.board, data.total);
				})
				.catch(function () {});
		});
	}

	function esc(s) {
		return String(s == null ? "" : s)
			.replace(/&/g, "&amp;")
			.replace(/</g, "&lt;")
			.replace(/>/g, "&gt;")
			.replace(/"/g, "&quot;");
	}

	function formatMoney(raw) {
		if (raw == null || raw === "") return '<span class="text-muted">—</span>';
		var n = Number(raw);
		if (isNaN(n)) return esc(String(raw));
		return esc(n.toLocaleString(undefined, { style: "currency", currency: "USD", maximumFractionDigits: 0 }));
	}

	function formatDistanceMiles(raw) {
		if (raw == null || raw === "") return '<span class="text-muted">—</span>';
		var n = Number(raw);
		if (isNaN(n)) return '<span class="text-muted">—</span>';
		if (n < 1) return "&lt;1 mi";
		if (n < 10) return esc(n.toFixed(1) + " mi");
		return esc(String(Math.round(n)) + " mi");
	}

	function formatDate(iso) {
		if (!iso) return '<span class="text-muted">—</span>';
		var parts = String(iso).slice(0, 10).split("-");
		if (parts.length !== 3) return esc(iso);
		return esc(parts[1] + "/" + parts[2] + "/" + parts[0]);
	}

	function fitLabel(row) {
		var band = (row.fit || {}).band || "weak";
		if (band === "strong") return "Strong";
		if (band === "possible") return "Possible";
		return "Low";
	}

	function flagLabel(row) {
		var parts = [];
		if (row.is_new) parts.push("NEW");
		if (row.bid_date_changed) parts.push("Date change");
		return parts.join(" · ");
	}

	function estimateValue(row) {
		if (row.estimate_high == null || row.estimate_high === "") return "";
		var n = Number(row.estimate_high);
		return isNaN(n) ? "" : n;
	}

	function projectNameCell(row) {
		var name = esc(row.name || "—");
		var url = row.project_url ? String(row.project_url) : "";
		var linked = name;
		if (/^https:\/\/login\.onlineplanservice\.com\//i.test(url)) {
			linked =
				'<a href="' +
				esc(url) +
				'" target="_blank" rel="noopener noreferrer">' +
				name +
				"</a>";
		}
		var detail = row.detail || {};
		var bits = [];
		if (detail.project_type) bits.push(esc(detail.project_type));
		if (detail.city && detail.city !== (row.location || "")) bits.push(esc(detail.city));
		var desc = detail.description ? String(detail.description) : "";
		if (desc.length > 180) desc = desc.slice(0, 177) + "…";
		var extra = "";
		if (bits.length) extra += '<div class="small text-muted">' + bits.join(" · ") + "</div>";
		if (desc) extra += '<div class="small text-muted">' + esc(desc) + "</div>";
		return linked + extra;
	}

	function fitCell(row) {
		var fit = row.fit || {};
		var band = fit.band || "weak";
		var score = fit.score == null ? "—" : String(fit.score);
		var label = fitLabel(row);
		var cls = band === "strong" ? "text-bg-success" : band === "possible" ? "text-bg-info" : "text-bg-secondary";
		var reasons = (fit.reasons || []).join(" · ");
		return (
			'<td class="text-nowrap">' +
			'<span class="badge ' +
			cls +
			'" title="' +
			esc(reasons) +
			'">' +
			esc(label) +
			" " +
			esc(score) +
			"</span></td>"
		);
	}

	function renderRow(row) {
		var flags = [];
		if (row.is_new) flags.push('<span class="badge text-bg-success">NEW</span>');
		if (row.bid_date_changed) flags.push('<span class="badge text-bg-warning">Date change</span>');
		var flagHtml = flags.length ? flags.join(" ") : '<span class="text-muted">—</span>';
		return (
			"<tr>" +
			fitCell(row) +
			'<td class="text-nowrap">' + flagHtml + "</td>" +
			'<td class="text-nowrap">' + formatDate(row.bid_date) + "</td>" +
			'<td class="text-nowrap">' + esc(row.bid_time || "—") + "</td>" +
			"<td>" + esc(row.location || "—") + "</td>" +
			'<td class="usis-gs-col-dist text-nowrap">' + formatDistanceMiles(row.distance_miles) + "</td>" +
			"<td>" + projectNameCell(row) + "</td>" +
			'<td class="text-nowrap text-end">' + formatMoney(row.estimate_high) + "</td>" +
			'<td class="text-end">' +
			(window.USISUi && window.USISUi.rowMenu
				? window.USISUi.rowMenu({
						id: row.plan_number || row.name,
						editHref: /^https:\/\/login\.onlineplanservice\.com\//i.test(String(row.project_url || ""))
							? String(row.project_url)
							: undefined,
						createTarget: "#usis-gs-import-btn",
					})
				: "") +
			"</td>" +
			"</tr>"
		);
	}

	function rowText(row) {
		var fit = row.fit || {};
		var detail = row.detail || {};
		return [
			row.plan_number,
			row.name,
			row.location,
			row.distance_miles,
			row.bid_date,
			row.bid_time,
			row.estimate_high,
			row.addenda_count,
			fit.building,
			fit.band,
			fitLabel(row),
			flagLabel(row),
			detail.project_type,
			detail.city,
			detail.description,
		]
			.filter(Boolean)
			.join(" ")
			.toLowerCase();
	}

	function applyLocalFilter() {
		if (!tbody || isFetching) return;
		var q = filterInput && filterInput.value ? String(filterInput.value).trim().toLowerCase() : "";
		if (!allItems.length && !q && loadError) return;
		if (!allItems.length) {
			if (filterCount) filterCount.textContent = "";
			if (q) {
				tbody.innerHTML =
					'<tr><td colspan="9" class="text-muted">No rows match your filter. Clear the search box to see all loaded jobs (or reload if the list is empty).</td></tr>';
			} else {
				tbody.innerHTML =
					'<tr><td colspan="9" class="text-muted">No Golden State planroom jobs match this view.</td></tr>';
			}
			if (autoFilter) autoFilter.paint();
			return;
		}
		var filtered = autoFilter ? autoFilter.filter(allItems) : allItems.slice();
		if (q) {
			filtered = filtered.filter(function (row) {
				return rowText(row).indexOf(q) !== -1;
			});
		}
		if (!filtered.length) {
			tbody.innerHTML =
				'<tr><td colspan="9" class="text-muted">No rows match your column filters and/or search. Clear a column filter or the search box.</td></tr>';
		} else {
			var rows = autoFilter ? autoFilter.sort(filtered) : filtered;
			tbody.innerHTML = rows.map(renderRow).join("");
		}
		if (autoFilter) autoFilter.paint();
		if (filterCount) {
			var labels = autoFilter ? autoFilter.getActiveLabels() : [];
			var parts = [];
			if (filtered.length !== allItems.length || labels.length || q) {
				parts.push("Showing " + filtered.length + " of " + allItems.length + " jobs");
			} else {
				parts.push(allItems.length + " jobs");
			}
			if (labels.length) parts.push("Filters on: " + labels.join(", "));
			filterCount.textContent = parts.join(" · ");
		}
	}

	function notify(kind, msg) {
		if (window.USISNotify && typeof window.USISNotify[kind] === "function") {
			window.USISNotify[kind](msg);
		}
	}

	function loadLeads() {
		if (!tbody) return;
		isFetching = true;
		loadError = null;
		tbody.innerHTML = '<tr><td colspan="9" class="text-muted">Loading…</td></tr>';
		var params = new URLSearchParams();
		params.set("limit", "2000");
		params.set("sort", "fit_score");
		if (locationSel && locationSel.value) params.set("location", locationSel.value);
		if (newOnly && newOnly.checked) params.set("new_only", "1");
		if (strongOnly && strongOnly.checked) params.set("strong_only", "1");
		var url = (API || "").replace(/\/$/, "") + "/api/v1/golden-state-planroom/leads?" + params.toString();
		fetch(url, { credentials: "include", headers: { Accept: "application/json" } })
			.then(function (r) {
				if (!r.ok) throw new Error("HTTP " + r.status);
				return r.json();
			})
			.then(function (data) {
				allItems = data.items || [];
				isFetching = false;
				loadError = null;
				if (data && data.total != null) setTabCount("gs_plan", data.total);
				else setTabCount("gs_plan", allItems.length);
				applyLocalFilter();
			})
			.catch(function (err) {
				allItems = [];
				isFetching = false;
				loadError = err.message;
				tbody.innerHTML =
					'<tr><td colspan="9" class="text-danger">Could not load planroom leads: ' +
					esc(err.message) +
					".</td></tr>";
			});
	}

	function importCsv(file) {
		if (!file) return;
		var fd = new FormData();
		fd.append("file", file, file.name);
		if (importBtn) importBtn.disabled = true;
		fetch((API || "").replace(/\/$/, "") + "/api/v1/golden-state-planroom/import", {
			method: "POST",
			credentials: "include",
			body: fd,
		})
			.then(function (r) {
				return r.json().then(function (data) {
					if (!r.ok) throw new Error(data.error || "HTTP " + r.status);
					return data;
				});
			})
			.then(function (data) {
				notify("success", "Imported " + data.loaded + " jobs from " + (data.source_file || "listing") + ".");
				loadLeads();
			})
			.catch(function (err) {
				notify("error", err.message || "Import failed");
			})
			.finally(function () {
				if (importBtn) importBtn.disabled = false;
				if (importInput) importInput.value = "";
			});
	}

	autoFilter = window.USIS_TABLE_AUTOFILTER
		? window.USIS_TABLE_AUTOFILTER.bind({
				table: "#usis-gs-leads-table",
				tableId: "crm.gs-planroom",
				defaultSort: { key: "fit", dir: "desc" },
				getRows: function () {
					return allItems;
				},
				resetButton: "#usis-gs-reset-view",
				mobileButton: "#usis-gs-sort-filter",
				columns: [
					{
						key: "fit",
						label: "Fit",
						type: "singleSelect",
						sortable: true,
						filterable: true,
						defaultDir: "desc",
						valueOptions: ["Strong", "Possible", "Low"],
						getValue: fitLabel,
					},
					{
						key: "flags",
						label: "Flags",
						type: "singleSelect",
						sortable: true,
						filterable: true,
						valueOptions: ["NEW", "Date change"],
						getValue: flagLabel,
					},
					{ key: "bid_date", label: "Bid date", type: "date", sortable: true, filterable: true },
					{ key: "bid_time", label: "Time", type: "text", sortable: true, filterable: true },
					{ key: "location", label: "Location", type: "singleSelect", sortable: true, filterable: true },
					{ key: "distance_miles", label: "Dist", type: "number", sortable: true, filterable: true },
					{ key: "name", label: "Project", type: "text", sortable: true, filterable: true },
					{
						key: "estimate_high",
						label: "Estimate high",
						type: "number",
						sortable: true,
						filterable: true,
						defaultDir: "desc",
						getValue: estimateValue,
					},
				],
				onChange: function () {
					applyLocalFilter();
				},
			})
		: null;

	if (filterInput) {
		filterInput.addEventListener("input", applyLocalFilter);
		filterInput.addEventListener("keydown", function (e) {
			if (e.key === "Enter") {
				e.preventDefault();
				applyLocalFilter();
			}
		});
	}
	if (locationSel) locationSel.addEventListener("change", loadLeads);
	if (newOnly) newOnly.addEventListener("change", loadLeads);
	if (strongOnly) strongOnly.addEventListener("change", loadLeads);
	if (reloadBtn) reloadBtn.addEventListener("click", loadLeads);
	if (importBtn && importInput) {
		importBtn.addEventListener("click", function () {
			importInput.click();
		});
		importInput.addEventListener("change", function () {
			if (importInput.files && importInput.files[0]) importCsv(importInput.files[0]);
		});
	}
	syncEstimateTabs();
	prefetchBoardCounts();
	if (document.readyState === "loading") {
		document.addEventListener("DOMContentLoaded", function () {
			syncEstimateTabs();
			loadLeads();
		});
	} else {
		loadLeads();
	}
})();
