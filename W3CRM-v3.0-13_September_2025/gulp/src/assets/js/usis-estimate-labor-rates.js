/**
 * Estimate detail — Labor rates tab: company wages plus housing, per diem, mandated OT.
 */
(function () {
	"use strict";

	var Api = typeof window.USISEstimateApi !== "undefined" ? window.USISEstimateApi : null;
	var estimateId = null;
	var payload = null;
	var saveTimer = null;
	var searchTimer = null;
	var expanded = {};

	function el(id) {
		return document.getElementById(id);
	}

	function notifyErr(msg) {
		if (window.USISNotify) window.USISNotify.error(String(msg));
		else window.alert(String(msg));
	}

	function notifyOk(msg) {
		if (window.USISNotify) window.USISNotify.success(String(msg));
	}

	function esc(s) {
		return String(s == null ? "" : s)
			.replace(/&/g, "&amp;")
			.replace(/</g, "&lt;")
			.replace(/>/g, "&gt;")
			.replace(/"/g, "&quot;");
	}

	function money4(n) {
		var num = Number(n);
		if (!isFinite(num)) return "—";
		return "$" + num.toFixed(4);
	}

	function setVal(id, v) {
		var n = el(id);
		if (n) n.value = v == null ? "" : String(v);
	}

	function numVal(id, fallback) {
		var n = el(id);
		if (!n) return fallback;
		var v = Number(n.value);
		return isFinite(v) ? v : fallback;
	}

	function strVal(id) {
		var n = el(id);
		return n ? String(n.value || "").trim() : "";
	}

	function settingsFromForm() {
		var ids = ((payload && payload.settings && payload.settings.wage_rate_ids) || []).slice();
		return {
			state: strVal("usis-est-labor-state"),
			year: numVal("usis-est-labor-year", new Date().getFullYear()),
			sub_area: strVal("usis-est-labor-area"),
			hours_per_day: numVal("usis-est-labor-hours", 8),
			days_per_week: numVal("usis-est-labor-days", 5),
			per_diem_per_day: numVal("usis-est-labor-perdiem", 0),
			housing_per_week: numVal("usis-est-labor-housing", 0),
			other_hourly: numVal("usis-est-labor-other", 0),
			wage_rate_ids: ids,
		};
	}

	function fillForm(item) {
		var s = (item && item.settings) || {};
		setVal("usis-est-labor-state", s.state || "");
		setVal("usis-est-labor-year", s.year || new Date().getFullYear());
		setVal("usis-est-labor-area", s.sub_area || "");
		setVal("usis-est-labor-hours", s.hours_per_day != null ? s.hours_per_day : 8);
		setVal("usis-est-labor-days", s.days_per_week != null ? s.days_per_week : 5);
		setVal("usis-est-labor-perdiem", s.per_diem_per_day != null ? s.per_diem_per_day : 0);
		setVal("usis-est-labor-housing", s.housing_per_week != null ? s.housing_per_week : 0);
		setVal("usis-est-labor-other", s.other_hourly != null ? s.other_hourly : 0);
	}

	function setLocked(locked) {
		["usis-est-labor-state", "usis-est-labor-year", "usis-est-labor-area", "usis-est-labor-hours", "usis-est-labor-days", "usis-est-labor-perdiem", "usis-est-labor-housing", "usis-est-labor-other", "usis-est-labor-trade-q", "usis-est-labor-trade-search", "usis-est-labor-save", "usis-est-labor-import"].forEach(function (id) {
			var n = el(id);
			if (n) n.disabled = !!locked;
		});
		var banner = el("usis-est-labor-lock");
		if (banner) banner.classList.toggle("d-none", !locked);
	}

	function showErr(msg) {
		var n = el("usis-est-labor-err");
		if (!n) return;
		if (!msg) {
			n.classList.add("d-none");
			n.textContent = "";
			return;
		}
		n.textContent = msg;
		n.classList.remove("d-none");
	}

	function updateScheduleNote(item) {
		var n = el("usis-est-labor-schedule");
		if (!n) return;
		var s = (item && item.schedule) || {};
		var hours = s.hours_per_day != null ? s.hours_per_day : 8;
		var days = s.days_per_week != null ? s.days_per_week : 5;
		var st = s.st_hours != null ? s.st_hours : 40;
		var ot = s.ot_hours != null ? s.ot_hours : 0;
		var dt = s.dt_hours != null ? s.dt_hours : 0;
		var note = hours + " hrs/day × " + days + " days = " + (s.clock_hours != null ? s.clock_hours : hours * days) + " clock hrs (" + st + " ST";
		if (ot) note += ", " + ot + " OT @ 1.5x";
		if (dt) note += ", " + dt + " DT @ 2x";
		note += "). Fringes stay straight time; OT premium is on base wage plus burden.";
		n.textContent = note;
	}

	function updateCostLibrary(item) {
		var out = el("usis-est-wage-out");
		if (!out) return;
		var trades = (item && item.trades) || [];
		if (!trades.length) {
			out.innerHTML = '<span class="text-muted">Import company trades on the Labor rates tab, then apply them to labor lines.</span>';
			return;
		}
		out.innerHTML = trades
			.map(function (row) {
				return (
					'<div class="d-flex justify-content-between align-items-start gap-2 border-bottom py-1">' +
					"<div><div>" +
					esc(row.trade || "Trade") +
					"</div><div class=\"text-muted\">" +
					esc(money4(row.project_loaded_hourly)) +
					"/hr project loaded</div></div>" +
					'<button type="button" class="btn btn-outline-primary btn-sm py-0 usis-est-wage-apply" data-id="' +
					esc(row.wage_rate_id) +
					'">Apply</button></div>'
				);
			})
			.join("");
	}

	function adderCell(amount) {
		var num = Number(amount);
		if (!isFinite(num) || num === 0) return '<span class="text-muted">—</span>';
		return esc(money4(num));
	}

	function breakdownHtml(row) {
		var company = row.company || {};
		var lines = company.burden_lines || [];
		var html = '<div class="small bg-light rounded p-2 mt-2">';
		html += "<div class=\"fw-medium mb-1\">Company package</div>";
		html += "<div>DIR package " + esc(money4(company.fringe_hourly)) + " + employer burden " + esc(money4(company.burden_hourly)) + "</div>";
		if (lines.length) {
			html += '<ul class="mb-1 mt-1 ps-3">';
			lines.forEach(function (line) {
				html +=
					"<li>" +
					esc(line.label) +
					" " +
					esc(String(line.pct)) +
					"% = " +
					esc(money4(line.amount)) +
					"</li>";
			});
			html += "</ul>";
		}
		html += "<div class=\"fw-medium mt-2 mb-1\">Job adders / hour</div><ul class=\"mb-0 ps-3\">";
		(row.adders || []).forEach(function (line) {
			html += "<li>" + esc(line.label) + " " + esc(money4(line.amount)) + "</li>";
		});
		html += "</ul></div>";
		return html;
	}

	function renderTrades(item) {
		var tbody = el("usis-est-labor-tbody");
		if (!tbody) return;
		var trades = (item && item.trades) || [];
		if (!trades.length) {
			tbody.innerHTML = '<tr><td colspan="9" class="text-muted">No trades yet. Search the company wage catalog and add one.</td></tr>';
			return;
		}
		tbody.innerHTML = trades
			.map(function (row, idx) {
				var id = row.wage_rate_id;
				var open = !!expanded[id];
				return (
					'<tr data-id="' +
					esc(id) +
					'">' +
					"<td>" +
					'<button type="button" class="btn btn-link btn-sm p-0 usis-est-labor-expand" aria-expanded="' +
					(open ? "true" : "false") +
					'">' +
					esc(row.trade || "—") +
					"</button>" +
					(row.sub_area ? '<div class="text-muted small">' + esc(row.sub_area) + "</div>" : "") +
					(open ? breakdownHtml(row) : "") +
					"</td>" +
					"<td>" +
					esc(row.state || "") +
					"</td>" +
					"<td>" +
					esc(row.year != null ? row.year : "") +
					"</td>" +
					'<td class="text-end text-nowrap">' +
					esc(money4(row.company_loaded_hourly)) +
					"</td>" +
					'<td class="text-end text-nowrap">' +
					adderCell(row.ot_hourly) +
					"</td>" +
					'<td class="text-end text-nowrap">' +
					adderCell(row.per_diem_hourly) +
					"</td>" +
					'<td class="text-end text-nowrap">' +
					adderCell(row.housing_hourly) +
					"</td>" +
					'<td class="text-end text-nowrap">' +
					adderCell(row.other_hourly) +
					"</td>" +
					'<td class="text-end text-nowrap">' +
					"<strong>" +
					esc(money4(row.project_loaded_hourly)) +
					"</strong>" +
					'<div class="mt-1 d-flex flex-wrap gap-1 justify-content-end">' +
					'<button type="button" class="btn btn-outline-secondary btn-sm py-0 usis-est-labor-copy" data-rate="' +
					esc(row.project_loaded_hourly) +
					'">Copy</button>' +
					'<button type="button" class="btn btn-outline-danger btn-sm py-0 usis-est-labor-remove" data-id="' +
					esc(id) +
					'"' +
					(item.locked ? " disabled" : "") +
					">Remove</button>" +
					"</div></td></tr>"
				);
			})
			.join("");
	}

	function render(item) {
		payload = item || payload;
		if (!payload) return;
		fillForm(payload);
		setLocked(!!payload.locked);
		updateScheduleNote(payload);
		renderTrades(payload);
		updateCostLibrary(payload);
		document.dispatchEvent(new CustomEvent("usis-labor-rates-updated", { detail: { item: payload } }));
	}

	function fetchItem() {
		if (!estimateId || !Api) return Promise.resolve(null);
		return Api.getLaborRates(estimateId).then(function (data) {
			return data && data.item ? data.item : null;
		});
	}

	function save(opts) {
		if (!estimateId || !Api) return Promise.resolve();
		if (payload && payload.locked) return Promise.resolve();
		var body = settingsFromForm();
		return Api.putLaborRates(estimateId, body)
			.then(function (data) {
				payload = data && data.item ? data.item : payload;
				render(payload);
				if (opts && opts.flash) notifyOk("Labor rates saved.");
				showErr("");
				return payload;
			})
			.catch(function (err) {
				var msg = (err && err.message) || "Could not save labor rates.";
				showErr(msg);
				if (opts && opts.flash) notifyErr(msg);
			});
	}

	function importCompany() {
		if (!estimateId || !Api) return;
		if (payload && payload.locked) return;
		var body = settingsFromForm();
		var run = Api.importCompanyLaborRates
			? Api.importCompanyLaborRates(estimateId, body)
			: Api.fetchJson("/api/v1/estimates/" + encodeURIComponent(estimateId) + "/labor-rates/import-company", {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify(body),
			});
		run.then(function (data) {
			payload = data && data.item ? data.item : payload;
			render(payload);
			var n = payload && payload.imported_count != null ? payload.imported_count : 0;
			var extra = payload && payload.truncated ? " (stopped at 200 trades)" : "";
			notifyOk(n ? "Imported " + n + " company trade" + (n === 1 ? "" : "s") + extra + "." : "No new company trades matched this state/year.");
			showErr("");
			searchTrades();
		}).catch(function (err) {
			var msg = (err && err.message) || "Could not import company trades.";
			showErr(msg);
			notifyErr(msg);
		});
	}

	function scheduleSave() {
		if (saveTimer) window.clearTimeout(saveTimer);
		saveTimer = window.setTimeout(function () {
			save({});
		}, 400);
	}

	function copyRate(rate) {
		var text = String(rate);
		var done = function () {
			notifyOk("Copied " + money4(rate) + "/hr");
		};
		if (navigator.clipboard && navigator.clipboard.writeText) {
			navigator.clipboard.writeText(text).then(done).catch(function () {
				window.prompt("Copy project loaded hourly", text);
			});
			return;
		}
		window.prompt("Copy project loaded hourly", text);
	}

	function searchTrades() {
		if (!Api) return;
		var out = el("usis-est-labor-trade-results");
		if (!out) return;
		var q = strVal("usis-est-labor-trade-q");
		var state = strVal("usis-est-labor-state");
		var year = strVal("usis-est-labor-year");
		var params = new URLSearchParams();
		params.set("limit", "20");
		if (q) params.set("q", q);
		if (state) params.set("state", state);
		if (year) params.set("year", year);
		out.innerHTML = '<div class="text-muted">Searching…</div>';
		Api.fetchJson("/api/v1/wage-rates?" + params.toString())
			.then(function (data) {
				var items = (data && data.items) || [];
				var have = {};
				((payload && payload.settings && payload.settings.wage_rate_ids) || []).forEach(function (id) {
					have[id] = true;
				});
				if (!items.length) {
					out.innerHTML = '<div class="text-muted">No company wage rates match.</div>';
					return;
				}
				out.innerHTML = items
					.map(function (row) {
						var added = have[row.id];
						return (
							'<div class="d-flex justify-content-between align-items-center gap-2 border-bottom py-1">' +
							"<div><div>" +
							esc(row.trade) +
							"</div><div class=\"text-muted\">" +
							esc(row.state) +
							(row.sub_area ? " · " + esc(row.sub_area) : "") +
							" · " +
							esc(row.year) +
							" · company " +
							esc(money4(row.total_loaded_hourly)) +
							"</div></div>" +
							'<button type="button" class="btn btn-outline-primary btn-sm usis-est-labor-add" data-id="' +
							esc(row.id) +
							'"' +
							(added || (payload && payload.locked) ? " disabled" : "") +
							">" +
							(added ? "Added" : "Add") +
							"</button></div>"
						);
					})
					.join("");
			})
			.catch(function () {
				out.innerHTML = '<div class="text-muted">Could not search wage rates.</div>';
			});
	}

	function addTrade(id) {
		if (!payload || payload.locked) return;
		payload.settings = payload.settings || {};
		payload.settings.wage_rate_ids = payload.settings.wage_rate_ids || [];
		if (payload.settings.wage_rate_ids.indexOf(id) >= 0) return;
		payload.settings.wage_rate_ids.push(id);
		save({ flash: false }).then(function () {
			searchTrades();
		});
	}

	function removeTrade(id) {
		if (!payload || payload.locked) return;
		payload.settings = payload.settings || {};
		payload.settings.wage_rate_ids = (payload.settings.wage_rate_ids || []).filter(function (x) {
			return x !== id;
		});
		save({ flash: false });
	}

	function showTab() {
		var btn = el("estd-tab-labor-rates");
		if (!btn) return;
		if (window.bootstrap && window.bootstrap.Tab) {
			window.bootstrap.Tab.getOrCreateInstance(btn).show();
			return;
		}
		btn.click();
	}

	function applyLoaded(item, extra) {
		var noEst = el("usis-est-labor-no-est");
		var root = el("usis-est-labor-root");
		if (extra && extra.missingEstimate) {
			estimateId = null;
			payload = null;
			if (noEst) noEst.classList.remove("d-none");
			if (root) root.classList.add("d-none");
			updateCostLibrary(null);
			return;
		}
		if (!item || !item.id) return;
		estimateId = item.id;
		if (noEst) noEst.classList.add("d-none");
		if (root) root.classList.remove("d-none");
		if (item.labor_rates && item.labor_rates.settings) {
			render(item.labor_rates);
			return;
		}
		fetchItem()
			.then(function (next) {
				if (next) render(next);
			})
			.catch(function (err) {
				showErr((err && err.message) || "Could not load labor rates.");
			});
	}

	function bind() {
		var saveBtn = el("usis-est-labor-save");
		if (saveBtn) saveBtn.addEventListener("click", function () {
			save({ flash: true });
		});
		var importBtn = el("usis-est-labor-import");
		if (importBtn) importBtn.addEventListener("click", importCompany);
		["usis-est-labor-state", "usis-est-labor-year", "usis-est-labor-area", "usis-est-labor-hours", "usis-est-labor-days", "usis-est-labor-perdiem", "usis-est-labor-housing", "usis-est-labor-other"].forEach(function (id) {
			var n = el(id);
			if (!n) return;
			n.addEventListener("change", scheduleSave);
			n.addEventListener("blur", scheduleSave);
		});
		var searchBtn = el("usis-est-labor-trade-search");
		if (searchBtn) searchBtn.addEventListener("click", searchTrades);
		var q = el("usis-est-labor-trade-q");
		if (q) {
			q.addEventListener("keydown", function (e) {
				if (e.key === "Enter") {
					e.preventDefault();
					searchTrades();
				}
			});
			q.addEventListener("input", function () {
				if (searchTimer) window.clearTimeout(searchTimer);
				searchTimer = window.setTimeout(searchTrades, 300);
			});
		}
		var results = el("usis-est-labor-trade-results");
		if (results) {
			results.addEventListener("click", function (e) {
				var add = e.target.closest(".usis-est-labor-add");
				if (!add) return;
				addTrade(add.getAttribute("data-id"));
			});
		}
		var tbody = el("usis-est-labor-tbody");
		if (tbody) {
			tbody.addEventListener("click", function (e) {
				var copy = e.target.closest(".usis-est-labor-copy");
				if (copy) {
					copyRate(copy.getAttribute("data-rate"));
					return;
				}
				var remove = e.target.closest(".usis-est-labor-remove");
				if (remove) {
					removeTrade(remove.getAttribute("data-id"));
					return;
				}
				var expand = e.target.closest(".usis-est-labor-expand");
				if (expand) {
					var tr = expand.closest("tr");
					var id = tr && tr.getAttribute("data-id");
					if (!id) return;
					expanded[id] = !expanded[id];
					renderTrades(payload);
				}
			});
		}
		var openBtn = el("usis-est-wage-open");
		if (openBtn) openBtn.addEventListener("click", showTab);
		var wageOut = el("usis-est-wage-out");
		if (wageOut) {
			wageOut.addEventListener("click", function (e) {
				var apply = e.target.closest(".usis-est-wage-apply");
				if (!apply) return;
				document.dispatchEvent(
					new CustomEvent("usis-apply-labor-rate", { detail: { wage_rate_id: apply.getAttribute("data-id") } })
				);
			});
		}
		document.addEventListener("usis-estimate-loaded", function (ev) {
			var detail = (ev && ev.detail) || {};
			applyLoaded(detail.item, detail);
		});
	}

	if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", bind);
	else bind();
})();
