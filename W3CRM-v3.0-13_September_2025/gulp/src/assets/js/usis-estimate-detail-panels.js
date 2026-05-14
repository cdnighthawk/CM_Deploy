/**
 * Estimate detail — Job information, Drawings, Specs (static), RFI tabs.
 * Listens for CustomEvent "usis-lead-estimate-loaded" { detail: { item, error? } } from usis-estimate-detail.js.
 * When item.project_id is set, loads project job + drawings + RFIs (same APIs as project detail).
 */
(function () {
	"use strict";

	var cache = { drawingSheets: [], rfis: [] };
	var filtersWired = false;
	var drawingsTabulator = null;
	var activeProjectId = null;

	function explicitWindowApiBase() {
		if (typeof window.USIS_API_BASE !== "string") return null;
		var s = window.USIS_API_BASE.trim().replace(/\/$/, "");
		if (!s) return null;
		try {
			if (new URL(s).origin === window.location.origin) return null;
		} catch (e) {
			/* keep s */
		}
		return s;
	}

	function metaApiBase() {
		if (typeof document === "undefined" || !document.querySelector) return null;
		var m = document.querySelector('meta[name="usis-api-base"]');
		if (!m) return null;
		var c = (m.getAttribute("content") || "").trim().replace(/\/$/, "");
		return c || null;
	}

	function apiBase() {
		var fromWin = explicitWindowApiBase();
		if (fromWin) return fromWin;
		var fromMeta = metaApiBase();
		if (fromMeta) return fromMeta;
		var loc = window.location;
		if (loc.protocol === "file:") return "http://127.0.0.1:5000";
		var host = loc.hostname || "";
		var proto = loc.protocol || "http:";
		var port = String(loc.port || "");
		var devPorts = {
			3000: 1,
			3001: 1,
			3002: 1,
			4173: 1,
			5173: 1,
			5174: 1,
			5500: 1,
			5501: 1,
			8080: 1,
			4200: 1,
			4321: 1,
			9630: 1,
			1234: 1,
		};
		if (devPorts[port]) return proto + "//" + host + ":5000";
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

	function resolveAssetUrl(u) {
		if (u == null || u === "") return "";
		var s = String(u).trim();
		if (!s) return "";
		if (/^https?:\/\//i.test(s)) return s;
		var b = apiBase();
		return b + (s.charAt(0) === "/" ? s : "/" + s);
	}

	function esc(s) {
		if (s == null) return "";
		var d = document.createElement("div");
		d.textContent = String(s);
		return d.innerHTML;
	}

	function fmtDash(s) {
		if (s == null || String(s).trim() === "") return '<span class="text-muted">—</span>';
		return esc(String(s).trim());
	}

	function fmtDate(iso) {
		if (!iso) return '<span class="text-muted">—</span>';
		try {
			var d = new Date(iso);
			if (isNaN(d.getTime())) return esc(String(iso));
			return esc(d.toLocaleDateString());
		} catch (e) {
			return esc(String(iso));
		}
	}

	function fmtMoney(n) {
		if (n == null || n === "") return '<span class="text-muted">—</span>';
		var x = Number(n);
		if (isNaN(x)) return esc(String(n));
		try {
			return esc(
				x.toLocaleString(undefined, { style: "currency", currency: "USD", maximumFractionDigits: 2 })
			);
		} catch (e) {
			return esc(String(x));
		}
	}

	function tr(label, innerHtml) {
		return (
			"<tr><th class=\"text-muted small fw-normal\" style=\"width:42%\">" +
			esc(label) +
			"</th><td>" +
			innerHtml +
			"</td></tr>"
		);
	}

	function setJobLoading(show) {
		var pane = document.getElementById("estd-pane-job");
		if (!pane) return;
		var n = pane.querySelector("[data-usis-estd-job-loading]");
		if (n) n.classList.toggle("d-none", !show);
	}

	function setJobErr(msg) {
		var pane = document.getElementById("estd-pane-job");
		if (!pane) return;
		var n = pane.querySelector("[data-usis-estd-job-error]");
		if (!n) return;
		if (msg) {
			n.textContent = msg;
			n.classList.remove("d-none");
		} else {
			n.textContent = "";
			n.classList.add("d-none");
		}
	}

	function setPaneLoading(paneId, loading) {
		var el = document.getElementById(paneId);
		if (!el) return;
		var n = el.querySelector("[data-usis-loading]");
		if (n) n.classList.toggle("d-none", !loading);
	}

	function setPaneError(paneId, msg) {
		var el = document.getElementById(paneId);
		if (!el) return;
		var n = el.querySelector("[data-usis-error]");
		if (!n) return;
		if (msg) {
			n.textContent = msg;
			n.classList.remove("d-none");
		} else {
			n.textContent = "";
			n.classList.add("d-none");
		}
	}

	function fetchJson(path) {
		var base = apiBase();
		var url = base + path;
		return fetch(url, { credentials: "omit" }).then(function (res) {
			if (!res.ok) {
				return res.text().then(function (t) {
					throw new Error(res.status + " " + (t || res.statusText));
				});
			}
			return res.json();
		});
	}

	function renderJobFromProject(item) {
		var title = document.getElementById("usis-estd-job-title");
		var sub = document.getElementById("usis-estd-job-subtitle");
		var badges = document.getElementById("usis-estd-job-badges");
		var tbody = document.getElementById("usis-estd-job-tbody");
		var notes = document.getElementById("usis-estd-job-notes");
		var extras = document.getElementById("usis-estd-job-extras");
		if (title) title.textContent = item.name || "—";
		if (sub) {
			var bits = [];
			if (item.number) bits.push("#" + item.number);
			if (item.city || item.state) bits.push([item.city, item.state].filter(Boolean).join(", "));
			sub.textContent = bits.join(" · ") || "Active project";
		}
		if (badges) {
			badges.innerHTML =
				'<span class="badge bg-light text-dark border">' +
				esc(item.status || "—") +
				'</span> <span class="badge bg-light text-muted border text-capitalize">' +
				esc((item.project_type || "—").replace(/_/g, " ")) +
				"</span>";
		}
		var addr = [item.address_line1, item.address_line2].filter(Boolean).join(", ");
		var cityLine = [item.city, item.state, item.postal_code].filter(Boolean).join(" ");
		if (item.country && item.country !== "US") cityLine = (cityLine ? cityLine + ", " : "") + item.country;
		var rows = [
			tr("Project id", fmtDash(item.id)),
			tr("Number", fmtDash(item.number)),
			tr("Address", fmtDash(addr || null)),
			tr("City / ZIP", fmtDash(cityLine || null)),
			tr("Contract value", fmtMoney(item.contract_value)),
			tr("Contract date", fmtDate(item.contract_date)),
			tr("Start date", fmtDate(item.start_date)),
			tr("Substantial completion", fmtDate(item.substantial_completion_date)),
			tr("Closeout", fmtDate(item.closeout_date)),
			tr("Retention %", item.retention_percentage != null ? esc(String(item.retention_percentage)) : "—"),
			tr("Prevailing wage", esc(item.prevailing_wage ? "Yes" : "No")),
			tr("DBE required", esc(item.dbe_required ? "Yes" : "No")),
			tr("GC", fmtDash(item.gc_company_name)),
			tr("Owner", fmtDash(item.owner_company_name)),
			tr("Architect", fmtDash(item.architect_company_name)),
			tr("Sage project id", fmtDash(item.sage_project_id)),
		];
		if (tbody) tbody.innerHTML = rows.join("");
		if (notes) {
			notes.innerHTML = item.notes
				? "<div class=\"text-body\">" + esc(item.notes).replace(/\n/g, "<br>") + "</div>"
				: '<span class="text-muted">—</span>';
		}
		if (extras) {
			var bits2 = [];
			if (item.primary_lead_detail_id) {
				var href = "construction/lead-detail.html?id=" + encodeURIComponent(item.primary_lead_detail_id);
				bits2.push('<a class="link-primary" href="' + href + '">Linked lead / opportunity</a>');
			}
			if (item.id) {
				bits2.push(
					'<a class="link-secondary" href="construction/project-detail.html?id=' +
						encodeURIComponent(item.id) +
						'">Open project workspace</a>'
				);
			}
			extras.innerHTML = bits2.length ? bits2.join("<br>") : "";
		}
		var root = document.getElementById("usis-estd-job-root");
		if (root) root.classList.remove("d-none");
	}

	function renderJobFromLead(le) {
		var title = document.getElementById("usis-estd-job-title");
		var sub = document.getElementById("usis-estd-job-subtitle");
		var badges = document.getElementById("usis-estd-job-badges");
		var tbody = document.getElementById("usis-estd-job-tbody");
		var notes = document.getElementById("usis-estd-job-notes");
		var extras = document.getElementById("usis-estd-job-extras");
		if (title) title.textContent = le.name || "—";
		if (sub) {
			sub.textContent = [le.number ? "#" + le.number : "", le.trade_name || ""].filter(Boolean).join(" · ");
		}
		if (badges) {
			var st = le.submission_state || "—";
			var crm = le.crm_stage ? String(le.crm_stage) : "";
			badges.innerHTML =
				'<span class="badge bg-light text-dark border">' +
				esc(st) +
				"</span>" +
				(crm
					? ' <span class="badge bg-light text-muted border">' + esc(crm) + "</span>"
					: "");
		}
		var loc = le.location && typeof le.location === "object" ? le.location : {};
		var city = loc.city != null ? String(loc.city) : le.city || "";
		var state = loc.state != null ? String(loc.state) : le.state || "";
		var locLine = [city, state].filter(function (x) {
			return String(x).trim();
		}).join(", ");
		var rows = [
			tr("Lead id", fmtDash(le.external_id || le.id)),
			tr("Due", fmtDate(le.due_at)),
			tr("Location", fmtDash(locLine || null)),
			tr("Company", fmtDash(le.company_name)),
			tr("ROM", fmtMoney(le.rom)),
			tr("Win probability", le.win_probability != null ? esc(String(le.win_probability)) : "—"),
		];
		if (tbody) tbody.innerHTML = rows.join("");
		if (notes) {
			var pi = le.project_information;
			if (typeof pi === "string" && pi.trim()) {
				notes.innerHTML = "<div class=\"text-body\">" + esc(pi).replace(/\n/g, "<br>") + "</div>";
			} else {
				notes.innerHTML = '<span class="text-muted">—</span>';
			}
		}
		var lid = le.external_id || le.id;
		if (extras) {
			extras.innerHTML =
				'<a class="link-primary" href="construction/lead-detail.html?id=' +
				encodeURIComponent(lid) +
				'">Open full lead / job card</a>' +
				'<br><span class="text-muted">No project linked yet — drawings and RFIs unlock after award / link.</span>';
		}
		var root = document.getElementById("usis-estd-job-root");
		if (root) root.classList.remove("d-none");
	}

	function loadJobPanel(le) {
		setJobErr("");
		setJobLoading(true);
		var rootEl = document.getElementById("usis-estd-job-root");
		if (rootEl) rootEl.classList.add("d-none");
		var pid = le.project_id;
		if (!pid) {
			setJobLoading(false);
			renderJobFromLead(le);
			return;
		}
		fetchJson("/api/v1/projects/" + encodeURIComponent(pid))
			.then(function (data) {
				setJobLoading(false);
				var item = data.item;
				if (!item) throw new Error("Missing project in response");
				renderJobFromProject(item);
			})
			.catch(function (err) {
				setJobLoading(false);
				setJobErr(err.message || String(err));
				renderJobFromLead(le);
			});
	}

	function showNoProjectDrawRfi() {
		var nd = document.getElementById("usis-estd-drawings-no-project");
		var nr = document.getElementById("usis-estd-rfi-no-project");
		var td = document.getElementById("usis-estd-drawings-tools");
		var tr = document.getElementById("usis-estd-rfi-tools");
		var upb = document.getElementById("usis-estd-drawing-upload-open");
		var snp = document.getElementById("usis-estd-specs-no-project");
		var sroot = document.getElementById("usis-estd-specs-root");
		var sfull = document.getElementById("usis-estd-specs-open-full");
		if (nd) {
			nd.classList.remove("d-none");
		}
		if (nr) nr.classList.remove("d-none");
		if (td) td.classList.add("d-none");
		if (tr) tr.classList.add("d-none");
		if (upb) upb.classList.add("d-none");
		if (snp) snp.classList.remove("d-none");
		if (sroot) {
			sroot.classList.add("d-none");
			sroot.innerHTML = "";
		}
		if (sfull) sfull.classList.add("d-none");
		setPaneLoading("estd-pane-drawings", false);
		setPaneLoading("estd-pane-rfi", false);
	}

	function showProjectDrawRfi() {
		var nd = document.getElementById("usis-estd-drawings-no-project");
		var nr = document.getElementById("usis-estd-rfi-no-project");
		var td = document.getElementById("usis-estd-drawings-tools");
		var tr = document.getElementById("usis-estd-rfi-tools");
		var upb = document.getElementById("usis-estd-drawing-upload-open");
		var snp = document.getElementById("usis-estd-specs-no-project");
		var sroot = document.getElementById("usis-estd-specs-root");
		var sfull = document.getElementById("usis-estd-specs-open-full");
		if (nd) nd.classList.add("d-none");
		if (nr) nr.classList.add("d-none");
		if (td) td.classList.remove("d-none");
		if (tr) tr.classList.remove("d-none");
		if (upb) upb.classList.remove("d-none");
		if (snp) snp.classList.add("d-none");
		if (sroot) sroot.classList.remove("d-none");
		if (sfull) sfull.classList.remove("d-none");
	}

	function updateRfiLinks(pid) {
		var open = document.getElementById("usis-estd-rfi-open-log");
		var create = document.getElementById("usis-estd-rfi-open-create");
		if (open) open.setAttribute("href", "construction/rfis.html?project_id=" + encodeURIComponent(pid));
		if (create) create.setAttribute("href", "construction/rfi-create.html?project_id=" + encodeURIComponent(pid));
	}

	function repopulateDrawingFacetSelects(items) {
		var discSel = document.getElementById("usis-estd-filter-drawing-discipline");
		var setSel = document.getElementById("usis-estd-filter-drawing-set");
		var discSet = {};
		var setSet = {};
		(items || []).forEach(function (s) {
			if (s.discipline) discSet[s.discipline] = 1;
			if (s.drawing_set) setSet[s.drawing_set] = 1;
		});
		if (discSel) {
			var curD = discSel.value;
			discSel.innerHTML = '<option value="">All disciplines</option>';
			Object.keys(discSet)
				.sort(function (a, b) {
					return a.localeCompare(b);
				})
				.forEach(function (k) {
					var o = document.createElement("option");
					o.value = k;
					o.textContent = k;
					discSel.appendChild(o);
				});
			if (curD && discSet[curD]) discSel.value = curD;
		}
		if (setSel) {
			var curS = setSel.value;
			setSel.innerHTML = '<option value="">All sets</option>';
			Object.keys(setSet)
				.sort(function (a, b) {
					return a.localeCompare(b);
				})
				.forEach(function (k) {
					var o = document.createElement("option");
					o.value = k;
					o.textContent = k;
					setSel.appendChild(o);
				});
			if (curS && setSet[curS]) setSel.value = curS;
		}
	}

	function filterDrawingSheetsClient(items) {
		var inp = document.getElementById("usis-estd-search-drawings");
		var discSel = document.getElementById("usis-estd-filter-drawing-discipline");
		var setSel = document.getElementById("usis-estd-filter-drawing-set");
		var q = inp && inp.value ? inp.value.trim().toLowerCase() : "";
		var disc = discSel ? discSel.value : "";
		var setv = setSel ? setSel.value : "";
		return (items || []).filter(function (s) {
			if (disc && (s.discipline || "") !== disc) return false;
			if (setv && (s.drawing_set || "") !== setv) return false;
			if (!q) return true;
			return JSON.stringify(s).toLowerCase().indexOf(q) !== -1;
		});
	}

	function buildOrRefreshDrawingsTabulator() {
		var el = document.getElementById("usis-estd-grid-drawings");
		if (!el) return;
		var rows = filterDrawingSheetsClient(cache.drawingSheets);
		if (typeof Tabulator === "undefined") {
			el.innerHTML =
				'<div class="alert alert-warning mb-0">Drawing grid requires Tabulator (CDN). Check your network or CSP.</div>';
			return;
		}
		var pid = activeProjectId || "";
		var cols = [
			{ title: "Sheet #", field: "sheet_number", headerFilter: "input", minWidth: 100, widthGrow: 1 },
			{ title: "Title", field: "sheet_title", headerFilter: "input", minWidth: 160, widthGrow: 2 },
			{ title: "Discipline", field: "discipline", headerFilter: "input", minWidth: 100, widthGrow: 1 },
			{ title: "Set", field: "drawing_set", headerFilter: "input", minWidth: 90, widthGrow: 1 },
			{
				title: "Current rev",
				field: "current_revision",
				minWidth: 110,
				formatter: function (cell) {
					var cr = cell.getValue();
					if (!cr) return "";
					var r = cr.revision != null ? String(cr.revision) : "";
					var v = cr.version != null ? String(cr.version) : "";
					return esc(r) + (v ? " · v" + esc(v) : "");
				},
			},
			{ title: "Revisions", field: "revision_count", hozAlign: "right", width: 100 },
			{
				title: "Updated",
				field: "current_revision",
				width: 170,
				formatter: function (cell) {
					var cr = cell.getValue();
					if (!cr || !cr.updated_at) return "—";
					try {
						return esc(new Date(cr.updated_at).toLocaleString());
					} catch (e) {
						return esc(cr.updated_at);
					}
				},
			},
			{
				title: "",
				hozAlign: "right",
				headerSort: false,
				width: 150,
				formatter: function (cell) {
					var wrap = document.createElement("div");
					wrap.className = "d-flex gap-1 flex-wrap justify-content-end";
					var data = cell.getRow().getData();
					var cr = data.current_revision;
					if (cr && cr.id && pid) {
						var a = document.createElement("a");
						a.href =
							"drawing-viewer.html?project_id=" +
							encodeURIComponent(pid) +
							"&drawing_id=" +
							encodeURIComponent(cr.id);
						a.className = "btn btn-primary btn-sm py-0";
						a.textContent = "View";
						wrap.appendChild(a);
					}
					if (cr && cr.file_url) {
						var p = document.createElement("a");
						p.href = resolveAssetUrl(cr.file_url);
						p.target = "_blank";
						p.rel = "noopener noreferrer";
						p.className = "btn btn-outline-secondary btn-sm py-0";
						p.textContent = "PDF";
						wrap.appendChild(p);
					}
					if (!wrap.childNodes.length) wrap.textContent = "—";
					return wrap;
				},
			},
		];
		if (drawingsTabulator) {
			drawingsTabulator.setData(rows);
			return;
		}
		drawingsTabulator = new Tabulator(el, {
			data: rows,
			layout: "fitColumns",
			pagination: "local",
			paginationSize: 25,
			paginationSizeSelector: [10, 25, 50, 100],
			movableColumns: true,
			placeholder: "No drawings for this project yet.",
			columns: cols,
		});
	}

	function applyDrawingFilter() {
		buildOrRefreshDrawingsTabulator();
	}

	function filterRows(rows, q, statusVal, getStatus) {
		var qq = (q || "").trim().toLowerCase();
		var st = (statusVal || "").trim().toLowerCase();
		return rows.filter(function (r) {
			if (st && String(getStatus(r) || "").toLowerCase() !== st) return false;
			if (!qq) return true;
			return JSON.stringify(r).toLowerCase().indexOf(qq) !== -1;
		});
	}

	function renderRfiTable(tbody, items) {
		if (!tbody) return;
		tbody.innerHTML = "";
		if (!items.length) {
			tbody.innerHTML =
				'<tr><td colspan="8" class="text-muted text-center py-4">No RFIs yet. Use "+ Create RFI" to start the log.</td></tr>';
			return;
		}
		items.forEach(function (row) {
			var tr = document.createElement("tr");
			var num = row.display_number || "RFI-" + row.number;
			var detail = "construction/rfi-detail.html?id=" + encodeURIComponent(row.id);
			var assignees = (row.assignees || [])
				.map(function (a) {
					return esc(a.user ? a.user.name : "");
				})
				.filter(Boolean)
				.join(", ") || "—";
			var mgr = row.rfi_manager ? esc(row.rfi_manager.name) : "—";
			var status = '<span class="text-uppercase small fw-semibold">' + esc(row.status) + "</span>";
			var due = row.due_at ? esc(new Date(row.due_at).toLocaleDateString()) : "—";
			tr.innerHTML =
				'<td><a class="link-primary text-decoration-none" href="' + detail + '">' + esc(num) + "</a></td>" +
				'<td><a class="text-decoration-none text-black fw-semibold" href="' + detail + '">' + esc(row.subject) + "</a></td>" +
				"<td>" + status + "</td>" +
				"<td>" + esc(row.ball_in_court || "—") + "</td>" +
				"<td>" + assignees + "</td>" +
				"<td>" + mgr + "</td>" +
				"<td>" + due + "</td>" +
				'<td class="text-end"><a class="btn btn-link btn-sm" href="' + detail + '">Open</a></td>';
			tbody.appendChild(tr);
		});
	}

	function applyRfiFilter() {
		var inp = document.getElementById("usis-estd-search-rfis");
		var sel = document.getElementById("usis-estd-filter-rfi-status");
		var q = inp ? inp.value : "";
		var st = sel ? sel.value : "";
		var rows = filterRows(cache.rfis, q, st, function (r) {
			return r.status;
		});
		renderRfiTable(document.getElementById("usis-estd-tbody-rfis"), rows);
	}

	function wireFiltersOnce() {
		if (filtersWired) return;
		filtersWired = true;
		var d = document.getElementById("usis-estd-search-drawings");
		if (d) d.addEventListener("input", applyDrawingFilter);
		var dd = document.getElementById("usis-estd-filter-drawing-discipline");
		var ds = document.getElementById("usis-estd-filter-drawing-set");
		if (dd) dd.addEventListener("change", applyDrawingFilter);
		if (ds) ds.addEventListener("change", applyDrawingFilter);
		var r1 = document.getElementById("usis-estd-search-rfis");
		var r2 = document.getElementById("usis-estd-filter-rfi-status");
		if (r1) r1.addEventListener("input", applyRfiFilter);
		if (r2) r2.addEventListener("change", applyRfiFilter);

		var estdDrawUp = document.getElementById("usis-estd-drawing-upload-submit");
		if (estdDrawUp && !estdDrawUp.dataset.usisWired) {
			estdDrawUp.dataset.usisWired = "1";
			estdDrawUp.addEventListener("click", function () {
				var pid = activeProjectId || window.__USIS_ESTIMATE_PROJECT_ID__;
				if (!pid) return;
				var err = document.getElementById("usis-estd-drawing-upload-err");
				var fileEl = document.getElementById("usis-estd-drawing-file");
				if (err) {
					err.classList.add("d-none");
					err.textContent = "";
				}
				if (!fileEl || !fileEl.files || !fileEl.files[0]) {
					if (err) {
						err.textContent = "Choose a PDF file.";
						err.classList.remove("d-none");
					}
					return;
				}
				var fd = new FormData();
				fd.append("file", fileEl.files[0]);
				var sn = document.getElementById("usis-estd-drawing-sheetno");
				var st = document.getElementById("usis-estd-drawing-title");
				var dc = document.getElementById("usis-estd-drawing-disc");
				var dsetForm = document.getElementById("usis-estd-drawing-set");
				var rv = document.getElementById("usis-estd-drawing-rev");
				if (sn && sn.value) fd.append("sheet_number", sn.value);
				if (st && st.value) fd.append("sheet_title", st.value);
				if (dc && dc.value) fd.append("discipline", dc.value);
				if (dsetForm && dsetForm.value) fd.append("drawing_set", dsetForm.value);
				if (rv && rv.value) fd.append("revision", rv.value);
				var url = apiBase() + "/api/v1/projects/" + encodeURIComponent(pid) + "/drawings";
				fetch(url, { method: "POST", body: fd, credentials: "omit" })
					.then(function (res) {
						if (!res.ok) {
							return res.text().then(function (t) {
								throw new Error(res.status + " " + (t || res.statusText));
							});
						}
						return res.json();
					})
					.then(function () {
						var modalEl = document.getElementById("usis-estd-modal-drawing-create");
						if (modalEl && window.bootstrap && window.bootstrap.Modal) {
							var inst = window.bootstrap.Modal.getInstance(modalEl);
							if (inst) inst.hide();
						}
						if (fileEl) fileEl.value = "";
						return loadDrawingsAndRfis(pid);
					})
					.catch(function (e) {
						if (err) {
							err.textContent = e.message || String(e);
							err.classList.remove("d-none");
						}
					});
			});
		}
	}

	function mountEstimateSpecs(projectId) {
		var sroot = document.getElementById("usis-estd-specs-root");
		var sfull = document.getElementById("usis-estd-specs-open-full");
		if (sfull && projectId) {
			sfull.setAttribute("href", "construction/specs-viewer.html?project_id=" + encodeURIComponent(projectId));
		}
		if (!sroot || !projectId || typeof window.USISSpecsBook === "undefined") return;
		sroot.innerHTML = "";
		window.USISSpecsBook.mount(sroot, projectId);
	}

	function loadDrawingsAndRfis(projectId) {
		wireFiltersOnce();
		var pathD =
			"/api/v1/projects/" + encodeURIComponent(projectId) + "/drawings?limit=2000&offset=0";
		var pathR = "/api/v1/projects/" + encodeURIComponent(projectId) + "/rfis";

		setPaneLoading("estd-pane-drawings", true);
		setPaneLoading("estd-pane-rfi", true);
		setPaneError("estd-pane-drawings", "");
		setPaneError("estd-pane-rfi", "");

		return Promise.all([
			fetchJson(pathD)
				.then(function (d) {
					cache.drawingSheets = d.items || [];
					repopulateDrawingFacetSelects(cache.drawingSheets);
					setPaneLoading("estd-pane-drawings", false);
					if (drawingsTabulator) {
						drawingsTabulator.destroy();
						drawingsTabulator = null;
					}
					applyDrawingFilter();
				})
				.catch(function (err) {
					cache.drawingSheets = [];
					setPaneLoading("estd-pane-drawings", false);
					setPaneError("estd-pane-drawings", err.message || String(err));
					if (drawingsTabulator) {
						drawingsTabulator.destroy();
						drawingsTabulator = null;
					}
					applyDrawingFilter();
				}),
			fetchJson(pathR)
				.then(function (d) {
					cache.rfis = d.items || [];
					setPaneLoading("estd-pane-rfi", false);
					applyRfiFilter();
				})
				.catch(function (err) {
					cache.rfis = [];
					setPaneLoading("estd-pane-rfi", false);
					setPaneError("estd-pane-rfi", err.message || String(err));
					applyRfiFilter();
				}),
		]);
	}

	function onLeadEstimateLoaded(ev) {
		var d = ev.detail || {};
		var item = d.item;
		var err = d.error;

		activeProjectId = null;
		window.__USIS_ESTIMATE_PROJECT_ID__ = null;
		cache.drawingSheets = [];
		cache.rfis = [];
		if (drawingsTabulator) {
			try {
				drawingsTabulator.destroy();
			} catch (e) {
				/* ignore */
			}
			drawingsTabulator = null;
		}

		if (err || !item) {
			setJobLoading(false);
			setJobErr(err || "Estimate not loaded.");
			var jr = document.getElementById("usis-estd-job-root");
			if (jr) jr.classList.add("d-none");
			showNoProjectDrawRfi();
			return;
		}

		window.__USIS_ESTIMATE_PROJECT_ID__ = item.project_id || null;
		activeProjectId = item.project_id || null;
		loadJobPanel(item);

		if (activeProjectId) {
			showProjectDrawRfi();
			updateRfiLinks(activeProjectId);
			loadDrawingsAndRfis(activeProjectId).then(function () {
				mountEstimateSpecs(activeProjectId);
			});
		} else {
			showNoProjectDrawRfi();
		}
	}

	document.addEventListener("usis-lead-estimate-loaded", onLeadEstimateLoaded);

	document.addEventListener("DOMContentLoaded", function () {
		var id = new URLSearchParams(window.location.search).get("id");
		if (!id || !String(id).trim()) {
			setJobLoading(false);
			setJobErr("No lead id in URL — open this page from the Estimates table.");
			showNoProjectDrawRfi();
		}
	});
})();
