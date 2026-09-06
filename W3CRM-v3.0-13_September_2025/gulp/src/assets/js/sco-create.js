/**
 * Subcontract Change Order create / detail.
 *
 * Query: ``project_id`` (required) and optional ``id`` (load + PATCH).
 * Lines: ``USISDocumentLines`` on usis-doc-lines / usis-doc-line-add / usis-doc-total.
 * Parent subcontract is a <select> — never a raw UUID field or window.prompt.
 * Server adds amount to subcontract total_amount when status becomes approved.
 * This page does not PATCH the commitment.
 */
(function () {
	"use strict";

	var STATUSES = ["draft", "issued", "approved", "void"];

	var state = {
		projectId: null,
		scoId: null,
		lines: null,
		busy: false,
		subcontracts: [],
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
		var el = $("usis-sco-error");
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
		if (!state.projectId) return "construction/project-detail.html?tab=procurement";
		return "construction/project-detail.html?id=" + encodeURIComponent(state.projectId) + "&tab=procurement";
	}

	function stampCancelLinks() {
		["usis-sco-cancel", "usis-sco-crumb"].forEach(function (id) {
			var a = $(id);
			if (a) a.setAttribute("href", projectReturnHref());
		});
		var emptyLink = $("usis-sco-empty-link");
		if (emptyLink) emptyLink.setAttribute("href", projectReturnHref());
	}

	function setPageTitle(text) {
		var title = $("usis-sco-page-title");
		var crumb = $("usis-sco-crumb-current");
		if (title) title.textContent = text;
		if (crumb) crumb.textContent = text;
		var breadcrumb = document.querySelector(".page-title .breadcrumb-item.active span");
		if (breadcrumb) breadcrumb.textContent = text;
		var h1 = document.querySelector(".page-title .breadcrumb h1");
		if (h1) h1.textContent = text;
	}

	function subcontractLabel(c) {
		if (!c) return "Subcontract";
		var left = String(c.reference_number || c.title || "").trim() || "Subcontract";
		var vendor = String(c.vendor_name || "").trim();
		return vendor ? left + " — " + vendor : left;
	}

	function scoParentLabel(item) {
		if (!item) return "Subcontract";
		var left = String(item.subcontract_number || item.reference_number || item.title || "").trim() || "Subcontract";
		var vendor = String(item.vendor_name || "").trim();
		return vendor ? left + " — " + vendor : left;
	}

	function fillSelect(sel, items, options) {
		options = options || {};
		if (!sel) return;
		var keep = options.selected || sel.value || "";
		sel.innerHTML = "";
		var blank = document.createElement("option");
		blank.value = "";
		blank.textContent = options.emptyLabel || "Select a subcontract…";
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
		opt.textContent = label || "Subcontract";
		sel.appendChild(opt);
		sel.value = id;
	}

	function showEmpty(empty) {
		var emptyEl = $("usis-sco-empty");
		var sel = $("usis-sco-commitment");
		if (emptyEl) emptyEl.classList.toggle("d-none", !empty);
		if (sel) sel.classList.toggle("d-none", !!empty);
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

	function loadSubcontracts(selectedId) {
		if (!state.projectId) return Promise.resolve([]);
		return fetchJson(pidPath("/commitments")).then(function (data) {
			state.subcontracts = (data.items || []).filter(function (c) {
				return (c.commitment_kind || "") === "subcontract";
			});
			fillSelect(
				$("usis-sco-commitment"),
				state.subcontracts.map(function (c) {
					return { id: c.id, label: subcontractLabel(c) };
				}),
				{ emptyLabel: "Select a subcontract…", selected: selectedId || "" }
			);
			var hasList = state.subcontracts.length > 0;
			var hasSelected = !!(selectedId && $("usis-sco-commitment") && $("usis-sco-commitment").value);
			showEmpty(!hasList && !hasSelected);
			return state.subcontracts;
		});
	}

	function applyItem(item) {
		if (!item) return;
		setVal("usis-sco-subject", item.subject || item.title || "");
		var num = $("usis-sco-number");
		var numWrap = $("usis-sco-number-wrap");
		if (num) num.textContent = item.number || "—";
		if (numWrap) numWrap.classList.toggle("d-none", !item.number);
		var status = String(item.status || "draft");
		if (STATUSES.indexOf(status) === -1) {
			ensureOption($("usis-sco-status"), status, status);
		}
		setVal("usis-sco-status", status);
		setVal("usis-sco-status-date", isoDate(item.status_date));
		setVal("usis-sco-notes", item.notes || "");
		ensureOption($("usis-sco-commitment"), item.commitment_id, scoParentLabel(item));
		if (item.commitment_id) showEmpty(false);
		if (state.lines) {
			state.lines.load(item.items && item.items.length ? item.items : [{}]);
		}
		setPageTitle(item.number ? "Subcontract Change Order " + item.number : "Subcontract Change Order");
	}

	function loadSco() {
		if (!state.scoId) return Promise.resolve();
		return fetchJson(pidPath("/scos/" + encodeURIComponent(state.scoId))).then(function (data) {
			applyItem((data && data.item) || data);
		});
	}

	function collectPayload() {
		var subject = val("usis-sco-subject");
		var commitmentId = val("usis-sco-commitment");
		var status = val("usis-sco-status") || "draft";
		var items = state.lines ? state.lines.collect() : [];
		if (!commitmentId) return { error: "Select a parent subcontract.", focus: "usis-sco-commitment" };
		if (!subject) return { error: "Subject is required.", focus: "usis-sco-subject" };
		if (STATUSES.indexOf(status) === -1) return { error: "Status is required.", focus: "usis-sco-status" };
		if (!items.length) return { error: "Add at least one line with a description.", focus: "usis-doc-line-add" };
		var body = {
			commitment_id: commitmentId,
			subject: subject,
			status: status,
			notes: val("usis-sco-notes") || null,
			items: items.map(function (row) {
				return {
					description: row.description,
					quantity: row.quantity,
					unit: row.unit,
					unit_price: row.unit_price,
					sort_order: row.sort_order,
				};
			}),
		};
		var sd = val("usis-sco-status-date");
		if (sd) body.status_date = sd;
		return { body: body };
	}

	function setBusy(on) {
		state.busy = !!on;
		["usis-sco-save", "usis-sco-save-footer"].forEach(function (id) {
			var el = $(id);
			if (el) el.disabled = state.busy;
		});
	}

	function save() {
		if (state.busy) return;
		if (!state.projectId) {
			flashError("Open this form from Procurement so a project id is in the URL.");
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
		var path = state.scoId
			? pidPath("/scos/" + encodeURIComponent(state.scoId))
			: pidPath("/scos");
		fetchJson(path, { method: state.scoId ? "PATCH" : "POST", body: collected.body })
			.then(function () {
				if (window.USISNotify && window.USISNotify.success) {
					window.USISNotify.success(state.scoId ? "Subcontract change order saved." : "Subcontract change order created.");
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
		state.scoId = (queryParam("id") || queryParam("sco_id") || "").trim() || null;
	}

	function wire() {
		var form = $("usis-sco-form");
		if (form) {
			form.addEventListener("submit", function (ev) {
				ev.preventDefault();
				save();
			});
		}
		["usis-sco-save", "usis-sco-save-footer"].forEach(function (id) {
			var el = $(id);
			if (el) el.addEventListener("click", save);
		});
	}

	function init() {
		resolveIds();
		stampCancelLinks();
		bindLines();
		wire();
		var sd = $("usis-sco-status-date");
		if (sd && !sd.value) sd.value = todayIso();
		if (!state.projectId) {
			flashError("Open this form from a project Procurement tab so a project id is in the URL.");
			showEmpty(false);
			return;
		}
		if (window.USISProjectContext && typeof window.USISProjectContext.setProjectId === "function") {
			window.USISProjectContext.setProjectId(state.projectId);
		}
		loadSubcontracts()
			.then(function () {
				return loadSco();
			})
			.catch(function (err) {
				flashError(errMessage(err));
			});
	}

	if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
	else init();
})();
