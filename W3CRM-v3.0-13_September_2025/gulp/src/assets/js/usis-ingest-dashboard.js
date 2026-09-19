/**
 * CM Ingest dashboard — recent ACCDocs/Forma uploads from GET /api/v1/ingest/activity.
 */
(function () {
	"use strict";

	function api() {
		return window.USIS_API && typeof window.USIS_API.fetchJson === "function"
			? window.USIS_API
			: null;
	}

	function el(id) {
		return document.getElementById(id);
	}

	function esc(s) {
		var d = document.createElement("div");
		d.textContent = s == null ? "" : String(s);
		return d.innerHTML;
	}

	function when(iso) {
		if (!iso) return "—";
		var dt = new Date(iso);
		if (isNaN(dt.getTime())) return String(iso);
		return dt.toLocaleString(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
	}

	function relWhen(iso) {
		if (!iso) return "—";
		var dt = new Date(iso);
		if (isNaN(dt.getTime())) return "—";
		var mins = Math.round((Date.now() - dt.getTime()) / 60000);
		if (mins < 1) return "just now";
		if (mins < 60) return mins + "m ago";
		var hrs = Math.round(mins / 60);
		if (hrs < 36) return hrs + "h ago";
		return when(iso);
	}

	function query() {
		var params = new URLSearchParams();
		params.set("kind", (el("usis-ingest-dash-kind") || {}).value || "all");
		params.set("source", (el("usis-ingest-dash-source") || {}).value || "all");
		params.set("days", (el("usis-ingest-dash-days") || {}).value || "14");
		params.set("limit", "120");
		var q = ((el("usis-ingest-dash-q") || {}).value || "").trim();
		if (q) params.set("q", q);
		return params;
	}

	function jobLabel(row) {
		var bits = [row.project_number, row.project_name || row.estimate_name].filter(Boolean);
		return bits.length ? bits.join(" · ") : "Unassigned";
	}

	function matchesProjectFilter(row) {
		var needle = ((el("usis-ingest-dash-project") || {}).value || "").trim().toLowerCase();
		if (!needle) return true;
		var hay = [row.project_number, row.project_name, row.estimate_name, row.lead_estimate_id, row.project_id]
			.filter(Boolean)
			.join(" ")
			.toLowerCase();
		return hay.indexOf(needle) >= 0;
	}

	function sourceBadge(source) {
		var raw = source || "other";
		var cls = "bg-secondary";
		if (raw === "autodesk_desktop_connector" || raw === "accdocs" || raw === "acc_docs") cls = "bg-primary";
		else if (raw === "mass_ingest") cls = "bg-info text-dark";
		else if (raw === "forma") cls = "bg-dark";
		var label = raw === "autodesk_desktop_connector" ? "ACCDocs" : raw.replace(/_/g, " ");
		return '<span class="badge ' + cls + '">' + esc(label) + "</span>";
	}

	function openLinks(row) {
		var parts = [];
		if (row.estimate_url) {
			parts.push('<a class="btn btn-link btn-sm p-0" href="' + esc(row.estimate_url) + '">Estimate</a>');
		}
		if (row.project_url) {
			parts.push('<a class="btn btn-link btn-sm p-0" href="' + esc(row.project_url) + '">Project</a>');
		}
		if (row.drawing_url) {
			parts.push('<a class="btn btn-link btn-sm p-0" href="' + esc(row.drawing_url) + '">Drawing</a>');
		} else if (row.file_url) {
			parts.push('<a class="btn btn-link btn-sm p-0" href="' + esc(row.file_url) + '" target="_blank" rel="noopener">File</a>');
		} else if (row.documents_url) {
			parts.push('<a class="btn btn-link btn-sm p-0" href="' + esc(row.documents_url) + '">Docs</a>');
		}
		return parts.join(" · ") || "—";
	}

	function renderStatus(status, projects) {
		var newCount = (projects || []).filter(function (p) { return p.is_new; }).length;
		var uploadEl = el("usis-ingest-stat-upload");
		var agentEl = el("usis-ingest-stat-agent");
		var rescanEl = el("usis-ingest-stat-rescan");
		var errEl = el("usis-ingest-stat-errors");
		var newEl = el("usis-ingest-stat-new");
		if (uploadEl) uploadEl.textContent = relWhen(status.last_successful_upload_at || status.last_upload_at);
		if (agentEl) {
			agentEl.textContent = status.agent_reporting ? relWhen(status.last_agent_event_at) : "No agent report yet";
			agentEl.parentElement.classList.toggle("stale", !!status.stale);
		}
		if (rescanEl) rescanEl.textContent = relWhen(status.last_rescan_at);
		if (errEl) errEl.textContent = String(status.open_error_count == null ? 0 : status.open_error_count);
		if (newEl) newEl.textContent = String(newCount);
		var hint = el("usis-ingest-dash-hint");
		if (hint) {
			var bits = [];
			if (status.watch_hint) bits.push("Watches " + status.watch_hint);
			if (status.rescan_interval_hint) bits.push("rescans every " + status.rescan_interval_hint);
			if (status.history_ui_hint) bits.push(status.history_ui_hint);
			hint.textContent = bits.join(" · ");
		}
	}

	function renderProjects(projects) {
		var box = el("usis-ingest-new-list");
		var count = el("usis-ingest-new-count");
		if (!box) return;
		var rows = (projects || []).filter(matchesProjectFilter);
		if (count) count.textContent = rows.length ? rows.length + " jobs" : "";
		if (!rows.length) {
			box.innerHTML = '<span class="text-muted small">No uploads in this window.</span>';
			return;
		}
		box.innerHTML = rows
			.map(function (p) {
				var href = p.estimate_url || p.project_url || "#";
				var badge = p.is_new ? '<span class="badge bg-success ms-1">New</span>' : "";
				var n = (p.upload_count || 0) + " files";
				return (
					'<a class="btn btn-sm btn-outline-secondary" href="' +
					esc(href) +
					'">' +
					esc(jobLabel(p)) +
					" <span class=\"text-muted\">" +
					esc(n) +
					"</span>" +
					badge +
					"</a>"
				);
			})
			.join("");
	}

	function renderItems(items, total) {
		var tb = el("usis-ingest-dash-tbody");
		var count = el("usis-ingest-dash-count");
		var rows = (items || []).filter(matchesProjectFilter);
		if (count) count.textContent = rows.length + (total != null ? " of " + total : "") + " files";
		if (!tb) return;
		if (!rows.length) {
			tb.innerHTML = '<tr><td colspan="7" class="text-muted">No ingest activity for these filters.</td></tr>';
			return;
		}
		tb.innerHTML = rows
			.map(function (row) {
				var title = row.filename || row.title || row.sheet_number || "Untitled";
				var extra = row.sheet_number && row.sheet_number !== title ? " · " + row.sheet_number : "";
				var job = jobLabel(row);
				var jobLink = row.estimate_url || row.project_url;
				var jobHtml = jobLink
					? '<a href="' + esc(jobLink) + '">' + esc(job) + "</a>"
					: esc(job);
				if (row.is_new_project) jobHtml += ' <span class="badge bg-success">New</span>';
				var path = row.estimate_folder_path
					? '<span class="usis-ingest-path" title="Estimate job folder (PR #53 path when present)">' +
						esc(row.estimate_folder_path) +
						"</span>"
					: '<span class="text-muted">—</span>';
				return (
					"<tr>" +
					"<td class=\"text-nowrap\">" +
					esc(when(row.created_at)) +
					"</td>" +
					"<td>" +
					esc(row.kind === "drawing" ? "Drawing" : "Document") +
					"</td>" +
					"<td>" +
					esc(title) +
					esc(extra) +
					"</td>" +
					"<td>" +
					jobHtml +
					"</td>" +
					"<td>" +
					sourceBadge(row.source) +
					"</td>" +
					"<td>" +
					path +
					"</td>" +
					'<td class="text-end text-nowrap">' +
					openLinks(row) +
					"</td>" +
					"</tr>"
				);
			})
			.join("");
	}

	function load() {
		var client = api();
		var tb = el("usis-ingest-dash-tbody");
		if (!client) {
			if (tb) tb.innerHTML = '<tr><td colspan="7" class="text-danger">API helper missing.</td></tr>';
			return;
		}
		if (tb) tb.innerHTML = '<tr><td colspan="7" class="text-muted">Loading ingest activity…</td></tr>';
		client
			.fetchJson("/api/v1/ingest/activity?" + query().toString())
			.then(function (data) {
				renderStatus(data.status || {}, data.projects || []);
				renderProjects(data.projects || []);
				renderItems(data.items || [], data.total);
			})
			.catch(function (err) {
				if (tb) {
					tb.innerHTML =
						'<tr><td colspan="7" class="text-danger">' +
						esc(err && err.message ? err.message : "Could not load ingest activity") +
						"</td></tr>";
				}
			});
	}

	var debounceTimer = 0;
	function debounceLoad() {
		clearTimeout(debounceTimer);
		debounceTimer = setTimeout(load, 180);
	}

	document.addEventListener("DOMContentLoaded", function () {
		["usis-ingest-dash-kind", "usis-ingest-dash-source", "usis-ingest-dash-days"].forEach(function (id) {
			var node = el(id);
			if (node) node.addEventListener("change", load);
		});
		["usis-ingest-dash-q", "usis-ingest-dash-project"].forEach(function (id) {
			var node = el(id);
			if (node) node.addEventListener("input", debounceLoad);
		});
		if (el("usis-ingest-dash-reload")) {
			el("usis-ingest-dash-reload").addEventListener("click", load);
		}
		load();
	});
})();
