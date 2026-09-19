/**
 * Prevailing wage rates (Admin → Wage rates).
 */
(function () {
	"use strict";

	var PAGE_SIZE = 100;
	var offset = 0;
	var total = 0;
	var items = [];
	var keepOpen = false;
	var searchTimer = null;

	function api() {
		return window.USIS_API || {};
	}

	function fetchJson(path, opts) {
		return api().fetchJson(path, opts || {});
	}

	function esc(s) {
		if (s == null) return "";
		var d = document.createElement("div");
		d.textContent = String(s);
		return d.innerHTML;
	}

	function el(id) {
		return document.getElementById(id);
	}

	function val(id) {
		var n = el(id);
		return n ? String(n.value || "").trim() : "";
	}

	function setVal(id, v) {
		var n = el(id);
		if (n) n.value = v == null ? "" : String(v);
	}

	function money(n) {
		if (n == null || n === "") return "";
		var num = Number(n);
		if (isNaN(num)) return "";
		return num.toFixed(2);
	}

	function modal() {
		var node = el("usis-modal-wr");
		if (!node || !window.bootstrap || !window.bootstrap.Modal) return null;
		return window.bootstrap.Modal.getOrCreateInstance(node);
	}

	function setErr(msg) {
		var box = el("usis-wr-err");
		if (!box) return;
		box.textContent = msg || "";
		box.classList.toggle("d-none", !msg);
	}

	function payload() {
		return {
			year: val("usis-wr-edit-year") === "" ? null : Number(val("usis-wr-edit-year")),
			state: val("usis-wr-edit-state"),
			sub_area: val("usis-wr-edit-area"),
			trade: val("usis-wr-edit-trade"),
			basic_hourly_rate: val("usis-wr-edit-basic"),
			health_welfare: val("usis-wr-edit-hw"),
			pension: val("usis-wr-edit-pension"),
			vacation_holiday: val("usis-wr-edit-vacation"),
			other_payments: val("usis-wr-edit-other"),
			training: val("usis-wr-edit-training"),
			notes: val("usis-wr-edit-notes"),
			is_assumed: !!(el("usis-wr-edit-assumed") && el("usis-wr-edit-assumed").checked),
		};
	}

	function fillForm(row) {
		var form = el("usis-wr-form");
		if (form) form.reset();
		setVal("usis-wr-id", row && row.id ? row.id : "");
		setVal("usis-wr-edit-year", row && row.year != null ? row.year : new Date().getFullYear());
		setVal("usis-wr-edit-state", row ? row.state : "");
		setVal("usis-wr-edit-area", row ? row.sub_area : "");
		setVal("usis-wr-edit-trade", row ? row.trade : "");
		setVal("usis-wr-edit-basic", row && row.basic_hourly_rate != null ? row.basic_hourly_rate : "");
		setVal("usis-wr-edit-hw", row && row.health_welfare != null ? row.health_welfare : "");
		setVal("usis-wr-edit-pension", row && row.pension != null ? row.pension : "");
		setVal("usis-wr-edit-vacation", row && row.vacation_holiday != null ? row.vacation_holiday : "");
		setVal("usis-wr-edit-other", row && row.other_payments != null ? row.other_payments : "");
		setVal("usis-wr-edit-training", row && row.training != null ? row.training : "");
		setVal("usis-wr-edit-notes", row ? row.notes : "");
		var assumed = el("usis-wr-edit-assumed");
		if (assumed) assumed.checked = !!(row && row.is_assumed);
		var title = el("usis-modal-wr-title");
		if (title) title.textContent = row ? "Wage rate" : "Add wage rate";
		var saveNew = el("usis-wr-save-new");
		if (saveNew) saveNew.classList.toggle("d-none", !!row);
		setErr("");
	}

	function openForm(row) {
		fillForm(row || null);
		var m = modal();
		if (m) m.show();
		setTimeout(function () {
			var year = el("usis-wr-edit-year");
			if (year) year.focus();
		}, 200);
	}

	function queryParams() {
		var p = new URLSearchParams();
		p.set("limit", String(PAGE_SIZE));
		p.set("offset", String(offset));
		var q = val("usis-wr-q");
		if (q) p.set("q", q);
		var year = val("usis-wr-year");
		if (year) p.set("year", year);
		var state = val("usis-wr-state");
		if (state) p.set("state", state);
		var trade = val("usis-wr-trade");
		if (trade) p.set("trade", trade);
		return p;
	}

	function render() {
		var tbody = el("usis-wr-tbody");
		if (!tbody) return;
		if (!items.length) {
			tbody.innerHTML = '<tr><td colspan="8" class="text-muted">No wage rates match these filters.</td></tr>';
		} else {
			tbody.innerHTML = items
				.map(function (it) {
					var assumed = it.is_assumed ? ' <span class="badge text-bg-secondary">Assumed</span>' : "";
					return (
						'<tr class="usis-wr-row" data-id="' +
						esc(it.id) +
						'" style="cursor:pointer"><td>' +
						esc(it.year != null ? it.year : "") +
						"</td><td>" +
						esc(it.state || "") +
						"</td><td>" +
						esc(it.sub_area || "") +
						"</td><td>" +
						esc(it.trade || "") +
						assumed +
						'</td><td class="text-end">' +
						esc(money(it.basic_hourly_rate)) +
						'</td><td class="text-end">' +
						esc(money(it.total_loaded_hourly)) +
						"</td><td>" +
						esc(it.notes || "") +
						'</td><td class="text-end">' +
						(window.USISUi && window.USISUi.rowMenu
							? window.USISUi.rowMenu({
									id: it.id,
									editClass: "usis-wr-edit",
									deleteClass: "usis-wr-del",
									createTarget: "#usis-wr-add",
								})
							: '<button type="button" class="btn btn-link btn-sm p-0 usis-wr-del">Delete</button>') +
						"</td></tr>"
					);
				})
				.join("");
		}
		var status = el("usis-wr-status");
		if (status) {
			if (!total) status.textContent = "0 rates";
			else {
				var start = offset + 1;
				var end = Math.min(offset + items.length, total);
				status.textContent = start + "–" + end + " of " + total;
			}
		}
		var prev = el("usis-wr-prev");
		var next = el("usis-wr-next");
		if (prev) prev.disabled = offset <= 0;
		if (next) next.disabled = offset + items.length >= total;
	}

	function load() {
		return fetchJson("/api/v1/wage-rates?" + queryParams().toString())
			.then(function (data) {
				items = (data && data.items) || [];
				total = data && data.total != null ? Number(data.total) : items.length;
				render();
			})
			.catch(function () {
				items = [];
				total = 0;
				var tbody = el("usis-wr-tbody");
				if (tbody) tbody.innerHTML = '<tr><td colspan="8" class="text-muted">Could not load wage rates.</td></tr>';
				render();
			});
	}

	function fillSelect(id, values, current, blankLabel) {
		var node = el(id);
		if (!node) return;
		var selected = current == null ? val(id) : current;
		node.innerHTML =
			'<option value="">' +
			esc(blankLabel) +
			"</option>" +
			(values || [])
				.map(function (v) {
					return '<option value="' + esc(v) + '">' + esc(v) + "</option>";
				})
				.join("");
		if (selected) node.value = selected;
	}

	function loadFacets() {
		return fetchJson("/api/v1/wage-rates/facets")
			.then(function (data) {
				fillSelect("usis-wr-year", data && data.years, null, "All years");
				fillSelect("usis-wr-state", data && data.states, null, "All states");
				fillSelect("usis-wr-trade", data && data.trades, null, "All trades");
			})
			.catch(function () {});
	}

	function save() {
		var body = payload();
		if (!body.state || !body.trade || !body.year) {
			setErr("Year, state, and trade are required.");
			return Promise.reject(new Error("required"));
		}
		var id = val("usis-wr-id");
		return fetchJson("/api/v1/wage-rates" + (id ? "/" + encodeURIComponent(id) : ""), {
			method: id ? "PATCH" : "POST",
			body: body,
		})
			.then(function () {
				return Promise.all([loadFacets(), load()]);
			})
			.then(function () {
				if (keepOpen) {
					fillForm(null);
					var year = el("usis-wr-edit-year");
					if (year) year.focus();
				} else {
					var m = modal();
					if (m) m.hide();
				}
			})
			.catch(function (err) {
				var msg = "Could not save wage rate.";
				if (err && err.body) {
					try {
						var parsed = JSON.parse(err.body);
						msg = parsed.error || msg;
					} catch (e) {
						msg = String(err.body).slice(0, 240) || msg;
					}
				}
				setErr(msg);
				throw err;
			})
			.finally(function () {
				keepOpen = false;
			});
	}

	function importCsv(file) {
		if (!file) return Promise.resolve();
		return file
			.text()
			.then(function (text) {
				return fetchJson("/api/v1/wage-rates/import", { method: "POST", body: { csv: text } });
			})
			.then(function (result) {
				var created = result && result.created != null ? result.created : 0;
				var updated = result && result.updated != null ? result.updated : 0;
				window.alert("Imported " + created + " new and updated " + updated + " existing wage rates.");
				offset = 0;
				return Promise.all([loadFacets(), load()]);
			})
			.catch(function (err) {
				var msg = "Could not import wage rates.";
				if (err && err.body) {
					try {
						var parsed = JSON.parse(err.body);
						msg = parsed.error || msg;
					} catch (e) {
						msg = String(err.body).slice(0, 240) || msg;
					}
				}
				window.alert(msg);
			});
	}

	function onReady() {
		loadFacets().then(load);
		var add = el("usis-wr-add");
		if (add)
			add.addEventListener("click", function () {
				openForm(null);
			});
		var importBtn = el("usis-wr-import");
		var importFile = el("usis-wr-import-file");
		if (importBtn && importFile) {
			importBtn.addEventListener("click", function () {
				importFile.click();
			});
			importFile.addEventListener("change", function () {
				var file = importFile.files && importFile.files[0];
				importFile.value = "";
				importCsv(file);
			});
		}
		["usis-wr-q", "usis-wr-year", "usis-wr-state", "usis-wr-trade"].forEach(function (id) {
			var node = el(id);
			if (!node) return;
			node.addEventListener(id === "usis-wr-q" ? "input" : "change", function () {
				if (searchTimer) window.clearTimeout(searchTimer);
				searchTimer = window.setTimeout(function () {
					offset = 0;
					load();
				}, id === "usis-wr-q" ? 250 : 0);
			});
		});
		var prev = el("usis-wr-prev");
		if (prev)
			prev.addEventListener("click", function () {
				offset = Math.max(0, offset - PAGE_SIZE);
				load();
			});
		var next = el("usis-wr-next");
		if (next)
			next.addEventListener("click", function () {
				offset += PAGE_SIZE;
				load();
			});
		var form = el("usis-wr-form");
		if (form) {
			form.addEventListener("submit", function (e) {
				e.preventDefault();
				keepOpen = false;
				save();
			});
		}
		var saveNew = el("usis-wr-save-new");
		if (saveNew) {
			saveNew.addEventListener("click", function () {
				if (form && typeof form.reportValidity === "function" && !form.reportValidity()) return;
				keepOpen = true;
				save();
			});
		}
		var tbody = el("usis-wr-tbody");
		if (tbody) {
			tbody.addEventListener("click", function (e) {
				var del = e.target.closest(".usis-wr-del");
				var edit = e.target.closest(".usis-wr-edit");
				var tr = e.target.closest("tr[data-id]");
				if (del) {
					e.preventDefault();
					e.stopPropagation();
					if (!tr || !window.confirm("Delete this wage rate?")) return;
					fetchJson("/api/v1/wage-rates/" + encodeURIComponent(tr.getAttribute("data-id")), { method: "DELETE" })
						.then(function () {
							return Promise.all([loadFacets(), load()]);
						})
						.catch(function () {
							window.alert("Could not delete wage rate.");
						});
					return;
				}
				if (edit) {
					e.preventDefault();
					e.stopPropagation();
				}
				if (!tr) return;
				var found = null;
				items.forEach(function (it) {
					if (String(it.id) === String(tr.getAttribute("data-id"))) found = it;
				});
				if (found) openForm(found);
			});
		}
	}

	if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", onReady);
	else onReady();
})();
