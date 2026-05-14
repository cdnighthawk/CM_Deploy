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
		// BrowserSync picks the next free port (3000, 3001, … 3008, …) when defaults are busy.
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

	function setText(id, text) {
		var el = document.getElementById(id);
		if (el) el.textContent = text;
	}

	function setHint(text) {
		var el = document.getElementById("usis-hr-sample-hint");
		if (!el) return;
		if (text) {
			el.textContent = text;
			el.classList.remove("d-none");
		} else {
			el.textContent = "";
			el.classList.add("d-none");
		}
	}

	function esc(s) {
		if (s == null) return "";
		return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/"/g, "&quot;");
	}

	function renderSampleEmployees(rows) {
		var tbody = document.getElementById("usis-hr-sample-employees-body");
		if (!tbody) return;
		tbody.innerHTML = "";
		if (!rows || !rows.length) {
			tbody.innerHTML = '<tr><td colspan="5" class="text-muted small">No rows yet.</td></tr>';
			return;
		}
		rows.forEach(function (row) {
			var tr = document.createElement("tr");
			tr.innerHTML =
				'<td><a href="usis-hr-employee.html?id=' +
				encodeURIComponent(row.user_id) +
				'" class="text-decoration-none">' +
				esc(row.name) +
				"</a></td><td>" +
				esc(row.email) +
				'</td><td class="text-end">' +
				esc(row.open_onboarding_steps) +
				'</td><td class="text-end">' +
				esc(row.pending_policies) +
				'</td><td class="text-end">' +
				esc(row.open_hr_training) +
				"</td>";
			tbody.appendChild(tr);
		});
	}

	function loadSummary() {
		var statusEl = document.getElementById("usis-hr-api-status");
		var base = apiBase();
		fetch(base + "/api/v1/hr/dashboard-summary", { credentials: "omit" })
			.then(function (r) {
				if (!r.ok) throw new Error("HTTP " + r.status);
				return r.json().then(function (data) {
					return { r: r, data: data };
				});
			})
			.then(function (bundle) {
				var data = bundle.data;
				var c = data.counts || {};
				setText("usis-hr-count-acks", String(c.pending_acknowledgments != null ? c.pending_acknowledgments : "0"));
				setText("usis-hr-count-onboarding", String(c.onboarding_in_progress != null ? c.onboarding_in_progress : "0"));
				setText("usis-hr-count-safety-exp", String(c.expiring_safety_certs_30d != null ? c.expiring_safety_certs_30d : "0"));
				setText("usis-hr-count-approvals", String(c.pending_approvals_hr != null ? c.pending_approvals_hr : "0"));
				if (statusEl) {
					statusEl.classList.remove("text-danger", "text-warning");
					if (data.stub) {
						statusEl.textContent =
							"API returned stub: true (placeholder). Stop and restart Flask from the USIS_CM backend so the live HR dashboard handler runs; then run flask db upgrade and python seed_hr_employees.py if the table is still empty.";
						statusEl.classList.add("text-warning");
					} else {
						statusEl.textContent = "Live aggregates from hr_* tables.";
					}
				}
				if (data.stub) {
					setHint(
						"Backend build is outdated or a different app is bound to this port. After restart you should see stub: false and employee rows from the database."
					);
				} else {
					setHint(typeof data.hint === "string" && data.hint ? data.hint : "");
				}
				renderSampleEmployees(data.sample_employees || []);
			})
			.catch(function (err) {
				setHint("");
				if (statusEl) {
					statusEl.textContent = "Could not load summary: " + (err && err.message ? err.message : err);
					statusEl.classList.add("text-danger");
				}
				setText("usis-hr-count-acks", "—");
				setText("usis-hr-count-onboarding", "—");
				setText("usis-hr-count-safety-exp", "—");
				setText("usis-hr-count-approvals", "—");
				renderSampleEmployees([]);
			});
	}

	if (document.readyState === "loading") {
		document.addEventListener("DOMContentLoaded", loadSummary);
	} else {
		loadSummary();
	}
})();
