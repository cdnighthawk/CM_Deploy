/**
 * Platform Admin console — inner left rail + organization workspace.
 */
(function () {
	"use strict";

	var FALLBACK_RAIL = [
		{ id: "overview", path: "/admin", title: "Overview" },
		{ id: "organizations", path: "/admin/organizations", title: "Organizations" },
		{ id: "provision", path: "/admin/provision", title: "Provision" },
		{ id: "plans", path: "/admin/plans", title: "Plans & entitlements" },
		{ id: "flags", path: "/admin/flags", title: "Feature flags" },
		{ id: "usage", path: "/admin/usage", title: "Usage & health" },
		{ id: "support", path: "/admin/support", title: "Support" },
		{ id: "operators", path: "/admin/operators", title: "Operators" },
		{ id: "audit", path: "/admin/audit", title: "Audit" },
		{ id: "policy", path: "/admin/policy", title: "Policy locks" },
	];

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
		var m = p.match(/\/admin\/(?:organizations|tenants)\/([^/]+)/i);
		if (m) return { kind: "tenant", id: decodeURIComponent(m[1]) };
		if (/\/admin\/flags/i.test(p)) return { kind: "flags" };
		if (/\/admin\/(?:usage|health)/i.test(p)) return { kind: "usage" };
		if (/\/admin\/audit/i.test(p)) return { kind: "audit" };
		if (/\/admin\/provision/i.test(p)) return { kind: "provision" };
		if (/\/admin\/plans/i.test(p)) return { kind: "plans" };
		if (/\/admin\/support/i.test(p)) return { kind: "support" };
		if (/\/admin\/operators/i.test(p)) return { kind: "operators" };
		if (/\/admin\/policy/i.test(p)) return { kind: "policy" };
		if (/\/admin\/organizations/i.test(p) || /\/admin\/tenants\/?$/i.test(p)) return { kind: "organizations" };
		return { kind: "overview" };
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

	function healthDot(st) {
		if (st === "ok") return "🟢";
		if (st === "warn") return "🟡";
		return "🔴";
	}

	function renderRail(activeId) {
		var nav = document.getElementById("usis-adm-rail");
		if (!nav) return;
		var html = '<ul class="nav flex-column">';
		FALLBACK_RAIL.forEach(function (t) {
			html +=
				'<li class="nav-item"><a class="nav-link' +
				(t.id === activeId ? " active" : "") +
				'" href="' +
				esc(t.path) +
				'">' +
				esc(t.title) +
				"</a></li>";
		});
		html += "</ul>";
		nav.innerHTML = html;
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

	function kpiCard(label, value) {
		return (
			'<div class="col-md-3"><div class="card border-0 shadow-sm"><div class="card-body py-3"><div class="small text-muted">' +
			esc(label) +
			'</div><div class="h5 mb-0">' +
			esc(value) +
			"</div></div></div></div>"
		);
	}

	function renderOverview() {
		document.getElementById("usis-adm-title").textContent = "Overview";
		document.getElementById("usis-adm-lead").textContent = "Platform health, seats, and recent audit.";
		fetchJson("/api/admin/overview").then(function (r) {
			if (r.status === 403) {
				document.getElementById("usis-adm-forbidden").classList.remove("d-none");
				document.getElementById("usis-adm-root").innerHTML = "";
				return;
			}
			var d = r.body || {};
			var by = d.organizations_by_status || {};
			var seats = d.seats || {};
			var health = d.health || {};
			var html = '<div class="row g-3 mb-3">';
			html += kpiCard("Organizations", d.organization_count || 0);
			html += kpiCard("Trial / active / suspended", (by.trial || 0) + " / " + (by.active || 0) + " / " + (by.suspended || 0));
			html += kpiCard("Office seats", (seats.office_used || 0) + " / " + (seats.office_cap || "—"));
			html += kpiCard("Field seats", (seats.field_used || 0) + " / " + (seats.field_cap || "—"));
			html += kpiCard("Open impersonations", d.open_impersonations || 0);
			html += kpiCard("AI calls today", d.ai_calls_today == null ? "not metered yet" : d.ai_calls_today);
			html += "</div><div class=\"d-flex flex-wrap gap-2 mb-3\">";
			Object.keys(health).forEach(function (k) {
				html +=
					'<span class="badge text-bg-light border">' +
					healthDot(health[k].status) +
					" " +
					esc(k) +
					"</span>";
			});
			html +=
				'</div><div class="card border-0 shadow-sm"><div class="card-body"><h2 class="h6">Last 20 platform audit rows</h2><div class="table-responsive"><table class="table table-sm mb-0"><thead class="table-light"><tr><th>When</th><th>Action</th><th>Reason</th></tr></thead><tbody>';
			(d.audit || []).forEach(function (row) {
				html +=
					"<tr><td>" +
					esc(row.created_at || "") +
					"</td><td>" +
					esc(row.action || "") +
					"</td><td>" +
					esc(row.reason || "") +
					"</td></tr>";
			});
			if (!(d.audit || []).length) html += '<tr><td colspan="3" class="text-muted">No audit rows.</td></tr>';
			html += "</tbody></table></div></div></div>";
			document.getElementById("usis-adm-root").innerHTML = html;
		});
	}

	function renderList() {
		document.getElementById("usis-adm-title").textContent = "Organizations";
		document.getElementById("usis-adm-lead").textContent = "Every subscriber company.";
		fetchJson("/api/admin/organizations").then(function (r) {
			if (r.status === 403) {
				document.getElementById("usis-adm-forbidden").classList.remove("d-none");
				document.getElementById("usis-adm-root").innerHTML = "";
				return;
			}
			var items = (r.body && r.body.items) || [];
			var html = '<div class="card border-0 shadow-sm"><div class="card-body">';
			if (!items.length) {
				html +=
					window.USISUi && window.USISUi.emptyState
						? window.USISUi.emptyState({ title: "No organizations", body: "Provision the first subscriber company." })
						: "<p class=\"text-muted\">No organizations.</p>";
			} else {
				html +=
					'<div class="table-responsive"><table class="table table-sm table-hover align-middle mb-0"><thead class="table-light"><tr><th>Name</th><th>Slug</th><th>Status</th><th>Plan</th><th>Office seats</th><th>Field devices</th><th>Last activity</th></tr></thead><tbody>';
				items.forEach(function (t) {
					var s = t.seats || {};
					html +=
						'<tr style="cursor:pointer" data-href="/admin/organizations/' +
						esc(t.id) +
						'"><td>' +
						esc(t.legal_name || t.name) +
						"</td><td>" +
						esc(t.slug || "") +
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
		});
	}

	function renderTenant(id) {
		document.getElementById("usis-adm-lead").textContent = "Organization workspace.";
		fetchJson("/api/admin/organizations/" + encodeURIComponent(id)).then(function (r) {
			if (!r.ok) {
				document.getElementById("usis-adm-root").innerHTML =
					"<p class=\"text-danger\">" + esc((r.body && r.body.error) || "Not found") + "</p>";
				return;
			}
			var t = r.body.item;
			document.getElementById("usis-adm-title").textContent = t.legal_name || t.name;
			var html = '<div class="card border-0 shadow-sm mb-3"><div class="card-body">';
			html +=
				'<div class="row g-2 mb-3"><div class="col-md-4"><label class="form-label small">Status</label><select class="form-select form-select-sm" id="usis-adm-status">';
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
					fetchJson("/api/admin/organizations/" + encodeURIComponent(id), { method: "PATCH", body: payload }).then(
						function (res) {
							if (!res.ok) return flash((res.body && res.body.error) || "Save failed", "danger");
							flash("Saved.", "success");
						}
					);
				}
				if (danger) askReason("Suspend or close tenant", send);
				else send(payload.reason);
			});
			document.getElementById("usis-adm-impersonate").addEventListener("click", function () {
				askReason("Impersonate " + (t.legal_name || t.name), function (reason) {
					fetchJson("/api/admin/organizations/" + encodeURIComponent(id) + "/impersonate", {
						method: "POST",
						body: { reason: reason },
					}).then(function (res) {
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

	function renderHealth() {
		document.getElementById("usis-adm-title").textContent = "Usage & health";
		fetchJson("/api/admin/usage").then(function (r) {
			var items = (r.body && r.body.items) || {};
			var html = '<div class="card border-0 shadow-sm"><div class="card-body"><ul class="list-unstyled mb-0">';
			Object.keys(items).forEach(function (k) {
				html +=
					"<li class=\"mb-2\">" +
					healthDot(items[k].status) +
					" <strong>" +
					esc(k) +
					"</strong> — " +
					esc(items[k].detail || "") +
					"</li>";
			});
			html += "</ul></div></div>";
			document.getElementById("usis-adm-root").innerHTML = html;
		});
	}

	function renderAudit() {
		document.getElementById("usis-adm-title").textContent = "Audit";
		fetchJson("/api/admin/audit").then(function (r) {
			var items = (r.body && r.body.items) || [];
			var html =
				'<div class="card border-0 shadow-sm"><div class="card-body"><div class="table-responsive"><table class="table table-sm"><thead class="table-light"><tr><th>When</th><th>Action</th><th>Tenant</th><th>Reason</th></tr></thead><tbody>';
			if (!items.length) html += '<tr><td colspan="4" class="text-muted">No audit rows.</td></tr>';
			items.forEach(function (row) {
				html +=
					"<tr><td>" +
					esc(row.created_at || "") +
					"</td><td>" +
					esc(row.action) +
					"</td><td>" +
					esc(row.tenant_id || "") +
					"</td><td>" +
					esc(row.reason || "") +
					"</td></tr>";
			});
			html += "</tbody></table></div></div></div>";
			document.getElementById("usis-adm-root").innerHTML = html;
		});
	}

	function renderProvision() {
		document.getElementById("usis-adm-title").textContent = "Provision";
		document.getElementById("usis-adm-lead").textContent = "Create an Organization. Does not copy USIS jobs or hire packets.";
		var html =
			'<div class="card border-0 shadow-sm"><div class="card-body">' +
			'<div class="mb-3"><label class="form-label small">Legal name</label><input class="form-control form-control-sm" id="usis-adm-prov-name"></div>' +
			'<div class="row g-2 mb-3"><div class="col-md-4"><label class="form-label small">Plan</label><select class="form-select form-select-sm" id="usis-adm-prov-plan"><option value="full">full</option><option value="office">office</option><option value="field">field</option></select></div>' +
			'<div class="col-md-4"><label class="form-label small">Office seats</label><input class="form-control form-control-sm" id="usis-adm-prov-office" value="25"></div>' +
			'<div class="col-md-4"><label class="form-label small">Field seats</label><input class="form-control form-control-sm" id="usis-adm-prov-field" value="25"></div></div>' +
			'<div class="mb-3"><label class="form-label small">First Company Admin email (optional)</label><input class="form-control form-control-sm" id="usis-adm-prov-email" type="email"></div>' +
			'<div class="d-flex justify-content-end"><button type="button" class="btn btn-sm btn-primary" id="usis-adm-prov-go">Create organization</button></div></div></div>';
		document.getElementById("usis-adm-root").innerHTML = html;
		document.getElementById("usis-adm-prov-go").addEventListener("click", function () {
			var name = document.getElementById("usis-adm-prov-name").value;
			if (!name) return flash("Legal name is required.", "danger");
			fetchJson("/api/admin/organizations", {
				method: "POST",
				body: {
					name: name,
					plan_key: document.getElementById("usis-adm-prov-plan").value,
					copy_catalog: false,
				},
			}).then(function (res) {
				if (!res.ok) return flash((res.body && res.body.error) || "Create failed", "danger");
				var id = res.body && res.body.item && res.body.item.id;
				var cap = {
					seat_cap_office: parseInt(document.getElementById("usis-adm-prov-office").value, 10),
					seat_cap_field: parseInt(document.getElementById("usis-adm-prov-field").value, 10),
					reason: "provision seat caps from admin console",
				};
				var next = Promise.resolve();
				if (id) {
					next = fetchJson("/api/admin/organizations/" + encodeURIComponent(id), { method: "PATCH", body: cap });
				}
				next.then(function () {
					flash("Organization created.", "success");
					if (id) window.location.href = "/admin/organizations/" + encodeURIComponent(id);
				});
			});
		});
	}

	function renderPlans() {
		document.getElementById("usis-adm-title").textContent = "Plans & entitlements";
		fetchJson("/api/admin/plans").then(function (r) {
			var items = (r.body && r.body.items) || [];
			var html = '<div class="row g-3">';
			items.forEach(function (p) {
				html +=
					'<div class="col-md-4"><div class="card border-0 shadow-sm"><div class="card-body"><h2 class="h6 text-capitalize">' +
					esc(p.plan_key) +
					'</h2><p class="small text-muted mb-2">Default modules. Per-org overrides stay on the organization workspace.</p><ul class="small mb-0">';
				(p.modules || []).forEach(function (m) {
					html += "<li>" + esc(m) + "</li>";
				});
				html += "</ul></div></div></div>";
			});
			html += "</div>";
			document.getElementById("usis-adm-root").innerHTML = html;
		});
	}

	function renderSupport() {
		document.getElementById("usis-adm-title").textContent = "Support";
		document.getElementById("usis-adm-lead").textContent = "Find an organization. Job files stay hidden until you impersonate.";
		fetchJson("/api/admin/organizations").then(function (r) {
			var items = (r.body && r.body.items) || [];
			var html =
				'<div class="mb-3"><input class="form-control form-control-sm" id="usis-adm-support-q" placeholder="Name, slug, or email"></div>' +
				'<div class="card border-0 shadow-sm"><div class="card-body p-0"><div class="list-group list-group-flush" id="usis-adm-support-list"></div></div></div>';
			document.getElementById("usis-adm-root").innerHTML = html;
			function draw(q) {
				var needle = (q || "").toLowerCase();
				var host = document.getElementById("usis-adm-support-list");
				var rows = items.filter(function (t) {
					if (!needle) return true;
					return (
						String(t.legal_name || t.name || "").toLowerCase().indexOf(needle) >= 0 ||
						String(t.slug || "").toLowerCase().indexOf(needle) >= 0
					);
				});
				host.innerHTML = rows
					.map(function (t) {
						return (
							'<div class="list-group-item d-flex justify-content-between align-items-center"><div><strong>' +
							esc(t.legal_name || t.name) +
							"</strong> <span class=\"text-muted small\">" +
							esc(t.slug) +
							" · " +
							esc(t.plan_key) +
							"</span></div><div><a class=\"btn btn-sm btn-outline-secondary me-1\" href=\"/admin/organizations/" +
							esc(t.id) +
							'">Open</a><button type="button" class="btn btn-sm btn-outline-primary usis-adm-sup-imp" data-id="' +
							esc(t.id) +
							'" data-name="' +
							esc(t.legal_name || t.name) +
							'">Impersonate</button></div></div>'
						);
					})
					.join("") || '<div class="p-3 text-muted">No matches.</div>';
				document.querySelectorAll(".usis-adm-sup-imp").forEach(function (btn) {
					btn.addEventListener("click", function () {
						askReason("Impersonate " + btn.getAttribute("data-name"), function (reason) {
							fetchJson("/api/admin/organizations/" + encodeURIComponent(btn.getAttribute("data-id")) + "/impersonate", {
								method: "POST",
								body: { reason: reason },
							}).then(function (res) {
								if (!res.ok) return flash((res.body && res.body.error) || "Failed", "danger");
								window.location.href = "/settings";
							});
						});
					});
				});
			}
			draw("");
			document.getElementById("usis-adm-support-q").addEventListener("input", function (ev) {
				draw(ev.target.value);
			});
		});
	}

	function renderOperators() {
		document.getElementById("usis-adm-title").textContent = "Operators";
		document.getElementById("usis-adm-root").innerHTML =
			window.USISUi && window.USISUi.emptyState
				? window.USISUi.emptyState({
						title: "Operator list",
						body: "Add and remove platform operators in a later slice. One operator flag is enough for v2 until then.",
					})
				: "<p class=\"text-muted\">Operator list ships in a later slice.</p>";
	}

	function renderPolicy() {
		document.getElementById("usis-adm-title").textContent = "Policy locks";
		document.getElementById("usis-adm-lead").textContent = "These keys can never be set true.";
		fetchJson("/api/admin/policy").then(function (r) {
			var items = (r.body && r.body.items) || [];
			var html = '<div class="card border-0 shadow-sm"><div class="card-body"><ul class="mb-0">';
			items.forEach(function (it) {
				html += "<li><code>" + esc(it.key) + "</code> — " + esc(it.message || "locked") + "</li>";
			});
			html += "</ul></div></div>";
			document.getElementById("usis-adm-root").innerHTML = html;
		});
	}

	function boot() {
		var page = pageKind();
		var railId = page.kind === "tenant" ? "organizations" : page.kind;
		renderRail(railId);
		if (page.kind === "tenant") return renderTenant(page.id);
		if (page.kind === "flags") return renderFlags();
		if (page.kind === "usage") return renderHealth();
		if (page.kind === "audit") return renderAudit();
		if (page.kind === "provision") return renderProvision();
		if (page.kind === "plans") return renderPlans();
		if (page.kind === "support") return renderSupport();
		if (page.kind === "operators") return renderOperators();
		if (page.kind === "policy") return renderPolicy();
		if (page.kind === "organizations") return renderList();
		renderOverview();
	}

	if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
	else boot();
})();
