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
			if (body && body.authenticated) return;
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
