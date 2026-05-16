/**
 * Shared L/M/E/S/O takeoff line grid — project-scoped pricing & estimate detail.
 * Exposes window.USISPricingLines for page drivers.
 */
(function (global) {
	"use strict";

	var COST_TYPES = [
		{ code: "L", label: "Labor" },
		{ code: "M", label: "Material" },
		{ code: "E", label: "Equipment" },
		{ code: "S", label: "Subcontract" },
		{ code: "O", label: "Other" },
	];

	function apiBase() {
		if (typeof global.USIS_API_BASE === "string" && global.USIS_API_BASE.trim()) {
			return global.USIS_API_BASE.trim().replace(/\/$/, "");
		}
		var loc = global.location;
		if (loc.protocol === "file:") return "http://127.0.0.1:5000";
		var host = loc.hostname || "";
		var proto = loc.protocol || "http:";
		var port = String(loc.port || "");
		var devPorts = {
			3000: 1,
			3001: 1,
			3002: 1,
			3003: 1,
			4173: 1,
			5173: 1,
			5174: 1,
			5500: 1,
			8080: 1,
		};
		if (devPorts[port]) return proto + "//" + host + ":5000";
		var loopback = host === "localhost" || host === "127.0.0.1" || host === "::1";
		if (loopback) {
			if (port === "5000") return "";
			return proto + "//" + host + ":5000";
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

	function escAttr(s) {
		return String(s == null ? "" : s)
			.replace(/&/g, "&amp;")
			.replace(/"/g, "&quot;")
			.replace(/</g, "&lt;");
	}

	function money(n) {
		if (n == null || n === "" || isNaN(Number(n))) return "—";
		return Number(n).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
	}

	function sellAmount(extended, markupPct) {
		var ext = Number(extended) || 0;
		var m = Number(markupPct);
		if (isNaN(m) || m <= 0) return ext;
		return ext * (1 + m / 100);
	}

	function rollupByType(lines) {
		var r = { L: 0, M: 0, E: 0, S: 0, O: 0 };
		for (var i = 0; i < lines.length; i++) {
			var ln = lines[i];
			var t = (ln.cost_type || "M").charAt(0).toUpperCase();
			if (!Object.prototype.hasOwnProperty.call(r, t)) t = "O";
			r[t] += Number(ln.extended_total) || 0;
		}
		return r;
	}

	function renderRollup(lines, opts) {
		opts = opts || {};
		var prefix = opts.idPrefix || "usis-cp-roll";
		var feePct = opts.feePct;
		var markupPct = opts.markupPct;
		var sub = 0;
		for (var i = 0; i < lines.length; i++) sub += Number(lines[i].extended_total) || 0;
		var by = rollupByType(lines);
		var feeAmt = feePct != null && !isNaN(Number(feePct)) ? sub * Number(feePct) : 0;
		var sellSub = sellAmount(sub, markupPct);
		var total = sub + feeAmt;

		function set(id, val) {
			var n = document.getElementById(id);
			if (n) n.textContent = val;
		}
		set(prefix + "-l", "$" + money(by.L));
		set(prefix + "-m", "$" + money(by.M));
		set(prefix + "-e", "$" + money(by.E));
		set(prefix + "-s", "$" + money(by.S));
		set(prefix + "-o", "$" + money(by.O));
		set(prefix + "-sub", "$" + money(sub));
		set(prefix + "-sell", "$" + money(sellSub));
		set(prefix + "-fee", "$" + money(feeAmt));
		set(prefix + "-total", "$" + money(total));
		set(prefix + "-grand", "$" + money(total));
	}

	function costTypeOptions(selected) {
		var sel = (selected || "M").charAt(0).toUpperCase();
		return COST_TYPES.map(function (ct) {
			var on = ct.code === sel ? " selected" : "";
			return (
				'<option value="' +
				ct.code +
				'"' +
				on +
				">" +
				ct.code +
				" — " +
				esc(ct.label) +
				"</option>"
			);
		}).join("");
	}

	function rowHtml(ln, opts) {
		opts = opts || {};
		var inpClass = opts.inputClass || "usis-cp-inp";
		var markupPct = opts.markupPct;
		var ext = Number(ln.extended_total) || 0;
		var sell = sellAmount(ext, markupPct);
		return (
			'<tr data-line-id="' +
			escAttr(ln.id) +
			'">' +
			'<td><input type="text" class="form-control form-control-sm ' +
			inpClass +
			'" data-f="section" value="' +
			escAttr(ln.section || "") +
			'"></td>' +
			'<td><input type="text" class="form-control form-control-sm ' +
			inpClass +
			'" data-f="job_cost_code" value="' +
			escAttr(ln.job_cost_code || "") +
			'"></td>' +
			'<td><input type="text" class="form-control form-control-sm ' +
			inpClass +
			'" data-f="description" value="' +
			escAttr(ln.description || "") +
			'"></td>' +
			'<td><select class="form-select form-select-sm ' +
			inpClass +
			'" data-f="cost_type">' +
			costTypeOptions(ln.cost_type) +
			"</select></td>" +
			'<td class="text-end"><input type="number" step="any" class="form-control form-control-sm text-end ' +
			inpClass +
			'" data-f="quantity" value="' +
			escAttr(ln.quantity) +
			'"></td>' +
			'<td><input type="text" class="form-control form-control-sm ' +
			inpClass +
			'" data-f="unit" value="' +
			escAttr(ln.unit || "") +
			'"></td>' +
			'<td class="text-end"><input type="number" step="any" class="form-control form-control-sm text-end ' +
			inpClass +
			'" data-f="unit_cost" value="' +
			escAttr(ln.unit_cost) +
			'"></td>' +
			'<td class="text-end fw-semibold usis-cp-ext">' +
			esc(money(ext)) +
			"</td>" +
			'<td class="text-end text-muted usis-cp-sell">' +
			esc(money(sell)) +
			"</td>" +
			'<td class="text-end">' +
			'<button type="button" class="btn btn-outline-danger btn-sm py-0 usis-cp-del" title="Delete line">×</button>' +
			"</td></tr>"
		);
	}

	function sectionHeaderRow(sectionName, colSpan) {
		return (
			'<tr class="table-light usis-cp-section-row"><td colspan="' +
			colSpan +
			'" class="fw-semibold small text-uppercase text-muted py-2">' +
			esc(sectionName || "(No section)") +
			"</td></tr>"
		);
	}

	function renderTableBody(lines, opts) {
		opts = opts || {};
		var tb = document.getElementById(opts.tbodyId || "usis-cp-lines-tbody");
		if (!tb) return;
		var colSpan = opts.colSpan || 10;
		if (!lines || !lines.length) {
			tb.innerHTML =
				'<tr><td colspan="' +
				colSpan +
				'" class="text-muted">No lines yet. Click <strong>Add line</strong>.</td></tr>';
			return;
		}
		var grouped = [];
		var seen = {};
		for (var i = 0; i < lines.length; i++) {
			var sec = (lines[i].section || "").trim() || "(No section)";
			if (!seen[sec]) {
				seen[sec] = true;
				grouped.push(sec);
			}
		}
		var html = [];
		for (var g = 0; g < grouped.length; g++) {
			var name = grouped[g];
			html.push(sectionHeaderRow(name, colSpan));
			for (var j = 0; j < lines.length; j++) {
				var ln = lines[j];
				var lnSec = (ln.section || "").trim() || "(No section)";
				if (lnSec === name) html.push(rowHtml(ln, opts));
			}
		}
		tb.innerHTML = html.join("");
	}

	function gatherRowPayload(tr, inputClass) {
		var cls = inputClass || "usis-cp-inp";
		var o = {};
		tr.querySelectorAll("." + cls).forEach(function (inp) {
			var f = inp.getAttribute("data-f");
			if (!f) return;
			if (inp.tagName === "SELECT") o[f] = inp.value;
			else if (f === "quantity" || f === "unit_cost") o[f] = inp.value === "" ? 0 : Number(inp.value);
			else o[f] = inp.value;
		});
		return o;
	}

	function updateRowTotals(tr, item, markupPct) {
		var extTd = tr.querySelector(".usis-cp-ext");
		var sellTd = tr.querySelector(".usis-cp-sell");
		var ext = item && item.extended_total != null ? item.extended_total : 0;
		if (extTd) extTd.textContent = money(ext);
		if (sellTd) sellTd.textContent = money(sellAmount(ext, markupPct));
	}

	function loadProjectLines(projectId) {
		var base = apiBase();
		return fetch(base + "/api/v1/projects/" + encodeURIComponent(projectId) + "/takeoff-lines", {
			credentials: "include",
			headers: { Accept: "application/json" },
		}).then(function (r) {
			if (!r.ok) return r.json().then(function (j) { throw new Error(j.error || "HTTP " + r.status); });
			return r.json();
		});
	}

	function patchLine(lineId, body) {
		var base = apiBase();
		return fetch(base + "/api/v1/takeoff-lines/" + encodeURIComponent(lineId), {
			method: "PATCH",
			headers: { "Content-Type": "application/json", Accept: "application/json" },
			credentials: "include",
			body: JSON.stringify(body),
		}).then(function (r) {
			if (r.status === 403) throw new Error("Writes disabled (set TAKEOFF_API_WRITES_ENABLED=1 in .env)");
			if (!r.ok) return r.json().then(function (j) { throw new Error(j.error || "HTTP " + r.status); });
			return r.json();
		});
	}

	function createProjectLine(projectId, body) {
		var base = apiBase();
		return fetch(base + "/api/v1/projects/" + encodeURIComponent(projectId) + "/takeoff-lines", {
			method: "POST",
			headers: { "Content-Type": "application/json", Accept: "application/json" },
			credentials: "include",
			body: JSON.stringify(body),
		}).then(function (r) {
			if (r.status === 403) throw new Error("Writes disabled (set TAKEOFF_API_WRITES_ENABLED=1 in .env)");
			if (!r.ok) return r.json().then(function (j) { throw new Error(j.error || "HTTP " + r.status); });
			return r.json();
		});
	}

	function deleteLine(lineId) {
		var base = apiBase();
		return fetch(base + "/api/v1/takeoff-lines/" + encodeURIComponent(lineId), {
			method: "DELETE",
			credentials: "include",
		}).then(function (r) {
			if (r.status === 403) throw new Error("Writes disabled (set TAKEOFF_API_WRITES_ENABLED=1 in .env)");
			if (!r.ok) return r.json().then(function (j) { throw new Error(j.error || "HTTP " + r.status); });
			return r;
		});
	}

	function wireTable(state) {
		var tb = document.getElementById(state.tbodyId || "usis-cp-lines-tbody");
		if (!tb) return;

		tb.addEventListener("focusout", function (e) {
			var tr = e.target.closest("tr[data-line-id]");
			if (!tr || !tb.contains(tr)) return;
			var rel = e.relatedTarget;
			if (rel && tr.contains(rel)) return;
			if (!e.target.classList.contains(state.inputClass || "usis-cp-inp")) return;
			var id = tr.getAttribute("data-line-id");
			var body = gatherRowPayload(tr, state.inputClass);
			patchLine(id, body)
				.then(function (data) {
					var it = data.item;
					if (it) {
						updateRowTotals(tr, it, state.getMarkupPct ? state.getMarkupPct() : 0);
						if (state.onLinePatched) state.onLinePatched(it);
					}
					if (state.onError) state.onError("");
				})
				.catch(function (err) {
					if (state.onError) state.onError(err.message || String(err));
				});
		});

		tb.addEventListener("change", function (e) {
			var t = e.target;
			if (!t.classList.contains(state.inputClass || "usis-cp-inp") || t.tagName !== "SELECT") return;
			var tr = t.closest("tr[data-line-id]");
			if (!tr) return;
			var id = tr.getAttribute("data-line-id");
			patchLine(id, gatherRowPayload(tr, state.inputClass))
				.then(function (data) {
					var it = data.item;
					if (it) {
						updateRowTotals(tr, it, state.getMarkupPct ? state.getMarkupPct() : 0);
						if (state.onLinePatched) state.onLinePatched(it);
					}
					if (state.onError) state.onError("");
				})
				.catch(function (err) {
					if (state.onError) state.onError(err.message || String(err));
				});
		});

		tb.addEventListener("click", function (e) {
			var btn = e.target.closest(".usis-cp-del");
			if (!btn) return;
			var tr = btn.closest("tr[data-line-id]");
			var id = tr && tr.getAttribute("data-line-id");
			if (!id) return;
			if (!global.confirm("Delete this line?")) return;
			deleteLine(id)
				.then(function () {
					if (state.onReload) return state.onReload();
				})
				.catch(function (err) {
					if (state.onError) state.onError(err.message || String(err));
				});
		});
	}

	global.USISPricingLines = {
		COST_TYPES: COST_TYPES,
		apiBase: apiBase,
		esc: esc,
		escAttr: escAttr,
		money: money,
		sellAmount: sellAmount,
		rollupByType: rollupByType,
		renderRollup: renderRollup,
		rowHtml: rowHtml,
		renderTableBody: renderTableBody,
		gatherRowPayload: gatherRowPayload,
		loadProjectLines: loadProjectLines,
		patchLine: patchLine,
		createProjectLine: createProjectLine,
		deleteLine: deleteLine,
		wireTable: wireTable,
	};
})(typeof window !== "undefined" ? window : this);
