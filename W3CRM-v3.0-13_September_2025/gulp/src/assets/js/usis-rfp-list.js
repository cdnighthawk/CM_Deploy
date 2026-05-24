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
			tb.innerHTML = '<tr><td colspan="4" class="text-muted">Add ?lead_estimate_id= or ?project_id=</td></tr>';
			return;
		}
		tb.innerHTML = '<tr><td colspan="4">Loading…</td></tr>';
		fetch(apiBase() + "/api/v1/rfps?" + q, { credentials: "include" })
			.then(function (r) {
				return r.json();
			})
			.then(function (data) {
				var rows = data.items || [];
				if (!rows.length) {
					tb.innerHTML = '<tr><td colspan="4" class="text-muted">No RFPs yet.</td></tr>';
					return;
				}
				tb.innerHTML = rows
					.map(function (x) {
						var pub = "/public/rfp/" + encodeURIComponent(x.public_token);
						var base = apiBase() || "http://127.0.0.1:5000";
						var vendorHref = base.replace(/\/$/, "") + pub;
						return (
							"<tr><td>" +
							esc(x.title) +
							"</td><td>" +
							esc(x.status) +
							"</td><td><code class=\"small\">" +
							esc(x.public_token) +
							"</code></td><td>" +
							'<a class="btn btn-sm btn-outline-primary" href="usis-rfp-detail.html?id=' +
							encodeURIComponent(x.id) +
							'">Detail</a> ' +
							'<a class="btn btn-sm btn-outline-secondary" href="' +
							esc(vendorHref) +
							'" target="_blank" rel="noopener">Vendor</a></td></tr>'
						);
					})
					.join("");
			})
			.catch(function () {
				tb.innerHTML = '<tr><td colspan="4" class="text-danger">Failed to load</td></tr>';
			});
	}

	document.addEventListener("DOMContentLoaded", function () {
		load();
		document.getElementById("usis-rfp-new").addEventListener("click", function () {
			var le = qs("lead_estimate_id");
			var pj = qs("project_id");
			var body = {};
			if (le) body.lead_estimate_id = le;
			if (pj) body.project_id = pj;
			if (!le && !pj) {
				alert("Add ?lead_estimate_id= or ?project_id= to the URL first.");
				return;
			}
			fetch(apiBase() + "/api/v1/rfps", {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				credentials: "include",
				body: JSON.stringify(body),
			})
				.then(function (r) {
					return r.json().then(function (j) {
						if (!r.ok) throw new Error(j.error || r.status);
						return j;
					});
				})
				.then(function () {
					load();
				})
				.catch(function (e) {
					alert(e.message || String(e));
				});
		});
	});
})();
