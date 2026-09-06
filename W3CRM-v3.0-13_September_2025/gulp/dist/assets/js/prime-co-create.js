/**
 * Prime Change Order create / detail — owner/GC contract change.
 *
 * Query: ``project_id`` (required) and optional ``id`` (load + PATCH).
 * Lines: ``USISDocumentLines`` on usis-doc-lines / usis-doc-line-add / usis-doc-total.
 * Server writes owner contract value when status becomes approved AND the
 * revises-contract checkbox is on. This page does not PATCH the contract.
 */
(function () {
	"use strict";

	var STATUSES = ["draft", "submitted", "approved", "void"];

	var state = {
		projectId: null,
		coId: null,
		lines: null,
		busy: false,
		primaryContractId: null,
	};

	function $(id) {
		return document.getElementById(id);
	}

	function queryParam(name) {
		try {
			return new URLSearchParams(window.location.search).get(name) || "";
		} catch (e) {
			return "";
		}
	}

	function fetchJson(path, opts) {
		if (window.USIS_API && typeof window.USIS_API.fetchJson === "function") {
			return window.USIS_API.fetchJson(path, opts || {});
		}
		return fetch(path, Object.assign({ credentials: "include", headers: { Accept: "application/json" } }, opts || {})).then(
			function (res) {
				return res.text().then(function (t) {
					var j = t ? JSON.parse(t) : {};
					if (!res.ok) {
						var err = new Error(j.error || res.statusText || String(res.status));
						err.body = t;
						throw err;
					}
					return j;
				});
			}
		);
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

	function val(id) {
		var el = $(id);
		return el ? String(el.value || "").trim() : "";
	}

	function setVal(id, value) {
		var el = $(id);
		if (el) el.value = value == null ? "" : String(value);
	}

	function todayIso() {
		var d = new Date();
		return d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0") + "-" + String(d.getDate()).padStart(2, "0");
	}

	function isoDate(raw) {
		if (!raw) return "";
		return String(raw).slice(0, 10);
	}

	function flashError(msg) {
		var el = $("usis-pco-error");
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

	function projectReturnHref() {
		if (!state.projectId) return "construction/project-detail.html";
		return "construction/project-detail.html?id=" + encodeURIComponent(state.projectId) + "&tab=contract";
	}

	function stampCancelLinks() {
		["usis-pco-cancel", "usis-pco-cancel-footer", "usis-pco-crumb"].forEach(function (id) {
			var a = $(id);
			if (a) a.setAttribute("href", projectReturnHref());
		});
	}

	function setPageTitle(text) {
		var title = $("usis-pco-page-title");
		var crumb = $("usis-pco-crumb-current");
		if (title) title.textContent = text;
		if (crumb) crumb.textContent = text;
		var breadcrumb = document.querySelector(".page-title .breadcrumb-item.active span");
		if (breadcrumb) breadcrumb.textContent = text;
		var h1 = document.querySelector(".page-title .breadcrumb h1");
		if (h1) h1.textContent = text;
	}

	function contractLabel(it) {
		if (!it) return "";
		var bits = [it.contract_number, it.title].filter(function (x) {
			return x && String(x).trim();
		});
		return bits.length ? bits.join(" — ") : "Owner contract";
	}

	function fillSelect(sel, items, options) {
		options = options || {};
		if (!sel) return;
		var keep = options.selected || sel.value || "";
		sel.innerHTML = "";
		var blank = document.createElement("option");
		blank.value = "";
		blank.textContent = options.emptyLabel || "Select…";
		sel.appendChild(blank);
		(items || []).forEach(function (it) {
			var opt = document.createElement("option");
			opt.value = it.id;
			opt.textContent = it.label;
			sel.appendChild(opt);
		});
		if (keep) sel.value = keep;
	}

	function ensureOption(sel, id, label) {
		if (!sel || !id) return;
		var found = Array.prototype.some.call(sel.options, function (o) {
			return String(o.value) === String(id);
		});
		if (found) {
			sel.value = id;
			return;
		}
		var opt = document.createElement("option");
		opt.value = id;
		opt.textContent = label || id;
		sel.appendChild(opt);
		sel.value = id;
	}

	function pidPath(suffix) {
		return "/api/v1/projects/" + encodeURIComponent(state.projectId) + suffix;
	}

	function bindLines() {
		if (!window.USISDocumentLines || typeof window.USISDocumentLines.bind !== "function") {
			flashError("Line grid failed to load.");
			return;
		}
		state.lines = window.USISDocumentLines.bind({
			tbody: "usis-doc-lines",
			addBtn: "usis-doc-line-add",
			totalEl: "usis-doc-total",
			minRows: 1,
		});
		state.lines.load([{}]);
	}

	function loadContracts() {
		return fetchJson(pidPath("/contracts")).then(function (data) {
			var items = (data.items || []).map(function (it) {
				return { id: it.id, label: contractLabel(it) };
			});
			state.primaryContractId = data.primary_id || (items[0] && items[0].id) || null;
			fillSelect($("usis-pco-contract"), items, { emptyLabel: "Select owner contract…" });
			if (!state.coId && state.primaryContractId && $("usis-pco-contract") && !$("usis-pco-contract").value) {
				$("usis-pco-contract").value = state.primaryContractId;
			}
		});
	}

	function loadCompanies() {
		return fetchJson(pidPath("/directory/companies?all=1"))
			.then(function (data) {
				var items = (data.items || []).map(function (it) {
					var id = it.company_id || it.id;
					var label = it.name || "Company";
					if (it.company_type) label += " (" + it.company_type + ")";
					return { id: id, label: label };
				});
				if (items.length) return items;
				return fetchJson(pidPath("/directory/companies?limit=50")).then(function (fallback) {
					return (fallback.items || []).map(function (it) {
						var label = it.name || "Company";
						if (it.company_type) label += " (" + it.company_type + ")";
						return { id: it.company_id || it.id, label: label };
					});
				});
			})
			.then(function (items) {
				fillSelect($("usis-pco-gc"), items, { emptyLabel: "Select GC company…" });
			});
	}

	function showSourceCpr(number) {
		var wrap = $("usis-pco-source-cpr-wrap");
		var el = $("usis-pco-source-cpr");
		if (!wrap || !el) return;
		if (!number) {
			wrap.classList.add("d-none");
			el.textContent = "—";
			return;
		}
		el.textContent = number;
		wrap.classList.remove("d-none");
	}

	function loadSourceCpr(item) {
		var cprId = item && (item.cpr_id || item.source_cpr_id);
		var known = item && (item.cpr_number || item.source_cpr_number || item.prime_co);
		if (known && typeof known === "string") {
			showSourceCpr(known);
		}
		if (!cprId) {
			if (!known) showSourceCpr("");
			return Promise.resolve();
		}
		return fetchJson(pidPath("/cprs/" + encodeURIComponent(cprId)))
			.then(function (data) {
				var cpr = (data && data.item) || {};
				showSourceCpr(cpr.number || known || "CPR");
			})
			.catch(function () {
				showSourceCpr(known || "CPR");
			});
	}

	function applyItem(item) {
		if (!item) return;
		setVal("usis-pco-title", item.subject || item.title || "");
		var num = $("usis-pco-number");
		var numWrap = $("usis-pco-number-wrap");
		if (num) num.value = item.number || "";
		if (numWrap) numWrap.classList.toggle("d-none", !item.number);
		var status = String(item.status || "draft");
		if (STATUSES.indexOf(status) === -1) {
			ensureOption($("usis-pco-status"), status, status);
		}
		setVal("usis-pco-status", status);
		setVal("usis-pco-status-date", isoDate(item.status_date));
		setVal("usis-pco-notes", item.notes || "");
		var chk = $("usis-pco-revises");
		if (chk) chk.checked = !!(item.approved_revises_contract || item.revises_contract);
		ensureOption($("usis-pco-contract"), item.prime_contract_id, contractLabel(item) || "Owner contract");
		ensureOption($("usis-pco-gc"), item.gc_company_id, item.gc_company_name || "GC company");
		if (state.lines) {
			state.lines.load(item.items && item.items.length ? item.items : [{}]);
		}
		setPageTitle(item.number ? "Prime Change Order " + item.number : "Prime Change Order");
		loadSourceCpr(item);
	}

	function loadCo() {
		if (!state.coId) {
			showSourceCpr("");
			return Promise.resolve();
		}
		return fetchJson(pidPath("/change-orders/" + encodeURIComponent(state.coId))).then(function (data) {
			applyItem((data && data.item) || data);
		});
	}

	function collectPayload() {
		var title = val("usis-pco-title");
		var contractId = val("usis-pco-contract");
		var status = val("usis-pco-status") || "draft";
		var items = state.lines ? state.lines.collect() : [];
		if (!title) return { error: "Title is required.", focus: "usis-pco-title" };
		if (!contractId) return { error: "Owner contract is required.", focus: "usis-pco-contract" };
		if (STATUSES.indexOf(status) === -1) return { error: "Status is required.", focus: "usis-pco-status" };
		if (!items.length) return { error: "Add at least one line with a description.", focus: "usis-doc-line-add" };
		var chk = $("usis-pco-revises");
		var body = {
			subject: title,
			title: title,
			status: status,
			prime_contract_id: contractId,
			notes: val("usis-pco-notes") || null,
			approved_revises_contract: !!(chk && chk.checked),
			items: items,
		};
		var sd = val("usis-pco-status-date");
		if (sd) body.status_date = sd;
		var gc = val("usis-pco-gc");
		if (gc) body.gc_company_id = gc;
		return { body: body };
	}

	function setBusy(on) {
		state.busy = !!on;
		["usis-pco-save", "usis-pco-save-footer"].forEach(function (id) {
			var el = $(id);
			if (el) el.disabled = state.busy;
		});
	}

	function save() {
		if (state.busy) return;
		if (!state.projectId) {
			flashError("Open this form from Contract admin so a project id is in the URL.");
			return;
		}
		var collected = collectPayload();
		if (collected.error) {
			flashError(collected.error);
			var focus = $(collected.focus);
			if (focus) focus.focus();
			return;
		}
		flashError("");
		setBusy(true);
		var path = state.coId
			? pidPath("/change-orders/" + encodeURIComponent(state.coId))
			: pidPath("/change-orders");
		fetchJson(path, { method: state.coId ? "PATCH" : "POST", body: collected.body })
			.then(function () {
				if (window.USISNotify && window.USISNotify.success) {
					window.USISNotify.success(state.coId ? "Prime change order saved." : "Prime change order created.");
				}
				window.location.href = projectReturnHref();
			})
			.catch(function (err) {
				setBusy(false);
				flashError(errMessage(err));
				if (window.USISNotify && window.USISNotify.error) {
					window.USISNotify.error(errMessage(err));
				}
			});
	}

	function resolveIds() {
		state.projectId = (
			queryParam("project_id") ||
			queryParam("projectId") ||
			(window.USISProjectContext &&
				window.USISProjectContext.getProjectId &&
				window.USISProjectContext.getProjectId()) ||
			""
		).trim();
		state.coId = (queryParam("id") || queryParam("co_id") || "").trim();
	}

	function wire() {
		var form = $("usis-pco-form");
		if (form) {
			form.addEventListener("submit", function (ev) {
				ev.preventDefault();
				save();
			});
		}
		["usis-pco-save", "usis-pco-save-footer"].forEach(function (id) {
			var el = $(id);
			if (el) el.addEventListener("click", save);
		});
	}

	function init() {
		resolveIds();
		stampCancelLinks();
		bindLines();
		wire();
		var sd = $("usis-pco-status-date");
		if (sd && !sd.value) sd.value = todayIso();
		if (!state.projectId) {
			flashError("Open this form from a project Contract admin so a project id is in the URL.");
			return;
		}
		if (window.USISProjectContext && typeof window.USISProjectContext.setProjectId === "function") {
			window.USISProjectContext.setProjectId(state.projectId);
		}
		Promise.all([loadContracts(), loadCompanies()])
			.then(function () {
				return loadCo();
			})
			.catch(function (err) {
				flashError(errMessage(err));
			});
	}

	if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
	else init();
})();
