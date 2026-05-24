/**
 * Project detail — Invoicing tab: pay applications (G702 summary + SOV lines).
 * GET/POST/PATCH/DELETE `/api/v1/projects/<id>/pay-applications`.
 */
(function () {
	"use strict";

	var projectId = null;
	var currentPayAppId = null;
	var currentItemStatus = "draft";

	function fetchJson(method, path, body) {
		var opts = { method: method || "GET" };
		if (body !== undefined && body !== null) opts.body = body;
		return window.USIS_API.fetchJson(path, opts);
	}

	function projectIdFromQuery() {
		var id = new URLSearchParams(window.location.search).get("id");
		return id && id.trim() ? id.trim() : null;
	}

	function toastErr(msg) {
		if (window.USISNotify && window.USISNotify.error) window.USISNotify.error(msg);
	}

	function toastOk(msg) {
		if (window.USISNotify && window.USISNotify.success) window.USISNotify.success(msg);
	}

	function setRegisterErr(msg) {
		var el = document.getElementById("usis-inv-register-error");
		if (!el) return;
		if (msg) {
			el.textContent = msg;
			el.classList.remove("d-none");
		} else {
			el.textContent = "";
			el.classList.add("d-none");
		}
	}

	function moneyOrEmpty(v) {
		if (v == null || v === "") return "";
		return String(v);
	}

	function setTexturaSyncStatus(msg, isError) {
		var el = document.getElementById("usis-inv-textura-sync-status");
		if (!el) return;
		if (!msg) {
			el.textContent = "";
			el.classList.add("d-none");
			el.classList.remove("text-danger");
			return;
		}
		el.textContent = msg;
		el.classList.remove("d-none");
		el.classList.toggle("text-danger", !!isError);
	}

	function syncFromTextura() {
		if (!projectId) return;
		var btn = document.getElementById("usis-inv-textura-sync");
		if (btn) btn.disabled = true;
		setTexturaSyncStatus("Syncing…", false);
		return fetchJson(
			"POST",
			"/api/v1/projects/" + encodeURIComponent(projectId) + "/integrations/textura/sync",
			null
		)
			.then(function (data) {
				var loaded = data && data.loaded != null ? data.loaded : 0;
				var skipped = data && data.skipped != null ? data.skipped : 0;
				var errors = data && data.errors != null ? data.errors : 0;
				setTexturaSyncStatus(
					"Textura: " + loaded + " updated, " + skipped + " skipped" + (errors ? ", " + errors + " errors" : ""),
					errors > 0 && loaded === 0
				);
				if (errors > 0 && loaded === 0) {
					toastErr("Textura sync failed — check API credentials and project number match.");
				} else {
					toastOk("Textura sync complete.");
				}
				return loadRegister();
			})
			.catch(function (err) {
				setTexturaSyncStatus(err.message || String(err), true);
				toastErr(err.message || String(err));
			})
			.finally(function () {
				if (btn) btn.disabled = false;
			});
	}

	function loadRegister() {
		if (!projectId) return;
		setRegisterErr("");
		return fetchJson("GET", "/api/v1/projects/" + encodeURIComponent(projectId) + "/pay-applications", null)
			.then(function (data) {
				var tb = document.getElementById("usis-inv-tbody-register");
				if (!tb) return;
				var items = data.items || [];
				tb.innerHTML = items
					.map(function (row) {
						return (
							"<tr data-pay-app-id=\"" +
							escapeHtml(row.id) +
							"\"><td>" +
							row.application_number +
							"</td><td>" +
							escapeHtml(row.period_to || "—") +
							"</td><td><span class=\"badge bg-light text-dark border\">" +
							escapeHtml(row.status) +
							(row.textura_invoice_id ? " <span class=\"badge bg-info-subtle text-info border\" title=\"Synced from Textura\">Textura</span>" : "") +
							"</span></td><td class=\"text-end font-monospace\">" +
							escapeHtml(row.current_payment_due || "—") +
							"</td><td class=\"text-end font-monospace\">" +
							escapeHtml(row.architect_certified_amount || "—") +
							"</td><td class=\"text-end\">" +
							(row.line_count != null ? row.line_count : "—") +
							"</td><td class=\"text-end\"><button type=\"button\" class=\"btn btn-sm btn-outline-primary usis-inv-open\">Open</button></td></tr>"
						);
					})
					.join("");
			})
			.catch(function (err) {
				setRegisterErr(err.message || String(err));
			});
	}

	function escapeHtml(s) {
		if (s == null) return "";
		var d = document.createElement("div");
		d.textContent = String(s);
		return d.innerHTML;
	}

	function isoToDatetimeLocal(iso) {
		if (!iso) return "";
		var s = String(iso);
		if (s.length >= 16) return s.slice(0, 16);
		return "";
	}

	function setEditorInputsEnabled(draft) {
		var ids = ["usis-inv-period-to", "usis-inv-notes", "usis-inv-l1", "usis-inv-l2", "usis-inv-add-line", "usis-inv-save-draft"];
		ids.forEach(function (id) {
			var el = document.getElementById(id);
			if (el) el.disabled = !draft;
		});
		var sub = document.getElementById("usis-inv-submit-app");
		if (sub) sub.disabled = !draft;
		var archAmt = document.getElementById("usis-inv-arch-amt");
		var archAt = document.getElementById("usis-inv-arch-at");
		if (archAmt) archAmt.disabled = false;
		if (archAt) archAt.disabled = false;
	}

	function fillSummary(item) {
		var p = document.getElementById("usis-inv-period-to");
		if (p) p.value = item.period_to ? String(item.period_to).slice(0, 10) : "";
		var n = document.getElementById("usis-inv-notes");
		if (n) n.value = item.notes || "";
		var l1 = document.getElementById("usis-inv-l1");
		if (l1) l1.value = moneyOrEmpty(item.original_contract_sum);
		var l2 = document.getElementById("usis-inv-l2");
		if (l2) l2.value = moneyOrEmpty(item.net_change_by_change_orders);
		function setSpan(id, val) {
			var el = document.getElementById(id);
			if (el) el.textContent = val == null || val === "" ? "—" : String(val);
		}
		setSpan("usis-inv-l3", item.contract_sum_to_date);
		setSpan("usis-inv-l4", item.total_completed_and_stored_to_date);
		setSpan("usis-inv-l5", item.retainage_total);
		setSpan("usis-inv-l6", item.total_earned_less_retainage);
		setSpan("usis-inv-l7", item.less_previous_certificates);
		setSpan("usis-inv-l8", item.current_payment_due);
		setSpan("usis-inv-l9", item.balance_to_finish_including_retainage);
		var aa = document.getElementById("usis-inv-arch-amt");
		if (aa) aa.value = moneyOrEmpty(item.architect_certified_amount);
		var at = document.getElementById("usis-inv-arch-at");
		if (at) at.value = isoToDatetimeLocal(item.architect_certified_at);
	}

	function sovRowHtml(line) {
		line = line || {};
		var openTr = line.id ? '<tr data-line-id="' + escapeHtml(line.id) + '">' : "<tr>";
		return (
			openTr +
			"<td><input type=\"text\" class=\"form-control form-control-sm\" data-field=\"phase_code\" value=\"" +
			escapeHtml(line.phase_code || "") +
			"\"></td>" +
			"<td><input type=\"text\" class=\"form-control form-control-sm\" data-field=\"description\" value=\"" +
			escapeHtml(line.description || "") +
			"\"></td>" +
			"<td><input type=\"text\" class=\"form-control form-control-sm text-end\" data-field=\"scheduled_value\" value=\"" +
			escapeHtml(line.scheduled_value || "0") +
			"\"></td>" +
			"<td><input type=\"text\" class=\"form-control form-control-sm text-end\" data-field=\"net_change_co\" value=\"" +
			escapeHtml(line.net_change_co || "0") +
			"\"></td>" +
			"<td><input type=\"text\" class=\"form-control form-control-sm text-end\" data-field=\"work_from_previous\" value=\"" +
			escapeHtml(line.work_from_previous || "0") +
			"\"></td>" +
			"<td><input type=\"text\" class=\"form-control form-control-sm text-end\" data-field=\"work_this_period\" value=\"" +
			escapeHtml(line.work_this_period || "0") +
			"\"></td>" +
			"<td><input type=\"text\" class=\"form-control form-control-sm text-end\" data-field=\"materials_stored\" value=\"" +
			escapeHtml(line.materials_stored || "0") +
			"\"></td>" +
			"<td><input type=\"text\" class=\"form-control form-control-sm text-end\" data-field=\"retention_to_date\" value=\"" +
			escapeHtml(line.retention_to_date || "0") +
			"\"></td>" +
			"<td><input type=\"text\" class=\"form-control form-control-sm text-end\" data-field=\"percent_complete\" value=\"" +
			escapeHtml(line.percent_complete != null ? line.percent_complete : "") +
			"\"></td>" +
			"<td class=\"text-end font-monospace small text-muted\">" +
			escapeHtml(line.balance_to_complete || "0") +
			"</td>" +
			"<td><button type=\"button\" class=\"btn btn-sm btn-outline-danger usis-inv-row-del\" title=\"Remove line\">×</button></td>" +
			"</tr>"
		);
	}

	function renderSovLines(lines) {
		var tb = document.getElementById("usis-inv-sov-tbody");
		if (!tb) return;
		if (!lines || !lines.length) {
			tb.innerHTML =
				"<tr><td colspan=\"11\" class=\"text-muted\">No lines yet — use <strong>+ Add line</strong> (draft only).</td></tr>";
			return;
		}
		tb.innerHTML = lines.map(function (li) {
			return sovRowHtml(li);
		}).join("");
	}

	function collectLines() {
		var tb = document.getElementById("usis-inv-sov-tbody");
		if (!tb) return [];
		var out = [];
		var idx = 0;
		tb.querySelectorAll("tr").forEach(function (tr) {
			if (tr.querySelector("td.text-muted[colspan]")) return;
			var o = { sort_order: idx };
			var lid = tr.getAttribute("data-line-id");
			if (lid) o.id = lid;
			tr.querySelectorAll("[data-field]").forEach(function (inp) {
				var f = inp.getAttribute("data-field");
				if (f) o[f] = inp.value;
			});
			out.push(o);
			idx++;
		});
		return out;
	}

	function openEditor(payAppId) {
		if (!projectId || !payAppId) return;
		currentPayAppId = payAppId;
		return fetchJson(
			"GET",
			"/api/v1/projects/" + encodeURIComponent(projectId) + "/pay-applications/" + encodeURIComponent(payAppId),
			null
		)
			.then(function (data) {
				var item = data.item;
				var lines = data.lines || [];
				currentItemStatus = item.status || "draft";
				var ed = document.getElementById("usis-inv-editor");
				if (ed) ed.classList.remove("d-none");
				var title = document.getElementById("usis-inv-editor-title");
				if (title) title.textContent = "Application #" + item.application_number + " (" + item.status + ")";
				fillSummary(item);
				renderSovLines(lines);
				setEditorInputsEnabled(currentItemStatus === "draft");
			})
			.catch(function (err) {
				toastErr(err.message || String(err));
			});
	}

	function closeEditor() {
		currentPayAppId = null;
		var ed = document.getElementById("usis-inv-editor");
		if (ed) ed.classList.add("d-none");
	}

	function saveDraft() {
		if (!projectId || !currentPayAppId) return;
		var body = {
			period_to: document.getElementById("usis-inv-period-to").value || null,
			notes: document.getElementById("usis-inv-notes").value || null,
			original_contract_sum: document.getElementById("usis-inv-l1").value || null,
			net_change_by_change_orders: document.getElementById("usis-inv-l2").value || "0",
			lines: collectLines(),
		};
		var aaEl = document.getElementById("usis-inv-arch-amt");
		var atEl = document.getElementById("usis-inv-arch-at");
		var aa = aaEl ? aaEl.value : "";
		var at = atEl ? atEl.value : "";
		if (aa !== "") body.architect_certified_amount = aa;
		if (at) {
			try {
				body.architect_certified_at = new Date(at).toISOString();
			} catch (e) {
				body.architect_certified_at = at;
			}
		}
		return fetchJson(
			"PATCH",
			"/api/v1/projects/" +
				encodeURIComponent(projectId) +
				"/pay-applications/" +
				encodeURIComponent(currentPayAppId),
			body
		)
			.then(function (data) {
				toastOk("Saved.");
				fillSummary(data.item);
				renderSovLines(data.lines || []);
				currentItemStatus = data.item.status;
				setEditorInputsEnabled(currentItemStatus === "draft");
				var title = document.getElementById("usis-inv-editor-title");
				if (title) title.textContent = "Application #" + data.item.application_number + " (" + data.item.status + ")";
				loadRegister();
			})
			.catch(function (err) {
				toastErr(err.message || String(err));
			});
	}

	function submitApp() {
		if (!projectId || !currentPayAppId) return;
		return fetchJson(
			"PATCH",
			"/api/v1/projects/" +
				encodeURIComponent(projectId) +
				"/pay-applications/" +
				encodeURIComponent(currentPayAppId),
			{ status: "submitted" }
		)
			.then(function (data) {
				toastOk("Marked submitted.");
				currentItemStatus = data.item.status;
				setEditorInputsEnabled(false);
				var title = document.getElementById("usis-inv-editor-title");
				if (title) title.textContent = "Application #" + data.item.application_number + " (" + data.item.status + ")";
				fillSummary(data.item);
				renderSovLines(data.lines || []);
				loadRegister();
			})
			.catch(function (err) {
				toastErr(err.message || String(err));
			});
	}

	function newApplication() {
		if (!projectId) return;
		return fetchJson("POST", "/api/v1/projects/" + encodeURIComponent(projectId) + "/pay-applications", {})
			.then(function (data) {
				toastOk("Created draft application.");
				var id = data.item.id;
				return loadRegister().then(function () {
					return openEditor(id);
				});
			})
			.catch(function (err) {
				toastErr(err.message || String(err));
			});
	}

	function wire() {
		projectId = projectIdFromQuery();
		var tab = document.getElementById("proj-tab-invoicing");
		if (tab) {
			tab.addEventListener("shown.bs.tab", function () {
				loadRegister();
			});
		}
		var ref = document.getElementById("usis-inv-refresh-register");
		if (ref) ref.addEventListener("click", loadRegister);
		var nw = document.getElementById("usis-inv-new-app");
		if (nw) nw.addEventListener("click", newApplication);
		var cl = document.getElementById("usis-inv-close-editor");
		if (cl) cl.addEventListener("click", closeEditor);
		var tx = document.getElementById("usis-inv-textura-sync");
		if (tx) tx.addEventListener("click", syncFromTextura);
		var sv = document.getElementById("usis-inv-save-draft");
		if (sv) sv.addEventListener("click", saveDraft);
		var sb = document.getElementById("usis-inv-submit-app");
		if (sb) sb.addEventListener("click", submitApp);
		var add = document.getElementById("usis-inv-add-line");
		if (add) {
			add.addEventListener("click", function () {
				if (currentItemStatus !== "draft") return;
				var tb = document.getElementById("usis-inv-sov-tbody");
				if (!tb) return;
				var empty = tb.querySelector("td.text-muted[colspan]");
				if (empty && empty.parentElement) empty.parentElement.remove();
				tb.insertAdjacentHTML("beforeend", sovRowHtml({}));
			});
		}
		var reg = document.getElementById("usis-inv-tbody-register");
		if (reg) {
			reg.addEventListener("click", function (ev) {
				var btn = ev.target.closest(".usis-inv-open");
				if (!btn) return;
				var tr = btn.closest("tr");
				if (!tr) return;
				var id = tr.getAttribute("data-pay-app-id");
				if (id) openEditor(id);
			});
		}
		var sov = document.getElementById("usis-inv-sov-tbody");
		if (sov) {
			sov.addEventListener("click", function (ev) {
				var del = ev.target.closest(".usis-inv-row-del");
				if (!del) return;
				var tr = del.closest("tr");
				if (tr) tr.remove();
			});
		}
	}

	if (document.readyState === "loading") {
		document.addEventListener("DOMContentLoaded", wire);
	} else {
		wire();
	}
})();
