/**
 * Reports page — Power BI embed via GET /api/v1/powerbi/embed-config.
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
		/* BrowserSync often uses 3000–3008 (or similar) when defaults are busy. */
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

	function embedUrl(base) {
		var path = "/api/v1/powerbi/embed-config";
		var b = (base || "").replace(/\/$/, "");
		return b ? b + path : path;
	}

	function setStatus(el, text, kind) {
		if (!el) return;
		el.textContent = text || "";
		el.className = "small mb-2";
		if (kind === "error") {
			el.classList.add("alert", "alert-danger", "py-2", "px-3");
		} else if (text) {
			el.classList.add("alert", "alert-info", "py-2", "px-3");
		} else {
			el.classList.add("text-muted");
		}
	}

	function setEmbedVisible(embedEl, show) {
		if (!embedEl) return;
		if (show) embedEl.classList.remove("d-none");
		else embedEl.classList.add("d-none");
	}

	function embedReport(embedEl, data) {
		var pbi = window.powerbi;
		if (!pbi || typeof pbi.embed !== "function") {
			return "Power BI client library did not load. Check the network tab for blocked CDN scripts.";
		}
		try {
			if (typeof pbi.reset === "function") {
				pbi.reset(embedEl);
			}
		} catch (e) {
			/* first load may have nothing to reset */
		}
		var tokenType = 1;
		var layoutType = 0;
		var displayOption = 0;
		var backgroundType = 0;
		try {
			if (pbi.models && pbi.models.TokenType && pbi.models.TokenType.Embed != null) {
				tokenType = pbi.models.TokenType.Embed;
			}
			if (pbi.models && pbi.models.LayoutType && pbi.models.LayoutType.Custom != null) {
				layoutType = pbi.models.LayoutType.Custom;
			}
			if (pbi.models && pbi.models.DisplayOption && pbi.models.DisplayOption.FitToWidth != null) {
				displayOption = pbi.models.DisplayOption.FitToWidth;
			}
			if (pbi.models && pbi.models.BackgroundType && pbi.models.BackgroundType.Transparent != null) {
				backgroundType = pbi.models.BackgroundType.Transparent;
			}
		} catch (e2) {
			tokenType = 1;
		}
		var cfg = {
			type: "report",
			tokenType: tokenType,
			accessToken: data.embedToken,
			embedUrl: data.embedUrl,
			id: data.reportId,
			settings: {
				layoutType: layoutType,
				customLayout: {
					displayOption: displayOption,
				},
				background: backgroundType,
				panes: {
					filters: { expanded: false, visible: false },
					pageNavigation: { visible: true },
				},
			},
		};
		var report = pbi.embed(embedEl, cfg);
		if (report && typeof report.on === "function") {
			report.on("loaded", function () {
				var iframe = embedEl.querySelector("iframe");
				if (iframe) {
					iframe.style.width = "100%";
					iframe.style.height = "100%";
				}
				if (typeof report.setPageView === "function") {
					report.setPageView("fitToWidth");
				}
			});
		}
		return null;
	}

	document.addEventListener("DOMContentLoaded", function () {
		var statusEl = document.getElementById("usis-powerbi-status");
		var embedEl = document.getElementById("usis-powerbi-embed");
		if (!statusEl || !embedEl) return;

		setEmbedVisible(embedEl, false);
		setStatus(statusEl, "Checking Power BI configuration…", "info");

		var url = embedUrl(apiBase());
		var headers = Object.assign({ Accept: "application/json" }, actorHeaders());

		fetch(url, { method: "GET", credentials: "include", headers: headers })
			.then(function (res) {
				if (!res.ok) {
					return res.text().then(function (t) {
						var msg = "Power BI configuration request failed (HTTP " + res.status + ").";
						if (t) msg += " " + String(t).slice(0, 280);
						throw new Error(msg);
					});
				}
				return res.json();
			})
			.then(function (data) {
				if (data && data.error) {
					setStatus(statusEl, String(data.error), "error");
					setEmbedVisible(embedEl, false);
					return;
				}
				if (!data || data.configured !== true) {
					var missing = Array.isArray(data.missing_env) ? data.missing_env : [];
					var parts = [];
					parts.push(data.message || "Power BI embed is not configured on the server.");
					if (missing.length) {
						parts.push("Missing: " + missing.join(", ") + ".");
					}
					parts.push(
						"Set POWERBI_TENANT_ID, POWERBI_CLIENT_ID, POWERBI_CLIENT_SECRET, POWERBI_WORKSPACE_ID, and POWERBI_REPORT_ID in the API environment (see backend/.env.example), restart Flask, and ensure the app registration (service principal) has access to the workspace."
					);
					setStatus(statusEl, parts.join(" "), "info");
					setEmbedVisible(embedEl, false);
					return;
				}
				var err = embedReport(embedEl, data);
				if (err) {
					setStatus(statusEl, err, "error");
					setEmbedVisible(embedEl, false);
					return;
				}
				setStatus(statusEl, "", null);
				setEmbedVisible(embedEl, true);
			})
			.catch(function (e) {
				setStatus(statusEl, e && e.message ? e.message : String(e), "error");
				setEmbedVisible(embedEl, false);
			});
	});
})();
