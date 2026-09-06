/**
 * Purchase Order Change Order create / detail.
 * POST/PATCH /api/v1/projects/<id>/wave2/po-change-orders — does not PATCH PO lines.
 */
(function () {
	"use strict";

	var state = {
		projectId: null,
		recordId: null,
		pos: [],
		parentLines: [],
		busy: false,
		applied: false,
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

	function num(el) {
		var v = parseFloat(String((el && el.value) || "0").replace(/,/g, ""));
		return isNaN(v) ? 0 : v;
	}

	function todayIso() {
		var d = new Date();
		return d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0") + "-" + String(d.getDate()).padStart(2, "0");
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
		var el = $("usis-poco-error");
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
		return "construction/project-detail.html?id=" + encodeURIComponent(state.projectId) + "&tab=procurement";
	}

	function stampCancelLinks() {
		["usis-poco-cancel", "usis-poco-crumb-list"].forEach(function (id) {
			var a = $(id);
			if (a) a.setAttribute("href", projectReturnHref());
		});
		var poLink = $("usis-poco-create-po");
		if (poLink) {
			poLink.setAttribute(
				"href",
				state.projectId
					? "construction/purchase-order-create.html?project_id=" + encodeURIComponent(state.projectId)
					: "construction/purchase-order-create.html"
			);
		}
	}

	function setTitles(text) {
		var title = text || t("New PO Change Order");
		var h1 = $("usis-poco-page-title");
		var crumb = $("usis-poco-crumb-current");
		if (h1) h1.textContent = title;
		if (crumb) crumb.textContent = title;
		if (document.title) document.title = title + " · USIS";
	}

	function poLabel(p) {
		if (!p) return "";
		var ref = (p.reference_number || "").trim();
		var title = (p.title || "").trim();
		var vendor = (p.vendor_name || "").trim();
		var rest = [title, vendor].filter(Boolean).join(" — ");
		if (ref && rest) return ref + " — " + rest;
		return ref || rest || "Purchase order";
	}

	function parentLineLabel(li) {
		if (!li) return "";
		var num = (li.item_number || "").trim();
		var desc = (li.description || "").trim() || "Line";
		return num ? num + " — " + desc : desc;
	}

	function parentLineById(id) {
		if (!id) return null;
		return (
			state.parentLines.find(function (li) {
				return String(li.id) === String(id);
			}) || null
		);
	}

	function parentLineOptionsHtml(selected) {
		var html = '<option value="">—</option>';
		state.parentLines.forEach(function (li) {
			html +=
				'<option value="' +
				esc(li.id) +
				'"' +
				(selected && String(selected) === String(li.id) ? " selected" : "") +
				">" +
				esc(parentLineLabel(li)) +
				"</option>";
		});
		return html;
	}

	function refreshTotals() {
		var tbody = $("usis-poco-lines-tbody");
		var totalEl = $("usis-poco-doc-amount");
		if (!tbody) return 0;
		var sum = 0;
		Array.prototype.forEach.call(tbody.querySelectorAll("tr[data-line]"), function (tr, i) {
			var idx = tr.querySelector("[data-line-idx]");
			if (idx) idx.textContent = String(i + 1);
			var ext = num(tr.querySelector("[data-line-qty]")) * num(tr.querySelector("[data-line-price]"));
			sum += ext;
			var extEl = tr.querySelector("[data-line-ext]");
			if (extEl) extEl.textContent = money(ext);
		});
		if (totalEl) totalEl.textContent = money(sum);
		return sum;
	}

	function syncParentSelect(tr) {
		var action = (tr.querySelector("[data-line-action]") || {}).value || "add";
		var parent = tr.querySelector("[data-line-parent]");
		if (!parent) return;
		parent.disabled = action === "add";
		if (action === "add") parent.value = "";
	}

	function applyParentPrefill(tr) {
		var parentId = (tr.querySelector("[data-line-parent]") || {}).value || "";
		var li = parentLineById(parentId);
		if (!li) return;
		var desc = tr.querySelector("[data-line-desc]");
		var qty = tr.querySelector("[data-line-qty]");
		var unit = tr.querySelector("[data-line-unit]");
		var price = tr.querySelector("[data-line-price]");
		if (desc && !String(desc.value || "").trim()) desc.value = li.description || "";
		if (qty && (qty.value === "" || qty.value === "1" || qty.value === "0")) qty.value = li.quantity != null ? li.quantity : "1";
		if (unit && (!unit.value || unit.value === "EA")) unit.value = li.unit || "EA";
		if (price && (price.value === "" || price.value === "0")) {
			price.value = li.unit_cost != null ? li.unit_cost : li.unit_price != null ? li.unit_price : "0";
		}
		refreshTotals();
	}

	function addLineRow(item) {
		var tbody = $("usis-poco-lines-tbody");
		if (!tbody) return;
		item = item || {};
		var action = String(item.action || "add").toLowerCase();
		if (action !== "change" && action !== "delete") action = "add";
		var parentId = item.parent_po_line_id || item.commitment_line_id || "";
		var tr = document.createElement("tr");
		tr.setAttribute("data-line", "1");
		tr.innerHTML =
			'<td class="text-muted" data-line-idx></td>' +
			'<td><select class="form-select form-select-sm" data-line-action>' +
			'<option value="add"' +
			(action === "add" ? " selected" : "") +
			">add</option>" +
			'<option value="change"' +
			(action === "change" ? " selected" : "") +
			">change</option>" +
			'<option value="delete"' +
			(action === "delete" ? " selected" : "") +
			">delete</option>" +
			"</select></td>" +
			'<td><select class="form-select form-select-sm" data-line-parent>' +
			parentLineOptionsHtml(parentId) +
			"</select></td>" +
			'<td><input type="text" class="form-control form-control-sm" data-line-desc maxlength="500" value="' +
			esc(item.description || "") +
			'"></td>' +
			'<td><input type="number" class="form-control form-control-sm" data-line-qty step="0.0001" value="' +
			esc(item.quantity != null && item.quantity !== "" ? item.quantity : "1") +
			'"></td>' +
			'<td><input type="text" class="form-control form-control-sm" data-line-unit maxlength="40" value="' +
			esc(item.unit || "EA") +
			'"></td>' +
			'<td><input type="number" class="form-control form-control-sm" data-line-price step="0.01" value="' +
			esc(item.unit_price != null && item.unit_price !== "" ? item.unit_price : item.unit_cost != null ? item.unit_cost : "0") +
			'"></td>' +
			'<td class="text-end usis-poco-ext" data-line-ext>$0.00</td>' +
			'<td class="text-end"><button type="button" class="btn btn-link btn-sm text-danger p-0" data-line-remove aria-label="Remove line">&times;</button></td>';
		tbody.appendChild(tr);
		syncParentSelect(tr);
		refreshTotals();
		return tr;
	}

	function refreshParentSelects() {
		var tbody = $("usis-poco-lines-tbody");
		if (!tbody) return;
		Array.prototype.forEach.call(tbody.querySelectorAll("tr[data-line]"), function (tr) {
			var sel = tr.querySelector("[data-line-parent]");
			if (!sel) return;
			var cur = sel.value;
			sel.innerHTML = parentLineOptionsHtml(cur);
			syncParentSelect(tr);
		});
	}

	function collectLines() {
		var tbody = $("usis-poco-lines-tbody");
		if (!tbody) return [];
		return Array.prototype.map
			.call(tbody.querySelectorAll("tr[data-line]"), function (tr, i) {
				var action = ((tr.querySelector("[data-line-action]") || {}).value || "add").trim().toLowerCase();
				var parent = ((tr.querySelector("[data-line-parent]") || {}).value || "").trim() || null;
				var desc = ((tr.querySelector("[data-line-desc]") || {}).value || "").trim();
				var qty = num(tr.querySelector("[data-line-qty]"));
				var price = num(tr.querySelector("[data-line-price]"));
				var unit = ((tr.querySelector("[data-line-unit]") || {}).value || "").trim() || "EA";
				return {
					action: action,
					parent_po_line_id: action === "add" ? null : parent,
					description: desc,
					quantity: qty,
					unit: unit,
					unit_price: price,
					line_total: Math.round(qty * price * 100) / 100,
					sort_order: i,
				};
			})
			.filter(function (row) {
				return row.description;
			});
	}

	function showEmptyPos(empty) {
		var emptyEl = $("usis-poco-empty-pos");
		var sel = $("usis-poco-commitment");
		if (emptyEl) emptyEl.classList.toggle("d-none", !empty);
		if (sel) sel.classList.toggle("d-none", !!empty);
	}

	function fillPoSelect(selected) {
		var sel = $("usis-poco-commitment");
		if (!sel) return;
		sel.innerHTML = "";
		var blank = document.createElement("option");
		blank.value = "";
		blank.textContent = t("Select a purchase order");
		sel.appendChild(blank);
		state.pos.forEach(function (p) {
			var opt = document.createElement("option");
			opt.value = p.id;
			opt.textContent = poLabel(p);
			sel.appendChild(opt);
		});
		if (selected) {
			sel.value = selected;
			if (sel.value !== String(selected)) {
				var extra = document.createElement("option");
				extra.value = selected;
				extra.textContent = t("Purchase order");
				sel.appendChild(extra);
				sel.value = selected;
			}
		}
		showEmptyPos(!state.pos.length && !selected);
	}

	function loadParentLines(poId) {
		state.parentLines = [];
		if (!state.projectId || !poId) {
			refreshParentSelects();
			return Promise.resolve([]);
		}
		return fetchJson(
			"/api/v1/projects/" + encodeURIComponent(state.projectId) + "/commitments/" + encodeURIComponent(poId) + "/line-items"
		)
			.then(function (data) {
				state.parentLines = data.items || [];
				refreshParentSelects();
				return state.parentLines;
			})
			.catch(function () {
				state.parentLines = [];
				refreshParentSelects();
				return [];
			});
	}

	function loadPurchaseOrders(selected) {
		if (!state.projectId) return Promise.resolve([]);
		return fetchJson("/api/v1/projects/" + encodeURIComponent(state.projectId) + "/commitments").then(function (data) {
			state.pos = (data.items || []).filter(function (c) {
				return (c.commitment_kind || "") === "purchase_order";
			});
			fillPoSelect(selected || "");
			return state.pos;
		});
	}

	function buildPayload() {
		var items = collectLines();
		var payload = {
			subject: (($("usis-poco-subject") || {}).value || "").trim(),
			commitment_id: (($("usis-poco-commitment") || {}).value || "").trim(),
			status: (($("usis-poco-status") || {}).value || "draft").trim() || "draft",
			notes: (($("usis-poco-notes") || {}).value || "").trim() || null,
			items: items,
		};
		var sd = ($("usis-poco-status-date") || {}).value;
		payload.status_date = sd || null;
		return payload;
	}

	function validate(payload) {
		if (!state.projectId) return t("Choose a project.");
		if (!payload.commitment_id) return t("Select a parent purchase order.");
		if (!payload.subject) return t("Subject is required.");
		if (!payload.status) return t("Status is required.");
		if (!payload.items.length) return t("Add at least one delta line.");
		var missingParent = payload.items.some(function (row) {
			return (row.action === "change" || row.action === "delete") && !row.parent_po_line_id;
		});
		if (missingParent) return t("Change and delete lines need a parent PO line.");
		return "";
	}

	function setBusy(on) {
		state.busy = !!on;
		var btn = $("usis-poco-save");
		if (btn) btn.disabled = !!on;
	}

	function fillForm(item) {
		item = item || {};
		state.applied = !!item.applied;
		var appliedEl = $("usis-poco-applied");
		if (appliedEl) appliedEl.classList.toggle("d-none", !state.applied);
		var subject = $("usis-poco-subject");
		if (subject) subject.value = item.subject || "";
		var status = $("usis-poco-status");
		if (status) status.value = item.status || "draft";
		var sd = $("usis-poco-status-date");
		if (sd) sd.value = item.status_date ? String(item.status_date).slice(0, 10) : "";
		var notes = $("usis-poco-notes");
		if (notes) notes.value = item.notes || "";
		var numEl = $("usis-poco-number");
		if (numEl) numEl.textContent = item.number || "—";
		setTitles(item.number || item.subject || t("PO Change Order"));
		var tbody = $("usis-poco-lines-tbody");
		if (tbody) tbody.innerHTML = "";
		var lines = item.items && item.items.length ? item.items : [{}];
		lines.forEach(function (row) {
			addLineRow(row);
		});
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
		var path = "/api/v1/projects/" + encodeURIComponent(state.projectId) + "/wave2/po-change-orders";
		var method = "POST";
		if (state.recordId) {
			path += "/" + encodeURIComponent(state.recordId);
			method = "PATCH";
		}
		setBusy(true);
		fetchJson(path, { method: method, body: payload })
			.then(function () {
				if (window.USISNotify && window.USISNotify.success) {
					window.USISNotify.success(state.recordId ? "PO change order saved." : "PO change order created.");
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
		var form = $("usis-poco-form");
		if (form) form.addEventListener("submit", save);
		var add = $("usis-poco-line-add");
		if (add) {
			add.addEventListener("click", function () {
				addLineRow({});
			});
		}
		var tbody = $("usis-poco-lines-tbody");
		if (tbody) {
			tbody.addEventListener("input", refreshTotals);
			tbody.addEventListener("change", function (e) {
				var tr = e.target.closest("tr[data-line]");
				if (!tr) return;
				if (e.target.matches("[data-line-action]")) {
					syncParentSelect(tr);
				}
				if (e.target.matches("[data-line-parent]")) {
					applyParentPrefill(tr);
				}
				refreshTotals();
			});
			tbody.addEventListener("click", function (e) {
				var btn = e.target.closest("[data-line-remove]");
				if (!btn) return;
				var tr = btn.closest("tr");
				if (!tr) return;
				if (tbody.querySelectorAll("tr[data-line]").length <= 1) return;
				tr.remove();
				refreshTotals();
			});
		}
		var poSel = $("usis-poco-commitment");
		if (poSel) {
			poSel.addEventListener("change", function () {
				loadParentLines(poSel.value);
			});
		}
	}

	function loadRecord() {
		if (!state.recordId) {
			var sd = $("usis-poco-status-date");
			if (sd && !sd.value) sd.value = todayIso();
			addLineRow({});
			return Promise.resolve();
		}
		return fetchJson(
			"/api/v1/projects/" + encodeURIComponent(state.projectId) + "/wave2/po-change-orders/" + encodeURIComponent(state.recordId)
		).then(function (data) {
			var item = data.item || {};
			return loadPurchaseOrders(item.commitment_id).then(function () {
				return loadParentLines(item.commitment_id).then(function () {
					fillForm(item);
					var sel = $("usis-poco-commitment");
					if (sel && item.commitment_id) sel.value = item.commitment_id;
				});
			});
		});
	}

	function init() {
		state.projectId = currentProjectId();
		state.recordId = (queryParam("id") || queryParam("poco_id") || "").trim() || null;
		if (state.projectId) rememberProject(state.projectId);
		stampCancelLinks();
		wire();
		if (!state.projectId) {
			flashError(t("Choose a project."));
			showEmptyPos(false);
			addLineRow({});
			return;
		}
		var start = state.recordId ? loadRecord() : loadPurchaseOrders("").then(function () {
			return loadRecord();
		});
		start.catch(function (e) {
			flashError(errMessage(e));
			if (!$("usis-poco-lines-tbody") || !$("usis-poco-lines-tbody").children.length) addLineRow({});
		});
	}

	if (document.readyState === "loading") {
		document.addEventListener("DOMContentLoaded", init);
	} else {
		init();
	}
})();
