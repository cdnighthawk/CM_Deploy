/**
 * Contractor Settings console — inner left rail + one editor per section.
 */
(function () {
	"use strict";

	var ALIASES = { users: "people", security: "people", senders: "mail", workflows: "money" };
	var FIELD_LABELS = {
		"company.legal_name": "Legal name",
		"company.dba": "DBA",
		"company.cslb": "CSLB",
		"company.timezone": "Timezone",
		"company.logo_document_id": "Logo document id",
		"company.letterhead_document_id": "Letterhead document id",
		"company.offices": "Offices (one per line: name | address)",
		"company.public_hostname": "Public hostname (request)",
		"company.public_hostname_status": "Hostname status",
		"public.legal_footer": "Legal footer (public RFP / hire / T&M)",
		"estimate.stage_labels": "Estimate stage labels (JSON)",
		"project.default_trades": "Default trades",
		"project.who_may_create": "Who may create projects",
		"time.require_cost_code": "Require cost code on punch",
		"field.geofence_mode": "Geofence mode (flag | block)",
		"field.signoff_required": "End-of-day sign-off required",
		"tm.requires_co": "T&M tickets require a change order",
		"punch.auto_push_procore": "Auto-push punch list to Procore",
		"mail.rfp.from_address": "RFP From address",
		"mail.rfp.from_name": "RFP From name",
		"mail.rfp.bcc_self": "BCC self on RFP send",
		"mail.field.from_address": "Field From address",
		"mail.hire.from_address": "Hire From address",
		"mail.allow_mailboxes": "Allow-listed M365 mailboxes",
		"mail.spam_confidence_move": "Spam move threshold",
		"mail.never_auto_spam_domains": "Never-auto-spam domains",
		"mail.never_auto_spam_subjects": "Never-auto-spam subject tokens",
		"correspondence.teams_ingest": "Teams ingest",
		"public.rfp_token_ttl_hours": "RFP token TTL (hours)",
		"public.hire_token_ttl_hours": "Hire token TTL (hours)",
		"public.tm_token_ttl_hours": "T&M token TTL (hours)",
		"files.spec_split_roles": "Spec-split roles",
		"hire.w4_edition": "W-4 edition",
		"hire.i9_edition": "I-9 edition",
		"hire.ssn_on_user": "Store SSN on User",
		"qb.employee_add": "QuickBooks EmployeeAdd",
		"edd.auto_file": "EDD auto-file",
		"qb.company_file_name": "QB company file name",
		"ai.default_provider": "Default provider (grok | local)",
		"ai.mode.construction_review": "Construction review",
		"ai.mode.estimating_review": "Estimating review",
		"ai.mode.spec_package_review": "Spec package review",
		"ai.mode.submittal_review": "Submittal review",
		"ai.mode.bid_feasibility": "Bid feasibility",
		"ai.mode.email_classify": "Email leftover classify",
		"ai.mode.door_schedule_extract": "Door schedule extract",
		"ai.mode.hardware_set_extract": "Hardware set extract",
		"ai.submittal_rubber_stamp_seconds": "Rubber-stamp seconds",
		"ai.email_scan_cap_per_run": "7-day scan cap",
		"ai.dump_correspondence_to_grok": "Dump correspondence to Grok",
		"po.skip_down": "PO skip-down",
	};
	var FALLBACK_RAIL = [
		{ id: "overview", path: "/settings", title: "Overview" },
		{ id: "company", path: "/settings/company", title: "Company" },
		{ id: "people", path: "/settings/people", title: "People & access" },
		{ id: "roles", path: "/settings/roles", title: "Roles & templates" },
		{ id: "projects", path: "/settings/projects", title: "Projects & defaults" },
		{ id: "money", path: "/settings/money", title: "Money & workflows" },
		{ id: "mail", path: "/settings/mail", title: "Mail & senders" },
		{ id: "correspondence", path: "/settings/correspondence", title: "Correspondence" },
		{ id: "files", path: "/settings/files", title: "Files & public links" },
		{ id: "time-field", path: "/settings/time-field", title: "Time & field" },
		{ id: "hiring", path: "/settings/hiring", title: "Hiring" },
		{ id: "ai", path: "/settings/ai", title: "AI" },
		{ id: "integrations", path: "/settings/integrations", title: "Integrations" },
		{ id: "audit", path: "/settings/audit", title: "Audit" },
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

	function sectionFromPath() {
		var p = (window.location.pathname || "").replace(/\\/g, "/");
		var m = p.match(/\/settings\/([a-z0-9-]+)/i);
		if (!m) return "overview";
		var id = m[1].toLowerCase();
		return ALIASES[id] || id;
	}

	function flash(msg, kind) {
		var el = document.getElementById("usis-set-flash");
		if (!el) return;
		el.className = "alert py-2 px-3 mb-3 alert-" + (kind || "success");
		el.textContent = msg;
		el.classList.remove("d-none");
	}

	function byKey(pack) {
		var map = {};
		(pack.items || []).forEach(function (it) {
			map[it.key] = it;
		});
		return map;
	}

	function findSection(rail, id) {
		var found = null;
		(rail || []).forEach(function (t) {
			if (t.id === id) found = t;
			(t.aliases || []).forEach(function (a) {
				if (a === id) found = t;
			});
		});
		return found;
	}

	function renderRail(rail, activeId) {
		var nav = document.getElementById("usis-set-rail");
		if (!nav) return;
		var html = '<ul class="nav flex-column">';
		(rail || FALLBACK_RAIL).forEach(function (t) {
			html +=
				'<li class="nav-item"><a class="nav-link' +
				(t.id === activeId ? " active" : "") +
				'" href="' +
				esc(t.path || "/settings/" + t.id) +
				'">' +
				esc(t.title) +
				"</a></li>";
		});
		html += "</ul>";
		nav.innerHTML = html;
	}

	function fieldControl(item) {
		var key = item.key;
		var val = item.value;
		var locked = !!item.locked;
		var dis = locked ? " disabled" : "";
		var help = locked ? '<div class="form-text text-muted">Platform policy — cannot be changed.</div>' : "";
		if (key === "ai.dump_correspondence_to_grok") {
			help = '<div class="form-text text-muted">Locked false. Correspondence is never dumped to Grok.</div>';
		}
		if (key === "po.skip_down" || key === "punch.auto_push_procore") {
			help = '<div class="form-text text-muted">Platform policy — locked false.</div>';
		}
		if (key === "hire.ssn_on_user" || key === "qb.employee_add" || key === "edd.auto_file") {
			help = '<div class="form-text text-muted">Platform policy — cannot be changed.</div>';
		}
		var label = FIELD_LABELS[key] || key;
		var id = "set-" + key.replace(/\./g, "-");
		if (typeof val === "boolean" || key.indexOf("ai.mode.") === 0 || key.indexOf("mail.rfp.bcc") === 0) {
			return (
				'<div class="form-check mb-3">' +
				'<input class="form-check-input usis-set-field" type="checkbox" id="' +
				id +
				'" data-key="' +
				esc(key) +
				'" data-type="bool"' +
				(val ? " checked" : "") +
				dis +
				">" +
				'<label class="form-check-label" for="' +
				id +
				'">' +
				esc(label) +
				"</label>" +
				help +
				"</div>"
			);
		}
		if (
			Array.isArray(val) ||
			key.indexOf("never_auto") >= 0 ||
			key === "mail.allow_mailboxes" ||
			key === "company.offices" ||
			key === "security.mfa_required_roles" ||
			key === "files.spec_split_roles" ||
			key === "estimate.stage_labels" ||
			key === "project.default_trades" ||
			key === "project.who_may_create"
		) {
			var text = Array.isArray(val)
				? val.join("\n")
				: typeof val === "object" && val
					? JSON.stringify(val, null, 2)
					: String(val || "");
			if (key === "company.offices") text = JSON.stringify(val || [], null, 2);
			if (key === "estimate.stage_labels") text = JSON.stringify(val || {}, null, 2);
			return (
				'<div class="mb-3"><label class="form-label small" for="' +
				id +
				'">' +
				esc(label) +
				"</label>" +
				'<textarea class="form-control form-control-sm usis-set-field" id="' +
				id +
				'" rows="4" data-key="' +
				esc(key) +
				'" data-type="json"' +
				dis +
				">" +
				esc(text) +
				"</textarea>" +
				help +
				"</div>"
			);
		}
		return (
			'<div class="mb-3"><label class="form-label small" for="' +
			id +
			'">' +
			esc(label) +
			"</label>" +
			'<input class="form-control form-control-sm usis-set-field" id="' +
			id +
			'" data-key="' +
			esc(key) +
			'" data-type="scalar" value="' +
			esc(val == null ? "" : val) +
			'"' +
			dis +
			">" +
			help +
			"</div>"
		);
	}

	function parseField(el) {
		var type = el.getAttribute("data-type");
		if (type === "bool") return el.checked;
		var raw = el.value;
		if (type === "json") {
			var t = raw.trim();
			if (!t) return [];
			if (t.charAt(0) === "[" || t.charAt(0) === "{") return JSON.parse(t);
			return t
				.split(/\r?\n/)
				.map(function (s) {
					return s.trim();
				})
				.filter(Boolean);
		}
		if (raw === "") return null;
		if (/^-?\d+(\.\d+)?$/.test(raw)) {
			return raw.indexOf(".") >= 0 ? parseFloat(raw) : parseInt(raw, 10);
		}
		return raw;
	}

	function saveTopic(keys) {
		var chain = Promise.resolve();
		var n = 0;
		document.querySelectorAll(".usis-set-field").forEach(function (el) {
			if (el.disabled) return;
			var key = el.getAttribute("data-key");
			if (keys.indexOf(key) < 0) return;
			var value;
			try {
				value = parseField(el);
			} catch (err) {
				flash("Invalid JSON for " + key, "danger");
				throw err;
			}
			n += 1;
			chain = chain.then(function () {
				return fetchJson("/api/settings/" + encodeURIComponent(key), { method: "PUT", body: { value: value } }).then(
					function (r) {
						if (!r.ok) throw new Error((r.body && r.body.error) || "Save failed");
					}
				);
			});
		});
		if (!n) {
			flash("Nothing to save", "secondary");
			return;
		}
		chain
			.then(function () {
				if (window.USISUi && window.USISUi.toast) window.USISUi.toast("Saved");
				flash("Saved.", "success");
			})
			.catch(function (err) {
				flash(err.message || "Save failed", "danger");
			});
	}

	function formHtml(topic, map) {
		var keys = topic.keys || [];
		var html = '<div class="card border-0 shadow-sm mb-3 usis-console-card"><div class="card-body">';
		if (!keys.length) {
			html += '<p class="text-muted small mb-0">No fields on this section.</p>';
		}
		keys.forEach(function (k) {
			html += fieldControl(map[k] || { key: k, value: "", locked: false });
		});
		if (keys.length) {
			html +=
				'<div class="d-flex justify-content-end"><button type="button" class="btn btn-sm btn-primary usis-set-save">Save</button></div>';
		}
		html += "</div></div>";
		return html;
	}

	function bindSave(keys) {
		document.querySelectorAll(".usis-set-save").forEach(function (save) {
			save.addEventListener("click", function () {
				saveTopic(keys);
			});
		});
	}

	function kpiCard(label, value) {
		return (
			'<div class="col-md-3"><div class="card border-0 shadow-sm usis-console-card"><div class="card-body py-3"><div class="small text-muted">' +
			esc(label) +
			'</div><div class="h5 mb-0">' +
			esc(value) +
			"</div></div></div></div>"
		);
	}

	function renderOverview() {
		fetchJson("/api/settings/overview").then(function (r) {
			if (!r.ok) {
				document.getElementById("usis-set-root").innerHTML =
					"<p class=\"text-danger\">" + esc((r.body && r.body.error) || "Cannot load overview") + "</p>";
				return;
			}
			var d = r.body || {};
			var seats = d.seats || {};
			var kpis = d.kpis || {};
			var modules = d.modules || {};
			var on = Object.keys(modules).filter(function (k) {
				return modules[k];
			});
			var html = '<div class="row g-3 mb-3">';
			html += kpiCard("Office seats", (seats.office_used || 0) + " / " + (seats.office_cap || "—"));
			html += kpiCard("Field devices", (seats.field_used || 0) + " / " + (seats.field_cap || "—"));
			html += kpiCard("Plan", (d.plan_key || "—") + (on.length ? " · " + on.length + " modules" : ""));
			if (kpis.open_rfps != null) html += kpiCard("Open RFPs", kpis.open_rfps);
			if (kpis.hires_in_flight != null) html += kpiCard("Hires in flight", kpis.hires_in_flight);
			if (kpis.clocked_in != null) html += kpiCard("Clocked in", kpis.clocked_in);
			html += "</div>";
			var can = d.can || {};
			html += '<div class="d-flex flex-wrap gap-2 mb-3">';
			if (can.invite) html += '<a class="btn btn-sm btn-primary" href="/settings/people">Invite user</a>';
			if (can.new_project) html += '<a class="btn btn-sm btn-outline-primary" href="/construction/projects.html">New project</a>';
			if (can.audit) html += '<a class="btn btn-sm btn-outline-secondary" href="/settings/audit">View audit</a>';
			html += "</div>";
			html += '<div class="card border-0 shadow-sm"><div class="card-body"><h2 class="h6">Last setting changes</h2>';
			html +=
				'<div class="table-responsive"><table class="table table-sm mb-0"><thead class="table-light"><tr><th>When</th><th>Action</th><th>Reason</th></tr></thead><tbody>';
			var rows = d.recent_changes || [];
			if (!rows.length) html += '<tr><td colspan="3" class="text-muted">No setting changes yet.</td></tr>';
			rows.forEach(function (row) {
				html +=
					"<tr><td>" +
					esc(row.created_at || "") +
					"</td><td>" +
					esc(row.action || "") +
					"</td><td>" +
					esc(row.reason || "") +
					"</td></tr>";
			});
			html += "</tbody></table></div></div></div>";
			document.getElementById("usis-set-root").innerHTML = html;
		});
	}

	function initTable(id) {
		if (!window.jQuery || !window.jQuery.fn || !window.jQuery.fn.DataTable) return;
		var $ = window.jQuery;
		if ($.fn.DataTable.isDataTable("#" + id)) {
			$(id ? "#" + id : "").DataTable().destroy();
		}
		try {
			$("#" + id).DataTable({ paging: true, searching: true, info: false, pageLength: 25, order: [[0, "asc"]] });
		} catch (e) {}
	}

	function renderUsers() {
		Promise.all([fetchJson("/api/settings/users"), fetchJson("/api/settings/roles")]).then(function (pair) {
			var r = pair[0];
			var rolesPack = (pair[1].ok && pair[1].body) || {};
			var roleList = rolesPack.items || [];
			if (!r.ok) {
				document.getElementById("usis-set-root").innerHTML =
					"<p class=\"text-danger\">" + esc((r.body && r.body.error) || "Cannot load users") + "</p>";
				return;
			}
			var items = (r.body && r.body.items) || [];
			var html =
				'<div class="d-flex justify-content-end mb-3"><button type="button" class="btn btn-sm btn-primary" id="usis-set-open-invite">Invite user</button></div>' +
				'<div class="card border-0 shadow-sm mb-3"><div class="card-body">' +
				'<div class="table-responsive"><table class="table table-sm table-hover align-middle mb-0" id="usis-set-people-table"><thead class="table-light"><tr><th>Name</th><th>Email</th><th>Office / field</th><th>Roles</th><th>Last login</th><th>Status</th><th>Devices</th><th></th></tr></thead><tbody>';
			if (!items.length) {
				html +=
					'<tr><td colspan="8">' +
					(window.USISUi && window.USISUi.emptyState
						? window.USISUi.emptyState({ title: "No users", body: "Invite someone to this company." })
						: "No users") +
					"</td></tr>";
			}
			items.forEach(function (u) {
				var name = [u.first_name, u.last_name].filter(Boolean).join(" ") || "—";
				var roles = (u.roles || [])
					.map(function (x) {
						return x.name || x.code;
					})
					.join(", ");
				html +=
					"<tr><td>" +
					esc(name) +
					"</td><td>" +
					esc(u.email || "") +
					"</td><td>" +
					esc(u.seat_kind || "office") +
					"</td><td>" +
					esc(roles || "—") +
					"</td><td>" +
					esc(u.last_login_at || "—") +
					"</td><td>" +
					esc(u.status || (u.is_active ? "active" : "inactive")) +
					"</td><td>" +
					esc(u.devices || 0) +
					'</td><td class="text-end text-nowrap"><button type="button" class="btn btn-sm btn-outline-secondary me-1 usis-set-roles" data-id="' +
					esc(u.id) +
					'">Roles</button><button type="button" class="btn btn-sm btn-outline-secondary me-1 usis-set-reset" data-id="' +
					esc(u.id) +
					'">Reset password</button><button type="button" class="btn btn-sm btn-outline-danger usis-set-deact" data-id="' +
					esc(u.id) +
					'">Deactivate</button></td></tr>';
			});
			html += "</tbody></table></div></div></div>";
			document.getElementById("usis-set-root").innerHTML = html;
			if (items.length) initTable("usis-set-people-table");
			var roleSel = document.getElementById("usis-set-inv-role");
			if (roleSel) {
				roleSel.innerHTML = '<option value="">(none)</option>';
				roleList.forEach(function (role) {
					roleSel.innerHTML += '<option value="' + esc(role.id) + '">' + esc(role.name || role.code) + "</option>";
				});
			}
			var openInv = document.getElementById("usis-set-open-invite");
			if (openInv) {
				openInv.addEventListener("click", function () {
					var modalEl = document.getElementById("usis-set-invite-modal");
					if (window.bootstrap && modalEl) window.bootstrap.Modal.getOrCreateInstance(modalEl).show();
				});
			}
			var inv = document.getElementById("usis-set-inv");
			if (inv) {
				inv.onclick = function () {
					var body = {
						email: document.getElementById("usis-set-inv-email").value,
						first_name: document.getElementById("usis-set-inv-first").value,
						last_name: document.getElementById("usis-set-inv-last").value,
						seat_kind: document.getElementById("usis-set-inv-seat").value,
					};
					var rid = document.getElementById("usis-set-inv-role").value;
					if (rid) body.role_ids = [rid];
					fetchJson("/api/settings/users/invite", { method: "POST", body: body }).then(function (res) {
						if (!res.ok) return flash((res.body && res.body.error) || "Invite failed", "danger");
						flash("Invite sent.", "success");
						var modalEl = document.getElementById("usis-set-invite-modal");
						if (window.bootstrap && modalEl) window.bootstrap.Modal.getInstance(modalEl) && window.bootstrap.Modal.getInstance(modalEl).hide();
						renderUsers();
					});
				};
			}
			document.querySelectorAll(".usis-set-deact").forEach(function (btn) {
				btn.addEventListener("click", function () {
					fetchJson("/api/settings/users/" + encodeURIComponent(btn.getAttribute("data-id")) + "/deactivate", {
						method: "POST",
						body: {},
					}).then(function (res) {
						if (!res.ok) return flash((res.body && res.body.error) || "Failed", "danger");
						flash("User deactivated.", "success");
						renderUsers();
					});
				});
			});
			document.querySelectorAll(".usis-set-reset").forEach(function (btn) {
				btn.addEventListener("click", function () {
					fetchJson("/api/settings/users/" + encodeURIComponent(btn.getAttribute("data-id")) + "/reset-password", {
						method: "POST",
						body: {},
					}).then(function (res) {
						if (!res.ok) return flash((res.body && res.body.error) || "Failed", "danger");
						flash("Reset email sent.", "success");
					});
				});
			});
			document.querySelectorAll(".usis-set-roles").forEach(function (btn) {
				btn.addEventListener("click", function () {
					var uid = btn.getAttribute("data-id");
					var user = items.filter(function (u) {
						return u.id === uid;
					})[0];
					var have = {};
					((user && user.roles) || []).forEach(function (x) {
						have[x.id] = true;
					});
					var body = document.getElementById("usis-set-roles-body");
					body.innerHTML = roleList
						.map(function (role) {
							return (
								'<div class="form-check"><input class="form-check-input usis-set-role-cb" type="checkbox" value="' +
								esc(role.id) +
								'" id="role-' +
								esc(role.id) +
								'"' +
								(have[role.id] ? " checked" : "") +
								'><label class="form-check-label" for="role-' +
								esc(role.id) +
								'">' +
								esc(role.name || role.code) +
								"</label></div>"
							);
						})
						.join("") || "<p class=\"text-muted small mb-0\">No role templates.</p>";
					document.getElementById("usis-set-roles-title").textContent = "Assign roles";
					var modalEl = document.getElementById("usis-set-roles-modal");
					if (window.bootstrap && modalEl) window.bootstrap.Modal.getOrCreateInstance(modalEl).show();
					document.getElementById("usis-set-roles-ok").onclick = function () {
						var ids = [];
						document.querySelectorAll(".usis-set-role-cb:checked").forEach(function (cb) {
							ids.push(cb.value);
						});
						fetchJson("/api/settings/users/" + encodeURIComponent(uid) + "/roles", {
							method: "POST",
							body: { role_ids: ids },
						}).then(function (res) {
							if (!res.ok) return flash((res.body && res.body.error) || "Failed", "danger");
							flash("Roles saved.", "success");
							if (window.bootstrap && modalEl) window.bootstrap.Modal.getInstance(modalEl) && window.bootstrap.Modal.getInstance(modalEl).hide();
							renderUsers();
						});
					};
				});
			});
		});
	}

	function renderRoles() {
		fetchJson("/api/settings/roles").then(function (r) {
			if (!r.ok) {
				document.getElementById("usis-set-root").innerHTML =
					"<p class=\"text-danger\">" + esc((r.body && r.body.error) || "Cannot load roles") + "</p>";
				return;
			}
			var items = r.body.items || [];
			var catalog = r.body.catalog || [];
			var levels = r.body.levels || ["none", "read", "write", "admin"];
			var html = '<div class="row g-3"><div class="col-md-4"><div class="card border-0 shadow-sm"><div class="card-body p-0"><div class="list-group list-group-flush" id="usis-set-role-list">';
			items.forEach(function (role, i) {
				html +=
					'<button type="button" class="list-group-item list-group-item-action usis-set-role-pick' +
					(i === 0 ? " active" : "") +
					'" data-id="' +
					esc(role.id) +
					'">' +
					esc(role.name || role.code) +
					'<div class="small text-muted">' +
					esc(role.code || "") +
					"</div></button>";
			});
			if (!items.length) html += '<div class="p-3 text-muted">No permission templates.</div>';
			html += '</div></div></div><div class="col-md-8" id="usis-set-role-matrix"></div></div>';
			document.getElementById("usis-set-root").innerHTML = html;

			function drawMatrix(role) {
				var host = document.getElementById("usis-set-role-matrix");
				if (!role) {
					host.innerHTML = "<p class=\"text-muted\">Select a template.</p>";
					return;
				}
				var perms = role.permissions || {};
				var h =
					'<div class="card border-0 shadow-sm"><div class="card-body"><h2 class="h6">' +
					esc(role.name || role.code) +
					'</h2><div class="table-responsive"><table class="table table-sm usis-role-matrix"><thead class="table-light"><tr><th>Tool</th>';
				levels.forEach(function (lv) {
					h += "<th class=\"text-center\">" + esc(lv) + "</th>";
				});
				h += "</tr></thead><tbody>";
				catalog.forEach(function (mod) {
					h += "<tr><td>" + esc(mod.name || mod.code) + "</td>";
					var cur = perms[mod.code] || "none";
					levels.forEach(function (lv) {
						h +=
							'<td class="text-center"><input type="radio" name="perm-' +
							esc(mod.code) +
							'" class="usis-role-level" data-code="' +
							esc(mod.code) +
							'" value="' +
							esc(lv) +
							'"' +
							(cur === lv ? " checked" : "") +
							"></td>";
					});
					h += "</tr>";
				});
				h +=
					'</tbody></table></div><div class="d-flex justify-content-end"><button type="button" class="btn btn-sm btn-primary" id="usis-set-role-save">Save template</button></div></div></div>';
				host.innerHTML = h;
				document.getElementById("usis-set-role-save").addEventListener("click", function () {
					var payload = {};
					document.querySelectorAll(".usis-role-level:checked").forEach(function (el) {
						payload[el.getAttribute("data-code")] = el.value;
					});
					fetchJson("/api/settings/roles/" + encodeURIComponent(role.id), {
						method: "PUT",
						body: { permissions: payload },
					}).then(function (res) {
						if (!res.ok) return flash((res.body && res.body.error) || "Save failed", "danger");
						flash("Template saved.", "success");
						role.permissions = payload;
					});
				});
			}

			drawMatrix(items[0]);
			document.querySelectorAll(".usis-set-role-pick").forEach(function (btn) {
				btn.addEventListener("click", function () {
					document.querySelectorAll(".usis-set-role-pick").forEach(function (b) {
						b.classList.remove("active");
					});
					btn.classList.add("active");
					var role = items.filter(function (x) {
						return x.id === btn.getAttribute("data-id");
					})[0];
					drawMatrix(role);
				});
			});
		});
	}

	function renderAudit() {
		fetchJson("/api/settings/audit").then(function (r) {
			var items = (r.body && r.body.items) || [];
			var html =
				'<div class="d-flex justify-content-end mb-2"><a class="btn btn-sm btn-outline-secondary" href="/api/settings/audit.csv">Export CSV</a></div>' +
				'<div class="card border-0 shadow-sm"><div class="card-body"><div class="table-responsive"><table class="table table-sm" id="usis-set-audit-table"><thead class="table-light"><tr><th>When</th><th>Action</th><th>Reason</th></tr></thead><tbody>';
			if (!items.length) {
				html += '<tr><td colspan="3" class="text-muted">No setting changes yet.</td></tr>';
			}
			items.forEach(function (row) {
				html +=
					"<tr><td>" +
					esc(row.created_at || "") +
					"</td><td>" +
					esc(row.action) +
					"</td><td>" +
					esc(row.reason || "") +
					"</td></tr>";
			});
			html += "</tbody></table></div></div></div>";
			document.getElementById("usis-set-root").innerHTML = html;
			if (items.length) initTable("usis-set-audit-table");
		});
	}

	function moneyVal(map, key, fallback) {
		var it = map[key];
		if (!it || it.value == null || it.value === "") return fallback;
		return it.value;
	}

	function renderMoney(map) {
		var html =
			'<div class="card border-0 shadow-sm mb-3"><div class="card-body">' +
			'<h2 class="h6">Spend bands</h2>' +
			'<p class="small text-muted">Creator $0 / PM $5,000 / Director $25,000 / President unlimited. Saving publishes a new purchase-order workflow version. In-flight POs stay on their frozen version.</p>' +
			'<div class="row g-2">' +
			'<div class="col-md-3"><label class="form-label small">Creator</label><input class="form-control form-control-sm" id="usis-band-0" value="' +
			esc(moneyVal(map, "po.band_0", 0)) +
			'"></div>' +
			'<div class="col-md-3"><label class="form-label small">PM</label><input class="form-control form-control-sm" id="usis-band-pm" value="' +
			esc(moneyVal(map, "po.band_pm", 5000)) +
			'"></div>' +
			'<div class="col-md-3"><label class="form-label small">Director</label><input class="form-control form-control-sm" id="usis-band-director" value="' +
			esc(moneyVal(map, "po.band_director", 25000)) +
			'"></div>' +
			'<div class="col-md-3"><label class="form-label small">President</label><input class="form-control form-control-sm" id="usis-band-president" placeholder="unlimited" value="' +
			esc(moneyVal(map, "po.band_president", "") === null ? "" : moneyVal(map, "po.band_president", "")) +
			'"></div></div>' +
			'<div class="form-check mt-3"><input class="form-check-input" type="checkbox" disabled id="usis-skip-down"><label class="form-check-label" for="usis-skip-down">Skip-down (locked false)</label></div>' +
			'<div class="form-check mt-2"><input class="form-check-input" type="checkbox" id="usis-tm-co"' +
			(map["tm.requires_co"] && map["tm.requires_co"].value ? " checked" : "") +
			'><label class="form-check-label" for="usis-tm-co">T&amp;M tickets require a change order</label></div>' +
			'<div class="d-flex justify-content-end mt-3"><button type="button" class="btn btn-sm btn-primary" id="usis-money-save">Save bands</button></div></div></div>' +
			'<div class="card border-0 shadow-sm mb-3"><div class="card-body"><h2 class="h6">Workflow pack</h2><p class="small text-muted">Click a process to edit steps. Publish increments version. No BPMN canvas.</p><div id="usis-set-wf"></div></div></div>';
		document.getElementById("usis-set-root").innerHTML = html;
		document.getElementById("usis-money-save").addEventListener("click", function () {
			function num(id) {
				var raw = document.getElementById(id).value.trim();
				if (!raw) return null;
				var n = Number(raw);
				return isNaN(n) ? null : n;
			}
			fetchJson("/api/settings/money", {
				method: "POST",
				body: {
					"po.band_0": num("usis-band-0"),
					"po.band_pm": num("usis-band-pm"),
					"po.band_director": num("usis-band-director"),
					"po.band_president": num("usis-band-president"),
					"tm.requires_co": document.getElementById("usis-tm-co").checked,
				},
			}).then(function (res) {
				if (!res.ok) return flash((res.body && res.body.error) || "Save failed", "danger");
				flash("Spend bands saved. A new purchase_order definition was published.", "success");
			});
		});
		return renderWorkflows(document.getElementById("usis-set-wf"));
	}

	function renderWorkflows(into) {
		return fetchJson("/api/settings/workflows").then(function (r) {
			var items = (r.body && r.body.items) || [];
			var html =
				'<div class="table-responsive"><table class="table table-sm table-hover align-middle mb-0" id="usis-wf-pack"><thead class="table-light"><tr><th>Process</th><th>Version</th><th>Steps</th></tr></thead><tbody>';
			if (!items.length) html += '<tr><td colspan="3" class="text-muted">No workflow pack rows.</td></tr>';
			items.forEach(function (wf) {
				html +=
					'<tr class="usis-wf-row" data-process="' +
					esc(wf.process_key) +
					'" style="cursor:pointer"><td>' +
					esc(wf.name || wf.process_key) +
					" <code>" +
					esc(wf.process_key) +
					"</code></td><td>" +
					esc(wf.version == null ? "—" : "v" + wf.version) +
					"</td><td>" +
					esc((wf.steps || []).length) +
					"</td></tr>";
			});
			html += "</tbody></table></div><div id=\"usis-wf-detail\" class=\"mt-3\"></div>";
			var host = into || document.getElementById("usis-set-root");
			host.innerHTML = html;
			function drawDetail(wf) {
				var box = document.getElementById("usis-wf-detail");
				if (!box) return;
				if (!(wf.steps || []).length) {
					box.innerHTML = '<p class="text-muted mb-0">No published definition yet.</p>';
					return;
				}
				var h =
					"<h3 class=\"h6\">" +
					esc(wf.process_key) +
					(wf.version ? " v" + wf.version : "") +
					"</h3>" +
					'<div class="table-responsive"><table class="table table-sm"><thead><tr><th>Key</th><th>Label</th><th>Order</th><th>Queue</th><th>Assignment</th></tr></thead><tbody>';
				(wf.steps || []).forEach(function (s) {
					h +=
						'<tr data-process="' +
						esc(wf.process_key) +
						'"><td><code>' +
						esc(s.step_key) +
						'</code></td><td><input class="form-control form-control-sm usis-wf-label" data-key="' +
						esc(s.step_key) +
						'" value="' +
						esc(s.label) +
						'"></td><td><input class="form-control form-control-sm usis-wf-sort" data-key="' +
						esc(s.step_key) +
						'" value="' +
						esc(s.sort_order) +
						'"></td><td><input class="form-control form-control-sm usis-wf-queue" data-key="' +
						esc(s.step_key) +
						'" value="' +
						esc(s.queue_key || "") +
						'"></td><td><select class="form-select form-select-sm usis-wf-assign" data-key="' +
						esc(s.step_key) +
						'">';
					["queue", "role", "creator", "unassigned"].forEach(function (p) {
						h +=
							'<option value="' +
							p +
							'"' +
							((s.assignment_policy || "queue") === p ? " selected" : "") +
							">" +
							p +
							"</option>";
					});
					h += "</select></td></tr>";
				});
				h +=
					'</tbody></table></div><div class="d-flex justify-content-end"><button type="button" class="btn btn-sm btn-primary" id="usis-wf-pub">Publish</button></div>';
				box.innerHTML = h;
				document.getElementById("usis-wf-pub").addEventListener("click", function () {
					var steps = [];
					box.querySelectorAll("tr[data-process]").forEach(function (tr) {
						var label = tr.querySelector(".usis-wf-label");
						if (!label) return;
						steps.push({
							step_key: label.getAttribute("data-key"),
							label: label.value,
							sort_order: parseInt(tr.querySelector(".usis-wf-sort").value, 10) || 0,
							queue_key: tr.querySelector(".usis-wf-queue").value,
							assignment_policy: tr.querySelector(".usis-wf-assign").value,
						});
					});
					fetchJson("/api/settings/workflows/" + encodeURIComponent(wf.process_key) + "/steps", {
						method: "PUT",
						body: { steps: steps },
					}).then(function (res) {
						if (!res.ok) return flash((res.body && res.body.error) || "Publish failed", "danger");
						flash("Published version " + ((res.body && res.body.version) || ""), "success");
					});
				});
			}
			document.querySelectorAll(".usis-wf-row").forEach(function (tr) {
				tr.addEventListener("click", function () {
					var pk = tr.getAttribute("data-process");
					var wf = items.filter(function (x) {
						return x.process_key === pk;
					})[0];
					document.querySelectorAll(".usis-wf-row").forEach(function (row) {
						row.classList.remove("table-active");
					});
					tr.classList.add("table-active");
					if (wf) drawDetail(wf);
				});
			});
		});
	}

	function renderMail(topic, map) {
		var html = formHtml(
			{
				keys: [
					"mail.rfp.from_address",
					"mail.rfp.from_name",
					"mail.rfp.bcc_self",
					"mail.field.from_address",
					"mail.hire.from_address",
				],
			},
			map
		);
		html +=
			'<div class="card border-0 shadow-sm mb-3"><div class="card-body"><h2 class="h6">Send domains</h2><p class="small text-muted">Default approved domain is gousis.com. Additional domains need platform approval.</p><div id="usis-mail-domains"></div>' +
			'<div class="input-group input-group-sm mt-2"><input class="form-control" id="usis-mail-domain" placeholder="contractor.com"><button type="button" class="btn btn-outline-primary" id="usis-mail-domain-add">Request</button></div></div></div>' +
			'<div class="d-flex gap-2 mb-3"><button type="button" class="btn btn-sm btn-outline-primary" id="usis-mail-test">Test send (to me)</button></div>' +
			'<div class="card border-0 shadow-sm mb-3"><div class="card-body"><h2 class="h6">RFP template preview</h2><div id="usis-mail-preview" class="border rounded p-3 bg-light small">Loading…</div></div></div>';
		document.getElementById("usis-set-root").innerHTML = html;
		bindSave(topic.keys || []);
		fetchJson("/api/settings/mail/domains").then(function (r) {
			var host = document.getElementById("usis-mail-domains");
			if (!host) return;
			var approved = ((r.body && r.body.approved) || []).join(", ");
			var items = (r.body && r.body.items) || [];
			var t = '<p class="small mb-2">Live: ' + esc(approved || "gousis.com") + "</p><ul class=\"mb-0\">";
			items.forEach(function (d) {
				t += "<li><code>" + esc(d.domain) + "</code> — " + esc(d.status) + "</li>";
			});
			if (!items.length) t += '<li class="text-muted">No extra domains requested.</li>';
			host.innerHTML = t + "</ul>";
		});
		document.getElementById("usis-mail-domain-add").addEventListener("click", function () {
			var domain = document.getElementById("usis-mail-domain").value;
			fetchJson("/api/settings/mail/domains", { method: "POST", body: { domain: domain } }).then(function (res) {
				if (!res.ok) return flash((res.body && res.body.error) || "Request failed", "danger");
				flash("Domain requested. Platform must approve before it is live.", "success");
			});
		});
		document.getElementById("usis-mail-test").addEventListener("click", function () {
			fetchJson("/api/settings/mail/test", { method: "POST", body: {} }).then(function (res) {
				if (!res.ok) return flash((res.body && res.body.error) || "Test send failed", "danger");
				flash(res.body.dry_run ? "Queued as dry-run (mail not configured)." : "Test send queued to you.", "success");
			});
		});
		fetchJson("/api/settings/mail/preview").then(function (r) {
			var el = document.getElementById("usis-mail-preview");
			if (el) el.innerHTML = (r.body && r.body.html) || "";
		});
	}

	function renderFiles(topic, map) {
		var html = formHtml(topic, map);
		html +=
			'<div class="card border-0 shadow-sm mb-3"><div class="card-body"><h2 class="h6">Active public tokens</h2><div id="usis-set-tokens"></div></div></div>' +
			'<p class="small text-muted">Storage vs cap: not metered yet.</p>';
		document.getElementById("usis-set-root").innerHTML = html;
		bindSave(topic.keys || []);
		fetchJson("/api/settings/tokens").then(function (r) {
			var items = (r.body && r.body.items) || [];
			var host = document.getElementById("usis-set-tokens");
			var t =
				'<div class="table-responsive"><table class="table table-sm"><thead><tr><th>Type</th><th>Title</th><th>Created</th><th>Expires</th><th></th></tr></thead><tbody>';
			if (!items.length) t += '<tr><td colspan="5" class="text-muted">No active public tokens.</td></tr>';
			items.forEach(function (it) {
				t +=
					"<tr><td>" +
					esc(it.type) +
					"</td><td>" +
					esc(it.title || "") +
					"</td><td>" +
					esc(it.created_at || "") +
					"</td><td>" +
					esc(it.expires_at || "—") +
					'</td><td><button type="button" class="btn btn-sm btn-outline-danger usis-tok-rev" data-id="' +
					esc(it.id) +
					'">Revoke</button></td></tr>';
			});
			host.innerHTML = t + "</tbody></table></div>";
			document.querySelectorAll(".usis-tok-rev").forEach(function (btn) {
				btn.addEventListener("click", function () {
					fetchJson("/api/settings/tokens/" + encodeURIComponent(btn.getAttribute("data-id")) + "/revoke", {
						method: "POST",
						body: {},
					}).then(function (res) {
						if (!res.ok) return flash((res.body && res.body.error) || "Revoke failed", "danger");
						flash("Token revoked.", "success");
						btn.closest("tr").remove();
					});
				});
			});
		});
	}

	function renderTimeField(topic, map) {
		var html = formHtml(topic, map);
		html +=
			'<p class="small mb-3"><a href="/time/settings">Cost-code library (Time Settings)</a> — this page does not invent a who’s-on-this-code tracker.</p>' +
			'<div class="card border-0 shadow-sm mb-3"><div class="card-body"><h2 class="h6">Field devices</h2><div id="usis-set-devices"></div></div></div>';
		document.getElementById("usis-set-root").innerHTML = html;
		bindSave(topic.keys || []);
		fetchJson("/api/settings/devices").then(function (r) {
			var items = (r.body && r.body.items) || [];
			var host = document.getElementById("usis-set-devices");
			var t =
				'<div class="table-responsive"><table class="table table-sm"><thead><tr><th>Name</th><th>User</th><th>Last seen</th><th>App</th><th></th></tr></thead><tbody>';
			if (!items.length) t += '<tr><td colspan="5" class="text-muted">No field devices.</td></tr>';
			items.forEach(function (d) {
				t +=
					"<tr><td>" +
					esc(d.name) +
					"</td><td>" +
					esc(d.user_email || "") +
					"</td><td>" +
					esc(d.last_seen || "—") +
					"</td><td>" +
					esc(d.app_version || "—") +
					'</td><td><button type="button" class="btn btn-sm btn-outline-danger usis-dev-rev" data-id="' +
					esc(d.id) +
					'">Revoke</button></td></tr>';
			});
			host.innerHTML = t + "</tbody></table></div>";
			document.querySelectorAll(".usis-dev-rev").forEach(function (btn) {
				btn.addEventListener("click", function () {
					fetchJson("/api/settings/devices/" + encodeURIComponent(btn.getAttribute("data-id")) + "/revoke", {
						method: "POST",
						body: {},
					}).then(function (res) {
						if (!res.ok) return flash((res.body && res.body.error) || "Revoke failed", "danger");
						flash("Device revoked.", "success");
						btn.closest("tr").remove();
					});
				});
			});
		});
	}

	function renderHiring(topic, map) {
		var html = formHtml(topic, map);
		html +=
			'<p class="small">Form editions: W-4 2026, I-9 01/20/25 exp 05/31/2027, CA DE-4. <a href="/people/hiring">People → Hiring register</a>. AI on packets stays off.</p>';
		document.getElementById("usis-set-root").innerHTML = html;
		bindSave(topic.keys || []);
	}

	function renderAi(topic, map) {
		var html = formHtml(topic, map);
		html += '<p class="small text-muted">Daily call meter: not metered yet.</p>';
		document.getElementById("usis-set-root").innerHTML = html;
		bindSave(topic.keys || []);
	}

	function renderIntegrations(map) {
		var html = formHtml({ keys: ["qb.company_file_name"] }, map);
		html += '<div id="usis-int-cards" class="row g-3"></div>';
		document.getElementById("usis-set-root").innerHTML = html;
		bindSave(["qb.company_file_name"]);
		fetchJson("/api/settings/integrations").then(function (r) {
			var items = (r.body && r.body.items) || {};
			var host = document.getElementById("usis-int-cards");
			var order = ["smtp", "celery", "b2", "m365", "teams", "qbwc", "local_llama", "grok", "ai"];
			var seen = {};
			var cards = "";
			function card(k, v) {
				v = v || {};
				return (
					'<div class="col-md-4"><div class="card border-0 shadow-sm"><div class="card-body"><div class="small text-muted">' +
					esc(k) +
					"</div><div class=\"h5 mb-1\">" +
					(v.status === "ok" ? "🟢" : v.status === "warn" ? "🟡" : "🔴") +
					"</div><p class=\"small mb-0\">" +
					esc(v.detail || "") +
					"</p></div></div></div>"
				);
			}
			order.forEach(function (k) {
				if (items[k]) {
					cards += card(k, items[k]);
					seen[k] = true;
				}
			});
			Object.keys(items).forEach(function (k) {
				if (!seen[k]) cards += card(k, items[k]);
			});
			cards +=
				'<div class="col-12"><a class="small" href="/settings/correspondence">Manage M365 mailboxes</a> · <a class="small" href="usis-hr-quickbooks-employee-reference.html">QBWC reference</a></div>';
			if (host) host.innerHTML = cards;
		});
	}

	function renderCorrespondence(topic, map) {
		var html = formHtml(topic, map);
		html += '<p class="small"><a href="usis-correspondence.html">Correspondence register</a> — this page does not render HTML bodies.</p>';
		document.getElementById("usis-set-root").innerHTML = html;
		bindSave(topic.keys || []);
	}

	function renderProjects(map) {
		function buildProjectsForm(allRoles) {
			var rolesAvailable = allRoles !== null;
			var roleCodes = (allRoles || []).map(function (r) {
				return r.code;
			}).filter(function (c) {
				return c && c !== "applicant";
			});
			var roleNames = {};
			(allRoles || []).forEach(function (r) {
				if (r.code) roleNames[r.code] = r.name || r.code;
			});
			var stageLabels = (map["estimate.stage_labels"] && map["estimate.stage_labels"].value) || {};
			var stageKeys = Object.keys(stageLabels);
			var defaultTrades = (map["project.default_trades"] && map["project.default_trades"].value) || [];
			var whoMayCreate = (map["project.who_may_create"] && map["project.who_may_create"].value) || ["admin", "pm", "estimator"];
			var requireCost = !!(map["time.require_cost_code"] && map["time.require_cost_code"].value);
			var geofenceMode = (map["field.geofence_mode"] && map["field.geofence_mode"].value) || "flag";
			var tmRequiresCo = !!(map["tm.requires_co"] && map["tm.requires_co"].value);
			var html = '<div class="card border-0 shadow-sm mb-3 usis-console-card"><div class="card-body">';
			html += '<h6 class="mb-3">Project defaults</h6>';
			if (!rolesAvailable) {
				html += '<div class="alert alert-warning small">Could not load role list. Showing stored values only.</div>';
			}
			html += '<form id="usis-proj-form" novalidate>';
			html += '<div class="mb-3">';
			html += '<label class="form-label small">Who may create projects</label>';
			if (rolesAvailable) {
				roleCodes.forEach(function (code) {
					html += '<div class="form-check">';
					html += '<input class="form-check-input proj-who-role" type="checkbox" id="proj-who-' + esc(code) + '" value="' + esc(code) + '"' + (whoMayCreate.indexOf(code) >= 0 ? " checked" : "") + '>';
					html += '<label class="form-check-label" for="proj-who-' + esc(code) + '">' + esc(roleNames[code] || code) + '</label>';
					html += '</div>';
				});
				whoMayCreate.forEach(function (code) {
					if (roleCodes.indexOf(code) < 0) {
						html += '<div class="form-check">';
						html += '<input class="form-check-input proj-who-role" type="checkbox" id="proj-who-' + esc(code) + '" value="' + esc(code) + '" checked>';
						html += '<label class="form-check-label text-muted" for="proj-who-' + esc(code) + '">(legacy) ' + esc(code) + '</label>';
						html += '</div>';
					}
				});
			} else {
				whoMayCreate.forEach(function (code) {
					html += '<div class="form-check">';
					html += '<input class="form-check-input proj-who-role" type="checkbox" id="proj-who-' + esc(code) + '" value="' + esc(code) + '" checked>';
					html += '<label class="form-check-label" for="proj-who-' + esc(code) + '">' + esc(code) + '</label>';
					html += '</div>';
				});
			}
			html += '<div class="small text-danger d-none" id="proj-who-error">At least one role must be selected.</div>';
			html += '</div>';
			html += '<div class="mb-3">';
			html += '<label class="form-label small">Default trades <span class="text-muted">(one per line)</span></label>';
			html += '<textarea class="form-control form-control-sm" id="proj-trades" rows="6">' + esc((Array.isArray(defaultTrades) ? defaultTrades : []).join("\n")) + '</textarea>';
			html += '<div class="form-text text-muted">Common: Drywall, Paint, Flooring, Ceilings, Doors & Hardware, Millwork, Glass & Glazing</div>';
			html += '</div>';
			html += '<div class="mb-3">';
			html += '<label class="form-label small">Estimate stage labels</label>';
			html += '<div id="proj-stages"></div>';
			html += '<div class="small text-danger d-none" id="proj-stages-error"></div>';
			html += '<button type="button" class="btn btn-sm btn-outline-primary mt-2" id="proj-add-stage">Add stage</button>';
			html += '</div>';
			html += '<div class="mb-3">';
			html += '<div class="form-check">';
			html += '<input class="form-check-input" type="checkbox" id="proj-require-cost"' + (requireCost ? " checked" : "") + (map["time.require_cost_code"] && map["time.require_cost_code"].locked ? " disabled" : "") + '>';
			html += '<label class="form-check-label" for="proj-require-cost">Require cost code on time punch</label>';
			html += '</div>';
			html += '<div class="form-check">';
			html += '<input class="form-check-input" type="checkbox" id="proj-tm-co"' + (tmRequiresCo ? " checked" : "") + (map["tm.requires_co"] && map["tm.requires_co"].locked ? " disabled" : "") + '>';
			html += '<label class="form-check-label" for="proj-tm-co">T&amp;M tickets require a change order</label>';
			html += '</div>';
			html += '</div>';
			html += '<div class="mb-3">';
			html += '<label class="form-label small">Geofence default mode</label>';
			html += '<select class="form-select form-select-sm" id="proj-geofence"' + (map["field.geofence_mode"] && map["field.geofence_mode"].locked ? " disabled" : "") + '>';
			html += '<option value="flag"' + (geofenceMode === "flag" ? " selected" : "") + '>Flag (log only)</option>';
			html += '<option value="block"' + (geofenceMode === "block" ? " selected" : "") + '>Block (prevent punch)</option>';
			html += '</select>';
			html += '</div>';
			html += '<div class="d-flex justify-content-between">';
			html += '<button type="button" class="btn btn-sm btn-outline-secondary" id="proj-show-json">Advanced (JSON)</button>';
			html += '<button type="submit" class="btn btn-sm btn-primary">Save settings</button>';
			html += '</div>';
			html += '</form>';
			html += '<div class="collapse mt-3" id="proj-json-editor">';
			html += '<p class="small text-muted">Advanced editor — reflects current form state</p>';
			html += '<div class="mb-2">';
			html += '<label class="form-label small">estimate.stage_labels</label>';
			html += '<textarea class="form-control form-control-sm mb-2" id="proj-json-stages" rows="4" readonly></textarea>';
			html += '</div>';
			html += '<div class="mb-2">';
			html += '<label class="form-label small">project.default_trades</label>';
			html += '<textarea class="form-control form-control-sm mb-2" id="proj-json-trades" rows="4" readonly></textarea>';
			html += '</div>';
			html += '<div class="mb-2">';
			html += '<label class="form-label small">project.who_may_create</label>';
			html += '<textarea class="form-control form-control-sm mb-2" id="proj-json-who" rows="2" readonly></textarea>';
			html += '</div>';
			html += '</div>';
			html += '</div></div>';
			html += '<p class="small"><a href="/construction/projects.html">All projects</a> — this page does not duplicate the job list.</p>';
			document.getElementById("usis-set-root").innerHTML = html;
			function updateJsonPreview() {
				var stages = {};
				var stageRows = document.querySelectorAll(".proj-stage-row");
				stageRows.forEach(function (row) {
					var key = row.querySelector(".proj-stage-key").value.trim();
					var label = row.querySelector(".proj-stage-label").value.trim();
					if (key && label) stages[key] = label;
				});
				var trades = document.getElementById("proj-trades").value.split("\n").map(function (s) {
					return s.trim();
				}).filter(Boolean);
				var who = [];
				document.querySelectorAll(".proj-who-role:checked").forEach(function (cb) {
					who.push(cb.value);
				});
				document.getElementById("proj-json-stages").value = JSON.stringify(stages, null, 2);
				document.getElementById("proj-json-trades").value = JSON.stringify(trades, null, 2);
				document.getElementById("proj-json-who").value = JSON.stringify(who, null, 2);
			}
			function renderStages(labels, keys) {
				var container = document.getElementById("proj-stages");
				if (!container) return;
				var html = "";
				keys.forEach(function (key) {
					html += '<div class="row g-2 mb-2 proj-stage-row">';
					html += '<div class="col-md-3"><input class="form-control form-control-sm proj-stage-key" placeholder="Key (a-z0-9_)" value="' + esc(key) + '" data-original="' + esc(key) + '" readonly></div>';
					html += '<div class="col-md-7"><input class="form-control form-control-sm proj-stage-label" placeholder="Label" value="' + esc(labels[key]) + '"></div>';
					html += '<div class="col-md-2"><button type="button" class="btn btn-sm btn-outline-danger w-100 proj-remove-stage" data-existing="true">Remove</button></div>';
					html += '</div>';
				});
				container.innerHTML = html;
				document.querySelectorAll(".proj-remove-stage").forEach(function (btn) {
					btn.addEventListener("click", function () {
						var isExisting = btn.getAttribute("data-existing") === "true";
						if (isExisting) {
							var row = btn.closest(".proj-stage-row");
							var key = row.querySelector(".proj-stage-key").value.trim();
							if (!confirm("Remove stage '" + key + "'? This may orphan estimates using this stage.")) return;
						}
						btn.closest(".proj-stage-row").remove();
						updateJsonPreview();
					});
				});
				document.querySelectorAll(".proj-stage-label").forEach(function (inp) {
					inp.addEventListener("input", updateJsonPreview);
				});
			}
			renderStages(stageLabels, stageKeys);
			updateJsonPreview();
			document.getElementById("proj-trades").addEventListener("input", updateJsonPreview);
			document.querySelectorAll(".proj-who-role").forEach(function (cb) {
				cb.addEventListener("change", updateJsonPreview);
			});
			document.getElementById("proj-add-stage").addEventListener("click", function () {
				var container = document.getElementById("proj-stages");
				var row = document.createElement("div");
				row.className = "row g-2 mb-2 proj-stage-row";
				row.innerHTML = '<div class="col-md-3"><input class="form-control form-control-sm proj-stage-key" placeholder="Key (a-z0-9_)" data-original="" data-new="true"></div>' +
					'<div class="col-md-7"><input class="form-control form-control-sm proj-stage-label" placeholder="Label"></div>' +
					'<div class="col-md-2"><button type="button" class="btn btn-sm btn-outline-danger w-100 proj-remove-stage">Remove</button></div>';
				container.appendChild(row);
				row.querySelector(".proj-remove-stage").addEventListener("click", function () {
					row.remove();
					updateJsonPreview();
				});
				row.querySelectorAll(".proj-stage-key, .proj-stage-label").forEach(function (inp) {
					inp.addEventListener("input", updateJsonPreview);
				});
				updateJsonPreview();
			});
			document.getElementById("usis-proj-form").addEventListener("submit", function (e) {
				e.preventDefault();
				var stagesErr = document.getElementById("proj-stages-error");
				var whoErr = document.getElementById("proj-who-error");
				stagesErr.classList.add("d-none");
				stagesErr.classList.remove("d-block");
				stagesErr.textContent = "";
				whoErr.classList.add("d-none");
				whoErr.classList.remove("d-block");
				var stages = {};
				var seenKeys = {};
				var valid = true;
				var stageRows = document.querySelectorAll(".proj-stage-row");
				if (stageRows.length === 0) {
					stagesErr.textContent = "At least one stage is required.";
					stagesErr.classList.remove("d-none");
					stagesErr.classList.add("d-block");
					return;
				}
				stageRows.forEach(function (row) {
					var keyInput = row.querySelector(".proj-stage-key");
					var labelInput = row.querySelector(".proj-stage-label");
					var key = keyInput.value.trim();
					var label = labelInput.value.trim();
					var isNew = keyInput.getAttribute("data-new") === "true";
					keyInput.classList.remove("is-invalid");
					labelInput.classList.remove("is-invalid");
					if (!key) {
						if (isNew) keyInput.classList.add("is-invalid");
						valid = false;
					} else if (!/^[a-z0-9_]+$/.test(key)) {
						if (isNew) keyInput.classList.add("is-invalid");
						stagesErr.textContent = "Keys must match ^[a-z0-9_]+$ (lowercase letters, numbers, underscore).";
						stagesErr.classList.remove("d-none");
						stagesErr.classList.add("d-block");
						valid = false;
					} else if (seenKeys[key]) {
						if (isNew) keyInput.classList.add("is-invalid");
						stagesErr.textContent = "Duplicate key: " + key;
						stagesErr.classList.remove("d-none");
						stagesErr.classList.add("d-block");
						valid = false;
					}
					if (!label) {
						labelInput.classList.add("is-invalid");
						valid = false;
					}
					if (key && label && /^[a-z0-9_]+$/.test(key) && !seenKeys[key]) {
						stages[key] = label;
						seenKeys[key] = true;
					}
				});
				if (!valid) return;
				var trades = document.getElementById("proj-trades").value.split("\n").map(function (s) {
					return s.trim();
				}).filter(Boolean);
				var who = [];
				document.querySelectorAll(".proj-who-role:checked").forEach(function (cb) {
					who.push(cb.value);
				});
				if (who.length === 0) {
					whoErr.classList.remove("d-none");
					whoErr.classList.add("d-block");
					return;
				}
				var chain = Promise.resolve();
				var saveKey = function (key, value) {
					if (map[key] && map[key].locked) return;
					chain = chain.then(function () {
						return fetchJson("/api/settings/" + encodeURIComponent(key), { method: "PUT", body: { value: value } }).then(function (r) {
							if (!r.ok) throw new Error((r.body && r.body.error) || "Save failed for " + key);
						});
					});
				};
				saveKey("estimate.stage_labels", stages);
				saveKey("project.default_trades", trades);
				saveKey("project.who_may_create", who);
				saveKey("time.require_cost_code", document.getElementById("proj-require-cost").checked);
				saveKey("field.geofence_mode", document.getElementById("proj-geofence").value);
				saveKey("tm.requires_co", document.getElementById("proj-tm-co").checked);
				chain.then(function () {
					if (window.USISNotify && window.USISNotify.success) window.USISNotify.success("Settings saved");
				}).catch(function (err) {
					if (window.USISNotify && window.USISNotify.error) {
						window.USISNotify.error(err.message || "Save failed");
					} else {
						flash(err.message || "Save failed", "danger");
					}
				});
			});
			document.getElementById("proj-show-json").addEventListener("click", function () {
				var editor = document.getElementById("proj-json-editor");
				if (editor) {
					if (editor.classList.contains("show")) {
						editor.classList.remove("show");
					} else {
						editor.classList.add("show");
					}
				}
			});
		}
		fetchJson("/api/settings/roles").catch(function () {
			return null;
		}).then(function (rolesResp) {
			buildProjectsForm(rolesResp && rolesResp.ok && rolesResp.body && rolesResp.body.items ? rolesResp.body.items : null);
		});
	}

	function boot() {
		fetchJson("/api/settings").then(function (r) {
			if (r.status === 403) {
				document.getElementById("usis-set-root").innerHTML = "<p class=\"text-danger\">Company Admin required.</p>";
				return;
			}
			if (!r.ok) {
				document.getElementById("usis-set-root").innerHTML = "<p class=\"text-danger\">Could not load settings.</p>";
				return;
			}
			var pack = r.body || {};
			var rail = pack.rail || pack.topics || FALLBACK_RAIL;
			var map = byKey(pack);
			var id = sectionFromPath();
			var topic = findSection(rail, id) || (id === "overview" ? { id: "overview", title: "Overview", description: "Seats, plan, and recent changes for this company", keys: [] } : null);
			renderRail(rail, topic ? topic.id : "overview");
			if (!topic || topic.id === "overview") {
				document.getElementById("usis-set-title").textContent = "Overview";
				document.getElementById("usis-set-lead").textContent = "Seats, plan, and recent changes for this company.";
				return renderOverview();
			}
			document.getElementById("usis-set-title").textContent = topic.title;
			document.getElementById("usis-set-lead").textContent = topic.description || "";
			if (topic.id === "people") return renderUsers();
			if (topic.id === "roles") return renderRoles();
			if (topic.id === "audit") return renderAudit();
			if (topic.id === "projects") return renderProjects(map);
			if (topic.id === "money") return renderMoney(map);
			if (topic.id === "mail") return renderMail(topic, map);
			if (topic.id === "correspondence") return renderCorrespondence(topic, map);
			if (topic.id === "files") return renderFiles(topic, map);
			if (topic.id === "time-field") return renderTimeField(topic, map);
			if (topic.id === "hiring") return renderHiring(topic, map);
			if (topic.id === "ai") return renderAi(topic, map);
			if (topic.id === "integrations") return renderIntegrations(map);
			document.getElementById("usis-set-root").innerHTML = formHtml(topic, map);
			bindSave(topic.keys || []);
		});
	}

	if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
	else boot();
})();
