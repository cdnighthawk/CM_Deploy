/**
 * Contractor Settings console — inner left rail + one editor per section.
 */
(function () {
	"use strict";

	var ALIASES = { users: "people", security: "people", senders: "mail", workflows: "money" };
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
				esc(key) +
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
			key === "estimate.stage_labels"
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
				esc(key) +
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
			esc(key) +
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

	function renderWorkflows(into) {
		return fetchJson("/api/settings/workflows").then(function (r) {
			var items = (r.body && r.body.items) || [];
			var html = "";
			items.forEach(function (wf) {
				html += '<div class="card border-0 shadow-sm mb-3"><div class="card-body">';
				html += "<h2 class=\"h6\">" + esc(wf.process_key) + (wf.version ? " v" + wf.version : "") + "</h2>";
				html +=
					'<div class="table-responsive"><table class="table table-sm"><thead><tr><th>Key</th><th>Label</th><th>Order</th><th>Queue</th></tr></thead><tbody>';
				(wf.steps || []).forEach(function (s) {
					html +=
						'<tr data-process="' +
						esc(wf.process_key) +
						'"><td>' +
						esc(s.step_key) +
						'</td><td><input class="form-control form-control-sm usis-wf-label" data-key="' +
						esc(s.step_key) +
						'" value="' +
						esc(s.label) +
						'"></td><td><input class="form-control form-control-sm usis-wf-sort" data-key="' +
						esc(s.step_key) +
						'" value="' +
						esc(s.sort_order) +
						'"></td><td>' +
						esc(s.queue_key || "") +
						"</td></tr>";
				});
				if (!(wf.steps || []).length) html += '<tr><td colspan="4" class="text-muted">No published definition yet.</td></tr>';
				html += "</tbody></table></div>";
				if ((wf.steps || []).length) {
					html +=
						'<div class="d-flex justify-content-end"><button type="button" class="btn btn-sm btn-primary usis-wf-pub" data-process="' +
						esc(wf.process_key) +
						'">Publish</button></div>';
				}
				html += "</div></div>";
			});
			var host = into || document.getElementById("usis-set-root");
			if (into) {
				into.innerHTML = html || "<p class=\"text-muted\">No workflows.</p>";
			} else {
				host.innerHTML = html || "<p class=\"text-muted\">No workflows.</p>";
			}
			document.querySelectorAll(".usis-wf-pub").forEach(function (btn) {
				btn.addEventListener("click", function () {
					var pk = btn.getAttribute("data-process");
					var steps = [];
					document.querySelectorAll('tr[data-process="' + pk + '"]').forEach(function (tr) {
						var label = tr.querySelector(".usis-wf-label");
						var sort = tr.querySelector(".usis-wf-sort");
						if (!label) return;
						steps.push({
							step_key: label.getAttribute("data-key"),
							label: label.value,
							sort_order: parseInt(sort.value, 10) || 0,
						});
					});
					fetchJson("/api/settings/workflows/" + encodeURIComponent(pk) + "/steps", {
						method: "PUT",
						body: { steps: steps },
					}).then(function (res) {
						if (!res.ok) return flash((res.body && res.body.error) || "Publish failed", "danger");
						flash("Published version " + ((res.body && res.body.version) || ""), "success");
					});
				});
			});
		});
	}

	function renderProjects(map) {
		var html = formHtml(
			{ keys: ["estimate.stage_labels"] },
			map
		);
		html +=
			'<p class="small"><a href="/construction/projects.html">All projects</a> — this page does not duplicate the job list.</p>';
		document.getElementById("usis-set-root").innerHTML = html;
		bindSave(["estimate.stage_labels"]);
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
			if (topic.id === "money") {
				document.getElementById("usis-set-root").innerHTML = formHtml(topic, map) + '<div id="usis-set-wf"></div>';
				bindSave(topic.keys || []);
				return renderWorkflows(document.getElementById("usis-set-wf"));
			}
			document.getElementById("usis-set-root").innerHTML = formHtml(topic, map);
			bindSave(topic.keys || []);
		});
	}

	if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
	else boot();
})();
