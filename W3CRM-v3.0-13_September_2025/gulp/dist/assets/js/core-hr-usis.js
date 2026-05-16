/**
 * Core HR (core-hr.html) — load employee rows from HR dashboard summary API;
 * name cells link to usis-hr-employee.html?id=<user UUID>.
 */
(function () {
	"use strict";

	var DEV_SERVER_PORTS = {
		3000: 1,
		3001: 1,
		3002: 1,
		3003: 1,
		3004: 1,
		3005: 1,
		3006: 1,
		4173: 1,
		5173: 1,
		5174: 1,
		5500: 1,
		5501: 1,
		8080: 1,
		4200: 1,
		4321: 1,
		9630: 1,
		1234: 1,
	};

	function explicitWindowApiBase() {
		if (typeof window.USIS_API_BASE !== "string") return null;
		var s = window.USIS_API_BASE.trim().replace(/\/$/, "");
		return s || null;
	}

	function metaApiBase() {
		if (typeof document === "undefined" || !document.querySelector) return null;
		var m = document.querySelector('meta[name="usis-api-base"]');
		if (!m) return null;
		var c = (m.getAttribute("content") || "").trim().replace(/\/$/, "");
		return c || null;
	}

	function isLikelyStaticDevPort(portStr) {
		if (DEV_SERVER_PORTS[portStr]) return true;
		var n = parseInt(portStr, 10);
		return !isNaN(n) && n >= 3000 && n <= 3099;
	}

	function apiBase() {
		var fromWin = explicitWindowApiBase();
		if (fromWin) return fromWin;
		var fromMeta = metaApiBase();
		if (fromMeta) return fromMeta;
		var loc = window.location;
		if (loc.protocol === "file:") return "http://127.0.0.1:5000";
		var host = loc.hostname || "";
		var proto = loc.protocol || "http:";
		var port = String(loc.port || "");
		if (isLikelyStaticDevPort(port)) return proto + "//" + host + ":5000";
		return "";
	}

	function esc(s) {
		if (s == null) return "";
		return String(s)
			.replace(/&/g, "&amp;")
			.replace(/</g, "&lt;")
			.replace(/"/g, "&quot;");
	}

	function shortId(uuid) {
		if (!uuid || String(uuid).length < 10) return esc(uuid || "—");
		var u = String(uuid);
		return esc(u.slice(0, 8) + "…");
	}

	function renderRows(rows) {
		var tbody = document.querySelector("#usis-core-hr-employees-tbl tbody");
		if (!tbody) return;
		tbody.innerHTML = "";
		if (!rows || !rows.length) {
			tbody.innerHTML =
				'<tr><td colspan="8" class="text-muted text-center py-4">No employees in the HR sample set yet. Run <code>python seed_hr_employees.py</code> from the backend folder, or open <a href="usis-hr-dashboard.html">HR dashboard</a> for KPIs.</td></tr>';
			return;
		}
		rows.forEach(function (row) {
			var uid = row.user_id || "";
			var name = row.name || row.email || "—";
			var href = "usis-hr-employee.html?id=" + encodeURIComponent(uid);
			var tr = document.createElement("tr");
			tr.innerHTML =
				'<td><div class="form-check custom-checkbox">' +
				'<input type="checkbox" class="form-check-input check-input" disabled aria-label="Row select">' +
				"</div></td>" +
				"<td><code class=\"small\">" +
				shortId(uid) +
				"</code></td>" +
				"<td>" +
				'<div class="d-flex align-items-center">' +
				'<div class="clearfix">' +
				'<h6 class="mb-0"><a href="' +
				href +
				'" class="text-decoration-none text-body">' +
				esc(name) +
				"</a></h6>" +
				'<small class="text-muted">Employee record</small>' +
				"</div></div></td>" +
				"<td>" +
				(row.email ? '<a href="mailto:' + esc(row.email) + '" class="text-primary">' + esc(row.email) + "</a>" : "—") +
				"</td>" +
				'<td><span class="text-muted">—</span></td>' +
				'<td><span class="text-muted">—</span></td>' +
				'<td><span class="text-muted">—</span></td>' +
				'<td><span class="badge badge-sm badge-success light">Active</span></td>';
			tbody.appendChild(tr);
		});
	}

	function load() {
		var statusEl = document.getElementById("usis-core-hr-api-status");
		var base = apiBase();
		fetch(base + "/api/v1/hr/dashboard-summary", { credentials: "omit" })
			.then(function (r) {
				if (!r.ok) throw new Error("HTTP " + r.status);
				return r.json();
			})
			.then(function (data) {
				if (statusEl) {
					statusEl.classList.remove("d-none", "text-danger", "text-warning");
					if (data.stub) {
						statusEl.textContent = "Placeholder data — restart the API for a live directory.";
						statusEl.classList.add("text-warning");
					} else if (typeof data.hint === "string" && data.hint.trim()) {
						statusEl.textContent = data.hint.trim();
						statusEl.classList.add("text-warning");
					} else {
						statusEl.textContent = "";
					}
				}
				renderRows(data.sample_employees || []);
			})
			.catch(function (err) {
				if (statusEl) {
					statusEl.textContent = "Could not load employees: " + (err && err.message ? err.message : err);
					statusEl.classList.remove("d-none");
					statusEl.classList.add("text-danger");
				}
				var tbody = document.querySelector("#usis-core-hr-employees-tbl tbody");
				if (tbody) {
					tbody.innerHTML =
						'<tr><td colspan="8" class="text-danger text-center py-4">Could not load employees. Check that the API is running and try again.</td></tr>';
				}
			});
	}

	if (document.readyState === "loading") {
		document.addEventListener("DOMContentLoaded", load);
	} else {
		load();
	}
})();
