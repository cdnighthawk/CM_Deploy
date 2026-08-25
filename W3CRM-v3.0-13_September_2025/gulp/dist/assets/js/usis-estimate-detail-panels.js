/**
 * Estimate detail — Job information, Drawings, Specs (static), RFI tabs.
 * Job information loads from the lead (GET /lead-estimates/:id). An Estimate row is not required.
 * Also listens for CustomEvent "usis-lead-estimate-loaded" { detail: { item, error? } }.
 * When item.project_id is set, loads project job + drawings + RFIs (same APIs as project detail).
 */
(function () {
	"use strict";

	var docPanels =
		typeof window.USISProjectDocPanels !== "undefined"
			? window.USISProjectDocPanels.init({
					returnUrl: true,
					ensureProjectFromLead: true,
					allowDrawingsWithoutProject: true,
					fromPage: "estimate",
					projectIdGlobalKey: "__USIS_ESTIMATE_PROJECT_ID__",
					getProjectId: function (it) {
						return it && (it.drawing_project_id || it.project_id);
					},
					panes: {
						drawings: "estd-pane-drawings",
						specs: "estd-pane-specs",
						rfi: "estd-pane-rfi",
					},
					ids: {
						drawingsNoProject: "usis-estd-drawings-no-project",
						drawingsTools: "usis-estd-drawings-tools",
						openViewer: "usis-estd-open-viewer",
						drawingUploadOpen: "usis-estd-drawing-upload-open",
						gridDrawings: "usis-estd-grid-drawings",
						searchDrawings: "usis-estd-search-drawings",
						filterDrawingDiscipline: "usis-estd-filter-drawing-discipline",
						filterDrawingSet: "usis-estd-filter-drawing-set",
						specsNoProject: "usis-estd-specs-no-project",
						specsRoot: "usis-estd-specs-root",
						specsOpenFull: "usis-estd-specs-open-full",
						rfiNoProject: "usis-estd-rfi-no-project",
						rfiTools: "usis-estd-rfi-tools",
						rfiOpenLog: "usis-estd-rfi-open-log",
						rfiOpenCreate: "usis-estd-rfi-open-create",
						searchRfis: "usis-estd-search-rfis",
						filterRfiStatus: "usis-estd-filter-rfi-status",
						tbodyRfis: "usis-estd-tbody-rfis",
						drawingUploadSubmit: "usis-estd-drawing-upload-submit",
						drawingUploadErr: "usis-estd-drawing-upload-err",
						drawingFile: "usis-estd-drawing-file",
						modalDrawingCreate: "usis-estd-modal-drawing-create",
					},
			  })
			: null;

	function explicitWindowApiBase() {
		if (typeof window.USIS_API_BASE !== "string") return null;
		var s = window.USIS_API_BASE.trim().replace(/\/$/, "");
		if (!s) return null;
		try {
			if (new URL(s).origin === window.location.origin) return null;
		} catch (e) {
			/* keep s */
		}
		return s;
	}

	function metaApiBase() {
		if (typeof document === "undefined" || !document.querySelector) return null;
		var m = document.querySelector('meta[name="usis-api-base"]');
		if (!m) return null;
		var c = (m.getAttribute("content") || "").trim().replace(/\/$/, "");
		return c || null;
	}

	function apiBase() {
		if (typeof window.usisApiBase === "function") {
			return window.usisApiBase();
		}
		var fromWin = explicitWindowApiBase();
		if (fromWin) return fromWin;
		var fromMeta = metaApiBase();
		if (fromMeta) return fromMeta;
		var loc = window.location;
		if (loc.protocol === "file:") return "http://127.0.0.1:5000";
		var host = loc.hostname || "";
		var proto = loc.protocol || "http:";
		var port = String(loc.port || "");
		var devPorts = {
			3000: 1,
			3001: 1,
			3002: 1,
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
		if (devPorts[port]) return "";
		var loopback = host === "localhost" || host === "127.0.0.1" || host === "::1";
		if (loopback) {
			if (port === "5000") return "";
			return proto + "//" + host + ":5000";
		}
		var ipv4 = /^\d{1,3}(\.\d{1,3}){3}$/.test(host);
		if (ipv4 && port && port !== "5000" && port !== "80" && port !== "443") {
			return proto + "//" + host + ":5000";
		}
		if ((host === "host.docker.internal" || host.endsWith(".local")) && port && port !== "5000") {
			return proto + "//" + host + ":5000";
		}
		return "";
	}

	function actorHeaders() {
		var id = null;
		try {
			id = window.localStorage.getItem("usisActorUserId");
		} catch (e) {}
		if (id && id.trim()) {
			return { "X-Usis-User-Id": id.trim() };
		}
		return {};
	}

	function resolveAssetUrl(u) {
		if (u == null || u === "") return "";
		var s = String(u).trim();
		if (!s) return "";
		if (/^https?:\/\//i.test(s)) return s;
		var b = apiBase();
		return b + (s.charAt(0) === "/" ? s : "/" + s);
	}

	function esc(s) {
		if (s == null) return "";
		var d = document.createElement("div");
		d.textContent = String(s);
		return d.innerHTML;
	}

	function fmtDash(s) {
		if (s == null || String(s).trim() === "") return '<span class="text-muted">—</span>';
		return esc(String(s).trim());
	}

	function fmtDate(iso) {
		if (!iso) return '<span class="text-muted">—</span>';
		try {
			var d = new Date(iso);
			if (isNaN(d.getTime())) return esc(String(iso));
			return esc(d.toLocaleDateString());
		} catch (e) {
			return esc(String(iso));
		}
	}

	function fmtMoney(n) {
		if (n == null || n === "") return '<span class="text-muted">—</span>';
		var x = Number(n);
		if (isNaN(x)) return esc(String(n));
		try {
			return esc(
				x.toLocaleString(undefined, { style: "currency", currency: "USD", maximumFractionDigits: 2 })
			);
		} catch (e) {
			return esc(String(x));
		}
	}

	function tr(label, innerHtml) {
		return (
			"<tr><th class=\"text-muted small fw-normal\" style=\"width:42%\">" +
			esc(label) +
			"</th><td>" +
			innerHtml +
			"</td></tr>"
		);
	}

	function setJobLoading(show) {
		var pane = document.getElementById("estd-pane-job");
		if (!pane) return;
		var n = pane.querySelector("[data-usis-estd-job-loading]");
		if (n) n.classList.toggle("d-none", !show);
	}

	function setJobErr(msg) {
		var pane = document.getElementById("estd-pane-job");
		if (!pane) return;
		var n = pane.querySelector("[data-usis-estd-job-error]");
		if (!n) return;
		if (msg) {
			n.textContent = msg;
			n.classList.remove("d-none");
		} else {
			n.textContent = "";
			n.classList.add("d-none");
		}
	}

	function setPaneLoading(paneId, loading) {
		var el = document.getElementById(paneId);
		if (!el) return;
		var n = el.querySelector("[data-usis-loading]");
		if (n) n.classList.toggle("d-none", !loading);
	}

	function setPaneError(paneId, msg) {
		var el = document.getElementById(paneId);
		if (!el) return;
		var n = el.querySelector("[data-usis-error]");
		if (!n) return;
		if (msg) {
			n.textContent = msg;
			n.classList.remove("d-none");
		} else {
			n.textContent = "";
			n.classList.add("d-none");
		}
	}

	function fetchJson(path) {
		var base = apiBase();
		var url = base + path;
		return fetch(url, {
			credentials: "include",
			headers: Object.assign({ Accept: "application/json" }, actorHeaders()),
		}).then(function (res) {
			if (!res.ok) {
				return res.text().then(function (t) {
					throw new Error(res.status + " " + (t || res.statusText));
				});
			}
			return res.json();
		});
	}

	function formatIsoDateTime(iso) {
		if (!iso) return null;
		try {
			var d = new Date(iso);
			if (isNaN(d.getTime())) return String(iso);
			try {
				return d.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
			} catch (e2) {
				return d.toLocaleString();
			}
		} catch (e) {
			return String(iso);
		}
	}

	function formatMoneyCur(n, currency) {
		if (n == null || n === "") return null;
		var cur = (currency || "USD").toString().trim() || "USD";
		try {
			return new Intl.NumberFormat(undefined, { style: "currency", currency: cur }).format(Number(n));
		} catch (e) {
			return Number(n).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + " " + cur;
		}
	}

	function formatPercent(p) {
		if (p == null || p === "") return null;
		var x = Number(p);
		if (isNaN(x)) return null;
		if (x >= 0 && x <= 1) x = x * 100;
		return x.toFixed(1).replace(/\.0$/, "") + "%";
	}

	function formatLocation(loc) {
		if (!loc || typeof loc !== "object") return null;
		var keys = [
			"formatted",
			"formattedAddress",
			"address",
			"address1",
			"street",
			"line1",
			"city",
			"state",
			"region",
			"postalCode",
			"zip",
			"country",
		];
		var parts = [];
		var seen = {};
		for (var i = 0; i < keys.length; i++) {
			var v = loc[keys[i]];
			if (v == null || String(v).trim() === "") continue;
			var text = String(v).trim();
			if (seen[text.toLowerCase()]) continue;
			seen[text.toLowerCase()] = 1;
			parts.push(text);
		}
		return parts.length ? parts.join(", ") : null;
	}

	function submissionBadgeClass(state) {
		var s = (state || "").toLowerCase();
		if (!s) return "bg-secondary";
		if (s.indexOf("declin") >= 0 || s.indexOf("lost") >= 0 || s.indexOf("no bid") >= 0) return "bg-danger";
		if (s.indexOf("submit") >= 0 || s.indexOf("award") >= 0 || s.indexOf("won") >= 0) return "bg-success";
		if (s.indexOf("review") >= 0 || s.indexOf("undecided") >= 0 || s.indexOf("new") >= 0) return "bg-warning text-dark";
		return "bg-primary";
	}

	function yn(v) {
		if (v === true) return "Yes";
		if (v === false) return "No";
		return "—";
	}

	function appendFieldRow(tbody, label, htmlValue) {
		if (!tbody) return;
		var row = document.createElement("tr");
		row.innerHTML =
			'<th class="text-muted fw-normal ps-3 py-2" scope="row" style="width:42%">' +
			esc(label) +
			'</th><td class="py-2 pe-3">' +
			htmlValue +
			"</td>";
		tbody.appendChild(row);
	}

	function appendDateRow(tbody, label, iso) {
		appendFieldRow(tbody, label, iso ? fmtDash(formatIsoDateTime(iso)) : '<span class="text-muted">—</span>');
	}

	function setJobBadges(container, item) {
		if (!container) return;
		container.innerHTML = "";
		function addBadge(text, cls) {
			if (!text) return;
			var span = document.createElement("span");
			span.className = "badge " + (cls || "bg-secondary") + " me-1 mb-1";
			span.textContent = text;
			container.appendChild(span);
		}
		if (item.submission_state) addBadge(item.submission_state, submissionBadgeClass(item.submission_state));
		if (item.workflow_bucket) addBadge(item.workflow_bucket, "bg-dark");
		if (item.source) addBadge(String(item.source).replace(/_/g, " "), "bg-light text-dark border");
		if (item.trade_name) addBadge("Trade: " + item.trade_name, "bg-light text-dark border");
		if (item.estimate_approved_at) addBadge("Estimate approved", "bg-success");
		else if (item.estimate_locked_at) addBadge("Estimate locked", "bg-secondary");
		if (item.priority) addBadge("Priority: " + item.priority, "bg-info text-dark");
		if (item.request_type) addBadge(item.request_type, "bg-secondary");
		if (item.market_sector) addBadge(item.market_sector, "bg-secondary");
		if (item.status) addBadge(item.status, "bg-light text-dark border");
	}

	function renderMembers(container, members) {
		if (!container) return;
		container.innerHTML = "";
		if (!members) {
			container.innerHTML = '<p class="text-muted mb-0 small">No team list in import.</p>';
			return;
		}
		if (Array.isArray(members) && members.length) {
			var ul = document.createElement("ul");
			ul.className = "list-unstyled mb-0";
			members.forEach(function (m) {
				if (!m || typeof m !== "object") return;
				var li = document.createElement("li");
				li.className = "mb-2 pb-2 border-bottom";
				var name =
					m.name ||
					[m.firstName, m.lastName].filter(Boolean).join(" ") ||
					m.displayName ||
					m.email ||
					"Member";
				var role = m.role || m.title || m.tradeName || "";
				var co = (m.company && m.company.name) || m.companyName || "";
				li.innerHTML =
					'<div class="fw-medium">' +
					esc(name) +
					"</div>" +
					(role ? '<div class="text-muted">' + esc(role) + "</div>" : "") +
					(co ? '<div class="text-muted">' + esc(co) + "</div>" : "");
				ul.appendChild(li);
			});
			container.appendChild(ul);
			return;
		}
		container.innerHTML = '<p class="text-muted mb-0 small">No team list in import.</p>';
	}

	function showJobRoot() {
		var root = document.getElementById("usis-estd-job-root");
		if (root) root.classList.remove("d-none");
	}

	function groupParentOf(item) {
		var gs = item && item.group_summary;
		return (gs && gs.parent) || null;
	}

	function isChildOpportunity(item) {
		var gs = item && item.group_summary;
		if (gs && gs.role === "child") return true;
		return !!(item && item.external_parent_id);
	}

	function renderJobDetailed(item) {
		var parent = groupParentOf(item);
		var jobName = (parent && parent.name) || item.name || "Untitled opportunity";
		var jobNumber = (parent && parent.number) || item.number;
		var title = document.getElementById("usis-estd-job-title");
		if (title) title.textContent = jobNumber ? jobNumber + " | " + jobName : jobName;

		var sub = document.getElementById("usis-estd-job-subtitle");
		if (sub) {
			var bits = [];
			if (item.trade_name) bits.push(item.trade_name);
			if (item.city || item.state) bits.push([item.city, item.state].filter(Boolean).join(", "));
			sub.textContent = bits.join(" · ") || "Opportunity details";
		}

		var dueBadge = document.getElementById("usis-estd-job-badge-due");
		if (dueBadge) {
			if (item.due_at) {
				dueBadge.className = "badge bg-danger fs-6 fw-normal";
				var dueStr = formatIsoDateTime(item.due_at);
				dueBadge.textContent = dueStr ? "Due " + dueStr : "Due (see dates)";
			} else {
				dueBadge.className = "badge bg-light text-muted border fs-6 fw-normal";
				dueBadge.textContent = "No bid due date";
			}
		}

		setJobBadges(document.getElementById("usis-estd-job-badges"), item);

		var cur = item.default_currency || "USD";
		var pub = document.getElementById("usis-estd-job-public-tbody");
		if (pub) {
			pub.innerHTML = "";
			appendFieldRow(pub, "Project #", fmtDash(jobNumber));
			appendFieldRow(pub, "Project name", fmtDash(jobName));
			appendDateRow(pub, "Bid due", item.due_at);
			var locStr = formatLocation(item.location);
			if (locStr) {
				appendFieldRow(pub, "Location", '<div class="small" style="white-space:pre-wrap;">' + esc(locStr) + "</div>");
			} else if (item.city || item.state) {
				appendFieldRow(pub, "Location", fmtDash([item.city, item.state].filter(Boolean).join(", ")));
			} else {
				appendFieldRow(pub, "Location", '<span class="text-muted">No location on file.</span>');
			}
			appendDateRow(pub, "Job walk", item.job_walk_at);
			appendDateRow(pub, "RFIs due", item.rfis_due_at);
			appendDateRow(pub, "Expected start", item.expected_start_at);
			appendDateRow(pub, "Expected finish", item.expected_finish_at);
			appendFieldRow(pub, "Project size", fmtDash(formatMoneyCur(item.project_size, cur)));
			appendFieldRow(pub, "Architect", fmtDash(item.architect || item.architect_company_name));
			appendFieldRow(pub, "Engineer", fmtDash(item.engineer));
			appendFieldRow(pub, "Property owner", fmtDash(item.property_owner || item.owner_company_name));
			appendFieldRow(pub, "Tenant", fmtDash(item.property_tenant));
			appendDateRow(pub, "Invite received", item.invited_at);
			appendDateRow(pub, "Contract start", item.contract_start_at || item.contract_date || item.start_date);
			appendDateRow(pub, "Created (BC)", item.bc_created_at);
			appendDateRow(pub, "Last updated (BC)", item.bc_updated_at);
		}

		var desc = document.getElementById("usis-estd-job-description");
		if (desc) {
			var narrative = item.project_information || item.notes;
			if (narrative && String(narrative).trim()) {
				desc.innerHTML = '<div class="small" style="white-space:pre-wrap;">' + esc(narrative) + "</div>";
			} else {
				desc.innerHTML =
					'<p class="text-muted small mb-0">No project description was provided in Building Connected for this opportunity.</p>';
			}
		}

		var trade = document.getElementById("usis-estd-job-trade");
		if (trade) {
			if (item.trade_specific_instructions && String(item.trade_specific_instructions).trim()) {
				trade.innerHTML =
					'<div style="white-space:pre-wrap;">' + esc(item.trade_specific_instructions) + "</div>";
			} else {
				trade.innerHTML = '<p class="text-muted small mb-0">No trade-specific instructions.</p>';
			}
		}

		var adv = document.getElementById("usis-estd-job-advanced");
		if (adv) {
			var abits = [];
			abits.push("<div><strong>NDA required:</strong> " + yn(item.is_nda_required) + "</div>");
			abits.push("<div><strong>Sealed bidding:</strong> " + yn(item.is_sealed_bidding) + "</div>");
			abits.push("<div><strong>Discoverable / public project:</strong> " + yn(item.project_is_public) + "</div>");
			abits.push("<div><strong>Archived:</strong> " + yn(item.is_archived) + "</div>");
			if (item.is_parent != null) {
				abits.push("<div><strong>Parent invite (BC):</strong> " + yn(item.is_parent) + "</div>");
			}
			adv.innerHTML = abits.join("");
		}

		var priv = document.getElementById("usis-estd-job-private-tbody");
		if (priv) {
			priv.innerHTML = "";
			appendFieldRow(priv, "Request type / budgeting", fmtDash(item.request_type));
			appendFieldRow(priv, "Client (company)", fmtDash(item.company_name || item.gc_company_name));
			appendFieldRow(priv, "Primary contact", fmtDash(item.client_contact));
			appendFieldRow(priv, "Fee %", fmtDash(formatPercent(item.fee_percentage)));
			appendFieldRow(priv, "Profit margin", fmtDash(formatPercent(item.profit_margin)));
			appendFieldRow(priv, "Market sector", fmtDash(item.market_sector));
			appendFieldRow(priv, "Owning office (id)", fmtDash(item.owning_office_id));
			appendFieldRow(priv, "Workflow bucket", fmtDash(item.workflow_bucket));
			appendFieldRow(priv, "ROM", fmtDash(formatMoneyCur(item.rom, cur)));
			appendFieldRow(
				priv,
				"Project value / final",
				fmtDash(formatMoneyCur(item.final_value != null ? item.final_value : item.contract_value, cur))
			);
			appendFieldRow(priv, "CRM stage", fmtDash(item.crm_stage));
			appendFieldRow(priv, "Win probability", fmtDash(formatPercent(item.win_probability)));
			appendFieldRow(priv, "Estimating hours", fmtDash(item.estimating_hours));
			appendFieldRow(priv, "Contract duration (days)", fmtDash(item.contract_duration));
			appendFieldRow(priv, "Avg. crew size", fmtDash(item.average_crew_size));
			if (item.takeoff_line_count != null) {
				appendFieldRow(priv, "Takeoff lines", '<span class="fw-medium">' + esc(String(item.takeoff_line_count)) + "</span>");
			}
			appendFieldRow(priv, "Priority", fmtDash(item.priority));
			appendDateRow(priv, "Follow-up", item.follow_up_at);
		}

		renderMembers(document.getElementById("usis-estd-job-members"), item.members);

		var foot = document.getElementById("usis-estd-job-footer");
		if (foot) {
			var lid = item.external_id || item.id;
			var extras = [];
			extras.push(
				"Building Connected ref <code>" +
					esc(item.external_id || "—") +
					"</code> · Internal id <code>" +
					esc(item.id || "—") +
					"</code>"
			);
			if (item.project_id) {
				extras.push(' · Linked project <code class="ms-1">' + esc(item.project_id) + "</code>");
				extras.push(
					' · <a class="link-secondary" href="construction/project-detail.html?id=' +
						encodeURIComponent(item.project_id) +
						'">Open project workspace</a>'
				);
			}
			if (lid) {
				extras.push(
					' · <a class="link-primary" href="construction/lead-detail.html?id=' +
						encodeURIComponent(lid) +
						'">Open lead</a>'
				);
			}
			foot.innerHTML = extras.join("");
		}

		showJobRoot();
	}

	function renderJobFromProject(item) {
		renderJobDetailed({
			name: item.name,
			number: item.number,
			city: item.city,
			state: item.state,
			location: {
				address: [item.address_line1, item.address_line2].filter(Boolean).join(", "),
				city: item.city,
				state: item.state,
				postalCode: item.postal_code,
				country: item.country,
			},
			status: item.status,
			request_type: item.project_type,
			architect_company_name: item.architect_company_name,
			owner_company_name: item.owner_company_name,
			gc_company_name: item.gc_company_name,
			contract_value: item.contract_value,
			contract_date: item.contract_date,
			start_date: item.start_date,
			notes: item.notes,
			id: item.id,
			project_id: item.id,
			external_id: item.primary_lead_detail_id,
		});
	}

	function pick(item, snap, key) {
		if (item && item[key] != null && item[key] !== "") return item[key];
		if (snap && snap[key] != null && snap[key] !== "") return snap[key];
		return item ? item[key] : null;
	}

	function leadFromEstimateItem(item) {
		var snap = (item && item.lead) || {};
		function g(key) {
			return pick(item, snap, key);
		}
		return {
			name: snap.name || item.lead_name || item.name,
			number: snap.number || item.number,
			trade_name: g("trade_name"),
			submission_state: g("submission_state"),
			crm_stage: g("crm_stage"),
			location: item.location || snap.location,
			city: item.city || snap.city,
			state: item.state || snap.state,
			company_name: g("company_name"),
			rom: g("rom"),
			win_probability: g("win_probability"),
			due_at: snap.due_at || item.due_at,
			project_information: g("project_information"),
			architect: g("architect"),
			engineer: g("engineer"),
			property_owner: g("property_owner"),
			property_tenant: g("property_tenant"),
			job_walk_at: g("job_walk_at"),
			rfis_due_at: g("rfis_due_at"),
			expected_start_at: g("expected_start_at"),
			expected_finish_at: g("expected_finish_at"),
			client_contact: g("client_contact"),
			request_type: g("request_type"),
			market_sector: g("market_sector"),
			trade_specific_instructions: g("trade_specific_instructions"),
			invited_at: g("invited_at"),
			contract_start_at: g("contract_start_at"),
			bc_created_at: g("bc_created_at"),
			bc_updated_at: g("bc_updated_at"),
			follow_up_at: g("follow_up_at"),
			project_size: g("project_size"),
			default_currency: g("default_currency") || "USD",
			is_nda_required: g("is_nda_required"),
			is_sealed_bidding: g("is_sealed_bidding"),
			project_is_public: g("project_is_public"),
			is_archived: g("is_archived"),
			is_parent: g("is_parent"),
			external_parent_id: g("external_parent_id"),
			fee_percentage: g("fee_percentage"),
			profit_margin: g("profit_margin"),
			owning_office_id: g("owning_office_id"),
			workflow_bucket: g("workflow_bucket"),
			final_value: g("final_value"),
			estimating_hours: g("estimating_hours"),
			contract_duration: g("contract_duration"),
			average_crew_size: g("average_crew_size"),
			takeoff_line_count: g("takeoff_line_count"),
			priority: g("priority"),
			source: g("source"),
			members: g("members"),
			client: g("client") || item.client,
			group_summary: item.group_summary || snap.group_summary,
			estimate_approved_at: g("estimate_approved_at") || item.approved_at,
			estimate_locked_at: g("estimate_locked_at") || item.locked_at,
			project_id: item.project_id || snap.project_id,
			external_id: snap.external_id || item.external_id,
			id:
				item.lead_id ||
				item.lead_estimate_id ||
				snap.id ||
				snap.external_id ||
				item.external_id ||
				item.id,
		};
	}

	function renderJobFromLead(raw) {
		renderJobDetailed(leadFromEstimateItem(raw));
	}

	function pageLeadKeys(item) {
		var urlId = (new URLSearchParams(window.location.search).get("id") || "").trim();
		var keys = {};
		function add(v) {
			if (v != null && String(v).trim()) keys[String(v).trim()] = true;
		}
		add(urlId);
		if (item) {
			add(item.id);
			add(item.external_id);
			add(item.lead_id);
			add(item.lead_estimate_id);
		}
		return keys;
	}

	function companyInitials(name) {
		var parts = String(name || "")
			.trim()
			.split(/\s+/)
			.filter(Boolean);
		if (!parts.length) return "GC";
		if (parts.length === 1) return parts[0].slice(0, 2);
		return (parts[0].charAt(0) + parts[1].charAt(0));
	}

	function formatDueCountdown(iso) {
		var due = new Date(iso);
		if (isNaN(due.getTime())) return null;
		var ms = due.getTime() - Date.now();
		if (ms <= 0 || ms > 48 * 60 * 60 * 1000) return null;
		var totalMin = Math.floor(ms / 60000);
		var hours = Math.floor(totalMin / 60);
		var mins = totalMin % 60;
		if (hours <= 0) return "Due " + mins + "m";
		return "Due " + hours + "h " + mins + "m";
	}

	function groupChildStatus(child) {
		var bucket = String(child.workflow_bucket || "").toUpperCase();
		var state = String(child.submission_state || "").toUpperCase().replace(/-/g, "_");
		var archived = child.is_archived === true || bucket.indexOf("ARCHIVED") >= 0;
		var declined = state === "DECLINED" || bucket.indexOf("DECLINED") >= 0;
		if (declined) return { text: archived ? "Declined / Archived" : "Declined", dueSoon: false };
		if (archived) {
			var accepted = state === "WILL_SUBMIT" || state === "SUBMITTED" || bucket.indexOf("ACCEPTED") >= 0;
			return { text: accepted ? "Accepted / Archived" : "Archived", dueSoon: false };
		}
		if (child.due_at) {
			var countdown = formatDueCountdown(child.due_at);
			if (countdown) return { text: countdown, dueSoon: true };
			var dueLabel = formatIsoDateTime(child.due_at);
			return { text: dueLabel ? "Due " + dueLabel : "Due", dueSoon: false };
		}
		return { text: child.submission_state || "—", dueSoon: false };
	}

	function estimateDetailHref(id) {
		if (!id) return "#";
		return "construction/estimate-detail.html?id=" + encodeURIComponent(id);
	}

	function formatClientFromJson(client) {
		if (!client || typeof client !== "object") return { company: "", contact: "", office: "" };
		var company = "";
		if (client.company && client.company.name) company = String(client.company.name);
		var office = client.office && client.office.name ? String(client.office.name) : "";
		if (company && office && company.toLowerCase().indexOf(office.toLowerCase()) < 0) {
			company = company + " - " + office;
		}
		var pc = client.lead || client.primaryContact || client.contact || {};
		var name = [pc.firstName || pc.first_name, pc.lastName || pc.last_name].filter(Boolean).join(" ");
		var phone = pc.phoneNumber || pc.phone || pc.mobile || "";
		var email = pc.email || pc.emailAddress || "";
		return { company: company, contact: [name, phone, email].filter(Boolean).join(" | "), office: office };
	}

	function setNavLink(el, href, enabled) {
		if (!el) return;
		if (enabled && href) {
			el.href = href;
			el.classList.remove("disabled");
		} else {
			el.href = "#";
			el.classList.add("disabled");
		}
	}

	function renderChildOpportunity(raw) {
		var nav = document.getElementById("usis-estd-child-nav");
		var card = document.getElementById("usis-estd-opp-detail");
		var clientBox = document.getElementById("usis-estd-opp-client");
		var tbody = document.getElementById("usis-estd-opp-tbody");
		var gs = raw && raw.group_summary;
		var childView = isChildOpportunity(raw);
		if (!childView) {
			if (nav) nav.classList.add("d-none");
			if (card) card.classList.add("d-none");
			return;
		}
		var parent = (gs && gs.parent) || {};
		var siblings = (gs && gs.children) || [];
		var currentId = String(raw.external_id || raw.id || "");
		var idx = -1;
		siblings.forEach(function (c, i) {
			if (c.external_id === currentId || c.id === currentId) idx = i;
		});
		setNavLink(
			document.getElementById("usis-estd-back-group"),
			estimateDetailHref(parent.external_id || parent.id),
			!!(parent.external_id || parent.id)
		);
		setNavLink(
			document.getElementById("usis-estd-prev-opp"),
			idx > 0 ? estimateDetailHref(siblings[idx - 1].external_id || siblings[idx - 1].id) : "",
			idx > 0
		);
		setNavLink(
			document.getElementById("usis-estd-next-opp"),
			idx >= 0 && idx < siblings.length - 1
				? estimateDetailHref(siblings[idx + 1].external_id || siblings[idx + 1].id)
				: "",
			idx >= 0 && idx < siblings.length - 1
		);
		var indexEl = document.getElementById("usis-estd-opp-index");
		if (indexEl) {
			indexEl.textContent = idx >= 0 ? idx + 1 + " of " + siblings.length : siblings.length ? siblings.length + " opportunities" : "";
		}
		if (nav) nav.classList.remove("d-none");

		var parsed = formatClientFromJson(raw.client);
		var company = raw.company_name || parsed.company || "—";
		var contact = raw.client_contact || parsed.contact || "";
		if (clientBox) {
			clientBox.innerHTML =
				'<div class="text-uppercase text-muted small fw-semibold mb-1">Client</div>' +
				'<div class="d-flex align-items-start gap-2">' +
				'<div class="usis-estd-group-avatar" aria-hidden="true">' +
				esc(companyInitials(company)) +
				"</div>" +
				"<div>" +
				'<div class="fw-semibold">' +
				esc(company) +
				"</div>" +
				(contact ? '<div class="text-muted small">' + esc(contact) + "</div>" : "") +
				"</div></div>";
		}
		if (tbody) {
			tbody.innerHTML = "";
			appendFieldRow(tbody, "Opportunity", fmtDash(raw.name));
			appendFieldRow(tbody, "Trade", fmtDash(raw.trade_name || "(no trade)"));
			appendDateRow(tbody, "Invited", raw.invited_at);
			appendDateRow(tbody, "Date due", raw.due_at);
			appendDateRow(tbody, "Job walk", raw.job_walk_at);
			appendDateRow(tbody, "RFIs due", raw.rfis_due_at);
			appendFieldRow(tbody, "Status", fmtDash(raw.submission_state));
		}
		if (card) card.classList.remove("d-none");
	}

	function renderGroupSummary(summary, item) {
		var card = document.getElementById("usis-estd-group-summary");
		var list = document.getElementById("usis-estd-group-summary-list");
		var countEl = document.getElementById("usis-estd-group-summary-count");
		if (!card || !list) return;
		var children = summary && Array.isArray(summary.children) ? summary.children : [];
		if (!children.length || isChildOpportunity(item)) {
			card.classList.add("d-none");
			list.innerHTML = "";
			if (countEl) countEl.textContent = "";
			return;
		}
		var current = pageLeadKeys(item);
		list.innerHTML = "";
		children.forEach(function (child) {
			var gc = child.company_name || "";
			var trade = child.trade_name || "(no trade)";
			var status = groupChildStatus(child);
			var isCurrent = !!(current[child.id] || current[child.external_id]);
			var href = child.external_id
				? "construction/estimate-detail.html?id=" + encodeURIComponent(child.external_id)
				: "construction/estimate-detail.html?id=" + encodeURIComponent(child.id || "");
			var row = document.createElement("a");
			row.href = href;
			row.className = "usis-estd-group-row" + (isCurrent ? " is-current" : "");
			row.innerHTML =
				'<div class="usis-estd-group-avatar" aria-hidden="true">' +
				esc(companyInitials(gc || child.name)) +
				"</div>" +
				'<div class="flex-grow-1" style="min-width:0">' +
				'<div class="fw-semibold">' +
				esc(gc || child.name || "Untitled opportunity") +
				"</div>" +
				'<div class="text-muted small">' +
				esc(trade) +
				"</div>" +
				"</div>" +
				'<div class="text-end small text-nowrap' +
				(status.dueSoon ? " usis-estd-group-due" : " text-muted") +
				'">' +
				esc(status.text) +
				"</div>";
			list.appendChild(row);
		});
		if (countEl) countEl.textContent = String(children.length);
		card.classList.remove("d-none");
	}

	function loadJobPanel(le) {
		setJobErr("");
		setJobLoading(false);
		renderJobFromLead(le);
		renderChildOpportunity(le);
		renderGroupSummary(le && le.group_summary, le);
	}

	function onLeadEstimateLoaded(ev) {
		var d = ev.detail || {};
		var item = d.item || d.lead;
		if (item) {
			loadJobPanel(item);
			if (docPanels) docPanels.onItemLoaded(item);
			return;
		}
		if (jobRootVisible()) return;
		setJobLoading(false);
		setJobErr(d.error || "Could not load job information.");
		if (docPanels) docPanels.showNoProject();
	}

	function jobRootVisible() {
		var jr = document.getElementById("usis-estd-job-root");
		return jr && !jr.classList.contains("d-none");
	}

	function loadJobFromUrl() {
		var id = new URLSearchParams(window.location.search).get("id");
		if (!id || !String(id).trim()) {
			setJobLoading(false);
			setJobErr("Open this page from Estimates or a lead.");
			if (docPanels) docPanels.showNoProject();
			return;
		}
		setJobErr("");
		setJobLoading(true);
		fetchJson("/api/v1/lead-estimates/" + encodeURIComponent(id))
			.then(function (data) {
				if (!data.item) throw new Error("Lead not found.");
				loadJobPanel(data.item);
				if (docPanels) docPanels.onItemLoaded(data.item);
			})
			.catch(function () {
				return fetchJson("/api/v1/estimates/" + encodeURIComponent(id)).then(function (data) {
					if (!data.item) throw new Error("Job information not found.");
					loadJobPanel(data.item);
					if (docPanels) docPanels.onItemLoaded(data.item);
				});
			})
			.catch(function (err) {
				if (jobRootVisible()) return;
				setJobLoading(false);
				setJobErr(err.message || String(err));
				if (docPanels) docPanels.showNoProject();
			});
	}

	document.addEventListener("usis-lead-estimate-loaded", onLeadEstimateLoaded);

	document.addEventListener("DOMContentLoaded", function () {
		loadJobFromUrl();
	});
})();
