/**
 * Redirect job applicants away from staff CM pages (client-side backup to server shell gate).
 */
(function () {
	"use strict";

	if (window.USIS_SKIP_APPLICANT_GUARD) return;
	if (location.protocol === "file:") return;

	var path = (location.pathname || "").replace(/\\/g, "/").toLowerCase();
	var publicPages =
		path.indexOf("apply.html") !== -1 ||
		path.indexOf("/apply/") !== -1 ||
		path.indexOf("page-login") !== -1 ||
		path.indexOf("page-register") !== -1 ||
		path.indexOf("page-forgot-password") !== -1 ||
		path.indexOf("page-reset-password") !== -1 ||
		path.indexOf("page-lock-screen") !== -1 ||
		path.indexOf("usis-hr-hire.html") !== -1;
	if (publicPages) return;

	function apiBase() {
		if (typeof window.usisApiBase === "function") return window.usisApiBase();
		if (typeof window.USIS_API_BASE === "string" && window.USIS_API_BASE.trim()) {
			return window.USIS_API_BASE.trim().replace(/\/$/, "");
		}
		var h = location.hostname || "";
		var port = String(location.port || "");
		var protocol = location.protocol || "";
		if (protocol === "https:" || port === "443" || port === "10000" || port === "") return "";
		if (h === "localhost" || h === "127.0.0.1") return protocol + "//" + h + ":5000";
		return "";
	}

	function redirectApplicant() {
		window.location.replace("/apply/application.html");
	}

	fetch(apiBase() + "/api/v1/auth/status", {
		credentials: "include",
		cache: "no-store",
		headers: { Accept: "application/json" },
	})
		.then(function (r) {
			return r.json();
		})
		.then(function (body) {
			if (body && body.authenticated && body.applicant_only) redirectApplicant();
		})
		.catch(function () {});
})();
