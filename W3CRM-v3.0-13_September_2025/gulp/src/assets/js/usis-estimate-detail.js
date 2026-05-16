/**
 * Estimate detail: load lead estimate + takeoff lines, edit grid, rollups, cost library hints.
 * Expects URL ?id=<lead external_id or UUID>. Uses window.USIS_API_BASE or http://127.0.0.1:5000
 */
(function () {
	var API =
		typeof window.usisApiBase === "function"
			? window.usisApiBase()
			: typeof window.USIS_API_BASE === "string"
				? window.USIS_API_BASE.trim().replace(/\/$/, "")
				: "http://127.0.0.1:5000";
	var leadKey = null;
	var leadItem = null;
	var sessionMe = null;
	var activeLineId = null;
	var dirtyByLine = {};

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

	function renderHeader(item) {
		var h = document.getElementById("usis-est-header");
		if (!h || !item) return;
		h.innerHTML =
			'<div class="col-md-6">' +
			'<h5 class="mb-1">' +
			esc(item.name || "—") +
			"</h5>" +
			'<p class="text-muted small mb-0">' +
			'<span class="me-2">Project # <strong>' +
			esc(item.number || "—") +
			"</strong></span>" +
			'<span class="me-2">Trade: ' +
			esc(item.trade_name || "—") +
			"</span><br>" +
			"Due: " +
			esc(item.due_at || "—") +
			" · Company: " +
			esc(item.company_name || "—") +
			"</p></div>" +
			'<div class="col-md-6 text-md-end small">' +
			"<div>ROM: <strong>$" +
			money(item.rom) +
			"</strong></div>" +
			"<div>Fee % (from BC): <strong>" +
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
		var approved = !!leadItem.estimate_approved_at;
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

	function postLeadAction(pathSuffix) {
		if (!leadKey) return Promise.resolve();
		return fetch(apiBaseTrimmed() + "/api/v1/lead-estimates/" + encodeURIComponent(leadKey) + pathSuffix, {
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
					var msg = mapApiError(j, r.status);
					throw new Error(msg);
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
		var q = ids.length ? "?columns=" + encodeURIComponent(ids.join(",")) : "";
		var url = apiBaseTrimmed() + "/api/v1/lead-estimates/" + encodeURIComponent(leadKey) + "/render/quote-report" + q;
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
			return;
		}
		tb.innerHTML = lines.map(rowHtml).join("");
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

	function loadDetail() {
		if (!leadKey) return Promise.resolve();
		showErr("");
		return fetch(API + "/api/v1/lead-estimates/" + encodeURIComponent(leadKey), {
			credentials: "include",
			headers: { Accept: "application/json" },
		})
			.then(function (r) {
				if (r.status === 404) throw new Error("Lead estimate not found for this id.");
				if (!r.ok) {
					return r.text().then(function (text) {
						var j = {};
						try {
							j = text ? JSON.parse(text) : {};
						} catch (eLd) {
							j = {};
						}
						throw new Error(mapApiError(j, r.status));
					});
				}
				return r.json();
			})
			.then(function (data) {
				leadItem = data.item;
				var lines = leadItem.takeoff_lines || [];
				renderHeader(leadItem);
				renderTable(lines);
				renderRollup(lines, leadItem.fee_percentage);
				applyTakeoffLockUI();
				var idline = document.getElementById("usis-est-detail-idline");
				if (idline) {
					idline.textContent =
						(leadItem.name || "—") +
						" · " +
						(leadItem.number || "—") +
						" · id " +
						(leadItem.external_id || leadItem.id);
				}
				document.dispatchEvent(
					new CustomEvent("usis-lead-estimate-loaded", { detail: { item: leadItem } })
				);
			})
			.catch(function (e) {
				showErr(e.message || String(e));
				document.dispatchEvent(
					new CustomEvent("usis-lead-estimate-loaded", {
						detail: { item: null, error: e.message || String(e) },
					})
				);
			});
	}

	function addLine() {
		if (!leadKey) return;
		if (leadItem && leadItem.estimate_locked_at) {
			showErr("This estimate is locked.");
			return;
		}
		fetch(API + "/api/v1/lead-estimates/" + encodeURIComponent(leadKey) + "/takeoff-lines", {
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
				postLeadAction("/approve-estimate")
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
				postLeadAction("/lock-estimate")
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
				postLeadAction("/unlock-estimate")
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
