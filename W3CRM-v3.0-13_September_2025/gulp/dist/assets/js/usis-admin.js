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
		Promise.all([
			fetchJson("/api/admin/organizations/" + encodeURIComponent(id)),
			fetchJson("/api/admin/organizations/" + encodeURIComponent(id) + "/notes"),
			fetchJson("/api/admin/users".indexOf("x") < 0 ? "/api/admin/organizations" : "/api/admin/organizations"),
		]).then(function (pair) {
			var r = pair[0];
			if (!r.ok) {
				document.getElementById("usis-adm-root").innerHTML =
					"<p class=\"text-danger\">" + esc((r.body && r.body.error) || "Not found") + "</p>";
				return;
			}
			var t = r.body.item;
			var notes = (pair[1].ok && pair[1].body && pair[1].body.items) || [];
			document.getElementById("usis-adm-title").textContent = t.legal_name || t.name;
			var tabs = ["profile", "plan", "entitlements", "flags", "seats", "usage", "notes", "audit", "danger"];
			var hash = (window.location.hash || "#profile").replace("#", "");
			if (tabs.indexOf(hash) < 0) hash = "profile";
			var html = '<ul class="nav nav-tabs mb-3" id="usis-adm-tabs">';
			tabs.forEach(function (tab) {
				html +=
					'<li class="nav-item"><a class="nav-link' +
					(tab === hash ? " active" : "") +
					'" href="#"' +
					' data-tab="' +
					tab +
					'">' +
					tab.charAt(0).toUpperCase() +
					tab.slice(1) +
					"</a></li>";
			});
			html += '</ul><div id="usis-adm-tab"></div>';
			document.getElementById("usis-adm-root").innerHTML = html;

			function draw(tab) {
				var box = document.getElementById("usis-adm-tab");
				var inner = "";
				if (tab === "profile") {
					inner =
						'<div class="card border-0 shadow-sm"><div class="card-body">' +
						'<div class="row g-2"><div class="col-md-6"><label class="form-label small">Legal name</label><input class="form-control form-control-sm" id="usis-adm-legal" value="' +
						esc(t.legal_name || t.name) +
						'"></div><div class="col-md-6"><label class="form-label small">Slug (read-only)</label><input class="form-control form-control-sm" disabled value="' +
						esc(t.slug) +
						'"></div></div>' +
						'<div class="mt-3"><h3 class="h6">Approved send domains</h3><ul>';
					(t.send_domains || []).forEach(function (d) {
						inner += "<li><code>" + esc(d.domain) + "</code> — " + esc(d.status) + "</li>";
					});
					if (!(t.send_domains || []).length) inner += '<li class="text-muted">gousis.com (default)</li>';
					inner +=
						'</ul><div class="input-group input-group-sm"><input class="form-control" id="usis-adm-domain" placeholder="contractor.com"><select class="form-select" id="usis-adm-domain-st"><option value="live">live</option><option value="pending">pending</option><option value="revoked">revoked</option></select><button type="button" class="btn btn-outline-primary" id="usis-adm-domain-go">Set</button></div></div>' +
						'<div class="d-flex justify-content-end mt-3"><button type="button" class="btn btn-sm btn-primary" id="usis-adm-save-profile">Save profile</button></div></div></div>';
				} else if (tab === "plan") {
					inner =
						'<div class="card border-0 shadow-sm"><div class="card-body"><label class="form-label small">Plan</label><select class="form-select form-select-sm" id="usis-adm-plan">';
					["field", "office", "full"].forEach(function (pk) {
						inner += '<option value="' + pk + '"' + (t.plan_key === pk ? " selected" : "") + ">" + pk + "</option>";
					});
					inner +=
						'</select><p class="small text-muted mt-2">Changing plan previews which modules turn off. Per-org entitlement overrides stay.</p><button type="button" class="btn btn-sm btn-primary" id="usis-adm-save-plan">Save plan</button></div></div>';
				} else if (tab === "entitlements") {
					inner = '<div class="card border-0 shadow-sm"><div class="card-body"><div class="row">';
					Object.keys(t.entitlements || {}).forEach(function (k) {
						inner +=
							'<div class="col-md-4"><div class="form-check"><input class="form-check-input usis-adm-ent" type="checkbox" data-key="' +
							esc(k) +
							'"' +
							(t.entitlements[k] ? " checked" : "") +
							'><label class="form-check-label">' +
							esc(k) +
							"</label></div></div>";
					});
					inner += '</div><button type="button" class="btn btn-sm btn-primary mt-3" id="usis-adm-save-ent">Save entitlements</button></div></div>';
				} else if (tab === "flags") {
					inner = '<div class="card border-0 shadow-sm"><div class="card-body">';
					Object.keys(t.flags || {}).forEach(function (k) {
						inner +=
							'<div class="form-check"><input class="form-check-input usis-adm-flag" type="checkbox" data-key="' +
							esc(k) +
							'"' +
							(t.flags[k] ? " checked" : "") +
							"><label class=\"form-check-label\">" +
							esc(k) +
							"</label></div>";
					});
					inner += "</div></div>";
				} else if (tab === "seats") {
					var s = t.seats || {};
					inner =
						'<div class="card border-0 shadow-sm"><div class="card-body"><p>Office ' +
						esc((s.office_used || 0) + " / " + (s.office_cap || t.seat_cap_office)) +
						" · Field " +
						esc((s.field_used || 0) + " / " + (s.field_cap || t.seat_cap_field)) +
						'</p><div class="row g-2"><div class="col-md-4"><label class="form-label small">Office cap</label><input class="form-control form-control-sm" id="usis-adm-cap-office" value="' +
						esc(t.seat_cap_office) +
						'"></div><div class="col-md-4"><label class="form-label small">Field cap</label><input class="form-control form-control-sm" id="usis-adm-cap-field" value="' +
						esc(t.seat_cap_field) +
						'"></div></div><button type="button" class="btn btn-sm btn-primary mt-3" id="usis-adm-save-seats">Save caps</button>' +
						'<hr><h3 class="h6">Temporary overage</h3><div class="row g-2"><div class="col-md-4"><select class="form-select form-select-sm" id="usis-ov-kind"><option value="office">office</option><option value="field">field</option></select></div>' +
						'<div class="col-md-4"><input class="form-control form-control-sm" id="usis-ov-exp" type="datetime-local"></div>' +
						'<div class="col-md-4"><button type="button" class="btn btn-sm btn-outline-primary" id="usis-ov-go">Grant</button></div></div></div></div>';
				} else if (tab === "usage") {
					inner = '<div class="card border-0 shadow-sm"><div class="card-body"><ul class="mb-0">';
					Object.keys(t.usage || {}).forEach(function (k) {
						inner += "<li>" + esc(k) + " — " + esc(t.usage[k]) + "</li>";
					});
					inner += "</ul></div></div>";
				} else if (tab === "notes") {
					inner =
						'<div class="card border-0 shadow-sm"><div class="card-body"><textarea class="form-control form-control-sm mb-2" id="usis-note" rows="3" placeholder="Operator note (not visible to the contractor)"></textarea><button type="button" class="btn btn-sm btn-primary mb-3" id="usis-note-go">Add note</button><ul class="mb-0">';
					notes.forEach(function (n) {
						inner += "<li><span class=\"text-muted small\">" + esc(n.created_at || "") + "</span> " + esc(n.body) + "</li>";
					});
					if (!notes.length) inner += '<li class="text-muted">No notes yet.</li>';
					inner += "</ul></div></div>";
				} else if (tab === "audit") {
					inner = '<p class="small"><a href="/api/admin/audit.csv?tenant_id=' + encodeURIComponent(id) + '">Export CSV</a></p><div id="usis-org-audit"></div>';
				} else if (tab === "danger") {
					inner =
						'<div class="card border-0 shadow-sm border-danger"><div class="card-body">' +
						'<p class="small text-muted">Danger routes require a reason of at least 12 characters. Wipe queues a job; it does not delete in this request.</p>' +
						'<div class="d-flex flex-wrap gap-2">' +
						'<button type="button" class="btn btn-sm btn-outline-warning" id="usis-d-sus">Suspend</button>' +
						'<button type="button" class="btn btn-sm btn-outline-success" id="usis-d-act">Reactivate</button>' +
						'<button type="button" class="btn btn-sm btn-outline-secondary" id="usis-d-exp">Queue export</button>' +
						'<button type="button" class="btn btn-sm btn-outline-danger" id="usis-d-wipe">Queue wipe</button>' +
						'<button type="button" class="btn btn-sm btn-danger" id="usis-d-close">Close</button></div></div></div>';
				}
				box.innerHTML = inner;
				function patch(payload, reasonNeeded) {
					function send(reason) {
						payload.reason = reason || payload.reason || "platform tenant update from admin";
						fetchJson("/api/admin/organizations/" + encodeURIComponent(id), { method: "PATCH", body: payload }).then(
							function (res) {
								if (!res.ok) return flash((res.body && res.body.error) || "Save failed", "danger");
								flash("Saved.", "success");
							}
						);
					}
					if (reasonNeeded) askReason("Confirm", send);
					else send(payload.reason);
				}
				var el;
				el = document.getElementById("usis-adm-save-profile");
				if (el)
					el.onclick = function () {
						patch({ legal_name: document.getElementById("usis-adm-legal").value, reason: "profile update from admin" });
					};
				el = document.getElementById("usis-adm-domain-go");
				if (el)
					el.onclick = function () {
						fetchJson("/api/admin/organizations/" + encodeURIComponent(id) + "/send-domains", {
							method: "POST",
							body: {
								domain: document.getElementById("usis-adm-domain").value,
								status: document.getElementById("usis-adm-domain-st").value,
							},
						}).then(function (res) {
							if (!res.ok) return flash((res.body && res.body.error) || "Failed", "danger");
							flash("Send domain saved.", "success");
						});
					};
				el = document.getElementById("usis-adm-save-plan");
				if (el)
					el.onclick = function () {
						askReason("Change plan", function (reason) {
							patch({ plan_key: document.getElementById("usis-adm-plan").value, reason: reason }, false);
						});
					};
				el = document.getElementById("usis-adm-save-ent");
				if (el)
					el.onclick = function () {
						var ents = {};
						document.querySelectorAll(".usis-adm-ent").forEach(function (cb) {
							ents[cb.getAttribute("data-key")] = cb.checked;
						});
						patch({ entitlements: ents, reason: "entitlement override from admin" });
					};
				document.querySelectorAll(".usis-adm-flag").forEach(function (cb) {
					cb.addEventListener("change", function () {
						askReason("Override flag " + cb.getAttribute("data-key"), function (reason) {
							fetchJson("/api/admin/flags/" + encodeURIComponent(cb.getAttribute("data-key")), {
								method: "PUT",
								body: { tenant_id: id, value: cb.checked, reason: reason },
							}).then(function (res) {
								if (!res.ok) flash((res.body && res.body.error) || "Failed", "danger");
								else flash("Flag saved.", "success");
							});
						});
					});
				});
				el = document.getElementById("usis-adm-save-seats");
				if (el)
					el.onclick = function () {
						askReason("Change seat caps", function (reason) {
							patch({
								seat_cap_office: parseInt(document.getElementById("usis-adm-cap-office").value, 10),
								seat_cap_field: parseInt(document.getElementById("usis-adm-cap-field").value, 10),
								reason: reason,
							});
						});
					};
				el = document.getElementById("usis-ov-go");
				if (el)
					el.onclick = function () {
						askReason("Grant overage", function (reason) {
							fetchJson("/api/admin/organizations/" + encodeURIComponent(id) + "/overage", {
								method: "POST",
								body: {
									seat_kind: document.getElementById("usis-ov-kind").value,
									expires_at: document.getElementById("usis-ov-exp").value,
									reason: reason,
								},
							}).then(function (res) {
								if (!res.ok) return flash((res.body && res.body.error) || "Failed", "danger");
								flash("Overage granted.", "success");
							});
						});
					};
				el = document.getElementById("usis-note-go");
				if (el)
					el.onclick = function () {
						fetchJson("/api/admin/organizations/" + encodeURIComponent(id) + "/notes", {
							method: "POST",
							body: { body: document.getElementById("usis-note").value },
						}).then(function (res) {
							if (!res.ok) return flash((res.body && res.body.error) || "Failed", "danger");
							flash("Note added.", "success");
						});
					};
				if (tab === "audit") {
					fetchJson("/api/admin/audit?tenant_id=" + encodeURIComponent(id)).then(function (res) {
						var rows = (res.body && res.body.items) || [];
						var h = '<table class="table table-sm"><thead><tr><th>When</th><th>Action</th><th>Reason</th></tr></thead><tbody>';
						rows.forEach(function (row) {
							h += "<tr><td>" + esc(row.created_at || "") + "</td><td>" + esc(row.action) + "</td><td>" + esc(row.reason || "") + "</td></tr>";
						});
						document.getElementById("usis-org-audit").innerHTML = h + "</tbody></table>";
					});
				}
				function danger(path, extra) {
					askReason("Danger: " + path, function (reason) {
						var body = Object.assign({ reason: reason }, extra || {});
						fetchJson("/api/admin/organizations/" + encodeURIComponent(id) + path, { method: "POST", body: body }).then(
							function (res) {
								if (!res.ok) return flash((res.body && res.body.error) || "Failed", "danger");
								flash("Queued / updated.", "success");
							}
						);
					});
				}
				el = document.getElementById("usis-d-sus");
				if (el) el.onclick = function () {
					danger("/suspend");
				};
				el = document.getElementById("usis-d-act");
				if (el) el.onclick = function () {
					danger("/reactivate");
				};
				el = document.getElementById("usis-d-exp");
				if (el) el.onclick = function () {
					danger("/export");
				};
				el = document.getElementById("usis-d-wipe");
				if (el) el.onclick = function () {
					danger("/wipe");
				};
				el = document.getElementById("usis-d-close");
				if (el) el.onclick = function () {
					danger("/close", { type: "CLOSE" });
				};
			}
			document.querySelectorAll("#usis-adm-tabs [data-tab]").forEach(function (a) {
				a.addEventListener("click", function (ev) {
					ev.preventDefault();
					document.querySelectorAll("#usis-adm-tabs .nav-link").forEach(function (x) {
						x.classList.remove("active");
					});
					a.classList.add("active");
					draw(a.getAttribute("data-tab"));
				});
			});
			draw(hash);
		});
	}

	function renderFlags() {
		document.getElementById("usis-adm-title").textContent = "Feature flags";
		document.getElementById("usis-adm-lead").textContent = "Default column plus per-organization overrides. Click a cell to change.";
		fetchJson("/api/admin/flags/matrix").then(function (r) {
			var keys = (r.body && r.body.keys) || [];
			var defaults = (r.body && r.body.defaults) || {};
			var orgs = (r.body && r.body.organizations) || [];
			var html = '<div class="table-responsive"><table class="table table-sm table-bordered"><thead><tr><th>Organization</th>';
			keys.forEach(function (k) {
				html += "<th class=\"small\">" + esc(k) + "<div class=\"text-muted\">def " + (defaults[k] ? "on" : "off") + "</div></th>";
			});
			html += "</tr></thead><tbody>";
			orgs.forEach(function (o) {
				html += "<tr><td>" + esc(o.name) + " <code>" + esc(o.slug) + "</code></td>";
				keys.forEach(function (k) {
					var on = o.flags && o.flags[k];
					html +=
						'<td class="text-center usis-flag-cell" style="cursor:pointer" data-org="' +
						esc(o.tenant_id) +
						'" data-key="' +
						esc(k) +
						'" data-on="' +
						(on ? "1" : "0") +
						'">' +
						(on ? "●" : "○") +
						"</td>";
				});
				html += "</tr>";
			});
			html += "</tbody></table></div>";
			document.getElementById("usis-adm-root").innerHTML = html || "<p class=\"text-muted\">No flags.</p>";
			document.querySelectorAll(".usis-flag-cell").forEach(function (td) {
				td.addEventListener("click", function () {
					var on = td.getAttribute("data-on") === "1";
					askReason("Override " + td.getAttribute("data-key"), function (reason) {
						fetchJson("/api/admin/flags/" + encodeURIComponent(td.getAttribute("data-key")), {
							method: "PUT",
							body: { tenant_id: td.getAttribute("data-org"), value: !on, reason: reason },
						}).then(function (res) {
							if (!res.ok) return flash((res.body && res.body.error) || "Failed", "danger");
							td.setAttribute("data-on", on ? "0" : "1");
							td.textContent = on ? "○" : "●";
							flash("Flag saved.", "success");
						});
					});
				});
			});
		});
	}

	function renderHealth() {
		document.getElementById("usis-adm-title").textContent = "Usage & health";
		Promise.all([fetchJson("/api/admin/usage"), fetchJson("/api/admin/usage/meters")]).then(function (pair) {
			var items = (pair[0].body && pair[0].body.items) || {};
			var meters = (pair[1].body && pair[1].body.items) || {};
			var html = '<div class="card border-0 shadow-sm mb-3"><div class="card-body"><h2 class="h6">Health</h2><ul class="list-unstyled mb-0">';
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
			html += '</ul></div></div><div class="card border-0 shadow-sm"><div class="card-body"><h2 class="h6">Meters</h2><ul class="mb-0">';
			Object.keys(meters).forEach(function (k) {
				html += "<li>" + esc(k) + " — " + esc((meters[k] && meters[k].label) || "not metered yet") + "</li>";
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
				'<div class="d-flex justify-content-end mb-2"><a class="btn btn-sm btn-outline-secondary" href="/api/admin/audit.csv">Export CSV</a></div>' +
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
			'<div class="mb-3"><label class="form-label small">Slug (optional)</label><input class="form-control form-control-sm" id="usis-adm-prov-slug"></div>' +
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
					slug: document.getElementById("usis-adm-prov-slug").value,
					plan_key: document.getElementById("usis-adm-prov-plan").value,
					seat_cap_office: parseInt(document.getElementById("usis-adm-prov-office").value, 10),
					seat_cap_field: parseInt(document.getElementById("usis-adm-prov-field").value, 10),
					admin_email: document.getElementById("usis-adm-prov-email").value,
					copy_catalog: false,
				},
			}).then(function (res) {
				if (!res.ok) return flash((res.body && res.body.error) || "Create failed", "danger");
				var id = res.body && res.body.item && res.body.item.id;
				flash("Organization created.", "success");
				if (id) window.location.href = "/admin/organizations/" + encodeURIComponent(id);
			});
		});
	}

	function renderPlans() {
		document.getElementById("usis-adm-title").textContent = "Plans & entitlements";
		fetchJson("/api/admin/plans").then(function (r) {
			var items = (r.body && r.body.items) || [];
			var all = (r.body && r.body.all_modules) || [];
			var html = '<div class="row g-3">';
			items.forEach(function (p) {
				html +=
					'<div class="col-md-4"><div class="card border-0 shadow-sm"><div class="card-body"><h2 class="h6 text-capitalize">' +
					esc(p.plan_key) +
					'</h2><p class="small text-muted mb-2">Changing defaults does not silently strip a company that has an explicit override.</p>';
				all.forEach(function (m) {
					var on = (p.modules || []).indexOf(m) >= 0;
					html +=
						'<div class="form-check"><input class="form-check-input usis-plan-mod" type="checkbox" data-plan="' +
						esc(p.plan_key) +
						'" data-mod="' +
						esc(m) +
						'"' +
						(on ? " checked" : "") +
						'><label class="form-check-label small">' +
						esc(m) +
						"</label></div>";
				});
				html +=
					'<button type="button" class="btn btn-sm btn-primary mt-2 usis-plan-save" data-plan="' +
					esc(p.plan_key) +
					'">Save</button></div></div></div>';
			});
			html += "</div>";
			document.getElementById("usis-adm-root").innerHTML = html;
			document.querySelectorAll(".usis-plan-save").forEach(function (btn) {
				btn.addEventListener("click", function () {
					var pk = btn.getAttribute("data-plan");
					var mods = [];
					document.querySelectorAll('.usis-plan-mod[data-plan="' + pk + '"]').forEach(function (cb) {
						if (cb.checked) mods.push(cb.getAttribute("data-mod"));
					});
					fetchJson("/api/admin/plans/" + encodeURIComponent(pk), { method: "PUT", body: { modules: mods } }).then(
						function (res) {
							if (!res.ok) return flash((res.body && res.body.error) || "Failed", "danger");
							flash("Plan defaults saved.", "success");
						}
					);
				});
			});
		});
	}

	function renderSupport() {
		document.getElementById("usis-adm-title").textContent = "Support";
		document.getElementById("usis-adm-lead").textContent = "Find an organization. Job files stay hidden until you impersonate.";
		Promise.all([fetchJson("/api/admin/organizations"), fetchJson("/api/admin/impersonate/sessions")]).then(function (pair) {
			var items = (pair[0].body && pair[0].body.items) || [];
			var sessions = (pair[1].body && pair[1].body.items) || [];
			var html =
				'<div class="mb-3"><input class="form-control form-control-sm" id="usis-adm-support-q" placeholder="Name, slug, or email"></div>' +
				'<div class="card border-0 shadow-sm mb-3"><div class="card-body p-0"><div class="list-group list-group-flush" id="usis-adm-support-list"></div></div></div>' +
				'<div class="card border-0 shadow-sm"><div class="card-body"><h2 class="h6">Active impersonations</h2><div id="usis-adm-sessions"></div></div></div>';
			document.getElementById("usis-adm-root").innerHTML = html;
			function drawSessions() {
				var host = document.getElementById("usis-adm-sessions");
				if (!sessions.length) {
					host.innerHTML = '<p class="text-muted mb-0">None open.</p>';
					return;
				}
				host.innerHTML = sessions
					.map(function (s) {
						return (
							'<div class="d-flex justify-content-between align-items-center border-bottom py-2"><div>' +
							esc(s.tenant_name || "") +
							" · " +
							esc(s.operator_email || "") +
							(s.target_email ? " as " + esc(s.target_email) : "") +
							'</div><button type="button" class="btn btn-sm btn-outline-danger usis-sess-end" data-id="' +
							esc(s.id) +
							'">Force end</button></div>'
						);
					})
					.join("");
				document.querySelectorAll(".usis-sess-end").forEach(function (btn) {
					btn.addEventListener("click", function () {
						fetchJson("/api/admin/impersonate/" + encodeURIComponent(btn.getAttribute("data-id")) + "/end", {
							method: "POST",
							body: {},
						}).then(function (res) {
							if (!res.ok) return flash((res.body && res.body.error) || "Failed", "danger");
							flash("Session ended.", "success");
							btn.closest("div").remove();
						});
					});
				});
			}
			drawSessions();
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
							'<div class="list-group-item"><div class="d-flex justify-content-between align-items-center"><div><strong>' +
							esc(t.legal_name || t.name) +
							"</strong> <span class=\"text-muted small\">" +
							esc(t.slug) +
							" · " +
							esc(t.plan_key) +
							'</span></div><div><a class="btn btn-sm btn-outline-secondary me-1" href="/admin/organizations/' +
							esc(t.id) +
							'">Open</a><button type="button" class="btn btn-sm btn-outline-primary usis-adm-sup-imp" data-id="' +
							esc(t.id) +
							'" data-name="' +
							esc(t.legal_name || t.name) +
							'">Impersonate tenant</button></div></div>' +
							'<div class="mt-2 input-group input-group-sm"><input class="form-control usis-as-user" data-id="' +
							esc(t.id) +
							'" placeholder="Target user UUID (impersonate as named user)"><button type="button" class="btn btn-outline-primary usis-as-user-go" data-id="' +
							esc(t.id) +
							'" data-name="' +
							esc(t.legal_name || t.name) +
							'">As user</button></div></div>'
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
				document.querySelectorAll(".usis-as-user-go").forEach(function (btn) {
					btn.addEventListener("click", function () {
						var input = document.querySelector('.usis-as-user[data-id="' + btn.getAttribute("data-id") + '"]');
						var uid = input ? input.value.trim() : "";
						if (!uid) return flash("Target user id required.", "danger");
						askReason("Viewing as user @ " + btn.getAttribute("data-name"), function (reason) {
							fetchJson("/api/admin/organizations/" + encodeURIComponent(btn.getAttribute("data-id")) + "/impersonate", {
								method: "POST",
								body: { reason: reason, target_user_id: uid },
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
		document.getElementById("usis-adm-lead").textContent = "Users with is_platform_operator. Cannot remove the last operator.";
		fetchJson("/api/admin/operators").then(function (r) {
			var items = (r.body && r.body.items) || [];
			var html =
				'<div class="input-group input-group-sm mb-3"><input class="form-control" id="usis-op-email" placeholder="user email"><button type="button" class="btn btn-primary" id="usis-op-add">Add operator</button></div>' +
				'<div class="card border-0 shadow-sm"><div class="card-body"><ul class="list-unstyled mb-0">';
			items.forEach(function (u) {
				html +=
					'<li class="d-flex justify-content-between align-items-center border-bottom py-2"><span>' +
					esc(u.name) +
					" <code>" +
					esc(u.email) +
					'</code></span><button type="button" class="btn btn-sm btn-outline-danger usis-op-del" data-id="' +
					esc(u.id) +
					'">Remove</button></li>';
			});
			if (!items.length) html += '<li class="text-muted">No operators.</li>';
			html += "</ul></div></div>";
			document.getElementById("usis-adm-root").innerHTML = html;
			document.getElementById("usis-op-add").addEventListener("click", function () {
				fetchJson("/api/admin/operators", {
					method: "POST",
					body: { email: document.getElementById("usis-op-email").value },
				}).then(function (res) {
					if (!res.ok) return flash((res.body && res.body.error) || "Failed", "danger");
					flash("Operator added.", "success");
					renderOperators();
				});
			});
			document.querySelectorAll(".usis-op-del").forEach(function (btn) {
				btn.addEventListener("click", function () {
					fetch(apiBase() + "/api/admin/operators/" + encodeURIComponent(btn.getAttribute("data-id")), {
						method: "DELETE",
						credentials: "include",
						headers: { Accept: "application/json" },
					})
						.then(function (res) {
							return res.json().then(function (j) {
								return { ok: res.ok, body: j };
							});
						})
						.then(function (res) {
							if (!res.ok) return flash((res.body && res.body.error) || "Failed", "danger");
							flash("Operator removed.", "success");
							renderOperators();
						});
				});
			});
		});
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
