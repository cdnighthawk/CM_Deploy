/**
 * BuildingConnected-style column sort: click a header to sort,
 * and show a blue arrow on the active column.
 */
(function (global) {
	"use strict";

	var STYLE_ID = "usis-table-sort-style";
	var CSS =
		"th.usis-sortable{cursor:pointer;user-select:none;-webkit-user-select:none}" +
		"th.usis-sortable:hover{color:#2b6cb0}" +
		"th.usis-sortable .usis-sort-arrow{" +
		"color:#3b9eff;font-weight:700;font-size:0.85em;margin-left:0.28rem;" +
		"line-height:1;display:inline-block;min-width:0.65em;vertical-align:0.05em" +
		"}";

	function injectStyle() {
		if (document.getElementById(STYLE_ID)) return;
		var el = document.createElement("style");
		el.id = STYLE_ID;
		el.textContent = CSS;
		document.head.appendChild(el);
	}

	function parseDate(v) {
		if (v == null || v === "") return NaN;
		var t = new Date(v).getTime();
		return t;
	}

	function isEmpty(v) {
		return v == null || v === "";
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

	function sortRows(rows, col, dir) {
		var mul = dir === "desc" ? -1 : 1;
		return rows.slice().sort(function (a, b) {
			return cmpValues(getVal(a, col), getVal(b, col), (col && col.type) || "text") * mul;
		});
	}

	function ensureArrow(th) {
		var el = th.querySelector(".usis-sort-arrow");
		if (el) return el;
		el = document.createElement("span");
		el.className = "usis-sort-arrow";
		el.setAttribute("aria-hidden", "true");
		th.appendChild(el);
		return el;
	}

	function bind(opts) {
		opts = opts || {};
		injectStyle();
		var table = typeof opts.table === "string" ? document.querySelector(opts.table) : opts.table;
		var columns = opts.columns || [];
		var storageKey = opts.storageKey || "";
		var state = {
			key: opts.defaultKey || (columns[0] && columns[0].key) || "",
			dir: opts.defaultDir || "asc",
		};
		if (storageKey) {
			try {
				var saved = JSON.parse(sessionStorage.getItem(storageKey) || "null");
				if (saved && saved.key) {
					state.key = saved.key;
					state.dir = saved.dir === "desc" ? "desc" : "asc";
				}
			} catch (e) {}
		}

		function colByKey(key) {
			for (var i = 0; i < columns.length; i++) {
				if (columns[i].key === key) return columns[i];
			}
			return null;
		}

		function persist() {
			if (!storageKey) return;
			try {
				sessionStorage.setItem(storageKey, JSON.stringify(state));
			} catch (e) {}
		}

		function paint() {
			if (!table) return;
			var ths = table.querySelectorAll("thead th[data-sort-key]");
			for (var i = 0; i < ths.length; i++) {
				var th = ths[i];
				var key = th.getAttribute("data-sort-key");
				th.classList.add("usis-sortable");
				th.setAttribute("role", "columnheader");
				th.setAttribute("tabindex", "0");
				if (!th.getAttribute("title")) th.setAttribute("title", "Click to sort");
				var arrow = ensureArrow(th);
				var active = key === state.key;
				th.classList.toggle("is-sorted", active);
				th.setAttribute("aria-sort", active ? (state.dir === "desc" ? "descending" : "ascending") : "none");
				if (active) {
					arrow.textContent = state.dir === "desc" ? "\u2193" : "\u2191";
					arrow.style.visibility = "visible";
				} else {
					arrow.textContent = "";
					arrow.style.visibility = "hidden";
				}
			}
		}

		function setSort(key) {
			if (!key || !colByKey(key)) return;
			if (state.key === key) {
				state.dir = state.dir === "asc" ? "desc" : "asc";
			} else {
				state.key = key;
				var col = colByKey(key);
				state.dir = (col && col.defaultDir) || "asc";
			}
			persist();
			paint();
			if (typeof opts.onChange === "function") opts.onChange(state);
		}

		if (table) {
			table.addEventListener("click", function (e) {
				var th = e.target.closest("th[data-sort-key]");
				if (!th || !table.contains(th)) return;
				setSort(th.getAttribute("data-sort-key"));
			});
			table.addEventListener("keydown", function (e) {
				if (e.key !== "Enter" && e.key !== " ") return;
				var th = e.target.closest("th[data-sort-key]");
				if (!th || !table.contains(th)) return;
				e.preventDefault();
				setSort(th.getAttribute("data-sort-key"));
			});
		}

		paint();

		return {
			apply: function (rows) {
				var col = colByKey(state.key);
				if (!col) return rows.slice();
				return sortRows(rows, col, state.dir);
			},
			getState: function () {
				return { key: state.key, dir: state.dir };
			},
			paint: paint,
		};
	}

	global.USIS_TABLE_SORT = { bind: bind, sortRows: sortRows };
})(window);
