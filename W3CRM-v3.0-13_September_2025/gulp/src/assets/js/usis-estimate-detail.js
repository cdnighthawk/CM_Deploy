/**
 * Estimate detail: load lead estimate + takeoff lines, edit grid, rollups, cost library hints.
 * Expects URL ?id=<lead external_id or UUID>. Uses window.USIS_API_BASE or http://127.0.0.1:5000
 */
(function () {
	var API = (window.USIS_API_BASE || "http://127.0.0.1:5000").replace(/\/$/, "");
	var leadKey = null;
	var leadItem = null;
	var activeLineId = null;

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
			"<td class=\"text-end\">" +
			'<button type="button" class="btn btn-outline-danger btn-sm py-0 usis-est-del" title="Delete line">×</button>' +
			"</td></tr>"
		);
	}

	function renderTable(lines) {
		var tb = document.getElementById("usis-est-lines-tbody");
		if (!tb) return;
		if (!lines || !lines.length) {
			tb.innerHTML = '<tr><td colspan="9" class="text-muted">No lines yet. Click <strong>Add line</strong>.</td></tr>';
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
		var id = tr.getAttribute("data-line-id");
		if (!id) return;
		var body = gatherRowPayload(tr);
		fetch(API + "/api/v1/takeoff-lines/" + encodeURIComponent(id), {
			method: "PATCH",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify(body),
		})
			.then(function (r) {
				if (r.status === 403) throw new Error("Writes disabled (set TAKEOFF_API_WRITES_ENABLED=1 in .env)");
				if (!r.ok) return r.json().then(function (j) { throw new Error(j.error || "HTTP " + r.status); });
				return r.json();
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
				showErr("");
			})
			.catch(function (e) {
				showErr(e.message || String(e));
			});
	}

	function wireTable() {
		var tb = document.getElementById("usis-est-lines-tbody");
		if (!tb) return;
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
			fetch(API + "/api/v1/takeoff-lines/" + encodeURIComponent(id), { method: "DELETE" })
				.then(function (r) {
					if (r.status === 403) throw new Error("Writes disabled");
					if (!r.ok) return r.json().then(function (j) { throw new Error(j.error || "HTTP " + r.status); });
					return loadDetail();
				})
				.catch(function (err) {
					showErr(err.message || String(err));
				});
		});
	}

	function loadDetail() {
		if (!leadKey) return Promise.resolve();
		showErr("");
		return fetch(API + "/api/v1/lead-estimates/" + encodeURIComponent(leadKey))
			.then(function (r) {
				if (r.status === 404) throw new Error("Lead estimate not found for this id.");
				if (!r.ok) throw new Error("HTTP " + r.status);
				return r.json();
			})
			.then(function (data) {
				leadItem = data.item;
				var lines = leadItem.takeoff_lines || [];
				renderHeader(leadItem);
				renderTable(lines);
				renderRollup(lines, leadItem.fee_percentage);
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
		fetch(API + "/api/v1/lead-estimates/" + encodeURIComponent(leadKey) + "/takeoff-lines", {
			method: "POST",
			headers: { "Content-Type": "application/json" },
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
		fetch(API + "/api/v1/cost-suggestions/material?q=" + encodeURIComponent(q))
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
		if (activeLineId == null || costStr === "" || costStr == null) {
			showErr("Focus a line (click a field), then Apply a material cost.");
			return;
		}
		var c = Number(costStr);
		if (isNaN(c)) return;
		fetch(API + "/api/v1/takeoff-lines/" + encodeURIComponent(activeLineId), {
			method: "PATCH",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify({ unit_cost: c, cost_type: "M" }),
		})
			.then(function (r) {
				if (r.status === 403) throw new Error("Writes disabled");
				if (!r.ok) return r.json().then(function (j) { throw new Error(j.error || "HTTP " + r.status); });
				return loadDetail();
			})
			.catch(function (e) {
				showErr(e.message || String(e));
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
		fetch(url)
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
		wireTable();
		var addBtn = document.getElementById("usis-est-add-line");
		if (addBtn) addBtn.addEventListener("click", addLine);
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
		loadDetail();
	}

	if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
	else init();
})();
