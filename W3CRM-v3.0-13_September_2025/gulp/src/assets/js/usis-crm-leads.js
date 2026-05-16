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

	function estimateStatusBadges(x) {
		var parts = [];
		if (x.estimate_approved_at) {
			var t = x.estimate_approved_at ? String(x.estimate_approved_at).slice(0, 16) : "";
			parts.push(
				'<span class="badge bg-success" title="Approved' +
					(t ? " · " + esc(t) : "") +
					'">Approved</span>'
			);
		} else if (x.estimate_locked_at) {
			parts.push(
				'<span class="badge bg-secondary" title="Locked (draft) · ' +
					esc(String(x.estimate_locked_at).slice(0, 16)) +
					'">Locked</span>'
			);
		} else {
			parts.push('<span class="text-muted small">—</span>');
		}
		return parts.join(" ");
	}

	function load() {
		var stage = document.getElementById("usis-crm-filter-stage");
		var v = stage && stage.value ? "&crm_stage=" + encodeURIComponent(stage.value) : "";
		var url = apiBase() + "/api/v1/lead-estimates?submission_state=undecided&limit=100" + v;
		var tb = document.getElementById("usis-crm-tbody");
		if (!tb) return;
		tb.innerHTML = '<tr><td colspan="5" class="text-muted">Loading…</td></tr>';
		fetch(url, { credentials: "include", headers: { Accept: "application/json" } })
			.then(function (r) {
				return r.json().then(function (j) {
					if (!r.ok) throw new Error((j && j.error) || "HTTP " + r.status);
					return j;
				});
			})
			.then(function (data) {
				var rows = data.items || [];
				if (!rows.length) {
					tb.innerHTML = '<tr><td colspan="5" class="text-muted">No rows.</td></tr>';
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
							'</td><td class="text-nowrap">' +
							estimateStatusBadges(x) +
							"</td><td>" +
							esc(x.due_at || "—") +
							'</td><td><a class="btn btn-sm btn-outline-primary" href="' +
							href +
							'">Open</a></td></tr>'
						);
					})
					.join("");
			})
			.catch(function (e) {
				tb.innerHTML =
					'<tr><td colspan="5" class="text-danger">' + esc(e.message || "Failed to load.") + "</td></tr>";
				if (window.USISNotify) window.USISNotify.error(e.message || "Failed to load leads.");
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
