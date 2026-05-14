/**
 * Lead detail — Job info tab: Building Connected–style layout, data from
 * GET /api/v1/lead-estimates/<id> (UUID or external_id).
 */
(function () {
	"use strict";

	var DEV_SERVER_PORTS = {
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

	function explicitWindowApiBase() {
		if (typeof window.USIS_API_BASE !== "string") return null;
		var s = window.USIS_API_BASE.trim().replace(/\/$/, "");
		if (!s) return null;
		// Mis-set to the static page origin → same as relative /api, yields HTML 404 from dev server.
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
		var fromWin = explicitWindowApiBase();
		if (fromWin) return fromWin;
		var fromMeta = metaApiBase();
		if (fromMeta) return fromMeta;

		var loc = window.location;
		if (loc.protocol === "file:") {
			return "http://127.0.0.1:5000";
		}
		var host = loc.hostname || "";
		var proto = loc.protocol || "http:";
		var port = String(loc.port || "");
		if (DEV_SERVER_PORTS[port]) {
			return proto + "//" + host + ":5000";
		}
		var loopback = host === "localhost" || host === "127.0.0.1" || host === "::1";
		if (loopback) {
			if (port === "5000") {
				return "";
			}
			return proto + "//" + host + ":5000";
		}
		// LAN / Docker Desktop: static on :3001 etc. but not in the fixed list above.
		var ipv4 = /^\d{1,3}(\.\d{1,3}){3}$/.test(host);
		if (ipv4 && port && port !== "5000" && port !== "80" && port !== "443") {
			return proto + "//" + host + ":5000";
		}
		if ((host === "host.docker.internal" || host.endsWith(".local")) && port && port !== "5000") {
			return proto + "//" + host + ":5000";
		}
		return "";
	}

	function leadIdFromQuery() {
		var id = new URLSearchParams(window.location.search).get("id");
		return id && id.trim() ? id.trim() : null;
	}

	function esc(s) {
		if (s == null) return "";
		var d = document.createElement("div");
		d.textContent = String(s);
		return d.innerHTML;
	}

	function textOrDash(s) {
		if (s == null || String(s).trim() === "") return '<span class="text-muted">—</span>';
		return esc(String(s).trim());
	}

	function formatIsoDate(iso) {
		if (!iso) return null;
		try {
			var d = new Date(iso);
			if (isNaN(d.getTime())) return String(iso);
			try {
				return d.toLocaleString(undefined, {
					dateStyle: "medium",
					timeStyle: "short",
				});
			} catch (e2) {
				try {
					return (
						d.toLocaleDateString() +
						" " +
						d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" })
					);
				} catch (e3) {
					return d.toString();
				}
			}
		} catch (e) {
			return String(iso);
		}
	}

	function formatMoney(n, currency) {
		if (n == null || n === "") return null;
		var cur = (currency || "USD").toString().trim() || "USD";
		try {
			return new Intl.NumberFormat(undefined, { style: "currency", currency: cur }).format(Number(n));
		} catch (e) {
			try {
				return Number(n).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + " " + cur;
			} catch (e2) {
				return String(n) + " " + cur;
			}
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
		for (var i = 0; i < keys.length; i++) {
			var v = loc[keys[i]];
			if (v != null && String(v).trim() !== "") parts.push(String(v).trim());
		}
		if (parts.length) return parts.join(", ");
		try {
			return JSON.stringify(loc);
		} catch (e) {
			return "[location]";
		}
	}

	function submissionBadgeClass(state) {
		var s = (state || "").toLowerCase();
		if (!s) return "bg-secondary";
		if (s.indexOf("declin") >= 0 || s.indexOf("lost") >= 0 || s.indexOf("no bid") >= 0) return "bg-danger";
		if (s.indexOf("submit") >= 0 || s.indexOf("award") >= 0 || s.indexOf("won") >= 0) return "bg-success";
		if (s.indexOf("review") >= 0 || s.indexOf("undecided") >= 0 || s.indexOf("new") >= 0) return "bg-warning text-dark";
		return "bg-primary";
	}

	function appendFieldRow(tbody, label, htmlValue) {
		if (!tbody) return;
		var tr = document.createElement("tr");
		tr.innerHTML =
			'<th class="text-muted fw-normal ps-3 py-2" scope="row" style="width:42%">' +
			esc(label) +
			'</th><td class="py-2 pe-3">' +
			htmlValue +
			"</td>";
		tbody.appendChild(tr);
	}

	function appendDateRow(tbody, label, iso) {
		if (!iso || !tbody) return;
		var formatted = formatIsoDate(iso);
		appendFieldRow(tbody, label, textOrDash(formatted));
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
			ul.className = "list-unstyled mb-0 small";
			members.forEach(function (m) {
				if (!m || typeof m !== "object") return;
				var li = document.createElement("li");
				li.className = "mb-2 pb-2 border-bottom border-light";
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
		var pre = document.createElement("pre");
		pre.className = "small mb-0 text-wrap";
		try {
			pre.textContent = JSON.stringify(members, null, 2);
		} catch (e) {
			pre.textContent = String(members);
		}
		container.appendChild(pre);
	}

	function setBadges(container, item) {
		if (!container || !item) return;
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
		if (item.priority) addBadge("Priority: " + item.priority, "bg-info text-dark");
		if (item.request_type) addBadge(item.request_type, "bg-secondary");
		if (item.market_sector) addBadge(item.market_sector, "bg-secondary");
	}

	function yn(v) {
		if (v === true) return "Yes";
		if (v === false) return "No";
		return "—";
	}

	function renderCrmToolbar(item) {
		var el = document.getElementById("usis-crm-toolbar");
		if (!el || !item || !item.id) return;
		el.classList.remove("d-none");
		var stages = ["New Lead", "Invited", "Estimating", "Submitted", "Awarded", "Lost"];
		var stage = item.crm_stage || "New Lead";
		var opts = stages
			.map(function (s) {
				return '<option value="' + esc(s) + '"' + (s === stage ? " selected" : "") + ">" + esc(s) + "</option>";
			})
			.join("");
		el.innerHTML =
			'<div class="card border-0 shadow-sm"><div class="card-body py-2 d-flex flex-wrap gap-2 align-items-center">' +
			'<label class="small mb-0 text-muted text-uppercase">CRM</label>' +
			'<select class="form-select form-select-sm" style="max-width:13rem" id="usis-crm-stage">' +
			opts +
			"</select>" +
			'<button type="button" class="btn btn-sm btn-outline-secondary" id="usis-crm-save-stage">Save stage</button>' +
			'<button type="button" class="btn btn-sm btn-success" id="usis-crm-award">Award (new project)</button>' +
			'<button type="button" class="btn btn-sm btn-outline-primary" id="usis-crm-ai">AI feasibility</button>' +
			'<a class="btn btn-sm btn-outline-dark" href="usis-rfp-list.html?lead_estimate_id=' +
			encodeURIComponent(item.id) +
			'">RFP list</a>' +
			"</div></div>";
		var idForApi = item.id;
		var sel = document.getElementById("usis-crm-stage");
		var save = document.getElementById("usis-crm-save-stage");
		if (save && sel) {
			save.addEventListener("click", function () {
				fetch(apiBase() + "/api/v1/lead-estimates/" + encodeURIComponent(idForApi), {
					method: "PATCH",
					headers: { "Content-Type": "application/json" },
					credentials: "omit",
					body: JSON.stringify({ crm_stage: sel.value }),
				})
					.then(function (res) {
						return res.json().then(function (j) {
							if (!res.ok) throw new Error(j.error || res.status);
							return j;
						});
					})
					.then(function () {
						if (window.USISNotify) window.USISNotify.success("Stage saved");
					})
					.catch(function (e) {
						if (window.USISNotify) window.USISNotify.error(String(e.message || e));
					});
			});
		}
		var award = document.getElementById("usis-crm-award");
		if (award) {
			award.addEventListener("click", function () {
				if (!window.confirm("Create a project and mark this lead Awarded?")) return;
				fetch(apiBase() + "/api/v1/lead-estimates/" + encodeURIComponent(idForApi) + "/award", {
					method: "POST",
					headers: { "Content-Type": "application/json" },
					credentials: "omit",
					body: JSON.stringify({}),
				})
					.then(function (res) {
						return res.json().then(function (j) {
							if (!res.ok) throw new Error(j.error || res.status);
							return j;
						});
					})
					.then(function (data) {
						if (window.USISNotify) window.USISNotify.success("Awarded");
						if (data.item) render(data.item);
					})
					.catch(function (e) {
						if (window.USISNotify) window.USISNotify.error(String(e.message || e));
					});
			});
		}
		var ai = document.getElementById("usis-crm-ai");
		if (ai) {
			ai.addEventListener("click", function () {
				fetch(apiBase() + "/api/v1/lead-estimates/" + encodeURIComponent(idForApi) + "/ai-feasibility", {
					method: "POST",
					headers: { "Content-Type": "application/json" },
					credentials: "omit",
					body: JSON.stringify({}),
				})
					.then(function (res) {
						return res.json();
					})
					.then(function (j) {
						if (window.aiReviewBus) {
							window.aiReviewBus.emit("review_requested", { mode: "bid_feasibility_review", payload: j });
						}
						if (window.USISNotify) window.USISNotify.info((j && j.message) || "AI feasibility queued (stub).");
					})
					.catch(function () {
						if (window.USISNotify) window.USISNotify.error("AI request failed");
					});
			});
		}
	}

	function render(item) {
		if (!item || typeof item !== "object") return;

		var loading = document.getElementById("usis-job-loading");
		var err = document.getElementById("usis-job-error");
		var root = document.getElementById("usis-job-root");
		if (loading) loading.classList.add("d-none");
		if (err) {
			err.classList.add("d-none");
			err.textContent = "";
		}
		if (root) root.classList.remove("d-none");

		var title = document.getElementById("usis-job-title");
		if (title) title.textContent = item.name || "Untitled opportunity";

		var sub = document.getElementById("usis-job-subtitle");
		if (sub) {
			var bits = [];
			if (item.number) bits.push(item.number);
			if (item.city || item.state) bits.push([item.city, item.state].filter(Boolean).join(", "));
			sub.textContent = bits.join(" · ") || "Opportunity details";
		}

		var dueBadge = document.getElementById("usis-job-badge-due");
		if (dueBadge) {
			if (item.due_at) {
				dueBadge.className = "badge bg-danger fs-6 fw-normal";
				var dueStr = formatIsoDate(item.due_at);
				dueBadge.textContent = dueStr ? "Due " + dueStr : "Due (see dates)";
			} else {
				dueBadge.className = "badge bg-light text-muted border fs-6 fw-normal";
				dueBadge.textContent = "No bid due date";
			}
		}

		setBadges(document.getElementById("usis-job-badges"), item);

		renderCrmToolbar(item);

		var pub = document.getElementById("usis-job-public-tbody");
		if (pub) {
			pub.innerHTML = "";
			appendFieldRow(pub, "Project #", textOrDash(item.number));
			appendFieldRow(pub, "Project name", textOrDash(item.name));
			appendDateRow(pub, "Bid due", item.due_at);
			var locStr = formatLocation(item.location);
			if (locStr) {
				appendFieldRow(pub, "Location", '<div class="small" style="white-space:pre-wrap;">' + esc(locStr) + "</div>");
			} else if (item.city || item.state) {
				appendFieldRow(pub, "Location", textOrDash([item.city, item.state].filter(Boolean).join(", ")));
			} else {
				appendFieldRow(pub, "Location", '<span class="text-muted">No location on file.</span>');
			}
			appendDateRow(pub, "Job walk", item.job_walk_at);
			appendDateRow(pub, "RFIs due", item.rfis_due_at);
			appendDateRow(pub, "Expected start", item.expected_start_at);
			appendDateRow(pub, "Expected finish", item.expected_finish_at);
			var cur = item.default_currency || "USD";
			if (item.project_size != null) {
				appendFieldRow(pub, "Project size", textOrDash(formatMoney(item.project_size, cur)));
			}
			appendFieldRow(pub, "Architect", textOrDash(item.architect));
			appendFieldRow(pub, "Engineer", textOrDash(item.engineer));
			appendFieldRow(pub, "Property owner", textOrDash(item.property_owner));
			appendFieldRow(pub, "Tenant", textOrDash(item.property_tenant));
			appendDateRow(pub, "Invite received", item.invited_at);
			appendDateRow(pub, "Contract start", item.contract_start_at);
			appendDateRow(pub, "Created (BC)", item.bc_created_at);
			appendDateRow(pub, "Last updated (BC)", item.bc_updated_at);
		}

		var desc = document.getElementById("usis-job-description");
		if (desc) {
			if (item.project_information && String(item.project_information).trim()) {
				desc.innerHTML =
					'<div class="small" style="white-space:pre-wrap;">' + esc(item.project_information) + "</div>";
			} else {
				desc.innerHTML =
					'<p class="text-muted small mb-0">No project description was provided in Building Connected for this opportunity.</p>';
			}
		}

		var trade = document.getElementById("usis-job-trade");
		if (trade) {
			if (item.trade_specific_instructions && String(item.trade_specific_instructions).trim()) {
				trade.innerHTML =
					'<div class="small" style="white-space:pre-wrap;">' + esc(item.trade_specific_instructions) + "</div>";
			} else {
				trade.innerHTML =
					'<p class="text-muted small mb-0">No trade-specific instructions.</p>';
			}
		}

		var adv = document.getElementById("usis-job-advanced");
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

		var priv = document.getElementById("usis-job-private-tbody");
		if (priv) {
			priv.innerHTML = "";
			var cur2 = item.default_currency || "USD";
			appendFieldRow(priv, "Request type / budgeting", textOrDash(item.request_type));
			appendFieldRow(priv, "Client (company)", textOrDash(item.company_name));
			appendFieldRow(priv, "Primary contact", textOrDash(item.client_contact));
			if (item.fee_percentage != null) {
				var fp = formatPercent(item.fee_percentage);
				appendFieldRow(priv, "Fee %", textOrDash(fp || String(item.fee_percentage)));
			}
			if (item.profit_margin != null) {
				var pm = formatPercent(item.profit_margin);
				appendFieldRow(priv, "Profit margin", textOrDash(pm || String(item.profit_margin)));
			}
			appendFieldRow(priv, "Market sector", textOrDash(item.market_sector));
			appendFieldRow(priv, "Owning office (id)", textOrDash(item.owning_office_id));
			appendFieldRow(priv, "Workflow bucket", textOrDash(item.workflow_bucket));
			if (item.rom != null) appendFieldRow(priv, "ROM", textOrDash(formatMoney(item.rom, cur2)));
			if (item.final_value != null)
				appendFieldRow(priv, "Project value / final", textOrDash(formatMoney(item.final_value, cur2)));
			appendFieldRow(priv, "CRM stage", textOrDash(item.crm_stage));
			var wp = formatPercent(item.win_probability);
			if (wp) appendFieldRow(priv, "Win probability", esc(wp));
			if (item.estimating_hours != null)
				appendFieldRow(priv, "Estimating hours", textOrDash(String(item.estimating_hours)));
			if (item.contract_duration != null)
				appendFieldRow(priv, "Contract duration (days)", textOrDash(String(item.contract_duration)));
			if (item.average_crew_size != null)
				appendFieldRow(priv, "Avg. crew size", textOrDash(String(item.average_crew_size)));
			if (item.takeoff_line_count != null) {
				appendFieldRow(
					priv,
					"Takeoff lines",
					'<span class="fw-medium">' + esc(String(item.takeoff_line_count)) + "</span>"
				);
			}
			appendFieldRow(priv, "Priority", textOrDash(item.priority));
			appendDateRow(priv, "Follow-up", item.follow_up_at);
			if (!priv.children.length) {
				appendFieldRow(priv, "Details", '<span class="text-muted">No private-summary fields in import.</span>');
			}
		}

		renderMembers(document.getElementById("usis-job-members"), item.members);

		var foot = document.getElementById("usis-job-footer");
		if (foot) {
			foot.innerHTML =
				"Building Connected ref <code>" +
				esc(item.external_id || "") +
				"</code> · Internal id <code>" +
				esc(item.id || "") +
				"</code>" +
				(item.project_id
					? ' · Linked project <code class="ms-1">' + esc(item.project_id) + "</code>"
					: "");
		}

		try {
			document.dispatchEvent(new CustomEvent("usis-lead-loaded", { detail: { item: item } }));
		} catch (e) {
			/* ignore */
		}
	}

	function showError(msg) {
		var loading = document.getElementById("usis-job-loading");
		var err = document.getElementById("usis-job-error");
		var root = document.getElementById("usis-job-root");
		if (loading) loading.classList.add("d-none");
		if (root) root.classList.add("d-none");
		if (err) {
			err.textContent = msg;
			err.classList.remove("d-none");
		}
	}

	function load() {
		var lid = leadIdFromQuery();
		if (!lid) {
			showError("Add a lead id to the URL (?id=…) to load Building Connected job info.");
			return;
		}
		var url = apiBase() + "/api/v1/lead-estimates/" + encodeURIComponent(lid);
		fetch(url, { credentials: "omit" })
			.then(function (res) {
				if (!res.ok) {
					return res.text().then(function (t) {
						var body = (t || "").trim();
						if (res.status === 404 && /<!doctype/i.test(body)) {
							throw new Error(
								"API returned HTML 404 (wrong server). Point the page at Flask: add " +
									'<meta name="usis-api-base" content="http://127.0.0.1:5000"> in &lt;head&gt;, or set window.USIS_API_BASE to your API root (not the static site URL). Hard-refresh after changing JS.'
							);
						}
						if (res.status === 404) {
							throw new Error(
								"Lead not found for id " +
									lid +
									". Use the UUID from our database or the Building Connected id exactly as imported (external_id)."
							);
						}
						throw new Error(res.status + " " + (body || res.statusText));
					});
				}
				return res.json();
			})
			.then(function (data) {
				var item = data.item;
				if (!item) throw new Error("Invalid API response");
				try {
					render(item);
				} catch (e) {
					if (typeof console !== "undefined" && console.error) console.error("usis lead-detail render", e);
					showError("Page render failed: " + (e.message || String(e)));
				}
			})
			.catch(function (e) {
				showError(e.message || String(e));
			});
	}

	if (document.readyState === "loading") {
		document.addEventListener("DOMContentLoaded", load);
	} else {
		load();
	}
})();
