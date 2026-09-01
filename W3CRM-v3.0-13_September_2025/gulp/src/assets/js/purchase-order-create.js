/**
 * Create Purchase Order page — same sectioned layout as RFI / Submittal create.
 *
 * Project is taken from ``?project_id=`` (or the active project context).
 * Creates via ``POST /api/v1/projects/<id>/commitments``.
 */
(function () {
	"use strict";

	var state = {
		projectId: null,
		costCodes: [],
		taxCodes: [],
		poTypes: [],
		lineCounter: 0,
		vendorSearchTimer: null,
	};

	function $(id) {
		return document.getElementById(id);
	}

	function t(key) {
		return window.USISI18n && typeof window.USISI18n.tr === "function" ? window.USISI18n.tr(key) : key;
	}

	function esc(s) {
		if (s == null || s === "") return "";
		var d = document.createElement("div");
		d.textContent = String(s);
		return d.innerHTML;
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
		return new URLSearchParams(window.location.search).get(name);
	}

	function currentProjectHint() {
		var fromQuery = queryParam("project_id") || queryParam("projectId") || queryParam("id");
		if (fromQuery) return fromQuery;
		if (window.USISProjectContext && typeof window.USISProjectContext.getProjectId === "function") {
			var fromCtx = window.USISProjectContext.getProjectId();
			if (fromCtx) return fromCtx;
		}
		try {
			return window.sessionStorage.getItem("usis.activeProjectId") || null;
		} catch (e) {
			return null;
		}
	}

	function rememberProject(projectId) {
		if (!projectId) return;
		if (window.USISProjectContext && typeof window.USISProjectContext.setProjectId === "function") {
			window.USISProjectContext.setProjectId(projectId);
		}
	}

	function todayIso() {
		var d = new Date();
		return d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0") + "-" + String(d.getDate()).padStart(2, "0");
	}

	function flashError(msg) {
		var el = $("usis-po-error");
		if (!el) return;
		if (!msg) {
			el.classList.add("d-none");
			el.textContent = "";
			return;
		}
		el.classList.remove("d-none");
		el.textContent = String(msg);
		try {
			window.scrollTo({ top: 0, behavior: "smooth" });
		} catch (e) {}
	}

	function dash(s) {
		if (s == null || String(s).trim() === "") return "—";
		return String(s).trim();
	}

	function formatProjectAddress(item) {
		if (!item) return "—";
		var street = [item.address_line1, item.address_line2].filter(Boolean).join(", ");
		var cityLine = [item.city, item.state, item.postal_code].filter(Boolean).join(" ");
		if (item.country && item.country !== "US") {
			cityLine = (cityLine ? cityLine + ", " : "") + item.country;
		}
		var parts = [street, cityLine].filter(Boolean);
		return parts.length ? parts.join(" · ") : "—";
	}

	function formatTypeStatus(item) {
		if (!item) return "—";
		var bits = [item.project_type, item.status].filter(function (x) {
			return x && String(x).trim();
		});
		return bits.length ? bits.join(" · ") : "—";
	}

	function setText(id, value) {
		var el = $(id);
		if (el) el.textContent = value;
	}

	function renderProjectCard(item) {
		var card = $("usis-po-project-card");
		if (!card) return;
		if (!item) {
			card.classList.add("d-none");
			return;
		}
		setText("usis-po-proj-number", dash(item.number));
		setText("usis-po-proj-name", dash(item.name));
		setText("usis-po-proj-type-status", formatTypeStatus(item));
		setText("usis-po-proj-address", formatProjectAddress(item));
		card.classList.remove("d-none");
	}

	function fillSelect(sel, items, options) {
		options = options || {};
		if (!sel) return;
		var current = sel.value;
		sel.innerHTML = "";
		var blank = document.createElement("option");
		blank.value = "";
		blank.textContent = t(options.emptyLabel || "—");
		sel.appendChild(blank);
		(items || []).forEach(function (it) {
			var opt = document.createElement("option");
			opt.value = it.id;
			opt.textContent = it.label;
			sel.appendChild(opt);
		});
		if (current) sel.value = current;
	}

	function fillSelectOptions(sel, items, valueKey, labelFn, selectedVal) {
		if (!sel) return;
		sel.innerHTML = '<option value="">—</option>';
		(items || []).forEach(function (it) {
			var o = document.createElement("option");
			o.value = it[valueKey];
			o.textContent = labelFn(it);
			if (selectedVal && String(selectedVal) === String(it[valueKey])) o.selected = true;
			sel.appendChild(o);
		});
	}

	function projectReturnHref() {
		if (!state.projectId) return "construction/project-detail.html";
		return "construction/project-detail.html?id=" + encodeURIComponent(state.projectId);
	}

	function stampCancelLinks() {
		["usis-po-cancel", "usis-po-cancel-footer"].forEach(function (id) {
			var a = $(id);
			if (a) a.setAttribute("href", projectReturnHref());
		});
	}

	function hideComboboxMenu(menu) {
		if (menu) menu.classList.add("d-none");
	}

	function wireEntityCombobox(inputId, menuId, hiddenId, searchFn, onPick) {
		var input = $(inputId);
		var menu = $(menuId);
		var hidden = $(hiddenId);
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
			clearTimeout(state.vendorSearchTimer);
			var q = input.value.trim();
			if (q.length < 1) {
				hideComboboxMenu(menu);
				return;
			}
			state.vendorSearchTimer = setTimeout(function () {
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
		if (!state.projectId) return Promise.resolve([]);
		return fetchJson(
			"/api/v1/projects/" + encodeURIComponent(state.projectId) + "/directory/companies?q=" + encodeURIComponent(q) + "&limit=20"
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

	function loadVendorProfile(companyId) {
		if (!companyId) return Promise.resolve();
		return fetchJson("/api/v1/companies/" + encodeURIComponent(companyId) + "/procurement-profile").then(function (data) {
			var item = data.item || {};
			var addr = $("usis-po-vendor-address");
			if (addr && item.address) addr.value = item.address;
			var csel = $("usis-po-vendor-contact");
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

	function costCodeOptionsHtml(selected) {
		var html = '<option value="">—</option>';
		state.costCodes.forEach(function (cc) {
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
		state.taxCodes.forEach(function (t) {
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

	function defaultPrefill() {
		return {
			cost_code_id: ($("usis-po-def-cc") || {}).value || "",
			tax_code: ($("usis-po-def-tax") || {}).value || "",
			resource: ($("usis-po-def-resource") || {}).value || "",
			delivery_date: ($("usis-po-def-delivery") || {}).value || "",
		};
	}

	function addLineRow(prefill) {
		var tb = $("usis-po-lines-tbody");
		if (!tb) return;
		state.lineCounter += 1;
		var p = Object.assign(defaultPrefill(), prefill || {});
		var tr = document.createElement("tr");
		tr.innerHTML =
			'<td><input class="form-control form-control-sm usis-po-line-itemno" value="' +
			esc(p.item_number || String(state.lineCounter)) +
			'"></td>' +
			'<td><input class="form-control form-control-sm usis-po-line-desc" value="' +
			esc(p.description || "") +
			'"></td>' +
			'<td><input class="form-control form-control-sm usis-po-line-qty" value="' +
			esc(p.quantity != null ? p.quantity : "") +
			'"></td>' +
			'<td><input class="form-control form-control-sm usis-po-line-unit" value="' +
			esc(p.unit || "EA") +
			'"></td>' +
			'<td><input class="form-control form-control-sm usis-po-line-cost" value="' +
			esc(p.unit_cost != null ? p.unit_cost : "") +
			'"></td>' +
			'<td><select class="form-select form-select-sm usis-po-line-cc">' +
			costCodeOptionsHtml(p.cost_code_id) +
			"</select></td>" +
			'<td><select class="form-select form-select-sm usis-po-line-tax">' +
			taxOptionsHtml(p.tax_code) +
			"</select></td>" +
			'<td><select class="form-select form-select-sm usis-po-line-resource">' +
			resourceOptionsHtml(p.resource) +
			"</select></td>" +
			'<td><input type="date" class="form-control form-control-sm usis-po-line-delivery" value="' +
			esc(p.delivery_date || "") +
			'"></td>' +
			'<td class="text-end"><button type="button" class="btn btn-link btn-sm text-danger p-0 usis-po-line-rm">×</button></td>';
		tb.appendChild(tr);
		tr.querySelector(".usis-po-line-rm").addEventListener("click", function () {
			tr.remove();
		});
	}

	function collectLineItems() {
		var rows = document.querySelectorAll("#usis-po-lines-tbody tr");
		var out = [];
		rows.forEach(function (tr, idx) {
			var desc = tr.querySelector(".usis-po-line-desc");
			var qty = tr.querySelector(".usis-po-line-qty");
			if (!desc || !String(desc.value || "").trim()) return;
			var body = {
				item_number: (tr.querySelector(".usis-po-line-itemno") || {}).value || String(idx + 1),
				description: String(desc.value).trim(),
				quantity: qty && qty.value.trim() ? qty.value.trim() : "0",
				unit: (tr.querySelector(".usis-po-line-unit") || {}).value || "EA",
				unit_cost: (tr.querySelector(".usis-po-line-cost") || {}).value || "0",
				sort_order: idx,
			};
			var cc = tr.querySelector(".usis-po-line-cc");
			if (cc && cc.value) body.cost_code_id = cc.value;
			var tax = tr.querySelector(".usis-po-line-tax");
			if (tax && tax.value) body.tax_code = tax.value;
			var res = tr.querySelector(".usis-po-line-resource");
			if (res && res.value) body.resource = res.value;
			var del = tr.querySelector(".usis-po-line-delivery");
			if (del && del.value) body.delivery_date = del.value;
			out.push(body);
		});
		return out;
	}

	function buildPayload(statusOverride) {
		var status = statusOverride || ($("usis-po-status") || {}).value || "draft";
		var payload = {
			commitment_kind: "purchase_order",
			vendor_company_id: ($("usis-po-vendor-id") || {}).value,
			reference_number: (($("usis-po-ref") || {}).value || "").trim() || null,
			title: (($("usis-po-title") || {}).value || "").trim(),
			status: status,
			currency: (($("usis-po-currency") || {}).value || "").trim() || "USD",
			notes: (($("usis-po-notes") || {}).value || "").trim() || null,
		};
		var sd = ($("usis-po-status-date") || {}).value;
		if (sd) payload.status_effective_date = sd;
		else if (status !== "draft") payload.status_effective_date = todayIso();
		var idate = ($("usis-po-issue-date") || {}).value;
		if (idate) payload.issue_date = idate;
		var pt = ($("usis-po-type") || {}).value;
		if (pt) payload.po_type = pt;
		var rd = ($("usis-po-reminder-date") || {}).value;
		if (rd) payload.reminder_date = rd;
		var vc = ($("usis-po-vendor-contact") || {}).value;
		if (vc) payload.vendor_contact_id = vc;
		var va = (($("usis-po-vendor-address") || {}).value || "").trim();
		if (va) payload.vendor_address_snapshot = va;
		var ib = ($("usis-po-issued-by-id") || {}).value;
		if (ib) payload.issued_by_user_id = ib;
		var ab = ($("usis-po-authorized-by-id") || {}).value;
		if (ab) payload.authorized_by_user_id = ab;
		var ia = (($("usis-po-issued-address") || {}).value || "").trim();
		if (ia) payload.issued_by_address_snapshot = ia;
		var ship = (($("usis-po-ship-to") || {}).value || "").trim();
		if (ship) payload.ship_to_address = ship;
		var dd = ($("usis-po-def-delivery") || {}).value;
		if (dd) payload.default_delivery_date = dd;
		var dcc = ($("usis-po-def-cc") || {}).value;
		if (dcc) payload.default_cost_code_id = dcc;
		var dt = ($("usis-po-def-tax") || {}).value;
		if (dt) payload.default_tax_code = dt;
		var dr = ($("usis-po-def-resource") || {}).value;
		if (dr) payload.default_resource = dr;
		var lines = collectLineItems();
		if (lines.length) payload.line_items = lines;
		return payload;
	}

	function setBusy(on) {
		["usis-po-btn-draft", "usis-po-btn-create", "usis-po-btn-draft-footer", "usis-po-btn-create-footer"].forEach(function (id) {
			var el = $(id);
			if (el) el.disabled = !!on;
		});
	}

	function submit(statusOverride) {
		flashError("");
		if (!state.projectId) {
			flashError(t("Choose a project."));
			return;
		}
		if (!($("usis-po-vendor-id") || {}).value) {
			flashError("Select a vendor.");
			return;
		}
		if (!(($("usis-po-title") || {}).value || "").trim()) {
			flashError("PO subject is required.");
			return;
		}
		if (!(($("usis-po-ref") || {}).value || "").trim()) {
			flashError("PO # is required.");
			return;
		}
		var payload = buildPayload(statusOverride);
		setBusy(true);
		fetchJson("/api/v1/projects/" + encodeURIComponent(state.projectId) + "/commitments", {
			method: "POST",
			body: payload,
		})
			.then(function () {
				if (window.USISNotify && window.USISNotify.success) {
					window.USISNotify.success("Purchase order created.");
				}
				window.location.href = projectReturnHref();
			})
			.catch(function (err) {
				flashError(err.message || String(err));
				if (window.USISNotify && window.USISNotify.error) {
					window.USISNotify.error(err.message || String(err));
				}
				setBusy(false);
			});
	}

	function loadLookups() {
		if (!state.projectId) return Promise.resolve();
		var pid = encodeURIComponent(state.projectId);
		return Promise.all([
			fetchJson("/api/v1/projects/" + pid + "/rfi-lookups/cost_codes").then(function (data) {
				state.costCodes = data.items || [];
				fillSelectOptions($("usis-po-def-cc"), state.costCodes, "id", function (cc) {
					return cc.code + (cc.description ? " — " + cc.description : "");
				});
			}),
			fetchJson("/api/v1/projects/" + pid + "/rfi-lookups/tax_codes").then(function (data) {
				state.taxCodes = data.items || [];
				fillSelectOptions($("usis-po-def-tax"), state.taxCodes, "code", function (t) {
					return t.label || t.code;
				});
			}),
			fetchJson("/api/v1/procurement/po-types").then(function (data) {
				state.poTypes = data.items || [];
				fillSelectOptions($("usis-po-type"), state.poTypes, "code", function (t) {
					return t.label;
				});
			}),
			fetchJson("/api/v1/projects/" + pid + "/procurement/defaults").then(function (data) {
				var item = (data && data.item) || {};
				var ship = $("usis-po-ship-to");
				if (ship && item.ship_to_address && !ship.value) ship.value = item.ship_to_address;
				var iss = $("usis-po-issue-date");
				if (iss && item.issue_date && !iss.value) iss.value = item.issue_date;
			}).catch(function () {}),
			fetchJson("/api/v1/projects/" + pid).then(function (data) {
				renderProjectCard(data.item || null);
			}).catch(function () {
				renderProjectCard(null);
			}),
		]).then(function () {
			refreshExistingLineSelects();
		});
	}

	function refreshExistingLineSelects() {
		document.querySelectorAll("#usis-po-lines-tbody tr").forEach(function (tr) {
			var cc = tr.querySelector(".usis-po-line-cc");
			var tax = tr.querySelector(".usis-po-line-tax");
			var res = tr.querySelector(".usis-po-line-resource");
			if (cc) {
				var cv = cc.value;
				cc.innerHTML = costCodeOptionsHtml(cv);
			}
			if (tax) {
				var tv = tax.value;
				tax.innerHTML = taxOptionsHtml(tv);
			}
			if (res) {
				var rv = res.value;
				res.innerHTML = resourceOptionsHtml(rv);
			}
		});
	}

	function loadProjects() {
		return fetchJson("/api/v1/projects?limit=2000").then(function (data) {
			var rows = data.items || [];
			fillSelect(
				$("usis-po-project"),
				rows.map(function (p) {
					return { id: p.id, label: (p.number ? p.number + " · " : "") + p.name };
				}),
				{ emptyLabel: "Select project…" }
			);
			var hint = currentProjectHint();
			var sel = $("usis-po-project");
			if (hint && sel) {
				sel.value = hint;
				if (sel.value !== hint) {
					var opt = document.createElement("option");
					opt.value = hint;
					opt.textContent = hint;
					sel.appendChild(opt);
					sel.value = hint;
				}
			}
			state.projectId = (sel && sel.value) || hint || null;
			if (state.projectId) rememberProject(state.projectId);
			stampCancelLinks();
			return state.projectId;
		});
	}

	function wireComboboxes() {
		wireEntityCombobox("usis-po-vendor-q", "usis-po-vendor-menu", "usis-po-vendor-id", searchDirectoryCompanies, function (it) {
			var hint = $("usis-po-vendor-dir-hint");
			var addBtn = $("usis-po-vendor-add-dir");
			if (hint && addBtn) {
				if (it.in_directory) {
					hint.classList.add("d-none");
					addBtn.classList.add("d-none");
				} else {
					hint.textContent = "Vendor is not in the project directory.";
					hint.classList.remove("d-none");
					addBtn.classList.remove("d-none");
					addBtn.onclick = function () {
						fetchJson("/api/v1/projects/" + encodeURIComponent(state.projectId) + "/directory/companies", {
							method: "POST",
							body: { company_id: it.id },
						})
							.then(function () {
								if (window.USISNotify && window.USISNotify.success) {
									window.USISNotify.success("Added to project directory.");
								}
								hint.classList.add("d-none");
								addBtn.classList.add("d-none");
							})
							.catch(function (e) {
								flashError(e.message || String(e));
							});
					};
				}
			}
			loadVendorProfile(it.id);
		});
		wireEntityCombobox("usis-po-issued-by-q", "usis-po-issued-by-menu", "usis-po-issued-by-id", searchUsers, null);
		wireEntityCombobox("usis-po-authorized-by-q", "usis-po-authorized-by-menu", "usis-po-authorized-by-id", searchUsers, null);
	}

	function wire() {
		var add = $("usis-po-line-add");
		if (add) {
			add.addEventListener("click", function () {
				addLineRow({});
			});
		}
		function onDraft() {
			submit("draft");
		}
		function onCreate() {
			submit(($("usis-po-status") || {}).value || "draft");
		}
		["usis-po-btn-draft", "usis-po-btn-draft-footer"].forEach(function (id) {
			var el = $(id);
			if (el) el.addEventListener("click", onDraft);
		});
		["usis-po-btn-create", "usis-po-btn-create-footer"].forEach(function (id) {
			var el = $(id);
			if (el) el.addEventListener("click", onCreate);
		});
		var sel = $("usis-po-project");
		if (sel) {
			sel.addEventListener("change", function () {
				state.projectId = sel.value || null;
				if (state.projectId) rememberProject(state.projectId);
				stampCancelLinks();
				loadLookups().catch(function (err) {
					flashError(err.message || String(err));
				});
			});
		}
		wireComboboxes();
	}

	function loadCreatedBy() {
		var el = $("usis-po-created-by-display");
		if (!el) return;
		fetchJson("/api/v1/me")
			.then(function (data) {
				var u = data.item || data.user || data;
				var name = "";
				if (u) {
					name = [u.first_name, u.last_name].filter(Boolean).join(" ").trim();
					if (!name) name = u.name || u.email || "";
				}
				el.textContent = name || "—";
			})
			.catch(function () {
				el.textContent = "—";
			});
	}

	function init() {
		var iss = $("usis-po-issue-date");
		if (iss && !iss.value) iss.value = todayIso();
		wire();
		loadCreatedBy();
		loadProjects()
			.then(function () {
				if (!state.projectId) {
					flashError(t("Choose a project."));
					return;
				}
				return loadLookups();
			})
			.then(function () {
				if ($("usis-po-lines-tbody") && !$("usis-po-lines-tbody").children.length) {
					addLineRow({});
				}
			})
			.catch(function (err) {
				flashError(err.message || String(err));
			});
	}

	if (document.readyState === "loading") {
		document.addEventListener("DOMContentLoaded", init);
	} else {
		init();
	}
})();
