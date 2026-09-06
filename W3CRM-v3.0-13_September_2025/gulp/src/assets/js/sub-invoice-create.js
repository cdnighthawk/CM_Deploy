/**
 * Subcontractor invoice create / detail.
 * Invoice FROM a subcontractor TO USIS — not a GC G702 pay app, not a PO bill.
 * GET/POST /api/v1/projects/<id>/wave2/sub-invoices
 * GET/PATCH /api/v1/projects/<id>/wave2/sub-invoices/<id>
 */
(function () {
	"use strict";

	var STATUSES = ["draft", "received", "approved", "rejected", "paid"];

	var state = {
		projectId: null,
		recordId: null,
		subs: [],
		sovLines: [],
		sovMode: false,
		previousToDate: 0,
		serverTotals: null,
		lastAutoSubject: "",
		retainageTouched: false,
		busy: false,
	};

	function $(id) {
		return document.getElementById(id);
	}

	function t(key) {
		return window.USISI18n && typeof window.USISI18n.tr === "function" ? window.USISI18n.tr(key) : key;
	}

	function fetchJson(path, opts) {
		if (window.USIS_API && typeof window.USIS_API.fetchJson === "function") {
			return window.USIS_API.fetchJson(path, opts || {});
		}
		return fetch(path, Object.assign({ credentials: "include", headers: { Accept: "application/json" } }, opts || {})).then(
			function (res) {
				return res.json().then(function (j) {
					if (!res.ok) throw new Error(j.error || res.statusText || String(res.status));
					return j;
				});
			}
		);
	}

	function queryParam(name) {
		try {
			return new URLSearchParams(window.location.search).get(name) || "";
		} catch (e) {
			return "";
		}
	}

	function esc(s) {
		if (s == null || s === "") return "";
		var d = document.createElement("div");
		d.textContent = String(s);
		return d.innerHTML;
	}

	function money(n) {
		var x = Number(n);
		if (isNaN(x)) return "$0.00";
		return x.toLocaleString(undefined, { style: "currency", currency: "USD" });
	}

	function toNum(v) {
		var n = parseFloat(String(v == null ? "" : v).replace(/,/g, ""));
		return isNaN(n) ? 0 : n;
	}

	function round2(n) {
		return Math.round((Number(n) + Number.EPSILON) * 100) / 100;
	}

	function numEl(el) {
		return toNum(el && el.value);
	}

	function errMessage(err) {
		if (!err) return "Could not save.";
		var body = err.body;
		if (typeof body === "string") {
			try {
				body = JSON.parse(body);
			} catch (e) {}
		}
		if (body && typeof body === "object") return body.error || body.message || err.message || "Could not save.";
		return err.message || "Could not save.";
	}

	function flashError(msg) {
		var el = $("usis-sinv-error");
		if (!el) return;
		if (!msg) {
			el.classList.add("d-none");
			el.textContent = "";
			return;
		}
		el.classList.remove("d-none");
		el.textContent = String(msg);
		try {
			el.scrollIntoView({ behavior: "smooth", block: "center" });
		} catch (e) {}
	}

	function currentProjectId() {
		var fromQuery = queryParam("project_id") || queryParam("projectId");
		if (fromQuery) return fromQuery.trim();
		if (window.USISProjectContext && typeof window.USISProjectContext.getProjectId === "function") {
			var fromCtx = window.USISProjectContext.getProjectId();
			if (fromCtx) return String(fromCtx).trim();
		}
		try {
			return (window.sessionStorage.getItem("usis.activeProjectId") || "").trim();
		} catch (e) {
			return "";
		}
	}

	function rememberProject(projectId) {
		if (!projectId) return;
		if (window.USISProjectContext && typeof window.USISProjectContext.setProjectId === "function") {
			window.USISProjectContext.setProjectId(projectId);
		}
	}

	function projectReturnHref() {
		if (!state.projectId) return "construction/project-detail.html";
		return "construction/project-detail.html?id=" + encodeURIComponent(state.projectId) + "&tab=subinv";
	}

	function procurementHref() {
		if (!state.projectId) return "construction/project-detail.html";
		return "construction/project-detail.html?id=" + encodeURIComponent(state.projectId) + "&tab=procurement";
	}

	function stampCancelLinks() {
		["usis-sinv-cancel", "usis-sinv-crumb-list"].forEach(function (id) {
			var a = $(id);
			if (a) a.setAttribute("href", projectReturnHref());
		});
		var subLink = $("usis-sinv-create-sub");
		if (subLink) subLink.setAttribute("href", procurementHref());
	}

	function setTitles(text) {
		var title = text || t("New Subcontractor Invoice");
		var h1 = $("usis-sinv-page-title");
		var crumb = $("usis-sinv-crumb-current");
		if (h1) h1.textContent = title;
		if (crumb) crumb.textContent = title;
		if (document.title) document.title = title + " · USIS";
	}

	function selectedSub() {
		var id = (($("usis-sinv-commitment") || {}).value || "").trim();
		if (!id) return null;
		return (
			state.subs.find(function (c) {
				return String(c.id) === String(id);
			}) || null
		);
	}

	function subLabel(c) {
		if (!c) return "";
		var ref = (c.reference_number || "").trim();
		var vendor = (c.vendor_name || "").trim();
		if (ref && vendor) return ref + " — " + vendor;
		return ref || vendor || "Subcontract";
	}

	function defaultSubject() {
		var num = (($("usis-sinv-number") || {}).value || "").trim();
		if (num) return "Invoice " + num;
		var sub = selectedSub();
		var vendor = sub ? (sub.vendor_name || "").trim() : "";
		var start = (($("usis-sinv-period-start") || {}).value || "").trim();
		var end = (($("usis-sinv-period-end") || {}).value || "").trim();
		var period = start && end ? start + " – " + end : start || end || "";
		if (vendor && period) return vendor + " — " + period;
		if (vendor) return "Invoice — " + vendor;
		if (period) return "Invoice " + period;
		return "Invoice";
	}

	function maybeAutofillSubject() {
		var el = $("usis-sinv-subject");
		if (!el) return;
		var cur = (el.value || "").trim();
		if (cur && cur !== state.lastAutoSubject) return;
		var next = defaultSubject();
		el.value = next;
		state.lastAutoSubject = next;
	}

	function defaultRetainagePct(sub) {
		if (sub && sub.retention_percentage != null && sub.retention_percentage !== "") {
			var n = toNum(sub.retention_percentage);
			if (!isNaN(n)) return n;
		}
		return 5;
	}

	function applyRetainageDefault(sub) {
		var el = $("usis-sinv-retainage-pct");
		if (!el || state.retainageTouched) return;
		el.value = String(defaultRetainagePct(sub));
	}

	function collectLines() {
		var tbody = $("usis-sinv-lines-tbody");
		if (!tbody) return [];
		return Array.prototype.map.call(tbody.querySelectorAll("tr[data-line]"), function (tr) {
			var desc = ((tr.querySelector("[data-line-desc]") || {}).value || "").trim();
			var amt = numEl(tr.querySelector("[data-line-amt]"));
			var sov = ((tr.querySelector("[data-sov-line-id]") || {}).value || "").trim();
			var row = { description: desc, this_period: round2(amt) };
			if (sov) row.sov_line_id = sov;
			return row;
		});
	}

	function formMath() {
		var lines = collectLines();
		var thisPeriod = round2(
			lines.reduce(function (sum, row) {
				return sum + toNum(row.this_period);
			}, 0)
		);
		var pct = numEl($("usis-sinv-retainage-pct"));
		var retainage = round2((thisPeriod * pct) / 100);
		var previous = round2(state.previousToDate);
		return {
			this_period: thisPeriod,
			previous_to_date: previous,
			retainage: retainage,
			amount_due: round2(thisPeriod - retainage),
		};
	}

	function refreshTotals() {
		var math = formMath();
		var thisEl = $("usis-sinv-this-period");
		var prevEl = $("usis-sinv-previous");
		var retEl = $("usis-sinv-retainage");
		var dueEl = $("usis-sinv-amount-due");
		if (thisEl) thisEl.textContent = money(math.this_period);
		if (prevEl) prevEl.textContent = money(math.previous_to_date);
		if (retEl) retEl.textContent = money(math.retainage);
		if (dueEl) dueEl.textContent = money(math.amount_due);
		var tbody = $("usis-sinv-lines-tbody");
		if (tbody) {
			Array.prototype.forEach.call(tbody.querySelectorAll("tr[data-line]"), function (tr, i) {
				var idx = tr.querySelector("[data-line-idx]");
				if (idx) idx.textContent = String(i + 1);
			});
		}
		return math;
	}

	function showServerTotals(item) {
		var el = $("usis-sinv-server-totals");
		if (!el) return;
		if (!item) {
			el.classList.add("d-none");
			el.textContent = "";
			state.serverTotals = null;
			return;
		}
		state.serverTotals = {
			this_period: item.this_period,
			previous_to_date: item.previous_to_date,
			retainage: item.retainage,
			amount_due: item.amount_due,
		};
		el.textContent =
			t("Saved from server") +
			": " +
			t("this period") +
			" " +
			money(item.this_period) +
			" · " +
			t("previous-to-date") +
			" " +
			money(item.previous_to_date) +
			" · " +
			t("retainage") +
			" " +
			money(item.retainage) +
			" · " +
			t("amount due") +
			" " +
			money(item.amount_due);
		el.classList.remove("d-none");
	}

	function setLinesHint(text) {
		var el = $("usis-sinv-lines-hint");
		if (el) el.textContent = text;
	}

	function addLineRow(item) {
		var tbody = $("usis-sinv-lines-tbody");
		if (!tbody) return;
		item = item || {};
		var locked = !!item.sov_line_id;
		var tr = document.createElement("tr");
		tr.setAttribute("data-line", "1");
		var descVal = item.description || "";
		var amtVal = item.this_period != null && item.this_period !== "" ? item.this_period : "0";
		tr.innerHTML =
			'<td class="text-muted" data-line-idx></td>' +
			'<td><input type="text" class="form-control form-control-sm" data-line-desc maxlength="500" value="' +
			esc(descVal) +
			'"' +
			(locked ? " readonly" : "") +
			">" +
			'<input type="hidden" data-sov-line-id value="' +
			esc(item.sov_line_id || "") +
			'"></td>' +
			'<td><input type="number" class="form-control form-control-sm text-end" data-line-amt step="0.01" value="' +
			esc(amtVal) +
			'"></td>';
		tbody.appendChild(tr);
		return tr;
	}

	function renderLines(sovItems, savedLines) {
		var tbody = $("usis-sinv-lines-tbody");
		if (!tbody) return;
		tbody.innerHTML = "";
		state.sovLines = sovItems || [];
		state.sovMode = state.sovLines.length > 0;
		var saved = savedLines || [];
		if (state.sovMode) {
			setLinesHint(t("One invoice line per subcontract SOV row. Enter this-period amounts only — this is not an SOV editor."));
			state.sovLines.forEach(function (sov) {
				var match = saved.find(function (row) {
					return row && String(row.sov_line_id || "") === String(sov.id);
				});
				addLineRow({
					description: (match && match.description) || sov.description || "",
					this_period: match && match.this_period != null ? match.this_period : 0,
					sov_line_id: sov.id,
				});
			});
		} else if (saved.length) {
			setLinesHint(t("This subcontract has no SOV. Enter a lump description and this-period amount."));
			saved.forEach(function (row) {
				addLineRow(row);
			});
		} else {
			setLinesHint(t("This subcontract has no SOV. Enter a lump description and this-period amount."));
			addLineRow({ description: "Invoice", this_period: 0 });
		}
		refreshTotals();
	}

	function clearLinesPending() {
		var tbody = $("usis-sinv-lines-tbody");
		if (tbody) tbody.innerHTML = "";
		state.sovLines = [];
		state.sovMode = false;
		state.previousToDate = 0;
		setLinesHint(t("Select a subcontract to load SOV rows, or enter a lump this-period amount if the subcontract has no SOV."));
		refreshTotals();
	}

	function showEmptySubs(empty) {
		var emptyEl = $("usis-sinv-empty-subs");
		var sel = $("usis-sinv-commitment");
		if (emptyEl) emptyEl.classList.toggle("d-none", !empty);
		if (sel) sel.classList.toggle("d-none", !!empty);
	}

	function fillSubSelect(selected) {
		var sel = $("usis-sinv-commitment");
		if (!sel) return;
		sel.innerHTML = "";
		var blank = document.createElement("option");
		blank.value = "";
		blank.textContent = t("Select a subcontract");
		sel.appendChild(blank);
		state.subs.forEach(function (c) {
			var opt = document.createElement("option");
			opt.value = c.id;
			opt.textContent = subLabel(c);
			sel.appendChild(opt);
		});
		if (selected) {
			sel.value = selected;
			if (sel.value !== String(selected)) {
				var extra = document.createElement("option");
				extra.value = selected;
				extra.textContent = t("Subcontract");
				sel.appendChild(extra);
				sel.value = selected;
			}
		}
		showEmptySubs(!state.subs.length && !selected);
	}

	function loadSubcontracts(selected) {
		if (!state.projectId) return Promise.resolve([]);
		return fetchJson("/api/v1/projects/" + encodeURIComponent(state.projectId) + "/commitments").then(function (data) {
			state.subs = (data.items || []).filter(function (c) {
				return (c.commitment_kind || "") === "subcontract";
			});
			fillSubSelect(selected || "");
			return state.subs;
		});
	}

	function previewPreviousToDate(commitmentId) {
		state.previousToDate = 0;
		if (!state.projectId || !commitmentId) {
			refreshTotals();
			return Promise.resolve(0);
		}
		return fetchJson("/api/v1/projects/" + encodeURIComponent(state.projectId) + "/wave2/sub-invoices")
			.then(function (data) {
				var sum = 0;
				(data.items || []).forEach(function (it) {
					if (String(it.commitment_id || "") !== String(commitmentId)) return;
					if (state.recordId && String(it.id) === String(state.recordId)) return;
					var st = String(it.status || "").toLowerCase();
					if (st !== "approved" && st !== "paid") return;
					sum += toNum(it.this_period != null ? it.this_period : it.amount);
				});
				state.previousToDate = round2(sum);
				refreshTotals();
				return state.previousToDate;
			})
			.catch(function () {
				state.previousToDate = 0;
				refreshTotals();
				return 0;
			});
	}

	function loadSovLines(commitmentId, savedLines) {
		state.sovLines = [];
		if (!state.projectId || !commitmentId) {
			clearLinesPending();
			return Promise.resolve([]);
		}
		return fetchJson(
			"/api/v1/projects/" +
				encodeURIComponent(state.projectId) +
				"/commitments/" +
				encodeURIComponent(commitmentId) +
				"/line-items"
		)
			.then(function (data) {
				renderLines(data.items || [], savedLines);
				return state.sovLines;
			})
			.catch(function () {
				renderLines([], savedLines);
				return [];
			});
	}

	function onSubcontractChange(savedLines) {
		var sub = selectedSub();
		applyRetainageDefault(sub);
		maybeAutofillSubject();
		var id = (($("usis-sinv-commitment") || {}).value || "").trim();
		if (!id) {
			clearLinesPending();
			return Promise.resolve();
		}
		return Promise.all([loadSovLines(id, savedLines || []), previewPreviousToDate(id)]);
	}

	function buildPayload() {
		maybeAutofillSubject();
		var payload = {
			subject: (($("usis-sinv-subject") || {}).value || "").trim() || defaultSubject(),
			commitment_id: (($("usis-sinv-commitment") || {}).value || "").trim(),
			status: (($("usis-sinv-status") || {}).value || "draft").trim() || "draft",
			period_start: (($("usis-sinv-period-start") || {}).value || "").trim() || null,
			period_end: (($("usis-sinv-period-end") || {}).value || "").trim() || null,
			retainage_pct: numEl($("usis-sinv-retainage-pct")),
			lines: collectLines(),
		};
		var number = (($("usis-sinv-number") || {}).value || "").trim();
		payload.number = number || null;
		return payload;
	}

	function validate(payload) {
		if (!state.projectId) return t("Choose a project.");
		if (!payload.commitment_id) return t("Select a parent subcontract.");
		if (!payload.period_start) return t("Period start is required.");
		if (!payload.period_end) return t("Period end is required.");
		if (payload.period_start && payload.period_end && payload.period_start > payload.period_end) {
			return t("Period end must be on or after period start.");
		}
		if (STATUSES.indexOf(payload.status) === -1) return t("Status is required.");
		if (!payload.subject) return t("Subject is required.");
		if (!payload.lines.length) return t("Add at least one invoice line.");
		if (!state.sovMode) {
			var missing = payload.lines.some(function (row) {
				return !row.description;
			});
			if (missing) return t("Description is required for the lump invoice line.");
		}
		return "";
	}

	function setBusy(on) {
		state.busy = !!on;
		var btn = $("usis-sinv-save");
		if (btn) btn.disabled = !!on;
	}

	function fillHeader(item) {
		item = item || {};
		var number = $("usis-sinv-number");
		if (number) number.value = item.number || "";
		var status = $("usis-sinv-status");
		if (status) status.value = item.status || "draft";
		var start = $("usis-sinv-period-start");
		if (start) start.value = item.period_start ? String(item.period_start).slice(0, 10) : "";
		var end = $("usis-sinv-period-end");
		if (end) end.value = item.period_end ? String(item.period_end).slice(0, 10) : "";
		var subject = $("usis-sinv-subject");
		if (subject) {
			subject.value = item.subject || "";
			state.lastAutoSubject = "";
		}
		var pct = $("usis-sinv-retainage-pct");
		if (pct) {
			if (item.retainage_pct != null && item.retainage_pct !== "") {
				pct.value = String(item.retainage_pct);
				state.retainageTouched = true;
			} else {
				applyRetainageDefault(selectedSub());
			}
		}
		if (item.previous_to_date != null && item.previous_to_date !== "") {
			state.previousToDate = toNum(item.previous_to_date);
		}
		setTitles(item.number || item.subject || t("Subcontractor Invoice"));
		showServerTotals(item);
		refreshTotals();
	}

	function save(ev) {
		if (ev) ev.preventDefault();
		if (state.busy) return;
		flashError("");
		var payload = buildPayload();
		var err = validate(payload);
		if (err) {
			flashError(err);
			return;
		}
		var path = "/api/v1/projects/" + encodeURIComponent(state.projectId) + "/wave2/sub-invoices";
		var method = "POST";
		if (state.recordId) {
			path += "/" + encodeURIComponent(state.recordId);
			method = "PATCH";
		}
		setBusy(true);
		fetchJson(path, { method: method, body: payload })
			.then(function () {
				if (window.USISNotify && window.USISNotify.success) {
					window.USISNotify.success(state.recordId ? "Subcontractor invoice saved." : "Subcontractor invoice created.");
				}
				window.location.href = projectReturnHref();
			})
			.catch(function (e) {
				flashError(errMessage(e));
				if (window.USISNotify && window.USISNotify.error) {
					window.USISNotify.error(errMessage(e));
				}
				setBusy(false);
			});
	}

	function wire() {
		var form = $("usis-sinv-form");
		if (form) form.addEventListener("submit", save);
		var tbody = $("usis-sinv-lines-tbody");
		if (tbody) tbody.addEventListener("input", refreshTotals);
		var pct = $("usis-sinv-retainage-pct");
		if (pct) {
			pct.addEventListener("input", function () {
				state.retainageTouched = true;
				refreshTotals();
			});
		}
		["usis-sinv-number", "usis-sinv-period-start", "usis-sinv-period-end"].forEach(function (id) {
			var el = $(id);
			if (el) el.addEventListener("input", maybeAutofillSubject);
			if (el) el.addEventListener("change", maybeAutofillSubject);
		});
		var subSel = $("usis-sinv-commitment");
		if (subSel) {
			subSel.addEventListener("change", function () {
				onSubcontractChange([]);
			});
		}
	}

	function loadRecord() {
		if (!state.recordId) {
			clearLinesPending();
			return Promise.resolve();
		}
		return fetchJson(
			"/api/v1/projects/" + encodeURIComponent(state.projectId) + "/wave2/sub-invoices/" + encodeURIComponent(state.recordId)
		).then(function (data) {
			var item = data.item || {};
			return loadSubcontracts(item.commitment_id).then(function () {
				var sel = $("usis-sinv-commitment");
				if (sel && item.commitment_id) sel.value = item.commitment_id;
				fillHeader(item);
				var saved = item.lines && item.lines.length ? item.lines : [];
				var sov = item.sov && item.sov.length ? item.sov : null;
				return loadSovLines(item.commitment_id, saved).then(function () {
					if (state.sovLines.length === 0 && sov && sov.length) {
						renderLines(sov, saved);
					}
					if (item.previous_to_date != null && item.previous_to_date !== "") {
						state.previousToDate = toNum(item.previous_to_date);
					}
					refreshTotals();
				});
			});
		});
	}

	function init() {
		state.projectId = currentProjectId();
		state.recordId = (queryParam("id") || queryParam("sinv_id") || "").trim() || null;
		if (state.projectId) rememberProject(state.projectId);
		stampCancelLinks();
		wire();
		if (!state.projectId) {
			flashError(t("Choose a project."));
			showEmptySubs(false);
			clearLinesPending();
			return;
		}
		var start = state.recordId
			? loadRecord()
			: loadSubcontracts("").then(function () {
					return loadRecord();
				});
		start.catch(function (e) {
			flashError(errMessage(e));
		});
	}

	if (document.readyState === "loading") {
		document.addEventListener("DOMContentLoaded", init);
	} else {
		init();
	}
})();
