(function () {
	"use strict";

	function apiBase() {
		if (typeof window.usisApiBase === "function") return window.usisApiBase();
		if (typeof window.USIS_API_BASE === "string" && window.USIS_API_BASE.trim()) {
			return window.USIS_API_BASE.trim().replace(/\/$/, "");
		}
		if (window.location.protocol === "file:") return "http://127.0.0.1:5000";
		return "";
	}

	function esc(s) {
		var d = document.createElement("div");
		d.textContent = s == null ? "" : String(s);
		return d.innerHTML;
	}

	function chip(st) {
		if (window.USISUi && window.USISUi.statusChip) return window.USISUi.statusChip(st || "");
		return esc(st || "");
	}

	function empty(title, body) {
		if (window.USISUi && window.USISUi.emptyState) return window.USISUi.emptyState({ title: title, body: body });
		return '<span class="text-muted">' + esc(body || title) + "</span>";
	}

	function fetchJson(path, opts) {
		return fetch(apiBase() + path, Object.assign({ credentials: "include", headers: { Accept: "application/json", "Content-Type": "application/json" } }, opts || {})).then(function (r) {
			return r.json().then(function (j) {
				if (!r.ok) throw new Error(j.error || r.statusText);
				return j;
			});
		});
	}

	function qs(name) {
		return new URLSearchParams(window.location.search).get(name);
	}

	function ensureInviteModal() {
		if (document.getElementById("hire-invite-modal")) return;
		var wrap = document.createElement("div");
		wrap.innerHTML =
			'<div class="modal fade" id="hire-invite-modal" tabindex="-1">' +
			'<div class="modal-dialog"><div class="modal-content"><div class="modal-header"><h5 class="modal-title">Invite link</h5>' +
			'<button class="btn-close" data-bs-dismiss="modal"></button></div><div class="modal-body">' +
			'<p class="small text-muted">Copy this link and send it if email is delayed. It is the only way to open the public packet.</p>' +
			'<input class="form-control" id="hire-invite-url" readonly>' +
			'</div><div class="modal-footer"><button class="btn btn-outline-secondary" type="button" data-bs-dismiss="modal">Close</button>' +
			'<button class="btn btn-primary" type="button" id="hire-invite-copy">Copy</button></div></div></div></div>';
		document.body.appendChild(wrap.firstElementChild);
		document.getElementById("hire-invite-copy").addEventListener("click", function () {
			var input = document.getElementById("hire-invite-url");
			if (!input || !input.value) return;
			if (navigator.clipboard && navigator.clipboard.writeText) {
				navigator.clipboard.writeText(input.value).then(function () {
					document.getElementById("hire-invite-copy").textContent = "Copied";
				}).catch(function () {
					input.select();
					document.execCommand("copy");
				});
			} else {
				input.select();
				document.execCommand("copy");
			}
		});
	}

	function showInviteUrl(url) {
		ensureInviteModal();
		var input = document.getElementById("hire-invite-url");
		if (input) input.value = url || "";
		var copy = document.getElementById("hire-invite-copy");
		if (copy) copy.textContent = "Copy";
		if (window.bootstrap) new window.bootstrap.Modal(document.getElementById("hire-invite-modal")).show();
	}

	function settingsFields() {
		return [
			["hire_mail_from", "Mail from", "email", false],
			["hire_mail_reply_to", "Reply-to", "email", false],
			["employer_legal_name", "Employer legal name", "text", false],
			["employer_address", "Employer address", "text", false],
			["employer_fein", "FEIN (restricted)", "text", true],
			["edd_account_number", "EDD account (restricted)", "text", true],
			["i9_section2_business_name", "I-9 examiner business name", "text", false],
			["i9_section2_address", "I-9 examiner address", "text", false],
			["marketplace_notice", "Marketplace notice", "text", false],
			["default_wage_order", "Default wage order", "text", false]
		];
	}

	function renderHiring(root) {
		ensureInviteModal();
		root.innerHTML =
			'<div class="d-flex flex-wrap justify-content-between align-items-center gap-2 mb-3">' +
			"<div><h5 class=\"mb-1\">Hiring</h5><p class=\"text-muted small mb-0\">New-hire packets. Payroll is set up in QuickBooks from the export — CM does not write employees to QB.</p></div>" +
			'<div class="d-flex gap-1"><button class="btn btn-sm btn-outline-secondary" type="button" id="hire-settings">Hire settings</button>' +
			'<button class="btn btn-sm btn-primary" type="button" id="hire-new">New hire</button></div></div>' +
			'<div class="d-flex flex-wrap gap-2 mb-2">' +
			'<select class="form-select form-select-sm" id="hire-filter-stage" style="max-width:12rem">' +
			'<option value="">All stages</option>' +
			["draft","invite_sent","employee_in_progress","employee_signed","hr_review","i9_section2","ready_for_payroll","payroll_setup","closed","void"].map(function (s) {
				return '<option value="' + s + '">' + s.replace(/_/g, " ") + "</option>";
			}).join("") +
			"</select>" +
			'<input class="form-control form-control-sm" type="week" id="hire-filter-week" style="max-width:12rem" title="Start week">' +
			'<div class="form-check"><input class="form-check-input" type="checkbox" id="hire-filter-i9"><label class="form-check-label small" for="hire-filter-i9">Incomplete I-9</label></div>' +
			'<div class="form-check"><input class="form-check-input" type="checkbox" id="hire-filter-dd"><label class="form-check-label small" for="hire-filter-dd">Missing deposit</label></div>' +
			"</div>" +
			'<div class="card"><div class="card-body table-responsive"><table class="table table-sm align-middle" id="hire-table">' +
			"<thead><tr><th>Employee</th><th>Job title</th><th>Start</th><th>Stage</th><th>W-4</th><th>I-9 §1</th><th>I-9 §2</th><th>DE-4</th><th>Deposit</th><th>Notices</th><th>Days to I-9 §2</th><th>Owner</th><th></th></tr></thead>" +
			"<tbody></tbody></table></div></div>" +
			'<div class="modal fade" id="hire-modal" tabindex="-1"><div class="modal-dialog modal-lg"><div class="modal-content"><div class="modal-header"><h5 class="modal-title">New hire</h5><button class="btn-close" data-bs-dismiss="modal"></button></div><div class="modal-body">' +
			'<div class="row g-2">' +
			'<div class="col-md-6"><label class="form-label">Job title</label><input class="form-control" id="nh-title" placeholder="Painter"></div>' +
			'<div class="col-md-6"><label class="form-label">Start of work</label><input class="form-control" id="nh-start" type="date"></div>' +
			'<div class="col-md-6"><label class="form-label">Invite email</label><input class="form-control" id="nh-email" type="email"></div>' +
			'<div class="col-md-6"><label class="form-label">Class</label><select class="form-select" id="nh-class"><option value="hourly_nonexempt">Hourly non-exempt</option><option value="salary_exempt">Salary exempt</option></select></div>' +
			'<div class="col-md-6"><label class="form-label">Type</label><select class="form-select" id="nh-type"><option value="new">New</option><option value="rehire">Rehire</option></select></div>' +
			'<div class="col-md-6"><label class="form-label">Wage order</label><select class="form-select" id="nh-wo"><option value="16">16 — field / construction</option><option value="4">4 — office</option></select></div>' +
			'<div class="col-md-6"><label class="form-label">Union</label><select class="form-select" id="nh-union"><option value="nonunion">Non-union</option><option value="union">Union</option></select></div>' +
			'<div class="col-md-6"><label class="form-label">Union local</label><input class="form-control" id="nh-local" placeholder="Optional"></div>' +
			'<div class="col-md-6"><label class="form-label">Pay frequency</label><select class="form-select" id="nh-freq"><option value="weekly">Weekly</option><option value="biweekly">Biweekly</option></select></div>' +
			'<div class="col-md-6"><label class="form-label">Pay rate (display)</label><input class="form-control" id="nh-rate" placeholder="$32/hr"></div>' +
			'<div class="col-md-6"><label class="form-label">Primary project id</label><input class="form-control" id="nh-project" placeholder="UUID (optional)"></div>' +
			'<div class="col-12"><div class="form-check"><input class="form-check-input" type="checkbox" id="nh-show-rate"><label class="form-check-label" for="nh-show-rate">Show rate on packet</label></div>' +
			'<div class="form-check"><input class="form-check-input" type="checkbox" id="nh-drives"><label class="form-check-label" for="nh-drives">Drives for work</label></div>' +
			'<div class="form-check"><input class="form-check-input" type="checkbox" id="nh-everify"><label class="form-check-label" for="nh-everify">Requires E-Verify (manual)</label></div></div>' +
			'</div></div><div class="modal-footer"><button class="btn btn-primary" type="button" id="nh-save">Create &amp; invite</button></div></div></div></div>' +
			'<div class="modal fade" id="hire-settings-modal" tabindex="-1"><div class="modal-dialog"><div class="modal-content"><div class="modal-header"><h5 class="modal-title">Hire settings</h5><button class="btn-close" data-bs-dismiss="modal"></button></div><div class="modal-body" id="hire-settings-body"></div>' +
			'<div class="modal-footer"><button class="btn btn-primary" type="button" id="hire-settings-save">Save</button></div></div></div></div>';

		function load() {
			var q = [];
			var st = document.getElementById("hire-filter-stage").value;
			if (st) q.push("stage=" + encodeURIComponent(st));
			var week = document.getElementById("hire-filter-week").value;
			if (week) q.push("start_week=" + encodeURIComponent(week));
			if (document.getElementById("hire-filter-i9").checked) q.push("incomplete_i9=1");
			if (document.getElementById("hire-filter-dd").checked) q.push("missing_deposit=1");
			fetchJson("/api/hires" + (q.length ? "?" + q.join("&") : "")).then(function (data) {
				var tb = root.querySelector("#hire-table tbody");
				var rows = data.items || [];
				if (!rows.length) {
					tb.innerHTML = '<tr><td colspan="13">' + empty("No packets", "Create a new hire to send a tokenized packet.") + "</td></tr>";
					return;
				}
				tb.innerHTML = rows.map(function (r) {
					return "<tr><td><a href=\"usis-people-hire-detail.html?id=" + encodeURIComponent(r.id) + "\">" + esc(r.employee) + "</a></td><td>" +
						esc(r.job_title || "") + "</td><td>" + esc(r.start_of_work_date) + "</td><td>" + chip(r.stage) + "</td><td>" + chip(r.w4) +
						"</td><td>" + chip(r.i9_section1) + "</td><td>" + chip(r.i9_section2) + "</td><td>" + chip(r.de4) + "</td><td>" +
						chip(r.deposit) + "</td><td>" + chip(r.notices) + "</td><td>" + esc(r.days_to_i9_section2_due) +
						"</td><td>" + esc(r.owner || "") +
						"</td><td><button class=\"btn btn-sm btn-outline-primary\" data-resend=\"" + esc(r.id) + "\">Resend</button> " +
						"<button class=\"btn btn-sm btn-outline-danger\" data-void=\"" + esc(r.id) + "\">Void</button></td></tr>";
				}).join("");
				if (window.jQuery && window.jQuery.fn.DataTable && !window.jQuery.fn.DataTable.isDataTable("#hire-table")) {
					window.jQuery("#hire-table").DataTable({ paging: true, searching: true, info: false, order: [[2, "asc"]] });
				}
			}).catch(function (e) {
				root.querySelector("#hire-table tbody").innerHTML = '<tr><td colspan="13" class="text-danger">' + esc(e.message) + "</td></tr>";
			});
		}

		document.getElementById("hire-filter-stage").addEventListener("change", load);
		document.getElementById("hire-filter-week").addEventListener("change", load);
		document.getElementById("hire-filter-i9").addEventListener("change", load);
		document.getElementById("hire-filter-dd").addEventListener("change", load);
		document.getElementById("hire-new").addEventListener("click", function () {
			if (window.bootstrap) new window.bootstrap.Modal(document.getElementById("hire-modal")).show();
		});
		document.getElementById("hire-settings").addEventListener("click", function () {
			fetchJson("/api/hires/settings").then(function (s) {
				document.getElementById("hire-settings-body").innerHTML = settingsFields().map(function (row) {
					var key = row[0], label = row[1], type = row[2], secret = row[3];
					var val = s[key] || "";
					var hint = secret ? '<div class="form-text">Leave blank to keep the current value' + (s[key + "_set"] ? " (on file)" : "") + ".</div>" : "";
					return '<label class="form-label">' + esc(label) + "</label>" +
						'<input class="form-control mb-2" data-setting="' + key + '" data-secret="' + (secret ? "1" : "0") + '" type="' + type + '" value="' + esc(secret ? "" : val) + '" placeholder="' + esc(secret ? val : "") + '">' + hint;
				}).join("");
				if (window.bootstrap) new window.bootstrap.Modal(document.getElementById("hire-settings-modal")).show();
			}).catch(function (e) { window.alert(e.message); });
		});
		document.getElementById("hire-settings-save").addEventListener("click", function () {
			var payload = {};
			root.querySelectorAll("[data-setting]").forEach(function (el) {
				var secret = el.getAttribute("data-secret") === "1";
				if (secret && !el.value) return;
				payload[el.getAttribute("data-setting")] = el.value;
			});
			fetchJson("/api/hires/settings", { method: "PATCH", body: JSON.stringify(payload) }).then(function () {
				var modalEl = document.getElementById("hire-settings-modal");
				if (window.bootstrap && modalEl) window.bootstrap.Modal.getInstance(modalEl).hide();
			}).catch(function (e) { window.alert(e.message); });
		});
		document.getElementById("nh-save").addEventListener("click", function () {
			fetchJson("/api/hires", {
				method: "POST",
				body: JSON.stringify({
					job_title: document.getElementById("nh-title").value,
					start_of_work_date: document.getElementById("nh-start").value,
					invite_email: document.getElementById("nh-email").value,
					employment_class: document.getElementById("nh-class").value,
					hire_type: document.getElementById("nh-type").value,
					wage_order: document.getElementById("nh-wo").value,
					union_status: document.getElementById("nh-union").value,
					union_local_name: document.getElementById("nh-local").value,
					pay_frequency: document.getElementById("nh-freq").value,
					pay_rate_display: document.getElementById("nh-rate").value,
					primary_project_id: document.getElementById("nh-project").value || null,
					show_rate_on_packet: document.getElementById("nh-show-rate").checked,
					drives_for_work: document.getElementById("nh-drives").checked,
					requires_e_verify: document.getElementById("nh-everify").checked
				})
			}).then(function (row) {
				return fetchJson("/api/hires/" + row.id + "/invite", { method: "POST", body: "{}" });
			}).then(function (inv) {
				load();
				if (inv && inv.invite_url) showInviteUrl(inv.invite_url);
			}).catch(function (e) { window.alert(e.message); });
		});
		root.addEventListener("click", function (ev) {
			var t = ev.target;
			if (t.getAttribute("data-resend")) {
				fetchJson("/api/hires/" + t.getAttribute("data-resend") + "/resend", { method: "POST", body: "{}" }).then(function (inv) {
					load();
					if (inv && inv.invite_url) showInviteUrl(inv.invite_url);
				}).catch(function (e) { window.alert(e.message); });
			}
			if (t.getAttribute("data-void")) {
				var reason = window.prompt("Void reason?");
				if (!reason) return;
				fetchJson("/api/hires/" + t.getAttribute("data-void") + "/void", { method: "POST", body: JSON.stringify({ reason: reason }) }).then(load).catch(function (e) { window.alert(e.message); });
			}
		});
		load();
	}

	function renderDirectory(root) {
		root.innerHTML = "<h5 class=\"mb-3\">Directory</h5><div class=\"card\"><div class=\"card-body table-responsive\"><table class=\"table table-sm\" id=\"dir-table\"><thead><tr><th>Name</th><th>Email</th><th>Hire stage</th><th>Start</th><th>Clock eligible</th></tr></thead><tbody></tbody></table></div></div>";
		fetchJson("/api/hires/directory").then(function (data) {
			var rows = data.items || [];
			var tb = root.querySelector("tbody");
			if (!rows.length) {
				tb.innerHTML = '<tr><td colspan="5">' + empty("No people", "Users appear here after they exist in USIS CM.") + "</td></tr>";
				return;
			}
			tb.innerHTML = rows.map(function (r) {
				var name = r.hire_packet_id
					? '<a href="usis-people-hire-detail.html?id=' + encodeURIComponent(r.hire_packet_id) + '">' + esc(r.name) + "</a>"
					: esc(r.name);
				return "<tr><td>" + name + "</td><td>" + esc(r.email) + "</td><td>" + (r.hire_stage ? chip(r.hire_stage) : "—") + "</td><td>" +
					esc(r.start_of_work_date) + "</td><td>" + (r.clock_eligible ? "Yes" : "No") + "</td></tr>";
			}).join("");
			if (window.jQuery && window.jQuery.fn.DataTable) window.jQuery("#dir-table").DataTable({ paging: true, searching: true, info: false });
		}).catch(function (e) {
			root.querySelector("tbody").innerHTML = '<tr><td colspan="5" class="text-danger">' + esc(e.message) + "</td></tr>";
		});
	}

	function tabBtn(id, label, on) {
		return '<button class="nav-link' + (on ? " active" : "") + '" data-tab="' + id + '" type="button">' + label + "</button>";
	}

	function renderDetail(root) {
		var id = qs("id");
		if (!id) {
			root.innerHTML = empty("Select a packet", "Open a hire from the board.");
			return;
		}
		ensureInviteModal();
		function load() {
			fetchJson("/api/hires/" + encodeURIComponent(id)).then(function (p) {
				var person = p.person || {};
				var gates = p.payroll_gates || {};
				var labels = p.payroll_gate_labels || {};
				root.innerHTML =
					'<div class="d-flex flex-wrap justify-content-between mb-3"><div><a href="usis-people-hiring.html">Hiring</a>' +
					"<h5 class=\"mt-2 mb-0\">" + esc(p.employee) + "</h5><div class=\"mt-1\">" + chip(p.stage) + " · " + esc(p.job_title) + " · " + esc(p.start_of_work_date) + "</div></div>" +
					'<div class="d-flex gap-1 flex-wrap"><button class="btn btn-sm btn-outline-primary" data-act="invite">Resend invite</button>' +
					'<button class="btn btn-sm btn-outline-secondary" data-act="link">Link user</button>' +
					'<a class="btn btn-sm btn-outline-secondary" href="' + apiBase() + "/api/hires/" + encodeURIComponent(id) + '/i9-packet">I-9 zip</a>' +
					'<a class="btn btn-sm btn-outline-secondary" href="' + apiBase() + "/api/hires/" + encodeURIComponent(id) + '/payroll-packet">Payroll zip</a></div></div>' +
					'<ul class="nav nav-tabs mb-3" id="hire-tabs">' +
					tabBtn("overview", "Overview", true) + tabBtn("data", "Employee data") + tabBtn("forms", "Forms") +
					tabBtn("i9s2", "I-9 Section 2") + tabBtn("notices", "Notices") + tabBtn("payroll", "Payroll setup") +
					tabBtn("audit", "Audit") + '</ul><div id="hire-tab-body"></div>';

				function show(tab) {
					var body = document.getElementById("hire-tab-body");
					root.querySelectorAll("#hire-tabs .nav-link").forEach(function (b) { b.classList.toggle("active", b.getAttribute("data-tab") === tab); });
					if (tab === "overview") {
						body.innerHTML = '<p class="muted small">Form pack ' + esc(p.form_pack_version_id) + " · workflow v" + esc(p.workflow_definition_version) + "</p>" +
							"<p>W-4 " + chip(p.w4) + " · I-9 §1 " + chip(p.i9_section1) + " · I-9 §2 " + chip(p.i9_section2) + "</p>" +
							(p.i9_section2_late ? '<div class="alert alert-warning">I-9 Section 2 is past 3 business days after start.</div>' : "") +
							(p.send_back_note ? '<p class="small">Last send-back note: ' + esc(p.send_back_note) + "</p>" : "") +
							'<label class="form-label">Send back note</label><textarea class="form-control mb-2" id="hire-sendback-note" rows="2"></textarea>' +
							'<button class="btn btn-sm btn-outline-warning me-1" type="button" data-act="sendback">Send back to employee</button>' +
							'<button class="btn btn-sm btn-outline-danger" type="button" data-act="lock">Lock / close packet</button>';
					} else if (tab === "data") {
						body.innerHTML = "<p>SSN " + esc(person.ssn_masked || "—") + ' <button class="btn btn-sm btn-outline-secondary" data-act="reveal">Reveal</button></p>' +
							"<p>" + esc(person.legal_name) + "<br>" + esc(person.email) + " · " + esc(person.mobile) + "<br>" +
							esc(person.address1) + " " + esc(person.city) + " " + esc(person.state) + " " + esc(person.zip) + "</p>" +
							'<p class="small text-muted">Pay rate ' + esc(p.pay_rate_display || "—") + " · frequency " + esc(p.pay_frequency || "") +
							" · union local " + esc(p.union_local_name || "—") + " · E-Verify required " + (p.requires_e_verify ? "yes" : "no") + "</p>" +
							'<pre id="reveal-box" class="small"></pre>';
					} else if (tab === "forms") {
						body.innerHTML = ["w4", "i9", "de4", "dd_auth", "notices"].map(function (k) {
							return '<p><a class="btn btn-sm btn-outline-primary" target="_blank" href="' + apiBase() + "/api/hires/" + encodeURIComponent(id) + "/preview/" + k + '">Open ' + k + "</a></p>";
						}).join("");
					} else if (tab === "i9s2") {
						var i9 = p.i9 || {};
						body.innerHTML = (p.i9_section2_late ? '<div class="alert alert-warning">I-9 Section 2 is late (more than 3 business days after start).</div>' : "") +
							'<p class="small text-muted">Photos are copies only. Examine original documents in person. List A, or List B plus List C — not both.</p>' +
							'<p class="small">Examiner (you): <strong>' + esc(p.examiner_name || "") + "</strong><br>Employer: " +
							esc(p.i9_employer_business_name || "") + "<br>" + esc(p.i9_employer_address || "") + "</p>" +
							'<label class="form-label">Document preset</label><select class="form-select mb-2" id="i9-preset"><option value="">Choose…</option></select>' +
							'<label class="form-label">First day of employment</label><input class="form-control mb-2" id="i9-first" type="date" value="' + esc(i9.first_day_of_employment || p.start_of_work_date || "") + '">' +
							'<label class="form-label">List mode</label><select class="form-select mb-2" id="i9-mode"><option value="A">List A</option><option value="BC">List B + List C</option></select>' +
							'<div id="i9-docs"></div>' +
							'<label class="form-label">Examiner title</label><input class="form-control mb-2" id="i9-title-job" placeholder="Office manager">' +
							'<label class="form-label">Additional information</label><textarea class="form-control mb-2" id="i9-add"></textarea>' +
							'<label class="form-label">Examiner signature</label><canvas id="i9-sig" width="480" height="120" style="width:100%;max-width:28rem;height:120px;border:1px solid #E3E8EE;border-radius:8px;background:#fff;touch-action:none"></canvas>' +
							'<button class="btn btn-sm btn-outline-secondary mb-2" type="button" data-act="i9clear">Clear signature</button>' +
							'<div><button class="btn btn-primary" data-act="i9sign">Save &amp; sign Section 2</button></div>' +
							'<form class="mt-3" id="i9-copy"><input type="file" name="file" class="form-control mb-2">' +
							'<select class="form-select mb-2" name="list_kind" id="i9-copy-kind"><option value="A">List A</option></select>' +
							'<button class="btn btn-sm btn-outline-secondary" type="submit">Upload copy</button></form>';
						function docFields(prefix, title, auth) {
							return '<div class="border rounded p-2 mb-2"><strong class="small">' + esc(prefix) + "</strong>" +
								'<input class="form-control mb-1" id="i9-' + prefix + '-title" placeholder="Document title" value="' + esc(title || "") + '">' +
								'<input class="form-control mb-1" id="i9-' + prefix + '-auth" placeholder="Issuing authority" value="' + esc(auth || "") + '">' +
								'<input class="form-control mb-1" id="i9-' + prefix + '-num" placeholder="Document number">' +
								'<input class="form-control mb-1" id="i9-' + prefix + '-exp" type="date">' +
								'<div class="form-check"><input class="form-check-input" type="checkbox" id="i9-' + prefix + '-na">' +
								'<label class="form-check-label" for="i9-' + prefix + '-na">Expiration N/A</label></div></div>';
						}
						function syncCopyKind() {
							var sel = document.getElementById("i9-copy-kind");
							var modeEl = document.getElementById("i9-mode");
							if (!sel || !modeEl) return;
							if (modeEl.value === "A") sel.innerHTML = '<option value="A">List A</option>';
							else sel.innerHTML = '<option value="B">List B</option><option value="C">List C</option>';
						}
						function paintDocs() {
							var mode = document.getElementById("i9-mode").value;
							var box = document.getElementById("i9-docs");
							if (!box) return;
							if (mode === "A") box.innerHTML = docFields("A", "U.S. Passport", "U.S. Department of State");
							else box.innerHTML = docFields("B", "Driver's license issued by a State", "State DMV") + docFields("C", "Social Security Account Number card", "Social Security Administration");
							syncCopyKind();
						}
						paintDocs();
						document.getElementById("i9-mode").addEventListener("change", paintDocs);
						fetchJson("/api/hires/meta").then(function (meta) {
							var sel = document.getElementById("i9-preset");
							if (!sel) return;
							(meta.i9_presets || []).forEach(function (pr) {
								var o = document.createElement("option");
								o.value = pr.key;
								o.textContent = pr.title;
								o.dataset.mode = pr.mode;
								sel.appendChild(o);
							});
							sel.addEventListener("change", function () {
								var pr = (meta.i9_presets || []).find(function (x) { return x.key === sel.value; });
								if (!pr) return;
								document.getElementById("i9-mode").value = pr.mode;
								paintDocs();
								if (pr.mode === "A") {
									document.getElementById("i9-A-title").value = pr.title;
									document.getElementById("i9-A-auth").value = pr.authority || "";
								} else {
									document.getElementById("i9-B-title").value = pr.b_title || pr.title;
									document.getElementById("i9-B-auth").value = pr.b_authority || pr.authority || "";
									document.getElementById("i9-C-title").value = pr.c_title || "";
									document.getElementById("i9-C-auth").value = pr.c_authority || "";
								}
							});
						}).catch(function () {});
						var canvas = document.getElementById("i9-sig");
						if (canvas) {
							var ctx = canvas.getContext("2d");
							ctx.strokeStyle = "#1B242C";
							ctx.lineWidth = 2;
							var drawing = false;
							function pos(e) {
								var r = canvas.getBoundingClientRect();
								var t = e.touches ? e.touches[0] : e;
								return { x: (t.clientX - r.left) * (canvas.width / r.width), y: (t.clientY - r.top) * (canvas.height / r.height) };
							}
							canvas.addEventListener("pointerdown", function (e) { drawing = true; var pnt = pos(e); ctx.beginPath(); ctx.moveTo(pnt.x, pnt.y); });
							canvas.addEventListener("pointermove", function (e) { if (!drawing) return; var pnt = pos(e); ctx.lineTo(pnt.x, pnt.y); ctx.stroke(); });
							canvas.addEventListener("pointerup", function () { drawing = false; });
						}
					} else if (tab === "notices") {
						body.innerHTML = (p.notice_acks || []).map(function (a) {
							return "<p>" + esc(a.notice_key) + " — " + esc(a.acknowledged_at || "not acknowledged") + "</p>";
						}).join("") || empty("No notices", "Employee acknowledges on the public packet.");
					} else if (tab === "payroll") {
						var keys = Object.keys(gates);
						body.innerHTML = keys.map(function (k) {
							return '<div class="form-check"><input class="form-check-input" disabled type="checkbox" ' + (gates[k] ? "checked" : "") + '><label class="form-check-label">' + esc(labels[k] || k) + "</label></div>";
						}).join("") +
							'<hr><div class="form-check"><input class="form-check-input" type="checkbox" id="flg-de34"' + (p.de34_filed ? " checked" : "") + '><label class="form-check-label">DE 34 filed</label></div>' +
							'<input class="form-control form-control-sm mb-2" id="flg-de34n" placeholder="Confirmation number" value="' + esc(p.de34_confirmation || "") + '">' +
							'<div class="form-check"><input class="form-check-input" type="checkbox" id="flg-qb"' + (p.qb_created ? " checked" : "") + '><label class="form-check-label">QB employee created</label></div>' +
							'<input class="form-control form-control-sm mb-2" id="flg-list" placeholder="QB ListID" value="' + esc(p.qb_list_id || "") + '">' +
							'<button class="btn btn-sm btn-primary" data-act="flags">Save flags</button> ' +
							'<button class="btn btn-sm btn-outline-secondary" data-act="login">Send login</button>';
					} else if (tab === "audit") {
						body.innerHTML = "Loading…";
						fetchJson("/api/hires/" + encodeURIComponent(id) + "/audit").then(function (a) {
							body.innerHTML = (a.items || []).map(function (x) {
								return "<p class=\"small mb-1\">" + esc(x.created_at) + " · " + esc(x.action) + " — " + esc(x.message) + "</p>";
							}).join("") || empty("No events", "");
						});
					}
				}

				root.querySelectorAll("#hire-tabs .nav-link").forEach(function (b) {
					b.addEventListener("click", function () { show(b.getAttribute("data-tab")); });
				});
				show("overview");

				if (!root._hireBound) {
					root._hireBound = true;
					root.addEventListener("click", function (ev) {
						var act = ev.target.getAttribute("data-act");
						if (!act) return;
						var packetId = qs("id");
						if (act === "invite") fetchJson("/api/hires/" + packetId + "/resend", { method: "POST", body: "{}" }).then(function (inv) {
							load();
							if (inv && inv.invite_url) showInviteUrl(inv.invite_url);
						}).catch(function (e) { window.alert(e.message); });
						if (act === "link") fetchJson("/api/hires/" + packetId + "/link-user", { method: "POST", body: "{}" }).then(load).catch(function (e) { window.alert(e.message); });
						if (act === "sendback") {
							fetchJson("/api/hires/" + packetId + "/send-back", {
								method: "POST",
								body: JSON.stringify({ note: (document.getElementById("hire-sendback-note") || {}).value || "" })
							}).then(load).catch(function (e) { window.alert(e.message); });
						}
						if (act === "lock") {
							if (!window.confirm("Lock this packet? The public link will stop working.")) return;
							fetchJson("/api/hires/" + packetId + "/lock", { method: "POST", body: "{}" }).then(load).catch(function (e) { window.alert(e.message); });
						}
						if (act === "reveal") {
							fetchJson("/api/hires/" + packetId + "/reveal-ssn", { method: "POST", body: "{}" }).then(function (j) {
								var box = document.getElementById("reveal-box");
								if (box) box.textContent = "SSN " + j.ssn + (j.dob ? " · DOB " + j.dob : "");
							}).catch(function (e) { window.alert(e.message); });
						}
						if (act === "i9clear") {
							var c0 = document.getElementById("i9-sig");
							if (c0) c0.getContext("2d").clearRect(0, 0, c0.width, c0.height);
						}
						if (act === "i9sign") {
							var mode = document.getElementById("i9-mode").value;
							function readDoc(kind) {
								var na = document.getElementById("i9-" + kind + "-na");
								return {
									list_kind: kind,
									document_title: document.getElementById("i9-" + kind + "-title").value,
									issuing_authority: document.getElementById("i9-" + kind + "-auth").value,
									document_number: document.getElementById("i9-" + kind + "-num").value,
									expiration: document.getElementById("i9-" + kind + "-exp").value,
									expiration_na: !!(na && na.checked)
								};
							}
							var docs = mode === "A" ? [readDoc("A")] : [readDoc("B"), readDoc("C")];
							var sig = document.getElementById("i9-sig");
							fetchJson("/api/hires/" + packetId + "/i9/section2", {
								method: "POST",
								body: JSON.stringify({
									sign: true,
									signature_png: sig ? sig.toDataURL("image/png") : "",
									first_day_of_employment: document.getElementById("i9-first").value,
									document_list_mode: mode,
									documents: docs,
									examiner_title: document.getElementById("i9-title-job").value,
									additional_information: document.getElementById("i9-add").value
								})
							}).then(load).catch(function (e) { window.alert(e.message); });
						}
						if (act === "flags") {
							fetchJson("/api/hires/" + packetId + "/payroll-flags", {
								method: "POST",
								body: JSON.stringify({
									de34_filed: document.getElementById("flg-de34").checked,
									de34_confirmation: document.getElementById("flg-de34n").value,
									qb_created: document.getElementById("flg-qb").checked,
									qb_list_id: document.getElementById("flg-list").value
								})
							}).then(load).catch(function (e) { window.alert(e.message); });
						}
						if (act === "login") fetchJson("/api/hires/" + packetId + "/send-login", { method: "POST", body: "{}" }).then(function () { window.alert("Login email queued."); }).catch(function (e) { window.alert(e.message); });
					});
					root.addEventListener("submit", function (ev) {
						if (ev.target.id !== "i9-copy") return;
						ev.preventDefault();
						var packetId = qs("id");
						var fd = new FormData(ev.target);
						fetch(apiBase() + "/api/hires/" + encodeURIComponent(packetId) + "/i9/copies", { method: "POST", body: fd, credentials: "include" })
							.then(function (r) { return r.json(); })
							.then(load)
							.catch(function (e) { window.alert(e.message); });
					});
				}
			}).catch(function (e) {
				root.innerHTML = '<p class="text-danger">' + esc(e.message) + "</p>";
			});
		}
		load();
	}

	document.addEventListener("DOMContentLoaded", function () {
		var page = document.body.getAttribute("data-people-page");
		if (page === "hiring") renderHiring(document.getElementById("usis-hiring-root"));
		if (page === "directory") renderDirectory(document.getElementById("usis-directory-root"));
		if (page === "detail") renderDetail(document.getElementById("usis-hire-detail-root"));
	});
})();
