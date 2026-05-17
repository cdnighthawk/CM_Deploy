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
	function fetchJson(path) {
		var base = apiBase();
		return fetch(base + path, { credentials: "omit" }).then(function (res) {
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
			credentials: "omit",
			headers: { "Content-Type": "application/json" },
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
		return fetch(base + path, { method: method, credentials: "omit" }).then(function (res) {
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
	function loadVendorsForCreate() {
		var sel = document.getElementById("usis-c-create-vendor");
		if (!sel) return Promise.resolve();
		return fetchJson("/api/v1/rfi-companies?limit=300").then(function (data) {
			sel.innerHTML = "";
			var items = (data.items || []).filter(function (c) {
				var t = (c.company_type || "").toLowerCase();
				return t === "vendor" || t === "subcontractor" || t === "gc" || t === "other";
			});
			items.forEach(function (c) {
				var o = document.createElement("option");
				o.value = c.id;
				o.textContent = c.name + " (" + c.company_type + ")";
				sel.appendChild(o);
			});
			if (!sel.options.length) {
				var o2 = document.createElement("option");
				o2.value = "";
				o2.textContent = "— add companies first —";
				sel.appendChild(o2);
			}
		});
	}
	function loadCostCodes() {
		if (!projectId) return Promise.resolve();
		return fetchJson("/api/v1/projects/" + encodeURIComponent(projectId) + "/rfi-lookups/cost_codes").then(function (data) {
			costCodesCache = data.items || [];
			var sel = document.getElementById("usis-c-line-cc");
			if (!sel) return;
			sel.innerHTML = '<option value="">—</option>';
			costCodesCache.forEach(function (cc) {
				var o = document.createElement("option");
				o.value = cc.id;
				o.textContent = cc.code + (cc.description ? " — " + cc.description : "");
				sel.appendChild(o);
			});
		});
	}
	function configureCreateModalForKind(kind) {
		var k = kind === "subcontract" ? "subcontract" : "purchase_order";
		var kindSel = document.getElementById("usis-c-create-kind");
		if (kindSel) kindSel.value = k;
		var wrap = document.getElementById("usis-c-create-kind-wrap");
		if (wrap) wrap.classList.add("d-none");
		var titleEl = document.getElementById("usis-c-create-modal-title");
		if (titleEl) titleEl.textContent = k === "subcontract" ? "New subcontract" : "New purchase order";
		var refLab = document.getElementById("usis-c-create-ref-label");
		var refInp = document.getElementById("usis-c-create-ref");
		if (refLab) {
			refLab.textContent = k === "subcontract" ? "Contract # (optional)" : "PO # (optional)";
		}
		if (refInp) {
			refInp.placeholder = k === "subcontract" ? "SUB-201" : "PO-1001";
		}
	}
	function openEditModal(cid) {
		if (!projectId || !cid) return;
		return fetchJson(
			"/api/v1/projects/" + encodeURIComponent(projectId) + "/commitments/" + encodeURIComponent(cid)
		)
			.then(function (data) {
				var item = data.item;
				document.getElementById("usis-c-edit-id").value = item.id;
				document.getElementById("usis-c-edit-modal-label").textContent =
					kindLabel(item.commitment_kind) + " — " + (item.reference_number || item.title || item.id);
				document.getElementById("usis-c-edit-vendorline").textContent =
					"Vendor: " + (item.vendor_name || item.vendor_company_id);
				var rfpWrap = document.getElementById("usis-c-edit-rfp-link-wrap");
				var rfpA = document.getElementById("usis-c-edit-rfp-link");
				if (item.rfp_id && rfpWrap && rfpA) {
					rfpA.href = "../usis-rfp-detail.html?id=" + encodeURIComponent(item.rfp_id);
					rfpA.textContent = item.rfp_title || "Open linked RFP";
					rfpWrap.classList.remove("d-none");
				} else if (rfpWrap) {
					rfpWrap.classList.add("d-none");
				}
				document.getElementById("usis-c-edit-status").value = item.status || "draft";
				document.getElementById("usis-c-edit-wf").value = item.workflow_rule_active ? "1" : "0";
				document.getElementById("usis-c-edit-titlefield").value = item.title || "";
				document.getElementById("usis-c-edit-ref").value = item.reference_number || "";
				document.getElementById("usis-c-edit-notes").value = item.notes || "";
				document.getElementById("usis-c-edit-total").value = item.total_amount != null ? item.total_amount : "";
				var rw = document.getElementById("usis-c-edit-ret-wrap");
				var ret = document.getElementById("usis-c-edit-ret");
				if (item.commitment_kind === "subcontract") {
					rw.classList.remove("d-none");
					ret.value = item.retention_percentage != null ? item.retention_percentage : "";
				} else {
					rw.classList.add("d-none");
					ret.value = "";
				}
				renderLinesTable(data.line_items || []);
				renderBillsTable(data.bill_allocations || []);
				return loadCostCodes();
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
				esc(li.description) +
				"</td><td>" +
				esc(li.quantity) +
				"</td><td>" +
				esc(li.unit) +
				"</td><td>" +
				esc(li.unit_cost) +
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
				loadVendorsForCreate().catch(function () {
					toastErr("Could not load vendor list.");
				});
			});
		}
		var createBtn = document.getElementById("usis-c-create-submit");
		if (createBtn) {
			createBtn.addEventListener("click", function () {
				if (!projectId) return;
				var vid = document.getElementById("usis-c-create-vendor").value;
				if (!vid) {
					toastErr("Select a vendor.");
					return;
				}
				var payload = {
					commitment_kind: document.getElementById("usis-c-create-kind").value,
					vendor_company_id: vid,
					title: document.getElementById("usis-c-create-title").value.trim() || "Commitment",
					reference_number: document.getElementById("usis-c-create-ref").value.trim() || null,
				};
				fetchJsonBody("POST", "/api/v1/projects/" + encodeURIComponent(projectId) + "/commitments", payload)
					.then(function () {
						toastOk("Commitment created.");
						if (createModal && window.bootstrap) {
							window.bootstrap.Modal.getOrCreateInstance(createModal).hide();
						}
						document.getElementById("usis-c-create-title").value = "";
						document.getElementById("usis-c-create-ref").value = "";
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
				};
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
				var cc = document.getElementById("usis-c-line-cc").value;
				if (cc) body.cost_code_id = cc;
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
	if (document.readyState === "loading") {
		document.addEventListener("DOMContentLoaded", wire);
	} else {
		wire();
	}
})();
