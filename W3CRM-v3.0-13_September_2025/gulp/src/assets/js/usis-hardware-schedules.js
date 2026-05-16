/**
 * Company hardware schedules (HD-1 … HD-N) — edit door_hardware_sets + items.
 * Catalog picker uses GET /api/v1/material-prices?csi_spec_section=087100 only.
 */
(function () {
	"use strict";

	var CSI_DOOR_HARDWARE = "087100";
	var sets = [];
	var selectedCode = null;
	var catalogTargetItemId = null;

	function apiBase() {
		if (typeof window.usisApiBase === "function") return window.usisApiBase();
		if (typeof window.USIS_API_BASE === "string") {
			return window.USIS_API_BASE.trim().replace(/\/$/, "");
		}
		var loc = window.location;
		if (loc && loc.protocol === "file:") return "http://127.0.0.1:5000";
		var port = String(loc.port || "");
		if (["3000", "3001", "3002", "3003"].indexOf(port) >= 0) return "";
		if (loc.hostname === "localhost" || loc.hostname === "127.0.0.1") {
			return loc.protocol + "//" + loc.hostname + ":5000";
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

	function money(n) {
		if (n == null || isNaN(Number(n))) return "—";
		return Number(n).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
	}

	function showErr(msg) {
		var el = document.getElementById("usis-hs-error");
		if (!el) return;
		if (!msg) {
			el.classList.add("d-none");
			el.textContent = "";
			return;
		}
		el.textContent = msg;
		el.classList.remove("d-none");
	}

	function parseJsonResponse(r, text) {
		var trimmed = (text || "").trim();
		if (!trimmed) {
			throw new Error("HTTP " + r.status + " (empty response)");
		}
		try {
			return JSON.parse(trimmed);
		} catch (e) {
			var preview = trimmed.slice(0, 80).replace(/\s+/g, " ");
			throw new Error("HTTP " + r.status + " — server did not return JSON (" + preview + ")");
		}
	}

	function fetchJson(path, opts) {
		opts = opts || {};
		return fetch(apiBase() + path, Object.assign({ credentials: "include", headers: { Accept: "application/json" } }, opts))
			.then(function (r) {
				return r.text().then(function (text) {
					if (!r.ok) {
						var j = parseJsonResponse(r, text);
						throw new Error((j && j.error) || "HTTP " + r.status);
					}
					return parseJsonResponse(r, text);
				});
			});
	}

	function selectedSet() {
		if (!selectedCode) return null;
		for (var i = 0; i < sets.length; i++) {
			if (sets[i].code === selectedCode) return sets[i];
		}
		return null;
	}

	function renderSetList() {
		var list = document.getElementById("usis-hs-set-list");
		if (!list) return;
		if (!sets.length) {
			list.innerHTML =
				'<div class="list-group-item text-muted small">No sets yet. Click + Add set.</div>';
			return;
		}
		list.innerHTML = sets
			.map(function (s) {
				var active = s.code === selectedCode ? " active" : "";
				return (
					'<button type="button" class="list-group-item list-group-item-action' +
					active +
					'" data-code="' +
					esc(s.code) +
					'">' +
					esc(s.code) +
					(s.name ? ' <span class="text-muted">— ' + esc(s.name) + "</span>" : "") +
					"</button>"
				);
			})
			.join("");
		list.querySelectorAll("[data-code]").forEach(function (btn) {
			btn.addEventListener("click", function () {
				selectSet(btn.getAttribute("data-code"));
			});
		});
	}

	function renderLines() {
		var hs = selectedSet();
		var tbody = document.getElementById("usis-hs-lines-tbody");
		var title = document.getElementById("usis-hs-set-title");
		var desc = document.getElementById("usis-hs-set-desc");
		var addBtn = document.getElementById("usis-hs-add-line");
		var totalEl = document.getElementById("usis-hs-lines-total");
		if (!tbody) return;
		if (!hs) {
			if (title) title.textContent = "Select a set";
			if (desc) desc.classList.add("d-none");
			if (addBtn) addBtn.classList.add("d-none");
			tbody.innerHTML = '<tr><td colspan="7" class="text-muted">Select a hardware set on the left.</td></tr>';
			if (totalEl) totalEl.textContent = "—";
			return;
		}
		if (title) title.textContent = hs.code + (hs.name ? " — " + hs.name : "");
		if (desc) {
			if (hs.description) {
				desc.textContent = hs.description;
				desc.classList.remove("d-none");
			} else {
				desc.classList.add("d-none");
			}
		}
		if (addBtn) addBtn.classList.remove("d-none");
		var items = hs.items || [];
		if (!items.length) {
			tbody.innerHTML = '<tr><td colspan="7" class="text-muted">No components. Click + Add line.</td></tr>';
		} else {
			tbody.innerHTML = items
				.map(function (it) {
					var cat =
						it.material_pricing_id
							? '<span class="text-success">Linked</span>'
							: '<span class="text-muted">—</span>';
					return (
						'<tr data-item-id="' +
						esc(it.id) +
						'">' +
						'<td><input class="form-control form-control-sm usis-hs-inp" data-field="label" value="' +
						esc(it.label) +
						'"></td>' +
						'<td><select class="form-select form-select-sm usis-hs-inp" data-field="cost_type">' +
						["L", "M", "E", "S", "O"]
							.map(function (c) {
								var sel = (it.cost_type || "M").charAt(0).toUpperCase() === c ? " selected" : "";
								return '<option value="' + c + '"' + sel + ">" + c + "</option>";
							})
							.join("") +
						"</select></td>" +
						'<td class="text-end"><input type="number" step="0.0001" class="form-control form-control-sm usis-hs-inp text-end" data-field="default_qty" value="' +
						esc(it.default_qty) +
						'" style="max-width:5rem"></td>' +
						'<td><input class="form-control form-control-sm usis-hs-inp" data-field="unit" value="' +
						esc(it.unit || "EA") +
						'" style="max-width:4rem"></td>' +
						'<td class="text-end"><input type="number" step="0.01" class="form-control form-control-sm usis-hs-inp text-end" data-field="default_unit_cost" value="' +
						esc(it.default_unit_cost) +
						'" style="max-width:6rem"></td>' +
						'<td>' +
						cat +
						' <button type="button" class="btn btn-xs btn-outline-primary btn-sm py-0 usis-hs-pick-cat" data-id="' +
						esc(it.id) +
						'">Pick</button></td>' +
						'<td class="text-end"><button type="button" class="btn btn-sm btn-outline-danger py-0 usis-hs-del-line" data-id="' +
						esc(it.id) +
						'">×</button></td>' +
						"</tr>"
					);
				})
				.join("");
		}
		var sub = 0;
		for (var j = 0; j < items.length; j++) {
			sub += (Number(items[j].default_qty) || 0) * (Number(items[j].default_unit_cost) || 0);
		}
		if (totalEl) totalEl.textContent = "$" + money(sub);
		wireLineInputs();
	}

	function patchItem(itemId, body) {
		return fetchJson("/api/v1/door-hardware-set-items/" + encodeURIComponent(itemId), {
			method: "PATCH",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify(body),
		}).then(function (data) {
			mergeSet(data.item);
			renderSetList();
			renderLines();
		});
	}

	function mergeSet(item) {
		if (!item || !item.code) return;
		var found = false;
		for (var i = 0; i < sets.length; i++) {
			if (sets[i].code === item.code) {
				sets[i] = item;
				found = true;
				break;
			}
		}
		if (!found) {
			sets.push(item);
			sets.sort(function (a, b) {
				return String(a.code).localeCompare(String(b.code), undefined, { numeric: true });
			});
		}
	}

	function wireLineInputs() {
		var tbody = document.getElementById("usis-hs-lines-tbody");
		if (!tbody) return;
		tbody.querySelectorAll(".usis-hs-inp").forEach(function (inp) {
			inp.addEventListener("change", function () {
				var tr = inp.closest("tr");
				var id = tr && tr.getAttribute("data-item-id");
				if (!id) return;
				var field = inp.getAttribute("data-field");
				var body = {};
				body[field] = inp.value;
				patchItem(id, body).catch(function (e) {
					showErr(e.message);
				});
			});
		});
		tbody.querySelectorAll(".usis-hs-del-line").forEach(function (btn) {
			btn.addEventListener("click", function () {
				var id = btn.getAttribute("data-id");
				if (!id || !window.confirm("Delete this component?")) return;
				fetchJson("/api/v1/door-hardware-set-items/" + encodeURIComponent(id), { method: "DELETE" })
					.then(function (data) {
						mergeSet(data.item);
						renderSetList();
						renderLines();
					})
					.catch(function (e) {
						showErr(e.message);
					});
			});
		});
		tbody.querySelectorAll(".usis-hs-pick-cat").forEach(function (btn) {
			btn.addEventListener("click", function () {
				catalogTargetItemId = btn.getAttribute("data-id");
				var modal = document.getElementById("usis-hs-catalog-modal");
				if (modal && typeof bootstrap !== "undefined") {
					bootstrap.Modal.getOrCreateInstance(modal).show();
				}
				searchCatalog();
			});
		});
	}

	function searchCatalog() {
		var q = (document.getElementById("usis-hs-catalog-q") || {}).value || "";
		var ul = document.getElementById("usis-hs-catalog-results");
		if (!ul) return;
		ul.innerHTML = '<li class="list-group-item text-muted">Searching…</li>';
		var url =
			"/api/v1/material-prices?csi_spec_section=" +
			encodeURIComponent(CSI_DOOR_HARDWARE) +
			"&limit=50";
		if (q.trim()) url += "&q=" + encodeURIComponent(q.trim());
		fetchJson(url)
			.then(function (data) {
				var items = data.items || [];
				if (!items.length) {
					ul.innerHTML =
						'<li class="list-group-item text-muted">No 08 71 00 items in catalog — import material CSV with spec section or use --tag-door-hardware.</li>';
					return;
				}
				ul.innerHTML = items
					.map(function (m) {
						return (
							'<li class="list-group-item d-flex justify-content-between align-items-start gap-2">' +
							"<span>" +
							esc(m.manufacturer) +
							" · " +
							esc(m.item) +
							(m.description ? '<br><span class="text-muted">' + esc(m.description) + "</span>" : "") +
							'<br><span class="text-muted">$' +
							esc(String(m.cost != null ? m.cost : "—")) +
							" / " +
							esc(m.unit_of_measure || "") +
							"</span></span>" +
							'<button type="button" class="btn btn-sm btn-primary py-0 usis-hs-apply-cat" data-id="' +
							esc(m.id) +
							'" data-cost="' +
							esc(m.cost != null ? m.cost : "") +
							'">Use</button>' +
							"</li>"
						);
					})
					.join("");
				ul.querySelectorAll(".usis-hs-apply-cat").forEach(function (btn) {
					btn.addEventListener("click", function () {
						if (!catalogTargetItemId) return;
						var body = {
							material_pricing_id: btn.getAttribute("data-id"),
						};
						var cost = btn.getAttribute("data-cost");
						if (cost !== "" && cost != null) body.default_unit_cost = cost;
						patchItem(catalogTargetItemId, body)
							.then(function () {
								var modal = document.getElementById("usis-hs-catalog-modal");
								if (modal && typeof bootstrap !== "undefined") {
									var inst = bootstrap.Modal.getInstance(modal);
									if (inst) inst.hide();
								}
							})
							.catch(function (e) {
								showErr(e.message);
							});
					});
				});
			})
			.catch(function (e) {
				ul.innerHTML = '<li class="list-group-item text-danger">' + esc(e.message) + "</li>";
			});
	}

	function selectSet(code) {
		selectedCode = code;
		renderSetList();
		renderLines();
	}

	function loadSets() {
		showErr("");
		return fetchJson("/api/v1/door-hardware-sets").then(function (data) {
			sets = data.items || [];
			sets.sort(function (a, b) {
				return String(a.code).localeCompare(String(b.code), undefined, { numeric: true });
			});
			if (!selectedCode && sets.length) selectedCode = sets[0].code;
			renderSetList();
			renderLines();
		});
	}

	function addSet() {
		var code = window.prompt("Hardware set code (e.g. HD-3)", "HD-");
		if (code == null) return;
		var name = window.prompt("Name (optional)", "") || "";
		fetchJson("/api/v1/door-hardware-sets", {
			method: "POST",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify({ code: code.trim(), name: name.trim() }),
		})
			.then(function (data) {
				mergeSet(data.item);
				selectedCode = data.item.code;
				loadSets();
				if (window.USISNotify) window.USISNotify.success("Created " + data.item.code);
			})
			.catch(function (e) {
				showErr(e.message);
			});
	}

	function addLine() {
		var hs = selectedSet();
		if (!hs) return;
		fetchJson("/api/v1/door-hardware-sets/" + encodeURIComponent(hs.code) + "/items", {
			method: "POST",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify({ label: "New component", cost_type: "M", default_qty: 1, unit: "EA" }),
		})
			.then(function (data) {
				mergeSet(data.item);
				renderLines();
			})
			.catch(function (e) {
				showErr(e.message);
			});
	}

	function init() {
		var addSetBtn = document.getElementById("usis-hs-add-set");
		var refreshBtn = document.getElementById("usis-hs-refresh");
		var addLineBtn = document.getElementById("usis-hs-add-line");
		var catSearch = document.getElementById("usis-hs-catalog-search");
		if (addSetBtn) addSetBtn.addEventListener("click", addSet);
		if (refreshBtn) refreshBtn.addEventListener("click", function () {
			loadSets().catch(function (e) {
				showErr(e.message);
			});
		});
		if (addLineBtn) addLineBtn.addEventListener("click", addLine);
		if (catSearch) catSearch.addEventListener("click", searchCatalog);
		loadSets().catch(function (e) {
			showErr(e.message);
		});
	}

	if (document.readyState === "loading") {
		document.addEventListener("DOMContentLoaded", init);
	} else {
		init();
	}
})();
