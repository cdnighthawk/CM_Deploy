/**
 * Shared money-document line grid for Wave 1 create/detail pages.
 * Columns: # · Description · Qty · Unit · Unit price · Extension
 */
(function (global) {
	"use strict";

	function money(n) {
		var x = Number(n);
		if (isNaN(x)) return "$0.00";
		return x.toLocaleString(undefined, { style: "currency", currency: "USD" });
	}

	function num(el) {
		var v = parseFloat(String((el && el.value) || "0").replace(/,/g, ""));
		return isNaN(v) ? 0 : v;
	}

	function bind(opts) {
		var tbody = typeof opts.tbody === "string" ? document.getElementById(opts.tbody) : opts.tbody;
		var addBtn = typeof opts.addBtn === "string" ? document.getElementById(opts.addBtn) : opts.addBtn;
		var totalEl = typeof opts.totalEl === "string" ? document.getElementById(opts.totalEl) : opts.totalEl;
		var minRows = opts.minRows == null ? 1 : opts.minRows;

		function extension(tr) {
			return num(tr.querySelector("[data-line-qty]")) * num(tr.querySelector("[data-line-price]"));
		}

		function refresh() {
			if (!tbody) return;
			var rows = tbody.querySelectorAll("tr[data-line]");
			var sum = 0;
			rows.forEach(function (tr, i) {
				var idx = tr.querySelector("[data-line-idx]");
				if (idx) idx.textContent = String(i + 1);
				var ext = extension(tr);
				sum += ext;
				var extEl = tr.querySelector("[data-line-ext]");
				if (extEl) extEl.textContent = money(ext);
			});
			if (totalEl) totalEl.textContent = money(sum);
			return sum;
		}

		function addRow(item) {
			if (!tbody) return;
			item = item || {};
			var tr = document.createElement("tr");
			tr.setAttribute("data-line", "1");
			tr.innerHTML =
				'<td class="text-muted" data-line-idx></td>' +
				'<td><input type="text" class="form-control form-control-sm" data-line-desc maxlength="500" required></td>' +
				'<td><input type="number" class="form-control form-control-sm" data-line-qty step="0.0001" min="0" value="1"></td>' +
				'<td><input type="text" class="form-control form-control-sm" data-line-unit maxlength="40" value="LS"></td>' +
				'<td><input type="number" class="form-control form-control-sm" data-line-price step="0.01" min="0" value="0"></td>' +
				'<td class="text-end" data-line-ext>$0.00</td>' +
				'<td class="text-end"><button type="button" class="btn btn-link btn-sm text-danger p-0" data-line-remove aria-label="Remove line">&times;</button></td>';
			tbody.appendChild(tr);
			if (item.description) tr.querySelector("[data-line-desc]").value = item.description;
			if (item.quantity != null) tr.querySelector("[data-line-qty]").value = item.quantity;
			if (item.unit) tr.querySelector("[data-line-unit]").value = item.unit;
			if (item.unit_price != null || item.unit_cost != null) {
				tr.querySelector("[data-line-price]").value = item.unit_price != null ? item.unit_price : item.unit_cost;
			}
			refresh();
			return tr;
		}

		function collect() {
			if (!tbody) return [];
			return Array.prototype.map.call(tbody.querySelectorAll("tr[data-line]"), function (tr, i) {
				var qty = num(tr.querySelector("[data-line-qty]"));
				var price = num(tr.querySelector("[data-line-price]"));
				return {
					sort_order: i,
					description: (tr.querySelector("[data-line-desc]").value || "").trim(),
					quantity: qty,
					unit: (tr.querySelector("[data-line-unit]").value || "").trim() || "LS",
					unit_price: price,
					line_total: Math.round(qty * price * 100) / 100,
				};
			}).filter(function (row) {
				return row.description;
			});
		}

		function load(items) {
			if (!tbody) return;
			tbody.innerHTML = "";
			(items && items.length ? items : [{}]).forEach(addRow);
			while (tbody.querySelectorAll("tr[data-line]").length < minRows) addRow({});
			refresh();
		}

		if (tbody && !tbody._usisLinesBound) {
			tbody._usisLinesBound = true;
			tbody.addEventListener("input", refresh);
			tbody.addEventListener("click", function (e) {
				var btn = e.target.closest("[data-line-remove]");
				if (!btn) return;
				var tr = btn.closest("tr");
				if (tr && tbody.querySelectorAll("tr[data-line]").length > minRows) {
					tr.remove();
					refresh();
				}
			});
		}
		if (addBtn && !addBtn._usisLinesBound) {
			addBtn._usisLinesBound = true;
			addBtn.addEventListener("click", function () {
				addRow({});
			});
		}

		return { addRow: addRow, collect: collect, load: load, refresh: refresh, total: refresh };
	}

	global.USISDocumentLines = { bind: bind, money: money };
})(window);
