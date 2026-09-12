/**
 * Unhide the header bell when the signed-in user has notifications.
 * List contents and the unread badge are owned by usis-header-notifications.js.
 */
(function (global) {
	"use strict";

	function apiBase() {
		if (typeof global.usisApiBase === "function") return global.usisApiBase();
		if (typeof global.USIS_API_BASE === "string" && global.USIS_API_BASE.trim()) {
			return global.USIS_API_BASE.trim().replace(/\/$/, "");
		}
		var loc = global.location;
		if (!loc) return "";
		if (loc.protocol === "file:") return "http://127.0.0.1:5000";
		var host = loc.hostname || "";
		if (host === "localhost" || host === "127.0.0.1") {
			return (loc.protocol + "//" + host + ":5000").replace(/\/$/, "");
		}
		return "";
	}

	function init() {
		var item = document.getElementById("usis-header-bell-item");
		if (!item) return;
		fetch(apiBase() + "/api/v1/me/notifications", {
			credentials: "include",
			headers: { Accept: "application/json" },
		})
			.then(function (r) {
				if (!r.ok) throw new Error("http");
				return r.json();
			})
			.then(function (data) {
				var items = (data && data.items) || [];
				var unread = Number((data && data.unread) || 0);
				if (!items.length && !unread) {
					item.classList.add("d-none");
					return;
				}
				item.classList.remove("d-none");
			})
			.catch(function () {
				item.classList.add("d-none");
			});
	}

	if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
	else init();
})(typeof window !== "undefined" ? window : this);
