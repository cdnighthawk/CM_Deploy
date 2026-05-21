/**
 * Default Flask API origin when the host has not set window.USIS_API_BASE (e.g. via build inject).
 * Kept external so strict Content-Security-Policy (default-src 'self') can allow script-src without 'unsafe-inline'.
 */
(function () {
	var h = window.location.hostname || "";
	var port = String(window.location.port || "");
	var protocol = window.location.protocol || "";
	var pageOrigin = protocol + "//" + h + (port ? ":" + port : "");

	function forceSameOriginOnProduction() {
		if (protocol === "https:" || port === "443" || port === "10000" || port === "") {
			window.USIS_API_BASE = "";
			return true;
		}
		return false;
	}

	var existing = window.USIS_API_BASE;
	if (existing != null && String(existing).trim() !== "") {
		var configured = String(existing).trim().replace(/\/$/, "");
		try {
			var cfgOrigin = new URL(configured).origin;
			if (cfgOrigin && cfgOrigin !== pageOrigin && forceSameOriginOnProduction()) {
				return;
			}
		} catch (e) {
			/* keep configured value for dev / relative overrides */
		}
		return;
	}
	var devPorts = {
		"3000": 1,
		"3001": 1,
		"3002": 1,
		"3003": 1,
		"4173": 1,
		"5173": 1,
		"8080": 1,
	};
	// Gulp BrowserSync proxies /api and /auth to Flask — same-origin keeps session cookies.
	if (devPorts[port] && (h === "localhost" || h === "127.0.0.1")) {
		window.USIS_API_BASE = "";
		return;
	}
	// Production (Render, custom domain): UI and API share one origin — do not point at 127.0.0.1:5000.
	if (protocol === "https:" || port === "443" || port === "10000" || port === "") {
		window.USIS_API_BASE = "";
		return;
	}
	var local = h === "localhost" || h === "127.0.0.1";
	window.USIS_API_BASE = local ? window.location.protocol + "//" + h + ":5000" : "";
})();
