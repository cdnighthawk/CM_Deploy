/**
 * Excel-style header AutoFilter (sort + filter nested in the column header).
 * Vanilla companion to the planned useAutoFilterGrid helper — no MUI in this stack.
 *
 * Persistence keys:
 *   grid:{tableId}:sort
 *   grid:{tableId}:filter
 *   grid:{tableId}:cols
 */
(function (global) {
	"use strict";

	var BLANK = "\u0000__USIS_EMPTY__\u0000";
	var STYLE_ID = "usis-table-autofilter-style";
	var DEBOUNCE_MS = 150;
	var POP_ID = "usis-af-pop";

	var CSS =
		"th.usis-af-th{position:relative;white-space:nowrap}" +
		"th.usis-af-th .usis-af-head{display:inline-flex;align-items:center;gap:0.2rem;max-width:100%}" +
		"th.usis-af-th .usis-af-label{cursor:pointer;user-select:none}" +
		"th.usis-af-th .usis-sort-arrow{color:#3b9eff;font-weight:700;font-size:0.85em;min-width:0.65em;line-height:1}" +
		"th.usis-af-th .usis-af-btn{" +
		"border:0;background:transparent;color:#8a94a6;padding:0 0.15rem;line-height:1;border-radius:0.2rem;" +
		"font-size:0.7rem;cursor:pointer;vertical-align:middle" +
		"}" +
		"th.usis-af-th .usis-af-btn:hover,th.usis-af-th .usis-af-btn:focus{color:#2b6cb0;background:rgba(43,108,176,0.08)}" +
		"th.usis-af-th.is-filtered .usis-af-btn{color:#0d6efd}" +
		"th.usis-af-th.is-filtered .usis-af-btn .usis-af-funnel{opacity:1}" +
		".usis-af-col-hide{display:none !important}" +
		"#usis-af-pop{" +
		"position:fixed;z-index:1080;min-width:16.5rem;max-width:20rem;max-height:min(28rem,70vh);" +
		"overflow:auto;background:#fff;border:1px solid rgba(0,0,0,0.12);border-radius:0.35rem;" +
		"box-shadow:0 0.5rem 1.25rem rgba(0,0,0,0.15);padding:0.55rem 0.65rem;font-size:0.8125rem" +
		"}" +
		"#usis-af-pop .usis-af-pop-title{font-weight:600;margin-bottom:0.35rem}" +
		"#usis-af-pop .usis-af-sort-row{display:flex;flex-wrap:wrap;gap:0.25rem;margin-bottom:0.45rem}" +
		"#usis-af-pop .usis-af-values{max-height:11rem;overflow:auto;border:1px solid #e5e7eb;border-radius:0.25rem;padding:0.25rem 0.4rem;background:#fff}" +
		"#usis-af-pop .usis-af-val{display:block;margin:0;padding:0.12rem 0;cursor:pointer}" +
		".usis-af-sheet .offcanvas-body{max-height:70vh;overflow:auto}" +
		"@media (max-width:767.98px){" +
		"th.usis-af-th .usis-af-btn{min-width:1.5rem;min-height:1.5rem;font-size:0.85rem}" +
		"}";

	function injectStyle() {
		if (document.getElementById(STYLE_ID)) return;
		var el = document.createElement("style");
		el.id = STYLE_ID;
		el.textContent = CSS;
		document.head.appendChild(el);
	}

	function esc(s) {
		return String(s == null ? "" : s)
			.replace(/&/g, "&amp;")
			.replace(/</g, "&lt;")
			.replace(/>/g, "&gt;")
			.replace(/"/g, "&quot;");
	}

	function storageGet(key) {
		try {
			var raw = localStorage.getItem(key);
			return raw ? JSON.parse(raw) : null;
		} catch (e) {
			return null;
		}
	}

	function storageSet(key, val) {
		try {
			if (val == null) localStorage.removeItem(key);
			else localStorage.setItem(key, JSON.stringify(val));
		} catch (e) {}
	}

	function storageClear(key) {
		try {
			localStorage.removeItem(key);
		} catch (e) {}
	}

	function persistKey(tableId, kind) {
		return "grid:" + tableId + ":" + kind;
	}

	function isEmpty(v) {
		return v == null || v === "" || v === BLANK;
	}

	function parseDate(v) {
		if (v == null || v === "") return NaN;
		if (v instanceof Date) return v.getTime();
		var t = new Date(v).getTime();
		return t;
	}

	function cmpValues(a, b, type) {
		if (isEmpty(a) && isEmpty(b)) return 0;
		if (isEmpty(a)) return 1;
		if (isEmpty(b)) return -1;
		if (type === "date") {
			var da = parseDate(a);
			var db = parseDate(b);
			if (isNaN(da) && isNaN(db)) return 0;
			if (isNaN(da)) return 1;
			if (isNaN(db)) return -1;
			return da - db;
		}
		if (type === "number") {
			var na = Number(a);
			var nb = Number(b);
			if (isNaN(na) && isNaN(nb)) return 0;
			if (isNaN(na)) return 1;
			if (isNaN(nb)) return -1;
			return na - nb;
		}
		return String(a).localeCompare(String(b), undefined, { numeric: true, sensitivity: "base" });
	}

	function getVal(row, col) {
		if (!col) return "";
		if (typeof col.getValue === "function") return col.getValue(row);
		return row[col.key];
	}

	function tokenOf(raw, col) {
		if (isEmpty(raw)) return BLANK;
		if (col && col.type === "date") {
			var t = parseDate(raw);
			if (!isNaN(t)) return new Date(t).toLocaleDateString();
		}
		if (col && col.type === "number") {
			var n = Number(raw);
			if (!isNaN(n)) return String(n);
		}
		return String(raw).trim();
	}

	function displayToken(token) {
		if (token === BLANK) return "(Blanks)";
		return token;
	}

	function colByKey(columns, key) {
		for (var i = 0; i < columns.length; i++) {
			if (columns[i].key === key) return columns[i];
		}
		return null;
	}

	function filterIsActive(spec) {
		if (!spec || typeof spec !== "object") return false;
		if (Array.isArray(spec.values)) return true;
		if (spec.text && String(spec.text).trim()) return true;
		if (spec.op && spec.op !== "any") return true;
		return false;
	}

	function summarizeFilter(col, spec) {
		if (!filterIsActive(spec)) return "";
		var label = (col && col.label) || (col && col.key) || "Column";
		if (spec.text && String(spec.text).trim()) return label + " contains " + String(spec.text).trim();
		if (spec.op && spec.op !== "any") {
			var op = spec.op;
			if (op === "empty") return label + " is empty";
			if (op === "notEmpty") return label + " is not empty";
			if (op === "gt") return label + " > " + spec.a;
			if (op === "lt") return label + " < " + spec.a;
			if (op === "eq" || op === "on") return label + " = " + spec.a;
			if (op === "before") return label + " before " + spec.a;
			if (op === "after") return label + " after " + spec.a;
			if (op === "between") return label + " between " + spec.a + " and " + spec.b;
			if (op === "has") return label + " has value";
			if (op === "none") return label + " is empty";
		}
		if (Array.isArray(spec.values)) {
			if (!spec.values.length) return label + " (none)";
			var shown = spec.values
				.slice(0, 3)
				.map(displayToken)
				.join(", ");
			if (spec.values.length > 3) shown += "…";
			return label + " = " + shown;
		}
		return label + " filtered";
	}

	function matchesSpec(row, col, spec) {
		if (!filterIsActive(spec)) return true;
		var raw = getVal(row, col);
		var token = tokenOf(raw, col);

		if (Array.isArray(spec.values)) {
			if (spec.values.indexOf(token) === -1) return false;
		}
		if (spec.text && String(spec.text).trim()) {
			var q = String(spec.text).trim().toLowerCase();
			if (String(isEmpty(raw) ? "" : raw).toLowerCase().indexOf(q) === -1) return false;
		}
		var op = spec.op;
		if (!op || op === "any") return true;
		if (op === "empty" || op === "none") return isEmpty(raw);
		if (op === "notEmpty" || op === "has") return !isEmpty(raw);

		if (col.type === "number") {
			var n = Number(raw);
			var a = spec.a === "" || spec.a == null ? NaN : Number(spec.a);
			var b = spec.b === "" || spec.b == null ? NaN : Number(spec.b);
			if (op === "eq") return !isNaN(n) && n === a;
			if (op === "gt") return !isNaN(n) && !isNaN(a) && n > a;
			if (op === "lt") return !isNaN(n) && !isNaN(a) && n < a;
			if (op === "between") return !isNaN(n) && !isNaN(a) && !isNaN(b) && n >= Math.min(a, b) && n <= Math.max(a, b);
		}
		if (col.type === "date") {
			var t = parseDate(raw);
			var da = parseDate(spec.a);
			var db = parseDate(spec.b);
			if (op === "on" || op === "eq") {
				if (isNaN(t) || isNaN(da)) return false;
				var d1 = new Date(t);
				var d2 = new Date(da);
				return d1.toDateString() === d2.toDateString();
			}
			if (op === "before") return !isNaN(t) && !isNaN(da) && t < da;
			if (op === "after") return !isNaN(t) && !isNaN(da) && t > da;
			if (op === "between") {
				if (isNaN(t) || isNaN(da) || isNaN(db)) return false;
				var lo = Math.min(da, db);
				var hi = Math.max(da, db);
				return t >= lo && t <= hi;
			}
		}
		return true;
	}

	function uniqueTokens(rows, col) {
		var seen = Object.create(null);
		var out = [];
		var extras = col.valueOptions || [];
		for (var e = 0; e < extras.length; e++) {
			var ev = extras[e];
			if (ev == null || ev === "") continue;
			var et = String(ev);
			if (!seen[et]) {
				seen[et] = true;
				out.push(et);
			}
		}
		for (var i = 0; i < rows.length; i++) {
			var t = tokenOf(getVal(rows[i], col), col);
			if (!seen[t]) {
				seen[t] = true;
				out.push(t);
			}
		}
		out.sort(function (a, b) {
			if (a === BLANK) return -1;
			if (b === BLANK) return 1;
			return String(a).localeCompare(String(b), undefined, { numeric: true, sensitivity: "base" });
		});
		return out;
	}

	function closePopup() {
		var pop = document.getElementById(POP_ID);
		if (pop) pop.remove();
	}

	function placePopup(pop, anchor) {
		var r = anchor.getBoundingClientRect();
		var w = pop.offsetWidth;
		var h = pop.offsetHeight;
		var left = r.left;
		if (left + w > window.innerWidth - 8) left = Math.max(8, window.innerWidth - w - 8);
		var top = r.bottom + 4;
		if (top + h > window.innerHeight - 8 && r.top - 4 - h > 8) top = r.top - 4 - h;
		pop.style.left = left + "px";
		pop.style.top = top + "px";
	}

	function sortRows(rows, col, dir) {
		if (!col || !dir) return rows.slice();
		var mul = dir === "desc" ? -1 : 1;
		return rows.slice().sort(function (a, b) {
			return cmpValues(getVal(a, col), getVal(b, col), col.type || "text") * mul;
		});
	}

	function bind(opts) {
		opts = opts || {};
		injectStyle();
		var table = typeof opts.table === "string" ? document.querySelector(opts.table) : opts.table;
		var columns = opts.columns || [];
		var tableId = opts.tableId || "grid";
		var debounceMs = opts.filterDebounceMs != null ? opts.filterDebounceMs : DEBOUNCE_MS;
		var hideable = opts.hideable !== false;
		var getRows = typeof opts.getRows === "function" ? opts.getRows : function () { return []; };
		var rowId = typeof opts.rowId === "function" ? opts.rowId : function (row) { return row && (row.id != null ? String(row.id) : ""); };

		var sortState = { key: (opts.defaultSort && opts.defaultSort.key) || "", dir: (opts.defaultSort && opts.defaultSort.dir) || "asc" };
		var filterState = {};
		var colState = {};

		var savedSort = storageGet(persistKey(tableId, "sort"));
		if (savedSort && savedSort.key) {
			sortState.key = savedSort.key;
			sortState.dir = savedSort.dir === "desc" ? "desc" : savedSort.dir === null ? null : "asc";
		}
		var savedFilter = storageGet(persistKey(tableId, "filter"));
		if (savedFilter && typeof savedFilter === "object") filterState = savedFilter;
		var savedCols = storageGet(persistKey(tableId, "cols"));
		if (savedCols && typeof savedCols === "object") colState = savedCols;

		var debounceTimer = null;
		var bound = false;

		function persistAll() {
			storageSet(persistKey(tableId, "sort"), sortState.dir ? { key: sortState.key, dir: sortState.dir } : { key: sortState.key, dir: null });
			storageSet(persistKey(tableId, "filter"), filterState);
			storageSet(persistKey(tableId, "cols"), colState);
		}

		function notify() {
			persistAll();
			paint();
			if (typeof opts.onChange === "function") opts.onChange(getState());
		}

		function notifyDebounced() {
			clearTimeout(debounceTimer);
			debounceTimer = setTimeout(notify, debounceMs);
		}

		function activeLabels() {
			var labels = [];
			for (var i = 0; i < columns.length; i++) {
				var c = columns[i];
				if (c.filterable === false) continue;
				if (filterIsActive(filterState[c.key])) labels.push(c.label || c.key);
			}
			return labels;
		}

		function matchesRow(row) {
			for (var i = 0; i < columns.length; i++) {
				var c = columns[i];
				if (c.filterable === false) continue;
				if (!matchesSpec(row, c, filterState[c.key])) return false;
			}
			return true;
		}

		function filterRows(rows) {
			return (rows || []).filter(matchesRow);
		}

		function applySort(rows) {
			if (!sortState.dir || !sortState.key) return (rows || []).slice();
			var col = colByKey(columns, sortState.key);
			if (!col || col.sortable === false) return (rows || []).slice();
			return sortRows(rows || [], col, sortState.dir);
		}

		function apply(rows) {
			return applySort(filterRows(rows));
		}

		function setSort(key, dir) {
			var col = colByKey(columns, key);
			if (!col || col.sortable === false) return;
			if (dir === "clear" || dir === null) {
				sortState.key = key;
				sortState.dir = null;
			} else if (dir === "asc" || dir === "desc") {
				sortState.key = key;
				sortState.dir = dir;
			} else if (sortState.key === key) {
				sortState.dir = sortState.dir === "asc" ? "desc" : sortState.dir === "desc" ? null : "asc";
			} else {
				sortState.key = key;
				sortState.dir = (col && col.defaultDir) || "asc";
			}
			notify();
		}

		function clearFilter(key) {
			delete filterState[key];
			notify();
		}

		function hideColumn(key, hidden) {
			if (!hideable) return;
			if (hidden) colState[key] = false;
			else delete colState[key];
			notify();
		}

		function reset() {
			sortState = {
				key: (opts.defaultSort && opts.defaultSort.key) || "",
				dir: (opts.defaultSort && opts.defaultSort.dir) || "asc",
			};
			filterState = {};
			colState = {};
			storageClear(persistKey(tableId, "sort"));
			storageClear(persistKey(tableId, "filter"));
			storageClear(persistKey(tableId, "cols"));
			closePopup();
			notify();
		}

		function decorateHeader(th, col) {
			if (!th || th.getAttribute("data-af-ready") === "1") return;
			th.setAttribute("data-af-ready", "1");
			th.classList.add("usis-af-th");
			if (col && col.key) {
				if (!th.getAttribute("data-sort-key") && col.sortable !== false) th.setAttribute("data-sort-key", col.key);
				if (!th.getAttribute("data-filter-key") && col.filterable !== false) th.setAttribute("data-filter-key", col.key);
			}
			var existing = th.querySelector(".usis-af-head");
			if (existing) return;
			var labelText = (th.textContent || "").replace(/\s+/g, " ").trim();
			if (col && col.label && !labelText) labelText = col.label;
			th.textContent = "";
			var head = document.createElement("span");
			head.className = "usis-af-head";
			var lab = document.createElement("span");
			lab.className = "usis-af-label";
			lab.textContent = labelText;
			var arrow = document.createElement("span");
			arrow.className = "usis-sort-arrow";
			arrow.setAttribute("aria-hidden", "true");
			head.appendChild(lab);
			head.appendChild(arrow);
			if (col && (col.filterable !== false || col.sortable !== false)) {
				var btn = document.createElement("button");
				btn.type = "button";
				btn.className = "usis-af-btn";
				btn.setAttribute("data-af-key", col.key);
				btn.setAttribute("aria-label", "Sort and filter " + (col.label || col.key));
				btn.innerHTML = '<i class="fa fa-filter usis-af-funnel" aria-hidden="true"></i>';
				head.appendChild(btn);
			}
			th.appendChild(head);
		}

		function paint() {
			if (!table) return;
			var ths = table.querySelectorAll("thead th");
			for (var i = 0; i < ths.length; i++) {
				var th = ths[i];
				var key = th.getAttribute("data-sort-key") || th.getAttribute("data-filter-key");
				var col = key ? colByKey(columns, key) : null;
				if (col) decorateHeader(th, col);
				var hidden = key && colState[key] === false;
				th.classList.toggle("usis-af-col-hide", !!hidden);
				var trs = table.querySelectorAll("tbody tr");
				for (var r = 0; r < trs.length; r++) {
					var td = trs[r].children[i];
					if (td) td.classList.toggle("usis-af-col-hide", !!hidden);
				}
				if (!col) continue;
				var filtered = filterIsActive(filterState[col.key]);
				th.classList.toggle("is-filtered", filtered);
				th.classList.toggle("is-sorted", !!(sortState.dir && sortState.key === col.key));
				th.setAttribute("aria-sort", sortState.key === col.key && sortState.dir ? (sortState.dir === "desc" ? "descending" : "ascending") : "none");
				var tip = [];
				if (sortState.key === col.key && sortState.dir) tip.push("Sorted " + (sortState.dir === "desc" ? "Z→A" : "A→Z"));
				var sum = summarizeFilter(col, filterState[col.key]);
				if (sum) tip.push(sum);
				if (tip.length) th.setAttribute("title", tip.join(" · "));
				else th.removeAttribute("title");
				var arrow = th.querySelector(".usis-sort-arrow");
				if (arrow) {
					if (sortState.key === col.key && sortState.dir) {
						arrow.textContent = sortState.dir === "desc" ? "\u2193" : "\u2191";
						arrow.style.visibility = "visible";
					} else {
						arrow.textContent = "";
						arrow.style.visibility = "hidden";
					}
				}
			}
		}

		function operatorFields(col, spec) {
			spec = spec || {};
			var type = col.type || "text";
			if (type === "singleSelect") return "";
			var html = '<div class="mb-2">';
			if (type === "text" || type === "string") {
				html +=
					'<input type="search" class="form-control form-control-sm usis-af-text" placeholder="Contains…" value="' +
					esc(spec.text || "") +
					'">';
			} else if (type === "number") {
				html +=
					'<select class="form-select form-select-sm mb-1 usis-af-op">' +
					opt("any", "Any value", spec.op) +
					opt("eq", "Equals", spec.op) +
					opt("gt", "Greater than", spec.op) +
					opt("lt", "Less than", spec.op) +
					opt("between", "Between", spec.op) +
					opt("empty", "Is empty", spec.op) +
					opt("notEmpty", "Is not empty", spec.op) +
					"</select>" +
					'<div class="d-flex gap-1">' +
					'<input type="number" step="any" class="form-control form-control-sm usis-af-a" placeholder="Value" value="' +
					esc(spec.a == null ? "" : spec.a) +
					'">' +
					'<input type="number" step="any" class="form-control form-control-sm usis-af-b" placeholder="And" value="' +
					esc(spec.b == null ? "" : spec.b) +
					'"></div>';
			} else if (type === "date") {
				html +=
					'<select class="form-select form-select-sm mb-1 usis-af-op">' +
					opt("any", "Any date", spec.op) +
					opt("on", "On", spec.op) +
					opt("before", "Before", spec.op) +
					opt("after", "After", spec.op) +
					opt("between", "Between", spec.op) +
					opt("empty", "Is empty", spec.op) +
					opt("notEmpty", "Is not empty", spec.op) +
					"</select>" +
					'<div class="d-flex gap-1">' +
					'<input type="date" class="form-control form-control-sm usis-af-a" value="' +
					esc(toDateInput(spec.a)) +
					'">' +
					'<input type="date" class="form-control form-control-sm usis-af-b" value="' +
					esc(toDateInput(spec.b)) +
					'"></div>';
			}
			html += "</div>";
			return html;
		}

		function opt(val, label, cur) {
			return '<option value="' + val + '"' + (cur === val ? " selected" : "") + ">" + esc(label) + "</option>";
		}

		function toDateInput(v) {
			if (!v) return "";
			var t = parseDate(v);
			if (isNaN(t)) return String(v).slice(0, 10);
			var d = new Date(t);
			var m = String(d.getMonth() + 1);
			if (m.length < 2) m = "0" + m;
			var day = String(d.getDate());
			if (day.length < 2) day = "0" + day;
			return d.getFullYear() + "-" + m + "-" + day;
		}

		function readSpecFromPanel(panel, col) {
			var spec = {};
			var text = panel.querySelector(".usis-af-text");
			if (text && text.value.trim()) spec.text = text.value.trim();
			var op = panel.querySelector(".usis-af-op");
			if (op && op.value && op.value !== "any") spec.op = op.value;
			var a = panel.querySelector(".usis-af-a");
			var b = panel.querySelector(".usis-af-b");
			if (a && a.value) spec.a = a.value;
			if (b && b.value) spec.b = b.value;
			var boxes = panel.querySelectorAll(".usis-af-cb");
			if (boxes.length) {
				var selected = [];
				var total = boxes.length;
				for (var i = 0; i < boxes.length; i++) {
					if (boxes[i].checked) selected.push(boxes[i].getAttribute("data-token"));
				}
				if (selected.length === 0) spec.values = [];
				else if (selected.length < total) spec.values = selected;
			}
			if (!filterIsActive(spec)) return null;
			return spec;
		}

		function writeSpec(key, spec) {
			if (!spec) delete filterState[key];
			else filterState[key] = spec;
		}

		function openPopup(anchor, key) {
			var col = colByKey(columns, key);
			if (!col) return;
			closePopup();
			var spec = filterState[key] || {};
			var rows = getRows() || [];
			var list = uniqueTokens(rows, col);
			var pop = document.createElement("div");
			pop.id = POP_ID;
			pop.setAttribute("role", "dialog");
			pop.setAttribute("aria-label", "Sort and filter " + (col.label || col.key));
			var checks = "";
			if (col.filterable !== false) {
				for (var i = 0; i < list.length; i++) {
					var tok = list[i];
					var checked = !spec.values || spec.values.indexOf(tok) !== -1;
					checks +=
						'<label class="usis-af-val"><input type="checkbox" class="form-check-input me-1 usis-af-cb" data-token="' +
						esc(tok) +
						'"' +
						(checked ? " checked" : "") +
						">" +
						esc(displayToken(tok)) +
						"</label>";
				}
			}
			var sortBtns =
				col.sortable === false
					? ""
					: '<div class="usis-af-sort-row">' +
						'<button type="button" class="btn btn-outline-secondary btn-sm usis-af-sort" data-dir="asc">A → Z</button>' +
						'<button type="button" class="btn btn-outline-secondary btn-sm usis-af-sort" data-dir="desc">Z → A</button>' +
						'<button type="button" class="btn btn-outline-secondary btn-sm usis-af-sort" data-dir="clear">Clear sort</button>' +
						"</div>";
			pop.innerHTML =
				'<div class="usis-af-pop-title">' +
				esc(col.label || col.key) +
				"</div>" +
				sortBtns +
				(col.filterable === false
					? ""
					: operatorFields(col, spec) +
						'<div class="d-flex gap-1 mb-1">' +
						'<button type="button" class="btn btn-outline-secondary btn-sm usis-af-selall">Select all</button>' +
						'<button type="button" class="btn btn-outline-secondary btn-sm usis-af-selnone">Clear</button>' +
						"</div>" +
						'<input type="search" class="form-control form-control-sm mb-1 usis-af-listq" placeholder="Search values…">' +
						'<div class="usis-af-values mb-2">' +
						(checks || '<span class="text-muted">No values yet.</span>') +
						"</div>" +
						'<div class="d-flex flex-wrap gap-1">' +
						'<button type="button" class="btn btn-outline-secondary btn-sm usis-af-clearf">Clear filter</button>' +
						(hideable ? '<button type="button" class="btn btn-outline-secondary btn-sm usis-af-hide">Hide column</button>' : "") +
						"</div>");
			document.body.appendChild(pop);
			placePopup(pop, anchor);

			function commit(debounced) {
				if (col.filterable === false) return;
				writeSpec(key, readSpecFromPanel(pop, col));
				if (debounced) notifyDebounced();
				else notify();
			}

			pop.addEventListener("click", function (e) {
				var t = e.target.closest("button");
				if (!t || !pop.contains(t)) return;
				if (t.classList.contains("usis-af-sort")) {
					setSort(key, t.getAttribute("data-dir"));
					return;
				}
				if (t.classList.contains("usis-af-selall")) {
					pop.querySelectorAll(".usis-af-cb").forEach(function (cb) {
						cb.checked = true;
					});
					commit(false);
					return;
				}
				if (t.classList.contains("usis-af-selnone")) {
					pop.querySelectorAll(".usis-af-cb").forEach(function (cb) {
						cb.checked = false;
					});
					commit(false);
					return;
				}
				if (t.classList.contains("usis-af-clearf")) {
					pop.querySelectorAll(".usis-af-cb").forEach(function (cb) {
						cb.checked = true;
					});
					var text = pop.querySelector(".usis-af-text");
					if (text) text.value = "";
					var opEl = pop.querySelector(".usis-af-op");
					if (opEl) opEl.value = "any";
					var a = pop.querySelector(".usis-af-a");
					var b = pop.querySelector(".usis-af-b");
					if (a) a.value = "";
					if (b) b.value = "";
					clearFilter(key);
					return;
				}
				if (t.classList.contains("usis-af-hide")) {
					hideColumn(key, true);
					closePopup();
				}
			});
			pop.addEventListener("change", function (e) {
				if (e.target.classList.contains("usis-af-cb") || e.target.classList.contains("usis-af-op")) commit(false);
			});
			pop.addEventListener("input", function (e) {
				if (e.target.classList.contains("usis-af-listq")) {
					var q = String(e.target.value || "").trim().toLowerCase();
					pop.querySelectorAll(".usis-af-val").forEach(function (lab) {
						var t = (lab.textContent || "").toLowerCase();
						lab.style.display = !q || t.indexOf(q) !== -1 ? "" : "none";
					});
					return;
				}
				if (
					e.target.classList.contains("usis-af-text") ||
					e.target.classList.contains("usis-af-a") ||
					e.target.classList.contains("usis-af-b")
				) {
					commit(true);
				}
			});
		}

		function ensureSheet() {
			var sid = "usis-af-sheet-" + String(tableId).replace(/[^a-zA-Z0-9_-]/g, "-");
			var el = document.getElementById(sid);
			if (el) return el;
			el = document.createElement("div");
			el.id = sid;
			el.className = "offcanvas offcanvas-bottom usis-af-sheet";
			el.tabIndex = -1;
			el.setAttribute("aria-labelledby", sid + "-title");
			el.innerHTML =
				'<div class="offcanvas-header py-2">' +
				'<h5 class="offcanvas-title" id="' +
				sid +
				'-title">Sort &amp; Filter</h5>' +
				'<button type="button" class="btn-close" data-bs-dismiss="offcanvas" aria-label="Close"></button>' +
				"</div>" +
				'<div class="offcanvas-body py-2" data-af-sheet-body></div>';
			document.body.appendChild(el);
			return el;
		}

		function fillSheet() {
			var el = ensureSheet();
			var body = el.querySelector("[data-af-sheet-body]");
			if (!body) return el;
			var parts = [];
			for (var i = 0; i < columns.length; i++) {
				var c = columns[i];
				if (c.filterable === false && c.sortable === false) continue;
				if (colState[c.key] === false) continue;
				var sum = summarizeFilter(c, filterState[c.key]) || "No filter";
				parts.push(
					'<div class="border rounded p-2 mb-2">' +
						'<div class="d-flex justify-content-between align-items-center gap-2">' +
						"<strong>" +
						esc(c.label || c.key) +
						"</strong>" +
						'<button type="button" class="btn btn-sm btn-outline-primary usis-af-sheet-open" data-af-key="' +
						esc(c.key) +
						'" data-af-table="' +
						esc(tableId) +
						'">Open</button>' +
						"</div>" +
						'<div class="small text-muted">' +
						esc(sum) +
						"</div></div>"
				);
			}
			var hidden = [];
			for (var h = 0; h < columns.length; h++) {
				if (colState[columns[h].key] === false) hidden.push(columns[h]);
			}
			if (hidden.length) {
				parts.push('<p class="small text-muted mb-1">Hidden columns</p>');
				for (var x = 0; x < hidden.length; x++) {
					parts.push(
						'<button type="button" class="btn btn-sm btn-outline-secondary me-1 mb-1 usis-af-unhide" data-af-key="' +
							esc(hidden[x].key) +
							'" data-af-table="' +
							esc(tableId) +
							'">Show ' +
							esc(hidden[x].label || hidden[x].key) +
							"</button>"
					);
				}
			}
			body.innerHTML = parts.join("") || '<p class="text-muted mb-0">No filterable columns.</p>';
			return el;
		}

		function openSheet() {
			var el = fillSheet();
			if (global.bootstrap && bootstrap.Offcanvas) {
				bootstrap.Offcanvas.getOrCreateInstance(el).show();
			} else {
				el.classList.add("show");
				el.style.visibility = "visible";
			}
		}

		function applyDomRows(tbody, getRowFromTr) {
			if (!tbody) return { shown: 0, total: 0 };
			var trs = Array.prototype.slice.call(tbody.querySelectorAll("tr[data-line-id], tr[data-id]"));
			var pairs = [];
			for (var i = 0; i < trs.length; i++) {
				var row = getRowFromTr(trs[i]);
				if (row) pairs.push({ tr: trs[i], row: row });
			}
			var rows = pairs.map(function (p) { return p.row; });
			var filtered = filterRows(rows);
			var visible = Object.create(null);
			for (var f = 0; f < filtered.length; f++) visible[rowId(filtered[f])] = true;
			var sorted = applySort(rows);
			for (var s = 0; s < sorted.length; s++) {
				var id = rowId(sorted[s]);
				for (var p = 0; p < pairs.length; p++) {
					if (rowId(pairs[p].row) === id) {
						pairs[p].tr.hidden = !visible[id];
						tbody.appendChild(pairs[p].tr);
						break;
					}
				}
			}
			paint();
			return { shown: filtered.length, total: rows.length };
		}

		function getState() {
			return {
				sort: { key: sortState.key, dir: sortState.dir },
				filter: filterState,
				cols: colState,
				activeLabels: activeLabels(),
			};
		}

		if (table && !bound) {
			bound = true;
			table.addEventListener("click", function (e) {
				var btn = e.target.closest(".usis-af-btn");
				if (btn && table.contains(btn)) {
					e.preventDefault();
					e.stopPropagation();
					openPopup(btn, btn.getAttribute("data-af-key"));
					return;
				}
				var lab = e.target.closest(".usis-af-label");
				if (lab && table.contains(lab)) {
					var th = lab.closest("th");
					var key = th && (th.getAttribute("data-sort-key") || th.getAttribute("data-filter-key"));
					if (key) setSort(key);
				}
			});
		}

		document.addEventListener("mousedown", function (e) {
			var pop = document.getElementById(POP_ID);
			if (!pop) return;
			if (pop.contains(e.target) || (e.target.closest && e.target.closest(".usis-af-btn"))) return;
			closePopup();
		});
		document.addEventListener("keydown", function (e) {
			if (e.key === "Escape") closePopup();
		});
		window.addEventListener("resize", closePopup);

		var resetBtn = typeof opts.resetButton === "string" ? document.querySelector(opts.resetButton) : opts.resetButton;
		if (resetBtn) resetBtn.addEventListener("click", reset);
		var mobileBtn = typeof opts.mobileButton === "string" ? document.querySelector(opts.mobileButton) : opts.mobileButton;
		if (mobileBtn) mobileBtn.addEventListener("click", openSheet);

		var sheetHost = document.body;
		sheetHost.addEventListener("click", function (e) {
			var openBtn = e.target.closest(".usis-af-sheet-open");
			if (openBtn) {
				if (openBtn.getAttribute("data-af-table") !== tableId) return;
				var key = openBtn.getAttribute("data-af-key");
				if (!colByKey(columns, key)) return;
				openPopup(openBtn, key);
				return;
			}
			var unhide = e.target.closest(".usis-af-unhide");
			if (unhide) {
				if (unhide.getAttribute("data-af-table") !== tableId) return;
				hideColumn(unhide.getAttribute("data-af-key"), false);
				fillSheet();
			}
		});

		paint();

		return {
			apply: apply,
			filter: filterRows,
			sort: applySort,
			matches: matchesRow,
			getState: getState,
			getActiveLabels: activeLabels,
			paint: paint,
			reset: reset,
			setSort: setSort,
			clearFilter: clearFilter,
			applyDomRows: applyDomRows,
			closePopup: closePopup,
			openSheet: openSheet,
			openColumn: function (key, anchor) {
				openPopup(anchor || document.body, key);
			},
			summarize: function (key) {
				return summarizeFilter(colByKey(columns, key), filterState[key]);
			},
		};
	}

	global.USIS_TABLE_AUTOFILTER = {
		bind: bind,
		BLANK: BLANK,
		persistKey: persistKey,
		closePopup: closePopup,
	};
})(window);
