(function () {
	"use strict";

	function apiBase() {
		if (typeof window.USIS_API_BASE === "string" && window.USIS_API_BASE.trim()) {
			var s = window.USIS_API_BASE.trim().replace(/\/$/, "");
			try {
				if (s && new URL(s).origin !== window.location.origin) return s;
			} catch (e) {
				if (s) return s;
			}
		}
		if (window.location.protocol === "file:") return "http://127.0.0.1:5000";
		return "";
	}

	function qs(name) {
		return new URLSearchParams(window.location.search).get(name);
	}

	function esc(s) {
		var d = document.createElement("div");
		d.textContent = s == null ? "" : String(s);
		return d.innerHTML;
	}

	function load() {
		var le = qs("lead_estimate_id");
		var pj = qs("project_id");
		var q = le ? "lead_estimate_id=" + encodeURIComponent(le) : pj ? "project_id=" + encodeURIComponent(pj) : "";
		var tb = document.getElementById("usis-rfp-tbody");
		if (!tb) return;
		if (!q) {
			tb.innerHTML = '<tr><td colspan="5">' +
				(window.USISUi ? window.USISUi.emptyState({ title: "Select a job first", body: "Add ?lead_estimate_id= or ?project_id= to load RFPs." }) : '<span class="text-muted">Add ?lead_estimate_id= or ?project_id=</span>') +
				"</td></tr>";
			return;
		}
		tb.innerHTML = '<tr><td colspan="5">Loading…</td></tr>';
		fetch(apiBase() + "/api/v1/rfps?" + q, { credentials: "include" })
			.then(function (r) {
				if (!r.ok) {
					return r.json().catch(function () {
						throw new Error("HTTP " + r.status + " - Server error. Please try again or contact support.");
					}).then(function (err) {
						throw new Error(err.error || err.message || "HTTP " + r.status);
					});
				}
				return r.json();
			})
			.then(function (data) {
				var rows = data.items || [];
				if (!rows.length) {
					tb.innerHTML = '<tr><td colspan="5">' +
						(window.USISUi ? window.USISUi.emptyState({ title: "No RFPs yet", body: "Create a draft to send to vendors." }) : '<span class="text-muted">No RFPs yet.</span>') +
						"</td></tr>";
					return;
				}
				tb.innerHTML = rows
					.map(function (x) {
						var src = x.line_source === "takeoff" ? "Takeoff" : x.line_source === "narrative" ? "Scope" : "Items";
						var title = esc(x.title) || "Untitled RFP";
						return (
							"<tr><td>" +
							'<a href="usis-rfp-detail.html?id=' +
							encodeURIComponent(x.id) +
							'">' +
							title +
							"</a>" +
							"</td><td>" +
							(window.USISUi ? window.USISUi.statusChip(x.status) : esc(x.status)) +
							"</td><td>" +
							(window.USISUi ? window.USISUi.statusChip(src) : esc(src)) +
							"</td><td><code class=\"small\">" +
							esc(x.public_token) +
							'</code></td><td class="text-end">' +
							(window.USISUi && window.USISUi.rowMenu
								? window.USISUi.rowMenu({
										id: x.id,
										editHref: "usis-rfp-detail.html?id=" + encodeURIComponent(x.id),
										createHref: "usis-rfp-detail.html",
										deleteClass: "usis-rfp-del",
										adminDelete: true,
										deleteUrl: "/api/v1/rfps/" + encodeURIComponent(x.id),
									})
								: "") +
							"</td></tr>"
						);
					})
					.join("");
			})
			.catch(function (err) {
				tb.innerHTML = '<tr><td colspan="5" class="text-center py-4">' +
					'<div class="alert alert-danger d-inline-block text-start mb-0" role="alert">' +
					'<i class="fas fa-exclamation-triangle me-2"></i>' +
					'<strong>Could not load RFPs</strong><br>' +
					'<span class="small">' + esc(err.message || "Failed to load") + '</span><br>' +
					'<button class="btn btn-sm btn-outline-danger mt-2" onclick="window.location.reload()">Reload Page</button>' +
					"</div></td></tr>";
			});
	}

	document.addEventListener("DOMContentLoaded", function () {
		load();
		document.getElementById("usis-rfp-new").addEventListener("click", function () {
			var le = qs("lead_estimate_id");
			var pj = qs("project_id");
			if (!le && !pj) {
				alert("Add ?lead_estimate_id= or ?project_id= to the URL first.");
				return;
			}
			var params = [];
			if (le) params.push("lead_estimate_id=" + encodeURIComponent(le));
			if (pj) params.push("project_id=" + encodeURIComponent(pj));
			params.push("mode=create");
			window.location.href = "usis-rfp-detail.html?" + params.join("&");
		});
	});
})();
