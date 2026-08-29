/**
 * Golden State / AGC San Diego weekly planroom lead list + HTML/CSV import.
 */
(function () {
	var API = typeof window.usisApiBase === "function" ? window.usisApiBase() : "";
	var tbody = document.getElementById("usis-gs-leads-tbody");
	var filterInput = document.getElementById("usis-gs-table-filter");
	var filterCount = document.getElementById("usis-gs-filter-count");
	var locationSel = document.getElementById("usis-gs-location");
	var sortSel = document.getElementById("usis-gs-sort");
	var newOnly = document.getElementById("usis-gs-new-only");
	var strongOnly = document.getElementById("usis-gs-strong-only");
	var importInput = document.getElementById("usis-gs-import-file");
	var importBtn = document.getElementById("usis-gs-import-btn");
	var reloadBtn = document.getElementById("usis-gs-reload");
	var allItems = [];
	var isFetching = false;

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

	function formatDate(iso) {
		if (!iso) return '<span class="text-muted">—</span>';
		var parts = String(iso).slice(0, 10).split("-");
		if (parts.length !== 3) return esc(iso);
		return esc(parts[1] + "/" + parts[2] + "/" + parts[0]);
	}

	function projectNameCell(row) {
		var name = esc(row.name || "—");
		var url = row.project_url ? String(row.project_url) : "";
		if (/^https:\/\/login\.onlineplanservice\.com\//i.test(url)) {
			return (
				'<a href="' +
				esc(url) +
				'" target="_blank" rel="noopener noreferrer">' +
				name +
				"</a>"
			);
		}
		return name;
	}

	function fitCell(row) {
		var fit = row.fit || {};
		var band = fit.band || "weak";
		var score = fit.score == null ? "—" : String(fit.score);
		var label = band === "strong" ? "Strong" : band === "possible" ? "Possible" : "Low";
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
		var plan = esc(row.plan_number || "—");
		var flags = [];
		if (row.is_new) flags.push('<span class="badge text-bg-success">NEW</span>');
		if (row.bid_date_changed) flags.push('<span class="badge text-bg-warning">Date change</span>');
		var flagHtml = flags.length ? flags.join(" ") : '<span class="text-muted">—</span>';
		var addenda = row.addenda_count ? esc(String(row.addenda_count)) : "0";
		return (
			"<tr>" +
			fitCell(row) +
			'<td class="text-nowrap">' + flagHtml + "</td>" +
			'<td class="text-nowrap">' + formatDate(row.bid_date) + "</td>" +
			'<td class="text-nowrap">' + esc(row.bid_time || "—") + "</td>" +
			"<td>" + esc(row.location || "—") + "</td>" +
			'<td class="text-nowrap text-end">' + addenda + "</td>" +
			'<td class="text-nowrap"><span class="fw-semibold">' + plan + "</span></td>" +
			"<td>" + projectNameCell(row) + "</td>" +
			'<td class="text-nowrap text-end">' + formatMoney(row.estimate_high) + "</td>" +
			"</tr>"
		);
	}

	function rowText(row) {
		var fit = row.fit || {};
		return [row.plan_number, row.name, row.location, row.bid_date, row.bid_time, fit.building, fit.band]
			.filter(Boolean)
			.join(" ")
			.toLowerCase();
	}

	function applyLocalFilter() {
		if (!tbody || isFetching) return;
		var q = filterInput && filterInput.value ? String(filterInput.value).trim().toLowerCase() : "";
		var filtered = allItems;
		if (q) {
			filtered = allItems.filter(function (row) {
				return rowText(row).indexOf(q) !== -1;
			});
		}
		if (!filtered.length) {
			tbody.innerHTML =
				'<tr><td colspan="9" class="text-muted">No Golden State planroom jobs match this view.</td></tr>';
		} else {
			tbody.innerHTML = filtered.map(renderRow).join("");
		}
		if (filterCount) {
			filterCount.textContent = filtered.length === allItems.length
				? allItems.length + " jobs"
				: "Showing " + filtered.length + " of " + allItems.length + " jobs";
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
		tbody.innerHTML = '<tr><td colspan="9" class="text-muted">Loading…</td></tr>';
		var params = new URLSearchParams();
		params.set("limit", "2000");
		params.set("sort", sortSel && sortSel.value ? sortSel.value : "fit_score");
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
				applyLocalFilter();
			})
			.catch(function (err) {
				allItems = [];
				isFetching = false;
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

	if (filterInput) filterInput.addEventListener("input", applyLocalFilter);
	if (locationSel) locationSel.addEventListener("change", loadLeads);
	if (sortSel) sortSel.addEventListener("change", loadLeads);
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
	document.addEventListener("DOMContentLoaded", loadLeads);
})();
