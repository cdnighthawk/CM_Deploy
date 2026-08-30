/**
 * Estimate detail: load a real Estimate record + takeoff lines, edit grid, rollups, cost library hints.
 * Expects URL ?id=<estimate UUID>. Legacy lead ids redirect to the lead's current estimate.
 */
(function () {
	var API =
		typeof window.usisApiBase === "function"
			? window.usisApiBase()
			: typeof window.USIS_API_BASE === "string"
				? window.USIS_API_BASE.trim().replace(/\/$/, "")
				: "http://127.0.0.1:5000";
	var Api = typeof window.USISEstimateApi !== "undefined" ? window.USISEstimateApi : null;
	var leadKey = null;
	var leadItem = null;
	var sessionMe = null;
	var activeLineId = null;
	var dirtyByLine = {};
	var lineAutoFilter = null;

	function parentLeadId(item) {
		if (Api) return Api.leadIdFromItem(item);
		if (!item) return null;
		var lead = item.lead || {};
		return item.lead_id || item.lead_estimate_id || lead.id || item.external_id || item.id || null;
	}

	function jobProjectId(item) {
		if (!item) return null;
		var lead = item.lead || {};
		return item.project_id || lead.project_id || null;
	}

	function isAwardedJob(item) {
		if (!item) return false;
		var lead = item.lead || {};
		var stage = String(lead.crm_stage || item.crm_stage || "").toLowerCase();
		var estStatus = String(item.status || "").toLowerCase();
		return (stage === "awarded" || estStatus === "awarded") && !!jobProjectId(item);
	}

	function awardLeadId(item) {
		return parentLeadId(item) || (item && (item.id || item.external_id)) || leadKey;
	}

	function isEstimateRecord(item) {
		if (!item) return false;
		if (item.entity === "lead_estimate") return false;
		if (item.entity === "estimate") return true;
		return !!(item.lead_estimate_id && item.id && item.id !== item.lead_estimate_id);
	}

	function syncConvertJobButtons(item) {
		var awardBtns = document.querySelectorAll(".usis-estd-award-job");
		var openBtns = document.querySelectorAll(".usis-estd-open-job");
		var pid = jobProjectId(item);
		var awarded = isAwardedJob(item);
		var canAward = !awarded;
		awardBtns.forEach(function (btn) {
			btn.classList.toggle("d-none", !canAward);
			btn.disabled = false;
		});
		openBtns.forEach(function (openBtn) {
			if (pid && awarded) {
				openBtn.classList.remove("d-none");
				openBtn.setAttribute("href", "construction/project-detail.html?id=" + encodeURIComponent(pid));
			} else {
				openBtn.classList.add("d-none");
				openBtn.removeAttribute("href");
			}
		});
	}

	function convertEstimateToJob() {
		var leadId = awardLeadId(leadItem);
		if (!leadId) {
			flashErr("Open this page from a lead or estimate, then award the job.");
			return;
		}
		if (isAwardedJob(leadItem)) {
			flashOk("This estimate is already a job.");
			return;
		}
		if (!window.confirm("Award this estimate and create an active job?")) {
			return;
		}
		var awardBtns = document.querySelectorAll(".usis-estd-award-job");
		awardBtns.forEach(function (btn) {
			btn.disabled = true;
		});
		var body = {};
		if (isEstimateRecord(leadItem)) body.estimate_id = leadItem.id;
		var req = Api
			? Api.awardLead(leadId, body)
			: fetch(apiBaseTrimmed() + "/api/v1/lead-estimates/" + encodeURIComponent(leadId) + "/award", {
					method: "POST",
					credentials: "include",
					headers: { "Content-Type": "application/json", Accept: "application/json" },
					body: JSON.stringify(body),
				}).then(function (r) {
					return r.text().then(function (text) {
						var j = {};
						try {
							j = text ? JSON.parse(text) : {};
						} catch (eAward) {
							j = {};
						}
						if (!r.ok) throw new Error(mapApiError(j, r.status));
						return j;
					});
				});
		req
			.then(function (data) {
				flashOk("Job awarded.");
				var pid = (data && data.project_id) || (data && data.item && data.item.project_id) || null;
				if (data && data.item) leadItem = Object.assign(leadItem || {}, data.item);
				syncConvertJobButtons(leadItem);
				return loadDetail().then(function () {
					if (!pid) return;
					document.querySelectorAll(".usis-estd-open-job").forEach(function (openBtn) {
						openBtn.classList.remove("d-none");
						openBtn.setAttribute("href", "construction/project-detail.html?id=" + encodeURIComponent(pid));
					});
				});
			})
			.catch(function (e) {
				flashErr(e.message || String(e));
			})
			.finally(function () {
				awardBtns.forEach(function (btn) {
					btn.disabled = false;
				});
			});
	}

	function rowStatusEl(tr) {
		return tr ? tr.querySelector(".usis-est-row-status") : null;
	}

	function setRowStatus(tr, text) {
		var el = rowStatusEl(tr);
		if (el) el.textContent = text || "";
	}

	function setLineDirty(id, dirty) {
		if (!id) return;
		if (dirty) dirtyByLine[id] = true;
		else delete dirtyByLine[id];
	}

	function hasAnyDirty() {
		for (var k in dirtyByLine) {
			if (dirtyByLine[k]) return true;
		}
		return false;
	}

	function mapApiError(j, status) {
		var code = j && j.error_code;
		var msg = (j && j.error) || "Request failed (HTTP " + status + ").";
		if (code === "ESTIMATE_LOCKED") {
			return "This estimate is locked. Ask an admin to unlock the takeoff, or keep viewing. Original: " + msg;
		}
		if (code === "TAKEOFF_WRITES_DISABLED") {
			return "Saving is disabled on the server (TAKEOFF_API_WRITES_ENABLED). Ask an admin to enable it. Original: " + msg;
		}
		if (code === "UNLOCK_FORBIDDEN") {
			return "Your account cannot unlock estimates; ask an admin or superuser. Original: " + msg;
		}
		return msg;
	}

	function flashErr(msg) {
		showErr(msg);
		if (window.USISNotify && msg) window.USISNotify.error(msg);
	}

	function flashOk(msg) {
		showErr("");
		if (window.USISNotify && msg) window.USISNotify.success(msg);
	}

	function esc(s) {
		return String(s == null ? "" : s)
			.replace(/&/g, "&amp;")
			.replace(/</g, "&lt;")
			.replace(/>/g, "&gt;")
			.replace(/"/g, "&quot;");
	}

	function escAttr(s) {
		return String(s == null ? "" : s)
			.replace(/&/g, "&amp;")
			.replace(/"/g, "&quot;")
			.replace(/</g, "&lt;");
	}

	function showErr(msg) {
		var el = document.getElementById("usis-est-detail-err");
		if (!el) return;
		if (msg) {
			el.textContent = msg;
			el.classList.remove("d-none");
		} else {
			el.textContent = "";
			el.classList.add("d-none");
		}
	}

	function money(n) {
		if (n == null || n === "" || isNaN(Number(n))) return "—";
		var x = Number(n);
		return x.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
	}

	function pct(n) {
		if (n == null || n === "" || isNaN(Number(n))) return "—";
		return (Number(n) * 100).toFixed(2) + "%";
	}

	function rollupByType(lines) {
		var r = { L: 0, M: 0, E: 0, S: 0, O: 0 };
		for (var i = 0; i < lines.length; i++) {
			var ln = lines[i];
			var t = (ln.cost_type || "M").charAt(0).toUpperCase();
			if (!r.hasOwnProperty(t)) t = "O";
			r[t] += Number(ln.extended_total) || 0;
		}
		return r;
	}

	function renderRollup(lines, feePct) {
		var sub = 0;
		for (var i = 0; i < lines.length; i++) sub += Number(lines[i].extended_total) || 0;
		var by = rollupByType(lines);
		var feeAmt = feePct != null && !isNaN(Number(feePct)) ? sub * Number(feePct) : 0;
		var total = sub + feeAmt;

		function set(id, val) {
			var n = document.getElementById(id);
			if (n) n.textContent = val;
		}
		set("usis-est-roll-l", "$" + money(by.L));
		set("usis-est-roll-m", "$" + money(by.M));
		set("usis-est-roll-e", "$" + money(by.E));
		set("usis-est-roll-s", "$" + money(by.S));
		set("usis-est-roll-o", "$" + money(by.O));
		set("usis-est-roll-sub", "$" + money(sub));
		set("usis-est-roll-fee", "$" + money(feeAmt));
		set("usis-est-roll-total", "$" + money(total));
	}

	function statusBadgeHtml(status) {
		var s = String(status || "draft").toLowerCase();
		var cls = "bg-light text-dark border";
		if (s === "submitted") cls = "bg-primary";
		else if (s === "awarded") cls = "bg-success";
		else if (s === "superseded") cls = "bg-warning text-dark";
		else if (s === "archived") cls = "bg-dark";
		else if (s === "draft") cls = "bg-secondary";
		return '<span class="badge ' + cls + ' text-capitalize">' + esc(s) + "</span>";
	}

	function drawingSetLabel(item) {
		if (item.drawing_set && item.drawing_set.name) return item.drawing_set.name;
		return "";
	}

	function renderHeader(item) {
		var h = document.getElementById("usis-est-header");
		if (!h || !item) return;
		var lead = item.lead || {};
		var leadName = lead.name || item.lead_name || item.company_name || "";
		var version = item.version_label || item.version || "";
		var gc = item.gc_name || item.company_name || "—";
		h.innerHTML =
			'<div class="col-md-7">' +
			'<h5 class="mb-1">' +
			esc(item.name || item.title || "—") +
			(version ? ' <span class="text-muted fw-normal small">v' + esc(String(version)) + "</span>" : "") +
			" " +
			statusBadgeHtml(item.status) +
			"</h5>" +
			'<p class="text-muted small mb-0">' +
			'<span class="me-2">GC: <strong>' +
			esc(gc) +
			"</strong></span>" +
			'<span class="me-2">Drawing set: <strong>' +
			esc(drawingSetLabel(item) || "—") +
			"</strong></span><br>" +
			'<span class="me-2">Project # <strong>' +
			esc(item.number || lead.number || "—") +
			"</strong></span>" +
			'<span class="me-2">Trade: ' +
			esc(item.trade_name || lead.trade_name || "—") +
			"</span><br>" +
			"Due: " +
			esc(item.due_at || lead.due_at || "—") +
			(leadName ? " · Lead: " + esc(leadName) : "") +
			"</p></div>" +
			'<div class="col-md-5 text-md-end small">' +
			"<div>ROM: <strong>$" +
			money(item.rom) +
			"</strong></div>" +
			"<div>Fee %: <strong>" +
			pct(item.fee_percentage) +
			"</strong></div>" +
			"<div>Profit margin: <strong>" +
			pct(item.profit_margin) +
			"</strong></div>" +
			"</div>";
	}

	var quoteColumnCatalog = null;

	function apiBaseTrimmed() {
		return String(API || "").replace(/\/$/, "");
	}

	function canUnlockEstimate(me) {
		if (!me) return false;
		if (me.is_superuser) return true;
		var roles = me.roles || [];
		for (var i = 0; i < roles.length; i++) {
			var c = String(roles[i].code || "").toLowerCase();
			if (c === "admin" || c === "superuser") return true;
		}
		return false;
	}

	function loadSessionMe() {
		return fetch(apiBaseTrimmed() + "/api/v1/me", {
			credentials: "include",
			headers: { Accept: "application/json" },
		})
			.then(function (r) {
				if (!r.ok) {
					sessionMe = null;
					return null;
				}
				return r.json();
			})
			.then(function (data) {
				sessionMe = data && data.item ? data.item : null;
				return sessionMe;
			})
			.catch(function () {
				sessionMe = null;
				return null;
			});
	}

	function applyTakeoffLockUI() {
		var banner = document.getElementById("usis-est-lock-banner");
		if (!leadItem) return;
		var locked = !!leadItem.estimate_locked_at;
		var approved = !!leadItem.estimate_approved_at || !!leadItem.approved_at;
		if (banner) {
			if (!locked) {
				banner.classList.add("d-none");
				banner.textContent = "";
			} else {
				var parts = [];
				if (approved) {
					parts.push("This estimate is approved and locked for editing.");
					if (leadItem.estimate_approved_at) parts.push("Approved at " + leadItem.estimate_approved_at + ".");
					if (leadItem.estimate_approved_by_email) parts.push("Approver: " + leadItem.estimate_approved_by_email + ".");
				} else {
					parts.push("This estimate is locked for editing (draft lock).");
				}
				parts.push("Takeoff and door schedule edits are blocked until an admin unlocks.");
				if (!canUnlockEstimate(sessionMe)) {
					parts.push("If you need changes, contact an admin — they can unlock the takeoff.");
				}
				banner.textContent = parts.join(" ");
				banner.classList.remove("d-none");
			}
		}
		var addBtn = document.getElementById("usis-est-add-line");
		var apprBtn = document.getElementById("usis-est-approve-lock");
		var lockBtn = document.getElementById("usis-est-lock-draft");
		var matBtn = document.getElementById("usis-est-mat-search");
		var unlBtn = document.getElementById("usis-est-unlock");
		if (addBtn) addBtn.disabled = locked;
		if (apprBtn) {
			apprBtn.classList.toggle("d-none", locked);
			apprBtn.disabled = locked;
		}
		if (lockBtn) {
			lockBtn.classList.toggle("d-none", locked);
			lockBtn.disabled = locked;
		}
		if (matBtn) matBtn.disabled = locked;
		if (unlBtn) {
			var showUnl = locked && canUnlockEstimate(sessionMe);
			unlBtn.classList.toggle("d-none", !showUnl);
		}
		var tb = document.getElementById("usis-est-lines-tbody");
		if (tb) {
			tb.querySelectorAll(".usis-est-inp").forEach(function (el) {
				if (el.tagName === "SELECT") el.disabled = locked;
				else el.readOnly = locked;
			});
			tb.querySelectorAll(".usis-est-del").forEach(function (b) {
				b.disabled = locked;
				b.classList.toggle("d-none", locked);
			});
		}
	}

	function postEstimateAction(action) {
		if (!leadKey) return Promise.resolve();
		if (Api) {
			return Api.postEstimateAction(leadKey, action).catch(function (err) {
				var mapped = mapApiError(err.body || {}, err.status);
				throw new Error(mapped);
			});
		}
		return fetch(apiBaseTrimmed() + "/api/v1/estimates/" + encodeURIComponent(leadKey) + "/" + action, {
			method: "POST",
			credentials: "include",
			headers: { Accept: "application/json" },
		}).then(function (r) {
			return r.text().then(function (text) {
				var j = {};
				try {
					j = text ? JSON.parse(text) : {};
				} catch (e) {
					j = {};
				}
				if (!r.ok) {
					throw new Error(mapApiError(j, r.status));
				}
				return j;
			});
		});
	}

	function ensureQuoteColumns() {
		if (quoteColumnCatalog) return Promise.resolve(quoteColumnCatalog);
		var url = apiBaseTrimmed() + "/api/v1/reports/catalog";
		return fetch(url, { credentials: "include", headers: { Accept: "application/json" } })
			.then(function (r) {
				return r.text().then(function (text) {
					var j = {};
					try {
						j = text ? JSON.parse(text) : {};
					} catch (e) {
						throw new Error("catalog not JSON");
					}
					if (!r.ok) throw new Error((j && j.error) || "HTTP " + r.status);
					return j;
				});
			})
			.then(function (data) {
				var items = data.items || [];
				var rep = null;
				for (var i = 0; i < items.length; i++) {
					if (items[i].id === "quote_report") {
						rep = items[i];
						break;
					}
				}
				quoteColumnCatalog = (rep && rep.column_options) || [];
				return quoteColumnCatalog;
			});
	}

	function renderQuoteColCheckboxes(opts) {
		var root = document.getElementById("usis-est-quote-report-cols");
		if (!root) return;
		if (!opts.length) {
			root.textContent = "Quote column options unavailable.";
			return;
		}
		var saved = null;
		if (window.localStorage) {
			try {
				var raw = localStorage.getItem("usis_quote_columns_v1");
				if (raw) saved = JSON.parse(raw);
			} catch (e1) {
				saved = null;
			}
		}
		var html = '<div class="row row-cols-1 g-1">';
		for (var i = 0; i < opts.length; i++) {
			var c = opts[i];
			var cid = String(c.id || "");
			var fid = "usis-est-qcol-" + cid.replace(/[^a-zA-Z0-9_-]/g, "_");
			var chk = "";
			if (Array.isArray(saved)) {
				chk = saved.indexOf(cid) >= 0 ? " checked" : "";
			} else if (c.default) {
				chk = " checked";
			}
			html +=
				'<div class="col"><div class="form-check">' +
				'<input type="checkbox" class="form-check-input usis-est-quote-col" id="' +
				escAttr(fid) +
				'" data-col-id="' +
				escAttr(cid) +
				'"' +
				chk +
				">" +
				'<label class="form-check-label" for="' +
				escAttr(fid) +
				'">' +
				esc(c.label || cid) +
				"</label></div></div>";
		}
		html += "</div>";
		root.innerHTML = html;
	}

	function openQuoteReportModal() {
		if (!leadKey) return;
		var root = document.getElementById("usis-est-quote-report-cols");
		if (root) root.textContent = "Loading…";
		var modalEl = document.getElementById("usis-est-quote-report-modal");
		if (modalEl && window.bootstrap) window.bootstrap.Modal.getOrCreateInstance(modalEl).show();
		ensureQuoteColumns()
			.then(function (opts) {
				renderQuoteColCheckboxes(opts);
			})
			.catch(function () {
				if (root) root.textContent = "Could not load column options.";
			});
	}

	function submitQuoteReport() {
		if (!leadKey) return;
		var modalEl = document.getElementById("usis-est-quote-report-modal");
		var boxes = document.querySelectorAll(".usis-est-quote-col:checked");
		var ids = [];
		for (var i = 0; i < boxes.length; i++) {
			var v = boxes[i].getAttribute("data-col-id");
			if (v) ids.push(v);
		}
		if (window.localStorage) {
			try {
				localStorage.setItem("usis_quote_columns_v1", JSON.stringify(ids));
			} catch (e2) {
				/* ignore */
			}
		}
		var url = Api
			? Api.quoteReportUrl(leadKey, ids)
			: apiBaseTrimmed() +
				"/api/v1/estimates/" +
				encodeURIComponent(leadKey) +
				"/render/quote-report" +
				(ids.length ? "?columns=" + encodeURIComponent(ids.join(",")) : "");
		window.open(url, "_blank", "noopener,noreferrer");
		if (modalEl && window.bootstrap) {
			var inst = bootstrap.Modal.getInstance(modalEl);
			if (inst) inst.hide();
		}
	}

	function rowHtml(ln) {
		var id = ln.id;
		var types = ["L", "M", "E", "S", "O"];
		var opts = types
			.map(function (t) {
				var sel = (ln.cost_type || "M").charAt(0).toUpperCase() === t ? " selected" : "";
				return '<option value="' + t + '"' + sel + ">" + t + "</option>";
			})
			.join("");
		return (
			"<tr data-line-id=\"" +
			escAttr(id) +
			'">' +
			"<td><input type=\"text\" class=\"form-control form-control-sm usis-est-inp\" data-f=\"section\" value=\"" +
			escAttr(ln.section || "") +
			'"></td>' +
			"<td><input type=\"text\" class=\"form-control form-control-sm usis-est-inp\" data-f=\"job_cost_code\" value=\"" +
			escAttr(ln.job_cost_code || "") +
			'"></td>' +
			"<td><input type=\"text\" class=\"form-control form-control-sm usis-est-inp\" data-f=\"description\" value=\"" +
			escAttr(ln.description || "") +
			'"></td>' +
			"<td><select class=\"form-select form-select-sm usis-est-inp\" data-f=\"cost_type\">" +
			opts +
			"</select></td>" +
			"<td class=\"text-end\"><input type=\"number\" step=\"any\" class=\"form-control form-control-sm text-end usis-est-inp\" data-f=\"quantity\" value=\"" +
			escAttr(ln.quantity) +
			'"></td>' +
			"<td><input type=\"text\" class=\"form-control form-control-sm usis-est-inp\" data-f=\"unit\" value=\"" +
			escAttr(ln.unit || "") +
			'"></td>' +
			"<td class=\"text-end\"><input type=\"number\" step=\"any\" class=\"form-control form-control-sm text-end usis-est-inp\" data-f=\"unit_cost\" value=\"" +
			escAttr(ln.unit_cost) +
			'"></td>' +
			"<td class=\"text-end fw-semibold usis-est-ext\">" +
			esc(money(ln.extended_total)) +
			"</td>" +
			'<td class="text-center text-muted small usis-est-row-status" style="width:2.75rem"></td>' +
			"<td class=\"text-end\">" +
			'<button type="button" class="btn btn-outline-danger btn-sm py-0 usis-est-del" title="Delete line">×</button>' +
			"</td></tr>"
		);
	}

	function renderTable(lines) {
		var tb = document.getElementById("usis-est-lines-tbody");
		if (!tb) return;
		dirtyByLine = {};
		if (!lines || !lines.length) {
			tb.innerHTML = '<tr><td colspan="10" class="text-muted">No lines yet. Click <strong>Add line</strong>.</td></tr>';
			applyLineAutoFilter();
			return;
		}
		tb.innerHTML = lines.map(rowHtml).join("");
		applyLineAutoFilter();
	}

	function ensureLineAutoFilter() {
		if (lineAutoFilter || !window.USIS_TABLE_AUTOFILTER) return lineAutoFilter;
		var id = leadKey || new URLSearchParams(window.location.search).get("id") || "unknown";
		lineAutoFilter = window.USIS_TABLE_AUTOFILTER.bind({
			table: "#usis-est-lines-table",
			tableId: "estimating.takeoff:" + id,
			getRows: function () {
				return (leadItem && leadItem.takeoff_lines) || [];
			},
			resetButton: "#usis-est-reset-view",
			mobileButton: "#usis-est-sort-filter",
			columns: [
				{ key: "section", label: "Section", type: "text", sortable: true, filterable: true },
				{ key: "job_cost_code", label: "Cost code", type: "text", sortable: true, filterable: true },
				{ key: "description", label: "Description", type: "text", sortable: true, filterable: true },
				{
					key: "cost_type",
					label: "Type",
					type: "singleSelect",
					sortable: true,
					filterable: true,
					valueOptions: ["L", "M", "E", "S", "O"],
				},
				{ key: "quantity", label: "Qty", type: "number", sortable: true, filterable: true },
				{
					key: "unit",
					label: "UOM",
					type: "singleSelect",
					sortable: true,
					filterable: true,
					valueOptions: ["SF", "LF", "EA", "SQ", "GAL"],
				},
				{ key: "unit_cost", label: "Unit cost", type: "number", sortable: true, filterable: true },
				{ key: "extended_total", label: "Extended", type: "number", sortable: true, filterable: true },
			],
			onChange: function () {
				applyLineAutoFilter();
			},
		});
		var status = document.getElementById("usis-est-lines-af-status");
		if (status && !status.getAttribute("data-af-wired")) {
			status.setAttribute("data-af-wired", "1");
			status.addEventListener("click", function (e) {
				if (e.target && e.target.id === "usis-est-af-clear" && lineAutoFilter) {
					lineAutoFilter.reset();
				}
			});
		}
		return lineAutoFilter;
	}

	function applyLineAutoFilter() {
		var af = ensureLineAutoFilter();
		var tb = document.getElementById("usis-est-lines-tbody");
		var status = document.getElementById("usis-est-lines-af-status");
		if (!tb) return;
		if (!af) {
			if (status) {
				status.textContent = "";
				status.classList.add("d-none");
			}
			return;
		}
		var dataRows = tb.querySelectorAll("tr[data-line-id]");
		if (!dataRows.length) {
			if (status) {
				status.textContent = "";
				status.classList.add("d-none");
			}
			af.paint();
			return;
		}
		var result = af.applyDomRows(tb, function (tr) {
			var id = tr.getAttribute("data-line-id");
			if (!id) return null;
			var live = gatherRowPayload(tr);
			var stored = {};
			if (leadItem && leadItem.takeoff_lines) {
				for (var i = 0; i < leadItem.takeoff_lines.length; i++) {
					if (String(leadItem.takeoff_lines[i].id) === String(id)) {
						stored = leadItem.takeoff_lines[i];
						break;
					}
				}
			}
			return Object.assign({ id: id }, stored, live);
		});
		var labels = af.getActiveLabels();
		if (status) {
			if (!labels.length && result.shown === result.total) {
				status.textContent = "";
				status.classList.add("d-none");
			} else {
				status.classList.remove("d-none");
				status.innerHTML =
					"Showing " +
					result.shown +
					" of " +
					result.total +
					" lines" +
					(labels.length ? " · Filters on: " + labels.join(", ") : "") +
					' <button type="button" class="btn btn-link btn-sm py-0 align-baseline" id="usis-est-af-clear">Clear</button>';
			}
		}
	}

	function gatherRowPayload(tr) {
		var o = {};
		tr.querySelectorAll(".usis-est-inp").forEach(function (inp) {
			var f = inp.getAttribute("data-f");
			if (!f) return;
			if (inp.tagName === "SELECT") o[f] = inp.value;
			else if (f === "quantity" || f === "unit_cost") o[f] = inp.value === "" ? 0 : Number(inp.value);
			else o[f] = inp.value;
		});
		return o;
	}

	function updateRowExtended(tr, ext) {
		var td = tr.querySelector(".usis-est-ext");
		if (td) td.textContent = money(ext);
	}

	function saveRow(tr) {
		if (leadItem && leadItem.estimate_locked_at) return;
		var id = tr.getAttribute("data-line-id");
		if (!id) return;
		setRowStatus(tr, "…");
		var body = gatherRowPayload(tr);
		fetch(API + "/api/v1/takeoff-lines/" + encodeURIComponent(id), {
			method: "PATCH",
			headers: { "Content-Type": "application/json", Accept: "application/json" },
			credentials: "include",
			body: JSON.stringify(body),
		})
			.then(function (r) {
				return r.text().then(function (text) {
					var j = {};
					try {
						j = text ? JSON.parse(text) : {};
					} catch (e0) {
						j = {};
					}
					if (!r.ok) {
						throw new Error(mapApiError(j, r.status));
					}
					return j;
				});
			})
			.then(function (data) {
				var it = data.item;
				if (it) updateRowExtended(tr, it.extended_total);
				if (leadItem && leadItem.takeoff_lines) {
					var ix = leadItem.takeoff_lines.findIndex(function (x) { return x.id === id; });
					if (ix >= 0) {
						Object.assign(leadItem.takeoff_lines[ix], it);
						renderRollup(leadItem.takeoff_lines, leadItem.fee_percentage);
					}
				}
				setLineDirty(id, false);
				setRowStatus(tr, "");
				showErr("");
			})
			.catch(function (e) {
				setRowStatus(tr, "!");
				flashErr(e.message || String(e));
			});
	}

	function wireTable() {
		var tb = document.getElementById("usis-est-lines-tbody");
		if (!tb) return;
		tb.addEventListener("input", function (e) {
			var t = e.target;
			if (!t.classList || !t.classList.contains("usis-est-inp")) return;
			var tr = t.closest("tr");
			var lid = tr && tr.getAttribute("data-line-id");
			if (lid) setLineDirty(lid, true);
		});
		tb.addEventListener("focusin", function (e) {
			var tr = e.target.closest("tr");
			if (tr && tr.getAttribute("data-line-id")) activeLineId = tr.getAttribute("data-line-id");
		});
		tb.addEventListener("focusout", function (e) {
			var tr = e.target.closest("tr");
			if (!tr || !tb.contains(tr)) return;
			var rel = e.relatedTarget;
			if (rel && tr.contains(rel)) return;
			if (e.target.classList.contains("usis-est-inp")) saveRow(tr);
		});
		tb.addEventListener("change", function (e) {
			var t = e.target;
			if (t.classList.contains("usis-est-inp") && t.tagName === "SELECT") {
				var tr = t.closest("tr");
				if (tr) saveRow(tr);
			}
		});
		tb.addEventListener("click", function (e) {
			var btn = e.target.closest(".usis-est-del");
			if (!btn) return;
			var tr = btn.closest("tr");
			var id = tr && tr.getAttribute("data-line-id");
			if (!id) return;
			if (!window.confirm("Delete this line?")) return;
			fetch(API + "/api/v1/takeoff-lines/" + encodeURIComponent(id), {
				method: "DELETE",
				credentials: "include",
			})
				.then(function (r) {
					if (!r.ok) {
						return r.text().then(function (text) {
							var j = {};
							try {
								j = text ? JSON.parse(text) : {};
							} catch (eDel) {
								j = {};
							}
							throw new Error(mapApiError(j, r.status));
						});
					}
					return loadDetail();
				})
				.catch(function (err) {
					flashErr(err.message || String(err));
				});
		});
	}

	function fireEstimateLoaded(item, error, extra) {
		var detail = Object.assign({ item: item || null, error: error || null }, extra || {});
		document.dispatchEvent(new CustomEvent("usis-lead-estimate-loaded", { detail: detail }));
		document.dispatchEvent(new CustomEvent("usis-estimate-loaded", { detail: detail }));
	}

	function currentLeadId() {
		return parentLeadId(leadItem) || (leadItem && (leadItem.id || leadItem.external_id)) || leadKey;
	}

	function openCreateEstimate(opts) {
		var id = currentLeadId();
		if (!window.USISEstimateCreate) {
			flashErr("Create estimate is not available on this page.");
			return;
		}
		if (!id) {
			flashErr("Open this page from a lead, then create an estimate.");
			return;
		}
		window.USISEstimateCreate.open(id, opts || {});
	}

	function applyLeadOnly(lead) {
		leadItem = lead;
		var idline = document.getElementById("usis-est-detail-idline");
		if (idline) {
			idline.textContent =
				((lead && (lead.name || lead.title)) || "Lead") +
				" · " +
				((lead && lead.number) || "—");
		}
		var noId = document.getElementById("usis-est-detail-no-id");
		if (noId) noId.classList.add("d-none");
		var cta = document.getElementById("usis-est-create-cta");
		if (cta) cta.classList.remove("d-none");
		var wrap = document.getElementById("usis-est-detail-root");
		if (wrap) wrap.classList.add("d-none");
		var rev = document.getElementById("usis-estd-revision");
		if (rev) rev.classList.add("d-none");
		syncConvertJobButtons(lead);
		showErr("");
		fireEstimateLoaded(lead, null, { missingEstimate: true });
	}

	function applyEstimateItem(item) {
		leadItem = item;
		if (item && item.id) leadKey = item.id;
		var lines = (item && item.takeoff_lines) || [];
		renderHeader(item);
		renderTable(lines);
		renderRollup(lines, item.fee_percentage);
		applyTakeoffLockUI();
		var idline = document.getElementById("usis-est-detail-idline");
		if (idline) {
			idline.textContent =
				(item.name || item.title || "—") +
				" · " +
				(item.number || (item.lead && item.lead.number) || "—") +
				" · estimate " +
				item.id;
		}
		var noId = document.getElementById("usis-est-detail-no-id");
		if (noId) noId.classList.add("d-none");
		var cta = document.getElementById("usis-est-create-cta");
		if (cta) cta.classList.add("d-none");
		var wrap = document.getElementById("usis-est-detail-root");
		if (wrap) wrap.classList.remove("d-none");
		var rev = document.getElementById("usis-estd-revision");
		if (rev) rev.classList.remove("d-none");
		syncConvertJobButtons(item);
		fireEstimateLoaded(item, null);
	}

	function loadDetail() {
		if (!leadKey) return Promise.resolve();
		showErr("");
		var loadPromise = Api
			? Api.resolveEstimateId(leadKey).then(function (resolved) {
					if (resolved.missingEstimate) {
						return { __leadOnly: true, item: resolved.item || resolved.lead || null };
					}
					if (resolved.item && resolved.item.id) leadKey = resolved.item.id;
					return resolved.item;
				})
			: fetch(API + "/api/v1/estimates/" + encodeURIComponent(leadKey), {
					credentials: "include",
					headers: { Accept: "application/json" },
				}).then(function (r) {
					return r.text().then(function (text) {
						var j = {};
						try {
							j = text ? JSON.parse(text) : {};
						} catch (eLd) {
							j = {};
						}
						if (r.status === 404) throw new Error("Estimate not found for this id.");
						if (!r.ok) throw new Error(mapApiError(j, r.status));
						return j.item;
					});
				});
		return loadPromise
			.then(function (item) {
				if (item && item.__leadOnly) {
					if (!item.item) throw new Error("Lead not found for this id.");
					applyLeadOnly(item.item);
					return;
				}
				if (!item) throw new Error("Estimate not found for this id.");
				applyEstimateItem(item);
			})
			.catch(function (e) {
				var lead = e.lead || null;
				if (lead) {
					applyLeadOnly(lead);
					return;
				}
				var msg = e.message || String(e);
				if (e.status === 403) msg = mapApiError(e.body || {}, e.status);
				showErr(msg);
				var wrap = document.getElementById("usis-est-detail-root");
				if (wrap) wrap.classList.remove("d-none");
				var noId = document.getElementById("usis-est-detail-no-id");
				if (noId) {
					noId.innerHTML =
						'This estimate could not be opened. <a href="construction/estimate.html">Back to Estimates</a> or <a href="construction/leads.html">Leads</a>.';
					noId.classList.remove("d-none");
				}
				syncConvertJobButtons(leadItem || { id: leadKey });
				fireEstimateLoaded(null, msg);
			});
	}

	function addLine() {
		if (!leadKey) return;
		if (leadItem && leadItem.estimate_locked_at) {
			showErr("This estimate is locked.");
			return;
		}
		fetch(API + "/api/v1/estimates/" + encodeURIComponent(leadKey) + "/takeoff-lines", {
			method: "POST",
			headers: { "Content-Type": "application/json", Accept: "application/json" },
			credentials: "include",
			body: JSON.stringify({
				description: "New line",
				quantity: 1,
				unit: "EA",
				unit_cost: 0,
				cost_type: "M",
			}),
		})
			.then(function (r) {
				if (r.status === 403) throw new Error("Writes disabled (set TAKEOFF_API_WRITES_ENABLED=1)");
				if (!r.ok) return r.json().then(function (j) { throw new Error(j.error || "HTTP " + r.status); });
				return loadDetail();
			})
			.catch(function (e) {
				showErr(e.message || String(e));
			});
	}

	function materialSearch() {
		var q = (document.getElementById("usis-est-mat-q") || {}).value || "";
		q = String(q).trim();
		var ul = document.getElementById("usis-est-mat-results");
		if (!ul) return;
		if (q.length < 2) {
			ul.innerHTML = '<li class="text-muted small">Type at least 2 characters.</li>';
			return;
		}
		fetch(API + "/api/v1/cost-suggestions/material?q=" + encodeURIComponent(q), {
			credentials: "include",
			headers: { Accept: "application/json" },
		})
			.then(function (r) { return r.json(); })
			.then(function (data) {
				var items = data.items || [];
				if (!items.length) {
					ul.innerHTML = '<li class="text-muted small">No matches.</li>';
					return;
				}
				ul.innerHTML = items
					.map(function (m) {
						var cost = m.cost != null ? m.cost : "—";
						var id = "mat-" + String(m.id).replace(/[^a-z0-9-]/gi, "");
						return (
							'<li class="small mb-1 d-flex justify-content-between align-items-start gap-2">' +
							"<span>" +
							esc(m.manufacturer) +
							" · " +
							esc(m.item) +
							'<br><span class="text-muted">$' +
							esc(String(cost)) +
							" / " +
							esc(m.unit_of_measure || "") +
							"</span></span>" +
							'<button type="button" class="btn btn-xs btn-outline-primary btn-sm py-0 usis-mat-apply" data-cost="' +
							escAttr(m.cost != null ? m.cost : "") +
							'">Apply</button>' +
							"</li>"
						);
					})
					.join("");
			});
	}

	function applyMaterialCost(costStr) {
		if (leadItem && leadItem.estimate_locked_at) {
			showErr("This estimate is locked.");
			return;
		}
		if (activeLineId == null || costStr === "" || costStr == null) {
			showErr("Focus a line (click a field), then Apply a material cost.");
			return;
		}
		var c = Number(costStr);
		if (isNaN(c)) return;
		fetch(API + "/api/v1/takeoff-lines/" + encodeURIComponent(activeLineId), {
			method: "PATCH",
			headers: { "Content-Type": "application/json", Accept: "application/json" },
			credentials: "include",
			body: JSON.stringify({ unit_cost: c, cost_type: "M" }),
		})
			.then(function (r) {
				if (!r.ok) {
					return r.text().then(function (text) {
						var j = {};
						try {
							j = text ? JSON.parse(text) : {};
						} catch (eMat) {
							j = {};
						}
						throw new Error(mapApiError(j, r.status));
					});
				}
				return loadDetail();
			})
			.catch(function (e) {
				flashErr(e.message || String(e));
			});
	}

	function wageSearch() {
		var st = (document.getElementById("usis-est-wage-state") || {}).value || "";
		var tr = (document.getElementById("usis-est-wage-trade") || {}).value || "";
		var yr = (document.getElementById("usis-est-wage-year") || {}).value || "";
		var out = document.getElementById("usis-est-wage-out");
		if (!out) return;
		if (!st.trim() || !tr.trim()) {
			out.textContent = "Enter state and trade.";
			return;
		}
		var url =
			API +
			"/api/v1/cost-suggestions/wage?state=" +
			encodeURIComponent(st.trim()) +
			"&trade=" +
			encodeURIComponent(tr.trim()) +
			(yr ? "&year=" + encodeURIComponent(yr.trim()) : "");
		fetch(url, { credentials: "include", headers: { Accept: "application/json" } })
			.then(function (r) { return r.json(); })
			.then(function (data) {
				if (data.item) {
					out.innerHTML =
						"<div>Loaded hourly (reference): <strong>$" +
						esc(String(data.total_loaded_hourly != null ? data.total_loaded_hourly.toFixed(4) : "—")) +
						"</strong></div>" +
						'<pre class="small bg-light p-2 rounded mt-1 mb-0">' +
						esc(JSON.stringify(data.item, null, 2)) +
						"</pre>";
				} else {
					out.innerHTML =
						'<span class="text-muted">No exact match. Near matches: ' +
						(data.near_matches ? data.near_matches.length : 0) +
						"</span>";
				}
			})
			.catch(function () {
				out.textContent = "Request failed.";
			});
	}

	function init() {
		var p = new URLSearchParams(window.location.search);
		leadKey = p.get("id");
		var wrap = document.getElementById("usis-est-detail-root");
		if (!leadKey) {
			if (wrap) wrap.classList.add("d-none");
			return;
		}
		if (wrap) wrap.classList.remove("d-none");
		window.addEventListener("beforeunload", function (e) {
			if (!hasAnyDirty()) return;
			e.preventDefault();
			e.returnValue = "";
		});
		wireTable();
		var compactBtn = document.getElementById("usis-est-compact-toggle");
		var estTbl = document.getElementById("usis-est-lines-table");
		if (compactBtn && estTbl) {
			compactBtn.classList.remove("d-none");
			compactBtn.addEventListener("click", function () {
				var on = estTbl.classList.toggle("usis-est-lines-compact");
				compactBtn.setAttribute("aria-pressed", on ? "true" : "false");
				compactBtn.textContent = on ? "Comfortable density" : "Compact density";
			});
		}
		document.querySelectorAll(".usis-estd-award-job").forEach(function (btn) {
			btn.addEventListener("click", convertEstimateToJob);
		});
		var newEst = document.getElementById("usis-estd-new-estimate");
		if (newEst) newEst.addEventListener("click", function () {
			openCreateEstimate({});
		});
		var revEst = document.getElementById("usis-estd-revision");
		if (revEst) {
			revEst.addEventListener("click", function () {
				openCreateEstimate({ copyFromId: leadItem && leadItem.id ? leadItem.id : "" });
			});
		}
		var ctaBtn = document.getElementById("usis-estd-create-from-cta");
		if (ctaBtn) ctaBtn.addEventListener("click", function () {
			openCreateEstimate({});
		});
		var addBtn = document.getElementById("usis-est-add-line");
		if (addBtn) addBtn.addEventListener("click", addLine);
		var qrBtn = document.getElementById("usis-est-quote-report");
		if (qrBtn) qrBtn.addEventListener("click", openQuoteReportModal);
		var qrSubmit = document.getElementById("usis-est-quote-report-open");
		if (qrSubmit) qrSubmit.addEventListener("click", submitQuoteReport);
		var ms = document.getElementById("usis-est-mat-search");
		if (ms) ms.addEventListener("click", materialSearch);
		var ul = document.getElementById("usis-est-mat-results");
		if (ul) {
			ul.addEventListener("click", function (e) {
				var b = e.target.closest(".usis-mat-apply");
				if (!b) return;
				applyMaterialCost(b.getAttribute("data-cost"));
			});
		}
		var ws = document.getElementById("usis-est-wage-search");
		if (ws) ws.addEventListener("click", wageSearch);
		var appr = document.getElementById("usis-est-approve-lock");
		if (appr) {
			appr.addEventListener("click", function () {
				if (!window.confirm("Approve this estimate and lock takeoff editing?")) return;
				postEstimateAction("approve")
					.then(function () {
						flashOk("Estimate approved and locked.");
						return loadDetail();
					})
					.catch(function (e) {
						flashErr(e.message || String(e));
					});
			});
		}
		var lck = document.getElementById("usis-est-lock-draft");
		if (lck) {
			lck.addEventListener("click", function () {
				if (!window.confirm("Lock this estimate (no formal approval recorded)?")) return;
				postEstimateAction("lock")
					.then(function () {
						flashOk("Estimate locked.");
						return loadDetail();
					})
					.catch(function (e) {
						flashErr(e.message || String(e));
					});
			});
		}
		var unl = document.getElementById("usis-est-unlock");
		if (unl) {
			unl.addEventListener("click", function () {
				if (!window.confirm("Unlock takeoff editing for this estimate?")) return;
				postEstimateAction("unlock")
					.then(function () {
						flashOk("Estimate unlocked.");
						return loadDetail();
					})
					.catch(function (e) {
						flashErr(e.message || String(e));
					});
			});
		}
		loadSessionMe().then(function () {
			loadDetail();
		});
	}

	if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
	else init();
})();
