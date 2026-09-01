/**
 * Line-card suggestions on the RFP vendor picker (manufacturer vs distributor).
 */
(function () {
	"use strict";

	function $(id) {
		return document.getElementById(id);
	}

	function esc(s) {
		if (s == null || s === "") return "";
		var d = document.createElement("div");
		d.textContent = String(s);
		return d.innerHTML;
	}

	function fetchJson(path, opts) {
		if (window.USIS_API && typeof window.USIS_API.fetchJson === "function") {
			return window.USIS_API.fetchJson(path, opts || {});
		}
		return Promise.reject(new Error("API helper missing"));
	}

	function rfpId() {
		var q = new URLSearchParams(window.location.search);
		return q.get("id") || q.get("rfp") || "";
	}

	function ensureSuggestedBox() {
		var box = $("usis-rfp-vendor-suggested");
		if (box) return box;
		var chips = $("usis-rfp-bidder-chips");
		if (!chips || !chips.parentNode) return null;
		box = document.createElement("div");
		box.id = "usis-rfp-vendor-suggested";
		box.className = "mb-2";
		chips.parentNode.insertBefore(box, chips);
		return box;
	}

	function alreadyPicked(companyId) {
		var boxes = document.querySelectorAll("[data-sel]");
		return Array.prototype.some.call(boxes, function () {
			return false;
		});
	}

	function pickViaSearchApi(row) {
		var ev = new CustomEvent("usis-rfp-pick-vendor", { detail: row });
		document.dispatchEvent(ev);
		if (typeof window.usisRfpPickVendor === "function") {
			window.usisRfpPickVendor(row);
			return;
		}
		var btn = document.querySelector('#usis-rfp-vendor-results [data-company="' + row.id + '"]');
		if (btn) btn.dispatchEvent(new MouseEvent("mousedown", { bubbles: true, cancelable: true }));
	}

	function loadSuggested() {
		var box = ensureSuggestedBox();
		var id = rfpId();
		if (!box || !id) return;
		fetchJson("/api/v1/rfps/" + encodeURIComponent(id) + "/vendors?suggested=1")
			.then(function (d) {
				var items = d.items || [];
				if (!items.length) {
					box.innerHTML = "";
					return;
				}
				box.innerHTML =
					'<p class="small text-muted mb-1">Suggested for this package</p>' +
					items
						.slice(0, 12)
						.map(function (c) {
							return (
								'<button type="button" class="btn btn-outline-secondary btn-sm me-1 mb-1" data-suggest="' +
								esc(c.id) +
								'">' +
								esc(c.name) +
								(c.match_reason ? ' <span class="text-muted">' + esc(c.match_reason) + "</span>" : "") +
								"</button>"
							);
						})
						.join("");
				box.querySelectorAll("[data-suggest]").forEach(function (btn) {
					btn.addEventListener("click", function () {
						var cid = btn.getAttribute("data-suggest");
						var row = items.find(function (c) {
							return c.id === cid;
						});
						if (row && typeof window.usisRfpPickVendor === "function") {
							window.usisRfpPickVendor(row);
							loadSuggested();
							return;
						}
					});
				});
			})
			.catch(function () {
				box.innerHTML = "";
			});
	}

	function ensureRoleSelect() {
		if ($("usis-nv-role-unset")) return;
		var type = $("usis-nv-type");
		if (!type || !type.parentNode || !type.parentNode.parentNode) return;
		var col = document.createElement("div");
		col.className = "col-12";
		col.innerHTML =
			'<label class="form-label small mb-1">Manufacturer or distributor</label>' +
			'<div class="btn-group btn-group-sm flex-wrap" role="group" aria-label="Supply role">' +
			'<input type="radio" class="btn-check" name="usis-nv-role" id="usis-nv-role-unset" value="" checked>' +
			'<label class="btn btn-outline-secondary" for="usis-nv-role-unset">Unset</label>' +
			'<input type="radio" class="btn-check" name="usis-nv-role" id="usis-nv-role-mfr" value="manufacturer">' +
			'<label class="btn btn-outline-primary" for="usis-nv-role-mfr">Manufacturer</label>' +
			'<input type="radio" class="btn-check" name="usis-nv-role" id="usis-nv-role-dist" value="distributor">' +
			'<label class="btn btn-outline-primary" for="usis-nv-role-dist">Distributor</label>' +
			'<input type="radio" class="btn-check" name="usis-nv-role" id="usis-nv-role-both" value="both">' +
			'<label class="btn btn-outline-primary" for="usis-nv-role-both">Both</label>' +
			"</div>";
		type.parentNode.parentNode.insertBefore(col, type.parentNode.nextSibling);
	}

	function onReady() {
		ensureRoleSelect();
		ensureSuggestedBox();
		loadSuggested();
		var modal = $("usis-rfp-vendor-modal");
		if (modal) {
			modal.addEventListener("shown.bs.modal", loadSuggested);
		}
		var save = $("usis-rfp-vendor-save");
		if (save) {
			save.addEventListener(
				"click",
				function () {
					var orig = window.USIS_API && window.USIS_API.fetchJson;
					if (!orig) return;
					window.USIS_API.fetchJson = function (path, opts) {
						opts = opts || {};
						if (path === "/api/v1/companies" && opts.method === "POST") {
							var body = opts.body;
							if (typeof body === "string") {
								try {
									body = JSON.parse(body);
								} catch (e) {
									body = {};
								}
							}
							if (body && typeof body === "object") {
								var roleEl = document.querySelector('input[name="usis-nv-role"]:checked');
								var role = roleEl ? roleEl.value : "";
								if (role) body.supply_role = role;
								opts.body = body;
							}
						}
						return orig.call(window.USIS_API, path, opts);
					};
					setTimeout(function () {
						window.USIS_API.fetchJson = orig;
					}, 8000);
				},
				true
			);
		}
	}

	if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", onReady);
	else onReady();
	window.usisLoadRfpVendorSuggestions = loadSuggested;
})();
