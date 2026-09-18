/**
 * Tenant Settings — Shopify-style topic list + one form per topic.
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

	function topicFromPath() {
		var p = (window.location.pathname || "").replace(/\\/g, "/");
		var m = p.match(/\/settings\/([a-z0-9-]+)/i);
		if (m) return m[1].toLowerCase();
		try {
			var u = new URL(window.location.href);
			return (u.searchParams.get("topic") || "").toLowerCase();
		} catch (e) {
			return "";
		}
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

	function fieldControl(item) {
		var key = item.key;
		var val = item.value;
		var locked = !!item.locked;
		var dis = locked ? " disabled" : "";
		var help = locked
			? '<div class="form-text text-muted">Platform policy — cannot be changed.</div>'
			: "";
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
		if (Array.isArray(val) || key.indexOf("never_auto") >= 0 || key === "mail.allow_mailboxes" || key === "company.offices" || key === "security.mfa_required_roles" || key === "files.spec_split_roles" || key === "estimate.stage_labels") {
			var text = Array.isArray(val) ? val.join("\n") : typeof val === "object" && val ? JSON.stringify(val, null, 2) : String(val || "");
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
			return t.split(/\r?\n/).map(function (s) { return s.trim(); }).filter(Boolean);
		}
		if (raw === "") return null;
		if (/^-?\d+(\.\d+)?$/.test(raw)) {
			return raw.indexOf(".") >= 0 ? parseFloat(raw) : parseInt(raw, 10);
		}
		return raw;
	}

	function renderTiles(topics) {
		var html = '<div class="row g-3 usis-settings-tiles">';
		topics.forEach(function (t) {
			html +=
				'<div class="col-12 col-md-6 col-xl-4">' +
				'<a class="card border-0 shadow-sm h-100 text-decoration-none usis-settings-tile" href="/settings/' +
				esc(t.id) +
				'">' +
				'<div class="card-body">' +
				'<div class="d-flex align-items-start gap-2">' +
				'<i class="icon feather icon-' +
				esc(t.icon || "settings") +
				' text-primary mt-1"></i>' +
				"<div><h2 class=\"h6 mb-1 text-body\">" +
				esc(t.title) +
				"</h2>" +
				'<p class="text-muted small mb-0">' +
				esc(t.description) +
				"</p></div></div></div></a></div>";
		});
		html += "</div>";
		return html;
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
				return fetchJson("/api/settings/" + encodeURIComponent(key), { method: "PUT", body: { value: value } }).then(function (r) {
					if (!r.ok) throw new Error((r.body && r.body.error) || "Save failed");
				});
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

	function renderForm(topic, pack, map) {
		var keys = topic.keys || [];
		var html = '<div class="card border-0 shadow-sm"><div class="card-body">';
		if (!keys.length && topic.id !== "users" && topic.id !== "audit" && topic.id !== "workflows") {
			html += "<p class=\"text-muted small mb-0\">No fields on this topic.</p>";
		}
		keys.forEach(function (k) {
			html += fieldControl(map[k] || { key: k, value: "", locked: false });
		});
		if (keys.length) {
			html +=
				'<div class="d-flex justify-content-end"><button type="button" class="btn btn-sm btn-primary" id="usis-set-save">Save</button></div>';
		}
		html += "</div></div>";
		document.getElementById("usis-set-root").innerHTML = html;
		var save = document.getElementById("usis-set-save");
		if (save) save.addEventListener("click", function () { saveTopic(keys); });
	}

	function renderUsers() {
		fetchJson("/api/settings/users").then(function (r) {
			if (!r.ok) {
				document.getElementById("usis-set-root").innerHTML = "<p class=\"text-danger\">" + esc((r.body && r.body.error) || "Cannot load users") + "</p>";
				return;
			}
			var items = (r.body && r.body.items) || [];
			var html =
				'<div class="card border-0 shadow-sm mb-3"><div class="card-body">' +
				'<div class="row g-2 align-items-end mb-3">' +
				'<div class="col-md-4"><label class="form-label small mb-0">Email</label><input class="form-control form-control-sm" id="usis-set-inv-email"></div>' +
				'<div class="col-md-3"><label class="form-label small mb-0">First</label><input class="form-control form-control-sm" id="usis-set-inv-first"></div>' +
				'<div class="col-md-3"><label class="form-label small mb-0">Last</label><input class="form-control form-control-sm" id="usis-set-inv-last"></div>' +
				'<div class="col-md-2"><button type="button" class="btn btn-sm btn-primary w-100" id="usis-set-inv">Invite</button></div></div>' +
				'<div class="table-responsive"><table class="table table-sm table-hover align-middle mb-0"><thead class="table-light"><tr><th>Name</th><th>Email</th><th>Active</th><th></th></tr></thead><tbody>';
			if (!items.length) {
				html +=
					'<tr><td colspan="4">' +
					(window.USISUi && window.USISUi.emptyState
						? window.USISUi.emptyState({ title: "No users", body: "Invite someone to this company." })
						: "No users") +
					"</td></tr>";
			}
			items.forEach(function (u) {
				html +=
					"<tr><td>" +
					esc([u.first_name, u.last_name].filter(Boolean).join(" ") || "—") +
					"</td><td>" +
					esc(u.email || "") +
					"</td><td>" +
					(u.is_active ? "Yes" : "No") +
					'</td><td class="text-end"><button type="button" class="btn btn-sm btn-outline-secondary me-1 usis-set-reset" data-id="' +
					esc(u.id) +
					'">Reset password</button><button type="button" class="btn btn-sm btn-outline-danger usis-set-deact" data-id="' +
					esc(u.id) +
					'">Deactivate</button></td></tr>';
			});
			html += "</tbody></table></div></div></div>";
			document.getElementById("usis-set-root").innerHTML = html;
			document.getElementById("usis-set-inv").addEventListener("click", function () {
				fetchJson("/api/settings/users/invite", {
					method: "POST",
					body: {
						email: document.getElementById("usis-set-inv-email").value,
						first_name: document.getElementById("usis-set-inv-first").value,
						last_name: document.getElementById("usis-set-inv-last").value,
					},
				}).then(function (res) {
					if (!res.ok) return flash((res.body && res.body.error) || "Invite failed", "danger");
					flash("Invite sent.", "success");
					renderUsers();
				});
			});
			document.querySelectorAll(".usis-set-deact").forEach(function (btn) {
				btn.addEventListener("click", function () {
					fetchJson("/api/settings/users/" + encodeURIComponent(btn.getAttribute("data-id")) + "/deactivate", { method: "POST", body: {} }).then(function (res) {
						if (!res.ok) return flash((res.body && res.body.error) || "Failed", "danger");
						flash("User deactivated.", "success");
						renderUsers();
					});
				});
			});
			document.querySelectorAll(".usis-set-reset").forEach(function (btn) {
				btn.addEventListener("click", function () {
					fetchJson("/api/settings/users/" + encodeURIComponent(btn.getAttribute("data-id")) + "/reset-password", { method: "POST", body: {} }).then(function (res) {
						if (!res.ok) return flash((res.body && res.body.error) || "Failed", "danger");
						flash("Reset email sent.", "success");
					});
				});
			});
		});
	}

	function renderAudit() {
		fetchJson("/api/settings/audit").then(function (r) {
			var items = (r.body && r.body.items) || [];
			var html = '<div class="card border-0 shadow-sm"><div class="card-body"><div class="table-responsive"><table class="table table-sm"><thead class="table-light"><tr><th>When</th><th>Action</th><th>Reason</th></tr></thead><tbody>';
			if (!items.length) {
				html += "<tr><td colspan=\"3\" class=\"text-muted\">No setting changes yet.</td></tr>";
			}
			items.forEach(function (row) {
				html += "<tr><td>" + esc(row.created_at || "") + "</td><td>" + esc(row.action) + "</td><td>" + esc(row.reason || "") + "</td></tr>";
			});
			html += "</tbody></table></div></div></div>";
			document.getElementById("usis-set-root").innerHTML = html;
		});
	}

	function renderWorkflows() {
		fetchJson("/api/settings/workflows").then(function (r) {
			var items = (r.body && r.body.items) || [];
			var html = "";
			items.forEach(function (wf) {
				html += '<div class="card border-0 shadow-sm mb-3"><div class="card-body">';
				html += "<h2 class=\"h6\">" + esc(wf.process_key) + (wf.version ? " v" + wf.version : "") + "</h2>";
				html += '<div class="table-responsive"><table class="table table-sm"><thead><tr><th>Key</th><th>Label</th><th>Order</th><th>Queue</th></tr></thead><tbody>';
				(wf.steps || []).forEach(function (s) {
					html +=
						"<tr data-process=\"" +
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
				if (!(wf.steps || []).length) html += "<tr><td colspan=\"4\" class=\"text-muted\">No published definition yet.</td></tr>";
				html += "</tbody></table></div>";
				if ((wf.steps || []).length) {
					html += '<div class="d-flex justify-content-end"><button type="button" class="btn btn-sm btn-primary usis-wf-pub" data-process="' + esc(wf.process_key) + '">Publish</button></div>';
				}
				html += "</div></div>";
			});
			document.getElementById("usis-set-root").innerHTML = html || "<p class=\"text-muted\">No workflows.</p>";
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
					fetchJson("/api/settings/workflows/" + encodeURIComponent(pk) + "/steps", { method: "PUT", body: { steps: steps } }).then(function (res) {
						if (!res.ok) return flash((res.body && res.body.error) || "Publish failed", "danger");
						flash("Published version " + ((res.body && res.body.version) || ""), "success");
						renderWorkflows();
					});
				});
			});
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
			var topics = pack.topics || [];
			var map = byKey(pack);
			var id = topicFromPath();
			var topic = null;
			topics.forEach(function (t) {
				if (t.id === id) topic = t;
			});
			var back = '<a class="btn btn-sm btn-outline-secondary" href="/settings">All settings</a>';
			if (!topic) {
				document.getElementById("usis-set-title").textContent = "Settings";
				document.getElementById("usis-set-lead").textContent = "Company controls for this tenant. Each topic opens one form.";
				document.getElementById("usis-set-actions").innerHTML = "";
				document.getElementById("usis-set-root").innerHTML = renderTiles(topics);
				return;
			}
			document.getElementById("usis-set-title").textContent = topic.title;
			document.getElementById("usis-set-lead").textContent = topic.description;
			document.getElementById("usis-set-actions").innerHTML = back;
			if (topic.id === "users") return renderUsers();
			if (topic.id === "audit") return renderAudit();
			if (topic.id === "workflows") return renderWorkflows();
			renderForm(topic, pack, map);
		});
	}

	if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
	else boot();
})();
