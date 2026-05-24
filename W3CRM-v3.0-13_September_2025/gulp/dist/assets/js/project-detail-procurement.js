/**
 * Project detail — Procurement tab: PO tool, Subcontract tool, RFP mini-list.
 * Commitments: GET/POST/PATCH `/api/v1/projects/<id>/commitments`.
 * RFPs: GET/POST `/api/v1/rfps` (same contract as usis-rfp-list.js).
 * Requires ?id= project UUID. Uses same apiBase() rules as project-detail-tools.js.
 */
(function () {
	"use strict";
	var projectId = null;
	var costCodesCache = [];
	var activeProcTool = "po";
	var taxCodesCache = [];
	var poTypesCache = [];
	var vendorSearchTimer = null;
	var createLineCounter = 0;

	function todayIso() {
		var d = new Date();
		return d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0") + "-" + String(d.getDate()).padStart(2, "0");
	}
	function isoDateOnly(val) {
		if (!val) return "";
		return String(val).slice(0, 10);
	}
	function fillSelectOptions(sel, items, valueKey, labelFn, selectedVal) {
		if (!sel) return;
		var keep = sel.getAttribute("data-usis-keep-first") === "1";
		var first = keep && sel.options.length ? sel.options[0].outerHTML : '<option value="">—</option>';
		sel.innerHTML = first;
		(items || []).forEach(function (it) {
			var o = document.createElement("option");
			o.value = it[valueKey];
			o.textContent = labelFn(it);
			if (selectedVal && String(selectedVal) === String(it[valueKey])) o.selected = true;
			sel.appendChild(o);
		});
	}
	function fillCostCodeSelects(selectedId) {
		var ids = [
			"usis-c-line-cc",
			"usis-c-create-def-cc",
		];
		ids.forEach(function (id) {
			var sel = document.getElementById(id);
			if (!sel) return;
			fillSelectOptions(
				sel,
				costCodesCache,
				"id",
				function (cc) {
					return cc.code + (cc.description ? " — " + cc.description : "");
				},
				id === "usis-c-create-def-cc" ? selectedId : null
			);
		});
	}
	function fillTaxCodeSelects() {
		["usis-c-line-tax", "usis-c-create-def-tax"].forEach(function (id) {
			var sel = document.getElementById(id);
			if (!sel) return;
			fillSelectOptions(
				sel,
				taxCodesCache,
				"code",
				function (t) {
					return t.label || t.code;
				},
				null
			);
		});
	}
	function loadPoTypes() {
		return fetchJson("/api/v1/procurement/po-types").then(function (data) {
			poTypesCache = data.items || [];
			["usis-c-create-po-type", "usis-c-edit-po-type"].forEach(function (id) {
				var sel = document.getElementById(id);
				if (!sel) return;
				fillSelectOptions(sel, poTypesCache, "code", function (t) { return t.label; }, null);
			});
		});
	}
	function loadTaxCodes() {
		if (!projectId) return Promise.resolve();
		return fetchJson("/api/v1/projects/" + encodeURIComponent(projectId) + "/rfi-lookups/tax_codes").then(function (data) {
			taxCodesCache = data.items || [];
			fillTaxCodeSelects();
		});
	}
	function loadProcurementDefaults() {
		if (!projectId) return Promise.resolve();
		return fetchJson("/api/v1/projects/" + encodeURIComponent(projectId) + "/procurement/defaults").then(function (data) {
			var item = (data && data.item) || {};
			var ship = document.getElementById("usis-c-create-ship-to");
			if (ship && item.ship_to_address) ship.value = item.ship_to_address;
			var iss = document.getElementById("usis-c-create-issue-date");
			if (iss && item.issue_date) iss.value = item.issue_date;
		});
	}
	function hideComboboxMenu(menu) {
		if (menu) menu.classList.add("d-none");
	}
	function wireEntityCombobox(inputId, menuId, hiddenId, searchFn, onPick) {
		var input = document.getElementById(inputId);
		var menu = document.getElementById(menuId);
		var hidden = document.getElementById(hiddenId);
		if (!input || !menu) return;
		function renderItems(items) {
			menu.innerHTML = "";
			if (!items.length) {
				menu.innerHTML = '<div class="list-group-item small text-muted">No matches</div>';
				menu.classList.remove("d-none");
				return;
			}
			items.forEach(function (it) {
				var btn = document.createElement("button");
				btn.type = "button";
				btn.className = "list-group-item list-group-item-action py-1 small";
				btn.textContent = it.label;
				btn.addEventListener("click", function () {
					if (hidden) hidden.value = it.id;
					input.value = it.label;
					hideComboboxMenu(menu);
					if (onPick) onPick(it);
				});
				menu.appendChild(btn);
			});
			menu.classList.remove("d-none");
		}
		input.addEventListener("input", function () {
			if (hidden) hidden.value = "";
			clearTimeout(vendorSearchTimer);
			var q = input.value.trim();
			if (q.length < 1) {
				hideComboboxMenu(menu);
				return;
			}
			vendorSearchTimer = setTimeout(function () {
				searchFn(q).then(renderItems).catch(function () {
					hideComboboxMenu(menu);
				});
			}, 250);
		});
		input.addEventListener("blur", function () {
			setTimeout(function () {
				hideComboboxMenu(menu);
			}, 200);
		});
	}
	function searchDirectoryCompanies(q) {
		return fetchJson(
			"/api/v1/projects/" + encodeURIComponent(projectId) + "/directory/companies?q=" + encodeURIComponent(q) + "&limit=20"
		).then(function (data) {
			return (data.items || []).map(function (c) {
				return {
					id: c.id,
					label: c.name + " (" + c.company_type + ")",
					in_directory: c.in_directory,
				};
			});
		});
	}
	function searchUsers(q) {
		return fetchJson("/api/v1/rfi-users?q=" + encodeURIComponent(q) + "&limit=20").then(function (data) {
			return (data.items || []).map(function (u) {
				return { id: u.id, label: u.name + (u.email ? " <" + u.email + ">" : "") };
			});
		});
	}
	function loadVendorProfile(companyId, prefix) {
		if (!companyId) return Promise.resolve();
		return fetchJson("/api/v1/companies/" + encodeURIComponent(companyId) + "/procurement-profile").then(function (data) {
			var item = data.item || {};
			var addr = document.getElementById(prefix + "-vendor-address");
			if (addr && item.address) addr.value = item.address;
			var csel = document.getElementById(prefix + "-vendor-contact");
			if (csel) {
				csel.innerHTML = '<option value="">—</option>';
				(item.contacts || []).forEach(function (c) {
					var o = document.createElement("option");
					o.value = c.id;
					o.textContent = c.label;
					csel.appendChild(o);
				});
			}
			return item;
		});
	}
	function wireVendorComboboxes() {
		wireEntityCombobox("usis-c-create-vendor-q", "usis-c-create-vendor-menu", "usis-c-create-vendor-id", searchDirectoryCompanies, function (it) {
			var hint = document.getElementById("usis-c-create-vendor-dir-hint");
			var addBtn = document.getElementById("usis-c-create-vendor-add-dir");
			if (hint && addBtn) {
				if (it.in_directory) {
					hint.classList.add("d-none");
					addBtn.classList.add("d-none");
				} else {
					hint.textContent = "Vendor is not in the project directory.";
					hint.classList.remove("d-none");
					addBtn.classList.remove("d-none");
					addBtn.onclick = function () {
						fetchJsonBody("POST", "/api/v1/projects/" + encodeURIComponent(projectId) + "/directory/companies", {
							company_id: it.id,
						})
							.then(function () {
								toastOk("Added to project directory.");
								hint.classList.add("d-none");
								addBtn.classList.add("d-none");
							})
							.catch(function (e) {
								toastErr(e.message || String(e));
							});
					};
				}
			}
			loadVendorProfile(it.id, "usis-c-create");
		});
		wireEntityCombobox("usis-c-edit-vendor-q", "usis-c-edit-vendor-menu", "usis-c-edit-vendor-id", searchDirectoryCompanies, function (it) {
			loadVendorProfile(it.id, "usis-c-edit");
		});
		wireEntityCombobox("usis-c-create-issued-by-q", "usis-c-create-issued-by-menu", "usis-c-create-issued-by-id", searchUsers, null);
		wireEntityCombobox("usis-c-create-authorized-by-q", "usis-c-create-authorized-by-menu", "usis-c-create-authorized-by-id", searchUsers, null);
		wireEntityCombobox("usis-c-edit-issued-by-q", "usis-c-edit-issued-by-menu", "usis-c-edit-issued-by-id", searchUsers, null);
		wireEntityCombobox("usis-c-edit-authorized-by-q", "usis-c-edit-authorized-by-menu", "usis-c-edit-authorized-by-id", searchUsers, null);
	}
	function costCodeOptionsHtml(selected) {
		var html = '<option value="">—</option>';
		costCodesCache.forEach(function (cc) {
			html +=
				'<option value="' +
				esc(cc.id) +
				'"' +
				(selected && String(selected) === String(cc.id) ? " selected" : "") +
				">" +
				esc(cc.code + (cc.description ? " — " + cc.description : "")) +
				"</option>";
		});
		return html;
	}
	function taxOptionsHtml(selected) {
		var html = '<option value="">—</option>';
		taxCodesCache.forEach(function (t) {
			html +=
				'<option value="' +
				esc(t.code) +
				'"' +
				(selected && String(selected) === String(t.code) ? " selected" : "") +
				">" +
				esc(t.label || t.code) +
				"</option>";
		});
		return html;
	}
	function resourceOptionsHtml(selected) {
		var opts = [
			["", "—"],
			["material", "Material"],
			["labor", "Labor"],
			["equipment", "Equipment"],
			["subcontractor", "Subcontractor"],
			["other", "Other"],
		];
		return opts
			.map(function (p) {
				return (
					'<option value="' +
					esc(p[0]) +
					'"' +
					(selected && String(selected) === String(p[0]) ? " selected" : "") +
					">" +
					esc(p[1]) +
					"</option>"
				);
			})
			.join("");
	}
	function addCreateLineRow(prefill) {
		var tb = document.getElementById("usis-c-create-lines-tbody");
		if (!tb) return;
		createLineCounter += 1;
		var p = prefill || {};
		var tr = document.createElement("tr");
		tr.innerHTML =
			'<td><input class="form-control form-control-sm usis-c-create-line-itemno" value="' +
			esc(p.item_number || String(createLineCounter)) +
			'"></td>' +
			'<td><input class="form-control form-control-sm usis-c-create-line-desc" value="' +
			esc(p.description || "") +
			'"></td>' +
			'<td><input class="form-control form-control-sm usis-c-create-line-qty" value="' +
			esc(p.quantity != null ? p.quantity : "") +
			'"></td>' +
			'<td><input class="form-control form-control-sm usis-c-create-line-unit" value="' +
			esc(p.unit || "EA") +
			'"></td>' +
			'<td><input class="form-control form-control-sm usis-c-create-line-cost" value="' +
			esc(p.unit_cost != null ? p.unit_cost : "") +
			'"></td>' +
			'<td><select class="form-select form-select-sm usis-c-create-line-cc">' +
			costCodeOptionsHtml(p.cost_code_id) +
			"</select></td>" +
			'<td><select class="form-select form-select-sm usis-c-create-line-tax">' +
			taxOptionsHtml(p.tax_code) +
			"</select></td>" +
			'<td><select class="form-select form-select-sm usis-c-create-line-resource">' +
			resourceOptionsHtml(p.resource) +
			"</select></td>" +
			'<td><input type="date" class="form-control form-control-sm usis-c-create-line-delivery" value="' +
			esc(isoDateOnly(p.delivery_date)) +
			'"></td>' +
			'<td class="text-end"><button type="button" class="btn btn-link btn-sm text-danger p-0 usis-c-create-line-rm">×</button></td>';
		tb.appendChild(tr);
		tr.querySelector(".usis-c-create-line-rm").addEventListener("click", function () {
			tr.remove();
		});
	}
	function collectCreateLineItems() {
		var rows = document.querySelectorAll("#usis-c-create-lines-tbody tr");
		var out = [];
		rows.forEach(function (tr, idx) {
			var desc = tr.querySelector(".usis-c-create-line-desc");
			var qty = tr.querySelector(".usis-c-create-line-qty");
			if (!desc || !String(desc.value || "").trim()) return;
			var body = {
				item_number: (tr.querySelector(".usis-c-create-line-itemno") || {}).value || String(idx + 1),
				description: String(desc.value).trim(),
				quantity: qty && qty.value.trim() ? qty.value.trim() : "0",
				unit: (tr.querySelector(".usis-c-create-line-unit") || {}).value || "EA",
				unit_cost: (tr.querySelector(".usis-c-create-line-cost") || {}).value || "0",
				sort_order: idx,
			};
			var cc = tr.querySelector(".usis-c-create-line-cc");
			if (cc && cc.value) body.cost_code_id = cc.value;
			var tax = tr.querySelector(".usis-c-create-line-tax");
			if (tax && tax.value) body.tax_code = tax.value;
			var res = tr.querySelector(".usis-c-create-line-resource");
			if (res && res.value) body.resource = res.value;
			var del = tr.querySelector(".usis-c-create-line-delivery");
			if (del && del.value) body.delivery_date = del.value;
			out.push(body);
		});
		return out;
	}
	function resetCreateForm() {
		createLineCounter = 0;
		[
			"usis-c-create-vendor-id",
			"usis-c-create-issued-by-id",
			"usis-c-create-authorized-by-id",
		].forEach(function (id) {
			var el = document.getElementById(id);
			if (el) el.value = "";
		});
		[
			"usis-c-create-vendor-q",
			"usis-c-create-title",
			"usis-c-create-ref",
			"usis-c-create-notes",
			"usis-c-create-vendor-address",
			"usis-c-create-issued-address",
			"usis-c-create-ship-to",
			"usis-c-create-issued-by-q",
			"usis-c-create-authorized-by-q",
			"usis-c-create-reminder-date",
			"usis-c-create-status-date",
			"usis-c-create-def-delivery",
		].forEach(function (id) {
			var el = document.getElementById(id);
			if (el) el.value = "";
		});
		var iss = document.getElementById("usis-c-create-issue-date");
		if (iss) iss.value = todayIso();
		var st = document.getElementById("usis-c-create-status");
		if (st) st.value = "draft";
		var cur = document.getElementById("usis-c-create-currency");
		if (cur) cur.value = "USD";
		var tb = document.getElementById("usis-c-create-lines-tbody");
		if (tb) tb.innerHTML = "";
		var hint = document.getElementById("usis-c-create-vendor-dir-hint");
		var addBtn = document.getElementById("usis-c-create-vendor-add-dir");
		if (hint) hint.classList.add("d-none");
		if (addBtn) addBtn.classList.add("d-none");
	}
	function buildCreatePayload(kind) {
		var status = document.getElementById("usis-c-create-status").value;
		var payload = {
			commitment_kind: kind,
			vendor_company_id: document.getElementById("usis-c-create-vendor-id").value,
			reference_number: document.getElementById("usis-c-create-ref").value.trim() || null,
			title: document.getElementById("usis-c-create-title").value.trim(),
			status: status,
			currency: document.getElementById("usis-c-create-currency").value.trim() || "USD",
			notes: document.getElementById("usis-c-create-notes").value.trim() || null,
		};
		var sd = document.getElementById("usis-c-create-status-date").value;
		if (sd) payload.status_effective_date = sd;
		else if (status !== "draft") payload.status_effective_date = todayIso();
		var idate = document.getElementById("usis-c-create-issue-date").value;
		if (idate) payload.issue_date = idate;
		var pt = document.getElementById("usis-c-create-po-type").value;
		if (pt) payload.po_type = pt;
		var rd = document.getElementById("usis-c-create-reminder-date").value;
		if (rd) payload.reminder_date = rd;
		var vc = document.getElementById("usis-c-create-vendor-contact").value;
		if (vc) payload.vendor_contact_id = vc;
		var va = document.getElementById("usis-c-create-vendor-address").value.trim();
		if (va) payload.vendor_address_snapshot = va;
		var ib = document.getElementById("usis-c-create-issued-by-id").value;
		if (ib) payload.issued_by_user_id = ib;
		var ab = document.getElementById("usis-c-create-authorized-by-id").value;
		if (ab) payload.authorized_by_user_id = ab;
		var ia = document.getElementById("usis-c-create-issued-address").value.trim();
		if (ia) payload.issued_by_address_snapshot = ia;
		var ship = document.getElementById("usis-c-create-ship-to").value.trim();
		if (ship) payload.ship_to_address = ship;
		var dd = document.getElementById("usis-c-create-def-delivery").value;
		if (dd) payload.default_delivery_date = dd;
		var dcc = document.getElementById("usis-c-create-def-cc").value;
		if (dcc) payload.default_cost_code_id = dcc;
		var dt = document.getElementById("usis-c-create-def-tax").value;
		if (dt) payload.default_tax_code = dt;
		var dr = document.getElementById("usis-c-create-def-resource").value;
		if (dr) payload.default_resource = dr;
		if (kind === "purchase_order") {
			var lines = collectCreateLineItems();
			if (lines.length) payload.line_items = lines;
		}
		return payload;
	}
	function apiBase() {
		if (typeof window.USIS_API_BASE === "string" && window.USIS_API_BASE.trim()) {
			var s = window.USIS_API_BASE.trim().replace(/\/$/, "");
			try {
				if (s && new URL(s).origin === window.location.origin) {
					/* fall through */
				} else if (s) {
					return s;
				}
			} catch (e) {
				if (s) return s;
			}
		}
		var loc = window.location;
		if (loc.protocol === "file:") {
			return "http://127.0.0.1:5000";
		}
		var host = loc.hostname || "";
		var proto = loc.protocol || "http:";
		var port = String(loc.port || "");
		var devPorts = { 3000: 1, 3001: 1, 3002: 1, 4173: 1, 5173: 1, 5174: 1, 5500: 1, 5501: 1, 8080: 1, 4200: 1, 4321: 1, 9630: 1, 1234: 1 };
		if (devPorts[port]) {
			return proto + "//" + host + ":5000";
		}
		var loopback = host === "localhost" || host === "127.0.0.1" || host === "::1";
		if (loopback) {
			if (port === "5000") return "";
			return proto + "//" + host + ":5000";
		}
		var ipv4 = /^\d{1,3}(\.\d{1,3}){3}$/.test(host);
		if (ipv4 && port && port !== "5000" && port !== "80" && port !== "443") {
			return proto + "//" + host + ":5000";
		}
		if ((host === "host.docker.internal" || host.endsWith(".local")) && port && port !== "5000") {
			return proto + "//" + host + ":5000";
		}
		return "";
	}
	function projectIdFromQuery() {
		var id = new URLSearchParams(window.location.search).get("id");
		return id && id.trim() ? id.trim() : null;
	}
	function esc(s) {
		if (s == null || s === "") return "";
		var d = document.createElement("div");
		d.textContent = String(s);
		return d.innerHTML;
	}
	function toastErr(msg) {
		if (window.USISNotify && window.USISNotify.error) window.USISNotify.error(msg);
	}
	function toastOk(msg) {
		if (window.USISNotify && window.USISNotify.success) window.USISNotify.success(msg);
	}
	function setPaneMsg(sel, msg) {
		var el = document.querySelector(sel);
		if (!el) return;
		if (msg) {
			el.textContent = msg;
			el.classList.remove("d-none");
		} else {
			el.textContent = "";
			el.classList.add("d-none");
		}
	}
	function setProcPoError(msg) {
		setPaneMsg("[data-usis-proc-po-error]", msg);
	}
	function setProcSubError(msg) {
		setPaneMsg("[data-usis-proc-sub-error]", msg);
	}
	function setProcPoLoading(on) {
		var el = document.querySelector("[data-usis-proc-po-loading]");
		if (!el) return;
		if (on) el.classList.remove("d-none");
		else el.classList.add("d-none");
	}
	function setProcSubLoading(on) {
		var el = document.querySelector("[data-usis-proc-sub-loading]");
		if (!el) return;
		if (on) el.classList.remove("d-none");
		else el.classList.add("d-none");
	}
	function setProcRfpError(msg) {
		setPaneMsg("[data-usis-proc-rfp-error]", msg);
	}
	function setProcRfpLoading(on) {
		var el = document.querySelector("[data-usis-proc-rfp-loading]");
		if (!el) return;
		if (on) el.classList.remove("d-none");
		else el.classList.add("d-none");
	}
	function actorHeaders() {
		var id = null;
		try {
			id = window.localStorage.getItem("usisActorUserId");
		} catch (e) {}
		if (id && id.trim()) {
			return { "X-Usis-User-Id": id.trim() };
		}
		return {};
	}
	function fetchJson(path) {
		var base = apiBase();
		return fetch(base + path, {
			credentials: "include",
			headers: Object.assign({ Accept: "application/json" }, actorHeaders()),
		}).then(function (res) {
			if (!res.ok) {
				return res.text().then(function (t) {
					throw new Error(res.status + " " + (t || res.statusText));
				});
			}
			return res.json();
		});
	}
	function fetchJsonBody(method, path, bodyObj) {
		var base = apiBase();
		var opts = {
			method: method,
			credentials: "include",
			headers: Object.assign(
				{ "Content-Type": "application/json", Accept: "application/json" },
				actorHeaders()
			),
		};
		if (bodyObj !== undefined && bodyObj !== null) {
			opts.body = JSON.stringify(bodyObj);
		}
		return fetch(base + path, opts).then(function (res) {
			if (!res.ok) {
				return res.text().then(function (t) {
					throw new Error(res.status + " " + (t || res.statusText));
				});
			}
			if (res.status === 204) return null;
			return res.json();
		});
	}
	function fetchEmpty(method, path) {
		var base = apiBase();
		return fetch(base + path, {
			method: method,
			credentials: "include",
			headers: Object.assign({ Accept: "application/json" }, actorHeaders()),
		}).then(function (res) {
			if (!res.ok) {
				return res.text().then(function (t) {
					throw new Error(res.status + " " + (t || res.statusText));
				});
			}
			return null;
		});
	}
	function kindLabel(k) {
		return k === "subcontract" ? "Subcontract" : "PO";
	}
	function linkedRfpCell(row) {
		if (!row.rfp_id) return "—";
		var href = "../usis-rfp-detail.html?id=" + encodeURIComponent(row.rfp_id);
		var label = row.rfp_title ? String(row.rfp_title) : "Open RFP";
		return '<a href="' + esc(href) + '">' + esc(label) + "</a>";
	}
	function renderCommitmentTable(items, kindFilter, tbodyId) {
		var tb = document.getElementById(tbodyId);
		if (!tb) return;
		tb.innerHTML = "";
		var rows = (items || []).filter(function (row) {
			return (row.commitment_kind || "") === kindFilter;
		});
		if (!rows.length) {
			tb.innerHTML = '<tr><td colspan="7" class="text-muted small">No items yet.</td></tr>';
			return;
		}
		rows.forEach(function (row) {
			var tr = document.createElement("tr");
			tr.innerHTML =
				"<td>" +
				esc(row.reference_number || "—") +
				"</td><td>" +
				esc(row.title || "") +
				"</td><td>" +
				esc(row.vendor_name || "") +
				"</td><td>" +
				linkedRfpCell(row) +
				"</td><td><span class=\"badge bg-light text-dark border\">" +
				esc(row.status) +
				"</span></td><td class=\"text-end\">" +
				esc(row.total_amount != null ? row.total_amount : "—") +
				'</td><td class="text-end"><button type="button" class="btn btn-link btn-sm p-0 usis-c-open" data-id="' +
				esc(row.id) +
				'">Edit</button></td>';
			tb.appendChild(tr);
		});
		tb.querySelectorAll(".usis-c-open").forEach(function (btn) {
			btn.addEventListener("click", function () {
				openEditModal(btn.getAttribute("data-id"));
			});
		});
	}
	function loadCommitmentsList() {
		if (!projectId) {
			setProcPoError("Open this page with ?id=<project UUID> to load procurement.");
			setProcSubError("Open this page with ?id=<project UUID> to load procurement.");
			return Promise.resolve();
		}
		setProcPoError("");
		setProcSubError("");
		setProcPoLoading(true);
		setProcSubLoading(true);
		return fetchJson("/api/v1/projects/" + encodeURIComponent(projectId) + "/commitments")
			.then(function (data) {
				var items = data.items || [];
				renderCommitmentTable(items, "purchase_order", "usis-tbody-commitments-po");
				renderCommitmentTable(items, "subcontract", "usis-tbody-commitments-sub");
			})
			.catch(function (e) {
				var m = String(e.message || e);
				setProcPoError(m);
				setProcSubError(m);
				toastErr("Could not load commitments.");
			})
			.finally(function () {
				setProcPoLoading(false);
				setProcSubLoading(false);
			});
	}
	function vendorPublicBase() {
		var b = apiBase();
		if (!b && window.location.protocol === "file:") return "http://127.0.0.1:5000";
		return (b || "").replace(/\/$/, "");
	}
	function formatDue(iso) {
		if (!iso) return "—";
		try {
			var d = new Date(iso);
			if (isNaN(d.getTime())) return esc(String(iso));
			return esc(d.toLocaleString(undefined, { dateStyle: "short", timeStyle: "short" }));
		} catch (e) {
			return esc(String(iso));
		}
	}
	function renderRfpRows(items) {
		var tb = document.getElementById("usis-proc-rfp-tbody");
		if (!tb) return;
		tb.innerHTML = "";
		if (!items || !items.length) {
			tb.innerHTML = '<tr><td colspan="5" class="text-muted small">No RFPs yet.</td></tr>';
			return;
		}
		var pubBase = vendorPublicBase();
		items.forEach(function (x) {
			var vendorHref = pubBase + "/public/rfp/" + encodeURIComponent(x.public_token);
			var tr = document.createElement("tr");
			tr.innerHTML =
				"<td>" +
				esc(x.title) +
				"</td><td>" +
				esc(x.status) +
				"</td><td>" +
				formatDue(x.due_at) +
				'</td><td><code class="small">' +
				esc(x.public_token) +
				'</code></td><td class="text-end text-nowrap">' +
				'<a class="btn btn-sm btn-outline-primary" href="../usis-rfp-detail.html?id=' +
				encodeURIComponent(x.id) +
				'">Open detail</a> ' +
				'<a class="btn btn-sm btn-outline-secondary" href="' +
				esc(vendorHref) +
				'" target="_blank" rel="noopener">Vendor portal</a></td>';
			tb.appendChild(tr);
		});
	}
	function loadRfpMiniList() {
		if (!projectId) {
			setProcRfpError("No project id.");
			return Promise.resolve();
		}
		setProcRfpError("");
		setProcRfpLoading(true);
		var q = "project_id=" + encodeURIComponent(projectId);
		return fetchJson("/api/v1/rfps?" + q)
			.then(function (data) {
				renderRfpRows(data.items || []);
			})
			.catch(function (e) {
				setProcRfpError(String(e.message || e));
				toastErr("Could not load RFPs.");
			})
			.finally(function () {
				setProcRfpLoading(false);
			});
	}
	var poListCache = [];

	function setProcMatError(msg) {
		setPaneMsg("[data-usis-proc-mat-error]", msg);
	}
	function setProcMatLoading(on) {
		var el = document.querySelector("[data-usis-proc-mat-loading]");
		if (!el) return;
		if (on) el.classList.remove("d-none");
		else el.classList.add("d-none");
	}
	function fmtDateOnly(iso) {
		if (!iso) return "—";
		try {
			var d = new Date(iso);
			if (isNaN(d.getTime())) return esc(String(iso));
			return esc(d.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" }));
		} catch (e) {
			return esc(String(iso));
		}
	}
	function renderMaterialOrders(items) {
		var tb = document.getElementById("usis-tbody-material-orders");
		if (!tb) return;
		tb.innerHTML = "";
		if (!items || !items.length) {
			tb.innerHTML = '<tr><td colspan="9" class="text-muted small">No material orders yet. Create a PO first, then add tracking rows here.</td></tr>';
			return;
		}
		items.forEach(function (row) {
			var tr = document.createElement("tr");
			var poLabel = row.commitment_ref || row.commitment_title || row.commitment_id || "—";
			tr.innerHTML =
				"<td>" +
				esc(row.vendor_name || "—") +
				"</td><td>" +
				esc(row.description || "—") +
				"</td><td class=\"small\">" +
				esc(poLabel) +
				"</td><td>" +
				fmtDateOnly(row.order_date) +
				"</td><td>" +
				fmtDateOnly(row.expected_delivery_date) +
				"</td><td>" +
				esc(row.shipping_company || "—") +
				"</td><td class=\"small\">" +
				esc(row.tracking_number || "—") +
				"</td><td><span class=\"badge bg-light text-dark border\">" +
				esc(row.status || "draft") +
				'</span></td><td class="text-end"><button type="button" class="btn btn-link btn-sm p-0 usis-mat-edit" data-id="' +
				esc(row.id) +
				'">Edit</button></td>';
			tb.appendChild(tr);
		});
		tb.querySelectorAll(".usis-mat-edit").forEach(function (btn) {
			btn.addEventListener("click", function () {
				openMaterialOrderPrompt(btn.getAttribute("data-id"));
			});
		});
	}
	function loadMaterialOrders() {
		if (!projectId) {
			setProcMatError("No project id.");
			return Promise.resolve();
		}
		setProcMatError("");
		setProcMatLoading(true);
		return fetchJson("/api/v1/projects/" + encodeURIComponent(projectId) + "/material-orders")
			.then(function (data) {
				renderMaterialOrders(data.items || []);
			})
			.catch(function (e) {
				setProcMatError(String(e.message || e));
				toastErr("Could not load material orders.");
			})
			.finally(function () {
				setProcMatLoading(false);
			});
	}
	function loadPoCache() {
		if (!projectId) return Promise.resolve([]);
		return fetchJson("/api/v1/projects/" + encodeURIComponent(projectId) + "/commitments").then(function (data) {
			poListCache = (data.items || []).filter(function (c) {
				return c.commitment_kind === "purchase_order";
			});
			return poListCache;
		});
	}
	function openMaterialOrderPrompt(existingId) {
		if (!projectId) return;
		loadPoCache()
			.then(function (pos) {
				if (!pos.length) {
					toastErr("Create a purchase order before adding material orders.");
					return;
				}
				var poOpts = pos
					.map(function (p, i) {
						return i + 1 + ") " + (p.reference_number || p.title || p.id);
					})
					.join("\n");
				var pick = window.prompt("Link to PO (enter number):\n" + poOpts, "1");
				if (pick === null) return;
				var idx = parseInt(pick, 10) - 1;
				if (isNaN(idx) || idx < 0 || idx >= pos.length) {
					toastErr("Invalid PO selection.");
					return;
				}
				var po = pos[idx];
				var vendor = window.prompt("Vendor name:", po.vendor_name || "");
				if (vendor === null) return;
				var desc = window.prompt("Material description:", "");
				if (desc === null) return;
				var lead = window.prompt("Lead time (days, optional):", "14");
				var anchor = window.prompt("Schedule need-by date (YYYY-MM-DD, optional):", "");
				var ship = window.prompt("Shipping company:", "");
				var track = window.prompt("Tracking number:", "");
				var body = {
					commitment_id: po.id,
					vendor_name: String(vendor).trim() || po.vendor_name,
					description: String(desc).trim() || null,
					lead_time_days: lead && String(lead).trim() ? parseInt(lead, 10) : null,
					schedule_anchor_date: anchor && String(anchor).trim() ? String(anchor).trim() : null,
					shipping_company: ship && String(ship).trim() ? String(ship).trim() : null,
					tracking_number: track && String(track).trim() ? String(track).trim() : null,
					status: "ordered",
				};
				var method = existingId ? "PATCH" : "POST";
				var path =
					"/api/v1/projects/" +
					encodeURIComponent(projectId) +
					"/material-orders" +
					(existingId ? "/" + encodeURIComponent(existingId) : "");
				return fetchJsonBody(method, path, body).then(function () {
					toastOk(existingId ? "Material order updated." : "Material order created.");
					return loadMaterialOrders();
				});
			})
			.catch(function (e) {
				if (e) toastErr(e.message || String(e));
			});
	}

	function createRfpDraft() {
		if (!projectId) {
			toastErr("No project id in the URL.");
			return;
		}
		return fetchJsonBody("POST", "/api/v1/rfps", { project_id: projectId })
			.then(function () {
				toastOk("RFP draft created.");
				return loadRfpMiniList();
			})
			.catch(function (e) {
				toastErr(e.message || String(e));
			});
	}
	function loadCostCodes() {
		if (!projectId) return Promise.resolve();
		return fetchJson("/api/v1/projects/" + encodeURIComponent(projectId) + "/rfi-lookups/cost_codes").then(function (data) {
			costCodesCache = data.items || [];
			fillCostCodeSelects();
		});
	}
	function configureCreateModalForKind(kind) {
		var k = kind === "subcontract" ? "subcontract" : "purchase_order";
		var kindSel = document.getElementById("usis-c-create-kind");
		if (kindSel) kindSel.value = k;
		var titleEl = document.getElementById("usis-c-create-modal-title");
		if (titleEl) titleEl.textContent = k === "subcontract" ? "New subcontract" : "New purchase order";
		var refLab = document.getElementById("usis-c-create-ref-label");
		var refInp = document.getElementById("usis-c-create-ref");
		if (refLab) refLab.textContent = k === "subcontract" ? "Contract #" : "PO #";
		if (refInp) {
			refInp.placeholder = k === "subcontract" ? "SUB-201" : "PO-1001";
			refInp.required = k !== "subcontract";
		}
		document.querySelectorAll(".usis-c-po-only").forEach(function (el) {
			if (k === "subcontract") el.classList.add("d-none");
			else el.classList.remove("d-none");
		});
	}
	function populateEditHeader(item) {
		document.getElementById("usis-c-edit-id").value = item.id;
		document.getElementById("usis-c-edit-modal-label").textContent =
			kindLabel(item.commitment_kind) + " — " + (item.reference_number || item.title || item.id);
		document.getElementById("usis-c-edit-vendor-id").value = item.vendor_company_id || "";
		document.getElementById("usis-c-edit-vendor-q").value = item.vendor_name || "";
		document.getElementById("usis-c-edit-status").value = item.status || "draft";
		document.getElementById("usis-c-edit-status-date").value = isoDateOnly(item.status_effective_date);
		document.getElementById("usis-c-edit-wf").value = item.workflow_rule_active ? "1" : "0";
		document.getElementById("usis-c-edit-titlefield").value = item.title || "";
		document.getElementById("usis-c-edit-ref").value = item.reference_number || "";
		document.getElementById("usis-c-edit-notes").value = item.notes || "";
		document.getElementById("usis-c-edit-total").value = item.total_amount != null ? item.total_amount : "";
		document.getElementById("usis-c-edit-currency").value = item.currency || "USD";
		document.getElementById("usis-c-edit-issue-date").value = isoDateOnly(item.issue_date);
		document.getElementById("usis-c-edit-reminder-date").value = isoDateOnly(item.reminder_date);
		document.getElementById("usis-c-edit-po-type").value = item.po_type || "";
		document.getElementById("usis-c-edit-vendor-address").value = item.vendor_address_snapshot || "";
		document.getElementById("usis-c-edit-issued-address").value = item.issued_by_address_snapshot || "";
		document.getElementById("usis-c-edit-ship-to").value = item.ship_to_address || "";
		document.getElementById("usis-c-edit-issued-by-id").value = item.issued_by_user_id || "";
		document.getElementById("usis-c-edit-authorized-by-id").value = item.authorized_by_user_id || "";
		document.getElementById("usis-c-edit-issued-by-q").value = item.issued_by_name || "";
		document.getElementById("usis-c-edit-authorized-by-q").value = item.authorized_by_name || "";
		document.querySelectorAll(".usis-c-edit-po-only").forEach(function (el) {
			if (item.commitment_kind === "subcontract") el.classList.add("d-none");
			else el.classList.remove("d-none");
		});
		var rw = document.getElementById("usis-c-edit-ret-wrap");
		var ret = document.getElementById("usis-c-edit-ret");
		if (item.commitment_kind === "subcontract") {
			rw.classList.remove("d-none");
			ret.value = item.retention_percentage != null ? item.retention_percentage : "";
		} else {
			rw.classList.add("d-none");
			ret.value = "";
		}
	}
	function openEditModal(cid) {
		if (!projectId || !cid) return;
		return fetchJson(
			"/api/v1/projects/" + encodeURIComponent(projectId) + "/commitments/" + encodeURIComponent(cid)
		)
			.then(function (data) {
				var item = data.item;
				populateEditHeader(item);
				var rfpWrap = document.getElementById("usis-c-edit-rfp-link-wrap");
				var rfpA = document.getElementById("usis-c-edit-rfp-link");
				if (item.rfp_id && rfpWrap && rfpA) {
					rfpA.href = "../usis-rfp-detail.html?id=" + encodeURIComponent(item.rfp_id);
					rfpA.textContent = item.rfp_title || "Open linked RFP";
					rfpWrap.classList.remove("d-none");
				} else if (rfpWrap) {
					rfpWrap.classList.add("d-none");
				}
				renderLinesTable(data.line_items || []);
				renderBillsTable(data.bill_allocations || []);
				return Promise.all([
					loadCostCodes(),
					loadTaxCodes(),
					loadPoTypes(),
					loadVendorProfile(item.vendor_company_id, "usis-c-edit"),
				]).then(function () {
					var csel = document.getElementById("usis-c-edit-vendor-contact");
					if (csel && item.vendor_contact_id) csel.value = item.vendor_contact_id;
					document.getElementById("usis-c-edit-po-type").value = item.po_type || "";
				});
			})
			.then(function () {
				var modal = document.getElementById("usis-modal-commitment-edit");
				if (modal && window.bootstrap && window.bootstrap.Modal) {
					window.bootstrap.Modal.getOrCreateInstance(modal).show();
				}
			})
			.catch(function (e) {
				toastErr("Could not open commitment: " + (e.message || e));
			});
	}
	function renderLinesTable(lines) {
		var tb = document.getElementById("usis-c-edit-lines-tbody");
		if (!tb) return;
		tb.innerHTML = "";
		lines.forEach(function (li) {
			var tr = document.createElement("tr");
			tr.innerHTML =
				"<td>" +
				esc(li.item_number || "—") +
				"</td><td>" +
				esc(li.description) +
				"</td><td>" +
				esc(li.quantity) +
				"</td><td>" +
				esc(li.unit) +
				"</td><td>" +
				esc(li.unit_cost) +
				"</td><td>" +
				esc(li.tax_code || "—") +
				"</td><td>" +
				esc(li.resource || "—") +
				"</td><td>" +
				esc(isoDateOnly(li.delivery_date) || "—") +
				"</td><td>" +
				esc(li.line_total) +
				'</td><td class="text-end"><button type="button" class="btn btn-link btn-sm text-danger p-0 usis-c-line-del" data-id="' +
				esc(li.id) +
				'">Remove</button></td>';
			tb.appendChild(tr);
		});
		tb.querySelectorAll(".usis-c-line-del").forEach(function (btn) {
			btn.addEventListener("click", function () {
				var lid = btn.getAttribute("data-id");
				var cid = document.getElementById("usis-c-edit-id").value;
				fetchEmpty(
					"DELETE",
					"/api/v1/projects/" +
						encodeURIComponent(projectId) +
						"/commitments/" +
						encodeURIComponent(cid) +
						"/line-items/" +
						encodeURIComponent(lid)
				)
					.then(function () {
						toastOk("Line removed.");
						return openEditModal(cid);
					})
					.catch(function (e) {
						toastErr(e.message || String(e));
					});
			});
		});
	}
	function renderBillsTable(bills) {
		var tb = document.getElementById("usis-c-edit-bills-tbody");
		if (!tb) return;
		tb.innerHTML = "";
		bills.forEach(function (b) {
			var tr = document.createElement("tr");
			tr.innerHTML =
				"<td>" +
				esc(b.vendor_bill_ref) +
				'</td><td class="text-end">' +
				esc(b.allocated_amount) +
				"</td><td>" +
				esc(b.billed_at || "—") +
				'</td><td class="text-end"><button type="button" class="btn btn-link btn-sm text-danger p-0 usis-c-bill-del" data-id="' +
				esc(b.id) +
				'">Remove</button></td>';
			tb.appendChild(tr);
		});
		tb.querySelectorAll(".usis-c-bill-del").forEach(function (btn) {
			btn.addEventListener("click", function () {
				var bid = btn.getAttribute("data-id");
				var cid = document.getElementById("usis-c-edit-id").value;
				fetchEmpty(
					"DELETE",
					"/api/v1/projects/" +
						encodeURIComponent(projectId) +
						"/commitments/" +
						encodeURIComponent(cid) +
						"/bill-allocations/" +
						encodeURIComponent(bid)
				)
					.then(function () {
						toastOk("Bill allocation removed.");
						return openEditModal(cid);
					})
					.catch(function (e) {
						toastErr(e.message || String(e));
					});
			});
		});
	}
	function onProcurementMainTabShown() {
		loadCommitmentsList();
		var rfpTab = document.getElementById("usis-proc-subtab-rfp");
		if (rfpTab && rfpTab.classList.contains("active")) {
			loadRfpMiniList();
		}
	}
	function wire() {
		projectId = projectIdFromQuery();
		var tab = document.getElementById("proj-tab-procurement");
		if (tab) {
			tab.addEventListener("shown.bs.tab", function () {
				onProcurementMainTabShown();
			});
		}
		var refreshPo = document.getElementById("usis-procurement-refresh-po");
		if (refreshPo) {
			refreshPo.addEventListener("click", function () {
				loadCommitmentsList();
			});
		}
		var refreshSub = document.getElementById("usis-procurement-refresh-sub");
		if (refreshSub) {
			refreshSub.addEventListener("click", function () {
				loadCommitmentsList();
			});
		}
		var subPo = document.getElementById("usis-proc-subtab-po");
		if (subPo) {
			subPo.addEventListener("shown.bs.tab", function () {
				activeProcTool = "po";
			});
		}
		var subSub = document.getElementById("usis-proc-subtab-sub");
		if (subSub) {
			subSub.addEventListener("shown.bs.tab", function () {
				activeProcTool = "sub";
			});
		}
		var subRfp = document.getElementById("usis-proc-subtab-rfp");
		if (subRfp) {
			subRfp.addEventListener("shown.bs.tab", function () {
				activeProcTool = "rfp";
				loadRfpMiniList();
			});
		}
		var subMat = document.getElementById("usis-proc-subtab-materials");
		if (subMat) {
			subMat.addEventListener("shown.bs.tab", function () {
				activeProcTool = "materials";
				loadMaterialOrders();
			});
		}
		var matRefresh = document.getElementById("usis-proc-materials-refresh");
		if (matRefresh) {
			matRefresh.addEventListener("click", function () {
				loadMaterialOrders();
			});
		}
		var matNew = document.getElementById("usis-proc-materials-new");
		if (matNew) {
			matNew.addEventListener("click", function () {
				openMaterialOrderPrompt(null);
			});
		}
		var rfpRefresh = document.getElementById("usis-proc-rfp-refresh");
		if (rfpRefresh) {
			rfpRefresh.addEventListener("click", function () {
				loadRfpMiniList();
			});
		}
		var rfpNew = document.getElementById("usis-proc-rfp-new");
		if (rfpNew) {
			rfpNew.addEventListener("click", function () {
				createRfpDraft();
			});
		}
		var createModal = document.getElementById("usis-modal-commitment-create");
		if (createModal) {
			createModal.addEventListener("show.bs.modal", function (ev) {
				var trigger = ev.relatedTarget;
				var kind =
					trigger && trigger.getAttribute
						? trigger.getAttribute("data-usis-commitment-kind")
						: null;
				if (!kind) {
					kind = activeProcTool === "sub" ? "subcontract" : "purchase_order";
				}
				configureCreateModalForKind(kind);
				resetCreateForm();
				Promise.all([loadCostCodes(), loadTaxCodes(), loadPoTypes(), loadProcurementDefaults()]).catch(
					function () {
						toastErr("Could not load procurement lookups.");
					}
				);
			});
		}
		var createLineAdd = document.getElementById("usis-c-create-line-add");
		if (createLineAdd) {
			createLineAdd.addEventListener("click", function () {
				addCreateLineRow({});
			});
		}
		var createBtn = document.getElementById("usis-c-create-submit");
		if (createBtn) {
			createBtn.addEventListener("click", function () {
				if (!projectId) return;
				var kind = document.getElementById("usis-c-create-kind").value;
				var vid = document.getElementById("usis-c-create-vendor-id").value;
				if (!vid) {
					toastErr("Select a vendor.");
					return;
				}
				if (!document.getElementById("usis-c-create-title").value.trim()) {
					toastErr("PO subject is required.");
					return;
				}
				if (kind === "purchase_order" && !document.getElementById("usis-c-create-ref").value.trim()) {
					toastErr("PO # is required.");
					return;
				}
				var payload = buildCreatePayload(kind);
				fetchJsonBody("POST", "/api/v1/projects/" + encodeURIComponent(projectId) + "/commitments", payload)
					.then(function () {
						toastOk("Commitment created.");
						if (createModal && window.bootstrap) {
							window.bootstrap.Modal.getOrCreateInstance(createModal).hide();
						}
						return loadCommitmentsList();
					})
					.catch(function (e) {
						toastErr(e.message || String(e));
					});
			});
		}
		var saveHdr = document.getElementById("usis-c-edit-save");
		if (saveHdr) {
			saveHdr.addEventListener("click", function () {
				var cid = document.getElementById("usis-c-edit-id").value;
				if (!cid || !projectId) return;
				var payload = {
					status: document.getElementById("usis-c-edit-status").value,
					workflow_rule_active: document.getElementById("usis-c-edit-wf").value === "1",
					title: document.getElementById("usis-c-edit-titlefield").value.trim(),
					reference_number: document.getElementById("usis-c-edit-ref").value.trim() || null,
					notes: document.getElementById("usis-c-edit-notes").value.trim() || null,
					currency: document.getElementById("usis-c-edit-currency").value.trim() || "USD",
					vendor_company_id: document.getElementById("usis-c-edit-vendor-id").value || undefined,
					vendor_address_snapshot: document.getElementById("usis-c-edit-vendor-address").value.trim() || null,
					ship_to_address: document.getElementById("usis-c-edit-ship-to").value.trim() || null,
					issued_by_address_snapshot: document.getElementById("usis-c-edit-issued-address").value.trim() || null,
				};
				var sd = document.getElementById("usis-c-edit-status-date").value;
				if (sd) payload.status_effective_date = sd;
				var idate = document.getElementById("usis-c-edit-issue-date").value;
				if (idate) payload.issue_date = idate;
				var rd = document.getElementById("usis-c-edit-reminder-date").value;
				if (rd) payload.reminder_date = rd;
				var pt = document.getElementById("usis-c-edit-po-type").value;
				payload.po_type = pt || null;
				var vc = document.getElementById("usis-c-edit-vendor-contact").value;
				payload.vendor_contact_id = vc || null;
				var ib = document.getElementById("usis-c-edit-issued-by-id").value;
				payload.issued_by_user_id = ib || null;
				var ab = document.getElementById("usis-c-edit-authorized-by-id").value;
				payload.authorized_by_user_id = ab || null;
				var tot = document.getElementById("usis-c-edit-total").value.trim();
				if (tot) payload.total_amount = tot;
				var rw = document.getElementById("usis-c-edit-ret-wrap");
				if (rw && !rw.classList.contains("d-none")) {
					var rp = document.getElementById("usis-c-edit-ret").value.trim();
					if (rp) payload.retention_percentage = rp;
				}
				fetchJsonBody(
					"PATCH",
					"/api/v1/projects/" + encodeURIComponent(projectId) + "/commitments/" + encodeURIComponent(cid),
					payload
				)
					.then(function () {
						toastOk("Saved.");
						return openEditModal(cid);
					})
					.catch(function (e) {
						toastErr(e.message || String(e));
					});
			});
		}
		var addLine = document.getElementById("usis-c-line-add");
		if (addLine) {
			addLine.addEventListener("click", function () {
				var cid = document.getElementById("usis-c-edit-id").value;
				if (!cid) return;
				var body = {
					description: document.getElementById("usis-c-line-desc").value.trim() || "Line",
					quantity: document.getElementById("usis-c-line-qty").value.trim() || "0",
					unit: document.getElementById("usis-c-line-unit").value.trim() || "EA",
					unit_cost: document.getElementById("usis-c-line-cost").value.trim() || "0",
				};
				var ino = document.getElementById("usis-c-line-itemno").value.trim();
				if (ino) body.item_number = ino;
				var cc = document.getElementById("usis-c-line-cc").value;
				if (cc) body.cost_code_id = cc;
				var tax = document.getElementById("usis-c-line-tax").value;
				if (tax) body.tax_code = tax;
				var res = document.getElementById("usis-c-line-resource").value;
				if (res) body.resource = res;
				var del = document.getElementById("usis-c-line-delivery").value;
				if (del) body.delivery_date = del;
				fetchJsonBody(
					"POST",
					"/api/v1/projects/" + encodeURIComponent(projectId) + "/commitments/" + encodeURIComponent(cid) + "/line-items",
					body
				)
					.then(function () {
						document.getElementById("usis-c-line-desc").value = "";
						document.getElementById("usis-c-line-qty").value = "";
						document.getElementById("usis-c-line-cost").value = "";
						toastOk("Line added.");
						return openEditModal(cid);
					})
					.catch(function (e) {
						toastErr(e.message || String(e));
					});
			});
		}
		var addBill = document.getElementById("usis-c-bill-add");
		if (addBill) {
			addBill.addEventListener("click", function () {
				var cid = document.getElementById("usis-c-edit-id").value;
				if (!cid) return;
				var ref = document.getElementById("usis-c-bill-ref").value.trim();
				var amt = document.getElementById("usis-c-bill-amt").value.trim();
				if (!ref || !amt) {
					toastErr("Bill ref and amount required.");
					return;
				}
				var body = { vendor_bill_ref: ref, allocated_amount: amt };
				var bd = document.getElementById("usis-c-bill-date").value;
				if (bd) body.billed_at = bd;
				fetchJsonBody(
					"POST",
					"/api/v1/projects/" + encodeURIComponent(projectId) + "/commitments/" + encodeURIComponent(cid) + "/bill-allocations",
					body
				)
					.then(function () {
						document.getElementById("usis-c-bill-ref").value = "";
						document.getElementById("usis-c-bill-amt").value = "";
						document.getElementById("usis-c-bill-date").value = "";
						toastOk("Bill allocation added.");
						return openEditModal(cid);
					})
					.catch(function (e) {
						toastErr(e.message || String(e));
					});
			});
		}
		var delC = document.getElementById("usis-c-edit-delete");
		if (delC) {
			delC.addEventListener("click", function () {
				var cid = document.getElementById("usis-c-edit-id").value;
				if (!cid || !projectId) return;
				if (!window.confirm("Delete this commitment and all lines/bills?")) return;
				fetchEmpty(
					"DELETE",
					"/api/v1/projects/" + encodeURIComponent(projectId) + "/commitments/" + encodeURIComponent(cid)
				)
					.then(function () {
						var modal = document.getElementById("usis-modal-commitment-edit");
						if (modal && window.bootstrap) {
							window.bootstrap.Modal.getOrCreateInstance(modal).hide();
						}
						toastOk("Deleted.");
						return loadCommitmentsList();
					})
					.catch(function (e) {
						toastErr(e.message || String(e));
					});
			});
		}
	}
	wireVendorComboboxes();
	if (document.readyState === "loading") {
		document.addEventListener("DOMContentLoaded", wire);
	} else {
		wire();
	}
})();
