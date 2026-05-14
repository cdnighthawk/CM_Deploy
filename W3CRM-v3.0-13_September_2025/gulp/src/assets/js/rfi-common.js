/**
 * Shared helpers for the Procore-parity RFI tool (log / create / detail pages).
 *
 * Exposes a single ``window.USIS_RFI`` namespace; each page-specific script
 * (``rfis-log.js``, ``rfi-create.js``, ``rfi-detail.js``) builds on top.
 */
(function () {
	"use strict";

	function apiBase() {
		var loc = window.location;
		var devPorts = {
			3000: 1, 3001: 1, 3002: 1, 4173: 1, 5173: 1, 5174: 1, 5500: 1, 5501: 1,
			8080: 1, 4200: 1, 4321: 1, 9630: 1, 1234: 1,
		};
		function isLoopbackHost(h) {
			return h === "localhost" || h === "127.0.0.1" || h === "[::1]" || h === "::1";
		}
		function flaskDevBase() {
			if (loc.protocol === "file:") return "http://127.0.0.1:5000";
			var host = loc.hostname || "";
			var proto = loc.protocol || "http:";
			var port = String(loc.port || "");
			if (devPorts[port]) return proto + "//" + host + ":5000";
			if (host === "localhost" || host === "127.0.0.1" || host === "::1") {
				return port === "5000" ? "" : proto + "//" + host + ":5000";
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
		function resolveOverride(s) {
			if (!s || !String(s).trim()) return null;
			var t = String(s).trim().replace(/\/$/, "");
			try {
				var u = new URL(t);
				if (u.origin === loc.origin) return flaskDevBase();
				if (isLoopbackHost(u.hostname) && devPorts[String(u.port || "")]) {
					var p = loc.protocol || "http:";
					return p + "//" + (loc.hostname || u.hostname) + ":5000";
				}
				return t;
			} catch (e) {
				return t;
			}
		}
		if (typeof window.USIS_API_BASE === "string" && window.USIS_API_BASE.trim()) {
			var w = resolveOverride(window.USIS_API_BASE);
			if (w !== null) return w;
		}
		return flaskDevBase();
	}

	function actorHeaders() {
		var id = null;
		try {
			id = window.localStorage.getItem("usisActorUserId");
		} catch (e) {}
		if (id && id.trim()) return { "X-Usis-User-Id": id.trim() };
		return {};
	}

	function buildUrl(path, params) {
		var base = apiBase();
		var url = base + path;
		if (params) {
			var qs = [];
			Object.keys(params).forEach(function (k) {
				var v = params[k];
				if (v === undefined || v === null || v === "") return;
				if (Array.isArray(v)) {
					qs.push(encodeURIComponent(k) + "=" + encodeURIComponent(v.join(",")));
				} else {
					qs.push(encodeURIComponent(k) + "=" + encodeURIComponent(String(v)));
				}
			});
			if (qs.length) url += (url.indexOf("?") === -1 ? "?" : "&") + qs.join("&");
		}
		return url;
	}

	function fetchJson(path, opts) {
		var o = opts || {};
		var url = typeof path === "string" ? buildUrl(path, o.params) : path;
		var headers = Object.assign({ Accept: "application/json" }, actorHeaders(), o.headers || {});
		var init = {
			method: o.method || "GET",
			headers: headers,
			credentials: "include",
		};
		if (o.body !== undefined) {
			if (typeof FormData !== "undefined" && o.body instanceof FormData) {
				init.body = o.body;
			} else {
				init.headers["Content-Type"] = "application/json";
				init.body = JSON.stringify(o.body);
			}
		}
		return fetch(url, init).then(function (res) {
			var ct = res.headers.get("content-type") || "";
			if (!res.ok) {
				return res.text().then(function (t) {
					var msg = t;
					try {
						if (ct.indexOf("application/json") !== -1) {
							var j = JSON.parse(t);
							msg = j.error || j.message || t;
						}
					} catch (e) {}
					var err = new Error(msg || res.statusText || ("HTTP " + res.status));
					err.status = res.status;
					throw err;
				});
			}
			if (ct.indexOf("application/json") === -1) return res.text();
			return res.json();
		});
	}

	function esc(s) {
		if (s == null || s === "") return "";
		var d = document.createElement("div");
		d.textContent = String(s);
		return d.innerHTML;
	}

	function escAttr(s) {
		return String(s == null ? "" : s)
			.replace(/&/g, "&amp;")
			.replace(/"/g, "&quot;")
			.replace(/</g, "&lt;");
	}

	function fmtDate(s) {
		if (!s) return "";
		var d = new Date(s);
		if (isNaN(+d)) return s;
		return d.toLocaleDateString();
	}

	function fmtDateTime(s) {
		if (!s) return "";
		var d = new Date(s);
		if (isNaN(+d)) return s;
		return d.toLocaleString();
	}

	function fmtMoney(v) {
		if (v == null || v === "") return "";
		var n = Number(v);
		if (!isFinite(n)) return String(v);
		return n.toLocaleString(undefined, { style: "currency", currency: "USD" });
	}

	function impactLabel(choice) {
		switch ((choice || "").toLowerCase()) {
			case "yes": return "Yes";
			case "yes_unknown": return "Yes (Unknown)";
			case "no": return "No";
			case "tbd": return "TBD";
			case "na": return "N/A";
			default: return "—";
		}
	}

	function statusLabel(s) {
		switch ((s || "").toLowerCase()) {
			case "draft": return "Draft";
			case "open": return "Open";
			case "closed": return "Closed";
			case "closed_draft": return "Closed-Draft";
			default: return s || "—";
		}
	}

	function loadProjects() {
		return fetchJson("/api/v1/projects?limit=500").then(function (data) {
			return data.items || [];
		});
	}

	function loadUsers(query) {
		return fetchJson("/api/v1/rfi-users", { params: { q: query || "" } }).then(
			function (data) { return data.items || []; }
		);
	}

	function loadCompanies(query) {
		return fetchJson("/api/v1/rfi-companies", { params: { q: query || "" } }).then(
			function (data) { return data.items || []; }
		);
	}

	function loadLookup(projectId, kind) {
		return fetchJson("/api/v1/projects/" + encodeURIComponent(projectId) + "/rfi-lookups/" + kind)
			.then(function (data) { return data.items || []; });
	}

	function loadCustomFieldDefs() {
		return fetchJson("/api/v1/rfi-custom-field-defs").then(function (data) {
			return data.items || [];
		});
	}

	function loadConfigurableFields(projectId) {
		return fetchJson(
			"/api/v1/rfi-configurable-fields",
			{ params: { project_id: projectId || "" } }
		).then(function (data) { return data.items || []; });
	}

	function listRfis(projectId, params) {
		var p = Object.assign({}, params || {});
		return fetchJson(
			"/api/v1/projects/" + encodeURIComponent(projectId) + "/rfis",
			{ params: p }
		);
	}

	function getRfi(rfiId) {
		return fetchJson("/api/v1/rfis/" + encodeURIComponent(rfiId));
	}

	function createRfi(projectId, payload) {
		return fetchJson(
			"/api/v1/projects/" + encodeURIComponent(projectId) + "/rfis",
			{ method: "POST", body: payload }
		);
	}

	function patchRfi(rfiId, payload) {
		return fetchJson(
			"/api/v1/rfis/" + encodeURIComponent(rfiId),
			{ method: "PATCH", body: payload }
		);
	}

	function deleteRfi(rfiId) {
		return fetchJson(
			"/api/v1/rfis/" + encodeURIComponent(rfiId),
			{ method: "DELETE" }
		);
	}

	function listSavedViews(projectId) {
		return fetchJson(
			"/api/v1/rfi-saved-views",
			{ params: { project_id: projectId || "" } }
		).then(function (d) { return d.items || []; });
	}

	function createSavedView(payload) {
		return fetchJson("/api/v1/rfi-saved-views", { method: "POST", body: payload });
	}

	function deleteSavedView(viewId) {
		return fetchJson(
			"/api/v1/rfi-saved-views/" + encodeURIComponent(viewId),
			{ method: "DELETE" }
		);
	}

	function getColumnPrefs(scopeKey) {
		return fetchJson("/api/v1/rfi-column-prefs/" + encodeURIComponent(scopeKey));
	}

	function putColumnPrefs(scopeKey, payload) {
		return fetchJson(
			"/api/v1/rfi-column-prefs/" + encodeURIComponent(scopeKey),
			{ method: "PUT", body: payload }
		);
	}

	function uploadRfiAttachment(rfiId, file) {
		var fd = new FormData();
		fd.append("file", file, file.name || "attachment");
		var url = buildUrl("/api/v1/rfis/" + encodeURIComponent(rfiId) + "/attachments/upload");
		return fetch(url, {
			method: "POST",
			credentials: "include",
			headers: actorHeaders(),
			body: fd,
		}).then(function (res) {
			var ct = res.headers.get("content-type") || "";
			if (!res.ok) {
				return res.text().then(function (t) {
					var msg = t;
					try {
						if (ct.indexOf("application/json") !== -1) {
							var j = JSON.parse(t);
							msg = j.error || j.message || t;
						}
					} catch (e) {}
					var err = new Error(msg || res.statusText || ("HTTP " + res.status));
					err.status = res.status;
					throw err;
				});
			}
			return res.json();
		});
	}

	function localStore(key) {
		return {
			get: function () {
				try { return JSON.parse(localStorage.getItem(key) || "null"); }
				catch (e) { return null; }
			},
			set: function (v) {
				try { localStorage.setItem(key, JSON.stringify(v)); }
				catch (e) {}
			},
			clear: function () {
				try { localStorage.removeItem(key); } catch (e) {}
			},
		};
	}

	function flashError(el, msg) {
		if (!el) return;
		if (!msg) {
			el.classList.add("d-none");
			el.textContent = "";
			return;
		}
		el.classList.remove("d-none");
		el.textContent = String(msg);
		try { window.scrollTo({ top: 0, behavior: "smooth" }); } catch (e) {}
	}

	function debounce(fn, ms) {
		var t = null;
		return function () {
			var ctx = this, args = arguments;
			clearTimeout(t);
			t = setTimeout(function () { fn.apply(ctx, args); }, ms || 200);
		};
	}

	function queryParam(name) {
		return new URLSearchParams(window.location.search).get(name);
	}

	window.USIS_RFI = {
		apiBase: apiBase,
		actorHeaders: actorHeaders,
		buildUrl: buildUrl,
		fetchJson: fetchJson,
		uploadRfiAttachment: uploadRfiAttachment,
		esc: esc,
		escAttr: escAttr,
		fmtDate: fmtDate,
		fmtDateTime: fmtDateTime,
		fmtMoney: fmtMoney,
		impactLabel: impactLabel,
		statusLabel: statusLabel,
		loadProjects: loadProjects,
		loadUsers: loadUsers,
		loadCompanies: loadCompanies,
		loadLookup: loadLookup,
		loadCustomFieldDefs: loadCustomFieldDefs,
		loadConfigurableFields: loadConfigurableFields,
		listRfis: listRfis,
		getRfi: getRfi,
		createRfi: createRfi,
		patchRfi: patchRfi,
		deleteRfi: deleteRfi,
		listSavedViews: listSavedViews,
		createSavedView: createSavedView,
		deleteSavedView: deleteSavedView,
		getColumnPrefs: getColumnPrefs,
		putColumnPrefs: putColumnPrefs,
		localStore: localStore,
		flashError: flashError,
		debounce: debounce,
		queryParam: queryParam,
	};
})();
