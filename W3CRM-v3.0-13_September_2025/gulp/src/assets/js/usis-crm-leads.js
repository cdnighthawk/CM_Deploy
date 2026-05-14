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

	function esc(s) {
		var d = document.createElement("div");
		d.textContent = s == null ? "" : String(s);
		return d.innerHTML;
	}

	function load() {
		var stage = document.getElementById("usis-crm-filter-stage");
		var v = stage && stage.value ? "&crm_stage=" + encodeURIComponent(stage.value) : "";
		var url = apiBase() + "/api/v1/lead-estimates?submission_state=undecided&limit=100" + v;
		var tb = document.getElementById("usis-crm-tbody");
		if (!tb) return;
		tb.innerHTML = '<tr><td colspan="4" class="text-muted">Loading…</td></tr>';
		fetch(url, { credentials: "omit" })
			.then(function (r) {
				return r.json();
			})
			.then(function (data) {
				var rows = data.items || [];
				if (!rows.length) {
					tb.innerHTML = '<tr><td colspan="4" class="text-muted">No rows.</td></tr>';
					return;
				}
				tb.innerHTML = rows
					.map(function (x) {
						var ext = x.external_id || x.id;
						var href = "construction/lead-detail.html?id=" + encodeURIComponent(ext);
						return (
							"<tr><td>" +
							esc(x.crm_stage || "—") +
							"</td><td>" +
							esc(x.name || x.number || "") +
							"</td><td>" +
							esc(x.due_at || "—") +
							'</td><td><a class="btn btn-sm btn-outline-primary" href="' +
							href +
							'">Open</a></td></tr>'
						);
					})
					.join("");
			})
			.catch(function () {
				tb.innerHTML = '<tr><td colspan="4" class="text-danger">Failed to load.</td></tr>';
			});
	}

	document.addEventListener("DOMContentLoaded", function () {
		load();
		var b = document.getElementById("usis-crm-refresh");
		if (b) b.addEventListener("click", load);
		var st = document.getElementById("usis-crm-filter-stage");
		if (st) st.addEventListener("change", load);
	});
})();
