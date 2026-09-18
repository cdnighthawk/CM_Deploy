/**
 * Platform Admin — tenants, flags, health, audit, impersonate.
 */
(function () {
	"use strict";

	function apiBase() {
		if (typeof window.usisApiBase === "function") return window.usisApiBase();
		if (typeof window.USIS_API_BASE === "string" && window.USIS_API_BASE.trim()) {
			return window.USIS_API_BASE.trim().replace(/\/$/, "");
		}
		return "";
	}

	function esc(s) {
		return String(s == null ? "" : s)
			.replace(/&/g, "&amp;")
			.replace(/</g, "&lt;")
			.replace(/>/g, "&gt;")
			.replace(/"/g, "&quot;");
	}

	function fetchJson(path, opts) {
		opts = opts || {};
		return fetch(apiBase() + path, {
			credentials: "include",
			headers: Object.assign({ Accept: "application/json", "Content-Type": "application/json" }, opts.headers || {}),
			method: opts.method || "GET",
			body: opts.body ? JSON.stringify(opts.body) : undefined,
		}).then(function (res) {
			return res.json().then(function (j) {
				return { ok: res.ok, status: res.status, body: j };
			});
		});
	}

	function pageKind() {
		var p = (window.location.pathname || "").replace(/\\/g, "/");
		var m = p.match(/\/admin\/tenants\/([^/]+)/i);
		if (m) return { kind: "tenant", id: decodeURIComponent(m[1]) };
		if (/\/admin\/flags/i.test(p)) return { kind: "flags" };
		if (/\/admin\/health/i.test(p)) return { kind: "health" };
		if (/\/admin\/audit/i.test(p)) return { kind: "audit" };
		return { kind: "list" };
	}

	function flash(msg, kind) {
		var el = document.getElementById("usis-adm-flash");
		if (!el) return;
		el.className = "alert py-2 px-3 mb-3 alert-" + (kind || "success");
		el.textContent = msg;
		el.classList.remove("d-none");
	}

	function chip(status) {
		if (window.USISUi && window.USISUi.statusChip) return window.USISUi.statusChip(status || "");
		return esc(status || "");
	}

	function askReason(title, cb) {
		var modalEl = document.getElementById("usis-adm-reason-modal");
		document.getElementById("usis-adm-reason-title").textContent = title || "Confirm";
		document.getElementById("usis-adm-reason").value = "";
		var modal = window.bootstrap ? window.bootstrap.Modal.getOrCreateInstance(modalEl) : null;
		var ok = document.getElementById("usis-adm-reason-ok");
		function done() {
			ok.removeEventListener("click", onOk);
		}
		function onOk() {
			var reason = (document.getElementById("usis-adm-reason").value || "").trim();
			if (reason.length < 12) {
				flash("Reason must be at least 12 characters.", "danger");
				return;
			}
			done();
			if (modal) modal.hide();
			cb(reason);
		}
		ok.addEventListener("click", onOk);
		if (modal) modal.show();
	}

	function navLinks() {
		return (
			'<a class="btn btn-sm btn-outline-secondary" href="/admin">Tenants</a> ' +
			'<a class="btn btn-sm btn-outline-secondary" href="/admin/flags">Flags</a> ' +
			'<a class="btn btn-sm btn-outline-secondary" href="/admin/health">Health</a> ' +
			'<a class="btn btn-sm btn-outline-secondary" href="/admin/audit">Audit</a>'
		);
	}

	function renderList() {
		document.getElementById("usis-adm-title").textContent = "Admin";
		document.getElementById("usis-adm-actions").innerHTML =
			navLinks() + ' <button type="button" class="btn btn-sm btn-primary" id="usis-adm-add">Add tenant</button>';
		fetchJson("/api/admin/tenants").then(function (r) {
			if (r.status === 403) {
				document.getElementById("usis-adm-forbidden").classList.remove("d-none");
				document.getElementById("usis-adm-root").innerHTML = "";
				return;
			}
			var items = (r.body && r.body.items) || [];
			var kpis = document.getElementById("usis-adm-kpis");
			kpis.classList.remove("d-none");
			var seats = 0;
			items.forEach(function (t) {
				seats += (t.seats && t.seats.office_used) || 0;
			});
			kpis.innerHTML =
				'<div class="col-md-3"><div class="card border-0 shadow-sm"><div class="card-body py-2"><div class="small text-muted">Tenants</div><div class="h5 mb-0">' +
				items.length +
				"</div></div></div></div>" +
				'<div class="col-md-3"><div class="card border-0 shadow-sm"><div class="card-body py-2"><div class="small text-muted">Office seats used</div><div class="h5 mb-0">' +
				seats +
				"</div></div></div></div>";
			var html = '<div class="card border-0 shadow-sm"><div class="card-body">';
			if (!items.length) {
				html +=
					window.USISUi && window.USISUi.emptyState
						? window.USISUi.emptyState({ title: "No tenants", body: "Create the first subscriber company." })
						: "<p class=\"text-muted\">No tenants.</p>";
			} else {
				html +=
					'<div class="table-responsive"><table class="table table-sm table-hover align-middle mb-0"><thead class="table-light"><tr><th>Name</th><th>Status</th><th>Plan</th><th>Office seats</th><th>Field devices</th><th>Last activity</th></tr></thead><tbody>';
				items.forEach(function (t) {
					var s = t.seats || {};
					html +=
						'<tr style="cursor:pointer" data-href="/admin/tenants/' +
						esc(t.id) +
						'"><td>' +
						esc(t.legal_name || t.name) +
						"</td><td>" +
						chip(t.status) +
						"</td><td>" +
						esc(t.plan_key) +
						"</td><td>" +
						esc((s.office_used || 0) + " / " + (s.office_cap || t.seat_cap_office || "—")) +
						"</td><td>" +
						esc((s.field_used || 0) + " / " + (s.field_cap || t.seat_cap_field || "—")) +
						"</td><td>" +
						esc(s.last_activity || "—") +
						"</td></tr>";
				});
				html += "</tbody></table></div>";
			}
			html += "</div></div>";
			document.getElementById("usis-adm-root").innerHTML = html;
			document.querySelectorAll("[data-href]").forEach(function (tr) {
				tr.addEventListener("click", function () {
					window.location.href = tr.getAttribute("data-href");
				});
			});
			var add = document.getElementById("usis-adm-add");
			if (add) {
				add.addEventListener("click", function () {
					var name = window.prompt("Company name");
					if (!name) return;
					fetchJson("/api/admin/tenants", { method: "POST", body: { name: name } }).then(function (res) {
						if (!res.ok) return flash((res.body && res.body.error) || "Create failed", "danger");
						flash("Tenant created.", "success");
						renderList();
					});
				});
			}
		});
	}

	function renderTenant(id) {
		document.getElementById("usis-adm-actions").innerHTML = navLinks();
		fetchJson("/api/admin/tenants/" + encodeURIComponent(id)).then(function (r) {
			if (!r.ok) {
				document.getElementById("usis-adm-root").innerHTML = "<p class=\"text-danger\">" + esc((r.body && r.body.error) || "Not found") + "</p>";
				return;
			}
			var t = r.body.item;
			document.getElementById("usis-adm-title").textContent = t.legal_name || t.name;
			var html = '<div class="card border-0 shadow-sm mb-3"><div class="card-body">';
			html += '<div class="row g-2 mb-3"><div class="col-md-4"><label class="form-label small">Status</label><select class="form-select form-select-sm" id="usis-adm-status">';
			["trial", "active", "past_due", "suspended", "closed"].forEach(function (st) {
				html += '<option value="' + st + '"' + (t.status === st ? " selected" : "") + ">" + st + "</option>";
			});
			html += '</select></div><div class="col-md-4"><label class="form-label small">Plan</label><select class="form-select form-select-sm" id="usis-adm-plan">';
			["field", "office", "full"].forEach(function (pk) {
				html += '<option value="' + pk + '"' + (t.plan_key === pk ? " selected" : "") + ">" + pk + "</option>";
			});
			html +=
				'</select></div><div class="col-md-4"><label class="form-label small">Notes</label><input class="form-control form-control-sm" id="usis-adm-notes" value="' +
				esc(t.notes || "") +
				'"></div></div>';
			html +=
				'<div class="row g-2 mb-3"><div class="col-md-4"><label class="form-label small">Office seats</label><input class="form-control form-control-sm" id="usis-adm-cap-office" value="' +
				esc(t.seat_cap_office) +
				'"></div><div class="col-md-4"><label class="form-label small">Field seats</label><input class="form-control form-control-sm" id="usis-adm-cap-field" value="' +
				esc(t.seat_cap_field) +
				'"></div></div>';
			html += "<h3 class=\"h6\">Entitlements</h3><div class=\"row mb-3\">";
			Object.keys(t.entitlements || {}).forEach(function (k) {
				html +=
					'<div class="col-md-4"><div class="form-check"><input class="form-check-input usis-adm-ent" type="checkbox" data-key="' +
					esc(k) +
					'" id="ent-' +
					esc(k) +
					'"' +
					(t.entitlements[k] ? " checked" : "") +
					'><label class="form-check-label" for="ent-' +
					esc(k) +
					'">' +
					esc(k) +
					"</label></div></div>";
			});
			html += "</div><h3 class=\"h6\">Flag overrides</h3>";
			Object.keys(t.flags || {}).forEach(function (k) {
				html +=
					'<div class="form-check"><input class="form-check-input usis-adm-flag" type="checkbox" data-key="' +
					esc(k) +
					'"' +
					(t.flags[k] ? " checked" : "") +
					"><label class=\"form-check-label\">" +
					esc(k) +
					"</label></div>";
			});
			html +=
				'<div class="d-flex justify-content-end gap-2 mt-3"><button type="button" class="btn btn-sm btn-outline-primary" id="usis-adm-impersonate">Impersonate</button><button type="button" class="btn btn-sm btn-primary" id="usis-adm-save">Save</button></div></div></div>';
			document.getElementById("usis-adm-root").innerHTML = html;
			document.getElementById("usis-adm-save").addEventListener("click", function () {
				var ents = {};
				document.querySelectorAll(".usis-adm-ent").forEach(function (el) {
					ents[el.getAttribute("data-key")] = el.checked;
				});
				var payload = {
					status: document.getElementById("usis-adm-status").value,
					plan_key: document.getElementById("usis-adm-plan").value,
					notes: document.getElementById("usis-adm-notes").value,
					seat_cap_office: parseInt(document.getElementById("usis-adm-cap-office").value, 10),
					seat_cap_field: parseInt(document.getElementById("usis-adm-cap-field").value, 10),
					entitlements: ents,
					reason: "platform tenant update from admin",
				};
				var danger = payload.status === "suspended" || payload.status === "closed";
				function send(reason) {
					payload.reason = reason;
					fetchJson("/api/admin/tenants/" + encodeURIComponent(id), { method: "PATCH", body: payload }).then(function (res) {
						if (!res.ok) return flash((res.body && res.body.error) || "Save failed", "danger");
						flash("Saved.", "success");
					});
				}
				if (danger) askReason("Suspend or close tenant", send);
				else send(payload.reason);
			});
			document.getElementById("usis-adm-impersonate").addEventListener("click", function () {
				askReason("Impersonate " + (t.legal_name || t.name), function (reason) {
					fetchJson("/api/admin/tenants/" + encodeURIComponent(id) + "/impersonate", { method: "POST", body: { reason: reason } }).then(function (res) {
						if (!res.ok) return flash((res.body && res.body.error) || "Impersonate failed", "danger");
						window.location.href = "/settings";
					});
				});
			});
			document.querySelectorAll(".usis-adm-flag").forEach(function (el) {
				el.addEventListener("change", function () {
					fetchJson("/api/admin/flags/" + encodeURIComponent(el.getAttribute("data-key")), {
						method: "PUT",
						body: { tenant_id: id, value: el.checked, reason: "tenant flag override" },
					});
				});
			});
		});
	}

	function renderFlags() {
		document.getElementById("usis-adm-title").textContent = "Feature flags";
		document.getElementById("usis-adm-actions").innerHTML = navLinks();
		fetchJson("/api/admin/flags").then(function (r) {
			var items = (r.body && r.body.items) || [];
			var html = '<div class="card border-0 shadow-sm"><div class="card-body">';
			items.forEach(function (f) {
				html +=
					'<div class="form-check mb-2"><input class="form-check-input usis-flag" type="checkbox" data-key="' +
					esc(f.key) +
					'"' +
					(f.value ? " checked" : "") +
					"><label class=\"form-check-label\">" +
					esc(f.key) +
					' <span class="text-muted small">' +
					esc(f.description || "") +
					"</span></label></div>";
			});
			html += "</div></div>";
			document.getElementById("usis-adm-root").innerHTML = html;
			document.querySelectorAll(".usis-flag").forEach(function (el) {
				el.addEventListener("change", function () {
					fetchJson("/api/admin/flags/" + encodeURIComponent(el.getAttribute("data-key")), {
						method: "PUT",
						body: { value: el.checked, reason: "platform flag change" },
					}).then(function (res) {
						if (!res.ok) flash((res.body && res.body.error) || "Failed", "danger");
						else flash("Flag saved.", "success");
					});
				});
			});
		});
	}

	function healthDot(st) {
		if (st === "ok") return "🟢";
		if (st === "warn") return "🟡";
		return "🔴";
	}

	function renderHealth() {
		document.getElementById("usis-adm-title").textContent = "Health";
		document.getElementById("usis-adm-actions").innerHTML = navLinks();
		fetchJson("/api/admin/health").then(function (r) {
			var items = (r.body && r.body.items) || {};
			var html = '<div class="card border-0 shadow-sm"><div class="card-body"><ul class="list-unstyled mb-0">';
			Object.keys(items).forEach(function (k) {
				html += "<li class=\"mb-2\">" + healthDot(items[k].status) + " <strong>" + esc(k) + "</strong> — " + esc(items[k].detail || "") + "</li>";
			});
			html += "</ul></div></div>";
			document.getElementById("usis-adm-root").innerHTML = html;
		});
		fetchJson("/api/ai/status").then(function () {});
	}

	function renderAudit() {
		document.getElementById("usis-adm-title").textContent = "Audit";
		document.getElementById("usis-adm-actions").innerHTML = navLinks();
		fetchJson("/api/admin/audit").then(function (r) {
			var items = (r.body && r.body.items) || [];
			var html = '<div class="card border-0 shadow-sm"><div class="card-body"><div class="table-responsive"><table class="table table-sm"><thead class="table-light"><tr><th>When</th><th>Action</th><th>Tenant</th><th>Reason</th></tr></thead><tbody>';
			if (!items.length) html += "<tr><td colspan=\"4\" class=\"text-muted\">No audit rows.</td></tr>";
			items.forEach(function (row) {
				html += "<tr><td>" + esc(row.created_at || "") + "</td><td>" + esc(row.action) + "</td><td>" + esc(row.tenant_id || "") + "</td><td>" + esc(row.reason || "") + "</td></tr>";
			});
			html += "</tbody></table></div></div></div>";
			document.getElementById("usis-adm-root").innerHTML = html;
		});
	}

	function boot() {
		var page = pageKind();
		if (page.kind === "tenant") return renderTenant(page.id);
		if (page.kind === "flags") return renderFlags();
		if (page.kind === "health") return renderHealth();
		if (page.kind === "audit") return renderAudit();
		renderList();
	}

	if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
	else boot();
})();
