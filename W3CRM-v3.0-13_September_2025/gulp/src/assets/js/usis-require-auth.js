/**
 * Redirects to Gulp ``page-login.html`` when the API reports no session.
 * Set ``window.USIS_SKIP_AUTH_GUARD = true`` on a page to disable (debug only).
 */
(function () {
	"use strict";

	if (window.USIS_SKIP_AUTH_GUARD) return;
	if (location.protocol === "file:") return;

	var p = (location.pathname || "").replace(/\\/g, "/").toLowerCase();
	var authPages =
		p.indexOf("page-login") !== -1 ||
		p.indexOf("page-register") !== -1 ||
		p.indexOf("page-forgot-password") !== -1 ||
		p.indexOf("page-reset-password") !== -1 ||
		p.indexOf("page-lock-screen") !== -1 ||
		p.indexOf("apply.html") !== -1 ||
		p.indexOf("/apply/") !== -1 ||
		p.indexOf("usis-hr-hire.html") !== -1;
	if (authPages) return;

	function apiBase() {
		if (typeof window.usisApiBase === "function") {
			return window.usisApiBase();
		}
		if (typeof window.USIS_API_BASE === "string") {
			return window.USIS_API_BASE.trim().replace(/\/$/, "");
		}
		var h = location.hostname || "";
		var port = String(location.port || "");
		var protocol = location.protocol || "";
		if (protocol === "https:" || port === "443" || port === "10000" || port === "") {
			return "";
		}
		if (h === "localhost" || h === "127.0.0.1") {
			return (protocol + "//" + h + ":5000").replace(/\/$/, "");
		}
		return "";
	}

	function isProductionHttps() {
		return location.protocol === "https:";
	}

	function isLocalDev() {
		var h = location.hostname || "";
		return h === "localhost" || h === "127.0.0.1" || h === "::1";
	}

	function startActivityTracking() {
		var lastInputAt = Date.now();
		var HB_MS = 45000;
		var IDLE_MS = 5 * 60 * 1000;

		function activityBody(extra) {
			var out = {
				path: (location.pathname || "") + (location.search || ""),
				title: document.title || "",
				visible: document.visibilityState === "visible",
			};
			if (extra) {
				for (var k in extra) {
					if (Object.prototype.hasOwnProperty.call(extra, k)) out[k] = extra[k];
				}
			}
			return JSON.stringify(out);
		}

		function postActivity(url, extra) {
			try {
				fetch(apiBase() + url, {
					method: "POST",
					credentials: "include",
					headers: { "Content-Type": "application/json", Accept: "application/json" },
					body: activityBody(extra),
					keepalive: true,
				}).catch(function () {});
			} catch (e) {}
		}

		function markInput() {
			lastInputAt = Date.now();
		}

		["pointerdown", "keydown", "scroll", "mousemove", "touchstart"].forEach(function (ev) {
			document.addEventListener(ev, markInput, { passive: true });
		});

		function tickHeartbeat() {
			if (document.visibilityState !== "visible") return;
			if (Date.now() - lastInputAt > IDLE_MS) return;
			postActivity("/api/v1/me/activity/heartbeat");
		}

		postActivity("/api/v1/me/activity/page-view");
		tickHeartbeat();
		setInterval(tickHeartbeat, HB_MS);
		document.addEventListener("visibilitychange", function () {
			if (document.visibilityState === "visible") {
				markInput();
				tickHeartbeat();
			}
		});
	}

	function redirectToLogin() {
		var here = location.href.split("#")[0];
		window.location.assign("/page-login.html?next=" + encodeURIComponent(here));
	}

	fetch(apiBase() + "/api/v1/auth/status", { credentials: "include", cache: "no-store" })
		.then(function (r) {
			if (!r.ok) {
				if (isProductionHttps()) {
					redirectToLogin();
					return null;
				}
				throw new Error("auth status " + r.status);
			}
			return r.json();
		})
		.then(function (body) {
			if (body === null) return;
			if (body && body.authenticated) {
				if (window.USISDrawingCache && typeof window.USISDrawingCache.refresh === "function") {
					window.USISDrawingCache.refresh();
				}
				startActivityTracking();
				return;
			}
			redirectToLogin();
		})
		.catch(function () {
			if (isProductionHttps()) {
				redirectToLogin();
				return;
			}
			if (!isLocalDev()) {
				redirectToLogin();
			}
		});
})();
