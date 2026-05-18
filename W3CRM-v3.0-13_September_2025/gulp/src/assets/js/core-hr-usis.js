/**
 * Core HR (core-hr.html) — employee directory from admin users API when permitted,
 * otherwise HR dashboard summary (users with hr_* activity).
 */
(function () {
	"use strict";

	function apiBase() {
		if (typeof window.usisApiBase === "function") {
			return window.usisApiBase();
		}
		if (typeof window.USIS_API_BASE === "string") {
			return window.USIS_API_BASE.trim().replace(/\/$/, "");
		}
		var loc = window.location;
		if (loc.protocol === "file:") {
			return "http://127.0.0.1:5000";
		}
		var h = loc.hostname || "";
		if (h === "localhost" || h === "127.0.0.1") {
			return (loc.protocol + "//" + h + ":5000").replace(/\/$/, "");
		}
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

	function displayName(u) {
		var n = [u.first_name, u.last_name].filter(Boolean).join(" ").trim();
		return n || u.email || u.name || "—";
	}

	function mapAdminUser(u) {
		return {
			user_id: u.id,
			name: displayName(u),
			email: u.email || "",
		};
	}

	function renderRows(rows) {
		var tbody = document.querySelector("#usis-core-hr-employees-tbl tbody");
		if (!tbody) return;
		tbody.innerHTML = "";
		if (!rows || !rows.length) {
			tbody.innerHTML =
				'<tr><td colspan="8" class="text-muted text-center py-4">No employees yet. Add staff in <a href="usis-user-directory.html">User admin</a>, or seed HR data from the <a href="usis-hr-dashboard.html">HR dashboard</a>.</td></tr>';
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

	function showLoadError(err) {
		var statusEl = document.getElementById("usis-core-hr-api-status");
		var msg =
			err && (err.message === "Failed to fetch" || err.name === "TypeError")
				? "Could not reach the API. Check that the backend is running and try again."
				: "Could not load employees: " + (err && err.message ? err.message : err);
		if (statusEl) {
			statusEl.textContent = msg;
			statusEl.classList.remove("d-none");
			statusEl.classList.add("text-danger");
		}
		var tbody = document.querySelector("#usis-core-hr-employees-tbl tbody");
		if (tbody) {
			tbody.innerHTML =
				'<tr><td colspan="8" class="text-danger text-center py-4">' + esc(msg) + "</td></tr>";
		}
	}

	function setStatusHint(text, kind) {
		var statusEl = document.getElementById("usis-core-hr-api-status");
		if (!statusEl) return;
		statusEl.classList.remove("text-danger", "text-warning");
		if (!text) {
			statusEl.textContent = "";
			return;
		}
		statusEl.textContent = text;
		if (kind === "warning") statusEl.classList.add("text-warning");
	}

	function loadHrSummary() {
		var base = apiBase();
		return fetch(base + "/api/v1/hr/dashboard-summary", {
			credentials: "include",
			headers: { Accept: "application/json" },
		})
			.then(function (r) {
				if (!r.ok) throw new Error("HTTP " + r.status);
				return r.json();
			})
			.then(function (data) {
				if (data.stub) {
					setStatusHint("Placeholder data — restart the API for a live directory.", "warning");
				} else if (typeof data.hint === "string" && data.hint.trim()) {
					setStatusHint(data.hint.trim(), "warning");
				} else {
					setStatusHint("", "");
				}
				renderRows(data.sample_employees || []);
			});
	}

	function load() {
		var base = apiBase();
		fetch(base + "/api/v1/admin/users?limit=500", {
			credentials: "include",
			headers: { Accept: "application/json" },
		})
			.then(function (r) {
				if (r.status === 401 || r.status === 403) {
					return loadHrSummary();
				}
				if (!r.ok) throw new Error("HTTP " + r.status);
				return r.json().then(function (data) {
					var rows = (data.items || []).map(mapAdminUser);
					if (!rows.length) {
						setStatusHint("No users in directory yet. Add staff in User admin.", "warning");
					} else {
						setStatusHint("", "");
					}
					renderRows(rows);
				});
			})
			.catch(function (err) {
				showLoadError(err);
			});
	}

	if (document.readyState === "loading") {
		document.addEventListener("DOMContentLoaded", load);
	} else {
		load();
	}
})();
