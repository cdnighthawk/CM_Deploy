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
		return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/"/g, "&quot;");
	}

	function fmtDate(iso) {
		if (!iso) return "—";
		try {
			var d = new Date(iso);
			if (isNaN(d.getTime())) return esc(iso);
			return esc(
				d.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" })
			);
		} catch (e) {
			return esc(iso);
		}
	}

	function isOverdue(dueIso, completedIso) {
		if (!dueIso || completedIso) return false;
		var t = new Date(dueIso).getTime();
		if (isNaN(t)) return false;
		return t < Date.now();
	}

	/** Expired or expiring within 30 days — same visual language as overdue HR training. */
	function certExpiryRowClass(expiresIso) {
		if (!expiresIso) return "";
		var t = new Date(expiresIso).getTime();
		if (isNaN(t)) return "";
		var now = Date.now();
		if (t < now) return "table-danger";
		var days = (t - now) / 86400000;
		if (days <= 30) return "table-warning";
		return "";
	}

	function payBasisLabel(basis) {
		var m = {
			hourly: "Hourly",
			salary: "Salary",
			prevailing_reference: "Prevailing reference",
			other: "Other",
		};
		var b = basis && String(basis).trim();
		return esc(m[b] || (b ? b.replace(/_/g, " ") : "—"));
	}

	function categoryLabel(cat) {
		if (!cat) return "—";
		return esc(String(cat).replace(/_/g, " "));
	}

	function docHubHref(documentId) {
		return "usis-documents-hub.html?document_id=" + encodeURIComponent(documentId);
	}

	function userIdFromQuery() {
		var id = new URLSearchParams(window.location.search).get("id");
		return id && String(id).trim() ? String(id).trim() : "";
	}

	function setText(id, text) {
		var el = document.getElementById(id);
		if (el) el.textContent = text;
	}

	function tbodyRows(tbodyId, rows, cols) {
		var tbody = document.getElementById(tbodyId);
		if (!tbody) return;
		tbody.innerHTML = "";
		if (!rows || !rows.length) {
			tbody.innerHTML =
				'<tr><td colspan="' + cols + '" class="text-muted small">No rows.</td></tr>';
			return;
		}
		rows.forEach(function (row) {
			var tr = document.createElement("tr");
			if (row.rowClass) tr.className = row.rowClass;
			tr.innerHTML = row.html;
			tbody.appendChild(tr);
		});
	}

	function renderPendingApprovals(items) {
		var wrap = document.getElementById("usis-hr-emp-pending-approvals-wrap");
		if (!wrap) return;
		if (!items || !items.length) {
			wrap.classList.add("d-none");
			return;
		}
		wrap.classList.remove("d-none");
		tbodyRows(
			"usis-hr-emp-pending-approvals-body",
			items.map(function (it) {
				return {
					html:
						"<td>" +
						esc(it.policy_title || it.policy_version) +
						'</td><td class="text-end small"><code>' +
						esc(it.approval_request_id) +
						"</code></td>",
				};
			}),
			2
		);
	}

	function renderDocumentLinks(links) {
		var wrap = document.getElementById("usis-hr-emp-doc-links-wrap");
		var ul = document.getElementById("usis-hr-emp-doc-links-list");
		if (!wrap || !ul) return;
		ul.innerHTML = "";
		if (!links || !links.length) {
			wrap.classList.add("d-none");
			return;
		}
		wrap.classList.remove("d-none");
		links.forEach(function (L) {
			var li = document.createElement("li");
			li.className = "mb-1";
			li.innerHTML =
				'<a href="' +
				esc(docHubHref(L.document_id)) +
				'">' +
				esc(L.label) +
				"</a> <span class=\"text-muted\">(" +
				esc(L.context) +
				")</span>";
			ul.appendChild(li);
		});
	}

	function policyStatusCell(it) {
		if (it.signed_at) {
			return '<span class="badge bg-success">Signed</span>';
		}
		if (it.pending_approval) {
			return '<span class="badge bg-warning text-dark">Approval pending</span>';
		}
		if (it.pending_signature) {
			return '<span class="badge bg-secondary">Signature pending</span>';
		}
		return '<span class="badge bg-light text-muted">—</span>';
	}

	function loadEmployee() {
		var statusEl = document.getElementById("usis-hr-emp-api-status");
		var contentEl = document.getElementById("usis-hr-emp-content");
		var uid = userIdFromQuery();
		if (!uid) {
			if (statusEl) {
				statusEl.textContent =
					"Missing id — open this page from the HR dashboard (employee name link) or add ?id=<user-uuid> to the URL.";
				statusEl.classList.add("text-warning");
			}
			return;
		}
		var base = apiBase();
		fetch(base + "/api/v1/hr/employees/" + encodeURIComponent(uid), { credentials: "include" })
			.then(function (r) {
				return r.json().then(function (data) {
					return { r: r, data: data };
				});
			})
			.then(function (bundle) {
				if (bundle.data && bundle.data.is_applicant_only && bundle.data.application_review_url) {
					window.location.replace(bundle.data.application_review_url);
					return;
				}
				if (bundle.r.status === 403) {
					if (statusEl) {
						statusEl.textContent =
							(bundle.data && bundle.data.message) ||
							"You do not have permission to view this employee.";
						statusEl.classList.remove("text-warning");
						statusEl.classList.add("text-danger");
					}
					if (contentEl) contentEl.classList.add("d-none");
					return;
				}
				if (!bundle.r.ok) {
					var msg =
						bundle.data && bundle.data.error
							? String(bundle.data.error)
							: "HTTP " + bundle.r.status;
					if (bundle.data && bundle.data.message) msg = String(bundle.data.message);
					throw new Error(msg);
				}
				var data = bundle.data;
				var u = data.user || {};
				if (statusEl) {
					statusEl.textContent =
						"Live data: users, hr_* (onboarding, policies, training, pay scales, HR docs), safety_training_records.";
					statusEl.classList.remove("text-danger", "text-warning");
				}
				if (contentEl) contentEl.classList.remove("d-none");
				setText("usis-hr-emp-name", u.name || u.email || "—");
				setText("usis-hr-emp-email", u.email || "—");
				setText("usis-hr-emp-id", u.id || "—");
				setText("usis-hr-emp-phone", u.phone && String(u.phone).trim() ? u.phone : "—");
				setText(
					"usis-hr-emp-active",
					u.is_active === false ? "Inactive" : u.is_active === true ? "Active" : "—"
				);
				setText("usis-hr-emp-last-login", u.last_login_at ? fmtDate(u.last_login_at) : "—");

				renderPendingApprovals(data.pending_hr_approvals || []);
				renderDocumentLinks(data.document_links || []);

				tbodyRows(
					"usis-hr-emp-onb-body",
					(data.onboarding_items || []).map(function (it) {
						var docCell = "—";
						if (it.document_id) {
							docCell =
								'<a href="' +
								esc(docHubHref(it.document_id)) +
								'" class="small">Open</a>';
						}
						return {
							html:
								"<td>" +
								esc(it.title) +
								'</td><td class="text-end">' +
								esc(it.sort_order != null ? it.sort_order : "—") +
								'</td><td class="text-end small">' +
								fmtDate(it.completed_at) +
								'</td><td class="text-end">' +
								docCell +
								"</td>",
						};
					}),
					4
				);
				tbodyRows(
					"usis-hr-emp-pol-body",
					(data.policy_acknowledgments || []).map(function (it) {
						return {
							html:
								"<td>" +
								esc(it.policy_title || it.policy_version) +
								"</td><td>" +
								policyStatusCell(it) +
								'</td><td class="text-end small">' +
								fmtDate(it.signed_at) +
								"</td>",
						};
					}),
					3
				);
				tbodyRows(
					"usis-hr-emp-trn-body",
					(data.training_assignments || []).map(function (it) {
						var overdue = isOverdue(it.due_at, it.completed_at);
						return {
							rowClass: overdue ? "table-warning" : "",
							html:
								"<td>" +
								esc(it.course_title || it.course_key) +
								'</td><td class="text-end small">' +
								fmtDate(it.due_at) +
								'</td><td class="text-end small">' +
								fmtDate(it.completed_at) +
								"</td>",
						};
					}),
					3
				);
				tbodyRows(
					"usis-hr-emp-certs-body",
					(data.regulatory_certifications || []).map(function (it) {
						var docCell = "—";
						if (it.document_id) {
							docCell =
								'<a href="' +
								esc(docHubHref(it.document_id)) +
								'" class="small">Open</a>';
						}
						var cred = it.credential_number && String(it.credential_number).trim();
						return {
							rowClass: certExpiryRowClass(it.expires_at),
							html:
								"<td>" +
								esc(it.training_label || it.training_type || "—") +
								'</td><td class="text-end small">' +
								fmtDate(it.completed_at) +
								'</td><td class="text-end small">' +
								fmtDate(it.expires_at) +
								"</td><td class=\"small\">" +
								esc(cred || "—") +
								'</td><td class="text-end">' +
								docCell +
								"</td>",
						};
					}),
					5
				);

				var payHint = document.getElementById("usis-hr-emp-pay-edit-hint");
				var caps = data.capabilities || {};
				if (payHint) {
					if (!caps.can_edit_hr_employee_records) payHint.classList.remove("d-none");
					else payHint.classList.add("d-none");
				}

				var dispatchNew = document.getElementById("usis-hr-emp-dispatch-new");
				if (dispatchNew) {
					if (caps.can_edit_hr_employee_records) dispatchNew.classList.remove("d-none");
					else dispatchNew.classList.add("d-none");
					dispatchNew.onclick = function () {
						createDispatchRevision(uid);
					};
				}
				tbodyRows(
					"usis-hr-emp-dispatch-body",
					(data.employee_dispatches || []).map(function (it) {
						return {
							html:
								"<td class=\"small\">" +
								esc(it.project_name || it.project_id || "—") +
								'</td><td class="text-end">' +
								esc(it.revision != null ? it.revision : "—") +
								'</td><td class="text-end small">' +
								fmtDate(it.effective_date) +
								'</td><td class="text-end small">' +
								esc(it.hourly_rate_snapshot || "—") +
								"</td><td class=\"small\">" +
								esc(it.notes || "—") +
								"</td>",
						};
					}),
					5
				);

				tbodyRows(
					"usis-hr-emp-pay-body",
					(data.pay_scales || []).map(function (it) {
						var docCell = "—";
						if (it.document_id) {
							docCell =
								'<a href="' +
								esc(docHubHref(it.document_id)) +
								'" class="small">Open</a>';
						}
						var wr = it.wage_rate && it.wage_rate.label ? it.wage_rate.label : "—";
						var cur = it.currency ? " " + esc(it.currency) : "";
						return {
							html:
								"<td class=\"small\">" +
								esc(it.label || "—") +
								"</td><td class=\"small\">" +
								payBasisLabel(it.pay_basis) +
								'</td><td class="text-end small">' +
								(it.hourly_rate != null && it.hourly_rate !== "" ? esc(it.hourly_rate) + cur : "—") +
								'</td><td class="text-end small">' +
								(it.annual_salary != null && it.annual_salary !== "" ? esc(it.annual_salary) + cur : "—") +
								'</td><td class="text-end small">' +
								fmtDate(it.effective_from) +
								'</td><td class="text-end small">' +
								fmtDate(it.effective_to) +
								'</td><td class="small">' +
								esc(wr) +
								'</td><td class="text-end">' +
								docCell +
								"</td>",
						};
					}),
					8
				);
				tbodyRows(
					"usis-hr-emp-hrdocs-body",
					(data.hr_employee_documents || []).map(function (it) {
						var docCell = "—";
						if (it.document_id) {
							docCell =
								'<a href="' +
								esc(docHubHref(it.document_id)) +
								'" class="small">Open</a>';
						}
						return {
							html:
								"<td class=\"small\">" +
								categoryLabel(it.category) +
								"</td><td class=\"small\">" +
								esc(it.title || "—") +
								'</td><td class="text-end">' +
								docCell +
								"</td>",
						};
					}),
					3
				);
			})
			.catch(function (err) {
				if (statusEl) {
					statusEl.textContent = "Could not load employee: " + (err && err.message ? err.message : err);
					statusEl.classList.add("text-danger");
				}
				if (contentEl) contentEl.classList.add("d-none");
			});
	}

	function createDispatchRevision(userId) {
		var base = apiBase();
		fetch(base + "/api/v1/hr/projects-picker", { credentials: "include" })
			.then(function (r) {
				return r.json().then(function (d) {
					return { r: r, d: d };
				});
			})
			.then(function (bundle) {
				if (!bundle.r.ok) throw new Error("Could not load projects");
				var items = bundle.d.items || [];
				if (!items.length) {
					window.alert("No projects available.");
					return;
				}
				var list = items
					.slice(0, 30)
					.map(function (p, i) {
						return i + 1 + ") " + (p.name || p.id);
					})
					.join("\n");
				var pick = window.prompt("Select project (number):\n" + list, "1");
				if (pick === null) return;
				var idx = parseInt(pick, 10) - 1;
				if (isNaN(idx) || idx < 0 || idx >= items.length) return;
				var proj = items[idx];
				var eff = window.prompt("Effective date (YYYY-MM-DD):", new Date().toISOString().slice(0, 10));
				if (eff === null) return;
				var rate = window.prompt("Hourly rate snapshot (optional):", "");
				var notes = window.prompt("Notes (optional):", "");
				var body = {
					project_id: proj.id,
					effective_date: String(eff).trim() || null,
					hourly_rate_snapshot: rate && String(rate).trim() ? String(rate).trim() : null,
					notes: notes && String(notes).trim() ? String(notes).trim() : null,
				};
				return fetch(base + "/api/v1/hr/employees/" + encodeURIComponent(userId) + "/dispatches", {
					method: "POST",
					credentials: "include",
					headers: { "Content-Type": "application/json" },
					body: JSON.stringify(body),
				});
			})
			.then(function (r) {
				if (!r) return;
				return r.json().then(function (d) {
					if (!r.ok) throw new Error((d && d.error) || "Create failed");
					loadEmployee();
				});
			})
			.catch(function (e) {
				window.alert(e.message || String(e));
			});
	}

	if (document.readyState === "loading") {
		document.addEventListener("DOMContentLoaded", loadEmployee);
	} else {
		loadEmployee();
	}
})();
