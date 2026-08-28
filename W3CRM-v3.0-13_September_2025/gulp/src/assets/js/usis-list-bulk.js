/**
 * Row checkboxes + bulk-action bar for list pages (leads, estimates, projects).
 */
(function () {
	"use strict";

	var selection = new Set();
	var cfg = null;

	function strId(id) {
		return id == null ? "" : String(id);
	}

	function notify(kind, message) {
		if (window.USISNotify && typeof window.USISNotify[kind] === "function") {
			window.USISNotify[kind](message);
			return;
		}
		window.alert(message);
	}

	function apiBase() {
		if (typeof window.usisApiBase === "function") {
			return String(window.usisApiBase() || "").replace(/\/$/, "");
		}
		if (typeof window.USIS_API_BASE === "string") {
			return window.USIS_API_BASE.trim().replace(/\/$/, "");
		}
		return "";
	}

	function updateBar() {
		if (!cfg) return;
		var bar = document.getElementById(cfg.barId);
		var countEl = document.getElementById(cfg.countId);
		if (countEl) countEl.textContent = selection.size + " selected";
		if (bar) bar.classList.toggle("d-none", selection.size === 0);
	}

	function updateCheckAll() {
		if (!cfg) return;
		var all = document.getElementById(cfg.checkAllId);
		var tbody = document.getElementById(cfg.tbodyId);
		if (!all || !tbody) return;
		var boxes = tbody.querySelectorAll(".usis-bulk-row-cb");
		if (!boxes.length) {
			all.checked = false;
			all.indeterminate = false;
			return;
		}
		var checked = 0;
		boxes.forEach(function (cb) {
			if (cb.checked) checked += 1;
		});
		all.checked = checked === boxes.length;
		all.indeterminate = checked > 0 && checked < boxes.length;
	}

	function visibleIds() {
		if (!cfg) return [];
		var tbody = document.getElementById(cfg.tbodyId);
		if (!tbody) return [];
		return Array.prototype.map
			.call(tbody.querySelectorAll("tr[data-id]"), function (tr) {
				return strId(tr.getAttribute("data-id"));
			})
			.filter(Boolean);
	}

	function afterRender() {
		updateCheckAll();
		updateBar();
	}

	function clear() {
		selection.clear();
		if (!cfg) return;
		var tbody = document.getElementById(cfg.tbodyId);
		if (tbody) {
			tbody.querySelectorAll(".usis-bulk-row-cb").forEach(function (cb) {
				cb.checked = false;
			});
		}
		afterRender();
	}

	function checkboxHtml(id) {
		var sid = strId(id);
		var checked = sid && selection.has(sid) ? " checked" : "";
		return (
			'<td class="text-center usis-bulk-col">' +
			'<input type="checkbox" class="usis-bulk-row-cb form-check-input m-0" aria-label="Select row"' +
			checked +
			">" +
			"</td>"
		);
	}

	function attach(options) {
		cfg = options || {};
		var tbody = document.getElementById(cfg.tbodyId);
		if (tbody && !tbody.getAttribute("data-usis-bulk-bound")) {
			tbody.setAttribute("data-usis-bulk-bound", "1");
			tbody.addEventListener("change", function (e) {
				var cb = e.target.closest(".usis-bulk-row-cb");
				if (!cb) return;
				var tr = cb.closest("tr");
				var id = tr && tr.getAttribute("data-id");
				if (!id) return;
				if (cb.checked) selection.add(id);
				else selection.delete(id);
				afterRender();
			});
		}
		var all = document.getElementById(cfg.checkAllId);
		if (all && !all.getAttribute("data-usis-bulk-bound")) {
			all.setAttribute("data-usis-bulk-bound", "1");
			all.addEventListener("change", function () {
				visibleIds().forEach(function (id) {
					if (all.checked) selection.add(id);
					else selection.delete(id);
				});
				if (tbody) {
					tbody.querySelectorAll(".usis-bulk-row-cb").forEach(function (cb) {
						cb.checked = all.checked;
					});
				}
				afterRender();
			});
		}
		var clr = document.getElementById(cfg.clearId);
		if (clr && !clr.getAttribute("data-usis-bulk-bound")) {
			clr.setAttribute("data-usis-bulk-bound", "1");
			clr.addEventListener("click", clear);
		}
		afterRender();
		return api;
	}

	function fetchJson(path, opts) {
		opts = opts || {};
		return fetch(apiBase() + path, {
			method: opts.method || "GET",
			credentials: "include",
			headers: {
				Accept: "application/json",
				"Content-Type": "application/json",
			},
			body: opts.body != null ? JSON.stringify(opts.body) : undefined,
		}).then(function (r) {
			return r.json().then(function (j) {
				if (!r.ok) throw new Error((j && j.error) || "HTTP " + r.status);
				return j;
			});
		});
	}

	var api = {
		attach: attach,
		checkboxHtml: checkboxHtml,
		afterRender: afterRender,
		clear: clear,
		ids: function () {
			return Array.from(selection);
		},
		size: function () {
			return selection.size;
		},
		has: function (id) {
			return selection.has(strId(id));
		},
		notify: notify,
		fetchJson: fetchJson,
	};

	window.USISListBulk = api;
})();
