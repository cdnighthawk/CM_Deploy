/**
 * Resolve Flask API root for credentialed fetch (empty string = same origin / Gulp proxy).
 * Must not use ``USIS_API_BASE || fallback`` — empty string is valid.
 */
(function (global) {
	"use strict";

	function usisApiBase() {
		if (typeof global.USIS_API_BASE === "string") {
			return global.USIS_API_BASE.trim().replace(/\/$/, "");
		}
		var loc = global.location;
		if (!loc || loc.protocol === "file:") {
			return "http://127.0.0.1:5000";
		}
		var port = String(loc.port || "");
		var protocol = loc.protocol || "";
		var h = loc.hostname || "";
		var devPorts = { "3000": 1, "3001": 1, "3002": 1, "3003": 1, "4173": 1, "5173": 1, "8080": 1 };
		if (devPorts[port] && (h === "localhost" || h === "127.0.0.1")) {
			return "";
		}
		if (protocol === "https:" || port === "443" || port === "10000" || port === "") {
			return "";
		}
		if (h === "localhost" || h === "127.0.0.1") {
			return (loc.protocol + "//" + h + ":5000").replace(/\/$/, "");
		}
		return "";
	}

	global.usisApiBase = usisApiBase;
})(typeof window !== "undefined" ? window : this);
