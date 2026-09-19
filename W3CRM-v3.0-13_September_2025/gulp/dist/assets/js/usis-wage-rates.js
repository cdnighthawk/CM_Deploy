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
	var burden = {
		social_security_pct: 6.2,
		medicare_pct: 1.45,
		futa_pct: 0.6,
		suta_pct: 0,
		workers_comp_pct: 0,
		other_pct: 0,
	};
	var BURDEN_LINES = [
		{ key: "social_security_pct", label: "Social Security" },
		{ key: "medicare_pct", label: "Medicare" },
		{ key: "futa_pct", label: "Federal unemployment (FUTA)" },
		{ key: "suta_pct", label: "State unemployment" },
		{ key: "workers_comp_pct", label: "Workers' compensation" },
		{ key: "other_pct", label: "Other (GL, etc.)" },
	];

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

	function money4(n) {
		var num = Number(n);
		if (isNaN(num)) return "0.0000";
		return num.toFixed(4);
	}

	function numVal(raw) {
		var s = String(raw == null ? "" : raw).trim();
		if (s === "") return 0;
		var n = Number(s);
		return isNaN(n) ? 0 : n;
	}

	function round4(n) {
		return Math.round(Number(n) * 10000) / 10000;
	}

	function clampPct(n) {
		if (n < 0) return 0;
		if (n > 100) return 100;
		return round4(n);
	}

	function burdenFromForm() {
		return {
			social_security_pct: clampPct(numVal(val("usis-wr-ss"))),
			medicare_pct: clampPct(numVal(val("usis-wr-medicare"))),
			futa_pct: clampPct(numVal(val("usis-wr-futa"))),
			suta_pct: clampPct(numVal(val("usis-wr-suta"))),
			workers_comp_pct: clampPct(numVal(val("usis-wr-wc"))),
			other_pct: clampPct(numVal(val("usis-wr-other-burden"))),
		};
	}

	function fillBurdenForm(rates) {
		burden = rates || burden;
		setVal("usis-wr-ss", burden.social_security_pct);
		setVal("usis-wr-medicare", burden.medicare_pct);
		setVal("usis-wr-futa", burden.futa_pct);
		setVal("usis-wr-suta", burden.suta_pct);
		setVal("usis-wr-wc", burden.workers_comp_pct);
		setVal("usis-wr-other-burden", burden.other_pct);
	}

	function calcLoaded(row, rates) {
		var basic = numVal(row && row.basic_hourly_rate);
		var vacation = numVal(row && row.vacation_holiday);
		var taxable = round4(basic + vacation);
		var fringe = round4(
			basic +
				numVal(row && row.health_welfare) +
				numVal(row && row.pension) +
				vacation +
				numVal(row && row.other_payments) +
				numVal(row && row.training)
		);
		var wcOverride = row && row.workers_comp_pct != null && String(row.workers_comp_pct).trim() !== "";
		var lines = BURDEN_LINES.map(function (meta) {
			var pct = rates[meta.key];
			if (meta.key === "workers_comp_pct" && wcOverride) pct = clampPct(numVal(row.workers_comp_pct));
			var amount = round4((taxable * pct) / 100);
			return { key: meta.key, label: meta.label, pct: pct, amount: amount };
		});
		var burdenHourly = round4(
			lines.reduce(function (sum, line) {
				return sum + line.amount;
			}, 0)
		);
		return {
			taxable: taxable,
			fringe: fringe,
			burden: burdenHourly,
			loaded: round4(fringe + burdenHourly),
			lines: lines,
		};
	}

	function renderCalc() {
		var box = el("usis-wr-calc-body");
		if (!box) return;
		var rates = burdenFromForm();
		var row = payload();
		var out = calcLoaded(row, rates);
		if (!out.fringe && !out.taxable) {
			box.textContent = "Enter a basic wage to see taxes, unemployment, and workers' comp.";
			return;
		}
		var html =
			'<div class="d-flex justify-content-between"><span>DIR package (wage + fringes)</span><strong>$' +
			esc(money4(out.fringe)) +
			"</strong></div>" +
			'<div class="text-muted">Taxable wages (basic + vacation): $' +
			esc(money4(out.taxable)) +
			"</div>";
		out.lines.forEach(function (line) {
			html +=
				'<div class="d-flex justify-content-between"><span>' +
				esc(line.label) +
				" (" +
				esc(String(line.pct)) +
				'%)</span><span>$' +
				esc(money4(line.amount)) +
				"</span></div>";
		});
		html +=
			'<hr class="my-1"><div class="d-flex justify-content-between"><span>Fully loaded</span><strong>$' +
			esc(money4(out.loaded)) +
			" / hr</strong></div>";
		box.innerHTML = html;
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
			workers_comp_pct: val("usis-wr-edit-wc"),
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
		setVal("usis-wr-edit-wc", row && row.workers_comp_pct != null ? row.workers_comp_pct : "");
		setVal("usis-wr-edit-notes", row ? row.notes : "");
		var assumed = el("usis-wr-edit-assumed");
		if (assumed) assumed.checked = !!(row && row.is_assumed);
		var title = el("usis-modal-wr-title");
		if (title) title.textContent = row ? "Wage rate" : "Add wage rate";
		var saveNew = el("usis-wr-save-new");
		if (saveNew) saveNew.classList.toggle("d-none", !!row);
		setErr("");
		renderCalc();
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
				if (data && data.burden) fillBurdenForm(data.burden);
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

	function loadBurden() {
		return fetchJson("/api/v1/wage-rates/burden")
			.then(function (data) {
				if (data && data.burden) fillBurdenForm(data.burden);
			})
			.catch(function () {
				fillBurdenForm(burden);
			});
	}

	function setBurdenErr(msg) {
		var box = el("usis-wr-burden-err");
		if (!box) return;
		box.textContent = msg || "";
		box.classList.toggle("d-none", !msg);
	}

	function saveBurden() {
		var body = burdenFromForm();
		setBurdenErr("");
		return fetchJson("/api/v1/wage-rates/burden", { method: "PUT", body: body })
			.then(function (data) {
				if (data && data.burden) fillBurdenForm(data.burden);
				else fillBurdenForm(body);
				renderCalc();
				return load();
			})
			.catch(function (err) {
				var msg = "Could not save employer burden.";
				if (err && err.body) {
					try {
						var parsed = JSON.parse(err.body);
						msg = parsed.error || msg;
					} catch (e) {
						msg = String(err.body).slice(0, 240) || msg;
					}
				}
				setBurdenErr(msg);
			});
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
		loadBurden();
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
		var burdenSave = el("usis-wr-burden-save");
		if (burdenSave)
			burdenSave.addEventListener("click", function () {
				saveBurden();
			});
		[
			"usis-wr-ss",
			"usis-wr-medicare",
			"usis-wr-futa",
			"usis-wr-suta",
			"usis-wr-wc",
			"usis-wr-other-burden",
			"usis-wr-edit-basic",
			"usis-wr-edit-hw",
			"usis-wr-edit-pension",
			"usis-wr-edit-vacation",
			"usis-wr-edit-other",
			"usis-wr-edit-training",
			"usis-wr-edit-wc",
		].forEach(function (id) {
			var node = el(id);
			if (node) node.addEventListener("input", renderCalc);
		});
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
