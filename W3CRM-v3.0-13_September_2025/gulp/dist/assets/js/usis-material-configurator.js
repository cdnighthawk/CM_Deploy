/**
 * Catalog option picker for configurable material_pricing rows (Larsen cabinets).
 * Size + mounting stay on the SKU; series, material, door, handle, and extras are chosen here.
 */
(function (global) {
	"use strict";

	var MODAL_ID = "usis-mat-cfg-modal";
	var pending = null;

	function esc(s) {
		return String(s == null ? "" : s)
			.replace(/&/g, "&amp;")
			.replace(/</g, "&lt;")
			.replace(/>/g, "&gt;")
			.replace(/"/g, "&quot;");
	}

	function money(n) {
		var v = Number(n);
		if (isNaN(v)) return "$0.00";
		return (
			(v < 0 ? "-$" : "$") +
			Math.abs(v).toFixed(2)
		);
	}

	function ensureModal() {
		var el = document.getElementById(MODAL_ID);
		if (el) return el;
		el = document.createElement("div");
		el.id = MODAL_ID;
		el.className = "modal fade";
		el.tabIndex = -1;
		el.setAttribute("aria-hidden", "true");
		el.innerHTML =
			'<div class="modal-dialog modal-dialog-centered modal-dialog-scrollable">' +
			'<div class="modal-content">' +
			'<div class="modal-header py-2">' +
			'<h5 class="modal-title fs-6" id="usis-mat-cfg-title">Configure item</h5>' +
			'<button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>' +
			"</div>" +
			'<div class="modal-body py-3" id="usis-mat-cfg-body"></div>' +
			'<div class="modal-footer py-2">' +
			'<div class="me-auto small" id="usis-mat-cfg-total"></div>' +
			'<button type="button" class="btn btn-outline-secondary btn-sm" data-bs-dismiss="modal">Cancel</button>' +
			'<button type="button" class="btn btn-primary btn-sm" id="usis-mat-cfg-apply">Add to estimate</button>' +
			"</div></div></div>";
		document.body.appendChild(el);
		el.querySelector("#usis-mat-cfg-apply").addEventListener("click", commit);
		el.addEventListener("change", refreshTotal);
		return el;
	}

	function groupValue(group) {
		if (group.multiple) {
			return Array.prototype.map
				.call(document.querySelectorAll('input[name="usis-cfg-' + group.id + '"]:checked'), function (n) {
					return n.value;
				});
		}
		var sel = document.getElementById("usis-cfg-" + group.id);
		return sel ? sel.value : group.default;
	}

	function collectSelections(schema) {
		var out = {};
		(schema.groups || []).forEach(function (group) {
			out[group.id] = groupValue(group);
		});
		return out;
	}

	function choiceCost(choice) {
		var n = Number(choice && choice.cost != null ? choice.cost : 0);
		return isNaN(n) ? 0 : n;
	}

	function preview(item, schema, selections) {
		var total = Number(item.cost != null ? item.cost : 0) || 0;
		var labels = [];
		(schema.groups || []).forEach(function (group) {
			var map = {};
			(group.choices || []).forEach(function (c) {
				map[c.id] = c;
			});
			if (group.multiple) {
				(selections[group.id] || []).forEach(function (id) {
					var c = map[id];
					if (!c) return;
					total += choiceCost(c);
					labels.push(c.label);
				});
				return;
			}
			var c = map[selections[group.id]];
			if (!c) return;
			total += choiceCost(c);
			labels.push(c.label);
		});
		return { total: total, labels: labels };
	}

	function renderGroup(group, selected) {
		if (group.multiple) {
			var picked = selected[group.id] || [];
			return (
				'<fieldset class="mb-3">' +
				'<legend class="form-label small fw-semibold mb-1">' +
				esc(group.label) +
				"</legend>" +
				(group.choices || [])
					.map(function (c) {
						var id = "usis-cfg-" + group.id + "-" + c.id;
						return (
							'<div class="form-check">' +
							'<input class="form-check-input" type="checkbox" name="usis-cfg-' +
							esc(group.id) +
							'" id="' +
							esc(id) +
							'" value="' +
							esc(c.id) +
							'"' +
							(picked.indexOf(c.id) >= 0 ? " checked" : "") +
							">" +
							'<label class="form-check-label" for="' +
							esc(id) +
							'">' +
							esc(c.label) +
							(c.cost ? " (" + money(c.cost) + ")" : "") +
							"</label></div>"
						);
					})
					.join("") +
				"</fieldset>"
			);
		}
		return (
			'<div class="mb-3">' +
			'<label class="form-label small fw-semibold mb-1" for="usis-cfg-' +
			esc(group.id) +
			'">' +
			esc(group.label) +
			"</label>" +
			'<select class="form-select form-select-sm" id="usis-cfg-' +
			esc(group.id) +
			'">' +
			(group.choices || [])
				.map(function (c) {
					return (
						'<option value="' +
						esc(c.id) +
						'"' +
						(c.id === selected[group.id] ? " selected" : "") +
						">" +
						esc(c.label) +
						(c.cost ? " (" + money(c.cost) + ")" : "") +
						"</option>"
					);
				})
				.join("") +
			"</select></div>"
		);
	}

	function selectedFromItem(item, existing) {
		var schema = item.configurator || {};
		var out = {};
		(schema.groups || []).forEach(function (group) {
			if (existing && existing[group.id] != null) {
				out[group.id] = existing[group.id];
				return;
			}
			out[group.id] = group.multiple ? [] : group.default;
		});
		return out;
	}

	function refreshTotal() {
		if (!pending) return;
		var sel = collectSelections(pending.item.configurator || {});
		var prev = preview(pending.item, pending.item.configurator || {}, sel);
		var totalEl = document.getElementById("usis-mat-cfg-total");
		if (totalEl) totalEl.textContent = "Unit cost " + money(prev.total);
	}

	function commit() {
		if (!pending) return;
		var sel = collectSelections(pending.item.configurator || {});
		var onApply = pending.onApply;
		var item = pending.item;
		hide();
		if (typeof onApply === "function") onApply(item, sel);
	}

	function hide() {
		var el = document.getElementById(MODAL_ID);
		if (el && global.bootstrap && global.bootstrap.Modal) {
			global.bootstrap.Modal.getOrCreateInstance(el).hide();
		}
		pending = null;
	}

	function open(item, existing, onApply) {
		if (!item || !item.configurator) return false;
		pending = { item: item, onApply: onApply };
		ensureModal();
		var title = document.getElementById("usis-mat-cfg-title");
		if (title) {
			title.textContent =
				(item.manufacturer || "") +
				" " +
				(item.item || "") +
				(item.mounting_type ? " · " + item.mounting_type : "");
		}
		var selected = selectedFromItem(item, existing && existing.selections ? existing.selections : existing);
		var body = document.getElementById("usis-mat-cfg-body");
		if (body) {
			body.innerHTML =
				'<p class="small text-muted mb-3">SKU is size and mounting. Pick series, material, door style, and hardware for this estimate line.</p>' +
				(item.configurator.groups || []).map(function (g) {
					return renderGroup(g, selected);
				}).join("");
		}
		refreshTotal();
		var el = document.getElementById(MODAL_ID);
		if (el && global.bootstrap && global.bootstrap.Modal) {
			global.bootstrap.Modal.getOrCreateInstance(el).show();
		}
		return true;
	}

	global.USISMaterialConfigurator = {
		open: open,
		preview: preview,
	};
})(window);
