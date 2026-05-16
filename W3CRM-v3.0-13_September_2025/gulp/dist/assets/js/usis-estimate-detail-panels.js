/**
 * Estimate detail — Job information, Drawings, Specs (static), RFI tabs.
 * Listens for CustomEvent "usis-lead-estimate-loaded" { detail: { item, error? } } from usis-estimate-detail.js.
 * When item.project_id is set, loads project job + drawings + RFIs (same APIs as project detail).
 */
(function () {
	"use strict";

	var docPanels =
		typeof window.USISProjectDocPanels !== "undefined"
			? window.USISProjectDocPanels.init({
					returnUrl: true,
					projectIdGlobalKey: "__USIS_ESTIMATE_PROJECT_ID__",
					panes: {
						drawings: "estd-pane-drawings",
						specs: "estd-pane-specs",
						rfi: "estd-pane-rfi",
					},
					ids: {
						drawingsNoProject: "usis-estd-drawings-no-project",
						drawingsTools: "usis-estd-drawings-tools",
						drawingUploadOpen: "usis-estd-drawing-upload-open",
						gridDrawings: "usis-estd-grid-drawings",
						searchDrawings: "usis-estd-search-drawings",
						filterDrawingDiscipline: "usis-estd-filter-drawing-discipline",
						filterDrawingSet: "usis-estd-filter-drawing-set",
						specsNoProject: "usis-estd-specs-no-project",
						specsRoot: "usis-estd-specs-root",
						specsOpenFull: "usis-estd-specs-open-full",
						rfiNoProject: "usis-estd-rfi-no-project",
						rfiTools: "usis-estd-rfi-tools",
						rfiOpenLog: "usis-estd-rfi-open-log",
						rfiOpenCreate: "usis-estd-rfi-open-create",
						searchRfis: "usis-estd-search-rfis",
						filterRfiStatus: "usis-estd-filter-rfi-status",
						tbodyRfis: "usis-estd-tbody-rfis",
						drawingUploadSubmit: "usis-estd-drawing-upload-submit",
						drawingUploadErr: "usis-estd-drawing-upload-err",
						drawingFile: "usis-estd-drawing-file",
						drawingSheetno: "usis-estd-drawing-sheetno",
						drawingTitle: "usis-estd-drawing-title",
						drawingDisc: "usis-estd-drawing-disc",
						drawingSet: "usis-estd-drawing-set",
						drawingRev: "usis-estd-drawing-rev",
						modalDrawingCreate: "usis-estd-modal-drawing-create",
					},
			  })
			: null;

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
		if (typeof window.usisApiBase === "function") {
			return window.usisApiBase();
		}
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
		if (devPorts[port]) return "";
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
		return fetch(url, {
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

	function onLeadEstimateLoaded(ev) {
		var d = ev.detail || {};
		var item = d.item;
		var err = d.error;

		if (docPanels) docPanels.reset();

		if (err || !item) {
			setJobLoading(false);
			setJobErr(err || "Estimate not loaded.");
			var jr = document.getElementById("usis-estd-job-root");
			if (jr) jr.classList.add("d-none");
			if (docPanels) docPanels.showNoProject();
			return;
		}

		loadJobPanel(item);

		if (docPanels) {
			if (item.project_id) docPanels.loadProject(item.project_id);
			else docPanels.showNoProject();
		}
	}

	document.addEventListener("usis-lead-estimate-loaded", onLeadEstimateLoaded);

	document.addEventListener("DOMContentLoaded", function () {
		var id = new URLSearchParams(window.location.search).get("id");
		if (!id || !String(id).trim()) {
			setJobLoading(false);
			setJobErr("No lead id in URL — open this page from the Estimates table.");
			if (docPanels) docPanels.showNoProject();
		}
	});
})();
