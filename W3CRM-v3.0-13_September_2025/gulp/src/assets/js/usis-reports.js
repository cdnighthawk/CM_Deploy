/**
 * Reports page — load GET /api/v1/reports/catalog and open parameterized HTML print routes.
 */
(function () {
	"use strict";

	var DEV_SERVER_PORTS = {
		3000: 1,
		3001: 1,
		3002: 1,
		3003: 1,
		3004: 1,
		3005: 1,
		3006: 1,
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

	function isLikelyStaticDevPort(portStr) {
		if (DEV_SERVER_PORTS[portStr]) return true;
		var n = parseInt(portStr, 10);
		return !isNaN(n) && n >= 3000 && n <= 3099;
	}

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
		if (typeof window.usisApiBase === "function") return window.usisApiBase();
		var fromWin = explicitWindowApiBase();
		if (fromWin) return fromWin;
		var fromMeta = metaApiBase();
		if (fromMeta) return fromMeta;
		var loc = window.location;
		if (loc.protocol === "file:") return "http://127.0.0.1:5000";
		var host = loc.hostname || "";
		var proto = loc.protocol || "http:";
		var port = String(loc.port || "");
		if (isLikelyStaticDevPort(port)) return proto + "//" + host + ":5000";
		var loopback = host === "localhost" || host === "127.0.0.1" || host === "::1";
		if (loopback) {
			if (port === "5000") return "";
			return proto + "//" + host + ":5000";
		}
		return "";
	}

	function esc(s) {
		return String(s == null ? "" : s)
			.replace(/&/g, "&amp;")
			.replace(/</g, "&lt;")
			.replace(/"/g, "&quot;");
	}

	function escAttr(s) {
		return String(s == null ? "" : s)
			.replace(/&/g, "&amp;")
			.replace(/"/g, "&quot;")
			.replace(/</g, "&lt;");
	}

	function showErr(msg) {
		var el = document.getElementById("usis-reports-catalog-error");
		if (!el) return;
		if (!msg) {
			el.classList.add("d-none");
			el.textContent = "";
			return;
		}
		el.textContent = msg;
		el.classList.remove("d-none");
	}

	function fetchJson(path) {
		var b = (apiBase() || "").replace(/\/$/, "");
		var url = b ? b + path : path;
		return fetch(url, { credentials: "include", headers: { Accept: "application/json" } }).then(function (r) {
			return r.text().then(function (text) {
				var j = {};
				try {
					j = text ? JSON.parse(text) : {};
				} catch (e) {
					throw new Error("Server did not return JSON (" + r.status + ")");
				}
				if (!r.ok) throw new Error((j && j.error) || "HTTP " + r.status);
				return j;
			});
		});
	}

	function groupByCategory(items) {
		var m = {};
		for (var i = 0; i < items.length; i++) {
			var it = items[i];
			var cat = it.category || "Other";
			if (!m[cat]) m[cat] = [];
			m[cat].push(it);
		}
		return m;
	}

	var pendingReport = null;

	function buildUrlFromTemplate(rep, values) {
		var tpl = rep.url_template || "";
		var path = tpl;
		var req = rep.required_params || [];
		for (var i = 0; i < req.length; i++) {
			var nm = req[i].name;
			var val = values[nm];
			if (val == null || String(val).trim() === "") throw new Error("Missing: " + (req[i].label || nm));
			path = path.split("{" + nm + "}").join(encodeURIComponent(String(val).trim()));
		}
		if (path.indexOf("{") >= 0) throw new Error("Unresolved URL placeholders — check catalog.");
		var opt = rep.optional_params || [];
		var qs = [];
		for (var j = 0; j < opt.length; j++) {
			var o = opt[j];
			var v = values[o.name];
			if (v != null && String(v).trim() !== "") {
				qs.push(encodeURIComponent(o.name) + "=" + encodeURIComponent(String(v).trim()));
			}
		}
		if (qs.length) path += (path.indexOf("?") >= 0 ? "&" : "?") + qs.join("&");
		return path;
	}

	function openModalForReport(rep) {
		pendingReport = rep;
		var title = document.getElementById("usis-report-open-title");
		if (title) title.textContent = rep.title || "Open report";
		var wrap = document.getElementById("usis-report-open-fields");
		if (!wrap) return;
		var html = "";
		var params = (rep.required_params || []).concat(rep.optional_params || []);
		for (var i = 0; i < params.length; i++) {
			var p = params[i];
			var id = "usis-rp-" + rep.id + "-" + p.name;
			html +=
				'<div class="mb-2">' +
				'<label class="form-label small mb-0" for="' +
				id +
				'">' +
				esc(p.label || p.name) +
				"</label>" +
				'<input type="text" class="form-control form-control-sm usis-report-param" data-name="' +
				esc(p.name) +
				'" id="' +
				id +
				'" placeholder="' +
				esc(p.hint || "") +
				'">' +
				(p.hint ? '<div class="form-text">' + esc(p.hint) + "</div>" : "") +
				"</div>";
		}
		var cols = rep.column_options || [];
		var savedColIds = null;
		if (cols.length && rep.id && window.localStorage) {
			try {
				var rawLs = localStorage.getItem("usis_report_columns_" + rep.id);
				if (rawLs) savedColIds = JSON.parse(rawLs);
			} catch (eLs) {
				savedColIds = null;
			}
		}
		if (cols.length) {
			html +=
				'<div class="mt-3 pt-2 border-top"><div class="fw-semibold small mb-2">Quote table columns</div>' +
				'<div class="row row-cols-1 g-1">';
			for (var j = 0; j < cols.length; j++) {
				var c = cols[j];
				var cid = String(c.id || "");
				var lid = "usis-rp-col-" + rep.id + "-" + cid;
				var chk = "";
				if (Array.isArray(savedColIds)) {
					chk = savedColIds.indexOf(cid) >= 0 ? " checked" : "";
				} else if (c.default) {
					chk = " checked";
				}
				html +=
					'<div class="col"><div class="form-check">' +
					'<input class="form-check-input usis-report-col" type="checkbox" id="' +
					lid +
					'" data-col-id="' +
					escAttr(cid) +
					'"' +
					chk +
					'>' +
					'<label class="form-check-label small" for="' +
					lid +
					'">' +
					esc(c.label || cid) +
					"</label></div></div>";
			}
			html += "</div></div>";
		}
		wrap.innerHTML = html;
		var modal = document.getElementById("usis-report-open-modal");
		if (modal && window.bootstrap) window.bootstrap.Modal.getOrCreateInstance(modal).show();
	}

	function submitModal() {
		if (!pendingReport) return;
		var wrap = document.getElementById("usis-report-open-fields");
		var inputs = wrap ? wrap.querySelectorAll(".usis-report-param") : [];
		var values = {};
		for (var i = 0; i < inputs.length; i++) {
			var inp = inputs[i];
			var nm = inp.getAttribute("data-name");
			if (nm) values[nm] = inp.value;
		}
		try {
			var path = buildUrlFromTemplate(pendingReport, values);
			var cboxes = wrap ? wrap.querySelectorAll(".usis-report-col:checked") : [];
			var colIds = [];
			for (var k = 0; k < cboxes.length; k++) {
				var rawId = cboxes[k].getAttribute("data-col-id");
				if (rawId) colIds.push(rawId);
			}
			if (wrap && wrap.querySelectorAll(".usis-report-col").length && pendingReport.id && window.localStorage) {
				try {
					localStorage.setItem("usis_report_columns_" + pendingReport.id, JSON.stringify(colIds));
				} catch (eSave) {
					/* ignore */
				}
			}
			if (colIds.length) {
				var q = "columns=" + encodeURIComponent(colIds.join(","));
				path += path.indexOf("?") >= 0 ? "&" + q : "?" + q;
			}
			var b = (apiBase() || "").replace(/\/$/, "");
			var url = (b ? b : "") + path;
			window.open(url, "_blank", "noopener,noreferrer");
			var modal = document.getElementById("usis-report-open-modal");
			if (modal && window.bootstrap) {
				var inst = bootstrap.Modal.getInstance(modal);
				if (inst) inst.hide();
			}
			showErr("");
		} catch (e) {
			if (window.USISNotify) window.USISNotify.error(e.message);
			else showErr(e.message);
		}
	}

	function renderCatalog(items) {
		var root = document.getElementById("usis-reports-catalog-root");
		if (!root) return;
		if (!items.length) {
			root.innerHTML = '<p class="text-muted small">No reports in catalog.</p>';
			return;
		}
		var byCat = groupByCategory(items);
		var cats = Object.keys(byCat).sort();
		var html = "";
		for (var c = 0; c < cats.length; c++) {
			var cat = cats[c];
			var list = byCat[cat];
			html += '<div class="col-12 col-lg-6 col-xxl-4">';
			html += '<div class="card border h-100"><div class="card-header py-2"><strong class="small">' + esc(cat) + "</strong></div>";
			html += '<ul class="list-group list-group-flush small">';
			for (var i = 0; i < list.length; i++) {
				var rep = list[i];
				html += '<li class="list-group-item py-2">';
				html += "<div><strong>" + esc(rep.title) + "</strong></div>";
				html += '<div class="text-muted">' + esc(rep.description || "") + "</div>";
				if (rep.kind === "external") {
					html += '<span class="badge bg-secondary mt-1">In-page / external</span>';
				} else {
					html +=
						'<button type="button" class="btn btn-sm btn-outline-primary mt-2 usis-report-open" data-id="' +
						esc(rep.id) +
						'">Open…</button>';
				}
				html += "</li>";
			}
			html += "</ul></div></div>";
		}
		root.innerHTML = html;
		root.querySelectorAll(".usis-report-open").forEach(function (btn) {
			btn.addEventListener("click", function () {
				var rid = btn.getAttribute("data-id");
				var rep = items.find(function (x) {
					return x.id === rid;
				});
				if (rep) openModalForReport(rep);
			});
		});
	}

	function init() {
		var submit = document.getElementById("usis-report-open-submit");
		if (submit) submit.addEventListener("click", submitModal);
		fetchJson("/api/v1/reports/catalog")
			.then(function (data) {
				showErr("");
				renderCatalog(data.items || []);
			})
			.catch(function (e) {
				showErr(e.message);
				var root = document.getElementById("usis-reports-catalog-root");
				if (root) root.innerHTML = "";
			});
	}

	if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
	else init();
})();
